from graph.state import TestWorkflowState


def route_after_execute(state: TestWorkflowState) -> str:
    """
    retry_count > 0  → last step failed (execute_step increments it on failure, resets to 0 on success)
    retry_count == 0 → last step passed
    """
    current_idx = state.get("current_step_index", 0)
    total_steps = len(state.get("raw_steps", []))
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if retry_count > 0:
        return "analyze_step" if retry_count < max_retries else "finalize"

    # Step passed — more steps remaining?
    return "inspect_page" if current_idx < total_steps else "finalize"
