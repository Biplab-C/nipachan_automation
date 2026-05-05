"""Generates locator candidates from DOM elements using stable strategy priority."""

import re
from locator_intelligence.models import LocatorDefinition


_NAMING_MAP = {
    "search_input": "SEARCH_INPUT",
    "submit_search": "SUBMIT_SEARCH_BUTTON",
    "add_to_cart": "ADD_TO_CART_BUTTON",
    "checkout": "CHECKOUT_BUTTON",
    "login_button": "LOGIN_BUTTON",
    "cart_link": "CART_LINK",
    "quantity_input": "QUANTITY_INPUT",
    "sort_dropdown": "SORT_DROPDOWN",
    "pagination_next": "NEXT_PAGE_BUTTON",
    "pagination_prev": "PREV_PAGE_BUTTON",
    "password_input": "PASSWORD_INPUT",
    "email_input": "EMAIL_INPUT",
    "phone_input": "PHONE_INPUT",
    "product_name": "PRODUCT_NAME",
    "product_price": "PRODUCT_PRICE",
    "product_card": "PRODUCT_CARDS",
    "navigation_link": "NAV_LINK",
    "form_submit": "SUBMIT_BUTTON",
    "close_button": "CLOSE_BUTTON",
    "primary_action": "PRIMARY_BUTTON",
    "heading": "PAGE_HEADING",
}


def generate_static_locator(el: dict, purpose: str, existing_names: set) -> LocatorDefinition | None:
    """Generate a single static locator for an element using priority strategy."""
    selector, strategy = _best_selector(el)
    if not selector:
        return None

    name = _unique_name(_NAMING_MAP.get(purpose, purpose.upper()), existing_names)
    confidence = _selector_confidence(el, strategy)

    return LocatorDefinition(
        name=name,
        locator_type="static",
        strategy=strategy,
        selector=selector,
        purpose=purpose,
        role=el.get("role") or None,
        match_count=1,
        visible_count=1,
        unique=True,
        confidence=confidence,
        source="generated",
    )


def generate_parameterized_locators(pattern: dict, existing_names: set) -> list[LocatorDefinition]:
    """Generate parameterized locators from a repeated pattern."""
    results = []
    purpose = pattern.get("purpose", "unknown")
    representative = pattern.get("representative") or (pattern.get("elements") or [{}])[0]
    class_str = representative.get("class_str", "")
    tag = representative.get("tag", "div")
    sample_texts = pattern.get("sample_texts", [])

    if purpose == "product_card" or pattern.get("pattern_type") == "card_collection":
        # Generate card-level parameterized locators
        card_class = _best_class_selector(class_str)

        results.extend([
            LocatorDefinition(
                name=_unique_name("PRODUCT_CARDS", existing_names),
                locator_type="collection",
                strategy="css",
                selector=f"{tag}.{card_class}" if card_class else tag,
                purpose="product_card",
                parameters=[],
                sample_values=sample_texts,
                confidence=0.80,
                source="generated",
            ),
            LocatorDefinition(
                name=_unique_name("PRODUCT_CARD_BY_NAME", existing_names),
                locator_type="parameterized",
                strategy="xpath",
                selector=f"xpath=//{tag}[contains(@class,'{card_class}')][.//*[normalize-space()='{{product_name}}']]" if card_class else f"xpath=//{tag}[.//*[normalize-space()='{{product_name}}']]",
                purpose="product_card",
                parameters=["product_name"],
                sample_values=sample_texts,
                confidence=0.85,
                source="generated",
            ),
            LocatorDefinition(
                name=_unique_name("ADD_TO_CART_BY_PRODUCT_NAME", existing_names),
                locator_type="parameterized",
                strategy="xpath",
                selector=f"xpath=//{tag}[contains(@class,'{card_class}')][.//*[normalize-space()='{{product_name}}']]//button[contains(.,'Add') or contains(@aria-label,'Add')]" if card_class else f"xpath=//{tag}[.//*[normalize-space()='{{product_name}}']]//button",
                purpose="add_to_cart",
                parameters=["product_name"],
                sample_values=sample_texts,
                confidence=0.82,
                source="generated",
            ),
            LocatorDefinition(
                name=_unique_name("PRODUCT_PRICE_BY_NAME", existing_names),
                locator_type="parameterized",
                strategy="xpath",
                selector=(
                    f"xpath=//{tag}[contains(@class,'{card_class}')][.//*[normalize-space()='{{product_name}}']]//*[contains(@class,'price')]"
                    if card_class else
                    f"xpath=//{tag}[.//*[normalize-space()='{{product_name}}']]//*[contains(@class,'price')]"
                ),
                purpose="product_price",
                parameters=["product_name"],
                sample_values=sample_texts,
                confidence=0.78,
                source="generated",
            ),
        ])
    else:
        # Generic repeated element
        param_name = f"{{item_text}}"
        results.append(
            LocatorDefinition(
                name=_unique_name(f"{purpose.upper()}_BY_TEXT", existing_names),
                locator_type="parameterized",
                strategy="xpath",
                selector=f"xpath=//{tag}[normalize-space()='{param_name}']",
                purpose=purpose,
                parameters=["item_text"],
                sample_values=sample_texts,
                confidence=0.75,
                source="generated",
            )
        )

    for loc in results:
        existing_names.add(loc.name)
    return results


def _best_selector(el: dict) -> tuple[str, str]:
    """Return (selector, strategy) using priority order."""
    # 1. data-testid
    if el.get("data_testid"):
        return f"[data-testid='{el['data_testid']}']", "css"
    # 2. stable id
    if el.get("id") and not re.search(r"\d{4,}|_[a-z0-9]{8,}", el["id"]):
        return f"#{el['id']}", "css"
    # 3. role + aria-label
    if el.get("role") and el.get("aria_label"):
        return f"[role='{el['role']}'][aria-label='{el['aria_label']}']", "css"
    # 4. name
    if el.get("name"):
        return f"[name='{el['name']}']", "css"
    # 5. placeholder
    if el.get("placeholder"):
        return f"[placeholder='{el['placeholder']}']", "css"
    # 6. type for inputs
    if el.get("tag") == "input" and el.get("type") and el["type"] not in ("text", ""):
        return f"input[type='{el['type']}']", "css"
    # 7. text
    if el.get("text") and len(el["text"]) < 50:
        return f"text={el['text']}", "text"
    # 8. aria-label alone
    if el.get("aria_label"):
        return f"[aria-label='{el['aria_label']}']", "css"
    # 9. stable class
    stable_cls = _best_class_selector(el.get("class_str", ""))
    if stable_cls and el.get("tag"):
        return f"{el['tag']}.{stable_cls}", "css"
    return "", "unknown"


def _best_class_selector(class_str: str) -> str:
    """Pick the most stable CSS class from a class string."""
    if not class_str:
        return ""
    classes = class_str.split()
    # Prefer BEM-style or semantic classes, avoid dynamic/hash classes
    stable = [c for c in classes if not re.search(r"\d{3,}|_[a-z0-9]{6,}|css-", c) and len(c) > 3]
    return stable[0] if stable else ""


def _selector_confidence(el: dict, strategy: str) -> float:
    scores = {"css": 0.88, "text": 0.82, "role": 0.90, "xpath": 0.75, "unknown": 0.40}
    base = scores.get(strategy, 0.60)
    if el.get("data_testid"):
        base = 0.97
    elif el.get("id"):
        base = 0.94
    elif el.get("aria_label"):
        base = 0.91
    return round(base, 2)


def _unique_name(base: str, existing: set) -> str:
    if base not in existing:
        existing.add(base)
        return base
    i = 2
    while f"{base}_{i}" in existing:
        i += 1
    name = f"{base}_{i}"
    existing.add(name)
    return name
