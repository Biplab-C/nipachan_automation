from agents.nlp_parser import parse_steps
from agents.code_generator import generate_script
from agents.error_analyzer import analyze_error
from execution.runner import run_script
from graph.state import TestWorkflowState


def parse_node(state: TestWorkflowState) -> dict:
    parsed = parse_steps(state["raw_steps"], state.get("selector_hints", {}))
    return {"parsed_actions": parsed, "status": "parsing"}


def generate_node(state: TestWorkflowState) -> dict:
    script = generate_script(state["parsed_actions"], state["app_url"])
    return {"generated_script": script, "status": "generating"}


def execute_node(state: TestWorkflowState) -> dict:
    result = run_script(state["generated_script"], state["app_url"])
    return {
        "execution_result": result,
        "step_results": result.get("step_results", []),
        "error_message": result.get("error", ""),
        "status": "running",
    }


def analyze_error_node(state: TestWorkflowState) -> dict:
    failed_steps = [s for s in state.get("step_results", []) if not s.get("passed")]
    suggestion = analyze_error(
        state.get("error_message", ""),
        state.get("generated_script", ""),
        failed_steps,
    )
    update = {
        "fix_suggestion": suggestion,
        "retry_count": state.get("retry_count", 0) + 1,
        "status": "retrying",
    }
    if suggestion.get("patched_script"):
        update["generated_script"] = suggestion["patched_script"]
    return update


def finalize_node(state: TestWorkflowState) -> dict:
    step_results = state.get("step_results", [])
    passed = all(s.get("passed") for s in step_results) if step_results else False
    report = {
        "run_id": state["run_id"],
        "passed": passed,
        "total_steps": len(step_results),
        "passed_steps": sum(1 for s in step_results if s.get("passed")),
        "failed_steps": sum(1 for s in step_results if not s.get("passed")),
        "retry_count": state.get("retry_count", 0),
        "step_results": step_results,
        "error_message": state.get("error_message", ""),
    }
    return {
        "final_report": report,
        "status": "completed" if passed else "failed",
    }
