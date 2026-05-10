"""
Orchestrates the full test case creation pipeline:
  1. Reserve TC ID in test_registry.json (UI index only)
  2. Scan existing step definitions
  3. Normalize raw steps via LLM
  4. Match normalized steps against catalog
  5. Write feature file
  6. Write step file (placeholders for unmatched steps)
  7. Write blank data JSON
  8. Update registry with file paths
"""
import logging
from pathlib import Path
from typing import Generator, List, Optional

from bdd import data_json_writer, feature_writer, step_file_writer
from bdd.step_definition_scanner import scan
from bdd.step_matcher import match
from authoring.normalization_service import normalize
from core.models import NormalizedStep, MatchResult
from providers.llm.base import LLMProvider
from execution.test_file_manager import (
    create_test_case as _registry_create,
    update_test_case as _registry_update,
    get_test_case,
)

logger = logging.getLogger(__name__)


def _fw_path() -> Path:
    import os
    _root = Path(__file__).parent.parent  # ai-test-engine/
    raw = os.getenv("PLAYWRIGHT_FRAMEWORK_PATH", "")
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (_root / p).resolve()
    return (_root.parent / "playwright-framework").resolve()


def create(
    name: str,
    app_url: str,
    raw_steps: List[str],
    llm: Optional[LLMProvider] = None,
) -> dict:
    """Synchronous creation. Returns final test case dict."""
    events = list(_pipeline(name, app_url, raw_steps, llm))
    # Last event contains the test case
    for ev in reversed(events):
        if ev.get("status") == "done":
            return ev.get("test_case", {})
    return {}


def create_streaming(
    name: str,
    app_url: str,
    raw_steps: List[str],
    llm: Optional[LLMProvider] = None,
) -> Generator[dict, None, None]:
    """Streaming creation — yields progress events."""
    yield from _pipeline(name, app_url, raw_steps, llm)


def _pipeline(name, app_url, raw_steps, llm) -> Generator[dict, None, None]:
    fw = _fw_path()

    # 1. Reserve TC ID
    yield {"status": "creating", "message": "Reserving test case ID…"}
    case = _registry_create(name=name, steps=raw_steps, app_url=app_url)
    tc_id = case["id"]
    yield {"status": "creating_done", "message": f"{tc_id} reserved"}

    # 2. Scan step definitions
    yield {"status": "scanning", "message": "Scanning existing step definitions…"}
    catalog = scan(fw)
    yield {"status": "scanning_done", "message": f"{len(catalog)} step(s) in catalog"}

    # 3. Normalize
    yield {"status": "normalizing", "message": f"Normalizing {len(raw_steps)} step(s)…"}
    try:
        normalized = normalize(raw_steps, catalog, llm)
    except Exception as exc:
        yield {"status": "error", "message": f"Normalization failed: {exc}"}
        return
    needs_review = sum(1 for s in normalized if s.needs_review)
    yield {"status": "normalizing_done", "message": f"{len(normalized)} step(s) normalized · {needs_review} need review"}

    # 3b. Auto-prepend navigation step if LLM didn't include one
    if not any(s.category == "navigation" for s in normalized):
        from core.models import NormalizedStep as _NS
        nav = _NS(
            raw_step="navigate",
            keyword="Given",
            step_text="I am on the application home page",
            step_pattern="I am on the application home page",
            category="navigation",
            parameters={},
            function_name="i_am_on_the_application_home_page",
            confidence=1.0,
            needs_review=False,
        )
        normalized.insert(0, nav)

    # 4. Match
    yield {"status": "matching", "message": "Matching against step catalog…"}
    results: List[MatchResult] = [match(s, catalog) for s in normalized]
    reused = sum(1 for r in results if r.matched)
    new_count = len(results) - reused
    yield {"status": "matching_done", "message": f"{reused} reused · {new_count} new placeholder(s)"}

    # 5. Feature file
    yield {"status": "feature", "message": "Writing feature file…"}
    feature_file = ""
    try:
        feature_file = feature_writer.write(fw, tc_id, name, app_url, normalized)
        yield {"status": "feature_done", "message": f"Feature file: {feature_file}"}
    except Exception as exc:
        yield {"status": "feature_done", "message": f"Feature file skipped ({exc})"}

    # 6. Step file
    yield {"status": "steps", "message": "Writing step definitions…"}
    steps_file = ""
    try:
        if feature_file:
            steps_file = step_file_writer.write(fw, tc_id, name, feature_file, normalized, results)
            yield {"status": "steps_done", "message": f"Step file: {steps_file}"}
        else:
            yield {"status": "steps_done", "message": "Step file skipped (no feature file)"}
    except Exception as exc:
        yield {"status": "steps_done", "message": f"Step file skipped ({exc})"}

    # 7. Data JSON
    yield {"status": "data", "message": "Creating blank data JSON…"}
    data_file = ""
    try:
        data_file = data_json_writer.write(fw, tc_id, name)
        yield {"status": "data_done", "message": f"Data file: {data_file}"}
    except Exception as exc:
        yield {"status": "data_done", "message": f"Data file skipped ({exc})"}

    # 8. Update registry — store gherkin_steps as display strings for the UI
    gherkin_step_strings = [f"{s.keyword} {s.step_text}" for s in normalized]
    _registry_update(
        tc_id=tc_id,
        feature_file=feature_file,
        steps_file=steps_file,
        data_file=data_file,
        gherkin_steps=gherkin_step_strings,
        write_file=False,
    )
    final = get_test_case(tc_id)
    yield {"status": "done", "message": f"{tc_id} created successfully", "test_case": final}
