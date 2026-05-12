# Data Model: Data Governance CRUD

**Feature**: 027-data-governance-crud | **Date**: 2026-04-01

## Entity Overview

```
┌──────────────────┐     ┌──────────────────┐
│ EventDefinition  │────▶│   LexiconTag     │
│                  │  *  │                  │
└──────────────────┘     └──────────────────┘
┌──────────────────┐
│PropertyDefinition│
│                  │
└──────────────────┘
┌──────────────────┐     ┌──────────────────┐
│   DropFilter     │     │  CustomProperty  │
│                  │     │                  │
└──────────────────┘     └──────────────────┘
┌──────────────────┐
│  LookupTable     │
│                  │
└──────────────────┘
```

## Domain 9: Data Definitions (Lexicon)

### EventDefinition

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | int | yes | Server-assigned |
| name | str | yes | Event name (unique identifier) |
| display_name | str | no | Human-readable name |
| description | str | no | |
| hidden | bool | no | Hidden from UI |
| dropped | bool | no | Data dropped at ingestion |
| merged | bool | no | Merged into another event |
| verified | bool | no | Verified by governance team |
| tags | list[str] | no | Assigned tag names |
| custom_event_id | int | no | Links to custom event |
| last_modified | str | no | ISO 8601 timestamp |
| status | str | no | |
| platforms | list[str] | no | Tracking platforms |
| created_utc | str | no | ISO 8601 timestamp |
| modified_utc | str | no | ISO 8601 timestamp |

### UpdateEventDefinitionParams

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| hidden | bool | no | |
| dropped | bool | no | |
| merged | bool | no | |
| verified | bool | no | |
| tags | list[str] | no | |
| description | str | no | |

### PropertyDefinition

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | int | yes | Server-assigned |
| name | str | yes | Property name |
| resource_type | PropertyResourceType | no | event, user, group |
| description | str | no | |
| hidden | bool | no | |
| dropped | bool | no | |
| merged | bool | no | |
| sensitive | bool | no | PII flag |
| data_group_id | str | no | |

### PropertyResourceType (Enum)

| Value | Wire Format |
|-------|-------------|
| event | "event" |
| user | "user" |
| group | "groupprofile" |

### UpdatePropertyDefinitionParams

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| hidden | bool | no | |
| dropped | bool | no | |
| merged | bool | no | |
| sensitive | bool | no | |
| description | str | no | |

### BulkUpdateEventsParams

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| events | list[BulkEventUpdate] | yes | |

### BulkEventUpdate

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | str | no | Event name (identifier) |
| id | int | no | Alternative identifier |
| hidden | bool | no | |
| dropped | bool | no | |
| merged | bool | no | |
| verified | bool | no | |
| tags | list[str] | no | |
| contacts | list[str] | no | |
| team_contacts | list[str] | no | |

### BulkUpdatePropertiesParams

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| properties | list[BulkPropertyUpdate] | yes | |

### BulkPropertyUpdate

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | str | yes | Property name |
| resource_type | PropertyResourceType | yes | |
| id | int | no | |
| hidden | bool | no | |
| dropped | bool | no | |
| sensitive | bool | no | |
| data_group_id | str | no | |

### LexiconTag

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | int | yes | Server-assigned |
| name | str | yes | Tag name |

### CreateTagParams

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | str | yes | Non-empty |

### UpdateTagParams

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | str | no | |

### TrackingMetadata

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| first_track | str | no | |
| (extra fields) | Any | no | Forward-compatible |

## Domain 10: Custom Properties

### CustomProperty

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| custom_property_id | int | yes | Server-assigned |
| name | str | yes | |
| description | str | no | |
| resource_type | CustomPropertyResourceType | yes | events, people, group_profiles |
| property_type | str | no | |
| display_formula | str | no | Formula expression |
| composed_properties | dict[str, ComposedPropertyValue] | no | Referenced properties |
| is_locked | bool | no | |
| is_visible | bool | no | |
| data_group_id | str | no | |
| created | str | no | ISO 8601 |
| modified | str | no | ISO 8601 |
| example_value | str | no | |

### CustomPropertyResourceType (Enum)

| Value | Wire Format |
|-------|-------------|
| events | "events" |
| people | "people" |
| group_profiles | "group_profiles" |

### ComposedPropertyValue

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| type | str | no | |
| type_cast | str | no | |
| resource_type | str | yes | |
| behavior | Any | no | |
| join_property_type | str | no | |

### CreateCustomPropertyParams

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | str | yes | |
| resource_type | CustomPropertyResourceType | yes | |
| description | str | no | |
| display_formula | str | no | Mutually exclusive with behavior |
| composed_properties | dict[str, ComposedPropertyValue] | no | Required if display_formula set |
| is_locked | bool | no | |
| is_visible | bool | no | |
| data_group_id | str | no | |
| behavior | Any | no | Mutually exclusive with display_formula |

**Validation rules**:
- `behavior` and `display_formula` are mutually exclusive
- `behavior` and `composed_properties` are mutually exclusive
- `display_formula` requires `composed_properties`
- One of `display_formula` or `behavior` must be set

### UpdateCustomPropertyParams

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | str | no | |
| description | str | no | |
| display_formula | str | no | |
| composed_properties | dict[str, ComposedPropertyValue] | no | |
| is_locked | bool | no | |
| is_visible | bool | no | |

Note: `resource_type` and `data_group_id` are immutable (not in update params). Uses PUT (full replacement).

## Domain 12: Drop Filters

### DropFilter

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | int | yes | Server-assigned |
| event_name | str | yes | |
| filters | list[Any] | no | Filter condition JSON |
| active | bool | no | |
| display_name | str | no | |
| created | str | no | ISO 8601 |

### CreateDropFilterParams

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| event_name | str | yes | |
| filters | Any | yes | Filter condition JSON |

### UpdateDropFilterParams

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | int | yes | |
| event_name | str | no | |
| filters | Any | no | |
| active | bool | no | |

### DropFilterLimitsResponse

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| filter_limit | int | yes | Maximum allowed filters |

## Domain 13: Lookup Tables

### LookupTable

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | int | yes | Server-assigned (may be string from API) |
| name | str | yes | |
| token | str | no | |
| created_at | str | no | ISO 8601 |
| last_modified_at | str | no | ISO 8601 |
| has_mapped_properties | bool | no | |

### UploadLookupTableParams

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | str | yes | 1-255 characters |
| file_path | str | yes | Path to local CSV file |
| data_group_id | int | no | For replacing existing table |

### MarkLookupTableReadyParams

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | str | yes | |
| key | str | yes | Primary key column name |
| data_group_id | int | no | |

### LookupTableUploadUrl

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| url | str | yes | Signed GCS upload URL |
| path | str | yes | GCS path for registration |
| key | str | yes | Primary key column name |

### UpdateLookupTableParams

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | str | no | |

## State Transitions

### Lookup Table Upload Flow

```
[No Table] → GET upload-url → [URL Obtained]
           → PUT csv to GCS → [Uploaded]
           → POST register  → [PENDING] → poll → [SUCCESS] or [FAILURE]
```

### Drop Filter Lifecycle

```
[Created (active=true)] → update(active=false) → [Inactive]
                        → delete                → [Deleted]
```

### Custom Property Lifecycle

```
[validate formula] → [Valid] → create → [Active]
                              → update → [Modified]
                              → delete → [Deleted]
```
