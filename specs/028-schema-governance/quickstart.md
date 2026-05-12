# Quickstart: Schema Registry & Data Governance

**Feature**: 028-schema-governance | **Date**: 2026-04-02

## Python Library Usage

### Schema Registry

```python
import mixpanel_data as mp

ws = mp.Workspace()

# List all schemas
schemas = ws.list_schema_registry()

# List schemas for events only
event_schemas = ws.list_schema_registry(entity_type="event")

# Create a schema for an event
schema_def = {
    "$schema": "http://json-schema.org/draft-07/schema",
    "properties": {
        "amount": {"type": "number"},
        "currency": {"type": "string"},
    },
    "required": ["amount"],
}
ws.create_schema("event", "Purchase", schema_def)

# Bulk create schemas
from mixpanel_data.types import BulkCreateSchemasParams, SchemaEntry

params = BulkCreateSchemasParams(
    entries=[
        SchemaEntry(name="Login", entity_type="event", schema_definition={...}),
        SchemaEntry(name="Signup", entity_type="event", schema_definition={...}),
    ],
    truncate=True,  # Replace existing event schemas
    entity_type="event",
)
result = ws.create_schemas_bulk(params)
print(f"Added: {result.added}, Deleted: {result.deleted}")

# Update a schema (merge semantics)
ws.update_schema("event", "Purchase", {
    "properties": {"tax": {"type": "number"}},
})

# Bulk update
results = ws.update_schemas_bulk(params)
for r in results:
    print(f"{r.name}: {r.status}")

# Delete schemas
resp = ws.delete_schemas(entity_type="event", entity_name="Purchase")
print(f"Deleted: {resp.delete_count}")
```

### Schema Enforcement

```python
from mixpanel_data.types import (
    InitSchemaEnforcementParams,
    UpdateSchemaEnforcementParams,
    ReplaceSchemaEnforcementParams,
)

# Get current enforcement config
config = ws.get_schema_enforcement()
print(f"Rule: {config.rule_event}, State: {config.state}")

# Get specific fields only
config = ws.get_schema_enforcement(fields="ruleEvent,state")

# Initialize enforcement
ws.init_schema_enforcement(
    InitSchemaEnforcementParams(rule_event="Warn and Accept")
)

# Partially update
ws.update_schema_enforcement(
    UpdateSchemaEnforcementParams(
        notification_emails=["data-team@example.com"],
        rule_event="Warn and Drop",
    )
)

# Fully replace
ws.replace_schema_enforcement(
    ReplaceSchemaEnforcementParams(
        events=[...],
        common_properties=[...],
        user_properties=[...],
        rule_event="Warn and Hide",
        notification_emails=["admin@example.com"],
    )
)

# Delete enforcement
ws.delete_schema_enforcement()
```

### Data Auditing

```python
# Full audit (events + properties)
audit = ws.run_audit()
print(f"Computed at: {audit.computed_at}")
for v in audit.violations:
    print(f"  {v.violation}: {v.name} ({v.count} occurrences)")

# Events-only audit (faster)
audit = ws.run_audit_events_only()
```

### Data Volume Anomalies

```python
from mixpanel_data.types import UpdateAnomalyParams, BulkUpdateAnomalyParams, BulkAnomalyEntry

# List all open anomalies
anomalies = ws.list_data_volume_anomalies(query_params={"status": "open"})
for a in anomalies:
    print(f"  {a.event_name}: {a.actual_count} (expected {a.predicted_lower}-{a.predicted_upper})")

# Dismiss a single anomaly
ws.update_anomaly(UpdateAnomalyParams(id=123, status="dismissed", anomaly_class="Event"))

# Bulk dismiss
ws.bulk_update_anomalies(BulkUpdateAnomalyParams(
    anomalies=[
        BulkAnomalyEntry(id=123, anomaly_class="Event"),
        BulkAnomalyEntry(id=456, anomaly_class="Property"),
    ],
    status="dismissed",
))
```

### Event Deletion Requests

```python
from mixpanel_data.types import CreateDeletionRequestParams, PreviewDeletionFiltersParams

# Preview what would be deleted
preview = ws.preview_deletion_filters(PreviewDeletionFiltersParams(
    event_name="Test Event",
    from_date="2026-01-01",
    to_date="2026-01-31",
))

# Create a deletion request
requests = ws.create_deletion_request(CreateDeletionRequestParams(
    event_name="Test Event",
    from_date="2026-01-01",
    to_date="2026-01-31",
    filters={"property": "value"},
))

# List all deletion requests
requests = ws.list_deletion_requests()
for r in requests:
    print(f"  {r.event_name}: {r.status} ({r.deleted_events_count} events)")

# Cancel a pending request
requests = ws.cancel_deletion_request(request_id=42)
```

## CLI Usage

### Schema Registry

```bash
# List schemas
mp schemas list
mp schemas list --entity-type event --format table

# Create a single schema
mp schemas create --entity-type event --entity-name Purchase \
  --schema-json '{"properties":{"amount":{"type":"number"}}}'

# Bulk create (with truncate)
mp schemas create-bulk --truncate --entity-type event \
  --entries '[{"name":"Login","entityType":"event","schemaJson":{...}}]'

# Update a schema
mp schemas update --entity-type event --entity-name Purchase \
  --schema-json '{"properties":{"tax":{"type":"number"}}}'

# Delete
mp schemas delete --entity-type event --entity-name Purchase
```

### Schema Enforcement

```bash
# Get enforcement config
mp lexicon enforcement get
mp lexicon enforcement get --fields ruleEvent,state

# Initialize
mp lexicon enforcement init --rule-event "Warn and Accept"

# Update (partial)
mp lexicon enforcement update --body '{"ruleEvent":"Warn and Drop"}'

# Replace (full)
mp lexicon enforcement replace --body '{"events":[],"commonProperties":[],...}'

# Delete
mp lexicon enforcement delete
```

### Audit

```bash
# Full audit
mp lexicon audit --format table

# Events-only audit
mp lexicon audit --events-only
```

### Anomalies

```bash
# List open anomalies
mp lexicon anomalies list --status open --format table

# Update status
mp lexicon anomalies update --id 123 --status dismissed --anomaly-class Event

# Bulk update
mp lexicon anomalies bulk-update --body '{"anomalies":[{"id":123,"anomalyClass":"Event"}],"status":"dismissed"}'
```

### Deletion Requests

```bash
# Preview
mp lexicon deletion-requests preview --event-name "Test Event" \
  --from-date 2026-01-01 --to-date 2026-01-31

# Create
mp lexicon deletion-requests create --event-name "Test Event" \
  --from-date 2026-01-01 --to-date 2026-01-31

# List
mp lexicon deletion-requests list --format table

# Cancel
mp lexicon deletion-requests cancel 42
```
