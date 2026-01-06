# Implementation Plan: Dynamic Text Search (`search_text()`)

**Status**: Draft
**Created**: 2026-01-05
**Author**: Claude (based on FTS research discussion)

## Overview

Add a `search_text()` method to Workspace that performs text search across event names and all string-type JSON properties using dynamically generated SQL queries.

This approach was chosen over DuckDB's Full-Text Search extension due to:
- **Architectural mismatch**: FTS requires VARCHAR columns; properties are JSON
- **Index maintenance**: FTS indexes don't auto-update; streaming ingestion makes this problematic
- **Workload mismatch**: Analytics is aggregation-heavy, not search-heavy

The dynamic query approach provides 80% of the value with minimal complexity.

## Design

### Public API

```python
@dataclass(frozen=True)
class SearchResult(ResultWithDataFrame):
    """Result from text search operation.

    Attributes:
        query: The search term used.
        table: Table that was searched.
        matches: List of matching rows as dictionaries.
        total_matches: Total count of matches (may exceed len(matches) if limited).
        searched_properties: List of property names that were searched.
    """
    query: str
    table: str
    matches: list[dict[str, Any]]
    total_matches: int
    searched_properties: list[str]

    @property
    def df(self) -> pd.DataFrame:
        """Convert matches to DataFrame."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        ...


def search_text(
    self,
    query: str,
    table: str,
    *,
    limit: int = 100,
    case_sensitive: bool = False,
    event: str | None = None,
) -> SearchResult:
    """Search for text across event names and string properties.

    Performs case-insensitive substring search across:
    - event_name column (for events tables)
    - All string-type properties in the JSON 'properties' column

    Args:
        query: Text to search for. Supports multiple words (AND logic).
        table: Table name to search in.
        limit: Maximum results to return. Default: 100.
        case_sensitive: Use case-sensitive matching. Default: False.
        event: Optional event name filter (search only this event type).

    Returns:
        SearchResult with matching rows and metadata.

    Raises:
        TableNotFoundError: If table doesn't exist.
        QueryError: If table lacks required columns.
        ValueError: If query is empty.

    Example:
        ```python
        # Search all events for "checkout"
        result = ws.search_text("checkout", "events")
        print(f"Found {result.total_matches} matches")
        for row in result.matches[:5]:
            print(row["event_name"], row["properties"])

        # Search only Purchase events for "error"
        result = ws.search_text("error", "events", event="Purchase")

        # Case-sensitive search
        result = ws.search_text("ErrorCode", "events", case_sensitive=True)
        ```
    """
```

### Internal Helper: Property Type Detection

```python
def _get_string_property_keys(
    self,
    table: str,
    *,
    event: str | None = None,
    sample_size: int = 1000,
) -> list[str]:
    """Get property keys that contain string values.

    Uses DuckDB's json_type() function to sample property values and
    identify which properties contain strings (searchable text).

    Strategy:
    1. Sample rows from the table
    2. Extract all property keys using json_keys()
    3. Check json_type() for each key's values
    4. Return keys where any value is VARCHAR type

    Args:
        table: Table name with 'properties' JSON column.
        event: Optional event filter.
        sample_size: Number of rows to sample for type inference.

    Returns:
        List of property key names that contain string values.
    """
```

### Generated SQL Pattern

For a search query like `ws.search_text("checkout error", "events")`:

```sql
-- Step 1: Get string properties (cached per session)
WITH property_sample AS (
    SELECT DISTINCT unnest(json_keys(properties)) as key
    FROM "events"
    WHERE properties IS NOT NULL
    LIMIT 1000
),
string_props AS (
    SELECT DISTINCT ps.key
    FROM property_sample ps
    JOIN "events" e ON json_type(e.properties, '$.' || ps.key) = 'VARCHAR'
    LIMIT 100
)
SELECT key FROM string_props ORDER BY key;

-- Step 2: Dynamic search query (generated from Step 1 results)
SELECT
    event_name,
    event_time,
    distinct_id,
    insert_id,
    properties
FROM "events"
WHERE
    (event_name ILIKE '%checkout%' AND event_name ILIKE '%error%')
    OR (properties->>'$.button_text' ILIKE '%checkout%' AND properties->>'$.button_text' ILIKE '%error%')
    OR (properties->>'$.page_title' ILIKE '%checkout%' AND properties->>'$.page_title' ILIKE '%error%')
    OR (properties->>'$.error_message' ILIKE '%checkout%' AND properties->>'$.error_message' ILIKE '%error%')
ORDER BY event_time DESC
LIMIT 100;
```

### DuckDB Functions Used

| Function | Purpose | Example |
|----------|---------|---------|
| `json_keys(json)` | Get all keys from JSON object | `json_keys('{"a":1,"b":2}')` → `['a', 'b']` |
| `json_type(json, path)` | Get type of JSON value at path | `json_type('{"a":"x"}', '$.a')` → `'VARCHAR'` |
| `properties->>'$.key'` | Extract JSON value as string | `properties->>'$.city'` → `'NYC'` |
| `ILIKE` | Case-insensitive LIKE | `event_name ILIKE '%checkout%'` |
| `unnest()` | Expand array to rows | `unnest(['a','b'])` → 2 rows |

### JSON Type Values

DuckDB's `json_type()` returns:
- `'VARCHAR'` - String (searchable)
- `'BIGINT'` / `'UBIGINT'` - Integer (skip)
- `'DOUBLE'` - Float (skip)
- `'BOOLEAN'` - Boolean (skip)
- `'ARRAY'` - Array (could recursively search, but skip for v1)
- `'OBJECT'` - Nested object (could recursively search, but skip for v1)
- `'NULL'` - Null value (skip)

### Performance Considerations

1. **Property discovery is O(sample_size)** - We sample 1000 rows to infer types
2. **Search is O(n * m)** where n = rows, m = string properties
3. **No index overhead** - Pure scan, leverages DuckDB's vectorized execution
4. **Caching** - Consider caching string property list per (table, event) key

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| Empty query string | Raise `ValueError("Search query cannot be empty")` |
| No string properties | Return empty result (log warning) |
| Query with special chars | Escape for LIKE (`%`, `_`, `\`) |
| Unicode in query | Pass through (DuckDB handles Unicode) |
| Null properties | `properties->>'$.key'` returns NULL, ILIKE NULL is false (safe) |
| Table without `properties` | Raise `QueryError` |

## TDD Test Plan

### Test File: `tests/unit/test_workspace_search.py`

#### Fixtures

```python
@pytest.fixture
def events_with_text(storage: StorageEngine) -> None:
    """Create events table with diverse text properties."""
    events = [
        {
            "event_name": "Checkout Started",
            "event_time": datetime(2024, 1, 1, 10, 0, 0),
            "distinct_id": "user_1",
            "insert_id": "id_1",
            "properties": {
                "button_text": "Begin Checkout",
                "page": "/cart",
                "item_count": 3,  # numeric - should not be searched
            },
        },
        {
            "event_name": "Checkout Error",
            "event_time": datetime(2024, 1, 1, 10, 5, 0),
            "distinct_id": "user_1",
            "insert_id": "id_2",
            "properties": {
                "error_message": "Payment declined",
                "error_code": 4001,  # numeric
                "page": "/checkout",
            },
        },
        {
            "event_name": "Page View",
            "event_time": datetime(2024, 1, 1, 11, 0, 0),
            "distinct_id": "user_2",
            "insert_id": "id_3",
            "properties": {
                "page": "/home",
                "referrer": "google.com",
            },
        },
        {
            "event_name": "Purchase Complete",
            "event_time": datetime(2024, 1, 2, 14, 0, 0),
            "distinct_id": "user_1",
            "insert_id": "id_4",
            "properties": {
                "confirmation_message": "Thank you for your purchase!",
                "amount": 99.99,  # numeric
                "currency": "USD",
            },
        },
    ]
    metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))
    storage.create_events_table("events", iter(events), metadata)


@pytest.fixture
def profiles_with_text(storage: StorageEngine) -> None:
    """Create profiles table with text properties."""
    profiles = [
        {
            "distinct_id": "user_1",
            "properties": {
                "$name": "John Doe",
                "$email": "john@example.com",
                "company": "Acme Corp",
                "plan": "enterprise",
            },
            "last_seen": datetime(2024, 1, 5, 12, 0, 0),
        },
        {
            "distinct_id": "user_2",
            "properties": {
                "$name": "Jane Smith",
                "$email": "jane@startup.io",
                "company": "Startup Inc",
                "plan": "free",
            },
            "last_seen": datetime(2024, 1, 4, 9, 0, 0),
        },
    ]
    metadata = TableMetadata(type="profiles", fetched_at=datetime.now(UTC))
    storage.create_profiles_table("profiles", iter(profiles), metadata)
```

#### Test Cases

```python
class TestSearchText:
    """Tests for Workspace.search_text() method."""

    # === Basic Functionality ===

    def test_search_finds_match_in_event_name(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """Search matches text in event_name column."""
        result = workspace.search_text("Checkout", "events")
        assert result.total_matches == 2
        event_names = [m["event_name"] for m in result.matches]
        assert "Checkout Started" in event_names
        assert "Checkout Error" in event_names

    def test_search_finds_match_in_string_property(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """Search matches text in string-type properties."""
        result = workspace.search_text("declined", "events")
        assert result.total_matches == 1
        assert result.matches[0]["event_name"] == "Checkout Error"

    def test_search_case_insensitive_by_default(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """Search is case-insensitive by default."""
        result_lower = workspace.search_text("checkout", "events")
        result_upper = workspace.search_text("CHECKOUT", "events")
        result_mixed = workspace.search_text("ChEcKoUt", "events")
        assert result_lower.total_matches == result_upper.total_matches
        assert result_lower.total_matches == result_mixed.total_matches

    def test_search_case_sensitive_option(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """Case-sensitive search when specified."""
        result_exact = workspace.search_text("Checkout", "events", case_sensitive=True)
        result_lower = workspace.search_text("checkout", "events", case_sensitive=True)
        assert result_exact.total_matches == 2
        assert result_lower.total_matches == 0

    # === Multiple Words (AND Logic) ===

    def test_search_multiple_words_all_must_match(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """Multiple search terms require all to match in same field."""
        result = workspace.search_text("Checkout Error", "events")
        assert result.total_matches == 1
        assert result.matches[0]["event_name"] == "Checkout Error"

    # === Filtering ===

    def test_search_with_event_filter(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """Event filter restricts search to specific event type."""
        # "page" appears in multiple events
        result_all = workspace.search_text("/checkout", "events")
        result_filtered = workspace.search_text("/checkout", "events", event="Checkout Error")
        assert result_all.total_matches >= 1
        assert result_filtered.total_matches == 1
        assert result_filtered.matches[0]["event_name"] == "Checkout Error"

    def test_search_with_limit(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """Limit parameter caps returned results."""
        result = workspace.search_text("page", "events", limit=2)
        assert len(result.matches) <= 2
        assert result.total_matches >= len(result.matches)

    # === Property Type Filtering ===

    def test_search_excludes_numeric_properties(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """Numeric property values are not searched."""
        # Search for "4001" which exists only as error_code (numeric)
        result = workspace.search_text("4001", "events")
        assert result.total_matches == 0
        assert "error_code" not in result.searched_properties

    def test_search_excludes_boolean_properties(
        self, workspace: Workspace, storage: StorageEngine
    ) -> None:
        """Boolean property values are not searched."""
        # Create event with boolean property
        events = [{
            "event_name": "Test",
            "event_time": datetime(2024, 1, 1, 10, 0, 0),
            "distinct_id": "user_1",
            "insert_id": "bool_test",
            "properties": {"is_active": True, "label": "true_label"},
        }]
        metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))
        storage.create_events_table("bool_events", iter(events), metadata)

        # "true" should match label but not is_active
        result = workspace.search_text("true", "bool_events")
        assert result.total_matches == 1
        assert "is_active" not in result.searched_properties
        assert "label" in result.searched_properties

    # === SearchResult Structure ===

    def test_result_contains_searched_properties_list(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """Result includes list of properties that were searched."""
        result = workspace.search_text("test", "events")
        assert isinstance(result.searched_properties, list)
        assert "button_text" in result.searched_properties
        assert "error_message" in result.searched_properties
        assert "page" in result.searched_properties
        # Numeric properties excluded
        assert "item_count" not in result.searched_properties
        assert "error_code" not in result.searched_properties
        assert "amount" not in result.searched_properties

    def test_result_df_property_returns_dataframe(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """SearchResult.df returns pandas DataFrame."""
        result = workspace.search_text("Checkout", "events")
        df = result.df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == result.total_matches
        assert "event_name" in df.columns
        assert "properties" in df.columns

    def test_result_to_dict_is_json_serializable(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """SearchResult.to_dict() produces JSON-serializable output."""
        import json
        result = workspace.search_text("Checkout", "events")
        serialized = json.dumps(result.to_dict())
        assert isinstance(serialized, str)

    # === Profiles Table ===

    def test_search_works_on_profiles_table(
        self, workspace: Workspace, profiles_with_text: None
    ) -> None:
        """Search works on profiles tables (no event_name column)."""
        result = workspace.search_text("enterprise", "profiles")
        assert result.total_matches == 1
        assert result.matches[0]["distinct_id"] == "user_1"

    def test_search_profiles_searches_distinct_id(
        self, workspace: Workspace, profiles_with_text: None
    ) -> None:
        """Search includes distinct_id column for profiles."""
        result = workspace.search_text("user_1", "profiles")
        assert result.total_matches == 1

    # === Edge Cases ===

    def test_search_empty_query_raises_error(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """Empty search query raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            workspace.search_text("", "events")
        with pytest.raises(ValueError, match="cannot be empty"):
            workspace.search_text("   ", "events")

    def test_search_nonexistent_table_raises_error(
        self, workspace: Workspace
    ) -> None:
        """Searching non-existent table raises TableNotFoundError."""
        with pytest.raises(TableNotFoundError):
            workspace.search_text("test", "nonexistent")

    def test_search_table_without_properties_column(
        self, workspace: Workspace, storage: StorageEngine
    ) -> None:
        """Table without 'properties' column raises QueryError."""
        storage.connection.execute("CREATE TABLE plain (id INT, name VARCHAR)")
        with pytest.raises(QueryError, match="properties"):
            workspace.search_text("test", "plain")

    def test_search_empty_table_returns_empty_result(
        self, workspace: Workspace, storage: StorageEngine
    ) -> None:
        """Search on empty table returns empty result."""
        metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))
        storage.create_events_table("empty", iter([]), metadata)
        result = workspace.search_text("anything", "empty")
        assert result.total_matches == 0
        assert result.matches == []

    def test_search_no_matches_returns_empty_result(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """Search with no matches returns empty result."""
        result = workspace.search_text("xyznonexistent123", "events")
        assert result.total_matches == 0
        assert result.matches == []

    def test_search_special_characters_escaped(
        self, workspace: Workspace, storage: StorageEngine
    ) -> None:
        """Special LIKE characters (%, _) are escaped in query."""
        events = [{
            "event_name": "Test % Percent",
            "event_time": datetime(2024, 1, 1, 10, 0, 0),
            "distinct_id": "user_1",
            "insert_id": "special_1",
            "properties": {"label": "100% complete"},
        }]
        metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))
        storage.create_events_table("special", iter(events), metadata)

        # Should find literal "%" not wildcard
        result = workspace.search_text("100%", "special")
        assert result.total_matches == 1

    def test_search_null_properties_handled(
        self, workspace: Workspace, storage: StorageEngine
    ) -> None:
        """Events with NULL properties don't cause errors."""
        events = [
            {
                "event_name": "Has Props",
                "event_time": datetime(2024, 1, 1, 10, 0, 0),
                "distinct_id": "user_1",
                "insert_id": "null_1",
                "properties": {"text": "searchable"},
            },
            {
                "event_name": "Null Props",
                "event_time": datetime(2024, 1, 1, 11, 0, 0),
                "distinct_id": "user_2",
                "insert_id": "null_2",
                "properties": None,  # Will be stored as NULL
            },
        ]
        metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))
        # Note: Current schema requires properties, this tests edge case
        storage.create_events_table("null_props", iter(events), metadata)

        # Should not error, should find the match
        result = workspace.search_text("searchable", "null_props")
        assert result.total_matches == 1


class TestGetStringPropertyKeys:
    """Tests for internal _get_string_property_keys() helper."""

    def test_returns_only_string_type_properties(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """Only properties with string values are returned."""
        keys = workspace._get_string_property_keys("events")
        assert "button_text" in keys
        assert "error_message" in keys
        assert "page" in keys
        # Numeric properties excluded
        assert "item_count" not in keys
        assert "error_code" not in keys
        assert "amount" not in keys

    def test_with_event_filter(
        self, workspace: Workspace, events_with_text: None
    ) -> None:
        """Event filter restricts property discovery."""
        keys = workspace._get_string_property_keys("events", event="Purchase Complete")
        assert "confirmation_message" in keys
        assert "currency" in keys
        # Properties from other events excluded
        assert "button_text" not in keys
        assert "error_message" not in keys

    def test_empty_table_returns_empty_list(
        self, workspace: Workspace, storage: StorageEngine
    ) -> None:
        """Empty table returns empty property list."""
        metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))
        storage.create_events_table("empty", iter([]), metadata)
        keys = workspace._get_string_property_keys("empty")
        assert keys == []
```

### Property-Based Tests: `tests/unit/test_workspace_search_pbt.py`

```python
"""Property-based tests for search_text using Hypothesis."""

from hypothesis import given, strategies as st
from mixpanel_data import Workspace

# Strategy for valid search queries
search_queries = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(blacklist_categories=["Cs"]),  # No surrogates
).filter(lambda x: x.strip())  # Non-empty after strip


class TestSearchTextProperties:
    """Property-based tests for search invariants."""

    @given(query=search_queries)
    def test_search_never_raises_unexpected_exception(
        self, workspace_with_events: Workspace, query: str
    ) -> None:
        """Search should handle any valid query string without crashing."""
        # Should complete without unexpected exceptions
        result = workspace_with_events.search_text(query, "events")
        assert result.total_matches >= 0
        assert len(result.matches) <= result.total_matches

    @given(limit=st.integers(min_value=1, max_value=1000))
    def test_matches_never_exceed_limit(
        self, workspace_with_events: Workspace, limit: int
    ) -> None:
        """Returned matches never exceed specified limit."""
        result = workspace_with_events.search_text("a", "events", limit=limit)
        assert len(result.matches) <= limit

    @given(query=search_queries)
    def test_searched_properties_are_strings(
        self, workspace_with_events: Workspace, query: str
    ) -> None:
        """searched_properties only contains string-type property names."""
        result = workspace_with_events.search_text(query, "events")
        # All searched properties should be strings
        for prop in result.searched_properties:
            assert isinstance(prop, str)
```

## Implementation Checklist

### Phase 1: Result Type
- [ ] Add `SearchResult` dataclass to `types.py`
- [ ] Implement `df` property with lazy caching
- [ ] Implement `to_dict()` serialization
- [ ] Implement `to_table_dict()` for CLI output
- [ ] Add unit tests for `SearchResult`

### Phase 2: Property Type Detection
- [ ] Add `_get_string_property_keys()` to Workspace
- [ ] Use `json_keys()` + `json_type()` for type inference
- [ ] Add event filter support
- [ ] Add unit tests for property detection

### Phase 3: Core Search Method
- [ ] Add `search_text()` to Workspace
- [ ] Generate dynamic SQL with OR conditions
- [ ] Escape special LIKE characters (`%`, `_`)
- [ ] Handle multi-word queries (AND logic per field)
- [ ] Add case sensitivity option
- [ ] Add event filter option
- [ ] Add limit parameter
- [ ] Add unit tests for all cases

### Phase 4: CLI Integration (Optional)
- [ ] Add `mp query search` command
- [ ] Support `--format` options (json, table, csv)
- [ ] Support `--jq` filtering
- [ ] Add CLI tests

## Performance Notes

| Dataset Size | Expected Latency | Notes |
|--------------|------------------|-------|
| 10K events | <100ms | Fast enough for interactive use |
| 100K events | 100-500ms | Acceptable for exploratory queries |
| 1M events | 1-5s | Consider suggesting time filters |
| 10M events | 10-60s | Recommend specific event filter |

For large datasets, the method should log a warning suggesting narrower filters.

## Future Enhancements

1. **Relevance Ranking**: Score matches by number of term occurrences
2. **Highlighting**: Return matched substrings for UI display
3. **Fuzzy Matching**: Support typo tolerance via Levenshtein distance
4. **Nested JSON**: Recursively search nested objects/arrays
5. **Caching**: Cache string property lists per (table, event) for session

## References

- [DuckDB JSON Functions](https://duckdb.org/docs/data/json/json_functions)
- [Original FTS Research Discussion](./README.md#why-not-fts) (this conversation)
- [Existing property_keys() implementation](../../src/mixpanel_data/workspace.py:2244)
