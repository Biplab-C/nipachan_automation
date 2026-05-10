import json
from providers.llm.base import LLMProvider


class MockProvider(LLMProvider):
    """Returns a deterministic stub for testing without a live LLM."""

    def __init__(self, response: str = "[]"):
        self._response = response

    def complete(self, system: str, user: str) -> str:
        return self._response

    @classmethod
    def with_steps(cls, steps: list) -> "MockProvider":
        return cls(json.dumps(steps))
