import json
import logging
import re

from agents.base import client, AGENT_MODEL

logger = logging.getLogger(__name__)

_FRAMEWORK_PROMPT = """You are a Playwright Page Object Model expert. Given a test step, available locators, and existing page object methods, determine the exact action.

Return ONLY valid JSON (no markdown fences):
{
  "locator_constant": "EXISTING_CONSTANT_NAME",
  "playwright_locator": "the actual locator string for that constant",
  "action": "click|fill|fill_and_submit|navigate|assert_visible|assert_text|select|hover",
  "value": "text to fill or select, empty otherwise",
  "method_name": "snake_case_method_name",
  "is_existing_method": false,
  "reasoning": "why"
}

CRITICAL RULES — read carefully:

1. REUSE EXISTING METHODS FIRST
   If existing_methods contains a method that already handles this step's locator+action,
   set method_name to that existing name and is_existing_method=true.
   Do NOT invent a new method that does the same thing.

2. NEVER DUPLICATE
   If SEARCH_INPUT already has a method with action "fill", do not create another fill method for SEARCH_INPUT.
   If you need to fill AND submit, use "fill_and_submit" (different action key = new method is OK).

3. COMPOUND ACTION: fill_and_submit
   Use action "fill_and_submit" when the step means TYPE and then SUBMIT:
   - "Search for X"         → fill_and_submit, value=X
   - "Search X"             → fill_and_submit, value=X
   - "Type X and search"    → fill_and_submit, value=X
   Use plain "fill" ONLY when the step is purely about typing with no submission.

4. INTENT MATCHING
   - "Purchase $0/month plan" → locator with "$0", "Free", "0/month" in its value
   - "Click Fake Pricing Page" → link/button with text "Fake Pricing Page"
   - "Search for cake" → fill_and_submit on search input, value="cake"

5. method_name must be snake_case and describe the full action:
   search_for_cake, click_submit_button, fill_email_input, verify_results_visible"""

_FALLBACK_PROMPT = """You are a Playwright test automation expert. Given a plain-English test step and visible page elements, determine the exact action.

Return ONLY valid JSON (no markdown fences):
{
  "action": "click|fill|fill_and_submit|navigate|assert_visible|assert_text|select|hover",
  "playwright_locator": "complete Playwright locator string",
  "value": "text to fill or select, empty otherwise",
  "method_name": "snake_case_method_name",
  "locator_constant": "",
  "is_existing_method": false,
  "reasoning": "why"
}

Use fill_and_submit when the step means type AND submit (search for X, enter X and search).
Locator priority: text= → #id → [placeholder=] → [role=] → CSS"""


def analyze_step_framework(step: str, locators_available: dict, current_url: str,
                            existing_methods: dict = None, retry_hint: str = "") -> dict:
    """Analyze a step using existing page object locators (framework-aware)."""
    locators_str = json.dumps(locators_available, indent=2)
    methods_str = json.dumps(existing_methods or {}, indent=2)
    retry_ctx = f"\nPREVIOUS FAILURE: {retry_hint}\nTry a different locator constant." if retry_hint else ""

    user_msg = (
        f"URL: {current_url}\n"
        f"Step: {step}{retry_ctx}\n\n"
        f"Available locators:\n{locators_str}\n\n"
        f"Existing methods (key=locator:action, value=method_name — REUSE these):\n{methods_str}"
    )

    response = client.chat.completions.create(
        model=AGENT_MODEL,
        messages=[
            {"role": "system", "content": _FRAMEWORK_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content.strip()
    logger.info("Framework step analyzer → '%s': %s", step, content[:200])
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content).strip()
    if not content:
        raise ValueError("Empty response from step analyzer (framework mode)")
    return json.loads(content)


def analyze_step(step: str, page_elements: list, current_url: str, retry_hint: str = "") -> dict:
    """Fallback: analyze a step using raw page elements (no page object)."""
    elements_str = json.dumps(page_elements[:60], indent=2)
    retry_ctx = f"\nPREVIOUS FAILURE: {retry_hint}\nTry a completely different locator." if retry_hint else ""

    response = client.chat.completions.create(
        model=AGENT_MODEL,
        messages=[
            {"role": "system", "content": _FALLBACK_PROMPT},
            {"role": "user", "content": f"URL: {current_url}\nStep: {step}{retry_ctx}\n\nElements:\n{elements_str}"},
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content.strip()
    logger.info("Raw step analyzer → '%s': %s", step, content[:200])
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content).strip()
    if not content:
        raise ValueError("Empty response from step analyzer (raw mode)")
    return json.loads(content)
