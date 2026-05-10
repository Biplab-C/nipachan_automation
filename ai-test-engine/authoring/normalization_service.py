"""
Orchestrates step normalization:
  1. Call LLM agent to normalize raw steps
  2. Apply confidence rules
  3. Return NormalizedStep list
"""
import logging
from typing import List, Optional

from agents import step_normalizer_agent
from core.models import CatalogItem, NormalizedStep
from providers.llm.base import LLMProvider
from providers.llm.deepseek_provider import DeepSeekProvider

logger = logging.getLogger(__name__)

_HIGH_CONFIDENCE = 0.85
_DRAFT_CONFIDENCE = 0.60


def normalize(
    raw_steps: List[str],
    catalog: List[CatalogItem],
    llm: Optional[LLMProvider] = None,
) -> List[NormalizedStep]:
    provider = llm or DeepSeekProvider()
    try:
        steps = step_normalizer_agent.normalize(raw_steps, catalog, provider)
    except Exception as exc:
        logger.warning("LLM normalization failed (%s), using fallback", exc)
        steps = _fallback(raw_steps)

    for step in steps:
        step.needs_review = step.confidence < _HIGH_CONFIDENCE
        if step.confidence < _DRAFT_CONFIDENCE and not step.ambiguity_reason:
            step.ambiguity_reason = "Low confidence — intent unclear"

    return steps


def _fallback(raw_steps: List[str]) -> List[NormalizedStep]:
    """Produce safe placeholders when the LLM is unavailable."""
    result = []
    for i, raw in enumerate(raw_steps):
        low = raw.lower()
        if i == 0 or any(w in low for w in ("open", "navigate", "go to", "launch")):
            kw = "Given"
        elif any(w in low for w in ("verify", "check", "assert", "confirm", "visible")):
            kw = "Then"
        else:
            kw = "When"
        result.append(NormalizedStep(
            raw_step=raw,
            keyword=kw,
            step_text=f"I {raw[0].lower()}{raw[1:]}",
            step_pattern=f"I {raw[0].lower()}{raw[1:]}",
            category="unknown",
            parameters={},
            function_name="",
            confidence=0.4,
            needs_review=True,
            ambiguity_reason="LLM unavailable — manual review required",
        ))
    return result
