import json
from pathlib import Path

from providers.storage import atomic_writer


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    atomic_writer.write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(path: Path, content: str) -> None:
    atomic_writer.write_text(path, content)


def write_text_with_backup(path: Path, content: str) -> None:
    atomic_writer.write_text_with_backup(path, content)
