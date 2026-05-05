import base64

import pytest
from playwright.sync_api import Page

from config.config import Config
from utils.excel_utils import ExcelUtils


# ------------------------------------------------------------------
# One-time setup
# ------------------------------------------------------------------

def pytest_configure(config):
    """Ensure required directories and sample data exist before any test runs."""
    Config.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    Config.HTML_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _bootstrap_sample_excel()


def _bootstrap_sample_excel():
    excel_path = Config.DATA_DIR / "sample_data.xlsx"
    if excel_path.exists():
        return
    ExcelUtils.create_excel(
        excel_path,
        {
            "Users": [
                {"id": 1, "name": "Alice", "email": "alice@example.com", "age": 30, "role": "admin",   "city": "New York"},
                {"id": 2, "name": "Bob",   "email": "bob@example.com",   "age": 25, "role": "user",    "city": "Los Angeles"},
                {"id": 3, "name": "Charlie","email": "charlie@example.com","age": 35,"role": "manager","city": "Chicago"},
                {"id": 4, "name": "Diana", "email": "diana@example.com", "age": 28, "role": "user",    "city": "New York"},
                {"id": 5, "name": "Eve",   "email": "eve@example.com",   "age": 32, "role": "admin",   "city": "Boston"},
            ],
            "Products": [
                {"id": 101, "name": "Laptop",  "price": 999.99, "category": "Electronics", "stock": 50},
                {"id": 102, "name": "Mouse",   "price":  29.99, "category": "Electronics", "stock": 200},
                {"id": 103, "name": "Desk",    "price": 349.99, "category": "Furniture",   "stock": 30},
                {"id": 104, "name": "Chair",   "price": 199.99, "category": "Furniture",   "stock": 45},
                {"id": 105, "name": "Monitor", "price": 499.99, "category": "Electronics", "stock": 75},
            ],
        },
    )


# ------------------------------------------------------------------
# Browser / context configuration (pytest-playwright hooks)
# ------------------------------------------------------------------

@pytest.fixture(scope="session")
def browser_type_launch_args():
    args = {
        "headless": Config.HEADLESS,
        "slow_mo": Config.SLOW_MO,
        "args": ["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
    }
    if Config.CHANNEL:
        args["channel"] = Config.CHANNEL
    return args


@pytest.fixture(scope="session")
def browser_context_args():
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


# ------------------------------------------------------------------
# Failure screenshot hook (pytest-html)
# ------------------------------------------------------------------

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" and rep.failed:
        page_obj: Page = item.funcargs.get("page")
        if page_obj:
            try:
                screenshot = page_obj.screenshot(full_page=True)
                b64 = base64.b64encode(screenshot).decode()
                html = f'<div><img src="data:image/png;base64,{b64}" style="max-width:800px"/></div>'
                extras = getattr(rep, "extras", [])
                extras.append({"name": "Screenshot", "format_type": "html", "content": html})
                rep.extras = extras
            except Exception:
                pass
