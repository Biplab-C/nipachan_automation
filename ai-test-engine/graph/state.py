from typing import TypedDict


class TestWorkflowState(TypedDict):
    run_id: str
    test_case_id: str
    app_url: str
    raw_steps: list

    # Per-step execution
    current_step_index: int
    current_url: str
    current_page_title: str
    page_elements: list
    step_cache: dict
    retry_hint: str
    current_action: dict
    step_results: list

    # Framework integration
    page_registry: dict        # url_key → {class_name, filename, locators, methods}
    current_page_key: str      # url_key of the page currently being interacted with
    current_locators: dict     # locator constants for the current page object

    # Locator Intelligence (new)
    current_inventory: dict        # serialized PageLocatorInventory for current page
    action_plan: dict              # current step's ActionPlan
    run_artifacts_dir: str         # path to temp_runs/{run_id}/

    # Execution control
    highlight_elements: bool
    error_message: str
    retry_count: int
    max_retries: int
    status: str
    final_report: dict
