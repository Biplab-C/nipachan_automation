import json
import logging
import re
from agents.base import client, AGENT_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Playwright Python expert. Generate a self-contained Playwright Python script.
Return ONLY Python code, no markdown fences, no explanation.

Requirements:
- Use playwright.sync_api (sync, not async)
- Import: from playwright.sync_api import sync_playwright
- Wrap in: with sync_playwright() as p: browser = p.chromium.launch(headless=True); page = browser.new_page()
- Use page.locator() for all selectors
- After each step, capture screenshot as base64 and store in step_results
- Write final JSON to os.environ["RESULTS_FILE"]
- JSON structure: {"passed": bool, "step_results": [{"step": int, "description": str, "passed": bool, "error": str|null, "screenshot": str|null, "duration_ms": int}]}
- Handle exceptions per step: mark that step failed, continue remaining steps
- At the end, overall passed = all steps passed
- App URL is in os.environ["APP_URL"]
- For screenshots: import base64; screenshot_b64 = base64.b64encode(page.screenshot()).decode()"""


def generate_script(parsed_actions: list[dict], app_url: str) -> str:
    actions_str = json.dumps(parsed_actions, indent=2)

    response = client.chat.completions.create(
        model=AGENT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"App URL: {app_url}\n\nActions to implement:\n{actions_str}"},
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content.strip()
    logger.info("Code generator raw response length: %d chars", len(content))

    # Strip markdown code fences if present
    content = re.sub(r"^```(?:python)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content).strip()

    if not content:
        raise ValueError("DeepSeek returned an empty response for code generation")

    return content
