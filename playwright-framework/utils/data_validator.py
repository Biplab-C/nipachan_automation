import logging
import re
from typing import Any, Dict, List, Optional, Type, Union

import jsonschema

logger = logging.getLogger(__name__)


class DataValidator:
    """
    Assertion utilities for data validation in tests.
    All methods are static — instantiation is optional.
    """

    # ------------------------------------------------------------------
    # Equality
    # ------------------------------------------------------------------

    @staticmethod
    def assert_equal(actual: Any, expected: Any, field: str = "value") -> None:
        assert actual == expected, (
            f"[{field}] Expected: '{expected}' | Actual: '{actual}'"
        )
        logger.info("[PASS] %s == %s", field, expected)

    @staticmethod
    def assert_not_equal(actual: Any, expected: Any, field: str = "value") -> None:
        assert actual != expected, (
            f"[{field}] Expected value NOT to be '{expected}', but it was"
        )
        logger.info("[PASS] %s != %s", field, expected)

    # ------------------------------------------------------------------
    # Containment
    # ------------------------------------------------------------------

    @staticmethod
    def assert_contains(actual: str, expected: str, field: str = "value") -> None:
        assert expected in actual, (
            f"[{field}] Expected '{expected}' to be in '{actual}'"
        )
        logger.info("[PASS] '%s' contains '%s'", field, expected)

    @staticmethod
    def assert_not_contains(actual: str, expected: str, field: str = "value") -> None:
        assert expected not in actual, (
            f"[{field}] Expected '{expected}' NOT to be in '{actual}'"
        )
        logger.info("[PASS] '%s' does not contain '%s'", field, expected)

    @staticmethod
    def assert_list_contains(actual_list: List, item: Any, field: str = "list") -> None:
        assert item in actual_list, (
            f"[{field}] Expected '{item}' in {actual_list}"
        )
        logger.info("[PASS] '%s' found in %s", item, field)

    @staticmethod
    def assert_list_not_contains(actual_list: List, item: Any, field: str = "list") -> None:
        assert item not in actual_list, (
            f"[{field}] Expected '{item}' NOT in {actual_list}"
        )
        logger.info("[PASS] '%s' not found in %s", item, field)

    # ------------------------------------------------------------------
    # Null checks
    # ------------------------------------------------------------------

    @staticmethod
    def assert_not_null(actual: Any, field: str = "value") -> None:
        assert actual is not None, f"[{field}] Expected non-null value"
        logger.info("[PASS] %s is not null", field)

    @staticmethod
    def assert_null(actual: Any, field: str = "value") -> None:
        assert actual is None, f"[{field}] Expected null, got '{actual}'"
        logger.info("[PASS] %s is null", field)

    # ------------------------------------------------------------------
    # Truthiness
    # ------------------------------------------------------------------

    @staticmethod
    def assert_truthy(actual: Any, field: str = "value") -> None:
        assert actual, f"[{field}] Expected truthy value, got: '{actual}'"
        logger.info("[PASS] %s is truthy", field)

    @staticmethod
    def assert_falsy(actual: Any, field: str = "value") -> None:
        assert not actual, f"[{field}] Expected falsy value, got: '{actual}'"
        logger.info("[PASS] %s is falsy", field)

    # ------------------------------------------------------------------
    # Type
    # ------------------------------------------------------------------

    @staticmethod
    def assert_type(actual: Any, expected_type: Type, field: str = "value") -> None:
        assert isinstance(actual, expected_type), (
            f"[{field}] Expected type '{expected_type.__name__}', "
            f"got '{type(actual).__name__}'"
        )
        logger.info("[PASS] %s is of type %s", field, expected_type.__name__)

    # ------------------------------------------------------------------
    # Numeric range
    # ------------------------------------------------------------------

    @staticmethod
    def assert_in_range(
        actual: Union[int, float],
        min_val: Union[int, float],
        max_val: Union[int, float],
        field: str = "value",
    ) -> None:
        assert min_val <= actual <= max_val, (
            f"[{field}] Expected {min_val} <= {actual} <= {max_val}"
        )
        logger.info("[PASS] %s = %s is in [%s, %s]", field, actual, min_val, max_val)

    @staticmethod
    def assert_greater_than(
        actual: Union[int, float], threshold: Union[int, float], field: str = "value"
    ) -> None:
        assert actual > threshold, (
            f"[{field}] Expected {actual} > {threshold}"
        )
        logger.info("[PASS] %s = %s > %s", field, actual, threshold)

    @staticmethod
    def assert_less_than(
        actual: Union[int, float], threshold: Union[int, float], field: str = "value"
    ) -> None:
        assert actual < threshold, (
            f"[{field}] Expected {actual} < {threshold}"
        )
        logger.info("[PASS] %s = %s < %s", field, actual, threshold)

    # ------------------------------------------------------------------
    # Collection size
    # ------------------------------------------------------------------

    @staticmethod
    def assert_list_length(actual: List, expected_length: int, field: str = "list") -> None:
        assert len(actual) == expected_length, (
            f"[{field}] Expected length {expected_length}, got {len(actual)}"
        )
        logger.info("[PASS] %s has length %d", field, expected_length)

    @staticmethod
    def assert_not_empty(actual: List, field: str = "list") -> None:
        assert len(actual) > 0, f"[{field}] Expected non-empty list"
        logger.info("[PASS] %s is not empty", field)

    # ------------------------------------------------------------------
    # String patterns
    # ------------------------------------------------------------------

    @staticmethod
    def assert_matches_regex(actual: str, pattern: str, field: str = "value") -> None:
        assert re.match(pattern, actual), (
            f"[{field}] '{actual}' does not match pattern '{pattern}'"
        )
        logger.info("[PASS] %s matches pattern '%s'", field, pattern)

    @staticmethod
    def assert_starts_with(actual: str, prefix: str, field: str = "value") -> None:
        assert actual.startswith(prefix), (
            f"[{field}] Expected '{actual}' to start with '{prefix}'"
        )
        logger.info("[PASS] %s starts with '%s'", field, prefix)

    @staticmethod
    def assert_ends_with(actual: str, suffix: str, field: str = "value") -> None:
        assert actual.endswith(suffix), (
            f"[{field}] Expected '{actual}' to end with '{suffix}'"
        )
        logger.info("[PASS] %s ends with '%s'", field, suffix)

    # ------------------------------------------------------------------
    # Dict validation
    # ------------------------------------------------------------------

    @staticmethod
    def assert_has_keys(data: Dict, keys: List[str], field: str = "dict") -> None:
        missing = [k for k in keys if k not in data]
        assert not missing, f"[{field}] Missing required keys: {missing}"
        logger.info("[PASS] %s has all required keys: %s", field, keys)

    @staticmethod
    def assert_dicts_equal(
        actual: Dict,
        expected: Dict,
        ignore_keys: Optional[List[str]] = None,
    ) -> None:
        ignore = set(ignore_keys or [])
        actual_f = {k: v for k, v in actual.items() if k not in ignore}
        expected_f = {k: v for k, v in expected.items() if k not in ignore}
        diff = {
            k: {"actual": actual_f.get(k), "expected": expected_f.get(k)}
            for k in set(list(actual_f) + list(expected_f))
            if actual_f.get(k) != expected_f.get(k)
        }
        assert not diff, f"Dict mismatch:\n{diff}"
        logger.info("[PASS] Dicts are equal (ignored: %s)", ignore_keys)

    # ------------------------------------------------------------------
    # JSON Schema
    # ------------------------------------------------------------------

    @staticmethod
    def assert_schema(data: Any, schema: Dict) -> None:
        try:
            jsonschema.validate(instance=data, schema=schema)
            logger.info("[PASS] Data conforms to JSON schema")
        except jsonschema.ValidationError as exc:
            raise AssertionError(f"Schema validation failed: {exc.message}") from exc
