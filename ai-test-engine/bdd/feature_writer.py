"""Writes Gherkin .feature files from NormalizedStep lists."""
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List

from core.models import NormalizedStep
from providers.storage import atomic_writer

logger = logging.getLogger(__name__)


def _slug(text: str, max_len: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:max_len]


def write(
    framework_path: Path,
    tc_id: str,
    tc_name: str,
    app_url: str,
    normalized_steps: List[NormalizedStep],
) -> str:
    """Write feature file. Returns filename."""
    features_dir = framework_path / "features"
    features_dir.mkdir(parents=True, exist_ok=True)
    _ensure_init(features_dir)

    slug = _slug(tc_name)
    filename = f"{tc_id}_{slug}.feature"
    filepath = features_dir / filename
    data_file = f"{tc_id}_{slug}.json"

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

    for step in normalized_steps:
        lines.append(f"    {step.keyword} {step.step_text}")

    atomic_writer.write_text(filepath, "\n".join(lines) + "\n")
    logger.info("FeatureWriter: wrote %s (%d steps)", filename, len(normalized_steps))
    return filename


def _ensure_init(directory: Path) -> None:
    init = directory / "__init__.py"
    if not init.exists():
        init.touch()
