# Nipachan v5 — Gherkin-First BDD Automation Generator

**Repo:** `https://github.com/Biplab-C/nipachan_automation/tree/v4`
Create a new branch/version: **v5**

---

## Goal

```
User writes plain English steps
→ AI normalizes to Gherkin
→ Scanner reads existing step definitions
→ Duplicates detected, reuse or create placeholders
→ Feature file written
→ Blank data JSON written
→ Supported placeholders implemented via deterministic templates
→ pytest-bdd executes
```

AI normalizes intent only. Templates generate code. No free-form Python from AI.

---

## What to Remove from v4

Disable or isolate — do not delete unless safe:

- Advanced Locator Intelligence
- Atomic action planning
- AI-based healing
- Locator registry as runtime dependency
- Page registry as runtime dependency
- Permanent `step_registry.json`

**Keep:** FastAPI UI, test case creation, feature file generation, blank JSON creation, pytest-bdd execution, WebActions, shared step definitions, CommonPage helpers, test registry (UI index only).

---

## Folder Structure

```
ai-test-engine/
  core/
    models.py
    contracts.py
    result.py
    errors.py
  authoring/
    test_case_service.py
    normalization_service.py
  bdd/
    feature_writer.py
    step_definition_scanner.py
    step_matcher.py
    step_file_writer.py
    data_json_writer.py
  implementation/
    implementation_generator.py
    supported_categories.py
    templates/
      search_template.py
      link_template.py
      button_template.py
      assertion_template.py
      form_template.py
  execution/
    test_runner.py
    run_service.py
    report_collector.py
  providers/
    llm/
      base.py
      deepseek_provider.py
      mock_provider.py
    storage/
      atomic_writer.py
      file_storage.py
  api/
    routes.py
  main.py

playwright-framework/
  features/
    TC_001_example.feature
    steps/
      shared/
        navigation_steps.py
        search_steps.py
        link_steps.py
        assertion_steps.py
        form_steps.py
      generated/
        TC_001_example_steps.py
  pages/
    base_page.py
    common_page.py
  data/
    TC_001_example.json
  utils/
    web_actions.py
    json_utils.py
  conftest.py
```

---

## Source of Truth

| Artifact | Role |
|---|---|
| Feature files | Scenario source of truth |
| Step definition files | Reusable implementation source of truth |
| Data JSON | Test data source of truth |
| `test_registry.json` | UI index only — no implementation truth |

No permanent `step_registry.json`. Step files are the real registry.

---

## StepDefinitionScanner

Scans:
- `playwright-framework/features/steps/shared/`
- `playwright-framework/features/steps/generated/`

Extracts `@given`, `@when`, `@then` (plain and `parsers.parse`) decorators into an in-memory catalog:

```json
{
  "keyword": "when",
  "pattern": "I search for \"{search_term}\"",
  "regex": "^I search for \"(?P<search_term>.+)\"$",
  "function_name": "i_search_for_value",
  "file_path": "features/steps/shared/search_steps.py",
  "implemented": true,
  "source": "shared"
}
```

Optional cache at `.temp/step_catalog_cache.json` — not source of truth, deletable.

---

## Placeholder Detection

A step is **unimplemented** if the function body:
- contains only `pass`
- raises `NotImplementedError`
- contains `# NIPACHAN_PLACEHOLDER: true`

Preferred placeholder format:

```python
@then(parsers.parse('I verify "{link_text}" link is visible'))
def i_verify_link_is_visible(page: Page, link_text: str):
    # NIPACHAN_PLACEHOLDER: true
    raise NotImplementedError("Auto implementation pending")
```

---

## Step Normalization

Normalize each raw English step to structured JSON:

```json
{
  "raw_step": "Search the Cake",
  "keyword": "When",
  "step_text": "I search for \"Cake\"",
  "step_pattern": "I search for \"{search_term}\"",
  "category": "search",
  "parameters": {"search_term": "Cake"},
  "function_name": "i_search_for_value",
  "confidence": 0.95,
  "needs_review": false
}
```

Supported categories: `navigation`, `search`, `link_assertion`, `link_click`, `button_click`, `text_assertion`, `form_input`, `dropdown_select`, `unknown`

---

## Confidence Rules

| Confidence | Behavior |
|---|---|
| ≥ 0.85 | Accept, allow duplicate matching and reuse |
| 0.60–0.84 | Accept as draft, create placeholder, `needs_review = true`, no auto-reuse |
| < 0.60 | Placeholder only, `needs_review = true`, no auto-implement |

---

## Step Matching Order

1. Exact pattern match
2. Parameterized regex match
3. Semantic AI match — only if confidence ≥ 0.85
4. No safe match → create new placeholder

---

## Test Case Creation Flow

1. Generate ID: `TC_001`, `TC_002`, etc.
2. Create blank data JSON immediately.
3. Scan step definitions via `StepDefinitionScanner`.
4. Normalize each raw step.
5. Match against `StepCatalog`.
6. Write feature file.
7. Write placeholder definitions only for unmatched steps.
8. Store minimal metadata for UI.

---

## Blank Data JSON

Always created, even if no data is needed:

```json
{
  "test_case_id": "TC_001",
  "data": {}
}
```

---

## Feature File Format

```gherkin
Feature: Check Shopping List

  Scenario: Check Shopping List
    Given I am on the application home page
    Then I verify "Shopping List" link is visible
    When I search for "Cake"
```

---

## Step File Writer Rules

- Implemented step found → do not duplicate
- Placeholder found → reuse
- No match → create placeholder in `features/steps/generated/`
- Reusable implemented steps live in `features/steps/shared/` only
- Never import steps from other TC-specific generated files

---

## Shared Step Definitions

Implement these in shared modules:

```
Given I am on the application home page
When I search for "{search_term}"
Then I verify "{link_text}" link is visible
When I click "{link_text}" link
Then I verify "{text}" is visible
When I enter "{value}" into "{field_name}"
When I click "{button_text}" button
```

---

## CommonPage Helpers

```python
class CommonPage:

    @staticmethod
    def _escape_xpath_text(text: str) -> str:
        # Safe XPath string escaping
        ...

    @staticmethod
    def link_by_text(text: str) -> str:
        escaped = CommonPage._escape_xpath_text(text)
        return f"xpath=//a[normalize-space()={escaped} or contains(normalize-space(), {escaped})]"

    @staticmethod
    def button_by_text(text: str) -> str:
        escaped = CommonPage._escape_xpath_text(text)
        return f"xpath=//button[normalize-space()={escaped} or contains(normalize-space(), {escaped})]"

    @staticmethod
    def text_by_value(text: str) -> str:
        escaped = CommonPage._escape_xpath_text(text)
        return f"xpath=//*[normalize-space()={escaped} or contains(normalize-space(), {escaped})]"
```

No unresolved `{text}` templates may be returned.

---

## WebActions Safety

Required methods: `click`, `send_text`, `press_key`, `wait_for_visible`, `assert_text_visible`, `select_option`

Mandatory guard — called before every Playwright action:

```python
def _validate_locator(locator: str):
    if "{" in locator and "}" in locator:
        raise ValueError(f"Unresolved locator template: {locator}")
```

---

## Implementation Generator

AI outputs category + parameters only. Templates generate code.

Supported: `search`, `link_assertion`, `link_click`, `button_click`, `text_assertion`, `form_input`, `dropdown_select`

If category is `unknown`: keep placeholder, mark `needs_review`, do not auto-implement.

---

## Execution Flow

1. Load test case metadata.
2. Scan generated step files for placeholders.
3. Implement supported placeholder categories via deterministic templates.
4. Do not overwrite shared implemented steps.
5. Run pytest-bdd.
6. Collect result.

No runtime AI healing. Pre-run implementation only.

---

## Atomic File Writing

1. Write to temp file.
2. Validate content.
3. Atomically replace target.
4. Backup before modifying existing Python step files.
5. Never auto-overwrite implemented shared steps.
6. Preserve user edits where possible.

---

## Tests Required

- `StepDefinitionScanner` extracts decorators correctly
- `StepDefinitionScanner` detects placeholders
- `StepMatcher` exact match
- `StepMatcher` parameterized match
- `StepMatcher` does not reuse on low confidence
- `FeatureWriter` produces valid feature file
- `DataJsonWriter` always creates blank JSON
- `StepFileWriter` creates placeholders only for new steps
- `WebActions` rejects unresolved locators
- Shared search step is reused across test cases
- No permanent `step_registry.json` is created or read

---

## Acceptance Scenarios

**TC_001** — steps: `Verify Shopping List link is there`, `Search the Cake`
- Blank JSON created
- Feature file created
- Reuses shared search + link steps
- No duplicate function created
- No `step_registry.json` touched

**TC_002** — step: `Search the Milk`
- Reuses `When I search for "{search_term}"`
- Does not create `i_search_for_milk`

**Unclear step** — `Make sure result is ok`
- `needs_review = true`, placeholder created, not auto-implemented, not reused

**Execution**
- Shared implemented steps run as-is
- Supported placeholders filled by templates pre-run
- Unknown placeholders remain marked
- No unresolved `{...}` locator reaches Playwright
