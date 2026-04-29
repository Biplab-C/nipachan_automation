import json
import logging
import re
from agents.base import client, AGENT_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a test automation expert. Convert plain English test steps into structured JSON actions.
Return ONLY a valid JSON array, no markdown fences, no explanation.
Each action object must have exactly these fields:
- action: string (navigate|click|fill|assert_text|assert_visible|assert_url|wait|select|hover|press_key)
- selector: string (CSS selector, or empty string if not applicable)
- value: string (input value, URL, text to assert, key name, or empty string)
- assertion: string (contains|equals|visible|not_visible|url_contains, or empty string)
- description: string (human-readable description of what this step does)
- confidence: number (0.0 to 1.0)

If a step is ambiguous, still produce the best guess with low confidence."""


def parse_steps(raw_steps: list[str], selector_hints: dict) -> list[dict]:
    hints_str = json.dumps(selector_hints) if selector_hints else "{}"
    steps_str = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(raw_steps))

    response = client.chat.completions.create(
        model=AGENT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Selector hints: {hints_str}\n\nTest steps:\n{steps_str}"},
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content.strip()
    logger.info("NLP parser raw response: %s", content)

    # Strip markdown code fences if present
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content).strip()

    if not content:
        raise ValueError("DeepSeek returned an empty response for NLP parsing")

    return json.loads(content)
