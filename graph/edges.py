from graph.state import TestWorkflowState


def route_after_execution(state: TestWorkflowState) -> str:
    passed = state.get("execution_result", {}).get("passed", False)
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if passed:
        return "finalize"
    elif retry_count < max_retries:
        return "analyze_error"
    else:
        return "finalize"


def route_after_analysis(state: TestWorkflowState) -> str:
    suggestion = state.get("fix_suggestion", {})
    if suggestion.get("retry"):
        return "generate"
    return "finalize"
