# Data Model: Schema Registry & Data Governance

**Feature**: 028-schema-governance | **Date**: 2026-04-02

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Schema Registry (Domain 14)                  │
│                                                                  │
│  SchemaEntry ─── entity_type, name, version, schema_json         │
│  BulkCreateSchemasParams ─── truncate, entity_type, entries[]    │
│  BulkCreateSchemasResponse ─── added, deleted                    │
│  BulkPatchResult ─── entity_type, name, status, error            │
│  DeleteSchemasResponse ─── delete_count                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              Schema Enforcement (Domain 15)                      │
│                                                                  │
│  SchemaEnforcementConfig ─── id, rule_event, state,              │
│      notification_emails[], events[], common_properties[],       │
│      user_properties[], initialized_by, initialized_from/to      │
│  InitSchemaEnforcementParams ─── rule_event                      │
│  UpdateSchemaEnforcementParams ─── notification_emails,           │
│      rule_event, events, properties                              │
│  ReplaceSchemaEnforcementParams ─── common_properties,           │
│      user_properties, events, rule_event, notification_emails    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Data Audit (Domain 15)                         │
│                                                                  │
│  AuditResponse ─── violations[], computed_at                     │
│  AuditViolation ─── violation, name, platform, version,          │
│      count, event, sensitive, property_type_error                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│               Data Volume Anomalies (Domain 15)                  │
│                                                                  │
│  DataVolumeAnomaly ─── id, timestamp, actual_count,              │
│      predicted_upper/lower, percent_variance, status, project,   │
│      event, event_name, property, property_name, metric,         │
│      metric_name, metric_type, primary_type, drift_types,        │
│      anomaly_class                                               │
│  UpdateAnomalyParams ─── id, status, anomaly_class               │
│  BulkUpdateAnomalyParams ─── anomalies[], status                 │
│  BulkAnomalyEntry ─── id, anomaly_class                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              Event Deletion Requests (Domain 15)                 │
│                                                                  │
│  EventDeletionRequest ─── id, display_name, event_name,          │
│      from_date, to_date, filters, status, deleted_events_count,  │
│      created, requesting_user                                    │
│  CreateDeletionRequestParams ─── from_date, to_date,             │
│      event_name, filters                                         │
│  PreviewDeletionFiltersParams ─── event_name, from_date,         │
│      to_date, filters                                            │
└─────────────────────────────────────────────────────────────────┘
```

## Detailed Entity Definitions

### Schema Registry Types

#### SchemaEntry (Response Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| entity_type | str | Yes | Entity type: "event", "custom_event", "profile" |
| name | str | Yes | Entity name (event name or "$user" for profile) |
| version | str or None | No | Schema version in YYYY-MM-DD format |
| schema_json | dict[str, Any] | Yes | JSON Schema Draft 7 definition |

**Alias**: camelCase (`entityType`, `schemaJson`)

#### BulkCreateSchemasParams (Request Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| truncate | bool or None | No | If true, delete all existing schemas of entity_type before inserting |
| entity_type | str or None | No | Entity type for all entries (only "event" supported for batch) |
| entries | list[SchemaEntry] | Yes | Schema entries to create |

#### BulkCreateSchemasResponse (Response Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| added | int | Yes | Number of schemas added |
| deleted | int | Yes | Number of schemas deleted (from truncate) |

#### BulkPatchResult (Response Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| entity_type | str | Yes | Entity type processed |
| name | str | Yes | Entity name processed |
| status | str | Yes | "ok" or "error" |
| error | str or None | No | Error message if status is "error" |

**Alias**: camelCase (`entityType`)

#### DeleteSchemasResponse (Response Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| delete_count | int | Yes | Number of schemas deleted |

---

### Schema Enforcement Types

#### SchemaEnforcementConfig (Response Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int or None | No | Config ID |
| last_modified | str or None | No | Last modification timestamp |
| last_modified_by | dict[str, Any] or None | No | User who last modified |
| rule_event | str or None | No | Enforcement action: "Warn and Accept", "Warn and Hide", "Warn and Drop" |
| notification_emails | list[str] or None | No | Notification recipients |
| events | list[dict[str, Any]] or None | No | Event enforcement rules |
| common_properties | list[dict[str, Any]] or None | No | Common property rules |
| user_properties | list[dict[str, Any]] or None | No | User property rules |
| initialized_by | dict[str, Any] or None | No | User who initialized |
| initialized_from | str or None | No | Initialization start date |
| initialized_to | str or None | No | Initialization end date |
| state | str or None | No | "planned" or "ingested" |

**Alias**: camelCase. **Extra**: `extra="allow"` for forward compatibility.

#### InitSchemaEnforcementParams (Request Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| rule_event | str | Yes | Enforcement action |

**Alias**: camelCase (`ruleEvent`)

#### UpdateSchemaEnforcementParams (Request Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| notification_emails | list[str] or None | No | Updated notification recipients |
| rule_event | str or None | No | Updated enforcement action |
| events | list[str] or None | No | Updated event list |
| properties | dict[str, list[str]] or None | No | Updated property map |

**Alias**: camelCase

#### ReplaceSchemaEnforcementParams (Request Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| common_properties | list[dict[str, Any]] | Yes | Full common property rules |
| user_properties | list[dict[str, Any]] | Yes | Full user property rules |
| events | list[dict[str, Any]] | Yes | Full event rules |
| rule_event | str | Yes | Enforcement action |
| notification_emails | list[str] | Yes | Notification recipients |
| schema_id | int or None | No | Schema definition ID |

**Alias**: camelCase

---

### Audit Types

#### AuditResponse (Response Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| violations | list[AuditViolation] | Yes | List of audit violations |
| computed_at | str | Yes | Timestamp of audit computation |

#### AuditViolation (Response Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| violation | str | Yes | Violation type (see below) |
| name | str | Yes | Property or event name |
| platform | str or None | No | Platform: "iOS", "Android", "Web" |
| version | str or None | No | Version string |
| count | int | Yes | Number of occurrences |
| event | str or None | No | Event name (for property violations) |
| sensitive | bool or None | No | Whether property is marked sensitive |
| property_type_error | str or None | No | Type mismatch description |

**Alias**: camelCase (`propertyTypeError`)

**Violation types**: "Unexpected Type for Property", "Property Length Too Long", "Missing Property", "Unexpected Event", "Unexpected Property"

---

### Anomaly Types

#### DataVolumeAnomaly (Response Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | Yes | Anomaly ID |
| timestamp | str or None | No | Detection timestamp |
| actual_count | int | Yes | Actual observed count |
| predicted_upper | int | Yes | Upper bound of prediction |
| predicted_lower | int | Yes | Lower bound of prediction |
| percent_variance | str | Yes | Variance percentage |
| status | str | Yes | "open" or "dismissed" |
| project | int | Yes | Project ID |
| event | int or None | No | Event ID |
| event_name | str or None | No | Event name |
| property | int or None | No | Property ID |
| property_name | str or None | No | Property name |
| metric | int or None | No | Metric ID |
| metric_name | str or None | No | Metric name |
| metric_type | str or None | No | Metric type |
| primary_type | str or None | No | Primary anomaly type |
| drift_types | dict[str, Any] or None | No | Drift type details |
| anomaly_class | str | Yes | "Event", "Property", "PropertyTypeDrift", "Metric" |

#### UpdateAnomalyParams (Request Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | Yes | Anomaly ID |
| status | str | Yes | New status: "open" or "dismissed" |
| anomaly_class | str | Yes | Anomaly class |

#### BulkUpdateAnomalyParams (Request Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| anomalies | list[BulkAnomalyEntry] | Yes | Anomalies to update |
| status | str | Yes | New status for all |

#### BulkAnomalyEntry (Request Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | Yes | Anomaly ID |
| anomaly_class | str | Yes | Anomaly class |

**Alias**: camelCase (`anomalyClass`)

---

### Deletion Request Types

#### EventDeletionRequest (Response Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | Yes | Request ID |
| display_name | str or None | No | Display name |
| event_name | str | Yes | Event to delete |
| from_date | str | Yes | Start date |
| to_date | str | Yes | End date |
| filters | dict[str, Any] or None | No | Deletion filters |
| status | str | Yes | "Submitted", "Processing", "Completed", "Failed" |
| deleted_events_count | int | Yes | Count of deleted events |
| created | str | Yes | Creation timestamp |
| requesting_user | dict[str, Any] | Yes | User who requested |

#### CreateDeletionRequestParams (Request Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| from_date | str | Yes | Start date (YYYY-MM-DD or datetime) |
| to_date | str | Yes | End date |
| event_name | str | Yes | Event name to delete |
| filters | dict[str, Any] or None | No | Optional filters |

#### PreviewDeletionFiltersParams (Request Model)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| event_name | str | Yes | Event name |
| from_date | str | Yes | Start date |
| to_date | str | Yes | End date |
| filters | dict[str, Any] or None | No | Optional filters |

---

## Validation Rules (from Django Reference)

### Schema Registry
- Schema JSON must be valid JSON Schema Draft 7
- Max 2000 properties per event
- Entity type must be "event", "custom_event", or "profile"
- For profile type, name must be "$user"
- Batch truncate: max 3000 entities per request

### Enforcement
- `rule_event` must be one of: "Warn and Accept", "Warn and Hide", "Warn and Drop"

### Event Deletion
- Time window: max 180 days in the past
- Max 10 requests per month
- Max 5 billion events per month
- `from_date` must be before `to_date`
- Must match at least 1 event

### Anomalies
- Status must be "open" or "dismissed"
- Anomaly class must be "Event", "Property", "PropertyTypeDrift", or "Metric"
