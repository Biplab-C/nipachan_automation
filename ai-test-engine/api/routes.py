import asyncio
import json
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from execution.test_file_manager import (
    create_test_case, update_test_case, delete_test_case,
    get_all_test_cases, get_test_case,
)
from execution import bdd_manager
from agents import step_dedup_agent
from graph.workflow import workflow

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=10)
_runs: dict = {}


# ── Test Case CRUD ──────────────────────────────────────────────────────────

class TestCaseCreate(BaseModel):
    name: str
    app_url: str
    steps: list[str]


class TestCaseUpdate(BaseModel):
    name: str = None
    app_url: str = None
    steps: list[str] = None


@router.get("/test-cases")
async def list_test_cases():
    return get_all_test_cases()


@router.post("/test-cases/stream")
async def add_test_case_stream(req: TestCaseCreate):
    """
    Streaming TC creation — yields SSE events for each sub-step so the UI
    can show a live progress dialog. Uses same pipeline as the regular endpoint.
    """
    loop = asyncio.get_running_loop()

    async def generate():
        def _event(status: str, message: str, **extra) -> str:
            payload = {"status": status, "message": message, **extra}
            return f"data: {json.dumps(payload)}\n\n"

        # 1 — Reserve TC_ID
        yield _event("creating", "Creating test case ID…")
        try:
            case = await loop.run_in_executor(
                executor, lambda: create_test_case(name=req.name, steps=req.steps, app_url=req.app_url)
            )
            tc_id = case["id"]
            yield _event("creating_done", f"Test case {tc_id} reserved")
        except Exception as exc:
            yield _event("error", f"Failed to create test case: {exc}")
            return

        # 2 — Step dedup (AI call)
        yield _event("dedup", f"Scanning {len(req.steps)} step(s) for duplicates…")
        gherkin_steps = []
        try:
            existing_patterns = bdd_manager.get_all_step_patterns()
            gherkin_steps = await loop.run_in_executor(
                executor,
                lambda: step_dedup_agent.analyze_steps(req.steps, existing_patterns),
            )
            new_count = sum(1 for s in gherkin_steps if s.get("is_new", True))
            reused = len(gherkin_steps) - new_count
            yield _event("dedup_done", f"{new_count} new step(s) · {reused} reused from existing library")
        except Exception as exc:
            gherkin_steps = _fallback_gherkin(req.steps)
            yield _event("dedup_done", "Step analysis complete (fallback mode)")

        # 3 — Feature file
        yield _event("feature", "Writing Gherkin feature file…")
        feature_file = ""
        try:
            feature_file = bdd_manager.create_feature_file(tc_id, req.name, req.app_url, gherkin_steps)
            yield _event("feature_done", f"Feature file created: {feature_file}")
        except Exception as exc:
            yield _event("feature_done", f"Feature file skipped ({str(exc)[:50]})")

        # 4 — Step definitions
        yield _event("steps", "Creating placeholder step definitions…")
        steps_file = ""
        try:
            if feature_file:
                steps_file = bdd_manager.create_step_definitions(tc_id, req.name, feature_file, gherkin_steps)
                new_count = sum(1 for s in gherkin_steps if s.get("is_new", True))
                yield _event("steps_done", f"Step definitions created: {new_count} placeholder(s)")
            else:
                yield _event("steps_done", "Step definitions skipped (no feature file)")
        except Exception as exc:
            yield _event("steps_done", f"Step definitions skipped ({str(exc)[:50]})")

        # 5 — Data JSON
        yield _event("data", "Creating blank test data JSON…")
        data_file = ""
        try:
            data_file = bdd_manager.create_data_json(tc_id, req.name)
            yield _event("data_done", f"Data file created: {data_file}")
        except Exception as exc:
            yield _event("data_done", f"Data file skipped ({str(exc)[:50]})")

        # 6 — Persist BDD file paths + gherkin steps for execution-time lookup
        update_test_case(tc_id=tc_id, feature_file=feature_file,
                         steps_file=steps_file, data_file=data_file,
                         gherkin_steps=gherkin_steps, write_file=False)
        final_case = get_test_case(tc_id)
        yield _event("done", f"✓ {tc_id} created successfully!", test_case=final_case)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/test-cases", status_code=201)
async def add_test_case(req: TestCaseCreate):
    """
    BDD pipeline on TC creation:
      1. Create registry entry to get TC_ID
      2. Step dedup agent → Gherkin steps (reuse or new)
      3. Feature file written
      4. Step definitions written (placeholders for new steps)
      5. Blank data JSON created
    """
    import logging
    logger = logging.getLogger(__name__)

    # Step 1: Reserve TC_ID in registry first (no files yet)
    case = create_test_case(name=req.name, steps=req.steps, app_url=req.app_url)
    tc_id = case["id"]

    # Step 2: Step dedup + Gherkin conversion
    feature_file = ""
    steps_file = ""
    data_file = ""
    gherkin_steps = []
    try:
        existing_patterns = bdd_manager.get_all_step_patterns()
        gherkin_steps = step_dedup_agent.analyze_steps(req.steps, existing_patterns)
        logger.info("TC %s: %d steps analyzed (%d new)",
                    tc_id, len(gherkin_steps), sum(1 for s in gherkin_steps if s.get("is_new", True)))
    except Exception as exc:
        logger.warning("Step dedup agent failed for %s: %s — falling back to plain placeholders", tc_id, exc)
        # Fallback: treat every step as new, use basic Gherkin
        gherkin_steps = _fallback_gherkin(req.steps)

    # Step 3: Feature file
    try:
        feature_file = bdd_manager.create_feature_file(tc_id, req.name, req.app_url, gherkin_steps)
    except Exception as exc:
        logger.error("Feature file creation failed: %s", exc)

    # Step 4: Step definitions (placeholders for new steps)
    try:
        if feature_file:
            steps_file = bdd_manager.create_step_definitions(tc_id, req.name, feature_file, gherkin_steps)
    except Exception as exc:
        logger.error("Step definitions creation failed: %s", exc)

    # Step 5: Blank data JSON (always)
    try:
        data_file = bdd_manager.create_data_json(tc_id, req.name)
    except Exception as exc:
        logger.error("Data JSON creation failed: %s", exc)

    # Update registry with file paths
    update_test_case(tc_id=tc_id, feature_file=feature_file, steps_file=steps_file,
                     data_file=data_file, write_file=False)
    return get_test_case(tc_id)


def _fallback_gherkin(english_steps: list[str]) -> list[dict]:
    """Basic Gherkin conversion when AI agent is unavailable."""
    result = []
    for i, step in enumerate(english_steps):
        step_lower = step.lower()
        if i == 0 or any(w in step_lower for w in ("navigate", "open", "go to", "launch")):
            kw = "Given"
        elif any(w in step_lower for w in ("verify", "check", "assert", "confirm", "should")):
            kw = "Then" if i == 0 else "And"
        else:
            kw = "When" if i == 1 else "And"
        result.append({
            "english_step": step,
            "gherkin_keyword": kw,
            "gherkin_step_text": f"I {step[0].lower()}{step[1:]}",
            "is_new": True,
            "matched_pattern": "",
            "step_type": "action",
            "anticipated_method": "",
        })
    return result


@router.get("/test-cases/{tc_id}")
async def get_tc(tc_id: str):
    try:
        return get_test_case(tc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Not found")


@router.put("/test-cases/{tc_id}")
async def edit_test_case(tc_id: str, req: TestCaseUpdate):
    try:
        return update_test_case(
            tc_id=tc_id,
            name=req.name,
            steps=req.steps,
            app_url=req.app_url,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Not found")


@router.delete("/test-cases/{tc_id}", status_code=204)
async def remove_test_case(tc_id: str):
    try:
        delete_test_case(tc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Not found")


# ── Execution ───────────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    max_retries: int = 3
    highlight_elements: bool = False


@router.post("/test-cases/{tc_id}/execute")
async def execute_test_case(tc_id: str, req: ExecuteRequest):
    try:
        tc = get_test_case(tc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Not found")

    run_id = str(uuid.uuid4())

    # Build step cache from previously discovered locators
    step_cache = {}
    for step, action in zip(tc["steps"], tc.get("step_actions", [])):
        if action.get("playwright_locator"):
            cache_key = f"{step}::{tc['app_url']}"
            step_cache[cache_key] = action

    initial_state = {
        "run_id": run_id,
        "test_case_id": tc_id,
        "app_url": tc["app_url"],
        "raw_steps": tc["steps"],
        "current_step_index": 0,
        "current_url": "",
        "current_page_title": "",
        "page_elements": [],
        "step_cache": step_cache,
        "retry_hint": "",
        "current_action": {},
        "step_results": [],
        "page_registry": {},
        "current_page_key": "",
        "current_locators": {},
        "error_message": "",
        "highlight_elements": req.highlight_elements,
        "retry_count": 0,
        "max_retries": req.max_retries,
        "status": "queued",
        "final_report": {},
    }

    _runs[run_id] = {"initial_state": initial_state, "status": "queued", "cancelled": False}
    return {"run_id": run_id}


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")

    run_data = _runs[run_id]
    initial_state = run_data["initial_state"]
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _run_sync():
        config = {"configurable": {"thread_id": run_id}}
        try:
            for chunk in workflow.stream(initial_state, config, stream_mode="updates"):
                if _runs[run_id].get("cancelled"):
                    break
                for node_output in chunk.values():
                    _runs[run_id].update(node_output)
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
        except Exception as exc:
            traceback.print_exc()
            _runs[run_id]["status"] = "failed"
            err = {"error": {"status": "failed", "error_message": traceback.format_exc()}}
            loop.call_soon_threadsafe(queue.put_nowait, err)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    loop.run_in_executor(executor, _run_sync)

    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=300)
            except asyncio.TimeoutError:
                break
            if item is None:
                done = {"__done__": True, "status": _runs[run_id].get("status", "completed")}
                yield f"data: {json.dumps(done)}\n\n"
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Not found")
    state = dict(_runs[run_id])
    state.pop("initial_state", None)
    return state


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str):
    """
    Graceful stop: current step finishes, then the workflow routes to finalize.
    The browser closes and files are written cleanly.
    """
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    from execution.execution_signals import request_stop
    request_stop(run_id)
    _runs[run_id]["stop_requested"] = True
    return {"stopping": True, "message": "Stop signal sent — current step will complete then execution will finalize"}


@router.delete("/runs/{run_id}")
async def cancel_run(run_id: str):
    """Immediate cancel — breaks the SSE stream. Use /stop for graceful stop between steps."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Not found")
    _runs[run_id]["cancelled"] = True
    _runs[run_id]["status"] = "cancelled"
    return {"cancelled": True}
