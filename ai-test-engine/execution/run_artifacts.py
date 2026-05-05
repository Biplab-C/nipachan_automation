"""Manages temporary run artifacts for evidence and debugging."""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_ai_root = Path(__file__).parent.parent
_TEMP_RUNS = _ai_root / "temp_runs"


def get_run_dir(run_id: str) -> Path:
    d = _TEMP_RUNS / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_action_plan(run_id: str, step_index: int, plan: dict):
    d = get_run_dir(run_id)
    filepath = d / f"action_plan_step_{step_index}.json"
    filepath.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def save_execution_log(run_id: str, log_entries: list[dict]):
    d = get_run_dir(run_id)
    filepath = d / "execution_log.json"
    payload = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(),
        "steps": log_entries,
    }
    filepath.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_inventory_diff(run_id: str, new_pages: list[str], updated_locators: int):
    d = get_run_dir(run_id)
    filepath = d / "locator_inventory_diff.json"
    payload = {
        "run_id": run_id,
        "new_pages": new_pages,
        "updated_locators": updated_locators,
        "generated_at": datetime.now().isoformat(),
    }
    filepath.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def cleanup_old_runs(keep_last: int = 20):
    """Remove oldest run dirs, keeping only the most recent N."""
    if not _TEMP_RUNS.exists():
        return
    runs = sorted(_TEMP_RUNS.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in runs[keep_last:]:
        try:
            import shutil
            shutil.rmtree(old)
        except Exception:
            pass
