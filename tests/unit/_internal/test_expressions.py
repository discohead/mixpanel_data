"""Unit tests for expression normalization utilities."""

from __future__ import annotations

import pytest

from mixpanel_data._internal.expressions import normalize_on_expression


class TestNormalizeOnExpression:
    """Tests for normalize_on_expression function."""

    # Category 1: Bare property names that need wrapping

    @pytest.mark.parametrize(
        ("bare_name", "expected"),
        [
            ("Source", 'properties["Source"]'),
            ("Screen Name", 'properties["Screen Name"]'),
            ("$os", 'properties["$os"]'),
            ("$browser", 'properties["$browser"]'),
        ],
    )
    def test_wraps_bare_property_names(self, bare_name: str, expected: str) -> None:
        """Bare property names should be wrapped in properties[] accessor."""
        assert normalize_on_expression(bare_name) == expected

    @pytest.mark.parametrize(
        "tricky_name",
        [
            "foo[0]",  # Contains [ but not an accessor
            "properties_count",  # Starts with "properties" but isn't accessor
            "user_id",  # Contains "user" but isn't accessor
            "event_type",  # Contains "event" but isn't accessor
        ],
    )
    def test_wraps_names_with_misleading_substrings(self, tricky_name: str) -> None:
        """Property names containing accessor-like substrings should still be wrapped."""
        result = normalize_on_expression(tricky_name)
        assert result == f'properties["{tricky_name}"]'

    # Category 2: Already-valid expressions (pass through unchanged)

    @pytest.mark.parametrize(
        "expression",
        [
            'properties["Source"]',
            'user["email"]',
            'event["name"]',
            'properties["Screen"] == "Home"',
            'properties["Type"] + " from " + properties["Source"]',
            'properties["Screen"] in ["Home", "Events"]',
            'defined(properties["Type"])',
            'if(properties["x"], "yes", "no")',
            'properties["x"] + user["y"]',  # Mixed accessors
        ],
    )
    def test_passes_through_valid_expressions(self, expression: str) -> None:
        """Expressions containing accessor syntax should pass through unchanged."""
        assert normalize_on_expression(expression) == expression

    # Category 3: Edge cases

    def test_empty_string_wrapped(self) -> None:
        """Empty string should be wrapped (API will handle the error)."""
        assert normalize_on_expression("") == 'properties[""]'

    def test_whitespace_only_wrapped(self) -> None:
        """Whitespace-only string should be wrapped (API will handle the error)."""
        assert normalize_on_expression("  ") == 'properties["  "]'

    def test_unicode_property_names(self) -> None:
        """Unicode property names should be wrapped correctly."""
        assert normalize_on_expression("日本語") == 'properties["日本語"]'
        assert normalize_on_expression("émoji🎉") == 'properties["émoji🎉"]'

    # Category 5: Special character escaping

    @pytest.mark.parametrize(
        ("name_with_quotes", "expected"),
        [
            ('my"property', 'properties["my\\"property"]'),
            ('"quoted"', 'properties["\\"quoted\\""]'),
            ('a"b"c', 'properties["a\\"b\\"c"]'),
            ('say "hello"', 'properties["say \\"hello\\""]'),
        ],
    )
    def test_escapes_double_quotes_in_property_names(
        self, name_with_quotes: str, expected: str
    ) -> None:
        """Property names containing double quotes should be escaped."""
        assert normalize_on_expression(name_with_quotes) == expected

    def test_backslash_before_quote_escaping(self) -> None:
        """Backslash before quote should be handled correctly."""
        # A property name ending with backslash followed by quote
        result = normalize_on_expression('path\\to\\"file')
        # The quote should be escaped, and existing backslashes preserved
        assert result == 'properties["path\\\\to\\\\\\"file"]'

    # Category 4: Idempotency

    def test_idempotent_for_bare_names(self) -> None:
        """Applying twice to a bare name should give same result."""
        once = normalize_on_expression("Source")
        twice = normalize_on_expression(once)
        assert once == twice == 'properties["Source"]'

    def test_idempotent_for_expressions(self) -> None:
        """Applying twice to an expression should give same result."""
        expr = 'properties["Type"] == "Event"'
        once = normalize_on_expression(expr)
        twice = normalize_on_expression(once)
        assert once == twice == expr
