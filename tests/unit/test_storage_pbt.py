"""Property-based tests for StorageEngine using Hypothesis.

These tests verify invariants that should hold for all possible inputs,
catching edge cases that example-based tests might miss.

Properties tested:
- Identifier quoting: _quote_identifier produces safe SQL identifiers
- Properties JSON roundtrip: event properties survive storage and retrieval
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from mixpanel_data._internal.storage import StorageEngine, _quote_identifier
from mixpanel_data.types import TableMetadata

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for JSON-serializable primitive values
json_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(),
)

# Strategy for JSON-serializable values (recursive: primitives, lists, dicts)
# This matches what Mixpanel event properties can contain
json_values: st.SearchStrategy[Any] = st.recursive(
    json_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(), children, max_size=5),
    ),
    max_leaves=15,
)

# Strategy for event properties (dict with string keys, JSON values)
event_properties = st.dictionaries(st.text(), json_values, max_size=10)

# Strategy for identifier strings that DuckDB can handle
# Excludes null bytes which are invalid in identifiers
identifier_strings = st.text(
    alphabet=st.characters(exclude_characters="\x00"),
    min_size=1,
    max_size=50,
)

# Strategy for valid table names (alphanumeric + underscore, not starting with _)
valid_table_names = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
    min_size=1,
    max_size=30,
).filter(lambda s: s and s[0] != "_" and s[0].isalpha())


# =============================================================================
# _quote_identifier Property Tests
# =============================================================================


class TestQuoteIdentifierProperties:
    """Property-based tests for _quote_identifier function."""

    @given(name=identifier_strings)
    @settings(max_examples=50)
    def test_quoted_identifier_usable_in_create_table(self, name: str) -> None:
        """Quoted identifier can be used in CREATE TABLE statements.

        This property verifies that _quote_identifier produces identifiers
        that DuckDB accepts in SQL statements, regardless of special characters
        in the input string.

        Args:
            name: Any string to use as a table identifier.
        """
        quoted = _quote_identifier(name)

        with StorageEngine.memory() as storage:
            # Should be able to create table with this identifier
            sql = f"CREATE TABLE {quoted} (id INTEGER)"
            storage.connection.execute(sql)

            # Table should exist with the exact name we specified
            result = storage.connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
                (name,),
            ).fetchone()

            assert result is not None, f"Table with name '{name}' not found"
            assert result[0] == name

    @given(name=identifier_strings)
    @settings(max_examples=50)
    def test_quoted_identifier_preserves_name_exactly(self, name: str) -> None:
        """Quoted identifier preserves the exact original name.

        After creating a table with a quoted identifier, querying the
        information_schema should return the exact original name.

        Args:
            name: Any string to use as a table identifier.
        """
        quoted = _quote_identifier(name)

        with StorageEngine.memory() as storage:
            storage.connection.execute(f"CREATE TABLE {quoted} (id INTEGER)")

            # Get all table names
            tables = storage.connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
            table_names = [t[0] for t in tables]

            assert name in table_names

    @given(name=identifier_strings)
    def test_quoted_identifier_usable_in_drop_table(self, name: str) -> None:
        """Quoted identifier can be used in DROP TABLE statements.

        Args:
            name: Any string to use as a table identifier.
        """
        quoted = _quote_identifier(name)

        with StorageEngine.memory() as storage:
            # Create and drop table
            storage.connection.execute(f"CREATE TABLE {quoted} (id INTEGER)")
            storage.connection.execute(f"DROP TABLE {quoted}")

            # Table should no longer exist
            result = storage.connection.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
                (name,),
            ).fetchone()
            assert result is not None
            assert result[0] == 0

    @given(name=identifier_strings)
    def test_quoted_identifier_usable_in_insert_and_select(self, name: str) -> None:
        """Quoted identifier can be used in INSERT and SELECT statements.

        Args:
            name: Any string to use as a table identifier.
        """
        quoted = _quote_identifier(name)

        with StorageEngine.memory() as storage:
            storage.connection.execute(f"CREATE TABLE {quoted} (value INTEGER)")
            storage.connection.execute(f"INSERT INTO {quoted} VALUES (42)")

            result = storage.connection.execute(
                f"SELECT value FROM {quoted}"
            ).fetchone()
            assert result is not None
            assert result[0] == 42

    @given(
        prefix=st.text(max_size=5),
        suffix=st.text(max_size=5),
        num_quotes=st.integers(min_value=1, max_value=3),
    )
    def test_quoted_identifier_handles_embedded_quotes(
        self, prefix: str, suffix: str, num_quotes: int
    ) -> None:
        """Quoted identifier correctly escapes embedded double quotes.

        This is critical for SQL injection prevention - embedded quotes
        must be escaped by doubling them.

        Args:
            prefix: Text before the quotes.
            suffix: Text after the quotes.
            num_quotes: Number of quote characters to embed.
        """
        # Build a name with guaranteed embedded quotes
        name = prefix + ('"' * num_quotes) + suffix

        # Filter out null bytes which are invalid
        assume("\x00" not in name)
        assume(len(name) > 0)

        quoted = _quote_identifier(name)

        with StorageEngine.memory() as storage:
            # Should work even with embedded quotes
            storage.connection.execute(f"CREATE TABLE {quoted} (id INTEGER)")

            result = storage.connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
                (name,),
            ).fetchone()
            assert result is not None
            assert result[0] == name


# =============================================================================
# Properties JSON Roundtrip Tests
# =============================================================================


class TestPropertiesJsonRoundtrip:
    """Property-based tests for event properties JSON roundtrip."""

    @given(properties=event_properties)
    @settings(max_examples=50)
    def test_event_properties_survive_roundtrip(
        self, properties: dict[str, Any]
    ) -> None:
        """Event properties should survive storage and retrieval intact.

        This property verifies that any JSON-serializable properties dict
        can be stored in an event and retrieved unchanged.

        Args:
            properties: A dictionary of JSON-serializable values.
        """
        with StorageEngine.memory() as storage:
            event = {
                "event_name": "Test Event",
                "event_time": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
                "distinct_id": "test_user",
                "insert_id": "test_insert_id",
                "properties": properties,
            }

            metadata = TableMetadata(
                type="events",
                fetched_at=datetime.now(UTC),
            )

            storage.create_events_table("test_events", iter([event]), metadata)

            # Retrieve the stored properties
            df = storage.execute_df("SELECT properties FROM test_events")
            assert len(df) == 1

            # Parse the stored JSON
            stored_properties = json.loads(df["properties"].iloc[0])

            # Should match original properties
            assert stored_properties == properties

    @given(table_name=valid_table_names, properties=event_properties)
    @settings(max_examples=30)
    def test_properties_survive_with_any_valid_table_name(
        self, table_name: str, properties: dict[str, Any]
    ) -> None:
        """Properties roundtrip works with any valid table name.

        Args:
            table_name: A valid table name (alphanumeric + underscore).
            properties: A dictionary of JSON-serializable values.
        """
        with StorageEngine.memory() as storage:
            event = {
                "event_name": "Test Event",
                "event_time": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
                "distinct_id": "test_user",
                "insert_id": "test_insert_id",
                "properties": properties,
            }

            metadata = TableMetadata(
                type="events",
                fetched_at=datetime.now(UTC),
            )

            storage.create_events_table(table_name, iter([event]), metadata)

            # Retrieve and verify
            df = storage.execute_df(f"SELECT properties FROM {table_name}")
            stored_properties = json.loads(df["properties"].iloc[0])
            assert stored_properties == properties


# =============================================================================
# Profile Properties Roundtrip Tests
# =============================================================================


class TestProfilePropertiesRoundtrip:
    """Property-based tests for profile properties roundtrip."""

    @given(properties=event_properties)
    @settings(max_examples=30)
    def test_profile_properties_survive_roundtrip(
        self, properties: dict[str, Any]
    ) -> None:
        """Profile properties should survive storage and retrieval intact.

        Args:
            properties: A dictionary of JSON-serializable values.
        """
        with StorageEngine.memory() as storage:
            profile = {
                "distinct_id": "test_user",
                "properties": properties,
                "last_seen": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
            }

            metadata = TableMetadata(
                type="profiles",
                fetched_at=datetime.now(UTC),
            )

            storage.create_profiles_table("test_profiles", iter([profile]), metadata)

            # Retrieve the stored properties
            df = storage.execute_df("SELECT properties FROM test_profiles")
            assert len(df) == 1

            stored_properties = json.loads(df["properties"].iloc[0])
            assert stored_properties == properties
