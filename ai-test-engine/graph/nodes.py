import logging
import re
import time
import traceback

import agents.page_object_generator as pog
import agents.step_analyzer as sa
import execution.framework_manager as fm
import execution.bdd_manager as bdd
import locator_intelligence.locator_inventory_manager as lim
from locator_intelligence.action_planner import build_action_plan, ActionPlan
from locator_intelligence.models import PageLocatorInventory
from execution.browser_controller import get_browser, close_browser, BrowserDeadError, _browsers as _browsers_ref
from execution.execution_signals import clear_stop, is_stop_requested
from execution.test_file_manager import update_test_case, get_test_case
from execution import run_artifacts
from graph.state import TestWorkflowState

# Playwright error phrases that mean the browser process is gone
_BROWSER_DEAD_PHRASES = (
    "target closed",
    "browser has been closed",
    "browser closed",
    "page closed",
    "context or browser has been closed",
    "connection refused",
    "session deleted because of page crash",
    "execution context was destroyed",
    "net::err",
)


def _is_browser_dead(exc: Exception) -> bool:
    msg = str(exc).lower()
    return isinstance(exc, BrowserDeadError) or any(p in msg for p in _BROWSER_DEAD_PHRASES)

logger = logging.getLogger(__name__)


# ── 1. Launch browser ─────────────────────────────────────────────────────────

def launch_browser_node(state: TestWorkflowState) -> dict:
    logger.info("Launching browser for run %s", state["run_id"])
    ctrl = get_browser(state["run_id"], headless=False, highlight=state.get("highlight_elements", False))
    ctrl.navigate(state["app_url"])

    # Set up run artifacts directory
    run_id = state["run_id"]
    artifacts_dir = str(run_artifacts.get_run_dir(run_id))
    run_artifacts.cleanup_old_runs(keep_last=20)

    return {
        "current_url": ctrl.current_url(),
        "current_page_title": ctrl.get_page_title(),
        "step_results": [],
        "step_cache": state.get("step_cache", {}),
        "page_registry": state.get("page_registry", {}),
        "current_locators": {},
        "current_inventory": {},
        "action_plan": {},
        "run_artifacts_dir": artifacts_dir,
        "retry_count": 0,
        "retry_hint": "",
        "status": "running",
    }


# ── 2. Inspect page ───────────────────────────────────────────────────────────

def inspect_page_node(state: TestWorkflowState) -> dict:
    try:
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
    except Exception as exc:
        if _is_browser_dead(exc):
            logger.warning("Browser dead during page inspection — forcing finalize")
            # Signal finalize by exhausting retries
            return {
                "page_elements": [],
                "retry_count": state.get("max_retries", 3),
                "error_message": f"Browser closed: {exc}",
                "status": "failed",
            }
        raise


# ── 3. Generate / load page object ────────────────────────────────────────────

def generate_page_object_node(state: TestWorkflowState) -> dict:
    url = state.get("current_url", "")
    title = state.get("current_page_title", "")

    # --- Locator Intelligence: build / reuse inventory ---
    try:
        ctrl = get_browser(state["run_id"])
        page = ctrl.page

        inventory: PageLocatorInventory = lim.build_inventory(page, url, title)
        locators_dict = lim.get_locators_dict(inventory)
        inventory_dict = inventory.to_dict()
        logger.info(
            "Inventory ready for %s: %d locators (%d validated)",
            inventory.page_key,
            len(inventory.locators),
            len(inventory.get_validated()),
        )
    except Exception as exc:
        logger.warning("Locator inventory build failed: %s — falling back to registry", exc)
        inventory = None
        inventory_dict = {}
        locators_dict = {}

    # --- Backward-compat: check framework registry for existing page class ---
    existing = fm.get_page_class_for_url(url)
    if existing:
        # Support both old format (url_key) and new locator-intelligence format (page_key)
        page_key_field = existing.get("url_key") or existing.get("page_key", "")
        if not page_key_field:
            page_key_field = fm._url_key(url)
        logger.info("Reusing page class %s for %s", existing.get("class_name", ""), url)
        # Merge inventory locators into existing page class if we got new ones
        if locators_dict and inventory:
            merged_locators = {**existing.get("locators", {}), **locators_dict}
            existing["locators"] = merged_locators
        registry = {**state.get("page_registry", {}), page_key_field: existing}
        return {
            "current_page_key": page_key_field,
            "page_registry": registry,
            "current_locators": existing.get("locators", {}),
            "current_inventory": inventory_dict,
            "status": "analyzing",
        }

    logger.info("Generating new page object for %s", url)
    try:
        if locators_dict and inventory:
            # Use inventory locators directly — no LLM needed
            page_info = fm.create_page_class(
                url=url,
                class_name=inventory.class_name,
                locators=locators_dict,
            )
        else:
            # Fall back to LLM-based generation
            elements = state.get("page_elements", [])
            result = pog.generate_page_locators(url=url, page_title=title, elements=elements)
            page_info = fm.create_page_class(
                url=url,
                class_name=result["class_name"],
                locators=result["locators"],
            )
            locators_dict = result["locators"]

        registry = {**state.get("page_registry", {}), page_info["url_key"]: page_info}
        return {
            "current_page_key": page_info["url_key"],
            "page_registry": registry,
            "current_locators": page_info["locators"],
            "current_inventory": inventory_dict,
            "status": "analyzing",
        }
    except Exception as exc:
        logger.warning("Page object generation failed: %s — falling back to raw elements", exc)
        return {
            "current_page_key": "",
            "current_locators": {},
            "current_inventory": inventory_dict,
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
        return {
            "current_action": state["step_cache"][cache_key],
            "action_plan": {},
            "status": "analyzing",
        }

    logger.info("Analyzing step %d: %s", idx + 1, step)

    # --- Try Locator Intelligence action planner first ---
    action_plan_dict = {}
    action = None

    inventory_dict = state.get("current_inventory", {})
    if inventory_dict and not retry_hint:
        try:
            inventory = PageLocatorInventory.from_dict(inventory_dict)
            plan = build_action_plan(step, inventory)
            if plan.is_executable() and plan.overall_confidence >= 0.75:
                logger.info(
                    "Action plan from inventory: intent=%s confidence=%.2f actions=%d",
                    plan.intent, plan.overall_confidence, len(plan.atomic_actions),
                )
                action_plan_dict = plan.to_dict()
                # Convert first atomic action to legacy action format for backward-compat
                first = plan.atomic_actions[0]
                action = {
                    "action": first.action_type,
                    "playwright_locator": first.locator_selector,
                    "value": first.value,
                    "method_name": _derive_method_name_from_plan(plan),
                    "locator_constant": first.locator_name,
                    "is_existing_method": False,
                    "reasoning": f"inventory-based plan: {plan.intent}",
                }
            else:
                logger.info(
                    "Action plan confidence too low (%.2f) or no actions — falling back to LLM",
                    plan.overall_confidence,
                )
        except Exception as exc:
            logger.warning("Action planner failed: %s — falling back to LLM", exc)

    # --- Fall back to existing LLM-based step analysis ---
    if action is None:
        try:
            if locators:
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
            action = {
                "action": "click",
                "playwright_locator": "",
                "value": "",
                "method_name": "unknown",
                "locator_constant": "",
                "is_existing_method": False,
                "reasoning": str(exc),
            }

    # Save action plan artifact if we have one
    if action_plan_dict:
        try:
            run_artifacts.save_action_plan(state["run_id"], idx, action_plan_dict)
        except Exception:
            pass

    return {
        "current_action": action,
        "action_plan": action_plan_dict,
        "status": "analyzing",
    }


def _derive_method_name_from_plan(plan: ActionPlan) -> str:
    """Derive a snake_case method name from the action plan."""
    intent = plan.intent.lower().replace(" ", "_")
    if plan.atomic_actions:
        first = plan.atomic_actions[0]
        if first.value:
            value_slug = re.sub(r"[^a-z0-9]", "_", first.value.lower())[:20].strip("_")
            return f"{intent}_{value_slug}"
    return intent


# ── 5. Execute step ───────────────────────────────────────────────────────────

def execute_step_node(state: TestWorkflowState) -> dict:
    idx = state["current_step_index"]
    step = state["raw_steps"][idx]
    action = state.get("current_action", {})
    action_plan_dict = state.get("action_plan", {})
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

    # --- Determine whether to use atomic action plan or single action ---
    atomic_actions = action_plan_dict.get("atomic_actions", []) if action_plan_dict else []
    use_atomic = bool(atomic_actions) and len(atomic_actions) > 0

    try:
        ctrl = get_browser(state["run_id"])  # Re-fetch in case state changed

        if use_atomic:
            # Execute each atomic action in sequence; stop on first failure
            logger.info("Executing %d atomic actions for step %d", len(atomic_actions), idx + 1)
            for atom_idx, atom in enumerate(atomic_actions):
                atom_type = atom.get("action_type", "click")
                atom_selector = atom.get("locator_selector", "")
                atom_value = atom.get("value", "")
                logger.info(
                    "  Atomic [%d/%d]: %s → %s (value=%r)",
                    atom_idx + 1, len(atomic_actions), atom_type, atom_selector, atom_value,
                )
                ctrl.execute_action(
                    action=atom_type,
                    locator=atom_selector,
                    value=atom_value,
                )
            # Use last atomic action's details for result reporting
            last_atom = atomic_actions[-1]
            result["action"] = last_atom.get("action_type", action.get("action", "click"))
            result["playwright_locator"] = last_atom.get("locator_selector", action.get("playwright_locator", ""))
            result["locator_constant"] = last_atom.get("locator_name", action.get("locator_constant", ""))
        else:
            # Single action path (legacy)
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
        if _is_browser_dead(exc):
            logger.warning("Browser dead on step %d — routing to finalize immediately: %s", idx + 1, exc)
            # Exhaust retries so route_after_execute sends us to finalize
            new_retry = state.get("max_retries", 3)
        else:
            logger.warning("Step %d FAILED: %s", idx + 1, exc)
            new_retry += 1
        try:
            # Best-effort screenshot — may also fail if browser is dead
            ctrl = _browsers_ref.get(state["run_id"])
            if ctrl and ctrl.is_alive():
                result["screenshot"] = ctrl.screenshot_b64()
        except Exception:
            pass

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
    run_id = state["run_id"]
    passed = bool(step_results) and all(s.get("passed") for s in step_results)

    # Resolve url_key for any steps that have current_url but empty url_key
    # (needed for write_test_file lookups — page class still exists, just no methods added)
    for r in step_results:
        if not r.get("url_key") and r.get("current_url"):
            info = fm.get_page_class_for_url(r["current_url"])
            if info:
                r["url_key"] = info["url_key"]
                r["page_class"] = r.get("page_class") or info.get("class_name", "")
                r["page_filename"] = r.get("page_filename") or info.get("filename", "")

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
            {
                "playwright_locator": r.get("playwright_locator", ""),
                "action": r.get("action", ""),
                "value": r.get("value", ""),
            }
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

    # 2. Update BDD step definitions with locator-based WebActions implementations
    try:
        tc_info = get_test_case(tc_id)
        steps_file = tc_info.get("steps_file", "")
        gherkin_steps = tc_info.get("gherkin_steps", [])  # Ordered list matching raw_steps
        step_registry = bdd._load_registry()

        if steps_file and gherkin_steps:
            for i, r in enumerate(step_results):
                if not r.get("passed"):
                    continue
                if not r.get("locator_constant") or not r.get("page_class"):
                    continue
                if i >= len(gherkin_steps):
                    continue

                # Find the registered func_name via the Gherkin step text (index-matched)
                gstep = gherkin_steps[i]
                step_text = gstep.get("gherkin_step_text", "")
                pattern_key = bdd._normalize(step_text)
                reg_entry = step_registry.get(pattern_key, {})
                func_name = reg_entry.get("function_name", "")

                if not func_name:
                    # Fallback: derive from step text as create_step_definitions does
                    func_name = re.sub(r'"[^"]+"', "value", step_text)
                    func_name = re.sub(r"[^a-z0-9]+", "_", func_name.lower()).strip("_")[:60]

                page_mod = r.get("page_filename", "").replace(".py", "")
                bdd.update_step_definition(
                    steps_filename=steps_file,
                    func_name=func_name,
                    locator_constant=r.get("locator_constant", ""),
                    action=r.get("action", "click"),
                    value=r.get("value", ""),
                    page_class=r["page_class"],
                    page_module=page_mod,
                )
                bdd.mark_step_implemented(
                    step_text=step_text,
                    page_class=r["page_class"],
                    method_name=r.get("locator_constant", ""),
                    playwright_locator=r.get("playwright_locator", ""),
                )
    except Exception:
        logger.warning("BDD step update failed:\n%s", traceback.format_exc())

    # 3. Write framework page-object files (kept for direct pytest runs)
    data_filename = None
    test_filename = ""
    try:
        data_filename = fm.write_test_data(tc_id, tc_name, raw_steps, step_results)
        test_filename = fm.write_test_file(tc_id, tc_name, raw_steps, step_results, data_filename)
    except Exception:
        logger.warning("Framework file writing failed:\n%s", traceback.format_exc())

    # 4. Save run artifacts: execution log and final action plan summary
    try:
        log_entries = [
            {
                "step": r.get("step"),
                "description": r.get("description", ""),
                "action": r.get("action", ""),
                "locator_constant": r.get("locator_constant", ""),
                "playwright_locator": r.get("playwright_locator", ""),
                "value": r.get("value", ""),
                "passed": r.get("passed", False),
                "error": r.get("error"),
                "duration_ms": r.get("duration_ms", 0),
            }
            for r in step_results
        ]
        run_artifacts.save_execution_log(run_id, log_entries)

        # Save inventory diff info
        inventory_dict = state.get("current_inventory", {})
        if inventory_dict:
            page_key = inventory_dict.get("page_key", "")
            num_locators = len(inventory_dict.get("locators", {}))
            run_artifacts.save_inventory_diff(run_id, [page_key] if page_key else [], num_locators)
    except Exception:
        logger.warning("Run artifact saving failed:\n%s", traceback.format_exc())

    clear_stop(state["run_id"])   # Clean up any stop signal for this run
    close_browser(state["run_id"])

    report = {
        "run_id": run_id,
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
            "run_dir": state.get("run_artifacts_dir", ""),
        },
    }

    return {
        "final_report": report,
        "status": "completed" if passed else "failed",
    }
