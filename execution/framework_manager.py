"""
Manages all Playwright framework file I/O:
  pages/  — Page Object classes
  data/   — Test data JSON files
  tests/  — Pytest test case files
"""
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_ai_root = Path(__file__).parent.parent  # absolute: d:\...\ai-test-engine
FRAMEWORK_REGISTRY_FILE = _ai_root / "framework_registry.json"


# ── Path helpers ─────────────────────────────────────────────────────────────

def _fw() -> Path:
    """Return the absolute path to the Playwright framework directory."""
    raw = os.getenv("PLAYWRIGHT_FRAMEWORK_PATH", "")
    if raw:
        p = Path(raw)
        # Resolve relative paths from the ai-test-engine directory, not CWD
        if not p.is_absolute():
            p = (_ai_root / p).resolve()
        return p
    # Default: playwright-framework sits next to ai-test-engine
    return (_ai_root.parent / "playwright-framework").resolve()


def _pages_dir() -> Path:
    d = _fw() / "pages"
    d.mkdir(exist_ok=True)
    return d


def _data_dir() -> Path:
    d = _fw() / "data"
    d.mkdir(exist_ok=True)
    return d


def _tests_dir() -> Path:
    d = _fw() / "tests"
    d.mkdir(exist_ok=True)
    return d


# ── Registry ─────────────────────────────────────────────────────────────────

def _load_registry() -> dict:
    if FRAMEWORK_REGISTRY_FILE.exists():
        return json.loads(FRAMEWORK_REGISTRY_FILE.read_text(encoding="utf-8"))
    return {}


def _save_registry(reg: dict):
    FRAMEWORK_REGISTRY_FILE.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def _url_key(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    domain = re.sub(r"[^a-z0-9]", "_", p.netloc.lower().replace("www.", "")).strip("_")
    path = re.sub(r"[^a-z0-9]", "_", p.path.lower()).strip("_")[:30]
    return f"{domain}_{path}".strip("_") or domain


def get_page_class_for_url(url: str) -> dict | None:
    return _load_registry().get(_url_key(url))


# ── Page Object creation ──────────────────────────────────────────────────────

def _ensure_page_file_exists(url_key: str) -> bool:
    """
    Recreate the page class file from registry data if it is missing from disk.
    Returns True if the file exists (or was recreated), False if registry entry missing.
    """
    reg = _load_registry()
    info = reg.get(url_key)
    if not info:
        return False
    filepath = _pages_dir() / info["filename"]
    if filepath.exists():
        return True

    logger.warning("Page file '%s' missing from disk — recreating from registry", info["filename"])
    class_name = info["class_name"]
    locators = info.get("locators", {})
    method_map = info.get("method_map", {})

    lines = [
        "from pages.base_page import BasePage",
        "",
        "",
        f"class {class_name}(BasePage):",
        f'    """Page object for {class_name}."""',
        "",
        "    # ── Locators ──────────────────────────────────────────────────",
    ]
    for name, selector in locators.items():
        lines.append(f'    {name} = "{selector}"')
    lines += [
        "",
        "    # ── Actions ───────────────────────────────────────────────────",
        "",
        f'    def open(self) -> "{class_name}":',
        "        self.navigate_to()",
        "        return self",
    ]

    # Restore methods from method_map (locator:action → method_name)
    for map_key, method_name in method_map.items():
        if method_name == "open":
            continue
        parts = map_key.split(":", 1)
        if len(parts) == 2:
            locator_constant, action = parts
            method_lines = _build_method(method_name, locator_constant, action, "", class_name)
            lines += [""] + method_lines

    filepath.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Recreated page file: %s", filepath)
    return True


def create_page_class(url: str, class_name: str, locators: dict) -> dict:
    """Create a new page object Python file and register it."""
    key = _url_key(url)
    filename = f"{key}_page.py"
    filepath = _pages_dir() / filename

    lines = [
        "from pages.base_page import BasePage",
        "",
        "",
        f"class {class_name}(BasePage):",
        f'    """Page object for {class_name}."""',
        "",
        "    # ── Locators ──────────────────────────────────────────────────",
    ]
    for name, selector in locators.items():
        lines.append(f'    {name} = "{selector}"')
    lines += [
        "",
        "    # ── Actions ───────────────────────────────────────────────────",
        "",
        f'    def open(self) -> "{class_name}":',
        "        self.navigate_to()",
        "        return self",
    ]

    filepath.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Created page class %s → %s", class_name, filename)

    page_info = {
        "url": url,
        "url_key": key,
        "class_name": class_name,
        "filename": filename,
        "locators": locators,
        "methods": ["open"],
        "method_map": {},  # "LOCATOR:action" → method_name
    }
    reg = _load_registry()
    reg[key] = page_info
    _save_registry(reg)
    return page_info


def get_method_map(url_key: str) -> dict:
    """Return {locator_constant:action → method_name} for an existing page class."""
    return _load_registry().get(url_key, {}).get("method_map", {})


def add_method_to_page_class(url_key: str, method_name: str, locator_constant: str,
                              action: str, value: str = "") -> str:
    """
    Append a new action method to an existing page class.
    Deduplicates by locator+action — if one already exists, returns its name without writing again.
    Returns the actual method name used (may differ from requested if a duplicate existed).
    """
    reg = _load_registry()
    info = reg.get(url_key)
    if not info:
        return method_name

    map_key = f"{locator_constant}:{action}"
    method_map = info.setdefault("method_map", {})

    # Dedup: same locator + action already has a method → reuse it
    if map_key in method_map:
        existing = method_map[map_key]
        logger.info("Dedup: reusing existing method '%s' for %s", existing, map_key)
        return existing

    # Name collision guard: different locator+action but same AI-chosen name
    # Derive a deterministic unique name from the locator constant instead of appending _v2
    if method_name in info.get("methods", []):
        method_name = _derive_method_name(locator_constant, action)
        # If that name is also taken, suffix with the locator constant for full uniqueness
        if method_name in info.get("methods", []):
            method_name = f"{_derive_method_name(locator_constant, action)}_{locator_constant.lower()}"

    filepath = _pages_dir() / info["filename"]
    if not filepath.exists():
        return method_name

    method_lines = _build_method(method_name, locator_constant, action, value, info["class_name"])
    existing_text = filepath.read_text(encoding="utf-8").rstrip()
    filepath.write_text(existing_text + "\n\n" + "\n".join(method_lines) + "\n", encoding="utf-8")

    method_map[map_key] = method_name
    info.setdefault("methods", []).append(method_name)
    reg[url_key] = info
    _save_registry(reg)
    logger.info("Added method '%s' to %s", method_name, info["filename"])
    return method_name


def _derive_method_name(locator_constant: str, action: str) -> str:
    """Derive a deterministic snake_case method name from the locator constant and action."""
    lc = locator_constant.lower()
    if action in ("assert_visible", "assert_text"):
        return f"verify_{lc}"
    if action == "click":
        return f"click_{lc}"
    if action == "fill":
        return f"fill_{lc}"
    if action == "fill_and_submit":
        return f"search_via_{lc}"
    if action == "hover":
        return f"hover_{lc}"
    if action == "select":
        return f"select_{lc}"
    return f"interact_{lc}"


def _build_method(method_name: str, locator: str, action: str, value: str, class_name: str) -> list:
    lines = [f"    def {method_name}(self) -> \"{class_name}\":"]
    if action == "click":
        lines.append(f"        self.actions.click(self.{locator})")
    elif action == "fill":
        val_repr = repr(value) if value else "text"
        lines.append(f"        self.actions.send_text(self.{locator}, {val_repr})")
    elif action == "fill_and_submit":
        # Compound: fill input then press Enter to submit
        val_repr = repr(value) if value else "text"
        lines.append(f"        self.actions.send_text(self.{locator}, {val_repr})")
        lines.append(f"        self.actions.press_key(self.{locator}, 'Enter')")
    elif action in ("assert_visible", "assert_text"):
        lines.append(f"        self.actions.wait_for_visible(self.{locator})")
    elif action == "hover":
        lines.append(f"        self.actions.hover(self.{locator})")
    elif action == "select":
        lines.append(f"        self.actions.select_option(self.{locator}, value={repr(value)})")
    else:
        lines.append(f"        self.actions.click(self.{locator})")
    lines.append("        return self")
    return lines


# ── Test data JSON ────────────────────────────────────────────────────────────

def write_test_data(tc_id: str, tc_name: str, raw_steps: list, step_results: list) -> str | None:
    """
    Write test data JSON only when the test has form inputs (fill / select actions).
    Returns filename, or None if no data is needed.
    """
    form_steps = [
        r for r in step_results
        if r.get("action") in ("fill", "select") and r.get("value")
    ]
    if not form_steps:
        logger.info("No form data needed for %s — skipping data file", tc_id)
        return None

    slug = re.sub(r"[^a-z0-9]+", "_", tc_name.lower()).strip("_")[:35]
    filename = f"{tc_id}_{slug}.json"
    filepath = _data_dir() / filename

    payload = {
        tc_id: {
            "test_name": tc_name,
            "generated_at": datetime.now().isoformat(),
            "form_inputs": [
                {
                    "step": r.get("step"),
                    "description": r.get("description", ""),
                    "locator_constant": r.get("locator_constant", ""),
                    "value": r.get("value", ""),
                }
                for r in form_steps
            ],
        }
    }
    filepath.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote test data → %s", filename)
    return filename


# ── Test case file ────────────────────────────────────────────────────────────

def write_test_file(tc_id: str, tc_name: str, raw_steps: list,
                    step_results: list, data_filename: str | None) -> str:
    """Write a pytest test file that uses framework page objects. Returns filename."""
    slug = re.sub(r"[^a-z0-9]+", "_", tc_name.lower()).strip("_")[:40]
    filename = f"{tc_id}_{slug}.py"
    filepath = _tests_dir() / filename

    reg = _load_registry()

    def _resolve_page_info(r: dict) -> tuple[str, str, str]:
        """Return (url_key, class_name, filename) for a step result, using all fallbacks."""
        key = r.get("url_key", "")
        cls = r.get("page_class", "")
        fn = r.get("page_filename", "")

        # Fallback 1: look up by url_key in registry
        if key and (not cls or not fn):
            reg_info = reg.get(key, {})
            cls = cls or reg_info.get("class_name", "")
            fn = fn or reg_info.get("filename", "")

        # Fallback 2: look up by current_url when url_key is missing
        if not key and r.get("current_url"):
            derived_key = _url_key(r["current_url"])
            reg_info = reg.get(derived_key, {})
            if reg_info:
                key = derived_key
                cls = cls or reg_info.get("class_name", "")
                fn = fn or reg_info.get("filename", "")

        return key, cls, fn

    # Collect unique page classes in order of first appearance
    pages_seen: dict[str, dict] = {}
    for r in step_results:
        key, cls, fn = _resolve_page_info(r)
        if cls and key and key not in pages_seen:
            pages_seen[key] = {
                "class_name": cls,
                "filename": fn,
                "var_name": _to_var(cls),
            }

    class_name = "".join(w.capitalize() for w in re.split(r"[^a-zA-Z0-9]", tc_name) if w)[:60] or "TestCase"
    has_data = bool(data_filename)

    # Ensure every referenced page class file exists on disk (recreate from registry if missing)
    for key in list(pages_seen.keys()):
        _ensure_page_file_exists(key)

    lines = [
        "import pytest",
        "from playwright.sync_api import Page",
        "",
    ]
    for info in pages_seen.values():
        if info["class_name"] and info["filename"]:
            mod = info["filename"].replace(".py", "")
            lines.append(f"from pages.{mod} import {info['class_name']}")
    if has_data:
        lines.append("from utils.json_utils import JsonUtils")
    lines += [
        "from utils.data_validator import DataValidator",
        "",
        f"# Auto-generated by AI Test Engine — {tc_id}",
        f"# Name: {tc_name}",
        "",
        f"class Test{class_name}:",
        "",
        "    @pytest.fixture(autouse=True)",
        "    def setup(self, page: Page):",
    ]
    if has_data:
        lines.append(f'        self.data = JsonUtils.get_test_data("{tc_id}", "{data_filename}")')
    for info in pages_seen.values():
        if info["class_name"]:
            lines.append(f"        self.{info['var_name']} = {info['class_name']}(page)")
    lines += [
        "",
        "    @pytest.mark.ai_generated",
        "    def test_execute(self):",
    ]

    # Open first page
    if pages_seen:
        first_var = next(iter(pages_seen.values()))["var_name"]
        lines.append(f"        self.{first_var}.open()")

    for r in step_results:
        key, _, _ = _resolve_page_info(r)
        method = r.get("method_name", "")
        var_name = pages_seen.get(key, {}).get("var_name", "")
        desc = r.get("description", "")
        lines.append(f"        # {desc}")
        if var_name and method and method not in ("open", "", "unknown"):
            lines.append(f"        self.{var_name}.{method}()")
        else:
            lines.append(f"        pass  # TODO: {desc}")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote test file → %s", filename)
    return filename


def _to_var(class_name: str) -> str:
    return re.sub(r"([A-Z])", r"_\1", class_name).lower().strip("_")
