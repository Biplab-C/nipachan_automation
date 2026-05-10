from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class NormalizedStep:
    raw_step: str
    keyword: str          # Given, When, Then, And
    step_text: str        # I search for "Cake"
    step_pattern: str     # I search for "{search_term}"
    category: str         # search, navigation, link_assertion, etc.
    parameters: Dict[str, str]
    function_name: str
    confidence: float
    needs_review: bool
    ambiguity_reason: str = ""


@dataclass
class CatalogItem:
    keyword: str
    pattern: str          # I search for "{search_term}"
    regex: str            # ^I search for "(?P<search_term>.+)"$
    function_name: str
    file_path: str
    implemented: bool
    source: str           # "shared" or "generated"


@dataclass
class MatchResult:
    matched: bool
    catalog_item: Optional[CatalogItem] = None
    match_type: str = ""  # "exact", "regex", "semantic", "none"


@dataclass
class TestCaseMeta:
    id: str
    name: str
    app_url: str
    feature_file: str
    step_file: str
    data_file: str
    status: str
    needs_review: bool
    raw_steps: List[str] = field(default_factory=list)
