"""
Calls the LLM to normalize plain English steps into structured NormalizedStep objects.
AI outputs category + parameters only — templates generate actual Playwright code.
"""
import json
import logging
import re
from typing import List

from core.models import CatalogItem, NormalizedStep
from providers.llm.base import LLMProvider

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a BDD/Gherkin expert. Convert plain English test steps into structured JSON.

Return ONLY a valid JSON array (no markdown fences):
[
  {
    "raw_step": "original plain English step",
    "keyword": "Given|When|Then|And",
    "step_text": "step body WITHOUT the keyword, with concrete values quoted",
    "step_pattern": "step body with {param_name} placeholders replacing literal values",
    "category": "one of: navigation|search|link_assertion|link_click|button_click|text_assertion|form_input|dropdown_select|unknown",
    "parameters": {"param_name": "concrete_value"},
    "function_name": "snake_case_function_name",
    "confidence": 0.0 to 1.0,
    "needs_review": true|false,
    "ambiguity_reason": "reason if needs_review is true, else empty string"
  }
]

KEYWORD RULES:
- First/setup step → Given
- User actions (click, fill, search, navigate, enter) → When / And
- Verifications (verify, check, assert, confirm, visible, should) → Then / And
- Consecutive same-type steps → And

CATEGORY RULES:
- navigation: go to page, open URL, navigate
- search: search for, look for, find
- link_assertion: verify link is visible, check link exists
- link_click: click link, click on link text
- button_click: click button
- text_assertion: verify text is visible, check text appears
- form_input: enter value into field, fill in, type
- dropdown_select: select from dropdown, choose option
- unknown: anything that doesn't fit above categories clearly

CONFIDENCE RULES:
- >= 0.85: clear unambiguous intent
- 0.60 - 0.84: recognizable but vague, needs_review = true
- < 0.60: unclear intent, needs_review = true

PATTERN RULES:
- Replace literal values with {param_name} placeholders
- Example: 'I search for "Cake"' → pattern: 'I search for "{search_term}"'
- Keep patterns reusable and generic

EXISTING PATTERNS (prefer reusing these exact patterns when semantically equivalent):
{existing_patterns}"""


def normalize(
    raw_steps: List[str],
    catalog: List[CatalogItem],
    llm: LLMProvider,
) -> List[NormalizedStep]:
    existing = [c.pattern for c in catalog]
    system = SYSTEM_PROMPT.replace("{existing_patterns}", json.dumps(existing, indent=2))
    steps_str = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(raw_steps))
    user = f"Convert these plain English steps:\n{steps_str}"

    raw = llm.complete(system, user)
    logger.info("step_normalizer_agent response preview: %s", raw[:300])

    raw = re.sub(r"^```(?:json)?\s*", "", raw).strip()
    raw = re.sub(r"\s*```$", "", raw).strip()
    if not raw:
        raise ValueError("Empty response from step normalizer agent")

    data = json.loads(raw)
    return [_to_normalized(d) for d in data]


def _to_normalized(d: dict) -> NormalizedStep:
    return NormalizedStep(
        raw_step=d.get("raw_step", ""),
        keyword=d.get("keyword", "When"),
        step_text=d.get("step_text", ""),
        step_pattern=d.get("step_pattern", d.get("step_text", "")),
        category=d.get("category", "unknown"),
        parameters=d.get("parameters", {}),
        function_name=d.get("function_name", ""),
        confidence=float(d.get("confidence", 0.5)),
        needs_review=bool(d.get("needs_review", False)),
        ambiguity_reason=d.get("ambiguity_reason", ""),
    )
