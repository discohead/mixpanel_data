# TypedDict for API Response Types - TDD Implementation Plan

## Overview

Add `TypedDict` definitions for core Mixpanel API response types to improve type safety, IDE support, and AI-assisted development. This change primarily benefits library maintainers (human and AI) by making the internal parsing code self-documenting.

## Motivation

Currently, API responses are typed as `dict[str, Any]`, forcing developers to:
1. Search documentation or examples to understand response structure
2. Make educated guesses about field names and types
3. Iterate through trial and error

With TypedDicts:
- IDE autocomplete shows available keys
- Mypy catches typos and type mismatches
- AI agents can write correct parsers on the first try
- Response contracts are documented in code

## Scope

### In Scope
- **Segmentation API**: `/segmentation`, `/segmentation/numeric`, `/segmentation/sum`, `/segmentation/average`
- **Funnel API**: `/funnels`, `/funnels/list`
- **Retention API**: `/retention`, `/retention/addiction`
- **Cohorts API**: `/cohorts/list`
- **Events Export API**: Raw event format from `/export`
- **Events Query API**: `/events`, `/events/top`, `/events/properties`

### Out of Scope
- JQL results (inherently dynamic)
- Lexicon/discovery responses (already well-typed with dataclasses)
- User profile/engage responses (complex, less frequently used)
- Bookmark API responses (already handled by dedicated types)

## Design Decisions

### 1. Location: New Internal Module
```
src/mixpanel_data/_internal/api_types.py
```

Rationale: TypedDicts are internal implementation details, not public API. They belong in `_internal/` alongside `api_client.py`.

### 2. Naming Convention
```python
class SegmentationAPIResponse(TypedDict):  # Top-level response
class SegmentationData(TypedDict):          # Nested structure
class SegmentationValues(TypedDict):        # Deeply nested
```

Pattern: `{Endpoint}APIResponse` for top-level, `{Endpoint}{Component}` for nested.

### 3. Optional Fields with `NotRequired`
```python
from typing import TypedDict, NotRequired

class FunnelAPIResponse(TypedDict):
    data: FunnelData
    computed_at: NotRequired[str]  # Not always present
```

### 4. Gradual Adoption
- TypedDicts used in `_transform_*` functions first
- API client methods remain `-> dict[str, Any]` initially
- Full migration to typed returns in a follow-up phase

## API Response Structures

### Segmentation Response
```python
class SegmentationAPIResponse(TypedDict):
    """Response from GET /segmentation endpoint."""
    data: SegmentationData
    legend_size: NotRequired[int]

class SegmentationData(TypedDict):
    """Nested data structure in segmentation response."""
    series: list[str]  # Date strings
    values: dict[str, dict[str, int]]  # {segment: {date: count}}
```

Source: [mixpanel-http-api-specification.md](../mixpanel-http-api-specification.md) lines 229-239

### Funnel Response
```python
class FunnelAPIResponse(TypedDict):
    """Response from GET /funnels endpoint."""
    data: dict[str, FunnelDateData]  # {date: FunnelDateData}

class FunnelDateData(TypedDict):
    """Per-date funnel data."""
    steps: list[FunnelStep]

class FunnelStepData(TypedDict):
    """Single step in funnel response."""
    count: int
    step: int
    event: NotRequired[str]
    goal: NotRequired[str]  # Legacy field name
    name: NotRequired[str]
```

Source: [mixpanel-http-api-specification.md](../mixpanel-http-api-specification.md) lines 287-298

### Retention Response
```python
class RetentionAPIResponse(TypedDict):
    """Response from GET /retention endpoint.

    Note: Response is keyed by date, not wrapped in 'data'.
    """
    # Actually: dict[str, RetentionCohortData] at top level
    # But TypedDict can't express this - use type alias instead

# Type alias for retention (can't use TypedDict for dynamic keys)
RetentionAPIResponse = dict[str, "RetentionCohortData"]

class RetentionCohortData(TypedDict):
    """Single cohort's retention data."""
    first: int  # Cohort size
    counts: list[int]  # Return counts by period
    percents: NotRequired[list[float]]  # Pre-calculated percentages
```

Source: [mixpanel-http-api-specification.md](../mixpanel-http-api-specification.md) lines 337-347

### Cohorts List Response
```python
class CohortListItem(TypedDict):
    """Single cohort in list response."""
    id: int
    name: str
    count: int
    description: str
    created: str  # Datetime string
    is_visible: bool
```

### Events Export Response (JSONL)
```python
class ExportedEvent(TypedDict):
    """Single event from /export endpoint."""
    event: str
    properties: ExportedEventProperties

class ExportedEventProperties(TypedDict, total=False):
    """Event properties with known and dynamic fields."""
    distinct_id: str
    time: int  # Unix timestamp
    # All other properties are dynamic - use total=False
```

### Events Query Response
```python
class EventCountsAPIResponse(TypedDict):
    """Response from GET /events endpoint."""
    data: EventCountsData
    legend_size: int

class EventCountsData(TypedDict):
    """Nested data in events response."""
    series: list[str]  # Date strings
    values: dict[str, dict[str, int]]  # {event: {date: count}}

class TopEventsAPIResponse(TypedDict):
    """Response from GET /events/top endpoint."""
    events: list[TopEventItem]
    type: str

class TopEventItem(TypedDict):
    """Single event in top events response."""
    event: str
    amount: int
    percent_change: NotRequired[float]
```

## Test-Driven Development Plan

### Phase 1: Create TypedDict Module with Tests

#### Task 1.1: Write type definition tests
**File**: `tests/unit/test_api_types.py`

```python
"""Tests for TypedDict API response types.

These tests verify that:
1. TypedDict definitions match actual API response shapes
2. Type narrowing works correctly with TypeGuard functions
3. Optional fields are handled properly
"""

class TestSegmentationTypes:
    def test_segmentation_response_structure(self) -> None:
        """SegmentationAPIResponse should match API spec."""
        response: SegmentationAPIResponse = {
            "data": {
                "series": ["2024-01-01", "2024-01-02"],
                "values": {"Login": {"2024-01-01": 100, "2024-01-02": 150}},
            },
            "legend_size": 1,
        }
        # Type checker validates structure
        assert response["data"]["series"] == ["2024-01-01", "2024-01-02"]

    def test_segmentation_response_optional_legend_size(self) -> None:
        """legend_size should be optional."""
        response: SegmentationAPIResponse = {
            "data": {
                "series": [],
                "values": {},
            },
        }
        assert "legend_size" not in response
```

Test patterns for each type:
- Valid complete response
- Valid minimal response (optional fields omitted)
- Type narrowing with TypeGuard (if needed)

#### Task 1.2: Implement TypedDict definitions
**File**: `src/mixpanel_data/_internal/api_types.py`

Implement all TypedDict classes. Run `mypy --strict` to validate.

### Phase 2: Add TypeGuard Functions

#### Task 2.1: Write TypeGuard tests
```python
class TestTypeGuards:
    def test_is_segmentation_response_valid(self) -> None:
        """is_segmentation_response should return True for valid responses."""
        valid: dict[str, Any] = {
            "data": {"series": [], "values": {}},
        }
        assert is_segmentation_response(valid)

    def test_is_segmentation_response_invalid_missing_data(self) -> None:
        """is_segmentation_response should return False if data missing."""
        invalid: dict[str, Any] = {"legend_size": 1}
        assert not is_segmentation_response(invalid)
```

#### Task 2.2: Implement TypeGuard functions
```python
from typing import TypeGuard

def is_segmentation_response(obj: dict[str, Any]) -> TypeGuard[SegmentationAPIResponse]:
    """Check if dict matches SegmentationAPIResponse structure."""
    if not isinstance(obj, dict):
        return False
    if "data" not in obj:
        return False
    data = obj["data"]
    if not isinstance(data, dict):
        return False
    if "series" not in data or "values" not in data:
        return False
    return True
```

### Phase 3: Integrate with Transform Functions

#### Task 3.1: Update transform function tests
**File**: `tests/unit/test_live_query.py`

Add tests verifying typed parsing:
```python
class TestTypedTransforms:
    def test_transform_segmentation_with_typed_response(self) -> None:
        """_transform_segmentation should work with typed response."""
        raw: SegmentationAPIResponse = {
            "data": {
                "series": ["2024-01-01"],
                "values": {"Login": {"2024-01-01": 100}},
            },
        }
        result = _transform_segmentation(
            raw, "Login", "2024-01-01", "2024-01-01", "day", None
        )
        assert result.total == 100
```

#### Task 3.2: Update transform function signatures
**File**: `src/mixpanel_data/_internal/services/live_query.py`

```python
# Before
def _transform_segmentation(
    raw: dict[str, Any],
    ...
) -> SegmentationResult:

# After
def _transform_segmentation(
    raw: SegmentationAPIResponse,
    ...
) -> SegmentationResult:
```

### Phase 4: Property-Based Tests

#### Task 4.1: Write PBT for TypedDict validation
**File**: `tests/unit/test_api_types_pbt.py`

```python
from hypothesis import given, strategies as st

class TestSegmentationTypesPBT:
    @given(
        series=st.lists(st.dates().map(lambda d: d.isoformat())),
        values=st.dictionaries(
            st.text(min_size=1, max_size=50),
            st.dictionaries(
                st.dates().map(lambda d: d.isoformat()),
                st.integers(min_value=0),
            ),
        ),
    )
    def test_segmentation_response_roundtrip(
        self, series: list[str], values: dict[str, dict[str, int]]
    ) -> None:
        """Generated SegmentationAPIResponse should parse correctly."""
        response: SegmentationAPIResponse = {
            "data": {"series": series, "values": values},
        }
        result = _transform_segmentation(
            response, "test", "2024-01-01", "2024-01-31", "day", None
        )
        expected_total = sum(
            count for segment in values.values() for count in segment.values()
        )
        assert result.total == expected_total
```

## Implementation Order

| Phase | Task | Test File | Implementation File | Estimated Tests |
|-------|------|-----------|---------------------|-----------------|
| 1.1 | Segmentation types | `test_api_types.py` | `api_types.py` | 4 |
| 1.2 | Funnel types | `test_api_types.py` | `api_types.py` | 4 |
| 1.3 | Retention types | `test_api_types.py` | `api_types.py` | 3 |
| 1.4 | Cohorts types | `test_api_types.py` | `api_types.py` | 2 |
| 1.5 | Events export types | `test_api_types.py` | `api_types.py` | 3 |
| 1.6 | Events query types | `test_api_types.py` | `api_types.py` | 4 |
| 2.1 | TypeGuard functions | `test_api_types.py` | `api_types.py` | 6 |
| 3.1 | Transform integration | `test_live_query.py` | `live_query.py` | 8 |
| 4.1 | Property-based tests | `test_api_types_pbt.py` | - | 6 |

**Total estimated tests**: ~40

## Verification Checklist

- [ ] All TypedDict definitions match documented API responses
- [ ] `mypy --strict` passes on all new code
- [ ] Existing tests continue to pass
- [ ] New type-specific tests cover valid/invalid cases
- [ ] Property-based tests verify transform invariants
- [ ] `ruff check` and `ruff format` pass
- [ ] Coverage remains above 90%

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| API response differs from documentation | TypeGuard functions provide runtime validation; tests use real response shapes from existing tests |
| Recursive types cause mypy issues | Keep nesting shallow; use type aliases for complex cases |
| Maintenance burden when API changes | TypedDicts are internal; changes are localized to one file |
| Performance impact of type checking | TypedDicts are zero-cost at runtime (just dicts) |

## Success Criteria

1. **Type Safety**: `mypy --strict` catches incorrect field access in transform functions
2. **IDE Support**: Autocomplete works for response fields in VS Code/PyCharm
3. **Documentation**: New developers can understand API response shapes without external docs
4. **Maintainability**: Adding new endpoint types follows established patterns
5. **No Regressions**: All existing tests pass; coverage maintained

## Future Work

- Extend to API client method return types (Phase 2)
- Add TypedDict for request parameters
- Consider Pydantic models for runtime validation (if needed)
- Generate TypedDicts from OpenAPI spec (if Mixpanel provides one)
