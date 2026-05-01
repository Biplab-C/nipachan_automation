from execution.execution_signals import is_stop_requested
from graph.state import TestWorkflowState


def route_after_inspect(state: TestWorkflowState) -> str:
    """After inspect_page: browser dead or stop requested → finalize. Otherwise continue."""
    run_id = state.get("run_id", "")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if retry_count >= max_retries and state.get("status") == "failed":
        return "finalize"

    if is_stop_requested(run_id):
        return "finalize"

    return "generate_page_object"


def route_after_execute(state: TestWorkflowState) -> str:
    """
    Called after every step execution.
    - Browser dead (retry_count == max_retries set by node) → finalize
    - Stop requested by user → finalize after current step
    - Retryable failure → analyze_step
    - Step passed + more steps → inspect_page
    - Step passed + done → finalize
    """
    run_id = state.get("run_id", "")
    current_idx = state.get("current_step_index", 0)
    total_steps = len(state.get("raw_steps", []))
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    # Unrecoverable: browser dead or retries exhausted
    if retry_count >= max_retries:
        return "finalize"

    # User requested stop — finish current step, then finalize
    if is_stop_requested(run_id):
        return "finalize"

    # Retryable failure
    if retry_count > 0:
        return "analyze_step"

    # Step passed
    return "inspect_page" if current_idx < total_steps else "finalize"
