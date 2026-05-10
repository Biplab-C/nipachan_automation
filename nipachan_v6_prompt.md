# Nipachan v6 Prompt — Pre-MVP Plugin Architecture and Review Layer

## Repository

Start from the completed **v5** branch of Nipachan.

Create a new version called **v6**.

---

## Main Goal

v6 is still before MVP.

Do not add too many automation features.

The goal of v6 is to make v5 **product-ready internally** by adding:

```text
1. Plugin-ready step category architecture
2. User review flow for messy/vague steps
3. Better step normalization confidence handling
4. Safer placeholder lifecycle
5. Cleaner generated/shared step promotion design
6. Better reports and diagnostics
7. Strong extension contracts for future versions
```

v6 should prepare Nipachan so future updates become Lego blocks.

---

## Core Principle

v5 created the robust Gherkin-first core.

v6 should make that core extensible.

Do not reintroduce v4 complexity.

Do not add advanced locator intelligence, AI healing, or complex atomic execution yet.

---

# Part 1 — v6 Architecture Goal

Target concept:

```text
Raw user step
↓
StepNormalizer
↓
NormalizedStep
↓
StepCatalog from scanned step definition files
↓
StepMatcher
↓
StepCategoryPlugin router
↓
FeatureWriter
↓
StepFileWriter
↓
ImplementationGenerator using plugin templates
↓
TestRunner
↓
ReportCollector
```

The important v6 addition is the plugin router.

---

# Part 2 — Add Core Contracts

Create or refine:

```text
ai-test-engine/core/contracts.py
```

Define clear interfaces or abstract base classes:

```python
class StepNormalizer:
    def normalize(self, raw_steps: list[str], context: dict) -> list[NormalizedStep]:
        ...

class StepCatalogProvider:
    def scan(self) -> list[StepDefinition]:
        ...

class StepMatcher:
    def match(self, step: NormalizedStep, catalog: list[StepDefinition]) -> StepMatchResult:
        ...

class StepCategoryPlugin:
    category: str

    def can_handle(self, step: NormalizedStep) -> bool:
        ...

    def generate_placeholder(self, step: NormalizedStep) -> str:
        ...

    def generate_implementation(self, step: NormalizedStep) -> str:
        ...

    def supported_patterns(self) -> list[str]:
        ...

class TestRunner:
    def run(self, test_case_id: str) -> RunResult:
        ...
```

---

# Part 3 — Core Data Models

Create or refine:

```text
ai-test-engine/core/models.py
```

Models:

```python
@dataclass
class TestCaseInput:
    name: str
    app_url: str
    raw_steps: list[str]

@dataclass
class NormalizedStep:
    raw_step: str
    keyword: str
    step_text: str
    step_pattern: str
    category: str
    parameters: dict
    function_name: str
    confidence: float
    needs_review: bool
    ambiguity_reason: str = ""

@dataclass
class StepDefinition:
    keyword: str
    pattern: str
    regex: str
    function_name: str
    file_path: str
    implemented: bool
    source: str

@dataclass
class StepMatchResult:
    matched: bool
    match_type: str
    confidence: float
    step_definition: StepDefinition | None
    reason: str

@dataclass
class StepReviewItem:
    raw_step: str
    normalized_step: str
    confidence: float
    status: str
    reason: str

@dataclass
class RunResult:
    test_case_id: str
    status: str
    passed: int
    failed: int
    skipped: int
    report_path: str | None
    errors: list[str]
```

---

# Part 4 — Plugin Architecture

Create:

```text
ai-test-engine/implementation/plugins/
```

Plugins:

```text
base.py
navigation_plugin.py
search_plugin.py
link_plugin.py
button_plugin.py
assertion_plugin.py
form_plugin.py
dropdown_plugin.py
manual_review_plugin.py
```

Each plugin must implement:

```python
class StepCategoryPlugin:
    category: str

    def can_handle(self, step: NormalizedStep) -> bool:
        ...

    def generate_placeholder(self, step: NormalizedStep) -> str:
        ...

    def generate_implementation(self, step: NormalizedStep) -> str:
        ...

    def supported_patterns(self) -> list[str]:
        ...
```

MVP-supported plugin categories:

```text
navigation
search
link_assertion
link_click
button_click
text_assertion
form_input
dropdown_select
manual_review
```

Unknown or low-confidence steps should route to `ManualReviewPlugin`.

---

# Part 5 — Plugin Registry

Create:

```text
ai-test-engine/implementation/plugin_registry.py
```

It should register plugins:

```python
plugins = [
    NavigationPlugin(),
    SearchPlugin(),
    LinkPlugin(),
    ButtonPlugin(),
    AssertionPlugin(),
    FormPlugin(),
    DropdownPlugin(),
    ManualReviewPlugin(),
]
```

Router behavior:

```text
1. If step.needs_review is true, route to ManualReviewPlugin unless user approved it.
2. Else find plugin where can_handle(step) is true.
3. If multiple plugins match, choose highest priority.
4. If no plugin matches, route to ManualReviewPlugin.
```

---

# Part 6 — User Review Flow

Add a pre-save review flow for normalized steps.

After user submits raw test steps:

```text
1. Normalize steps.
2. Build review table.
3. UI shows raw step, normalized step, category, confidence, status.
4. User may accept, edit, or mark manual.
5. Only accepted steps are saved as ready.
6. Manual steps are saved as placeholders but not auto-implemented.
```

Review item example:

```json
{
  "raw_step": "Go next",
  "normalized_step": "When I click \"Next\" button",
  "category": "button_click",
  "confidence": 0.70,
  "status": "needs_review",
  "reason": "Likely button action, but target is not fully confirmed."
}
```

UI status options:

```text
ready
needs_review
manual_only
unsupported
```

API can support this with two endpoints:

```text
POST /api/test-cases/preview
POST /api/test-cases
```

`preview` returns normalized review items.

`create` saves the accepted/edited result.

---

# Part 7 — Step Normalization Upgrade

Improve normalization output.

Every normalized step must include:

```json
{
  "raw_step": "...",
  "keyword": "When",
  "step_text": "I search for \"Cake\"",
  "step_pattern": "I search for \"{search_term}\"",
  "category": "search",
  "parameters": {
    "search_term": "Cake"
  },
  "function_name": "i_search_for_value",
  "confidence": 0.95,
  "needs_review": false,
  "ambiguity_reason": "",
  "alternatives": []
}
```

Add alternatives for medium-confidence cases:

```json
"alternatives": [
  {
    "step_text": "I click \"Next\" button",
    "category": "button_click",
    "confidence": 0.70
  },
  {
    "step_text": "I click \"Next\" link",
    "category": "link_click",
    "confidence": 0.62
  }
]
```

Do not auto-use alternatives unless user selects them.

---

# Part 8 — Confidence Policy

Implement strict confidence policy:

```text
confidence >= 0.85:
  status = ready

0.60 <= confidence < 0.85:
  status = needs_review

confidence < 0.60:
  status = manual_only
```

Effects:

```text
ready:
  can be matched/reused
  can be auto-implemented if plugin supports it

needs_review:
  can be saved
  cannot be semantically reused unless user accepts
  cannot be auto-implemented unless user accepts

manual_only:
  saved as placeholder
  not auto-implemented
  execution should clearly fail or skip with manual review message
```

---

# Part 9 — Safe Duplicate Matching in v6

Use v5 scanner-based StepCatalog.

No permanent step registry.

Matching order remains:

```text
1. Exact decorator pattern match
2. Parameterized regex match
3. Semantic match only for ready steps
4. New placeholder
```

For `needs_review` steps:

```text
Do not semantic-match automatically.
Use exact/regex match only.
```

For `manual_only` steps:

```text
Do not match semantically.
Create placeholder with manual review marker.
```

---

# Part 10 — Placeholder Lifecycle

Improve placeholder metadata.

Generated placeholder should include structured marker comments:

```python
@then(parsers.parse('I verify "{text}" is visible'))
def i_verify_text_is_visible_generated(page: Page, text: str):
    # NIPACHAN_PLACEHOLDER: true
    # NIPACHAN_CATEGORY: text_assertion
    # NIPACHAN_CONFIDENCE: 0.72
    # NIPACHAN_STATUS: needs_review
    # NIPACHAN_REASON: User confirmation required.
    raise NotImplementedError("Nipachan placeholder requires review or implementation.")
```

Scanner must read these markers.

ImplementationGenerator should only replace placeholder when:

```text
status = ready
category is supported
plugin can generate implementation
existing function is still placeholder
```

Never replace implemented functions.

---

# Part 11 — Shared vs Generated Step Promotion Design

Do not fully automate promotion in v6 unless safe.

Add design support:

```text
generated/ = TC-specific placeholders and generated implementations
shared/ = manually curated or explicitly promoted reusable steps
```

Add optional endpoint or CLI command:

```text
promote-step
```

Promotion requirements:

```text
1. Step is implemented.
2. Step has passed in at least one run.
3. Step pattern is generic.
4. No duplicate shared pattern exists.
5. User explicitly confirms promotion.
```

For v6, it is acceptable to implement only the internal service and leave UI simple.

---

# Part 12 — Implementation Plugins

Each plugin should generate deterministic code.

## SearchPlugin

Handles:

```text
I search for "{search_term}"
```

Generates or reuses shared search implementation.

## LinkPlugin

Handles:

```text
I verify "{link_text}" link is visible
I click "{link_text}" link
```

Uses:

```python
CommonPage.link_by_text(link_text)
```

## ButtonPlugin

Handles:

```text
I click "{button_text}" button
```

Uses:

```python
CommonPage.button_by_text(button_text)
```

## AssertionPlugin

Handles:

```text
I verify "{text}" is visible
I verify page contains "{text}"
```

Uses:

```python
CommonPage.text_by_value(text)
```

## FormPlugin

Handles:

```text
I enter "{value}" into "{field_name}"
```

Uses:

```python
CommonPage.input_by_label_or_placeholder(field_name)
```

## DropdownPlugin

Handles:

```text
I select "{value}" from "{field_name}"
```

Use simple generic select handling.

## ManualReviewPlugin

Generates placeholder only.

Never auto-implements.

---

# Part 13 — Report and Diagnostics

Improve report output.

For every test case creation, produce a creation summary:

```json
{
  "test_case_id": "TC_001",
  "feature_file": "...",
  "data_file": "...",
  "steps": [
    {
      "raw_step": "Search the Cake",
      "normalized": "When I search for \"Cake\"",
      "category": "search",
      "confidence": 0.95,
      "match_type": "parameterized_existing",
      "action": "reused_existing_step"
    }
  ]
}
```

For execution, produce:

```json
{
  "test_case_id": "TC_001",
  "status": "passed",
  "implemented_placeholders": 1,
  "reused_steps": 2,
  "manual_review_steps": 0,
  "pytest_exit_code": 0,
  "report_path": "..."
}
```

---

# Part 14 — API Changes

Add or refine:

```text
POST /api/test-cases/preview
POST /api/test-cases
GET /api/test-cases
GET /api/test-cases/{id}
POST /api/test-cases/{id}/execute
GET /api/test-cases/{id}/creation-summary
GET /api/runs/{run_id}
```

Preview endpoint:

Input:

```json
{
  "name": "Check Shopping List",
  "url": "https://example.com",
  "steps": ["Search the Cake", "Go next"]
}
```

Output:

```json
{
  "review_items": [
    {
      "raw_step": "Search the Cake",
      "normalized_step": "When I search for \"Cake\"",
      "confidence": 0.95,
      "status": "ready"
    },
    {
      "raw_step": "Go next",
      "normalized_step": "When I click \"Next\" button",
      "confidence": 0.70,
      "status": "needs_review"
    }
  ]
}
```

Create endpoint should accept reviewed/edited normalized steps.

---

# Part 15 — UI Review Table

Add a simple review table in UI.

Columns:

```text
Raw Step
Normalized Step
Category
Confidence
Status
Action
```

Actions:

```text
Accept
Edit
Mark Manual
```

For v6, keep UI basic.

---

# Part 16 — File Safety

Keep v5 atomic writing rules.

Add:

```text
1. Never replace non-placeholder function.
2. Never promote generated step to shared without explicit confirmation.
3. Preserve user code.
4. Create backups before modifying step files.
5. If plugin generation fails, leave placeholder unchanged.
```

---

# Part 17 — No Reintroduction of v4 Complexity

Do not add:

```text
advanced locator intelligence
AI healing
complex atomic action graphs
rich page locator inventory
runtime self-modifying execution
browser DOM familiarization as required core flow
```

Those are future optional plugins, not v6 core.

---

# Part 18 — Tests Required

Add tests for:

```text
PluginRegistry routes ready step to correct plugin
PluginRegistry routes needs_review step to ManualReviewPlugin unless accepted
StepNormalizer returns confidence/status
Preview endpoint returns review items
Create endpoint accepts reviewed steps
Placeholder markers are written
Scanner reads placeholder markers
ImplementationGenerator replaces only placeholders
Implemented functions are not overwritten
Promotion service refuses unsafe promotion
Creation summary includes match/reuse decisions
No permanent step_registry.json exists
```

---

# Part 19 — Acceptance Criteria

v6 is successful if:

```text
1. User can preview messy steps before saving.
2. High-confidence steps are marked ready.
3. Medium-confidence steps are marked needs_review.
4. Low-confidence steps are manual_only.
5. User can accept/edit reviewed steps.
6. Step matching still uses scanned step definitions, not JSON registry.
7. Plugin architecture generates deterministic implementations.
8. Implemented shared steps are never overwritten.
9. Placeholder lifecycle is clear and scannable.
10. Reports explain what was reused, generated, or left for review.
```

---

# Part 20 — Deliverables

Provide:

```text
1. Summary of v6 changes.
2. New plugin architecture explanation.
3. Files changed.
4. Example preview API response.
5. Example UI review flow.
6. Example placeholder with metadata markers.
7. Example creation summary.
8. Confirmation that v4 complexity was not reintroduced.
9. Test results.
```

---

## Final v6 Target

```text
Nipachan v6 is a pre-MVP, plugin-ready BDD automation generator.

It keeps v5’s Gherkin-first robustness and adds:
- step category plugins
- review flow for vague steps
- confidence policy
- safer placeholder lifecycle
- better diagnostics

It does not add advanced AI execution, healing, or locator intelligence yet.
```
