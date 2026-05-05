"""
Manages shared step definition files.
Reusable steps go to features/steps/shared/ instead of TC-specific files.
"""
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_ai_root = Path(__file__).parent.parent


def _fw() -> Path:
    raw = os.getenv("PLAYWRIGHT_FRAMEWORK_PATH", "")
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = (_ai_root / p).resolve()
        return p
    return (_ai_root.parent / "playwright-framework").resolve()


def _shared_dir() -> Path:
    d = _fw() / "features" / "steps" / "shared"
    d.mkdir(parents=True, exist_ok=True)
    init = d / "__init__.py"
    if not init.exists():
        init.touch()
    return d


_SHARED_FILE_MAP = {
    "search": "search_steps.py",
    "navigation": "navigation_steps.py",
    "cart": "cart_steps.py",
    "assertion": "assertion_steps.py",
    "login": "auth_steps.py",
    "form": "form_steps.py",
    "product": "product_steps.py",
    "pagination": "pagination_steps.py",
}


def get_shared_file_for_purpose(purpose: str) -> str:
    """Return the shared step file name for a given step purpose."""
    for key, filename in _SHARED_FILE_MAP.items():
        if key in purpose.lower():
            return filename
    return "common_steps.py"


def ensure_shared_step(gherkin_keyword: str, step_text: str, func_name: str,
                        page_class: str, page_module: str,
                        action_type: str, locator_constant: str, value: str,
                        purpose: str = "") -> str:
    """
    Write a reusable step to the appropriate shared file.
    Returns the shared filename.
    """
    filename = get_shared_file_for_purpose(purpose)
    filepath = _shared_dir() / filename

    # Build file header if new
    if not filepath.exists():
        header = "\n".join([
            "# Shared step definitions — auto-managed by Nipachan",
            "# Do not import from TC-specific files; use these shared steps.",
            "",
            "import pytest",
            "from pytest_bdd import given, when, then, parsers",
            "from playwright.sync_api import Page",
            "from utils.web_actions import WebActions",
            "",
        ])
        filepath.write_text(header, encoding="utf-8")

    content = filepath.read_text(encoding="utf-8")

    # Skip if function already defined
    if f"def {func_name}" in content:
        return filename

    # Add imports
    page_import = f"from pages.{page_module} import {page_class}"
    if page_import not in content:
        content = content.replace(
            "from utils.web_actions import WebActions",
            f"from utils.web_actions import WebActions\n{page_import}",
        )

    # Build decorator
    kw = gherkin_keyword.lower()
    if '"' in step_text:
        escaped = step_text.replace("'", "\\'")
        decorator = f"@{kw}(parsers.parse('{escaped}'))"
        # Add string params to function signature
        params = re.findall(r'"(\{[^}]+\})"', step_text)
        param_names = [p.strip("{}") for p in params]
        sig_extra = (", " + ", ".join(f"{p}: str" for p in param_names)) if param_names else ""
    else:
        decorator = f'@{kw}("{step_text}")'
        sig_extra = ""

    # Build implementation
    impl = _build_impl(action_type, page_class, locator_constant, value)

    step_code = f"""

{decorator}
def {func_name}(page: Page{sig_extra}):
{impl}
"""
    filepath.write_text(content.rstrip() + step_code, encoding="utf-8")
    logger.info("Added shared step '%s' to %s", func_name, filename)
    return filename


def _build_impl(action: str, page_class: str, locator: str, value: str) -> str:
    lc = f"{page_class}.{locator}" if locator else '""'
    if action == "click":
        return f"    WebActions(page).click({lc})"
    if action == "fill":
        return f"    WebActions(page).send_text({lc}, {repr(value)})"
    if action == "fill_and_submit":
        return f"    WebActions(page).send_text({lc}, {repr(value)})\n    WebActions(page).press_key({lc}, 'Enter')"
    if action in ("assert_visible", "assert_text", "wait_visible"):
        return f"    WebActions(page).wait_for_visible({lc})"
    if action == "hover":
        return f"    WebActions(page).hover({lc})"
    if action == "select":
        return f"    WebActions(page).select_option({lc}, value={repr(value)})"
    if action == "navigate":
        return f"    page.goto({repr(value)})"
    return f"    WebActions(page).click({lc})"
