"""
Manages BDD/Gherkin framework files:
  features/             — .feature files (Gherkin scenarios)
  features/steps/       — pytest-bdd step definition files
  data/                 — blank + populated test data JSON
  step_registry.json    — global step pattern registry (for dedup)
"""
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_ai_root = Path(__file__).parent.parent
STEP_REGISTRY_FILE = _ai_root / "step_registry.json"


# ── Path resolution (always absolute) ────────────────────────────────────────

def _fw() -> Path:
    raw = os.getenv("PLAYWRIGHT_FRAMEWORK_PATH", "")
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = (_ai_root / p).resolve()
        return p
    return (_ai_root.parent / "playwright-framework").resolve()


def _features_dir() -> Path:
    d = _fw() / "features"
    d.mkdir(parents=True, exist_ok=True)
    # Make features/ a package so step files can be imported from each other
    init = d / "__init__.py"
    if not init.exists():
        init.touch()
    return d


def _steps_dir() -> Path:
    d = _fw() / "features" / "steps"
    d.mkdir(parents=True, exist_ok=True)
    init = d / "__init__.py"
    if not init.exists():
        init.touch()
    return d


def _data_dir() -> Path:
    d = _fw() / "data"
    d.mkdir(exist_ok=True)
    return d


# ── Step Registry ─────────────────────────────────────────────────────────────

def _load_registry() -> dict:
    if STEP_REGISTRY_FILE.exists():
        return json.loads(STEP_REGISTRY_FILE.read_text(encoding="utf-8"))
    return {}


def _save_registry(reg: dict):
    STEP_REGISTRY_FILE.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def _normalize(step_text: str) -> str:
    """Strip keyword prefix for registry key."""
    return re.sub(r"^(Given|When|Then|And|But)\s+", "", step_text.strip(), flags=re.IGNORECASE)


def get_all_step_patterns() -> list[str]:
    """Return all registered step patterns (for dedup agent)."""
    return list(_load_registry().keys())


def register_step(keyword: str, step_text: str, function_name: str,
                  steps_file: str, implemented: bool = False):
    """Add a step to the global registry."""
    reg = _load_registry()
    pattern = _normalize(step_text)
    if pattern not in reg:
        reg[pattern] = {
            "full_step": f"{keyword} {step_text}",
            "function_name": function_name,
            "steps_file": steps_file,
            "implemented": implemented,
            "page_class": "",
            "method_name": "",
            "created_at": datetime.now().isoformat(),
        }
        _save_registry(reg)
        logger.info("Registered step: %s", pattern)


def mark_step_implemented(step_text: str, page_class: str, method_name: str,
                          playwright_locator: str = ""):
    """Update a registry entry when the step gets a real implementation."""
    reg = _load_registry()
    pattern = _normalize(step_text)
    if pattern in reg:
        reg[pattern].update({
            "implemented": True,
            "page_class": page_class,
            "method_name": method_name,
            "playwright_locator": playwright_locator,
        })
        _save_registry(reg)


# ── Feature File ──────────────────────────────────────────────────────────────

def _slug(text: str, max_len: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:max_len]


def create_feature_file(tc_id: str, tc_name: str, app_url: str,
                        gherkin_steps: list[dict]) -> str:
    """Write a Gherkin .feature file. Returns filename."""
    filename = f"{tc_id}_{_slug(tc_name)}.feature"
    filepath = _features_dir() / filename
    data_file = f"{tc_id}_{_slug(tc_name)}.json"

    lines = [
        f"# {tc_id}: {tc_name}",
        f"# URL: {app_url}",
        f"# Created: {datetime.now().strftime('%Y-%m-%d')}",
        f"# Data: {data_file}",
        "",
        f"Feature: {tc_name}",
        "",
        f"  Scenario: {tc_name}",
    ]

    for s in gherkin_steps:
        kw = s.get("gherkin_keyword", "When")
        body = s.get("gherkin_step_text", "")
        lines.append(f"    {kw} {body}")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Created feature file: %s", filename)
    return filename


# ── Step Definitions ──────────────────────────────────────────────────────────

def _step_to_func_name(step_text: str) -> str:
    clean = re.sub(r'"[^"]+"', "value", step_text)
    clean = re.sub(r"[^a-z0-9]+", "_", clean.lower()).strip("_")
    return clean[:60] or "step"


def _anticipated(step_type: str) -> str:
    if step_type == "navigation":
        return "page_object.open()"
    if step_type == "assertion":
        return "page_object.verify_something()"
    return "page_object.do_action()"


def create_step_definitions(tc_id: str, tc_name: str,
                             feature_filename: str,
                             gherkin_steps: list[dict]) -> str:
    """
    Create placeholder step definition file.
    Only generates code for NEW steps (is_new=True).
    Existing steps are imported from their original file via registry.
    Returns filename.
    """
    filename = f"{tc_id}_{_slug(tc_name)}_steps.py"
    filepath = _steps_dir() / filename

    new_steps = [s for s in gherkin_steps if s.get("is_new", True)]
    reused_steps = [s for s in gherkin_steps if not s.get("is_new", True)]

    feature_rel = f"../{feature_filename}"
    class_name = "".join(w.capitalize() for w in re.split(r"[^a-zA-Z0-9]", tc_name) if w)

    lines = [
        f"# {tc_id} — {tc_name}",
        "# Auto-generated by AI Test Engine",
        "# Placeholders — implementations filled during test execution",
        "",
        "import pytest",
        "from pytest_bdd import given, when, then, parsers, scenarios",
        "from playwright.sync_api import Page",
        "",
        f'scenarios("{feature_rel}")',
        "",
    ]

    # Reused steps — import their decorated functions from the source step file
    if reused_steps:
        reg = _load_registry()

        # Group reused funcs by source step file
        imports: dict[str, list[str]] = {}   # step_file → [func_name, ...]
        step_notes: list[str] = []

        for s in reused_steps:
            step_text = s.get("gherkin_step_text", "")
            kw = s.get("gherkin_keyword", "")
            pattern = _normalize(step_text)
            entry = reg.get(pattern, {})
            src_file = entry.get("steps_file", "")
            func = entry.get("function_name", "")
            if src_file and func:
                imports.setdefault(src_file, []).append(func)
            note = f"# {kw} {step_text}"
            if src_file:
                note += f"  →  {src_file}"
                if func:
                    note += f"::{func}"
            step_notes.append(note)

        lines += [
            "",
            "# ── Reused steps ─────────────────────────────────────────────",
            "# These steps already exist and are re-imported below.",
            "# pytest-bdd discovers them automatically; the import makes them",
            "# explicit so you can see exactly which file owns each definition.",
            "",
        ]
        lines += step_notes
        lines.append("")

        # Explicit re-imports so the functions appear in this module's namespace
        for src_file, funcs in imports.items():
            module = src_file.replace(".py", "")
            lines.append(f"from features.steps.{module} import (")
            for fn in funcs:
                lines.append(f"    {fn},  # noqa: F401")
            lines.append(")")
        lines.append("")

    if new_steps:
        lines.append("# ── New step definitions ─────────────────────────────────────")

    seen_funcs = set()

    for s in new_steps:
        kw = s.get("gherkin_keyword", "When").lower()
        step_text = s.get("gherkin_step_text", "")
        english = s.get("english_step", "")
        step_type = s.get("step_type", "action")
        anticipated = s.get("anticipated_method", _anticipated(step_type))

        func_name = _step_to_func_name(step_text)
        if func_name in seen_funcs:
            func_name = f"{func_name}_{tc_id.lower()}"
        seen_funcs.add(func_name)

        # Build decorator — parameterize quoted values
        if '"' in step_text:
            escaped = step_text.replace("'", "\\'")
            decorator = f"@{kw}(parsers.parse('{escaped}'))"
        else:
            decorator = f'@{kw}("{step_text}")'

        lines += [
            "",
            decorator,
            f"def {func_name}(page: Page):",
            f"    # {english}",
            f"    # Anticipated: {anticipated}",
            "    pass  # TODO: filled during execution",
        ]

        # Register in global step registry
        register_step(
            keyword=kw.capitalize(),
            step_text=step_text,
            function_name=func_name,
            steps_file=filename,
            implemented=False,
        )

    filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Created step definitions: %s (%d new, %d reused)",
                filename, len(new_steps), len(reused_steps))
    return filename


def _build_step_impl(action: str, page_class: str, locator: str, value: str) -> str:
    """Build WebActions implementation lines for a step. Page class used only for its locator constant."""
    lc = f"{page_class}.{locator}" if locator else '""'
    if action == "click":
        return f"    WebActions(page).click({lc})"
    if action == "fill":
        return f"    WebActions(page).send_text({lc}, {repr(value)})"
    if action == "fill_and_submit":
        return (f"    WebActions(page).send_text({lc}, {repr(value)})\n"
                f"    WebActions(page).press_key({lc}, 'Enter')")
    if action in ("assert_visible", "assert_text"):
        return f"    WebActions(page).wait_for_visible({lc})"
    if action == "hover":
        return f"    WebActions(page).hover({lc})"
    if action == "select":
        return f"    WebActions(page).select_option({lc}, value={repr(value)})"
    if action == "navigate":
        return f"    page.goto({repr(value)})"
    return f"    WebActions(page).click({lc})"


def rebuild_reused_imports(steps_filename: str):
    """
    Re-scan the step registry and refresh the reused-step imports block
    in an existing step definition file. Call this whenever new steps are registered.
    """
    filepath = _steps_dir() / steps_filename
    if not filepath.exists():
        return

    content = filepath.read_text(encoding="utf-8")
    reg = _load_registry()

    # Find all step patterns whose steps_file differs from this file
    reused_block_lines = [
        "# ── Reused steps ─────────────────────────────────────────────",
        "# These steps already exist and are re-imported below.",
        "# pytest-bdd discovers them automatically; the import makes them",
        "# explicit so you can see exactly which file owns each definition.",
        "",
    ]

    imports: dict[str, list[str]] = {}
    for pattern, entry in reg.items():
        src = entry.get("steps_file", "")
        if src and src != steps_filename:
            # Check if this step is referenced in this file (via scenarios)
            # We only include it if the function name appears as a comment
            fn = entry.get("function_name", "")
            if fn and f"# {fn}" in content:
                imports.setdefault(src, []).append(fn)

    if not imports:
        return

    for src_file, funcs in imports.items():
        module = src_file.replace(".py", "")
        reused_block_lines.append(f"from features.steps.{module} import (")
        for fn in funcs:
            reused_block_lines.append(f"    {fn},  # noqa: F401")
        reused_block_lines.append(")")

    # If block already exists, replace it; otherwise insert after scenarios()
    block_marker = "# ── Reused steps ───"
    if block_marker in content:
        # Replace existing reused block up to the next non-comment/import line
        pattern_re = rf"{re.escape(block_marker)}.*?(?=\n# ── New step|$)"
        new_block = "\n".join(reused_block_lines)
        content = re.sub(pattern_re, new_block, content, count=1, flags=re.DOTALL)
    else:
        insert_after = 'scenarios('
        idx = content.find(insert_after)
        if idx != -1:
            end = content.find('\n', idx) + 1
            content = content[:end] + "\n" + "\n".join(reused_block_lines) + "\n" + content[end:]

    filepath.write_text(content, encoding="utf-8")
    logger.info("Rebuilt reused imports in %s", steps_filename)


def update_step_definition(steps_filename: str, func_name: str,
                            locator_constant: str, action: str, value: str,
                            page_class: str, page_module: str):
    """
    Replace the placeholder `pass` in a step definition with a WebActions call.
    Page class is referenced only for its locator constant — no page methods.
    """
    filepath = _steps_dir() / steps_filename
    if not filepath.exists():
        logger.warning("Step file not found: %s", steps_filename)
        return

    content = filepath.read_text(encoding="utf-8")

    if f"def {func_name}" not in content:
        logger.warning("Function '%s' not found in %s", func_name, steps_filename)
        return

    if "pass  # TODO: filled during execution" not in content:
        logger.info("Function '%s' already implemented — skipping", func_name)
        return

    # Inject imports if missing
    page_import = f"from pages.{page_module} import {page_class}"
    wa_import = "from utils.web_actions import WebActions"
    for imp in [wa_import, page_import]:
        if imp not in content:
            content = content.replace(
                "from playwright.sync_api import Page",
                f"from playwright.sync_api import Page\n{imp}",
            )

    # Build the actual implementation
    impl_body = _build_step_impl(action, page_class, locator_constant, value)

    # Replace pass inside this specific function (match def…comments…pass)
    pattern = (
        rf"(def {re.escape(func_name)}\(page: Page\):"
        rf"(?:\n    #[^\n]*)*)"
        rf"\n    pass  # TODO: filled during execution"
    )
    replacement = rf"\1\n{impl_body}"
    new_content = re.sub(pattern, replacement, content, count=1, flags=re.DOTALL)

    if new_content != content:
        filepath.write_text(new_content, encoding="utf-8")
        logger.info("Updated step '%s': %s → %s.%s", func_name, action, page_class, locator_constant)
    else:
        logger.warning("Regex did not match for '%s' in %s", func_name, steps_filename)


# ── Delete BDD Files ─────────────────────────────────────────────────────────

def delete_bdd_files(feature_file: str, steps_file: str):
    """Delete feature file and step definitions. Cleans up step registry entries."""
    for filename, dir_fn in [(feature_file, _features_dir), (steps_file, _steps_dir)]:
        if filename:
            p = dir_fn() / filename
            if p.exists():
                p.unlink()
                logger.info("Deleted: %s", p)

    # Remove registry entries that belonged to this steps file
    if steps_file:
        reg = _load_registry()
        stale = [k for k, v in reg.items() if v.get("steps_file") == steps_file]
        for k in stale:
            del reg[k]
        if stale:
            _save_registry(reg)
            logger.info("Removed %d registry entries for %s", len(stale), steps_file)


# ── Data JSON ─────────────────────────────────────────────────────────────────

def create_data_json(tc_id: str, tc_name: str) -> str:
    """Create blank data JSON. Always created, even if no form data needed. Returns filename."""
    filename = f"{tc_id}_{_slug(tc_name)}.json"
    filepath = _data_dir() / filename

    if filepath.exists():
        return filename  # Never overwrite existing data

    payload = {
        tc_id: {
            "test_name": tc_name,
            "created_at": datetime.now().isoformat(),
            "test_data": {},
        }
    }
    filepath.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Created blank data JSON: %s", filename)
    return filename
