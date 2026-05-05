"""Classifies DOM elements into semantic purposes deterministically."""

import re

_PURPOSE_RULES = [
    # (purpose, score, conditions) — evaluated in order, first match wins
    # Deterministic high-confidence rules
    ("search_input",      0.95, lambda e: _match(e, type_=("search",), placeholder_re=r"search|find|keyword|query")),
    ("submit_search",     0.95, lambda e: _match(e, type_=("submit",), aria_re=r"search", text_re=r"search|find|go")),
    ("add_to_cart",       0.95, lambda e: _match(e, tag=("button","a"), text_re=r"add.{0,8}cart|add.{0,8}bag|add.{0,8}basket", aria_re=r"add.{0,8}cart")),
    ("checkout",          0.95, lambda e: _match(e, tag=("button","a"), text_re=r"checkout|proceed|pay now", aria_re=r"checkout")),
    ("login_button",      0.93, lambda e: _match(e, tag=("button","a","input"), text_re=r"^(log.?in|sign.?in)$", type_=("submit",))),
    ("cart_link",         0.92, lambda e: _match(e, tag=("a","button"), aria_re=r"cart|basket|bag", text_re=r"cart|basket|bag")),
    ("quantity_input",    0.92, lambda e: _match(e, type_=("number",), aria_re=r"quantity|qty|amount")),
    ("filter_option",     0.88, lambda e: _match(e, tag=("input",), type_=("checkbox","radio"), parent_class_re=r"filter|facet|refine")),
    ("sort_dropdown",     0.90, lambda e: _match(e, tag=("select",), aria_re=r"sort|order", name_re=r"sort|order")),
    ("pagination_next",   0.92, lambda e: _match(e, tag=("a","button"), text_re=r"next|next page|>$", aria_re=r"next.page|next")),
    ("pagination_prev",   0.92, lambda e: _match(e, tag=("a","button"), text_re=r"prev|previous|<$", aria_re=r"prev")),
    ("password_input",    0.95, lambda e: _match(e, type_=("password",))),
    ("email_input",       0.95, lambda e: _match(e, type_=("email",), placeholder_re=r"email|e-mail")),
    ("phone_input",       0.90, lambda e: _match(e, type_=("tel",), placeholder_re=r"phone|mobile|tel")),
    ("product_name",      0.85, lambda e: _match(e, tag=("h1","h2","h3","span","a"), parent_class_re=r"product|item|card", text_re=r"\S+")),
    ("product_price",     0.88, lambda e: _match(e, tag=("span","div","p"), class_re=r"price|cost|amount", text_re=r"[\$¥€£]|\d+\.\d+")),
    ("product_card",      0.82, lambda e: _match(e, tag=("div","article","li"), class_re=r"product.?card|item.?card|product.?tile|product.?item")),
    ("navigation_link",   0.80, lambda e: _match(e, tag=("a",), parent_tag=("nav","header"), text_re=r"\S+")),
    ("heading",           0.75, lambda e: e.get("tag") in ("h1","h2","h3")),
    ("form_submit",       0.88, lambda e: _match(e, type_=("submit",))),
    ("text_input",        0.70, lambda e: _match(e, type_=("text",""), tag=("input","textarea"))),
    ("close_button",      0.90, lambda e: _match(e, tag=("button",), aria_re=r"close|dismiss", text_re=r"^(x|✕|close)$")),
    ("primary_action",    0.70, lambda e: _match(e, tag=("button",), class_re=r"primary|main|cta", role=("button",))),
    ("link",              0.60, lambda e: e.get("tag") == "a" and e.get("href")),
    ("button",            0.55, lambda e: e.get("tag") == "button" or e.get("role") == "button"),
    ("input",             0.50, lambda e: e.get("tag") in ("input", "textarea", "select")),
]


def _match(el: dict, tag=None, type_=None, role=None, text_re=None,
           aria_re=None, placeholder_re=None, class_re=None, name_re=None,
           parent_class_re=None, parent_tag=None) -> bool:
    if tag and el.get("tag") not in tag:
        return False
    if type_ and el.get("type", "").lower() not in [t.lower() for t in type_]:
        return False
    if role and el.get("role") not in role:
        return False
    if text_re and not re.search(text_re, el.get("text", ""), re.I):
        return False
    if aria_re and not re.search(aria_re, el.get("aria_label", ""), re.I):
        return False
    if placeholder_re and not re.search(placeholder_re, el.get("placeholder", ""), re.I):
        return False
    if class_re and not re.search(class_re, el.get("class_str", ""), re.I):
        return False
    if name_re and not re.search(name_re, el.get("name", ""), re.I):
        return False
    if parent_class_re:
        p = el.get("parent_summary") or {}
        if not re.search(parent_class_re, p.get("class", ""), re.I):
            return False
    if parent_tag:
        p = el.get("parent_summary") or {}
        if p.get("tag") not in parent_tag:
            return False
    return True


def classify_element(el: dict) -> tuple[str, float]:
    """Return (purpose, confidence) for a DOM element."""
    for purpose, base_confidence, rule in _PURPOSE_RULES:
        try:
            if rule(el):
                return purpose, base_confidence
        except Exception:
            continue
    return "unknown", 0.3


def classify_all(elements: list[dict]) -> list[dict]:
    """Add purpose and confidence to each element dict."""
    for el in elements:
        purpose, confidence = classify_element(el)
        el["purpose"] = purpose
        el["confidence"] = confidence
    return elements
