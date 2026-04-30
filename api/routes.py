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


@router.post("/test-cases", status_code=201)
async def add_test_case(req: TestCaseCreate):
    return create_test_case(name=req.name, steps=req.steps, app_url=req.app_url)


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


@router.delete("/runs/{run_id}")
async def cancel_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Not found")
    _runs[run_id]["cancelled"] = True
    _runs[run_id]["status"] = "cancelled"
    return {"cancelled": True}
