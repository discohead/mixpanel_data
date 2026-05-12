# Quickstart: Workspace Facade

**Feature**: 009-workspace
**Date**: 2025-12-23

This guide demonstrates common usage patterns for the Workspace class.

---

## Installation

```bash
pip install mixpanel_data
```

---

## Configuration

### Using Environment Variables

```bash
export MP_USERNAME="sa_your_username"
export MP_SECRET="your_secret"
export MP_PROJECT_ID="12345"
export MP_REGION="us"  # or "eu", "in"
```

### Using Config File

```bash
# Add an account (stored in ~/.mp/config.toml)
mp auth add production --username sa_xxx --secret xxx --project 12345 --region us

# Set as default
mp auth default production
```

---

## Basic Usage

### Fetch and Query Events

```python
from mixpanel_data import Workspace

# Create workspace (uses default credentials)
ws = Workspace()

# Fetch last 30 days of events
ws.fetch_events(
    from_date="2024-01-01",
    to_date="2024-01-31"
)

# Query with SQL
df = ws.sql("""
    SELECT
        event_name,
        COUNT(*) as count
    FROM events
    GROUP BY event_name
    ORDER BY count DESC
    LIMIT 10
""")

print(df)

# Get single value
total = ws.sql_scalar("SELECT COUNT(*) FROM events")
print(f"Total events: {total}")

# Close when done
ws.close()
```

### Using Context Manager

```python
from mixpanel_data import Workspace

with Workspace() as ws:
    ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
    print(ws.sql_scalar("SELECT COUNT(*) FROM events"))
# Resources automatically cleaned up
```

---

## Ephemeral Workspaces

For temporary analysis that shouldn't persist:

```python
from mixpanel_data import Workspace

with Workspace.ephemeral() as ws:
    # Fetch data to temporary database
    ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")

    # Run analysis
    df = ws.sql("""
        SELECT
            DATE_TRUNC('day', event_time) as day,
            COUNT(*) as count
        FROM events
        GROUP BY 1
        ORDER BY 1
    """)

    print(df)
# Temporary database automatically deleted
```

---

## Schema Discovery

Explore what data exists before writing queries:

```python
from mixpanel_data import Workspace

ws = Workspace()

# List all events
events = ws.events()
print(f"Found {len(events)} events")
for event in events[:5]:
    print(f"  - {event}")

# List properties for an event
props = ws.properties("Purchase")
print(f"\nPurchase properties: {props}")

# Get sample values
values = ws.property_values("country", event="Purchase", limit=10)
print(f"\nCountry values: {values}")

# List saved funnels and cohorts
funnels = ws.funnels()
cohorts = ws.cohorts()
print(f"\nFunnels: {len(funnels)}, Cohorts: {len(cohorts)}")

ws.close()
```

---

## Live Analytics Queries

Run real-time analytics without storing data locally:

### Segmentation

```python
from mixpanel_data import Workspace

ws = Workspace()

# Basic segmentation
result = ws.segmentation(
    event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31"
)

print(f"Total: {result.total}")
print(result.df.head())

# Segmented by property
result = ws.segmentation(
    event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31",
    on="country",
    unit="week"
)

print(result.df)
ws.close()
```

### Funnel Analysis

```python
from mixpanel_data import Workspace

ws = Workspace()

# Get funnel ID from saved funnels
funnels = ws.funnels()
funnel_id = funnels[0].funnel_id

# Run funnel query
result = ws.funnel(
    funnel_id,
    from_date="2024-01-01",
    to_date="2024-01-31"
)

print(f"Overall conversion: {result.conversion_rate:.1%}")
for step in result.steps:
    print(f"  {step.event}: {step.count} ({step.conversion_rate:.1%})")

ws.close()
```

### Retention Analysis

```python
from mixpanel_data import Workspace

ws = Workspace()

result = ws.retention(
    born_event="Sign Up",
    return_event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31",
    unit="week"
)

print(result.df)  # Cohort retention table
ws.close()
```

---

## Query-Only Access

Open an existing database without API credentials:

```python
from mixpanel_data import Workspace

# Open existing database (no credentials needed)
ws = Workspace.open("my_analysis.db")

# Run queries
df = ws.sql("SELECT * FROM events LIMIT 100")

# Check what tables exist
for table in ws.tables():
    print(f"{table.name}: {table.row_count} rows")

ws.close()
```

---

## Workspace Introspection

```python
from mixpanel_data import Workspace

ws = Workspace()
ws.fetch_events("jan_events", from_date="2024-01-01", to_date="2024-01-31")

# Get workspace info
info = ws.info()
print(f"Database: {info.path}")
print(f"Project: {info.project_id}")
print(f"Region: {info.region}")
print(f"Size: {info.size_mb:.2f} MB")
print(f"Tables: {info.tables}")

# List tables with details
for table in ws.tables():
    print(f"\n{table.name} ({table.type}):")
    print(f"  Rows: {table.row_count}")
    print(f"  Fetched: {table.fetched_at}")

# Get table schema
schema = ws.schema("jan_events")
for col in schema.columns:
    print(f"  {col.name}: {col.type}")

ws.close()
```

---

## Table Management

```python
from mixpanel_data import Workspace

ws = Workspace()

# Fetch some data
ws.fetch_events("old_events", from_date="2023-01-01", to_date="2023-01-31")
ws.fetch_events("new_events", from_date="2024-01-01", to_date="2024-01-31")

# Drop specific table
ws.drop("old_events")

# Or drop all events tables
# ws.drop_all(type="events")

ws.close()
```

---

## Escape Hatches

For advanced operations not covered by the Workspace API:

```python
from mixpanel_data import Workspace

ws = Workspace()

# Direct DuckDB access
conn = ws.connection
result = conn.execute("""
    SELECT DISTINCT properties->>'$.browser' as browser
    FROM events
    WHERE properties->>'$.browser' IS NOT NULL
""").fetchall()

# Direct API access
api = ws.api
raw_response = api.segmentation(
    event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31"
)

ws.close()
```

---

## Using Named Accounts

Switch between different Mixpanel projects:

```python
from mixpanel_data import Workspace

# Use staging account
staging = Workspace(account="staging")
staging.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
staging.close()

# Use production account
prod = Workspace(account="production")
prod.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
prod.close()
```

---

## Error Handling

```python
from mixpanel_data import (
    Workspace,
    ConfigError,
    AuthenticationError,
    TableExistsError,
    TableNotFoundError,
)

try:
    ws = Workspace()
except ConfigError as e:
    print(f"No credentials configured: {e}")
    exit(1)

try:
    ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
except TableExistsError:
    print("Table 'events' already exists. Drop it first.")
    ws.drop("events")
    ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
except AuthenticationError as e:
    print(f"Invalid credentials: {e}")

try:
    ws.drop("nonexistent")
except TableNotFoundError:
    print("Table doesn't exist")

ws.close()
```

---

## Best Practices

1. **Use context managers** for automatic cleanup
2. **Use ephemeral workspaces** for one-time analysis
3. **Use Workspace.open()** for read-only access to shared databases
4. **Use discovery methods** before writing queries
5. **Drop tables explicitly** before re-fetching (prevents TableExistsError)
6. **Store credentials in config file** rather than environment for multi-project work
