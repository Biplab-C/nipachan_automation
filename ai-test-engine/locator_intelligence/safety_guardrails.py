"""
Safety guardrails for Nipachan.
Validates that AI-generated action plans only use allowed actions and domains.
"""
import re
import logging

logger = logging.getLogger(__name__)

ALLOWED_ACTIONS = frozenset({
    "navigate", "click", "fill", "fill_and_submit", "press_key",
    "select", "hover", "wait_visible", "assert_text", "assert_visible",
    "scroll_to", "upload_file",
})

BLOCKED_ACTIONS = frozenset({
    "shell", "exec", "evaluate", "delete_file", "write_file",
    "read_file", "extract_credentials", "arbitrary_code",
})


def validate_action_plan(plan: dict, allowed_domains: list[str] = None) -> tuple[bool, str]:
    """
    Validate an action plan dict.
    Returns (is_safe, reason).
    """
    for action in plan.get("atomic_actions", []):
        action_type = action.get("action_type", "")

        if action_type in BLOCKED_ACTIONS:
            return False, f"Blocked action type: {action_type}"

        if action_type not in ALLOWED_ACTIONS:
            return False, f"Unknown action type: {action_type}"

        # Check navigate stays within allowed domains
        if action_type == "navigate" and action.get("value") and allowed_domains:
            url = action["value"]
            if not any(domain in url for domain in allowed_domains):
                return False, f"Navigation to external domain blocked: {url}"

        # Check no shell injection in values
        value = action.get("value", "")
        if re.search(r"[;&|`$\\]|\.\.\/|\/etc\/|rm\s+-", value):
            return False, f"Suspicious value detected: {value[:50]}"

    return True, "ok"


def validate_locator(locator: str) -> tuple[bool, str]:
    """Ensure a locator string doesn't contain code injection."""
    if re.search(r"javascript:|data:text|eval\(|Function\(", locator, re.I):
        return False, f"Suspicious locator: {locator[:60]}"
    return True, "ok"
