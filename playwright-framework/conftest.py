import base64
import json
import os
import time

import pytest
from playwright.sync_api import Page

from config.config import Config
from utils.excel_utils import ExcelUtils

# Make all shared step modules available as pytest fixtures globally.
# pytest-bdd v7 requires this — plain imports in test files do NOT register fixtures.
pytest_plugins = [
    "features.steps.shared.navigation_steps",
    "features.steps.shared.search_steps",
    "features.steps.shared.link_steps",
    "features.steps.shared.assertion_steps",
    "features.steps.shared.form_steps",
    "features.steps.shared.analysis_steps",
]


# ------------------------------------------------------------------
# pytest-bdd step tracking (emits NIPACHAN_STEP: JSON lines to stdout)
# ------------------------------------------------------------------

_step_state: dict = {}   # nodeid → {counter, start}
_failed_steps: set = set()  # (nodeid, step_num) pairs already reported via step_error


def pytest_bdd_before_step(request, feature, scenario, step, step_func):
    nid = request.node.nodeid
    if nid not in _step_state:
        _step_state[nid] = {"counter": 0}
    _step_state[nid]["counter"] += 1
    _step_state[nid]["start"] = time.time()


def pytest_bdd_after_step(request, feature, scenario, step, step_func, step_func_args):
    nid = request.node.nodeid
    state = _step_state.get(nid, {"counter": 1, "start": time.time()})
    step_num = state.get("counter", 1)
    if (nid, step_num) in _failed_steps:
        return  # already reported via step_error
    duration = int((time.time() - state.get("start", time.time())) * 1000)
    _emit_step(step_num, step, passed=True, error="", duration=duration)


def pytest_bdd_step_error(request, feature, scenario, step, step_func, step_func_args, exception):
    nid = request.node.nodeid
    state = _step_state.get(nid, {"counter": 1, "start": time.time()})
    step_num = state.get("counter", 1)
    _failed_steps.add((nid, step_num))
    duration = int((time.time() - state.get("start", time.time())) * 1000)
    _emit_step(step_num, step, passed=False, error=str(exception), duration=duration)


def _emit_step(step_num: int, step, passed: bool, error: str, duration: int):
    result = {
        "step": step_num,
        "description": f"{step.keyword} {step.name}",
        "passed": passed,
        "error": error,
        "skipped": False,
        "duration_ms": duration,
    }
    print(f"\nNIPACHAN_STEP:{json.dumps(result)}", flush=True)


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

@pytest.fixture
def app_url() -> str:
    """Application URL for navigation steps. Set APP_URL env var before running tests."""
    return os.environ.get("APP_URL", "http://localhost")


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
