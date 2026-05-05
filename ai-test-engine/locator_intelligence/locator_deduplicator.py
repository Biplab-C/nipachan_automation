"""
Deduplicates locator candidates:
- Same selector → duplicate
- Same purpose + parent structure → prefer parameterized
- Value-specific locators → merge into one parameterized locator
"""
import re
from locator_intelligence.models import LocatorDefinition


def deduplicate(locators: list[LocatorDefinition]) -> list[LocatorDefinition]:
    seen_selectors: set[str] = set()
    seen_purposes: dict[str, LocatorDefinition] = {}
    result: list[LocatorDefinition] = []

    # Sort: parameterized first (prefer them over static duplicates), then by confidence desc
    sorted_locs = sorted(locators, key=lambda l: (0 if l.is_parameterized() else 1, -l.confidence))

    for loc in sorted_locs:
        # Normalize selector for comparison
        norm = _normalize_selector(loc.selector)

        # Exact duplicate selector
        if norm in seen_selectors:
            continue

        # Same purpose already covered by a parameterized locator
        if loc.purpose in seen_purposes:
            existing = seen_purposes[loc.purpose]
            if existing.is_parameterized() and not loc.is_parameterized():
                continue  # parameterized already covers this purpose
            if existing.confidence >= loc.confidence:
                continue

        seen_selectors.add(norm)
        seen_purposes[loc.purpose] = loc
        result.append(loc)

    # Merge value-specific text locators into parameterized ones
    result = _merge_text_locators(result)
    return result


def _normalize_selector(sel: str) -> str:
    """Remove specific values for comparison (treat 'text=Cake' same structure as 'text=Milk')."""
    # Strip text= values for structural comparison
    sel = re.sub(r"text=.+", "text=VALUE", sel)
    # Strip specific quoted strings in CSS/XPath
    sel = re.sub(r"'[^']{1,60}'", "'VALUE'", sel)
    sel = re.sub(r'"[^"]{1,60}"', '"VALUE"', sel)
    return sel.strip()


def _merge_text_locators(locators: list[LocatorDefinition]) -> list[LocatorDefinition]:
    """
    If multiple static text= locators with same purpose exist,
    replace them with a single parameterized one.
    """
    text_by_purpose: dict[str, list[LocatorDefinition]] = {}
    others = []

    for loc in locators:
        if loc.strategy == "text" and not loc.is_parameterized():
            text_by_purpose.setdefault(loc.purpose, []).append(loc)
        else:
            others.append(loc)

    for purpose, group in text_by_purpose.items():
        if len(group) >= 2:
            # Merge into one parameterized locator
            samples = [re.sub(r"^text=", "", l.selector) for l in group]
            tag = group[0].name.lower().split("_")[0]
            merged = LocatorDefinition(
                name=group[0].name,  # Keep first name
                locator_type="parameterized",
                strategy="xpath",
                selector=f"xpath=//{{tag}}[normalize-space()='{{item_text}}']".replace("{tag}", tag),
                purpose=purpose,
                parameters=["item_text"],
                sample_values=samples,
                confidence=round(sum(l.confidence for l in group) / len(group) * 0.95, 2),
                source="merged",
            )
            others.append(merged)
        else:
            others.extend(group)

    return others
