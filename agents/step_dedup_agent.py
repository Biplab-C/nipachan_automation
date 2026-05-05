import json
import logging
import re

from agents.base import client, AGENT_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a BDD/Gherkin expert. Convert plain English test steps to Gherkin format.
Deduplicate against existing step patterns — reuse them when semantically equivalent.

Return ONLY a valid JSON array (no markdown fences):
[
  {
    "english_step": "original plain English step",
    "gherkin_keyword": "Given|When|Then|And",
    "gherkin_step_text": "step body WITHOUT the keyword",
    "is_new": true,
    "matched_pattern": "exact existing pattern text if reused, else empty string",
    "step_type": "navigation|action|assertion",
    "anticipated_method": "snake_case page object method name guess"
  }
]

KEYWORD RULES:
- First/setup step → Given
- User actions (click, fill, search, navigate) → When / And
- Verifications (verify, check, assert, confirm) → Then / And
- Consecutive same-type steps → And

DEDUP RULES:
- If an existing pattern is semantically equivalent (even if worded differently), set is_new=false and matched_pattern=that pattern
- Only create a new step when no existing pattern covers the same intent

GHERKIN STYLE:
- Parameterize literal values: 'Search for Cake' → 'I search for "Cake"'
- Start step text with subject: 'I click on ...', 'I verify ...', 'the page should ...'
- Keep steps reusable and concise"""


def analyze_steps(english_steps: list[str], existing_patterns: list[str]) -> list[dict]:
    """
    Convert English steps to Gherkin, deduplicating against existing patterns.
    Returns list of step dicts.
    """
    steps_str = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(english_steps))
    patterns_str = json.dumps(existing_patterns, indent=2)

    response = client.chat.completions.create(
        model=AGENT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Existing step patterns:\n{patterns_str}\n\n"
                    f"New plain English steps to convert:\n{steps_str}"
                ),
            },
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content.strip()
    logger.info("Step dedup agent response: %s", content[:400])
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content).strip()
    if not content:
        raise ValueError("Empty response from step dedup agent")
    return json.loads(content)
