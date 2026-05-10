import shutil
import tempfile
from pathlib import Path


def write_text(target: Path, content: str, encoding: str = "utf-8") -> None:
    """Write content to target atomically via a temp file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with open(fd, "w", encoding=encoding) as f:
            f.write(content)
        _validate(tmp_path, content)
        shutil.move(tmp_path, target)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def write_text_with_backup(target: Path, content: str, encoding: str = "utf-8") -> None:
    """Write to target with a .bak backup of the previous content."""
    if target.exists():
        backup = target.with_suffix(target.suffix + ".bak")
        shutil.copy2(target, backup)
    write_text(target, content, encoding)


def _validate(path: str, expected: str) -> None:
    with open(path, encoding="utf-8") as f:
        actual = f.read()
    if actual != expected:
        raise IOError("Atomic write validation failed: content mismatch")
