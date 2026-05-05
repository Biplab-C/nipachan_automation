import json
import logging
import re

from agents.base import client, AGENT_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Playwright Page Object Model expert. Given a list of interactive page elements, generate a structured page locators definition.

Return ONLY valid JSON (no markdown fences):
{
  "class_name": "PascalCasePageName",
  "locators": {
    "ELEMENT_CONSTANT_NAME": "playwright_locator_string"
  }
}

Rules for ELEMENT_CONSTANT_NAME (UPPER_SNAKE_CASE):
- Be descriptive and action-oriented
- Suffix by type: _BUTTON, _LINK, _INPUT, _DROPDOWN, _HEADING, _LABEL
- Examples: SEARCH_INPUT, SUBMIT_BUTTON, FAKE_PRICING_LINK, FREE_PLAN_BUTTON

Rules for playwright_locator_string (priority order):
1. text= for clear visible text: text=Submit
2. #id when available: #search-box
3. [placeholder="..."] for inputs
4. [role="button"][name="..."] for accessibility
5. CSS selector as last resort

class_name: combine domain + page context in PascalCase.
  Examples: UltimateQaAutomationPage, AmazonSearchPage, GoogleHomePage

Include ALL meaningful interactive elements. Skip nav/cookie/overlay items
that appear on every page unless they are the primary focus."""


def generate_page_locators(url: str, page_title: str, elements: list) -> dict:
    elements_str = json.dumps(elements[:70], indent=2)

    response = client.chat.completions.create(
        model=AGENT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Page URL: {url}\nPage title: {page_title}\n\nElements:\n{elements_str}"},
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content.strip()
    logger.info("Page object generator — class for: %s", url)
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content).strip()
    if not content:
        raise ValueError("Empty response from page object generator")
    return json.loads(content)
