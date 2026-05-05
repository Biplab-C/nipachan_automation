"""
Decomposes a Gherkin step into an atomic action plan using the locator inventory.
Avoids LLM inventing locators — uses inventory first.
"""
import json
import logging
import re
from dataclasses import dataclass, field

from locator_intelligence.models import PageLocatorInventory, LocatorDefinition

logger = logging.getLogger(__name__)


@dataclass
class AtomicAction:
    action_type: str          # fill | click | press_key | wait_visible | assert_text | navigate | select | hover
    locator_name: str         # CONSTANT name from inventory (empty for navigate/press_key)
    locator_selector: str     # resolved selector
    value: str = ""           # text to fill, key to press, URL to navigate, etc.
    parameters: dict = field(default_factory=dict)   # e.g. {"product_name": "Cake"}
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type,
            "locator_name": self.locator_name,
            "locator_selector": self.locator_selector,
            "value": self.value,
            "parameters": self.parameters,
            "confidence": self.confidence,
        }


@dataclass
class ActionPlan:
    gherkin_step: str
    intent: str
    atomic_actions: list[AtomicAction] = field(default_factory=list)
    overall_confidence: float = 0.0
    source: str = "inventory"  # inventory | llm | fallback

    def to_dict(self) -> dict:
        return {
            "gherkin_step": self.gherkin_step,
            "intent": self.intent,
            "atomic_actions": [a.to_dict() for a in self.atomic_actions],
            "overall_confidence": self.overall_confidence,
            "source": self.source,
        }

    def is_executable(self) -> bool:
        return bool(self.atomic_actions) and self.overall_confidence >= 0.50


# --- Intent patterns for common step patterns ---
_INTENT_PATTERNS = [
    (r"search\s+for\s+[\"']?(.+?)[\"']?\s*$", "search", ["fill_search", "submit_search"]),
    (r"add\s+[\"']?(.+?)[\"']?\s+to\s+(cart|basket|bag)", "add_to_cart", ["click_add_to_cart"]),
    (r"click\s+on\s+[\"']?(.+?)[\"']?", "click", ["click"]),
    (r"navigate\s+to\s+(.+)", "navigate", ["navigate"]),
    (r"fill\s+[\"']?(.+?)[\"']?\s+with\s+[\"']?(.+?)[\"']?", "fill_field", ["fill"]),
    (r"verify|assert|check|should\s+see\s+[\"']?(.+?)[\"']?", "assert_visible", ["wait_visible"]),
    (r"select\s+[\"']?(.+?)[\"']?\s+from\s+[\"']?(.+?)[\"']?", "select_option", ["select"]),
    (r"hover\s+over\s+[\"']?(.+?)[\"']?", "hover", ["hover"]),
]


def build_action_plan(gherkin_step: str, inventory: PageLocatorInventory,
                      extracted_params: dict = None) -> ActionPlan:
    """
    Build an atomic action plan from a Gherkin step using the locator inventory.
    Tries deterministic intent matching before falling back to LLM.
    """
    params = extracted_params or {}
    step_lower = gherkin_step.lower().strip()

    for pattern, intent, action_types in _INTENT_PATTERNS:
        m = re.search(pattern, step_lower)
        if not m:
            continue

        plan = ActionPlan(gherkin_step=gherkin_step, intent=intent, source="inventory")

        if intent == "search":
            search_term = m.group(1).strip().strip('"\'')
            search_input = _find_locator(inventory, ["search_input", "text_input"])
            if search_input:
                plan.atomic_actions = [
                    AtomicAction("fill", search_input.name, search_input.selector,
                                 value=search_term, confidence=search_input.confidence),
                    AtomicAction("press_key", search_input.name, search_input.selector,
                                 value="Enter", confidence=0.95),
                ]
                plan.overall_confidence = _avg_confidence(plan.atomic_actions)
                return plan

        elif intent == "add_to_cart":
            product_name = m.group(1).strip().strip('"\'')
            add_btn = _find_parameterized(inventory, "add_to_cart", "product_name")
            if add_btn:
                resolved = add_btn.resolve(product_name=product_name)
                plan.atomic_actions = [
                    AtomicAction("click", add_btn.name, resolved,
                                 parameters={"product_name": product_name},
                                 confidence=add_btn.confidence),
                ]
                plan.overall_confidence = add_btn.confidence
                return plan

        elif intent == "click":
            target = m.group(1).strip().strip('"\'')
            loc = _find_by_text_or_purpose(inventory, target)
            if loc:
                resolved = loc.resolve(**params) if loc.parameters else loc.selector
                plan.atomic_actions = [
                    AtomicAction("click", loc.name, resolved, confidence=loc.confidence),
                ]
                plan.overall_confidence = loc.confidence
                return plan

        elif intent == "navigate":
            url = m.group(1).strip()
            plan.atomic_actions = [AtomicAction("navigate", "", "", value=url, confidence=0.95)]
            plan.overall_confidence = 0.95
            return plan

        elif intent == "assert_visible":
            target = m.group(1).strip().strip('"\'')
            loc = _find_by_text_or_purpose(inventory, target)
            if loc:
                plan.atomic_actions = [
                    AtomicAction("wait_visible", loc.name, loc.selector, confidence=loc.confidence),
                ]
                plan.overall_confidence = loc.confidence
                return plan

    # No deterministic match — return empty plan (caller will fall back to LLM)
    return ActionPlan(gherkin_step=gherkin_step, intent="unknown", source="fallback",
                      overall_confidence=0.0)


def _find_locator(inventory: PageLocatorInventory, purposes: list[str]) -> LocatorDefinition | None:
    for purpose in purposes:
        for loc in inventory.locators.values():
            if loc.purpose == purpose and not loc.is_parameterized():
                return loc
    return None


def _find_parameterized(inventory: PageLocatorInventory, purpose: str, param: str) -> LocatorDefinition | None:
    for loc in inventory.locators.values():
        if loc.purpose == purpose and param in loc.parameters:
            return loc
    return None


def _find_by_text_or_purpose(inventory: PageLocatorInventory, target: str) -> LocatorDefinition | None:
    target_lower = target.lower()
    # Exact purpose match
    for loc in inventory.locators.values():
        if loc.purpose.replace("_", " ") in target_lower:
            return loc
    # Text match in selector
    for loc in inventory.locators.values():
        if target_lower in loc.selector.lower():
            return loc
    return None


def _avg_confidence(actions: list[AtomicAction]) -> float:
    if not actions:
        return 0.0
    return round(sum(a.confidence for a in actions) / len(actions), 2)
