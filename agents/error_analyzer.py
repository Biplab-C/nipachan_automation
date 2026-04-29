import json
import logging
import re
from agents.base import client, AGENT_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Playwright debugging expert. Analyze test failures and suggest fixes.
Return ONLY valid JSON, no markdown fences, no explanation.

Return exactly this structure:
{
  "root_cause": "description of the root cause",
  "issue_type": "selector|timing|logic|network|other",
  "fixed_selector": "corrected CSS selector or empty string",
  "fixed_action": "description of the corrected action or empty string",
  "patched_script": "the complete fixed Python script or empty string",
  "retry": true
}

Set retry to true only if you are confident the patch will resolve the issue.
Set retry to false if the issue is environmental or unrecoverable."""


def analyze_error(error_message: str, generated_script: str, failed_steps: list[dict]) -> dict:
    failed_str = json.dumps(failed_steps, indent=2)

    response = client.chat.completions.create(
        model=AGENT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Error:\n{error_message}\n\nFailed steps:\n{failed_str}\n\nOriginal script:\n{generated_script}",
            },
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content.strip()
    logger.info("Error analyzer raw response: %s", content)

    # Strip markdown code fences if present
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content).strip()

    if not content:
        raise ValueError("DeepSeek returned an empty response for error analysis")

    return json.loads(content)
