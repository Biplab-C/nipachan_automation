from abc import ABC, abstractmethod
from typing import List

from core.models import CatalogItem, NormalizedStep


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        ...


class StepNormalizerContract(ABC):
    @abstractmethod
    def normalize(self, raw_steps: List[str], catalog: List[CatalogItem]) -> List[NormalizedStep]:
        ...
