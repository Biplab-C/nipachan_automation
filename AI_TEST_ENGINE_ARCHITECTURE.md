# AI Test Engine — Architecture & Developer Guide

**Stack:** Python · FastAPI · LangGraph · DeepSeek · Playwright · pytest-bdd  
**Framework path:** `D:\Playwright Project\claude\playwright-framework`  
**Engine path:** `D:\Playwright Project\claude\ai-test-engine`

---

## 1. System Overview

The system is split into two cooperating layers:

| Layer | Path | Role |
|---|---|---|
| **AI Test Engine** | `ai-test-engine/` | Orchestrates AI agents, drives the browser, generates all framework artifacts |
| **Playwright Framework** | `playwright-framework/` | Contains the generated test assets — page classes, BDD feature files, step definitions, test data |

Users interact with a web UI at **http://localhost:8000**. They write test steps in plain English. The engine converts them into structured BDD tests and executes them against a real browser.

---

## 2. Directory Structure

```
claude/
├── ai-test-engine/
│   ├── agents/
│   │   ├── base.py                  # DeepSeek client (shared across all agents)
│   │   ├── step_dedup_agent.py      # Converts English → Gherkin, deduplicates
│   │   ├── page_object_generator.py # DOM elements → page locator constants
│   │   └── step_analyzer.py        # Gherkin step + locators → WebActions call
│   ├── execution/
│   │   ├── browser_controller.py    # Playwright browser lifecycle
│   │   ├── bdd_manager.py           # Manages feature files, step defs, step registry
│   │   ├── framework_manager.py     # Manages page class files, data JSON, test files
│   │   ├── test_file_manager.py     # TC registry (test_registry.json)
│   │   └── execution_signals.py    # Thread-safe stop signals
│   ├── graph/
│   │   ├── state.py                 # LangGraph TypedDict state definition
│   │   ├── nodes.py                 # All workflow node functions
│   │   ├── edges.py                 # Conditional routing logic
│   │   └── workflow.py              # Graph assembly and compilation
│   ├── api/
│   │   └── routes.py               # FastAPI endpoints
│   ├── ui/
│   │   └── index.html              # Single-page web UI
│   ├── main.py                     # Entry point (uvicorn)
│   ├── test_registry.json          # TC metadata store
│   ├── framework_registry.json     # Page class registry (URL → class info)
│   ├── step_registry.json          # Gherkin step pattern registry
│   └── .env.example                # Environment configuration
│
└── playwright-framework/
    ├── pages/                       # Page Object classes (locators only)
    ├── features/
    │   ├── *.feature               # Gherkin scenario files
    │   └── steps/
    │       └── *_steps.py          # pytest-bdd step definitions
    ├── data/                        # Test data JSON files
    ├── tests/                       # Legacy pytest test files (also generated)
    ├── utils/
    │   ├── web_actions.py          # Retry-wrapped Playwright actions
    │   ├── data_validator.py       # Assertion utilities
    │   ├── json_utils.py           # JSON read/write helpers
    │   └── excel_utils.py          # Excel read/write helpers
    ├── config/
    │   └── config.py               # Framework config (HEADLESS, HIGHLIGHT, etc.)
    ├── conftest.py                  # Browser fixtures (pytest-playwright hooks)
    └── requirements.txt
```

---

## 3. Environment Setup

### 3.1 Install dependencies

```bash
# AI engine
cd ai-test-engine
pip install -r requirements.txt

# Playwright framework
cd ../playwright-framework
pip install -r requirements.txt
playwright install chromium
```

### 3.2 Configure `.env`

Copy `ai-test-engine/.env.example` to `ai-test-engine/.env` and fill in:

```env
DEEPSEEK_API_KEY=sk-your-key-here
PLAYWRIGHT_FRAMEWORK_PATH=../playwright-framework
PLAYWRIGHT_PYTHON=python
MAX_RETRIES=3
TEMP_RUNS_DIR=./temp_runs
```

### 3.3 Start the engine

```bash
cd ai-test-engine
python main.py
# → http://localhost:8000
```

---

## 4. AI Agents

### 4.1 Step Dedup Agent (`agents/step_dedup_agent.py`)

**Triggered:** When a test case is saved from the UI.

**Input:**
- Plain English test steps (e.g., `"Search for Cake"`)
- All existing Gherkin step patterns from `step_registry.json`

**Output:** JSON array — one entry per step:
```json
{
  "english_step": "Search for Cake",
  "gherkin_keyword": "When",
  "gherkin_step_text": "I search for \"Cake\"",
  "is_new": true,
  "matched_pattern": "",
  "step_type": "action",
  "anticipated_method": "search_for_cake"
}
```

If a step already exists in the registry (`is_new: false`), it is **not** written as a new function — instead it is re-imported from the source step file.

---

### 4.2 Page Object Generator (`agents/page_object_generator.py`)

**Triggered:** First time a URL is visited during execution.

**Input:**
- Page URL and title
- List of DOM elements (tag, text, id, role, aria-label, placeholder, href)

**Output:**
```json
{
  "class_name": "HebHomePage",
  "locators": {
    "SEARCH_INPUT": "#search-input",
    "SHOPPING_LISTS_LINK": "a[aria-label='Shopping lists menu']",
    "SUBMIT_SEARCH_BUTTON": "button[aria-label='Submit search']"
  }
}
```

The generated page class contains **locators only** — no action methods.

---

### 4.3 Step Analyzer (`agents/step_analyzer.py`)

**Triggered:** For every step during execution.

**Input:**
- Gherkin step text
- Available locator constants from the current page class
- Existing method map (for deduplication)
- Optional retry hint (if previous attempt failed)

**Output:**
```json
{
  "locator_constant": "SEARCH_INPUT",
  "playwright_locator": "#search-input",
  "action": "fill_and_submit",
  "value": "Cake",
  "method_name": "search_for_cake",
  "is_existing_method": false,
  "reasoning": "SEARCH_INPUT is the text field; fill_and_submit fills it and presses Enter"
}
```

**Action types:**

| Action | WebActions call generated |
|---|---|
| `click` | `WebActions(page).click(PageClass.LOCATOR)` |
| `fill` | `WebActions(page).send_text(PageClass.LOCATOR, "value")` |
| `fill_and_submit` | `send_text(...)` + `press_key(..., "Enter")` |
| `assert_visible` | `WebActions(page).wait_for_visible(PageClass.LOCATOR)` |
| `hover` | `WebActions(page).hover(PageClass.LOCATOR)` |
| `select` | `WebActions(page).select_option(PageClass.LOCATOR, value="...")` |
| `navigate` | `page.goto("url")` |

---

## 5. LangGraph Workflow

### 5.1 State (`graph/state.py`)

```
run_id                  unique ID for this execution run
test_case_id            TC identifier (e.g. TC_001)
app_url                 starting URL
raw_steps               list of English step strings

current_step_index      0-based index of the step being executed
current_url             URL of the current page
current_page_title      title of the current page
page_elements           DOM elements captured by last inspection
current_page_key        registry key for the current page class
current_locators        locator constants for the current page
step_cache              {step::url → action} — avoids re-calling AI for known steps

current_action          action dict returned by step_analyzer
step_results            accumulated list of step outcomes
page_registry           {url_key → page class info}

highlight_elements      bool — highlight elements before acting
error_message           last error string
retry_count             retries for the current step (0 = passed / >0 = failed)
max_retries             configurable max (default 3)
status                  current workflow status string
final_report            assembled report dict
```

### 5.2 Graph topology

```
launch_browser
    │
    ▼
inspect_page ──[browser dead or stop]──► finalize
    │
    ▼ [route_after_inspect → generate_page_object]
    │
generate_page_object
    │  (loads from registry if page already seen, else calls AI)
    ▼
analyze_step
    │  (uses cache if step+url already known)
    ▼
execute_step
    │
    ├──[step passed + more steps]──► inspect_page  (loops back)
    ├──[step passed + all done]────► finalize
    ├──[step failed + retries left]► analyze_step  (retry with hint)
    ├──[max retries reached]───────► finalize
    ├──[stop requested]────────────► finalize
    └──[browser dead]──────────────► finalize
         │
         ▼
       finalize
         │  updates BDD step definitions with real implementations
         │  writes test data JSON
         │  writes framework test file
         │  closes browser
         ▼
        END
```

### 5.3 Routing logic summary

| Condition | Route to |
|---|---|
| Stop signal set | `finalize` |
| Browser dead (`BrowserDeadError` or Playwright "target closed") | `finalize` |
| `retry_count >= max_retries` | `finalize` |
| `retry_count > 0` | `analyze_step` (retry same step with hint) |
| Step passed + more steps | `inspect_page` |
| Step passed + all steps done | `finalize` |

---

## 6. BDD Framework Design

### 6.1 Page class — locators only

```python
# playwright-framework/pages/heb_com_page.py
from pages.base_page import BasePage

class HebHomePage(BasePage):
    """Page object for HebHomePage."""

    # ── Locators ──────────────────────────────────────────────────
    SEARCH_INPUT            = "#search-input"
    SHOPPING_LISTS_LINK     = "a[aria-label='Shopping lists menu']"
    SUBMIT_SEARCH_BUTTON    = "button[aria-label='Submit search']"
    CART_LINK               = "a[aria-label='Go to Cart page.']"

    # ── Actions ───────────────────────────────────────────────────
    def open(self) -> "HebHomePage":
        self.navigate_to()
        return self
```

No action methods are generated. All behaviour lives in step definitions.

---

### 6.2 Feature file

```gherkin
# TC_001: Check Shopping List
# URL: https://www.heb.com/
# Created: 2026-05-01
# Data: TC_001_check_shopping_list.json

Feature: Check Shopping List

  Scenario: Check Shopping List
    Given I am on the HEB home page
    When I verify the shopping list link is visible
    And I search for "Cake"
    Then the first item name should contain "Cake"
```

---

### 6.3 Step definition — before execution (placeholder)

```python
# playwright-framework/features/steps/TC_001_check_shopping_list_steps.py

from pytest_bdd import given, when, then, parsers, scenarios
from playwright.sync_api import Page

scenarios("../TC_001_check_shopping_list.feature")

@given("I am on the HEB home page")
def i_am_on_the_heb_home_page(page: Page):
    # Navigate to HEB home page
    # Anticipated: page_object.open()
    pass  # TODO: filled during execution

@when("I verify the shopping list link is visible")
def i_verify_the_shopping_list_link_is_visible(page: Page):
    # Verify shopping list link is visible
    pass  # TODO: filled during execution
```

---

### 6.4 Step definition — after execution (implemented)

```python
from pytest_bdd import given, when, then, parsers, scenarios
from playwright.sync_api import Page
from pages.heb_com_page import HebHomePage
from utils.web_actions import WebActions

scenarios("../TC_001_check_shopping_list.feature")

@given("I am on the HEB home page")
def i_am_on_the_heb_home_page(page: Page):
    # Navigate to HEB home page
    heb_home_page = HebHomePage(page)
    heb_home_page.open()

@when("I verify the shopping list link is visible")
def i_verify_the_shopping_list_link_is_visible(page: Page):
    # Verify shopping list link is visible
    WebActions(page).wait_for_visible(HebHomePage.SHOPPING_LISTS_LINK)

@when(parsers.parse('I search for "Cake"'))
def i_search_for_value(page: Page):
    # Search for Cake
    WebActions(page).send_text(HebHomePage.SEARCH_INPUT, 'Cake')
    WebActions(page).press_key(HebHomePage.SEARCH_INPUT, 'Enter')
```

---

### 6.5 Duplicate step handling

When TC_002 reuses a step already defined in TC_001, the step is **imported** rather than duplicated:

```python
# TC_002_search_flower_steps.py

# ── Reused steps ─────────────────────────────────────────────
# Given I am on the HEB home page  →  TC_001_check_shopping_list_steps.py::i_am_on_the_heb_home_page
# When I search for "Cake"          →  TC_001_check_shopping_list_steps.py::i_search_for_value

from features.steps.TC_001_check_shopping_list_steps import (
    i_am_on_the_heb_home_page,  # noqa: F401
    i_search_for_value,          # noqa: F401
)

# ── New step definitions ──────────────────────────────────────
@then("the flower results should be visible")
def the_flower_results_should_be_visible(page: Page):
    pass  # TODO: filled during execution
```

---

## 7. TC Lifecycle

```
Step 1 — User saves test case from UI
  ├── Step Dedup Agent scans existing step_registry.json
  ├── Gherkin steps generated (new or reused)
  ├── features/TC_00X_name.feature             ← written
  ├── features/steps/TC_00X_name_steps.py      ← written (placeholders)
  ├── data/TC_00X_name.json                    ← written (blank)
  └── test_registry.json updated

Step 2 — User clicks Execute
  ├── Browser launches (headless=false by default)
  ├── Per page visited:
  │     ├── DOM inspected (up to 80 elements captured)
  │     └── Page class created in pages/ (locators only)
  ├── Per step:
  │     ├── Step Analyzer picks locator + action
  │     ├── Playwright executes action
  │     └── Screenshot captured
  └── After all steps:
        ├── Step definitions updated (pass → WebActions call)
        ├── data/ file updated (if form inputs were used)
        ├── tests/ file written (legacy pytest format)
        └── Browser closed

Step 3 — Run BDD tests via pytest
  cd playwright-framework
  pytest features/steps/TC_001_check_shopping_list_steps.py -v
```

---

## 8. API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/test-cases` | List all test cases |
| `POST` | `/api/test-cases/stream` | Create TC with SSE progress stream |
| `GET` | `/api/test-cases/{id}` | Get single test case |
| `PUT` | `/api/test-cases/{id}` | Update TC name/URL/steps |
| `DELETE` | `/api/test-cases/{id}` | Delete TC + feature/step files |
| `POST` | `/api/test-cases/{id}/execute` | Start execution, returns `run_id` |
| `GET` | `/api/runs/{run_id}/stream` | SSE stream of live step results |
| `GET` | `/api/runs/{run_id}` | Get run state snapshot |
| `POST` | `/api/runs/{run_id}/stop` | Graceful stop (between steps) |
| `DELETE` | `/api/runs/{run_id}` | Immediate cancel |

---

## 9. Registry Files

### `test_registry.json` — TC metadata
```json
{
  "cases": {
    "TC_001": {
      "id": "TC_001",
      "name": "Check Shopping List",
      "filename": "TC_001_check_shopping_list.py",
      "app_url": "https://www.heb.com/",
      "steps": ["Verify Shopping List link is there", "Search the Cake"],
      "gherkin_steps": [...],
      "feature_file": "TC_001_check_shopping_list.feature",
      "steps_file": "TC_001_check_shopping_list_steps.py",
      "data_file": "TC_001_check_shopping_list.json",
      "status": "passed",
      "created_at": "2026-05-01T10:00:00"
    }
  }
}
```

### `framework_registry.json` — Page class index
```json
{
  "heb_com": {
    "url": "https://www.heb.com/",
    "class_name": "HebHomePage",
    "filename": "heb_com_page.py",
    "locators": { "SEARCH_INPUT": "#search-input", ... },
    "methods": ["open"],
    "method_map": {}
  }
}
```

### `step_registry.json` — Global step pattern index
```json
{
  "I search for \"Cake\"": {
    "full_step": "When I search for \"Cake\"",
    "function_name": "i_search_for_value",
    "steps_file": "TC_001_check_shopping_list_steps.py",
    "implemented": true,
    "page_class": "HebHomePage",
    "method_name": "SEARCH_INPUT"
  }
}
```

---

## 10. Configuration Reference

### `config/config.py` (Playwright Framework)

| Variable | Default | Description |
|---|---|---|
| `BROWSER` | `chromium` | Browser engine |
| `HEADLESS` | `false` | Run without visible window |
| `HIGHLIGHT_ELEMENTS` | `false` | Red border flash before each action |
| `SLOW_MO` | `0` | Millisecond delay between actions |
| `TIMEOUT` | `30000` | Default element wait timeout (ms) |
| `MAX_RETRIES` | `3` | WebActions retry count |
| `RETRY_DELAY` | `1.0` | Seconds between retries |

### `.env` (AI Test Engine)

| Variable | Description |
|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `PLAYWRIGHT_FRAMEWORK_PATH` | Relative/absolute path to framework |
| `PLAYWRIGHT_PYTHON` | Python interpreter for subprocess runs |
| `MAX_RETRIES` | Max step retries during execution |

---

## 11. Running Tests

```bash
cd playwright-framework

# Run all AI-generated BDD tests
pytest features/steps/ -v

# Run a specific test case
pytest features/steps/TC_001_check_shopping_list_steps.py -v

# Run with visible browser
HEADLESS=false pytest features/steps/ -v

# Run with element highlighting
HIGHLIGHT_ELEMENTS=true pytest features/steps/ -v

# Run with HTML report
pytest features/steps/ --html=reports/html-report/report.html --self-contained-html
```

---

## 12. Key Design Decisions

| Decision | Rationale |
|---|---|
| **Page class = locators only** | Single source of truth for selectors; step definitions own the behaviour; reduces coupling |
| **BDD (pytest-bdd) over plain pytest** | Gherkin step patterns enable automatic reuse detection across test cases |
| **SSE streaming for both creation and execution** | Users see live progress; no polling needed |
| **Index-based step matching in finalize** | Gherkin step order matches English step order exactly; no fuzzy text matching required |
| **Stop signal (not immediate cancel)** | Current step always completes cleanly; files are always written correctly |
| **Browser-dead detection in routing** | Stops retrying AI calls immediately when browser crashes — no wasted API calls |
| **Page class auto-recovery** | If page file is deleted, `_ensure_page_file_exists()` rebuilds it from registry |
| **Absolute path resolution** | `_fw()` resolves `PLAYWRIGHT_FRAMEWORK_PATH` relative to `ai-test-engine/`, not CWD |
