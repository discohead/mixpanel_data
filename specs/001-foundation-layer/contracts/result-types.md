# Contract: Result Types

**Type**: Internal Python Interface
**Module**: `mixpanel_data.types`
**Public Access**: Direct import from `mixpanel_data`

## Interface Definition

### FetchResult

```python
@dataclass(frozen=True)
class FetchResult:
    """Result of a data fetch operation."""

    table: str
    """Name of the created table."""

    rows: int
    """Number of rows fetched."""

    type: Literal["events", "profiles"]
    """Type of data fetched."""

    duration_seconds: float
    """Time taken to complete the fetch."""

    date_range: tuple[str, str] | None
    """Date range for events (None for profiles)."""

    fetched_at: datetime
    """Timestamp when fetch completed."""

    @property
    def df(self) -> pd.DataFrame:
        """
        Convert result data to pandas DataFrame.

        Returns:
            DataFrame with fetched data.

        Note:
            Conversion is lazy - computed on first access.
        """
        ...

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize result for JSON output.

        Returns:
            Dictionary representation (excludes raw data).
        """
        ...
```

### SegmentationResult

```python
@dataclass(frozen=True)
class SegmentationResult:
    """Result of a segmentation query."""

    event: str
    """Queried event name."""

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    unit: Literal["day", "week", "month"]
    """Time unit for aggregation."""

    segment_property: str | None
    """Property used for segmentation (None if total only)."""

    total: int
    """Total count across all segments and time periods."""

    series: dict[str, dict[str, int]]
    """
    Time series data by segment.

    Structure: {segment_name: {date_string: count}}
    Example: {"US": {"2024-01-01": 150, "2024-01-02": 200}, "EU": {...}}
    For unsegmented queries, segment_name is "total".
    """

    @property
    def df(self) -> pd.DataFrame:
        """
        Convert to DataFrame with columns: date, segment, count.

        For unsegmented queries, segment column is 'total'.
        """
        ...

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        ...
```

### FunnelResult

```python
@dataclass(frozen=True)
class FunnelResult:
    """Result of a funnel query."""

    funnel_id: int
    """Funnel identifier."""

    funnel_name: str
    """Funnel display name."""

    from_date: str
    """Query start date."""

    to_date: str
    """Query end date."""

    conversion_rate: float
    """Overall conversion rate (0.0 to 1.0)."""

    steps: list[FunnelStep]
    """Step-by-step breakdown."""

    @property
    def df(self) -> pd.DataFrame:
        """
        Convert to DataFrame with columns: step, event, count, conversion_rate.
        """
        ...

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        ...


@dataclass(frozen=True)
class FunnelStep:
    """Single step in a funnel."""

    event: str
    """Event name for this step."""

    count: int
    """Number of users at this step."""

    conversion_rate: float
    """Conversion rate from previous step (0.0 to 1.0)."""
```

### RetentionResult

```python
@dataclass(frozen=True)
class RetentionResult:
    """Result of a retention query."""

    born_event: str
    """Event that defines cohort membership."""

    return_event: str
    """Event that defines return."""

    from_date: str
    """Query start date."""

    to_date: str
    """Query end date."""

    unit: Literal["day", "week", "month"]
    """Time unit for retention periods."""

    cohorts: list[CohortInfo]
    """Cohort retention data."""

    @property
    def df(self) -> pd.DataFrame:
        """
        Convert to DataFrame with columns: cohort_date, cohort_size, period_N.
        """
        ...

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        ...


@dataclass(frozen=True)
class CohortInfo:
    """Retention data for a single cohort."""

    date: str
    """Cohort date (when users were 'born')."""

    size: int
    """Number of users in cohort."""

    retention: list[float]
    """Retention percentages by period (0.0 to 1.0)."""
```

### JQLResult

```python
@dataclass(frozen=True)
class JQLResult:
    """Result of a JQL query."""

    @property
    def df(self) -> pd.DataFrame:
        """Convert result to DataFrame."""
        ...

    @property
    def raw(self) -> list[Any]:
        """Raw result data from JQL execution."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        ...
```

## Common Behaviors

All result types share these behaviors:

1. **Immutable**: Created with `frozen=True`, cannot be modified
2. **Lazy DataFrame**: `df` property computed on first access, cached
3. **JSON Serializable**: `to_dict()` returns serializable dictionary
4. **Type Safe**: Full type hints for IDE/mypy support

## Usage Examples

```python
from mixpanel_data import Workspace

ws = Workspace()

# FetchResult
result = ws.fetch_events(
    name="january_events",
    from_date="2024-01-01",
    to_date="2024-01-31",
)
print(f"Fetched {result.rows} rows in {result.duration_seconds:.2f}s")
print(f"Table: {result.table}")
df = result.df  # Lazy conversion

# SegmentationResult
seg = ws.segmentation(
    event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31",
    on="country",
)
print(f"Total: {seg.total}")
seg.df.head()

# FunnelResult
funnel = ws.funnel(
    funnel_id=12345,
    from_date="2024-01-01",
    to_date="2024-01-31",
)
print(f"Conversion: {funnel.conversion_rate:.1%}")
for step in funnel.steps:
    print(f"  {step.event}: {step.count} ({step.conversion_rate:.1%})")

# JSON serialization
import json
print(json.dumps(result.to_dict(), indent=2))
```

## Testing Contract

```python
def test_fetch_result_immutable():
    """FetchResult should be immutable."""
    result = FetchResult(
        table="test",
        rows=100,
        type="events",
        duration_seconds=1.5,
        date_range=("2024-01-01", "2024-01-31"),
        fetched_at=datetime.now(),
    )

    with pytest.raises(FrozenInstanceError):
        result.rows = 200


def test_fetch_result_df_lazy():
    """DataFrame should be computed lazily."""
    result = FetchResult(...)

    # No DataFrame created yet
    assert "_df" not in result.__dict__

    # Access triggers computation
    df = result.df
    assert isinstance(df, pd.DataFrame)


def test_fetch_result_to_dict_serializable():
    """to_dict output must be JSON serializable."""
    result = FetchResult(...)
    data = result.to_dict()

    # Should not raise
    json.dumps(data)

    # Should have expected keys
    assert "table" in data
    assert "rows" in data
    assert "fetched_at" in data


def test_segmentation_result_df_columns():
    """SegmentationResult.df should have expected columns."""
    result = SegmentationResult(...)
    df = result.df

    assert "date" in df.columns
    assert "count" in df.columns
```
