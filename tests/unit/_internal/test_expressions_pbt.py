"""Property-based tests for expression normalization using Hypothesis."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from mixpanel_data._internal.expressions import normalize_on_expression

# Strategy for bare property names (no accessor patterns)
bare_property_names = st.text(min_size=1).filter(
    lambda s: 'properties["' not in s and 'user["' not in s and 'event["' not in s
)

# Strategy for valid expressions (contain at least one accessor)
valid_expressions = st.sampled_from(
    [
        'properties["Source"]',
        'user["email"]',
        'event["name"]',
        'properties["x"] == "y"',
        'defined(properties["z"])',
    ]
)


class TestNormalizeOnExpressionProperties:
    """Property-based tests for normalize_on_expression."""

    @given(name=bare_property_names)
    def test_bare_names_get_wrapped(self, name: str) -> None:
        """Any bare property name should be wrapped in properties[] accessor.

        Invariant: If input contains no accessor patterns, output wraps it
        with proper escaping of special characters.

        Args:
            name: A string that does not contain any filter expression accessors.
        """
        result = normalize_on_expression(name)

        # The result should be wrapped in properties["..."]
        assert result.startswith('properties["')
        assert result.endswith('"]')

        # Extract and unescape the inner content to verify it matches the input
        inner = result[len('properties["') : -len('"]')]
        unescaped = inner.replace('\\"', '"').replace("\\\\", "\\")
        assert unescaped == name

    @given(expr=valid_expressions)
    def test_expressions_pass_through(self, expr: str) -> None:
        """Expressions with accessor patterns should pass through unchanged.

        Invariant: If input contains accessor pattern, output equals input.

        Args:
            expr: A valid filter expression containing at least one accessor.
        """
        assert normalize_on_expression(expr) == expr

    @given(name=st.text())
    def test_idempotent(self, name: str) -> None:
        """Normalizing twice should equal normalizing once.

        Invariant: normalize(normalize(x)) == normalize(x)

        Args:
            name: Any string input (bare name or expression).
        """
        once = normalize_on_expression(name)
        twice = normalize_on_expression(once)
        assert once == twice

    @given(name=st.text())
    def test_output_always_has_accessor(self, name: str) -> None:
        """Output should always contain at least one accessor pattern.

        Invariant: Every normalized expression contains a valid accessor.

        Args:
            name: Any string input (bare name or expression).
        """
        result = normalize_on_expression(name)
        accessors = ('properties["', 'user["', 'event["')
        assert any(accessor in result for accessor in accessors)

    @given(name=bare_property_names)
    def test_wrapped_output_has_valid_syntax(self, name: str) -> None:
        """Wrapped output should have properly escaped quotes for valid syntax.

        Invariant: For bare property names, the output should be a valid
        properties["..."] accessor where any double quotes in the property
        name are escaped with backslash.

        Args:
            name: A bare property name (no accessor patterns).
        """
        result = normalize_on_expression(name)

        # The result should start with properties[" and end with "]
        assert result.startswith('properties["')
        assert result.endswith('"]')

        # Extract the content between properties[" and "]
        inner = result[len('properties["') : -len('"]')]

        # Unescape the inner content: replace \" with " and \\ with \
        # This reverses the escaping that should have been applied
        unescaped = inner.replace('\\"', '"').replace("\\\\", "\\")

        # The unescaped content should equal the original input
        assert unescaped == name

    @given(
        prefix=st.text(max_size=20),
        suffix=st.text(max_size=20),
    )
    def test_quotes_in_names_are_escaped(self, prefix: str, suffix: str) -> None:
        """Property names containing quotes should have them escaped.

        Invariant: Any double quote in a bare property name must be escaped
        in the output to prevent syntax errors.

        Args:
            prefix: Text before the embedded quote.
            suffix: Text after the embedded quote.
        """
        # Construct a property name with an embedded quote
        name = f'{prefix}"{suffix}'

        # Skip if accidentally contains accessor pattern
        if 'properties["' in name or 'user["' in name or 'event["' in name:
            return

        result = normalize_on_expression(name)

        # Extract the inner content and verify it unescapes to the original
        assert result.startswith('properties["')
        assert result.endswith('"]')
        inner = result[len('properties["') : -len('"]')]
        unescaped = inner.replace('\\"', '"').replace("\\\\", "\\")
        assert unescaped == name
