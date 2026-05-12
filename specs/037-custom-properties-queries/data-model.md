# Data Model: Custom Properties in Queries

**Feature**: 037-custom-properties-queries
**Date**: 2026-04-07

## Entities

### PropertyInput

A raw property reference mapping a formula variable to a named event or user property.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | (required) | The raw property name (e.g., `"price"`, `"$browser"`) |
| `type` | `Literal["string", "number", "boolean", "datetime", "list"]` | `"string"` | Property data type |
| `resource_type` | `Literal["event", "user"]` | `"event"` | Property domain |

**Immutable**: Yes (frozen dataclass)

**Bookmark JSON mapping**:
```
PropertyInput.name          → composedProperties[letter].value
PropertyInput.type          → composedProperties[letter].type
PropertyInput.resource_type → composedProperties[letter].resourceType
```

### InlineCustomProperty

An ephemeral computed property defined by a formula and input property references.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `formula` | `str` | (required) | Expression in arb-selector formula language (max 20,000 chars) |
| `inputs` | `dict[str, PropertyInput]` | (required) | Mapping from single uppercase letters (A-Z) to property references |
| `property_type` | `Literal["string", "number", "boolean", "datetime"] \| None` | `None` | Result type of the formula; `None` defers to containing type |
| `resource_type` | `Literal["events", "people"]` | `"events"` | Data domain |

**Immutable**: Yes (frozen dataclass)

**Convenience constructor**: `InlineCustomProperty.numeric(formula, **properties)` — creates an all-numeric-input inline custom property. All inputs are typed as `"number"` with `resource_type="event"`, and `property_type` is set to `"number"`.

**Bookmark JSON mapping** (in filter, group-by, or measurement):
```json
{
    "customProperty": {
        "displayFormula": "<formula>",
        "composedProperties": {
            "<letter>": {"value": "<name>", "type": "<type>", "resourceType": "<resource_type>"}
        },
        "propertyType": "<property_type or fallback>",
        "resourceType": "<resource_type>"
    }
}
```

### CustomPropertyRef

A reference to a persisted custom property by its integer ID.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `int` | (required) | The custom property's ID (must be positive) |

**Immutable**: Yes (frozen dataclass)

**Bookmark JSON mapping** (in filter, group-by, or measurement):
```json
{
    "customPropertyId": 42
}
```

### PropertySpec (type alias)

```
PropertySpec = str | CustomPropertyRef | InlineCustomProperty
```

Used as the accepted type for `property` fields in `Metric`, `GroupBy`, and `Filter`.

## Modified Entities

### Metric (widened)

| Field | Before | After |
|-------|--------|-------|
| `property` | `str \| None` | `str \| CustomPropertyRef \| InlineCustomProperty \| None` |

### GroupBy (widened)

| Field | Before | After |
|-------|--------|-------|
| `property` | `str` | `str \| CustomPropertyRef \| InlineCustomProperty` |

### Filter (widened)

| Field | Before | After |
|-------|--------|-------|
| `_property` | `str` | `str \| CustomPropertyRef \| InlineCustomProperty` |
| All 18 class methods `property` param | `str` | `str \| CustomPropertyRef \| InlineCustomProperty` |

## Validation Rules

| Code | Entity | Rule | Severity |
|------|--------|------|----------|
| CP1 | `CustomPropertyRef` | `id` must be a positive integer | error |
| CP2 | `InlineCustomProperty` | `formula` must be non-empty (after stripping whitespace) | error |
| CP3 | `InlineCustomProperty` | `inputs` must have at least one entry | error |
| CP4 | `InlineCustomProperty` | `inputs` keys must be single uppercase letters A-Z | error |
| CP5 | `InlineCustomProperty` | `formula` must not exceed 20,000 characters | error |
| CP6 | `InlineCustomProperty` | Each `PropertyInput.name` must be non-empty (after stripping whitespace) | error |

**Enforcement location**: `_validate_custom_property()` in `validation.py`, called from `validate_query_args()`, `validate_funnel_args()`, and `validate_retention_args()`.

## Bookmark JSON Output by Position

### Filter position

**Plain string** (unchanged):
```json
{"resourceType": "events", "filterType": "number", "defaultType": "number", "value": "amount", "filterValue": 100, "filterOperator": "is greater than"}
```

**CustomPropertyRef**:
```json
{"customPropertyId": 42, "resourceType": "events", "filterType": "number", "defaultType": "number", "filterValue": 100, "filterOperator": "is greater than"}
```

**InlineCustomProperty**:
```json
{"customProperty": {"displayFormula": "A * B", "composedProperties": {"A": {"value": "price", "type": "number", "resourceType": "event"}, "B": {"value": "quantity", "type": "number", "resourceType": "event"}}, "propertyType": "number", "resourceType": "events"}, "resourceType": "events", "filterType": "number", "defaultType": "number", "filterValue": 100, "filterOperator": "is greater than"}
```

### Group-by position

**Plain string** (unchanged):
```json
{"value": "country", "propertyName": "country", "resourceType": "events", "propertyType": "string", "propertyDefaultType": "string"}
```

**CustomPropertyRef**:
```json
{"customPropertyId": 42, "propertyType": "number", "propertyDefaultType": "number", "isHidden": false}
```

**InlineCustomProperty**:
```json
{"customProperty": {"displayFormula": "A * B", "composedProperties": {"A": {"value": "price", "type": "number", "resourceType": "event"}, "B": {"value": "quantity", "type": "number", "resourceType": "event"}}, "propertyType": "number", "resourceType": "events"}, "propertyType": "number", "propertyDefaultType": "number", "isHidden": false}
```

### Measurement position

**Plain string** (unchanged):
```json
{"math": "average", "property": {"name": "amount", "resourceType": "events"}}
```

**CustomPropertyRef**:
```json
{"math": "average", "property": {"customPropertyId": 42, "name": "", "resourceType": "events"}}
```

**InlineCustomProperty**:
```json
{"math": "average", "property": {"customProperty": {"displayFormula": "A * B", "composedProperties": {"A": {"value": "price", "type": "number", "resourceType": "event"}, "B": {"value": "quantity", "type": "number", "resourceType": "event"}}, "name": "", "description": "", "propertyType": "number", "resourceType": "events"}, "name": "", "resourceType": "events", "dataset": "$mixpanel", "dataGroupId": null}}
```
