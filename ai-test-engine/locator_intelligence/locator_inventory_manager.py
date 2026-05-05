"""
Manages the locator inventory registry (framework_registry.json).
Integrates all locator_intelligence sub-modules into a single entry point.
"""
import json
import logging
import os
import re
from pathlib import Path

from locator_intelligence.models import LocatorDefinition, PageLocatorInventory
from locator_intelligence.page_profiler import normalize_page_key
from locator_intelligence.dom_collector import collect_elements, collect_headings
from locator_intelligence.element_classifier import classify_all
from locator_intelligence.pattern_detector import detect_repeated_patterns
from locator_intelligence.locator_generator import generate_static_locator, generate_parameterized_locators
from locator_intelligence.locator_deduplicator import deduplicate
from locator_intelligence.locator_validator import validate_all

logger = logging.getLogger(__name__)

_ai_root = Path(__file__).parent.parent
REGISTRY_FILE = _ai_root / "framework_registry.json"


def _load_registry() -> dict:
    if REGISTRY_FILE.exists():
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    return {}


def _save_registry(reg: dict):
    REGISTRY_FILE.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def get_inventory_for_url(url: str) -> PageLocatorInventory | None:
    """Load existing inventory for a URL if it exists."""
    reg = _load_registry()
    profiled = normalize_page_key(url)
    page_key = profiled["page_key"]
    entry = reg.get(page_key)
    if entry and "locators" in entry and isinstance(list(entry["locators"].values() or [{}])[0] if entry["locators"] else {}, dict):
        # Check it's the rich new format
        first = list(entry["locators"].values())[0] if entry["locators"] else {}
        if "confidence" in first:
            return PageLocatorInventory.from_dict(entry)
    return None


def build_inventory(page, url: str, title: str = "") -> PageLocatorInventory:
    """
    Full pipeline: collect → classify → detect patterns → generate → dedup → validate → save.
    Returns the PageLocatorInventory for this page.
    """
    logger.info("Building locator inventory for: %s", url)

    # Profile page
    headings = collect_headings(page)
    profiled = normalize_page_key(url, title, headings)
    page_key = profiled["page_key"]
    class_name = profiled["class_name"]

    # Check existing
    existing = get_inventory_for_url(url)
    if existing and len(existing.get_validated()) >= 3:
        logger.info("Reusing existing inventory for %s (%d locators)", page_key, len(existing.locators))
        return existing

    # Collect & classify elements
    elements = collect_elements(page)
    elements = classify_all(elements)
    logger.info("Collected %d elements on %s", len(elements), page_key)

    # Generate static locators from classified elements
    existing_names: set[str] = set()
    static_locs: list[LocatorDefinition] = []
    seen_purposes: set[str] = set()

    for el in elements:
        purpose = el.get("purpose", "unknown")
        if purpose == "unknown" or purpose in seen_purposes:
            continue
        loc = generate_static_locator(el, purpose, existing_names)
        if loc:
            static_locs.append(loc)
            seen_purposes.add(purpose)

    # Detect repeated patterns and generate parameterized locators
    patterns = detect_repeated_patterns(elements)
    param_locs: list[LocatorDefinition] = []
    for pattern in patterns:
        param_locs.extend(generate_parameterized_locators(pattern, existing_names))

    # Combine and deduplicate
    all_locs = deduplicate(static_locs + param_locs)

    # Validate against page (non-blocking)
    try:
        all_locs = validate_all(page, all_locs, max_to_validate=25)
    except Exception as e:
        logger.warning("Validation step failed: %s", e)

    # Build inventory
    inventory = PageLocatorInventory(
        page_key=page_key,
        class_name=class_name,
        url=url,
        url_patterns=[profiled.get("url_pattern", "")],
        title=title,
        page_type=profiled.get("page_type", "unknown"),
    )
    for loc in all_locs:
        inventory.add_locator(loc)

    # Save to registry
    _persist_inventory(inventory)
    logger.info("Inventory built for %s: %d locators", page_key, len(all_locs))
    return inventory


def _persist_inventory(inventory: PageLocatorInventory):
    reg = _load_registry()
    reg[inventory.page_key] = inventory.to_dict()
    _save_registry(reg)


def get_locators_dict(inventory: PageLocatorInventory) -> dict:
    """Return {CONSTANT_NAME: selector_string} for backward-compat with existing code."""
    return {name: loc.selector for name, loc in inventory.locators.items()}


def get_inventory_for_page_key(page_key: str) -> PageLocatorInventory | None:
    reg = _load_registry()
    entry = reg.get(page_key)
    if entry and "locators" in entry:
        return PageLocatorInventory.from_dict(entry)
    return None
