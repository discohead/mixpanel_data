# Public API Contract: Workspace.query()

**Feature**: 029-insights-query-api  
**Date**: 2026-04-04

## Method Signature

```python
def query(
    self,
    events: str | Metric | Sequence[str | Metric],
    *,
    # Time range
    from_date: str | None = None,
    to_date: str | None = None,
    last: int = 30,
    unit: Literal["hour", "day", "week", "month", "quarter"] = "day",

    # Aggregation defaults (apply to plain-string events)
    math: MathType = "total",
    math_property: str | None = None,
    per_user: PerUserAggregation | None = None,

    # Breakdown
    group_by: str | GroupBy | list[str | GroupBy] | None = None,

    # Filters
    where: Filter | list[Filter] | None = None,

    # Formula
    formula: str | None = None,
    formula_label: str | None = None,

    # Analysis mode
    rolling: int | None = None,
    cumulative: bool = False,

    # Result shape
    mode: Literal["timeseries", "total", "table"] = "timeseries",
) -> QueryResult:
```

## Public Types

### Metric

```python
@dataclass(frozen=True)
class Metric:
    event: str
    math: MathType = "total"
    property: str | None = None
    per_user: PerUserAggregation | None = None
    filters: list[Filter] | None = None
```

### Filter

Constructed via class methods only:

```python
Filter.equals(property, value, *, resource_type="events") -> Filter
Filter.not_equals(property, value, *, resource_type="events") -> Filter
Filter.contains(property, value, *, resource_type="events") -> Filter
Filter.not_contains(property, value, *, resource_type="events") -> Filter
Filter.greater_than(property, value, *, resource_type="events") -> Filter
Filter.less_than(property, value, *, resource_type="events") -> Filter
Filter.between(property, min_val, max_val, *, resource_type="events") -> Filter
Filter.is_set(property, *, resource_type="events") -> Filter
Filter.is_not_set(property, *, resource_type="events") -> Filter
Filter.is_true(property, *, resource_type="events") -> Filter
Filter.is_false(property, *, resource_type="events") -> Filter
```

### GroupBy

```python
@dataclass(frozen=True)
class GroupBy:
    property: str
    property_type: Literal["string", "number", "boolean", "datetime"] = "string"
    bucket_size: int | float | None = None
    bucket_min: int | float | None = None
    bucket_max: int | float | None = None
```

### QueryResult

```python
@dataclass(frozen=True)
class QueryResult(ResultWithDataFrame):
    computed_at: str
    from_date: str
    to_date: str
    headers: list[str]
    series: dict[str, Any]
    params: dict[str, Any]
    meta: dict[str, Any]

    @property
    def df(self) -> pd.DataFrame: ...
```

### Type Aliases

```python
MathType = Literal[
    "total", "unique", "dau", "wau", "mau",
    "average", "median", "min", "max", "sum",
    "p25", "p75", "p90", "p99",
]

PerUserAggregation = Literal["average", "total", "min", "max"]

FilterPropertyType = Literal["string", "number", "boolean", "datetime", "list"]
```

## Public Exports

The following names must be exported from `mixpanel_data.__init__`:

- `Metric`
- `Filter`
- `GroupBy`
- `QueryResult`
- `MathType`
- `PerUserAggregation`

## Error Contract

All validation errors raise `ValueError` with descriptive messages before any API call.

| Condition | Error Message Pattern |
|-----------|----------------------|
| Property math without property | `math='{math}' requires math_property to be set` |
| Property set for non-property math | `math_property is only valid with property-based math types (...), not '{math}'` |
| per_user with DAU/WAU/MAU | `per_user is incompatible with math='{math}'` |
| Formula with < 2 events | `formula requires at least 2 events (got {n})` |
| Rolling + cumulative | `rolling and cumulative are mutually exclusive` |
| Rolling <= 0 | `rolling must be a positive integer` |
| last <= 0 | `last must be a positive integer` |
| to_date without from_date | `to_date requires from_date` |
| Explicit dates + non-default last | `Cannot combine last={last} with explicit dates; use either last or from_date/to_date` |
| Invalid date format | `from_date must be YYYY-MM-DD format (got '{from_date}')` |
| bucket_min/max without bucket_size | `bucket_min/bucket_max require bucket_size` |
| bucket_size <= 0 | `bucket_size must be positive` |

API errors propagate as existing exception types:
- `AuthenticationError` (401)
- `QueryError` (400, 403, 404)
- `RateLimitError` (429) — with automatic retry
- `ServerError` (5xx)

## Backward Compatibility

- No existing methods are modified
- No existing types are changed
- New types are additive exports
- `query()` is a new method on `Workspace` — no naming conflicts
