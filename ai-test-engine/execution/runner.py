import json
import os
import subprocess
import sys
import time
from pathlib import Path

TEMP_RUNS_DIR = Path(os.getenv("TEMP_RUNS_DIR", "./temp_runs"))
PLAYWRIGHT_PYTHON = os.getenv("PLAYWRIGHT_PYTHON", sys.executable)


def run_script(script: str, app_url: str) -> dict:
    TEMP_RUNS_DIR.mkdir(parents=True, exist_ok=True)

    run_id = f"{os.getpid()}_{int(time.time() * 1000)}"
    script_file = TEMP_RUNS_DIR / f"script_{run_id}.py"
    results_file = TEMP_RUNS_DIR / f"results_{run_id}.json"

    try:
        script_file.write_text(script, encoding="utf-8")

        env = os.environ.copy()
        env["APP_URL"] = app_url
        env["RESULTS_FILE"] = str(results_file)

        start = time.time()
        proc = subprocess.run(
            [PLAYWRIGHT_PYTHON, str(script_file)],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        duration_ms = int((time.time() - start) * 1000)

        if results_file.exists():
            result = json.loads(results_file.read_text(encoding="utf-8"))
            result["duration_ms"] = duration_ms
            return result

        stderr = proc.stderr.strip() or proc.stdout.strip() or "Script produced no results file"
        return {
            "passed": False,
            "step_results": [],
            "error": stderr,
            "duration_ms": duration_ms,
        }

    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "step_results": [],
            "error": "Script timed out after 120s",
            "duration_ms": 120000,
        }
    except Exception as exc:
        return {"passed": False, "step_results": [], "error": str(exc), "duration_ms": 0}
    finally:
        for f in [script_file, results_file]:
            try:
                if f.exists():
                    f.unlink()
            except Exception:
                pass
