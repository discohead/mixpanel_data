# Research: Phase 1 — Shared Infrastructure Extraction

**Date**: 2026-04-05
**Status**: Complete

## R1: Segfilter Format — Operator Mapping

**Decision**: Map bookmark filter operators to segfilter symbolic operators using the canonical TypeScript reference.

**Rationale**: The TypeScript reference at `analytics/iron/common/widgets/property-filter-menu/models/segfilter.ts` defines the authoritative bidirectional mapping with round-trip test coverage. The existing Python attempt at `mixpanel_mcp/mcp_server/utils/reports/flows.py` has known bugs (wrong `"is set"`, wrong `"contains"`, no type-aware operand shaping).

### Complete Operator Mapping (PropertyFilter → Segfilter)

#### String Operators (`STRING_OPERATOR_MAP`)

| Bookmark `filterOperator` | Segfilter `filter.operator` | Segfilter `filter.operand` |
|---|---|---|
| `"equals"` | `"=="` | `["value1", "value2"]` (array) |
| `"does not equal"` | `"!="` | `["value1", "value2"]` (array) |
| `"contains"` | `"in"` | `"substring"` (string, not array) |
| `"does not contain"` | `"not in"` | `"substring"` (string, not array) |
| `"is set"` | `"set"` | `""` (empty string) |
| `"is not set"` | `"not set"` | `""` (empty string) |

#### Number Operators (`NUMBER_OPERATOR_MAP`)

| Bookmark `filterOperator` | Segfilter `filter.operator` | Segfilter `filter.operand` |
|---|---|---|
| `"is equal to"` / `"equals"` | `"=="` | `"50"` (stringified) |
| `"does not equal"` | `"!="` | `"50"` (stringified) |
| `"is greater than"` | `">"` | `"50"` (stringified) |
| `"is less than"` | `"<"` | `"50"` (stringified) |
| `"is at least"` | `">="` | `"50"` (stringified) |
| `"is at most"` | `"<="` | `"50"` (stringified) |
| `"is between"` / `"between"` | `"><"` | `["10", "50"]` (stringified array) |
| `"not between"` | `"!><"` | `["10", "50"]` (stringified array) |
| `"is set"` | `"is set"` | `""` (empty string) |
| `"is not set"` | `"is not set"` | `""` (empty string) |

**Note**: Number `"is set"` / `"is not set"` use the literal words, while string `"is set"` / `"is not set"` use `"set"` / `"not set"` (no "is" prefix). This is the canonical format — not a bug.

#### Boolean Operators

| Bookmark `filterOperator` | Segfilter `filter.operator` | Segfilter `filter.operand` |
|---|---|---|
| `"true"` | *(omitted — no operator field)* | `"true"` |
| `"false"` | *(omitted — no operator field)* | `"false"` |

#### Datetime Operators (`DATETIME_OPERATOR_MAP`)

| Bookmark `filterOperator` | Segfilter `filter.operator` | Segfilter `filter.operand` | Extra |
|---|---|---|---|
| `"on"` | `"=="` | `"MM/DD/YYYY"` | — |
| `"not on"` | `"!="` | `"MM/DD/YYYY"` | — |
| `"before"` | `">"` | `"MM/DD/YYYY"` | — |
| `"since"` | `"<"` | `"MM/DD/YYYY"` | — |
| `"in the last"` | `">"` | window value (int) | `unit: "days"` |
| `"not in the last"` | `">"` | window value (int) | `unit: "days"` |
| `"between"` / `"was between"` | `"><"` | `["MM/DD/YYYY", "MM/DD/YYYY"]` | — |
| `"not between"` / `"was not between"` | `"!><"` | `["MM/DD/YYYY", "MM/DD/YYYY"]` | — |

**Date format conversion**: `YYYY-MM-DD` (bookmark) → `MM/DD/YYYY` (segfilter).

**Time unit conversion**: `"day"` → `"days"`, `"hour"` → `"hours"`, `"week"` → `"weeks"`, `"month"` → `"months"`, `"minute"` → `"minutes"`.

**Alternatives considered**: Using the buggy `mixpanel_mcp` implementation as a starting point. Rejected because its operator mappings are incorrect (uses `"contains"` instead of `"in"` for string contains, missing type-aware operand shaping).

## R2: Segfilter Format — Property Structure

**Decision**: Map bookmark `resourceType` to segfilter `property.source` using the canonical `RESOURCE_TYPE_MAP`.

**Rationale**: Critical finding — the mapping is NOT identity. `"events"` maps to `"properties"`, not `"events"`.

### Resource Type Mapping

| Bookmark `resourceType` | Segfilter `property.source` |
|---|---|
| `"events"` | `"properties"` |
| `"people"` | `"user"` |
| `"cohorts"` | `"cohort"` |
| `"other"` | `"other"` |

### Segfilter Structure

```python
{
    "property": {
        "name": "country",        # from Filter._property
        "source": "properties",   # from RESOURCE_TYPE_MAP[Filter._resource_type]
        "type": "string",         # from Filter._property_type
    },
    "type": "string",             # Filter._property_type
    "selected_property_type": "string",  # Filter._property_type
    "filter": {
        "operator": "==",         # from operator mapping
        "operand": ["US"],        # type-aware value shaping
    },
}
```

## R3: Time Section Extraction — Approach

**Decision**: Extract inline time-building code from `workspace.py:_build_query_params()` (lines 1704-1728) into a standalone function that returns a single time entry dict.

**Rationale**: The existing code handles three cases (between with both dates, between with from_date only, relative "in the last"). These exact cases are reused by funnels and retention. Flows needs a separate builder because its date_range format is structurally different (flat dict, not `sections.time[]` entry).

**Alternatives considered**: Single unified builder returning both formats. Rejected because the two formats share no structural overlap — unifying would add conditional logic that obscures both shapes.

## R4: Validation Extraction — Approach

**Decision**: Extract time rules (V7-V10, V15, V20) and group-by rules (V11-V12, V18, V24) into separate functions called by `validate_query_args()`.

**Rationale**: These rule blocks are self-contained — they only depend on their respective parameters, not on events/math/formula parameters. The existing function is 520+ lines; extracting ~175 lines improves readability and enables reuse by `validate_funnel_args()`, `validate_retention_args()`, and `validate_flow_args()`.

**Alternatives considered**: Moving all shared validation into a base class. Rejected because the validation functions are stateless — inheritance adds complexity without benefit.

## R5: Bookmark Enums — New Constants Needed

**Decision**: Add the following new frozenset constants to `bookmark_enums.py`.

| Constant | Values | Source |
|---|---|---|
| `VALID_FUNNEL_ORDER` | `{"loose", "any"}` | Design doc section 3.1, `analytics/` funnels behavior |
| `VALID_CONVERSION_WINDOW_UNITS` | `{"second", "minute", "hour", "day", "week", "month", "session"}` | Design doc section 3.1 |
| `VALID_RETENTION_UNITS` | `{"day", "week", "month"}` | Design doc section 4.1 |
| `VALID_RETENTION_ALIGNMENT` | `{"birth", "interval_start"}` | Design doc section 4.1 |
| `VALID_FLOWS_COUNT_TYPES` | `{"unique", "total", "session"}` | Design doc section 5.2 |
| `VALID_FLOWS_CHART_TYPES` | `{"sankey", "top-paths"}` | Design doc section 5.5 |

**Existing constants verified**:
- `VALID_MATH_FUNNELS` — exists, contains `{"general", "unique", "session", "total", "conversion_rate", "conversion_rate_unique", "conversion_rate_total", "conversion_rate_session"}`. Design doc section 3.3 adds property aggregation types (`average`, `median`, `min`, `max`, `p25`, `p75`, `p90`, `p99`) — needs extension.
- `VALID_MATH_RETENTION` — exists, contains `{"unique", "retention_rate", "total", "average"}`. Matches design doc section 4.3. Complete as-is.
- `VALID_CHART_TYPES` — exists, already contains `"funnel-steps"`, `"funnel-top-paths"`, `"retention-curve"`. Complete as-is.

## R6: Filter Class — Supported Operators Inventory

**Decision**: The segfilter converter must handle the following 14 `Filter` class methods:

| Method | Bookmark Operator | Property Type |
|---|---|---|
| `Filter.equals()` | `"equals"` | `"string"` |
| `Filter.not_equals()` | `"does not equal"` | `"string"` |
| `Filter.contains()` | `"contains"` | `"string"` |
| `Filter.greater_than()` | `"is greater than"` | `"number"` |
| `Filter.less_than()` | `"is less than"` | `"number"` |
| `Filter.is_set()` | `"is set"` | `"string"` |
| `Filter.is_not_set()` | `"is not set"` | `"string"` |
| `Filter.is_true()` | `"true"` | `"boolean"` |
| `Filter.is_false()` | `"false"` | `"boolean"` |
| `Filter.on()` | `"was on"` | `"datetime"` |
| `Filter.not_on()` | `"was not on"` | `"datetime"` |
| `Filter.before()` | `"was before"` | `"datetime"` |
| `Filter.in_the_last()` | `"was in the"` | `"datetime"` |
| `Filter.not_in_the_last()` | `"was not in the"` | `"datetime"` |

`Filter.not_contains()` (operator `"does not contain"`) and `Filter.between()` (operator `"is between"`) exist on the `Filter` class and are handled by the converter. `is_at_least` and `is_at_most` methods do not exist on `Filter` — these operators appear only in legacy bookmarks. The converter handles all operators in its mapping dicts (including legacy ones) for completeness, even if some are not currently constructible via `Filter` class methods.
