# Quickstart: Lexicon Schemas API

**Feature**: 012-lexicon-schemas
**Date**: 2025-12-24

---

## Python Library Usage

### List All Lexicon Schemas

```python
import mixpanel_data as mp

ws = mp.Workspace()

# Get all Lexicon schemas in the project
schemas = ws.lexicon_schemas()
for s in schemas:
    print(f"{s.entity_type}: {s.name}")
    if s.schema_json.description:
        print(f"  Description: {s.schema_json.description}")
```

### Filter by Entity Type

```python
# Get only event schemas
event_schemas = ws.lexicon_schemas(entity_type="event")

# Get only profile property schemas
profile_schemas = ws.lexicon_schemas(entity_type="profile")
```

### Get Single Schema

```python
# Get a specific schema by type and name
schema = ws.lexicon_schema("event", "Purchase")

if schema:
    print(f"Event: {schema.name}")
    print(f"Description: {schema.schema_json.description}")

    # Inspect properties
    for prop_name, prop_schema in schema.schema_json.properties.items():
        print(f"  {prop_name}: {prop_schema.type}")
        if prop_schema.description:
            print(f"    Description: {prop_schema.description}")
else:
    print("Schema not found")
```

### Access Metadata

```python
schema = ws.lexicon_schema("event", "Purchase")

if schema and schema.schema_json.metadata:
    meta = schema.schema_json.metadata
    print(f"Display Name: {meta.display_name}")
    print(f"Tags: {meta.tags}")
    print(f"Hidden: {meta.hidden}")
    print(f"Contacts: {meta.contacts}")
```

### Serialize to Dictionary

```python
schemas = ws.lexicon_schemas()
for s in schemas:
    data = s.to_dict()
    print(json.dumps(data, indent=2))
```

---

## CLI Usage

### List All Lexicon Schemas

```bash
# JSON output (default)
mp inspect lexicon

# Table format
mp inspect lexicon --format table

# CSV format
mp inspect lexicon --format csv
```

### Filter by Entity Type

```bash
# Event schemas only
mp inspect lexicon --entity-type event

# Profile schemas only
mp inspect lexicon --entity-type profile
```

### Get Single Schema

```bash
# Get specific schema
mp inspect lexicon --entity-type event --name Purchase

# JSON output with pretty formatting
mp inspect lexicon --entity-type event --name Purchase --format json
```

---

## Caching Behavior

Schema queries are cached for the duration of the session:

```python
ws = mp.Workspace()

# First call hits the API
schemas1 = ws.lexicon_schemas()

# Second call returns cached result (no API call)
schemas2 = ws.lexicon_schemas()

# Clear cache to force fresh data
ws.clear_discovery_cache()

# This call hits the API again
schemas3 = ws.lexicon_schemas()
```

---

## Error Handling

```python
from mixpanel_data.exceptions import AuthenticationError, QueryError, RateLimitError

try:
    schemas = ws.lexicon_schemas()
except AuthenticationError:
    print("Check your credentials")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except QueryError as e:
    print(f"Query failed: {e}")
```

---

## Rate Limit Considerations

The Lexicon API has a strict **5 requests per minute** limit. Best practices:

1. **Use caching**: Don't call `ws.lexicon_schemas()` in a loop
2. **Store results**: Save schema data locally if needed repeatedly
3. **Filter at source**: Use `entity_type` filter to reduce response size

```python
# Good: Single call, cached
event_schemas = ws.lexicon_schemas(entity_type="event")
for s in event_schemas:
    process(s)

# Bad: Multiple calls in loop (may hit rate limit)
for event_name in event_names:
    schema = ws.lexicon_schema("event", event_name)  # Each call may hit API
```
