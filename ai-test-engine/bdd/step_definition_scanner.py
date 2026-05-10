"""
Scans step definition Python files and builds an in-memory StepCatalog.
Step definition files are the source of truth — no permanent JSON registry.
"""
import ast
import json
import logging
import re
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from core.models import CatalogItem

logger = logging.getLogger(__name__)

# Decorator names we care about
_KEYWORDS = {"given", "when", "then"}

# Matches: @given("text") or @when(parsers.parse("text")) and single-quote variants
_DEC_RE = re.compile(
    r'@(given|when|then)\s*\(\s*'
    r'(?:parsers\.parse\s*\(\s*)?'
    r'(["\'])(.+?)\2'
    r'(?:\s*\))?'
    r'\s*\)',
    re.IGNORECASE | re.DOTALL,
)
_FUNC_RE = re.compile(r'^\s*def\s+(\w+)\s*\(')

# {param_name} → named regex group
_PARAM_RE = re.compile(r'\{(\w+)\}')

# Placeholder detection
_PLACEHOLDER_MARKERS = (
    "# NIPACHAN_PLACEHOLDER: true",
    "raise NotImplementedError",
)


def _pattern_to_regex(pattern: str) -> str:
    escaped = re.escape(pattern)
    escaped = _PARAM_RE.sub(lambda m: f'(?P<{m.group(1)}>.+)', escaped)
    # re.escape converts { } to \{ \} so we need to handle that
    escaped = re.sub(r'\\\{(\w+)\\\}', lambda m: f'(?P<{m.group(1)}>.+)', re.escape(pattern))
    return f"^{escaped}$"


def _is_implemented(func_body_lines: List[str]) -> bool:
    body = "\n".join(func_body_lines)
    if any(m in body for m in _PLACEHOLDER_MARKERS):
        return False
    stripped = [l.strip() for l in func_body_lines if l.strip() and not l.strip().startswith("#")]
    if not stripped or stripped == ["pass"]:
        return False
    return True


def _source_tag(file_path: Path, shared_dir: Path, generated_dir: Path) -> str:
    try:
        file_path.relative_to(shared_dir)
        return "shared"
    except ValueError:
        pass
    try:
        file_path.relative_to(generated_dir)
        return "generated"
    except ValueError:
        return "other"


def scan(framework_path: Path) -> List[CatalogItem]:
    """
    Scan all step definition files in shared/ and generated/ and return a StepCatalog.
    Rebuilds from code on every call — not cached.
    """
    steps_root = framework_path / "features" / "steps"
    shared_dir = steps_root / "shared"
    generated_dir = steps_root / "generated"

    search_dirs = [shared_dir, generated_dir, steps_root]
    py_files: List[Path] = []
    for d in search_dirs:
        if d.exists():
            for f in d.glob("*.py"):
                if f.name != "__init__.py" and f not in py_files:
                    py_files.append(f)

    catalog: List[CatalogItem] = []
    for py_file in py_files:
        catalog.extend(_scan_file(py_file, shared_dir, generated_dir))

    logger.info("StepDefinitionScanner: %d items from %d files", len(catalog), len(py_files))
    return catalog


def _scan_file(py_file: Path, shared_dir: Path, generated_dir: Path) -> List[CatalogItem]:
    try:
        text = py_file.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Cannot read %s: %s", py_file, e)
        return []

    lines = text.splitlines()
    items: List[CatalogItem] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        dec_match = _DEC_RE.search(line)
        if dec_match:
            keyword = dec_match.group(1).lower()
            pattern = dec_match.group(3)

            # Find the def on the next non-blank line
            func_name = ""
            body_start = i + 1
            for j in range(i + 1, min(i + 5, len(lines))):
                fm = _FUNC_RE.match(lines[j])
                if fm:
                    func_name = fm.group(1)
                    body_start = j + 1
                    break

            # Collect function body until next def/decorator or EOF
            body_lines: List[str] = []
            for j in range(body_start, len(lines)):
                l = lines[j]
                if l and not l[0].isspace() and l.strip():
                    break
                body_lines.append(l)

            implemented = _is_implemented(body_lines) if func_name else False
            source = _source_tag(py_file, shared_dir, generated_dir)
            rel_path = str(py_file.relative_to(py_file.parents[3])).replace("\\", "/")

            item = CatalogItem(
                keyword=keyword,
                pattern=pattern,
                regex=_pattern_to_regex(pattern),
                function_name=func_name,
                file_path=rel_path,
                implemented=implemented,
                source=source,
            )
            items.append(item)
        i += 1
    return items


def save_cache(catalog: List[CatalogItem], cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps([asdict(c) for c in catalog], indent=2),
        encoding="utf-8",
    )
