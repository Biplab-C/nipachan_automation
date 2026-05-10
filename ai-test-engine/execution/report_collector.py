"""Parses pytest output and returns a structured run report."""
import re
from typing import List


def parse(stdout: str, stderr: str, returncode: int) -> dict:
    lines = stdout.splitlines()
    passed = _count(lines, r"(\d+) passed")
    failed = _count(lines, r"(\d+) failed")
    errors = _count(lines, r"(\d+) error")
    warnings = _count(lines, r"(\d+) warning")

    failures = _extract_failures(lines)

    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "warnings": warnings,
        "returncode": returncode,
        "success": returncode == 0,
        "failures": failures,
        "raw_output": stdout + ("\n" + stderr if stderr else ""),
    }


def _count(lines: List[str], pattern: str) -> int:
    for line in reversed(lines):
        m = re.search(pattern, line)
        if m:
            return int(m.group(1))
    return 0


def _extract_failures(lines: List[str]) -> List[str]:
    failures = []
    in_failure = False
    current: List[str] = []
    for line in lines:
        if line.startswith("FAILED ") or line.startswith("_ FAILED"):
            in_failure = True
        if in_failure:
            current.append(line)
            if line.startswith("=") and len(current) > 1:
                failures.append("\n".join(current))
                current = []
                in_failure = False
    return failures
