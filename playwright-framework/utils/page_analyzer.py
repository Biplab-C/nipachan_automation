"""
Analyzes the current browser page and writes a page object with stable locators.
Called by the 'the page is analyzed' BDD step.
Output: playwright-framework/pages/{slug}_page.py + pages/analysis/{slug}.json
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from playwright.sync_api import Page

_PAGES_DIR = Path(__file__).parent.parent / "pages"
_ANALYSIS_DIR = _PAGES_DIR / "analysis"


def analyze_and_save(page: Page) -> str:
    """Capture elements from current page, write page object. Returns file path."""
    url = page.url
    slug = _url_slug(url)
    class_name = _class_name(slug)

    elements = _capture(page)
    _write_page_object(slug, class_name, url, elements)
    _write_snapshot(slug, url, elements)
    return str(_PAGES_DIR / f"{slug}_page.py")


def _capture(page: Page) -> List[Dict]:
    elements = []

    # Links
    for el in page.locator("a[href]").all():
        try:
            text = el.inner_text(timeout=500).strip()
            href = el.get_attribute("href") or ""
            if text and len(text) < 80:
                elements.append({"type": "link", "name": text, "locator": f'role=link[name="{_esc(text)}"]', "href": href})
        except Exception:
            pass

    # Buttons
    for el in page.locator("button, [role='button'], input[type='submit'], input[type='button']").all():
        try:
            text = (el.inner_text(timeout=500) or el.get_attribute("value") or el.get_attribute("aria-label") or "").strip()
            if text and len(text) < 80:
                elements.append({"type": "button", "name": text, "locator": f'role=button[name="{_esc(text)}"]'})
        except Exception:
            pass

    # Inputs / text fields
    for el in page.locator("input:not([type='hidden']):not([type='submit']):not([type='button']), textarea").all():
        try:
            label = (
                el.get_attribute("aria-label") or
                el.get_attribute("placeholder") or
                el.get_attribute("name") or
                el.get_attribute("id") or ""
            ).strip()
            input_type = el.get_attribute("type") or "text"
            if label:
                elements.append({"type": f"input[{input_type}]", "name": label, "locator": f'[placeholder="{_esc(label)}"]'})
        except Exception:
            pass

    # Selects / dropdowns
    for el in page.locator("select").all():
        try:
            label = (el.get_attribute("aria-label") or el.get_attribute("name") or el.get_attribute("id") or "").strip()
            if label:
                elements.append({"type": "select", "name": label, "locator": f'select[name="{_esc(label)}"]'})
        except Exception:
            pass

    # Deduplicate by locator
    seen = set()
    unique = []
    for e in elements:
        if e["locator"] not in seen:
            seen.add(e["locator"])
            unique.append(e)
    return unique


def _write_page_object(slug: str, class_name: str, url: str, elements: List[Dict]):
    _PAGES_DIR.mkdir(exist_ok=True)
    lines = [
        f"# Auto-analyzed: {url}",
        f"# Captured: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"class {class_name}:",
    ]

    grouped: Dict[str, List[Dict]] = {}
    for e in elements:
        grouped.setdefault(e["type"], []).append(e)

    for group_type, items in grouped.items():
        lines.append(f"    # {group_type}s")
        for item in items:
            const = re.sub(r"[^A-Z0-9]+", "_", item["name"].upper()).strip("_")[:40]
            lines.append(f'    {const} = {repr(item["locator"])}')
        lines.append("")

    path = _PAGES_DIR / f"{slug}_page.py"
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_snapshot(slug: str, url: str, elements: List[Dict]):
    _ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    data = {"url": url, "captured_at": datetime.now().isoformat(), "elements": elements}
    path = _ANALYSIS_DIR / f"{slug}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _url_slug(url: str) -> str:
    url = re.sub(r"https?://", "", url).rstrip("/")
    return re.sub(r"[^a-z0-9]+", "_", url.lower()).strip("_")[:50]


def _class_name(slug: str) -> str:
    return "".join(w.capitalize() for w in slug.split("_")) + "Page"


def _esc(text: str) -> str:
    return text.replace('"', '\\"')
