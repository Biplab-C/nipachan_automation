# Claude Code Implementation Prompt
## AI-Powered Test Automation with LangGraph + DeepSeek + Playwright

---

## Context

I have an existing Playwright test framework. I want to build an AI-powered layer on top of it that:
- Accepts manual test steps written in plain English via a web UI
- Uses LangGraph to orchestrate multiple DeepSeek AI agents
- Converts those steps into Playwright scripts and executes them against my existing framework
- Shows live results back in the UI with self-healing retry on failure

---

## What already exists (do not recreate)

- A Playwright framework located at `./playwright-framework/`
- It has existing page objects, fixtures, and a `playwright.config.ts`
- Tests are run via `npx playwright test` or a programmatic API
- Assume Node.js 18+ is available

---

## What needs to be built

### 1. Project structure

Create the following alongside the existing Playwright framework:

```
ai-test-engine/
├── agents/
│   ├── __init__.py
│   ├── base.py              # DeepSeek client setup
│   ├── nlp_parser.py        # Agent 1: English → structured actions
│   ├── code_generator.py    # Agent 2: Actions → Playwright script
│   └── error_analyzer.py    # Agent 3: Failure → fix suggestion
├── graph/
│   ├── __init__.py
│   ├── state.py             # LangGraph TypedDict state definition
│   ├── nodes.py             # All LangGraph node functions
│   ├── edges.py             # Conditional edge / router logic
│   └── workflow.py          # Graph assembly and compilation
├── execution/
│   ├── __init__.py
│   └── runner.py            # Calls into the existing Playwright framework
├── api/
│   ├── __init__.py
│   └── routes.py            # FastAPI routes (invoke, status, stream, cancel)
├── ui/
│   └── index.html           # Single-page UI (plain HTML/JS, no framework)
├── .env.example
├── requirements.txt
└── main.py                  # Entry point: uvicorn server
```

---

### 2. DeepSeek agent configuration (`agents/base.py`)

- Use the `openai` Python SDK pointed at DeepSeek's base URL (`https://api.deepseek.com/v1`)
- Read `DEEPSEEK_API_KEY` from environment variable
- Expose a single shared `client` instance imported by all agents
- Model routing:
  - Orchestration/planning → `deepseek-reasoner`
  - NLP parsing, code generation, error analysis → `deepseek-chat`

---

### 3. LangGraph state (`graph/state.py`)

Define a `TestWorkflowState` as a `TypedDict` with these fields:

| Field | Type | Purpose |
|---|---|---|
| `run_id` | str | Unique identifier for this run |
| `raw_steps` | list[str] | Original plain English steps from user |
| `app_url` | str | Target application URL |
| `selector_hints` | dict | Optional CSS/XPath hints user provides |
| `parsed_actions` | list[dict] | Output of NLP parser agent |
| `generated_script` | str | Output of code generator agent |
| `execution_result` | dict | Output from Playwright runner |
| `step_results` | list[dict] | Per-step pass/fail with screenshots |
| `error_message` | str | Last error if execution failed |
| `fix_suggestion` | dict | Output of error analyzer agent |
| `retry_count` | int | Current retry attempt number |
| `max_retries` | int | Max allowed retries (default: 3) |
| `status` | str | Current workflow status string |
| `final_report` | dict | Assembled final output |

---

### 4. LangGraph nodes (`graph/nodes.py`)

Implement these five node functions. Each receives `TestWorkflowState` and returns a partial state dict.

**`parse_node`**
- Calls `nlp_parser` agent with `raw_steps` and `selector_hints`
- Prompt instructs DeepSeek to return a JSON array of action objects:
  `{ action, selector, value, assertion, description }`
- Updates `parsed_actions` in state
- Sets `status = "parsing"`

**`generate_node`**
- Calls `code_generator` agent with `parsed_actions` and `app_url`
- Instructs DeepSeek to generate a self-contained Playwright Python script
- The script must:
  - Import from the existing framework's fixtures if available
  - Use `async/await` with `playwright.async_api`
  - Use `page.locator()` for all selectors
  - Capture a screenshot after each step
  - Write results to a temp JSON file that the runner reads
- Updates `generated_script` in state
- Sets `status = "generating"`

**`execute_node`**
- Calls `execution/runner.py` which writes the generated script to a temp file and runs it using subprocess against the existing Playwright framework
- Collects stdout, stderr, exit code, and the JSON results file
- Updates `execution_result`, `step_results`, `error_message` in state
- Sets `status = "running"`

**`analyze_error_node`**
- Only called when execution fails
- Calls `error_analyzer` agent with `error_message`, `generated_script`, and the failed step details
- Agent returns: `{ root_cause, fixed_selector, fixed_action, patched_script, retry }`
- Updates `fix_suggestion` and applies `patched_script` to `generated_script` if provided
- Sets `status = "retrying"`

**`finalize_node`**
- Assembles `final_report` from `step_results`, `retry_count`, overall pass/fail
- Sets `status` to `"completed"` or `"failed"`

---

### 5. Conditional edges (`graph/edges.py`)

Implement a `route_after_execution` function used as a conditional edge after `execute_node`:

```
if execution passed       → "finalize"
if failed and retries < max_retries → "analyze_error"
if failed and retries >= max_retries → "finalize"
```

Implement a `route_after_analysis` function after `analyze_error_node`:

```
if fix_suggestion.retry == True  → "generate"   (re-generate with patch)
if fix_suggestion.retry == False → "finalize"
```

---

### 6. Graph assembly (`graph/workflow.py`)

- Create a `StateGraph(TestWorkflowState)`
- Add all five nodes
- Set entry point to `parse_node`
- Wire edges:
  - `parse → generate` (always)
  - `generate → execute` (always)
  - `execute → route_after_execution` (conditional)
  - `analyze_error → route_after_analysis` (conditional)
  - `finalize → END`
- Attach a `MemorySaver` checkpointer
- Compile and export as `workflow = graph.compile(checkpointer=...)`

---

### 7. Execution runner (`execution/runner.py`)

- Accepts the generated Python script as a string
- Writes it to a temp file in a `./temp_runs/` directory
- Runs it with `subprocess` using the existing framework's virtual environment Python
- Passes `app_url` as an environment variable so the script can read it
- Reads the JSON results file written by the script
- Returns structured `{ passed, step_results, error, duration_ms }`
- Cleans up temp files after run

---

### 8. FastAPI API (`api/routes.py`)

Implement these endpoints:

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/run` | Start a new workflow. Body: `{ steps, app_url, selector_hints }`. Returns `run_id`. |
| `GET` | `/api/run/{run_id}` | Get current state snapshot for a run |
| `GET` | `/api/run/{run_id}/stream` | SSE stream of state updates as each node completes |
| `DELETE` | `/api/run/{run_id}` | Cancel a running workflow |
| `GET` | `/api/runs` | List all runs with status summary |

- Use `graph.ainvoke()` for execution (non-blocking via `BackgroundTasks`)
- Use `graph.astream()` with `stream_mode="updates"` for the SSE endpoint
- Use LangGraph's `thread_id = run_id` as the config for checkpointing

---

### 9. Frontend UI (`ui/index.html`)

Single HTML file, no build step, no framework. Use vanilla JS and CSS variables for light/dark mode support.

**Layout — three panels:**

**Left panel — Test input**
- Textarea for plain English test steps (one step per line)
- Input for App URL
- Optional textarea for selector hints (JSON format, collapsed by default)
- "Execute" button — disabled while a run is in progress
- "Cancel" button — appears only during a run

**Middle panel — Live execution status**
- Status badge showing current workflow node (Parsing / Generating / Running / Retrying / Done)
- Step-by-step list that populates in real time as SSE events arrive
- Each step row shows: step number, description, status icon (spinner / ✓ / ✗), duration
- Retry counter badge if retries are happening

**Right panel — Results**
- Overall pass/fail banner
- Collapsible section per step showing: action taken, selector used, screenshot thumbnail (if available), error message if failed
- "Download Report" button that exports `final_report` as JSON
- "Re-run" button that pre-fills the left panel and starts a new run

**SSE connection logic:**
- On Execute click: POST to `/api/run`, get `run_id`, open `EventSource` to `/api/run/{run_id}/stream`
- Parse each SSE event and update the relevant panel live
- Close the EventSource when status is `completed`, `failed`, or `cancelled`

---

### 10. Environment and dependencies

**`.env.example`:**
```
DEEPSEEK_API_KEY=your_key_here
PLAYWRIGHT_FRAMEWORK_PATH=./playwright-framework
PLAYWRIGHT_PYTHON=./playwright-framework/.venv/bin/python
MAX_RETRIES=3
TEMP_RUNS_DIR=./temp_runs
```

**`requirements.txt`** must include:
```
langgraph
langchain-core
openai
fastapi
uvicorn
python-dotenv
```

**`main.py`** must:
- Load `.env`
- Mount `ui/` as a static directory at `/`
- Include the API router at `/api`
- Start with `uvicorn.run` on port 8000

---

## Agent prompt guidelines

When writing the system prompts for each DeepSeek agent, follow these rules:

- **NLP parser**: instruct it to return ONLY valid JSON, no markdown fences, no explanation. Schema must be strict. If a step is ambiguous, include a `"confidence": 0.0-1.0` field.
- **Code generator**: instruct it to return ONLY Python code, no markdown fences. The script must be runnable as-is. It must write results to `os.environ["RESULTS_FILE"]`.
- **Error analyzer**: instruct it to return ONLY valid JSON. It must identify whether the issue is a selector problem, timing problem, or logic problem, and set `"retry": true/false` accordingly.

---

## Integration constraints (important)

- Do NOT modify anything inside `./playwright-framework/`
- The generated Playwright scripts must be compatible with whatever `playwright.config.ts` already exists in the framework
- If the framework uses TypeScript, the code generator agent should emit TypeScript, not Python — detect this by checking if `playwright.config.ts` exists
- The runner should invoke tests the same way the framework does today (check for `package.json` scripts like `test` or `e2e`)

---

## Deliver in this order

1. `requirements.txt` and `.env.example`
2. `agents/` — all three agent files
3. `graph/` — state, nodes, edges, workflow
4. `execution/runner.py`
5. `api/routes.py`
6. `ui/index.html`
7. `main.py`
8. A `README.md` with setup steps and how to run

For each file, explain briefly what it does before writing it.