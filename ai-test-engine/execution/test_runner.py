"""
Runs pytest-bdd for a specific test case.
Pre-run: fills supported placeholders via ImplementationGenerator.
Does not use LangGraph. No runtime AI healing.
"""
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from implementation.implementation_generator import implement_placeholders

logger = logging.getLogger(__name__)


def _fw_default() -> Path:
    _root = Path(__file__).parent.parent  # ai-test-engine/
    raw = os.environ.get("PLAYWRIGHT_FRAMEWORK_PATH", "")
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (_root / p).resolve()
    return (_root.parent / "playwright-framework").resolve()


def run(
    framework_path: Path,
    tc_id: str,
    app_url: str,
    steps_file: str,
    timeout: int = 300,
) -> dict:
    """
    Pre-implement placeholders then execute pytest-bdd.
    Returns a result dict with status, stdout, stderr, returncode.
    """
    generated_dir = framework_path / "features" / "steps" / "generated"
    step_file = generated_dir / steps_file

    # Pre-run: fill supported placeholders with deterministic templates
    implemented = 0
    if step_file.exists():
        implemented = implement_placeholders(step_file)
        logger.info("Pre-run: implemented %d placeholder(s) in %s", implemented, steps_file)
    else:
        # Legacy flat steps location
        flat_step = framework_path / "features" / "steps" / steps_file
        if flat_step.exists():
            implemented = implement_placeholders(flat_step)

    # Build env with APP_URL so navigation fixture knows where to go
    env = os.environ.copy()
    env["APP_URL"] = app_url

    cmd = [
        sys.executable, "-m", "pytest",
        str(step_file if step_file.exists() else framework_path / "features" / "steps" / steps_file),
        "-v", "--tb=short", "--no-header",
        f"--rootdir={framework_path}",
    ]

    logger.info("Running: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(framework_path),
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )
        return {
            "tc_id": tc_id,
            "status": "passed" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "placeholders_implemented": implemented,
        }
    except subprocess.TimeoutExpired:
        return {
            "tc_id": tc_id,
            "status": "timeout",
            "returncode": -1,
            "stdout": "",
            "stderr": f"Test timed out after {timeout}s",
            "placeholders_implemented": implemented,
        }
    except Exception as exc:
        return {
            "tc_id": tc_id,
            "status": "error",
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "placeholders_implemented": implemented,
        }
