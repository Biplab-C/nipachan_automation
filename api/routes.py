import asyncio
import json
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from graph.workflow import workflow

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=10)
_runs: dict[str, dict] = {}


class RunRequest(BaseModel):
    steps: list[str]
    app_url: str
    selector_hints: dict = {}
    max_retries: int = 3


@router.post("/run")
async def start_run(req: RunRequest):
    run_id = str(uuid.uuid4())
    initial_state = {
        "run_id": run_id,
        "raw_steps": req.steps,
        "app_url": req.app_url,
        "selector_hints": req.selector_hints,
        "parsed_actions": [],
        "generated_script": "",
        "execution_result": {},
        "step_results": [],
        "error_message": "",
        "fix_suggestion": {},
        "retry_count": 0,
        "max_retries": req.max_retries,
        "status": "queued",
        "final_report": {},
    }
    _runs[run_id] = {"initial_state": initial_state, "status": "queued", "cancelled": False}
    return {"run_id": run_id}


@router.get("/run/{run_id}/stream")
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
            error_chunk = {"error": {"status": "failed", "error_message": traceback.format_exc()}}
            loop.call_soon_threadsafe(queue.put_nowait, error_chunk)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    loop.run_in_executor(executor, _run_sync)

    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=180)
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


@router.get("/run/{run_id}")
async def get_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    state = dict(_runs[run_id])
    state.pop("initial_state", None)
    return state


@router.delete("/run/{run_id}")
async def cancel_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    _runs[run_id]["cancelled"] = True
    _runs[run_id]["status"] = "cancelled"
    return {"cancelled": True}


@router.get("/runs")
async def list_runs():
    return [
        {
            "run_id": k,
            "status": v.get("status"),
            "passed": v.get("final_report", {}).get("passed") if v.get("final_report") else None,
        }
        for k, v in _runs.items()
    ]
