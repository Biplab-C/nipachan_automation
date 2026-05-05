# Claude Code Prompt — Nipachan Locator Intelligence & Stable Action Plan Implementation

## Context
You are working on **Nipachan**, an AI-based autonomous test automation engine.

Current stack:
- Python
- FastAPI
- LangGraph
- DeepSeek / LLM agent layer
- Playwright
- pytest-bdd

Current high-level architecture:
- `ai-test-engine/` handles AI agents, browser execution, LangGraph workflow, API, and UI.
- `playwright-framework/` stores generated page objects, BDD feature files, step definitions, test data, and utility classes.

Current design already includes:
- `agents/step_dedup_agent.py`
- `agents/page_object_generator.py`
- `agents/step_analyzer.py`
- `execution/browser_controller.py`
- `execution/bdd_manager.py`
- `execution/framework_manager.py`
- `graph/state.py`
- `graph/nodes.py`
- `graph/edges.py`
- `graph/workflow.py`
- `framework_registry.json`
- `step_registry.json`
- `test_registry.json`

## Goal
Refactor and extend the framework so Nipachan does not rediscover locators for every test case.

When Nipachan encounters a new page, it should create a reusable **smart locator inventory** for that page.

The inventory must support:
- Static locators
- Collection locators
- Relative locators
- Parameterized locators
- Locator deduplication
- Locator validation
- Locator confidence score
- Reuse across future test cases

Important example:
On an ecommerce search results page, do not create separate locators like:

```python
CAKE_PRODUCT = "//span[text()='Cake']"
MILK_PRODUCT = "//span[text()='Milk']"
RICE_PRODUCT = "//span[text()='Rice']"
```

Instead, create reusable parameterized locators like:

```python
PRODUCT_CARD_BY_NAME = "xpath=//div[contains(@class,'product-card')][.//*[normalize-space()='{product_name}']]"
ADD_TO_CART_BY_PRODUCT_NAME = "xpath=//div[contains(@class,'product-card')][.//*[normalize-space()='{product_name}']]//button[contains(., 'Add') or contains(@aria-label, 'Add')]"
```

---

# Implementation Instructions

## Step 1 — Add a Locator Intelligence module

Create a new module:

```text
ai-test-engine/locator_intelligence/
```

Suggested files:

```text
locator_intelligence/
├── models.py
├── page_profiler.py
├── dom_collector.py
├── element_classifier.py
├── pattern_detector.py
├── locator_generator.py
├── locator_deduplicator.py
├── locator_validator.py
└── locator_inventory_manager.py
```

Purpose:
This module is responsible for creating and maintaining reusable locators per page.

---

## Step 2 — Define locator data models

In `locator_intelligence/models.py`, define structured models or dataclasses for locator inventory.

Required concepts:

```python
LocatorType = "static" | "collection" | "relative" | "parameterized"
LocatorStrategy = "css" | "xpath" | "role" | "text" | "label" | "placeholder" | "test_id"
```

Example model shape:

```python
@dataclass
class LocatorDefinition:
    name: str
    locator_type: str
    strategy: str
    selector: str
    purpose: str
    role: str | None = None
    parameters: list[str] = field(default_factory=list)
    sample_values: list[str] = field(default_factory=list)
    match_count: int = 0
    visible_count: int = 0
    unique: bool = False
    confidence: float = 0.0
    source: str = "generated"
    validated: bool = False
```

Also define:

```python
@dataclass
class PageLocatorInventory:
    page_key: str
    class_name: str
    url: str
    url_patterns: list[str]
    title: str
    page_type: str
    locators: dict[str, LocatorDefinition]
```

---

## Step 3 — Update page identity logic

Do not use raw URL as the only page key.

Implement normalized page identity.

Rules:
- Remove tracking query params.
- Group similar URLs.
- Detect page type using URL, title, headings, and visible landmarks.
- Example `/search?q=cake`, `/search?q=milk`, and `/search?page=2` should map to one logical search results page.

Expected page keys:

```text
home_page
search_results_page
product_detail_page
cart_page
login_page
checkout_page
```

If the page type is unknown, generate a safe fallback key using domain and route.

---

## Step 4 — Capture meaningful page elements

In `dom_collector.py`, collect only meaningful elements, not raw full DOM.

Capture:
- buttons
- links
- inputs
- textareas
- selects
- checkboxes
- radio buttons
- visible headings
- table rows
- list items
- product cards or repeated cards
- elements with `data-testid`, `data-test`, `data-qa`
- elements with `aria-label`, `role`, `placeholder`, `name`, `id`

Each captured element should include:

```json
{
  "tag": "button",
  "text": "Add to Cart",
  "id": "",
  "class": "add-cart-btn",
  "role": "button",
  "aria_label": "Add Cake to cart",
  "placeholder": "",
  "data_testid": "add-to-cart",
  "visible": true,
  "bounding_box": {...},
  "parent_summary": {...},
  "dom_path": "..."
}
```

Avoid saving huge DOM snapshots in the registry. Use snapshots only for debugging or run evidence.

---

## Step 5 — Classify elements by purpose

In `element_classifier.py`, classify elements into semantic purposes.

Examples:

```text
search_input
submit_search
cart_link
login_button
product_card
product_name
product_price
add_to_cart_button
filter_option
sort_dropdown
pagination_next
checkout_button
form_field
primary_action
navigation_link
assertion_text
```

Use deterministic rules first:
- role
- tag
- placeholder
- aria-label
- text
- data-testid
- class names

Use LLM only when deterministic classification is not enough.

---

## Step 6 — Detect repeated patterns

In `pattern_detector.py`, detect repeated structures such as:
- product cards
- result rows
- table rows
- menu items
- list items
- filter options

When repeated structures contain similar child layout but different text values, infer parameterized locators.

Example repeated product cards:

```text
Card 1: Cake, ¥300, Add
Card 2: Milk, ¥200, Add
Card 3: Rice, ¥500, Add
```

Should generate:

```python
PRODUCT_CARDS
PRODUCT_CARD_BY_NAME
PRODUCT_PRICE_BY_NAME
ADD_TO_CART_BY_PRODUCT_NAME
```

---

## Step 7 — Generate locator candidates

In `locator_generator.py`, generate locator candidates using this priority:

```text
1. data-testid / data-test / data-qa
2. role + accessible name
3. stable id
4. name / placeholder / aria-label
5. stable CSS class combinations
6. Playwright text locator
7. relative XPath
8. absolute XPath only as last resort
```

Avoid absolute XPath unless there is no other option.

For static locators, generate constants like:

```python
SEARCH_INPUT = "css=input[type='search']"
CART_LINK = "role=link[name='Cart']"
SORT_DROPDOWN = "css=select[name='sort']"
```

For repeated entities, generate parameterized locators like:

```python
PRODUCT_CARD_BY_NAME = "xpath=//div[contains(@class,'product-card')][.//*[normalize-space()='{product_name}']]"
PRODUCT_PRICE_BY_NAME = "xpath=//div[contains(@class,'product-card')][.//*[normalize-space()='{product_name}']]//*[contains(@class,'price')]"
ADD_TO_CART_BY_PRODUCT_NAME = "xpath=//div[contains(@class,'product-card')][.//*[normalize-space()='{product_name}']]//button[contains(., 'Add') or contains(@aria-label, 'Add')]"
```

---

## Step 8 — Deduplicate locators

In `locator_deduplicator.py`, avoid creating duplicate locators.

Deduplication rules:
- Same selector means duplicate.
- Same purpose + same role + same parent pattern means duplicate.
- Value-specific locators with same structure should become one parameterized locator.
- Prefer parameterized locators over many hardcoded text locators.
- Prefer stable strategies over XPath when possible.

Example conversion:

Bad:

```python
CAKE_PRODUCT_NAME = "xpath=//span[text()='Cake']"
MILK_PRODUCT_NAME = "xpath=//span[text()='Milk']"
```

Good:

```python
PRODUCT_NAME_BY_TEXT = "xpath=//span[normalize-space()='{product_name}']"
```

Better for ecommerce:

```python
PRODUCT_CARD_BY_NAME = "xpath=//div[contains(@class,'product-card')][.//*[normalize-space()='{product_name}']]"
```

---

## Step 9 — Validate locators before saving

In `locator_validator.py`, every generated locator must be validated before being saved.

Validation checks:
- Does selector resolve?
- How many elements match?
- How many are visible?
- Is the locator unique when it should be unique?
- Is the locator stable after reload?
- Does the role/purpose match the expected element?
- For parameterized locators, validate with sample values.

Store validation metadata:

```json
{
  "match_count": 1,
  "visible_count": 1,
  "unique": true,
  "validated": true,
  "confidence": 0.94
}
```

For parameterized locators:

```json
{
  "parameters": ["product_name"],
  "sample_values": ["Cake", "Milk", "Rice"],
  "validated_samples": 3,
  "confidence": 0.89
}
```

---

## Step 10 — Update framework registry structure

Upgrade `framework_registry.json` so it stores rich locator inventory.

Target shape:

```json
{
  "search_results_page": {
    "page_key": "search_results_page",
    "class_name": "SearchResultsPage",
    "url_patterns": ["/search", "/products"],
    "title_pattern": "Search Results",
    "page_type": "search_results",
    "locators": {
      "SEARCH_INPUT": {
        "name": "SEARCH_INPUT",
        "locator_type": "static",
        "strategy": "css",
        "selector": "input[type='search']",
        "purpose": "search_input",
        "confidence": 0.94,
        "validated": true
      },
      "PRODUCT_CARD_BY_NAME": {
        "name": "PRODUCT_CARD_BY_NAME",
        "locator_type": "parameterized",
        "strategy": "xpath",
        "selector": "//div[contains(@class,'product-card')][.//*[normalize-space()='{product_name}']]",
        "parameters": ["product_name"],
        "purpose": "product_card",
        "sample_values": ["Cake", "Milk"],
        "confidence": 0.89,
        "validated": true
      }
    }
  }
}
```

Keep backward compatibility where possible, but prefer the new structure.

---

## Step 11 — Generate page objects with parameterized locator helpers

Update page object generation so locator-only page classes can include static helper methods for parameterized locators.

Example output:

```python
class SearchResultsPage(BasePage):
    SEARCH_INPUT = "css=input[type='search']"
    PRODUCT_CARDS = "css=[data-testid='product-card'], .product-card"

    PRODUCT_CARD_BY_NAME = (
        "xpath=//div[contains(@class,'product-card')]"
        "[.//*[normalize-space()='{product_name}']]"
    )

    ADD_TO_CART_BY_PRODUCT_NAME = (
        "xpath=//div[contains(@class,'product-card')]"
        "[.//*[normalize-space()='{product_name}']]"
        "//button[contains(., 'Add') or contains(@aria-label, 'Add')]"
    )

    @staticmethod
    def product_card_by_name(product_name: str) -> str:
        return SearchResultsPage.PRODUCT_CARD_BY_NAME.format(
            product_name=product_name
        )

    @staticmethod
    def add_to_cart_by_product_name(product_name: str) -> str:
        return SearchResultsPage.ADD_TO_CART_BY_PRODUCT_NAME.format(
            product_name=product_name
        )
```

Do not add business action methods to page classes. Page classes should remain locator-focused.

---

## Step 12 — Update WebActions to resolve locator strategies

If existing `WebActions` only accepts raw selector strings, extend it to support strategy prefixes.

Supported formats:

```text
css=input[type='search']
xpath=//button[text()='Add']
role=button[name='Add to Cart']
text=Checkout
placeholder=Search
label=Email
test_id=product-card
```

Create a resolver method:

```python
def resolve_locator(page: Page, locator: str):
    ...
```

Expected behavior:

```python
WebActions(page).click(SearchResultsPage.ADD_TO_CART_BY_PRODUCT_NAME.format(product_name="Cake"))
```

should work even when the locator uses `xpath=...` or `css=...` prefix.

---

## Step 13 — Update Step Analyzer to use inventory first

Modify `step_analyzer.py` so it does not ask the LLM to invent locators if the page inventory already has suitable locators.

New priority:

```text
1. Match step intent to existing locator inventory.
2. Prefer validated high-confidence locators.
3. Prefer parameterized locators for dynamic values.
4. Ask LLM only to choose among available candidates, not invent from scratch.
5. If no suitable locator exists, enrich page inventory and retry.
```

For a step like:

```gherkin
When I add "Cake" to the cart
```

The analyzer should return:

```json
{
  "action": "click",
  "locator_name": "ADD_TO_CART_BY_PRODUCT_NAME",
  "locator": "SearchResultsPage.add_to_cart_by_product_name(product_name)",
  "parameters": {
    "product_name": "Cake"
  },
  "confidence": 0.91
}
```

---

## Step 14 — Introduce atomic action plan

Do not directly convert one Gherkin step into one Playwright action.

Introduce a structured action plan.

Example:

```json
{
  "gherkin_step": "When I search for \"Cake\" and add the first item to cart",
  "intent": "search_and_add_product",
  "atomic_actions": [
    {
      "type": "fill",
      "locator_name": "SEARCH_INPUT",
      "value": "Cake"
    },
    {
      "type": "press_key",
      "locator_name": "SEARCH_INPUT",
      "value": "Enter"
    },
    {
      "type": "wait_visible",
      "locator_name": "PRODUCT_CARDS"
    },
    {
      "type": "click",
      "locator_name": "ADD_TO_CART_FIRST_PRODUCT"
    }
  ],
  "confidence": 0.88
}
```

This action plan should be saved in the run evidence before generating final code.

---

## Step 15 — Retry at atomic action level

Current retry is likely step-level. Change or prepare the design so retries happen at atomic action level.

Example:

```text
Step: Search Cake and add first item to cart
```

If search succeeds but add-to-cart fails, retry only the add-to-cart action, not the full search step.

---

## Step 16 — Promote code only after successful validation

Avoid writing final BDD step implementations directly during unstable execution.

Use this flow:

```text
1. Create temporary run artifact
2. Execute using structured action plan
3. Validate action results
4. Generate preview implementation
5. Promote to framework only when successful
```

Suggested folder:

```text
ai-test-engine/temp_runs/{run_id}/
├── action_plan.json
├── locator_inventory_diff.json
├── execution_log.json
├── screenshots/
└── generated_steps_preview.py
```

Only after success, update:

```text
playwright-framework/pages/
playwright-framework/features/steps/
framework_registry.json
step_registry.json
```

---

## Step 17 — Improve step registry with parameterized patterns

Avoid value-specific registry keys.

Bad:

```json
"I search for \"Cake\"": {...}
```

Good:

```json
"I search for \"{search_term}\"": {
  "function_name": "i_search_for_value",
  "parameters": ["search_term"],
  "implemented": true
}
```

Generated step:

```python
@when(parsers.parse('I search for "{search_term}"'))
def i_search_for_value(page: Page, search_term: str):
    WebActions(page).send_text(SearchResultsPage.SEARCH_INPUT, search_term)
    WebActions(page).press_key(SearchResultsPage.SEARCH_INPUT, "Enter")
```

---

## Step 18 — Avoid importing reusable steps from TC-specific files

Do not reuse steps like this:

```python
from features.steps.TC_001_check_shopping_list_steps import i_search_for_value
```

Instead, move reusable steps into shared files:

```text
features/steps/shared/search_steps.py
features/steps/shared/navigation_steps.py
features/steps/shared/cart_steps.py
features/steps/shared/assertion_steps.py
```

TC-specific files should only contain truly TC-specific steps.

---

## Step 19 — Add confidence scores everywhere

All AI or heuristic decisions should include confidence.

Required outputs should include:

```json
{
  "decision": "selected locator",
  "confidence": 0.91,
  "reason": "aria-label and role match add-to-cart intent"
}
```

Routing recommendation:

```text
confidence >= 0.85: execute normally
0.60 <= confidence < 0.85: execute with stronger validation
confidence < 0.60: do not promote generated code automatically
```

---

## Step 20 — Add safety guardrails

Because Nipachan writes and executes Python code, add guardrails.

Allowed actions:

```text
navigate within allowed domain
click
fill
press
select
hover
wait/assert visible
assert text
```

Blocked actions:

```text
shell commands
file deletion
local file access
credential extraction
unknown external domain navigation
arbitrary Python execution generated by LLM
```

LLM should produce structured JSON only. Deterministic code generator should create Python code.

---

# Expected Final Result

After implementation, Nipachan should behave like this:

```text
User creates test case
↓
Nipachan opens app URL
↓
If page is new, creates smart locator inventory
↓
Inventory includes static, collection, relative, and parameterized locators
↓
Step analyzer maps user steps to existing locator inventory
↓
Complex steps are decomposed into atomic actions
↓
Execution validates each action
↓
Successful action plan is promoted into BDD step definitions
↓
Future test cases reuse existing locator inventory and parameterized step patterns
```

# Core Principle

Do not let AI directly generate uncontrolled Playwright code.

AI should produce:
- normalized intent
- locator suggestions
- parameterized locator patterns
- atomic action plans
- confidence scores

Deterministic code should generate:
- page object files
- step definitions
- registry updates
- test data files

# Immediate Implementation Priority

Implement in this order:

1. Locator data models
2. Page identity normalization
3. DOM meaningful element collector
4. Locator generator
5. Parameterized locator generator
6. Locator deduplicator
7. Locator validator
8. Framework registry upgrade
9. Page object writer update
10. Step analyzer inventory-first logic
11. Atomic action plan
12. Temporary run artifacts
13. Safe promotion to framework files
14. Parameterized step registry
15. Shared step files
