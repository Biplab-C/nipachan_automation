"""
Fills NIPACHAN_PLACEHOLDER steps with deterministic template code.
AI does not write Python. Only category + parameters drive template selection.

Called pre-run on generated step files.
Never touches shared/ step files.
"""
import logging
import re
from pathlib import Path
from typing import List, Optional

from implementation.supported_categories import is_supported
from implementation.templates import (
    assertion_template,
    button_template,
    form_template,
    link_template,
    search_template,
)
from providers.storage import atomic_writer

logger = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"#\s*NIPACHAN_PLACEHOLDER:\s*true")
_FUNC_RE = re.compile(r"^def\s+(\w+)\s*\(([^)]*)\)\s*:")
_CATEGORY_RE = re.compile(r"#\s*category:\s*(\w+)")


def implement_placeholders(step_file: Path) -> int:
    """
    Scan step_file for NIPACHAN_PLACEHOLDER blocks and replace with template code.
    Returns number of steps implemented.
    """
    if not step_file.exists():
        return 0

    content = step_file.read_text(encoding="utf-8")
    lines = content.splitlines()
    count = 0
    new_lines: List[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if _PLACEHOLDER_RE.search(line):
            # Walk back to find the def line
            def_idx = _find_def_above(new_lines)
            if def_idx is not None:
                def_line = new_lines[def_idx]
                fm = _FUNC_RE.match(def_line.strip())
                if fm:
                    params_raw = fm.group(2)
                    param_names = [p.split(":")[0].strip() for p in params_raw.split(",")]
                    non_page = [p for p in param_names if p and p != "page"]

                    # Find category comment (should be the line after placeholder marker)
                    category = _extract_category(lines, i)

                    impl = _render(category, non_page)
                    if impl:
                        # Replace from def line onwards through the raise/pass
                        block_end = _find_block_end(lines, i)
                        # Rewrite: keep everything up to def, add impl, skip old body
                        new_lines = new_lines[:def_idx + 1]
                        for impl_line in impl.splitlines():
                            new_lines.append(impl_line)
                        i = block_end + 1
                        count += 1
                        continue
        new_lines.append(line)
        i += 1

    if count:
        atomic_writer.write_text_with_backup(step_file, "\n".join(new_lines) + "\n")
        logger.info("ImplementationGenerator: filled %d placeholder(s) in %s", count, step_file.name)
    return count


def _find_def_above(lines: List[str]) -> Optional[int]:
    for idx in range(len(lines) - 1, -1, -1):
        if _FUNC_RE.match(lines[idx].strip()):
            return idx
    return None


def _find_block_end(lines: List[str], placeholder_line: int) -> int:
    for j in range(placeholder_line + 1, len(lines)):
        stripped = lines[j].strip()
        if stripped and not stripped.startswith("#") and not lines[j][0].isspace():
            return j - 1
        if "raise NotImplementedError" in lines[j] or stripped == "pass":
            return j
    return len(lines) - 1


def _extract_category(lines: List[str], from_idx: int) -> str:
    for j in range(from_idx, min(from_idx + 5, len(lines))):
        m = _CATEGORY_RE.search(lines[j])
        if m:
            return m.group(1)
    return "unknown"


def _render(category: str, params: List[str]) -> str:
    if not is_supported(category):
        return ""
    first = params[0] if params else "value"
    second = params[1] if len(params) > 1 else "field"

    if category == "search":
        return search_template.render(first)
    if category == "link_assertion":
        return link_template.render_assertion(first)
    if category == "link_click":
        return link_template.render_click(first)
    if category == "button_click":
        return button_template.render(first)
    if category == "text_assertion":
        return assertion_template.render(first)
    if category == "form_input":
        return form_template.render_input(second, first)
    if category == "dropdown_select":
        return form_template.render_dropdown(second, first)
    return ""
