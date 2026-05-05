import json
import logging
from pathlib import Path
from typing import Any, Dict, Union

from config.config import Config

logger = logging.getLogger(__name__)


class JsonUtils:
    """Utility class for reading and writing JSON test data files."""

    @staticmethod
    def read(file_path: Union[str, Path]) -> Any:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            logger.info("Loaded JSON: %s", path)
            return data
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in %s: %s", path, exc)
            raise

    @staticmethod
    def write(file_path: Union[str, Path], data: Any, indent: int = 2) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        logger.info("Written JSON: %s", path)

    @staticmethod
    def get_test_data(key: str, file_name: str = "test_data.json") -> Any:
        """Shortcut to read a top-level key from the default test data file."""
        file_path = Config.DATA_DIR / file_name
        data = JsonUtils.read(file_path)
        if key not in data:
            raise KeyError(f"Key '{key}' not found in {file_name}")
        return data[key]

    @staticmethod
    def merge(base: Dict, override: Dict) -> Dict:
        """Deep-merge two dicts (override wins on conflicts)."""
        result = base.copy()
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(result.get(k), dict):
                result[k] = JsonUtils.merge(result[k], v)
            else:
                result[k] = v
        return result
