from typing import TypedDict


class TestWorkflowState(TypedDict):
    run_id: str
    raw_steps: list[str]
    app_url: str
    selector_hints: dict
    parsed_actions: list[dict]
    generated_script: str
    execution_result: dict
    step_results: list[dict]
    error_message: str
    fix_suggestion: dict
    retry_count: int
    max_retries: int
    status: str
    final_report: dict
