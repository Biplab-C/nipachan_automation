"""
Matches a NormalizedStep against the StepCatalog.

Matching order:
  1. Exact pattern match
  2. Parameterized regex match
  3. Semantic AI match (only if confidence >= 0.85)
  4. No safe match → None (caller creates placeholder)
"""
import re
import logging
from typing import List, Optional

from core.models import CatalogItem, MatchResult, NormalizedStep

logger = logging.getLogger(__name__)

_CONFIDENCE_SEMANTIC = 0.85


def match(normalized: NormalizedStep, catalog: List[CatalogItem]) -> MatchResult:
    # 1. Exact pattern
    for item in catalog:
        if item.pattern.lower() == normalized.step_pattern.lower():
            logger.debug("Exact match: %s", item.pattern)
            return MatchResult(matched=True, catalog_item=item, match_type="exact")

    # 2. Parameterized regex
    for item in catalog:
        try:
            if re.fullmatch(item.regex, normalized.step_text, re.IGNORECASE):
                logger.debug("Regex match: %s", item.pattern)
                return MatchResult(matched=True, catalog_item=item, match_type="regex")
        except re.error:
            continue

    # 3. Semantic — only when confidence is high enough
    if normalized.confidence >= _CONFIDENCE_SEMANTIC:
        sem = _semantic_match(normalized, catalog)
        if sem:
            logger.debug("Semantic match: %s", sem.pattern)
            return MatchResult(matched=True, catalog_item=sem, match_type="semantic")

    return MatchResult(matched=False, match_type="none")


def _semantic_match(normalized: NormalizedStep, catalog: List[CatalogItem]) -> Optional[CatalogItem]:
    """
    Light semantic matching using category + keyword alignment.
    No AI call here — that happens upstream in NormalizationService.
    """
    candidates = [
        c for c in catalog
        if c.keyword == normalized.keyword.lower() and c.implemented
    ]
    pattern_words = set(normalized.step_pattern.lower().split())
    best: Optional[CatalogItem] = None
    best_score = 0.0
    for c in candidates:
        c_words = set(c.pattern.lower().split())
        overlap = len(pattern_words & c_words) / max(len(pattern_words | c_words), 1)
        if overlap > best_score and overlap >= 0.6:
            best_score = overlap
            best = c
    return best
