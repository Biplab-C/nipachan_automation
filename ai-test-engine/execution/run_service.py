"""
Manages run lifecycle: create, stream output, stop.
Emits structured SSE events the UI can consume:
  {"execute_step": {"status": "running", "step_results": [...]}}
  {"finalize":     {"status": "passed",  "final_report": {...}}}
  {"__done__": true, "status": "passed"}
"""
import json
import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Generator, List, Optional

logger = logging.getLogger(__name__)

_runs: dict = {}

_NIPACHAN_PREFIX = "NIPACHAN_STEP:"


def _fw_path() -> Path:
    _root = Path(__file__).parent.parent  # ai-test-engine/
    raw = os.getenv("PLAYWRIGHT_FRAMEWORK_PATH", "")
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (_root / p).resolve()
    return (_root.parent / "playwright-framework").resolve()


def start(
    tc_id: str,
    app_url: str,
    steps_file: str,
    raw_steps: List[str] = None,
    gherkin_steps: List[str] = None,
) -> str:
    """Queue a run and return run_id."""
    run_id = str(uuid.uuid4())
    _runs[run_id] = {
        "tc_id": tc_id,
        "app_url": app_url,
        "steps_file": steps_file,
        "raw_steps": raw_steps or [],
        "gherkin_steps": gherkin_steps or [],
        "status": "queued",
        "step_results": [],
        "cancelled": False,
        "process": None,
    }
    return run_id


def stream(run_id: str) -> Generator[str, None, None]:
    """
    Execute the test and yield SSE lines.
    Parses NIPACHAN_STEP: lines from pytest output and emits structured events.
    """
    run = _runs.get(run_id)
    if not run:
        yield _sse({"error": {"status": "error", "error_message": f"run {run_id} not found"}})
        return

    from implementation.implementation_generator import implement_placeholders
    from execution.test_file_manager import update_test_case

    fw = _fw_path()
    tc_id = run["tc_id"]
    app_url = run["app_url"]
    steps_file = run["steps_file"]
    gherkin_steps: List[str] = run["gherkin_steps"]
    total_steps = len(gherkin_steps) if gherkin_steps else len(run["raw_steps"])

    # Locate step file
    step_file = fw / "features" / "steps" / "generated" / steps_file
    if not step_file.exists():
        step_file = fw / "features" / "steps" / steps_file

    # Pre-run: fill supported placeholders
    if step_file.exists():
        n = implement_placeholders(step_file)
        if n:
            yield _sse({"execute_step": {"status": "running", "message": f"Implemented {n} placeholder(s)"}})

    env = os.environ.copy()
    env["APP_URL"] = app_url

    cmd = [
        sys.executable, "-m", "pytest",
        str(step_file),
        "-v", "--tb=short", "--no-header",
        "-s",                          # disable stdout capture so NIPACHAN_STEP lines reach the pipe
        "--override-ini=addopts=",     # skip HTML report and other addopts during API execution
        f"--rootdir={fw}",
    ]

    run["status"] = "running"
    yield _sse({"execute_step": {"status": "running", "message": "pytest-bdd started", "step_results": []}})

    raw_steps: List[str] = run["raw_steps"]
    total_user_steps = len(raw_steps)
    # gherkin may have auto-added steps (e.g. navigation) before user steps
    gherkin_offset = max(0, len(gherkin_steps) - total_user_steps)

    def _user_desc(user_num: int) -> str:
        if 1 <= user_num <= len(raw_steps):
            return raw_steps[user_num - 1]
        return f"Step {user_num}"

    def _gherkin_to_user(gherkin_num: int) -> int:
        return gherkin_num - gherkin_offset

    step_results: List[dict] = []
    failed_user_step: Optional[int] = None
    all_output_lines: List[str] = []

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(fw),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        run["process"] = proc

        for line in proc.stdout:
            if run["cancelled"]:
                proc.kill()
                break

            stripped = line.strip()
            all_output_lines.append(stripped)

            if stripped.startswith(_NIPACHAN_PREFIX):
                try:
                    raw_data = json.loads(stripped[len(_NIPACHAN_PREFIX):])
                    gherkin_num = raw_data["step"]
                    user_num = _gherkin_to_user(gherkin_num)

                    if user_num < 1:
                        # Infrastructure step (e.g. auto-navigation) — only surface on failure
                        if not raw_data.get("passed", True):
                            entry = {
                                "step": 1,
                                "description": _user_desc(1),
                                "passed": False,
                                "error": f"Setup failed: {raw_data.get('error', '')}",
                                "skipped": False,
                                "duration_ms": raw_data.get("duration_ms", 0),
                            }
                            step_results.append(entry)
                            failed_user_step = 1
                            yield _sse({"execute_step": {"status": "running", "step_results": list(step_results)}})
                        continue

                    entry = {
                        "step": user_num,
                        "description": _user_desc(user_num),
                        "passed": raw_data.get("passed", True),
                        "error": raw_data.get("error", ""),
                        "skipped": False,
                        "duration_ms": raw_data.get("duration_ms", 0),
                    }
                    step_results.append(entry)
                    if not entry["passed"]:
                        failed_user_step = user_num
                    yield _sse({"execute_step": {"status": "running", "step_results": list(step_results)}})
                except (json.JSONDecodeError, KeyError):
                    pass

        proc.wait()

        no_steps_ran = len(step_results) == 0

        if no_steps_ran and proc.returncode != 0:
            # pytest failed at collection/import — show real error on step 1
            error_output = "\n".join(l for l in all_output_lines if l)[-3000:]
            step_results.append({
                "step": 1,
                "description": _user_desc(1),
                "passed": False,
                "error": f"pytest collection/setup failed:\n{error_output}",
                "skipped": False,
                "duration_ms": 0,
            })
            for i in range(2, total_user_steps + 1):
                step_results.append({"step": i, "description": _user_desc(i),
                                     "passed": False, "error": "", "skipped": True, "duration_ms": 0})
        elif failed_user_step is not None or proc.returncode != 0:
            reported = {s["step"] for s in step_results}
            max_reported = max(reported) if reported else 0
            for i in range(max_reported + 1, total_user_steps + 1):
                step_results.append({"step": i, "description": _user_desc(i),
                                     "passed": False, "error": "", "skipped": True, "duration_ms": 0})

        # Push final step state to middle panel
        yield _sse({"execute_step": {"status": "running", "step_results": list(step_results)}})

        overall_passed = proc.returncode == 0
        passed_count = sum(1 for s in step_results if s.get("passed"))
        failed_count = sum(1 for s in step_results if not s.get("passed") and not s.get("skipped"))
        skipped_count = sum(1 for s in step_results if s.get("skipped"))
        status = "passed" if overall_passed else "failed"

        final_report = {
            "passed": overall_passed,
            "passed_steps": passed_count,
            "failed_steps": failed_count,
            "skipped_steps": skipped_count,
            "total_steps": total_user_steps or len(step_results),
            "retry_count": 0,
            "step_results": step_results,
        }

        run["status"] = status
        run["returncode"] = proc.returncode
        run["step_results"] = step_results

        try:
            update_test_case(tc_id=tc_id, status=status, write_file=False)
        except Exception:
            pass

        # Finalize includes step_results so handleEvent calls updateLiveSteps
        yield _sse({"finalize": {"status": status, "step_results": list(step_results), "final_report": final_report}})
        yield _sse({"__done__": True, "status": status})

    except Exception as exc:
        logger.exception("run_service stream error")
        run["status"] = "error"
        yield _sse({"error": {"status": "error", "error_message": str(exc)}})
        yield _sse({"__done__": True, "status": "error"})


def stop(run_id: str) -> bool:
    run = _runs.get(run_id)
    if not run:
        return False
    run["cancelled"] = True
    proc = run.get("process")
    if proc:
        proc.terminate()
    run["status"] = "stopped"
    return True


def cancel(run_id: str) -> bool:
    return stop(run_id)


def get(run_id: str) -> Optional[dict]:
    run = _runs.get(run_id)
    if not run:
        return None
    safe = {k: v for k, v in run.items() if k != "process"}
    return safe


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"
