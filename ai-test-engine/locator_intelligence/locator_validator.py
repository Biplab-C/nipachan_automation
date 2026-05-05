"""Validates locators against the live Playwright page."""
import logging
import re
from locator_intelligence.models import LocatorDefinition

logger = logging.getLogger(__name__)


def validate_locator(page, loc: LocatorDefinition) -> LocatorDefinition:
    """
    Try the locator against the page. Updates match_count, visible_count,
    unique, validated, confidence.
    """
    try:
        if loc.is_parameterized() and loc.sample_values:
            return _validate_parameterized(page, loc)
        return _validate_static(page, loc)
    except Exception as e:
        logger.debug("Validation error for %s: %s", loc.name, e)
        loc.validated = False
        loc.confidence = round(loc.confidence * 0.5, 2)
        return loc


def _validate_static(page, loc: LocatorDefinition) -> LocatorDefinition:
    selector = _to_playwright_selector(loc.selector, loc.strategy)
    try:
        locator = page.locator(selector)
        count = locator.count()
        visible = sum(1 for i in range(min(count, 5)) if _is_visible(locator.nth(i)))

        loc.match_count = count
        loc.visible_count = visible
        loc.unique = (count == 1)
        loc.validated = count > 0

        # Adjust confidence based on match results
        if count == 0:
            loc.confidence = round(loc.confidence * 0.3, 2)
        elif count == 1 and visible == 1:
            loc.confidence = min(1.0, round(loc.confidence * 1.05, 2))
        elif count > 5:
            loc.confidence = round(loc.confidence * 0.7, 2)  # Too many matches — ambiguous

        return loc
    except Exception as e:
        logger.debug("Static validation failed for %s: %s", loc.name, e)
        loc.validated = False
        return loc


def _validate_parameterized(page, loc: LocatorDefinition) -> LocatorDefinition:
    """Validate by trying each sample value."""
    successes = 0
    for sample in loc.sample_values[:3]:
        try:
            if loc.parameters:
                resolved = loc.selector.format(**{loc.parameters[0]: sample})
            else:
                resolved = loc.selector
            selector = _to_playwright_selector(resolved, loc.strategy)
            locator = page.locator(selector)
            count = locator.count()
            if count > 0:
                successes += 1
        except Exception:
            pass

    total = min(len(loc.sample_values), 3)
    loc.validated_samples = successes
    loc.validated = successes > 0
    if total > 0:
        ratio = successes / total
        loc.confidence = round(loc.confidence * (0.7 + 0.3 * ratio), 2)
    return loc


def _to_playwright_selector(selector: str, strategy: str) -> str:
    """Convert our selector format to Playwright locator string."""
    if selector.startswith(("css=", "xpath=", "text=", "role=", "id=")):
        return selector
    if strategy == "xpath" or selector.startswith("//") or selector.startswith("(//"):
        return f"xpath={selector}" if not selector.startswith("xpath=") else selector
    return selector


def _is_visible(locator) -> bool:
    try:
        return locator.is_visible()
    except Exception:
        return False


def validate_all(page, locators: list[LocatorDefinition], max_to_validate: int = 30) -> list[LocatorDefinition]:
    """Validate up to max_to_validate locators. Skip already-validated ones."""
    count = 0
    for loc in locators:
        if loc.validated:
            continue
        if count >= max_to_validate:
            break
        validate_locator(page, loc)
        count += 1
    return locators
