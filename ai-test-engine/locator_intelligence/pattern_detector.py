"""Detects repeated DOM patterns and infers parameterized locator structures."""

import re
from collections import Counter


def detect_repeated_patterns(elements: list[dict]) -> list[dict]:
    """
    Find groups of elements that share the same structure but different text/values.
    Returns a list of pattern group dicts.
    """
    groups = []

    # Group by (parent_class, tag, purpose)
    buckets: dict[str, list[dict]] = {}
    for el in elements:
        parent = el.get("parent_summary") or {}
        parent_cls = parent.get("class", "").split()[0] if parent.get("class") else ""
        key = f"{el.get('tag')}|{parent_cls}|{el.get('purpose', 'unknown')}"
        buckets.setdefault(key, []).append(el)

    for key, group in buckets.items():
        if len(group) < 2:
            continue
        texts = [el.get("text", "") for el in group if el.get("text")]
        if len(set(texts)) < 2:
            continue  # All same text — not a repeated pattern with different values

        tag, parent_cls, purpose = key.split("|")
        pattern = {
            "pattern_type": "repeated_element",
            "tag": tag,
            "parent_class": parent_cls,
            "purpose": purpose,
            "count": len(group),
            "sample_texts": list(set(texts))[:5],
            "elements": group,
        }
        groups.append(pattern)

    # Detect card-like structures (product cards, result items)
    card_groups = _detect_card_structures(elements)
    groups.extend(card_groups)

    return groups


def _detect_card_structures(elements: list[dict]) -> list[dict]:
    """Detect product card / result card patterns."""
    card_indicators = re.compile(
        r"product.?card|item.?card|product.?tile|result.?item|search.?result|"
        r"product.?item|listing|grid.?item", re.I
    )
    cards = []
    for el in elements:
        cls_str = el.get("class_str", "")
        if card_indicators.search(cls_str) or (
            el.get("tag") in ("article", "li") and
            el.get("sibling_count", 0) >= 2
        ):
            cards.append(el)

    if len(cards) >= 2:
        sample_texts = [el.get("text", "")[:50] for el in cards[:5]]
        return [{
            "pattern_type": "card_collection",
            "purpose": "product_card",
            "count": len(cards),
            "sample_texts": sample_texts,
            "elements": cards,
            "representative": cards[0],
        }]
    return []


def infer_parameterized_name(purpose: str, pattern_type: str) -> str:
    """Generate a UPPER_SNAKE_CASE locator name for a parameterized pattern."""
    mapping = {
        "product_card": "PRODUCT_CARD_BY_NAME",
        "product_name": "PRODUCT_NAME_BY_TEXT",
        "product_price": "PRODUCT_PRICE_BY_NAME",
        "add_to_cart": "ADD_TO_CART_BY_PRODUCT_NAME",
        "filter_option": "FILTER_OPTION_BY_LABEL",
        "navigation_link": "NAV_LINK_BY_TEXT",
        "table_row": "TABLE_ROW_BY_TEXT",
        "list_item": "LIST_ITEM_BY_TEXT",
        "button": "BUTTON_BY_TEXT",
        "link": "LINK_BY_TEXT",
    }
    return mapping.get(purpose, f"{purpose.upper()}_BY_VALUE")
