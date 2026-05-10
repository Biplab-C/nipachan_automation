import asyncio
import json
import traceback
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from authoring import test_case_service
from execution import run_service
from execution.test_file_manager import (
    get_all_test_cases,
    get_test_case,
    update_test_case,
    delete_test_case,
)

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=10)


# ── Models ───────────────────────────────────────────────────────────────────

class TestCaseCreate(BaseModel):
    name: str
    app_url: str
    steps: list[str]


class TestCaseUpdate(BaseModel):
    name: str = None
    app_url: str = None
    steps: list[str] = None


class ExecuteRequest(BaseModel):
    pass  # v5 execution needs no extra params


# ── Test Case CRUD ────────────────────────────────────────────────────────────

@router.get("/test-cases")
async def list_test_cases():
    return get_all_test_cases()


@router.get("/test-cases/{tc_id}")
async def get_tc(tc_id: str):
    try:
        return get_test_case(tc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Not found")


@router.post("/test-cases/stream")
async def add_test_case_stream(req: TestCaseCreate):
    """SSE streaming creation — yields progress events for each pipeline stage."""
    loop = asyncio.get_running_loop()

    async def generate():
        def _event(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        gen = test_case_service.create_streaming(
            name=req.name,
            app_url=req.app_url,
            raw_steps=req.steps,
        )

        def _collect():
            return list(gen)

        try:
            events = await loop.run_in_executor(executor, _collect)
            for ev in events:
                yield _event(ev)
        except Exception as exc:
            traceback.print_exc()
            yield _event({"status": "error", "message": str(exc)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/test-cases", status_code=201)
async def add_test_case(req: TestCaseCreate):
    """Synchronous TC creation."""
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        executor,
        lambda: test_case_service.create(
            name=req.name,
            app_url=req.app_url,
            raw_steps=req.steps,
        ),
    )
    return result


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


# ── Execution ─────────────────────────────────────────────────────────────────

@router.post("/test-cases/{tc_id}/execute")
async def execute_test_case(tc_id: str, req: ExecuteRequest = None):
    try:
        tc = get_test_case(tc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Not found")

    steps_file = tc.get("steps_file", "")
    if not steps_file:
        raise HTTPException(status_code=400, detail="No step file found for this test case")

    gs = tc.get("gherkin_steps", [])
    # gherkin_steps may be strings (v5) or dicts (v4) — normalise to strings
    if gs and isinstance(gs[0], dict):
        gs = [f"{s.get('gherkin_keyword','')} {s.get('gherkin_step_text','')}".strip() for s in gs]

    run_id = run_service.start(
        tc_id=tc_id,
        app_url=tc["app_url"],
        steps_file=steps_file,
        raw_steps=tc.get("steps", []),
        gherkin_steps=gs,
    )
    return {"run_id": run_id}


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    if run_service.get(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _run_sync():
        try:
            for chunk in run_service.stream(run_id):
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
        except Exception as exc:
            traceback.print_exc()
            err = json.dumps({"status": "error", "__done__": True, "message": str(exc)})
            loop.call_soon_threadsafe(queue.put_nowait, f"data: {err}\n\n")
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    loop.run_in_executor(executor, _run_sync)

    async def event_generator():
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=300)
            except asyncio.TimeoutError:
                break
            if item is None:
                break
            yield item

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    run = run_service.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Not found")
    return run


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str):
    if run_service.get(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run_service.stop(run_id)
    return {"stopping": True}


@router.delete("/runs/{run_id}")
async def cancel_run(run_id: str):
    if run_service.get(run_id) is None:
        raise HTTPException(status_code=404, detail="Not found")
    run_service.cancel(run_id)
    return {"cancelled": True}
