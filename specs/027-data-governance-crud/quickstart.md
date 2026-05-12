# Quickstart: Data Governance CRUD

**Feature**: 027-data-governance-crud | **Date**: 2026-04-01

## Library Usage

### Event & Property Definitions

```python
import mixpanel_data as mp

ws = mp.Workspace()

# Get event definitions
defs = ws.get_event_definitions(names=["Purchase", "Signup"])

# Update an event definition
from mixpanel_data.types import UpdateEventDefinitionParams
ws.update_event_definition("Purchase", UpdateEventDefinitionParams(
    description="User completed a purchase",
    verified=True,
    tags=["core-metrics", "revenue"],
))

# Delete an event definition
ws.delete_event_definition("debug_test_event")

# Bulk update events
from mixpanel_data.types import BulkUpdateEventsParams, BulkEventUpdate
ws.bulk_update_event_definitions(BulkUpdateEventsParams(
    events=[
        BulkEventUpdate(name="OldEvent1", hidden=True),
        BulkEventUpdate(name="OldEvent2", hidden=True),
    ]
))

# Get property definitions
props = ws.get_property_definitions(names=["$browser"], resource_type="event")

# View tracking metadata and history
meta = ws.get_tracking_metadata("Purchase")
history = ws.get_event_history("Purchase")

# Export full lexicon
export = ws.export_lexicon(export_types=["events", "properties"])
```

### Lexicon Tags

```python
tags = ws.list_lexicon_tags()

from mixpanel_data.types import CreateTagParams
tag = ws.create_lexicon_tag(CreateTagParams(name="core-metrics"))

from mixpanel_data.types import UpdateTagParams
ws.update_lexicon_tag(tag.id, UpdateTagParams(name="key-metrics"))

ws.delete_lexicon_tag("key-metrics")
```

### Drop Filters

```python
filters = ws.list_drop_filters()
limits = ws.get_drop_filter_limits()

from mixpanel_data.types import CreateDropFilterParams
ws.create_drop_filter(CreateDropFilterParams(
    event_name="debug_log",
    filters={"property": "env", "operator": "equals", "value": "test"},
))

from mixpanel_data.types import UpdateDropFilterParams
ws.update_drop_filter(UpdateDropFilterParams(id=123, active=False))

ws.delete_drop_filter(123)
```

### Custom Properties

```python
props = ws.list_custom_properties()
prop = ws.get_custom_property("abc123")

from mixpanel_data.types import CreateCustomPropertyParams
# Validate before creating
result = ws.validate_custom_property(CreateCustomPropertyParams(
    name="Revenue Per User",
    resource_type="events",
    display_formula='number(properties["amount"])',
    composed_properties={"amount": {"resource_type": "event"}},
))

# Create the property
prop = ws.create_custom_property(CreateCustomPropertyParams(
    name="Revenue Per User",
    resource_type="events",
    display_formula='number(properties["amount"])',
    composed_properties={"amount": {"resource_type": "event"}},
))

ws.delete_custom_property("abc123")
```

### Lookup Tables

```python
tables = ws.list_lookup_tables()

from mixpanel_data.types import UploadLookupTableParams
# Upload a CSV file (3-step process handled automatically)
table = ws.upload_lookup_table(UploadLookupTableParams(
    name="Product Catalog",
    file_path="/path/to/products.csv",
))

# Download a lookup table
csv_bytes = ws.download_lookup_table(data_group_id=42)

# Get a download URL
url = ws.get_lookup_download_url(data_group_id=42)

# Delete
ws.delete_lookup_tables(data_group_ids=[42])
```

## CLI Usage

```bash
# Event definitions
mp lexicon events get --names Purchase,Signup
mp lexicon events update --name Purchase --verified --tags core-metrics,revenue
mp lexicon events delete --name debug_test_event

# Tags
mp lexicon tags list
mp lexicon tags create --name core-metrics
mp lexicon tags delete --name old-tag

# Drop filters
mp drop-filters list --format table
mp drop-filters create --event-name debug_log --filters '{"property": "env", "operator": "equals", "value": "test"}'
mp drop-filters limits

# Custom properties
mp custom-properties list --format table
mp custom-properties validate --name "Revenue" --resource-type events --display-formula 'number(properties["amount"])'
mp custom-properties create --name "Revenue" --resource-type events --display-formula 'number(properties["amount"])'

# Lookup tables
mp lookup-tables list
mp lookup-tables upload --name "Product Catalog" --file products.csv
mp lookup-tables download --data-group-id 42 --output products_backup.csv
mp lookup-tables delete --data-group-ids 42

# Export full lexicon
mp lexicon export --types events,properties --format json > lexicon_backup.json
```
