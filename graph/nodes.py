import logging
import time
import traceback

import agents.page_object_generator as pog
import agents.step_analyzer as sa
import execution.framework_manager as fm
from execution.browser_controller import get_browser, close_browser
from execution.test_file_manager import update_test_case
from graph.state import TestWorkflowState

logger = logging.getLogger(__name__)


# ── 1. Launch browser ─────────────────────────────────────────────────────────

def launch_browser_node(state: TestWorkflowState) -> dict:
    logger.info("Launching browser for run %s", state["run_id"])
    ctrl = get_browser(state["run_id"], headless=False, highlight=state.get("highlight_elements", False))
    ctrl.navigate(state["app_url"])
    return {
        "current_url": ctrl.current_url(),
        "current_page_title": ctrl.get_page_title(),
        "step_results": [],
        "step_cache": state.get("step_cache", {}),
        "page_registry": state.get("page_registry", {}),
        "current_locators": {},
        "retry_count": 0,
        "retry_hint": "",
        "status": "running",
    }


# ── 2. Inspect page ───────────────────────────────────────────────────────────

def inspect_page_node(state: TestWorkflowState) -> dict:
    ctrl = get_browser(state["run_id"])
    elements = ctrl.get_page_elements()
    url = ctrl.current_url()
    title = ctrl.get_page_title()
    logger.info("Inspected '%s' — %d elements", url, len(elements))
    return {
        "page_elements": elements,
        "current_url": url,
        "current_page_title": title,
        "status": "inspecting",
    }


# ── 3. Generate / load page object ────────────────────────────────────────────

def generate_page_object_node(state: TestWorkflowState) -> dict:
    url = state.get("current_url", "")
    title = state.get("current_page_title", "")
    elements = state.get("page_elements", [])

    existing = fm.get_page_class_for_url(url)
    if existing:
        logger.info("Reusing page class %s for %s", existing["class_name"], url)
        registry = {**state.get("page_registry", {}), existing["url_key"]: existing}
        return {
            "current_page_key": existing["url_key"],
            "page_registry": registry,
            "current_locators": existing.get("locators", {}),
            "status": "analyzing",
        }

    logger.info("Generating new page object for %s", url)
    try:
        result = pog.generate_page_locators(url=url, page_title=title, elements=elements)
        page_info = fm.create_page_class(
            url=url,
            class_name=result["class_name"],
            locators=result["locators"],
        )
        registry = {**state.get("page_registry", {}), page_info["url_key"]: page_info}
        return {
            "current_page_key": page_info["url_key"],
            "page_registry": registry,
            "current_locators": page_info["locators"],
            "status": "analyzing",
        }
    except Exception as exc:
        logger.warning("Page object generation failed: %s — falling back to raw elements", exc)
        return {
            "current_page_key": "",
            "current_locators": {},
            "status": "analyzing",
        }


# ── 4. Analyze step ───────────────────────────────────────────────────────────

def analyze_step_node(state: TestWorkflowState) -> dict:
    idx = state["current_step_index"]
    step = state["raw_steps"][idx]
    locators = state.get("current_locators", {})
    page_key = state.get("current_page_key", "")
    retry_hint = state.get("retry_hint", "")

    cache_key = f"{step}::{state.get('current_url', '')}"
    if cache_key in state.get("step_cache", {}) and not retry_hint:
        logger.info("Cache hit for step: %s", step)
        return {"current_action": state["step_cache"][cache_key], "status": "analyzing"}

    logger.info("Analyzing step %d: %s", idx + 1, step)
    try:
        if locators:
            # Pass existing method_map so AI can reuse existing methods
            method_map = fm.get_method_map(page_key)
            action = sa.analyze_step_framework(
                step=step,
                locators_available=locators,
                current_url=state.get("current_url", ""),
                existing_methods=method_map,
                retry_hint=retry_hint,
            )
        else:
            action = sa.analyze_step(
                step=step,
                page_elements=state.get("page_elements", []),
                current_url=state.get("current_url", ""),
                retry_hint=retry_hint,
            )
    except Exception as exc:
        logger.error("Step analysis failed: %s", exc)
        action = {"action": "click", "playwright_locator": "", "value": "", "method_name": "unknown",
                  "locator_constant": "", "is_existing_method": False, "reasoning": str(exc)}

    return {"current_action": action, "status": "analyzing"}


# ── 5. Execute step ───────────────────────────────────────────────────────────

def execute_step_node(state: TestWorkflowState) -> dict:
    idx = state["current_step_index"]
    step = state["raw_steps"][idx]
    action = state.get("current_action", {})
    ctrl = get_browser(state["run_id"])
    page_key = state.get("current_page_key", "")
    page_info = state.get("page_registry", {}).get(page_key, {})

    logger.info("Executing step %d: %s | %s → %s",
                idx + 1, step, action.get("action"), action.get("playwright_locator"))

    result = {
        "step": idx + 1,
        "description": step,
        "url_key": page_key,
        "current_url": state.get("current_url", ""),   # kept as fallback for write_test_file
        "page_class": page_info.get("class_name", ""),
        "page_filename": page_info.get("filename", ""),
        "method_name": action.get("method_name", ""),
        "locator_constant": action.get("locator_constant", ""),
        "playwright_locator": action.get("playwright_locator", ""),
        "action": action.get("action", "click"),
        "value": action.get("value", ""),
        "is_existing_method": action.get("is_existing_method", False),
        "passed": False,
        "error": None,
        "screenshot": None,
        "duration_ms": 0,
    }

    start = time.time()
    new_cache = dict(state.get("step_cache", {}))
    new_retry = state.get("retry_count", 0)

    try:
        ctrl.execute_action(
            action=action.get("action", "click"),
            locator=action.get("playwright_locator", ""),
            value=action.get("value", ""),
        )
        result["passed"] = True
        result["screenshot"] = ctrl.screenshot_b64()
        new_cache[f"{step}::{state.get('current_url', '')}"] = action
        new_retry = 0
    except Exception as exc:
        result["error"] = str(exc)
        logger.warning("Step %d FAILED: %s", idx + 1, exc)
        try:
            result["screenshot"] = ctrl.screenshot_b64()
        except Exception:
            pass
        new_retry += 1

    result["duration_ms"] = int((time.time() - start) * 1000)

    step_results = [r for r in state.get("step_results", []) if r["step"] != idx + 1]
    step_results.append(result)

    if result["passed"]:
        next_idx = idx + 1
        retry_hint = ""
    else:
        next_idx = idx
        retry_hint = result["error"] or "Unknown error"

    return {
        "step_results": step_results,
        "current_step_index": next_idx,
        "retry_count": new_retry,
        "retry_hint": retry_hint,
        "step_cache": new_cache,
        "status": "running",
    }


# ── 6. Finalize ───────────────────────────────────────────────────────────────

def finalize_node(state: TestWorkflowState) -> dict:
    step_results = state.get("step_results", [])
    raw_steps = state.get("raw_steps", [])
    tc_id = state["test_case_id"]
    passed = bool(step_results) and all(s.get("passed") for s in step_results)

    # Add discovered methods to page classes; dedup returns the actual name used
    for r in step_results:
        if not (r.get("passed") and r.get("method_name") and r.get("locator_constant")):
            continue
        # Always attempt add — add_method_to_page_class deduplicates via method_map safely

        # Resolve url_key — fall back to current_url lookup if empty
        url_key = r.get("url_key", "")
        if not url_key and r.get("current_url"):
            info = fm.get_page_class_for_url(r["current_url"])
            if info:
                url_key = info["url_key"]
                r["url_key"] = url_key  # Patch for write_test_file

        if not url_key:
            continue

        actual_name = fm.add_method_to_page_class(
            url_key=url_key,
            method_name=r["method_name"],
            locator_constant=r["locator_constant"],
            action=r.get("action", "click"),
            value=r.get("value", ""),
        )
        r["method_name"] = actual_name  # Use deduplicated name in test file

    # Write test data JSON
    try:
        from execution.test_file_manager import get_test_case
        tc = get_test_case(tc_id)
        tc_name = tc.get("name", tc_id)
    except Exception:
        tc_name = tc_id

    # 1. Update registry only (write_file=False prevents raw-locator overwrite)
    try:
        step_actions = [
            {"playwright_locator": r.get("playwright_locator", ""), "action": r.get("action", ""), "value": r.get("value", "")}
            for r in step_results
        ]
        update_test_case(
            tc_id=tc_id,
            step_actions=step_actions,
            status="passed" if passed else "failed",
            write_file=False,
        )
    except Exception:
        pass

    # 2. Write page-object test file last so it is never overwritten
    data_filename = None
    test_filename = ""
    try:
        data_filename = fm.write_test_data(tc_id, tc_name, raw_steps, step_results)
        test_filename = fm.write_test_file(tc_id, tc_name, raw_steps, step_results, data_filename)
    except Exception:
        logger.warning("Framework file writing failed:\n%s", traceback.format_exc())

    close_browser(state["run_id"])

    report = {
        "run_id": state["run_id"],
        "test_case_id": tc_id,
        "passed": passed,
        "total_steps": len(raw_steps),
        "passed_steps": sum(1 for s in step_results if s.get("passed")),
        "failed_steps": sum(1 for s in step_results if not s.get("passed")),
        "retry_count": state.get("retry_count", 0),
        "step_results": step_results,
        "artifacts": {
            "test_file": test_filename,
            "data_file": data_filename,
        },
    }

    return {
        "final_report": report,
        "status": "completed" if passed else "failed",
    }
