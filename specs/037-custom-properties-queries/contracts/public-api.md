# Public API Contract: Custom Properties in Queries

**Feature**: 037-custom-properties-queries
**Date**: 2026-04-07

## New Types (exported from `mixpanel_data`)

### PropertyInput

```python
@dataclass(frozen=True)
class PropertyInput:
    name: str
    type: Literal["string", "number", "boolean", "datetime", "list"] = "string"
    resource_type: Literal["event", "user"] = "event"
```

### InlineCustomProperty

```python
@dataclass(frozen=True)
class InlineCustomProperty:
    formula: str
    inputs: dict[str, PropertyInput]
    property_type: Literal["string", "number", "boolean", "datetime"] | None = None
    resource_type: Literal["events", "people"] = "events"

    @classmethod
    def numeric(cls, formula: str, /, **properties: str) -> InlineCustomProperty: ...
```

### CustomPropertyRef

```python
@dataclass(frozen=True)
class CustomPropertyRef:
    id: int
```

### PropertySpec (type alias)

```python
PropertySpec = str | CustomPropertyRef | InlineCustomProperty
```

## Modified Signatures

### Metric.property

```python
# Before
property: str | None = None

# After
property: str | CustomPropertyRef | InlineCustomProperty | None = None
```

### GroupBy.property

```python
# Before
property: str

# After
property: str | CustomPropertyRef | InlineCustomProperty
```

### Filter._property (internal) + all 18 class methods

```python
# Before (example: Filter.equals)
@classmethod
def equals(cls, property: str, value: str | list[str], *, resource_type: ...) -> Filter: ...

# After
@classmethod
def equals(cls, property: str | CustomPropertyRef | InlineCustomProperty, value: str | list[str], *, resource_type: ...) -> Filter: ...
```

All 18 class methods: `equals`, `not_equals`, `contains`, `not_contains`, `greater_than`, `less_than`, `between`, `is_set`, `is_not_set`, `is_true`, `is_false`, `on`, `not_on`, `before`, `since`, `in_the_last`, `not_in_the_last`, `date_between`.

## Unchanged Method Signatures

The following query methods accept custom properties through their existing parameters (no signature changes needed):

- `Workspace.query(events=..., group_by=..., where=...)` — events accepts `Metric` (whose `property` is widened), group_by accepts `GroupBy` (whose `property` is widened), where accepts `Filter` (whose `_property` is widened)
- `Workspace.query_funnel(steps=..., group_by=..., where=...)` — same pattern
- `Workspace.query_retention(born_event=..., return_event=..., group_by=..., where=...)` — same pattern
- `Workspace.build_params(...)`, `Workspace.build_funnel_params(...)`, `Workspace.build_retention_params(...)` — same pattern

## Backward Compatibility

All changes are **additive union extensions**:

- `str` remains a valid type for all property fields
- No method signatures are removed or narrowed
- No default values change
- No required parameters are added
- Existing code calling any of these methods with string properties continues to work identically

## Error Contract

| Condition | Error Type | Message Pattern |
|-----------|-----------|----------------|
| `CustomPropertyRef(id=0)` or negative | `BookmarkValidationError` | "custom property ID must be a positive integer (got {id})" |
| `InlineCustomProperty(formula="")` | `BookmarkValidationError` | "inline custom property formula must be non-empty" |
| `InlineCustomProperty(inputs={})` | `BookmarkValidationError` | "inline custom property must have at least one input" |
| `InlineCustomProperty(inputs={"ab": ...})` | `BookmarkValidationError` | "inline custom property input keys must be single uppercase letters (A-Z), got 'ab'" |
| Formula > 20,000 chars | `BookmarkValidationError` | "inline custom property formula exceeds maximum length of 20,000 characters (got {len})" |
| `PropertyInput(name="")` in inputs | `BookmarkValidationError` | "inline custom property input '{key}' has an empty property name" |

## Engine Compatibility

| Feature | Insights | Funnels | Retention | Flows |
|---------|----------|---------|-----------|-------|
| Custom property in group_by | Yes | Yes | Yes | No (out of scope) |
| Custom property in where | Yes | Yes | Yes | No (out of scope) |
| Custom property in Metric.property | Yes | Yes | N/A | N/A |
