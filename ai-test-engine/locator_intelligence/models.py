from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LocatorDefinition:
    name: str
    locator_type: str          # static | collection | relative | parameterized
    strategy: str              # css | xpath | role | text | label | placeholder | test_id
    selector: str              # raw selector (may contain {param} placeholders)
    purpose: str               # search_input | product_card | add_to_cart_button | etc.
    role: Optional[str] = None
    parameters: list = field(default_factory=list)       # e.g. ["product_name"]
    sample_values: list = field(default_factory=list)    # e.g. ["Cake", "Milk"]
    match_count: int = 0
    visible_count: int = 0
    unique: bool = False
    confidence: float = 0.0
    source: str = "generated"   # generated | manual | validated
    validated: bool = False
    validated_samples: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "locator_type": self.locator_type,
            "strategy": self.strategy,
            "selector": self.selector,
            "purpose": self.purpose,
            "role": self.role,
            "parameters": self.parameters,
            "sample_values": self.sample_values,
            "match_count": self.match_count,
            "visible_count": self.visible_count,
            "unique": self.unique,
            "confidence": self.confidence,
            "source": self.source,
            "validated": self.validated,
            "validated_samples": self.validated_samples,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LocatorDefinition":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def is_parameterized(self) -> bool:
        return bool(self.parameters) or "{" in self.selector

    def resolve(self, **kwargs) -> str:
        """Resolve a parameterized locator with actual values."""
        try:
            return self.selector.format(**kwargs)
        except KeyError:
            return self.selector


@dataclass
class PageLocatorInventory:
    page_key: str
    class_name: str
    url: str
    url_patterns: list = field(default_factory=list)
    title: str = ""
    page_type: str = "unknown"
    locators: dict = field(default_factory=dict)  # name → LocatorDefinition

    def to_dict(self) -> dict:
        return {
            "page_key": self.page_key,
            "class_name": self.class_name,
            "url": self.url,
            "url_patterns": self.url_patterns,
            "title": self.title,
            "page_type": self.page_type,
            "locators": {k: v.to_dict() for k, v in self.locators.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PageLocatorInventory":
        inv = cls(
            page_key=d["page_key"],
            class_name=d["class_name"],
            url=d.get("url", ""),
            url_patterns=d.get("url_patterns", []),
            title=d.get("title", ""),
            page_type=d.get("page_type", "unknown"),
        )
        for name, loc_dict in d.get("locators", {}).items():
            try:
                inv.locators[name] = LocatorDefinition.from_dict(loc_dict)
            except Exception:
                pass
        return inv

    def add_locator(self, loc: LocatorDefinition):
        self.locators[loc.name] = loc

    def get_validated(self) -> list:
        return [l for l in self.locators.values() if l.validated]

    def get_high_confidence(self, threshold: float = 0.85) -> list:
        return [l for l in self.locators.values() if l.confidence >= threshold]
