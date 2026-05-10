from dataclasses import dataclass
from typing import Any


@dataclass
class Result:
    ok: bool
    value: Any = None
    error: str = ""

    @classmethod
    def success(cls, value=None) -> "Result":
        return cls(ok=True, value=value)

    @classmethod
    def failure(cls, error: str) -> "Result":
        return cls(ok=False, error=error)
