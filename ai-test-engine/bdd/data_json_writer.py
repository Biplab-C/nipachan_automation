"""Always creates a blank data JSON for every test case."""
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from providers.storage import atomic_writer

logger = logging.getLogger(__name__)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]


def write(framework_path: Path, tc_id: str, tc_name: str) -> str:
    """Create blank data JSON. Never overwrites existing data. Returns filename."""
    data_dir = framework_path / "data"
    data_dir.mkdir(exist_ok=True)

    filename = f"{tc_id}_{_slug(tc_name)}.json"
    filepath = data_dir / filename

    if filepath.exists():
        return filename  # never overwrite

    payload = {"test_case_id": tc_id, "data": {}}
    atomic_writer.write_text(filepath, json.dumps(payload, indent=2))
    logger.info("DataJsonWriter: created %s", filename)
    return filename
