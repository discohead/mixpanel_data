# Public API Contract: Typed Flow Query API

**Date**: 2026-04-06  
**Feature**: 034-flow-query

---

## 1. New Public Types

### FlowStep

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class FlowStep:
    event: str
    forward: int | None = None
    reverse: int | None = None
    label: str | None = None
    filters: list[Filter] | None = None
    filters_combinator: Literal["all", "any"] = "all"
```

### FlowQueryResult

```python
@dataclass(frozen=True)
class FlowQueryResult(ResultWithDataFrame):
    computed_at: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    flows: list[dict[str, Any]] = field(default_factory=list)
    breakdowns: list[dict[str, Any]] = field(default_factory=list)
    overall_conversion_rate: float = 0.0
    params: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    mode: Literal["sankey", "paths"] = "sankey"

    @property
    def nodes_df(self) -> pd.DataFrame: ...

    @property
    def edges_df(self) -> pd.DataFrame: ...

    @property
    def graph(self) -> nx.DiGraph: ...

    @property
    def df(self) -> pd.DataFrame: ...

    def top_transitions(self, n: int = 10) -> list[tuple[str, str, int]]: ...

    def drop_off_summary(self) -> dict[str, Any]: ...

    def to_dict(self) -> dict[str, Any]: ...
```

### Type Aliases

```python
FlowCountType = Literal["unique", "total", "session"]
FlowChartType = Literal["sankey", "paths"]
```

---

## 2. New Workspace Methods

### query_flow()

```python
def query_flow(
    self,
    event: str | FlowStep | Sequence[str | FlowStep],
    *,
    forward: int = 3,
    reverse: int = 0,
    from_date: str | None = None,
    to_date: str | None = None,
    last: int = 30,
    conversion_window: int = 7,
    conversion_window_unit: Literal["day", "week", "month"] = "day",
    count_type: Literal["unique", "total", "session"] = "unique",
    cardinality: int = 3,
    collapse_repeated: bool = False,
    hidden_events: list[str] | None = None,
    mode: Literal["sankey", "paths"] = "sankey",
) -> FlowQueryResult: ...
```

### build_flow_params()

```python
def build_flow_params(
    self,
    event: str | FlowStep | Sequence[str | FlowStep],
    *,
    forward: int = 3,
    reverse: int = 0,
    from_date: str | None = None,
    to_date: str | None = None,
    last: int = 30,
    conversion_window: int = 7,
    conversion_window_unit: Literal["day", "week", "month"] = "day",
    count_type: Literal["unique", "total", "session"] = "unique",
    cardinality: int = 3,
    collapse_repeated: bool = False,
    hidden_events: list[str] | None = None,
    mode: Literal["sankey", "paths"] = "sankey",
) -> dict[str, Any]: ...
```

### query_saved_flows() (renamed from query_flows)

```python
def query_saved_flows(self, bookmark_id: int) -> FlowsResult: ...
```

---

## 3. New API Client Method

### arb_funnels_query()

```python
def arb_funnels_query(
    self,
    body: dict[str, Any],
) -> dict[str, Any]: ...
```

**Request body format**:
```json
{
    "project_id": 12345,
    "query_type": "flows_sankey",
    "bookmark": { /* flat flow bookmark params */ }
}
```

---

## 4. New Service Method

### LiveQueryService.query_flow()

```python
def query_flow(
    self,
    bookmark_params: dict[str, Any],
    project_id: int,
    mode: str = "sankey",
) -> FlowQueryResult: ...
```

---

## 5. New Validation Functions

### validate_flow_args()

```python
def validate_flow_args(
    *,
    steps: list[str],
    forward: int = 3,
    reverse: int = 0,
    count_type: str = "unique",
    mode: str = "sankey",
    cardinality: int = 3,
    conversion_window: int = 7,
    from_date: str | None = None,
    to_date: str | None = None,
    last: int = 30,
) -> list[ValidationError]: ...
```

### validate_flow_bookmark()

```python
def validate_flow_bookmark(
    params: dict[str, Any],
) -> list[ValidationError]: ...
```

---

## 6. New Internal Functions

### build_segfilter_entry()

```python
def build_segfilter_entry(f: Filter) -> dict[str, Any]: ...
```

Located in `_internal/bookmark_builders.py`. Converts a `Filter` object to legacy segfilter format.

---

## 7. Exports (__init__.py)

New additions to `__all__`:

```python
# Types
"FlowStep",
"FlowQueryResult",

# Type aliases
"FlowCountType",
"FlowChartType",
```

---

## 8. Error Contract

All validation errors raise `BookmarkValidationError` containing `list[ValidationError]`.

Each `ValidationError` includes:
- `code`: Rule code (e.g., `"FL1"`, `"FL3"`, `"FLB3"`)
- `path`: Parameter path (e.g., `"forward"`, `"steps[0].event"`)
- `message`: Human-readable error message
- `severity`: `"error"` or `"warning"`
- `suggestion`: Fuzzy-matched suggestion for enum mismatches (optional)
