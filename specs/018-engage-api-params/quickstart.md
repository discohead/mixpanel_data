# Quickstart: Engage API Full Parameter Support

**Feature**: 018-engage-api-params
**Date**: 2026-01-04

## Overview

This feature adds 6 new parameters to profile querying, enabling:
- Fetching specific profiles by ID
- Querying group profiles (companies, accounts)
- Filtering by user behavior
- Controlling cohort member inclusion

## Python Library Usage

### Fetch Specific Profiles by ID

```python
from mixpanel_data import Workspace

ws = Workspace()

# Fetch a single user profile
result = ws.fetch_profiles(distinct_id="user_abc123")

# Fetch multiple user profiles (up to 2000)
result = ws.fetch_profiles(
    distinct_ids=["user_abc123", "user_def456", "user_ghi789"]
)

# Stream specific profiles without storing
for profile in ws.stream_profiles(distinct_id="user_abc123"):
    print(profile)

ws.close()
```

### Query Group Profiles

```python
# Fetch company profiles instead of user profiles
result = ws.fetch_profiles(
    name="companies",
    group_id="companies"
)

# Query accounts with filtering
result = ws.fetch_profiles(
    name="enterprise_accounts",
    group_id="accounts",
    where='properties["plan"]=="enterprise"'
)
```

### Filter by User Behavior

```python
# Users who made a purchase in the last 7 days
result = ws.fetch_profiles(
    name="recent_buyers",
    behaviors='selector(event == "Purchase", time > now() - 7*24*60*60)'
)

# With explicit timestamp for consistent pagination
import time
result = ws.fetch_profiles(
    name="active_users",
    behaviors='selector(event == "Login", time > now() - 30*24*60*60)',
    as_of_timestamp=int(time.time())
)
```

### Control Cohort Member Inclusion

```python
# Include all cohort members (default behavior)
result = ws.fetch_profiles(
    cohort_id="power_users",
    include_all_users=True  # Default
)

# Only include cohort members WITH profile data
result = ws.fetch_profiles(
    cohort_id="power_users",
    include_all_users=False
)
```

## CLI Usage

### Fetch Specific Profiles

```bash
# Single profile
mp fetch profiles --distinct-id user_abc123

# Multiple profiles
mp fetch profiles --distinct-ids user_abc123 --distinct-ids user_def456

# Save to custom table
mp fetch profiles --name specific_users --distinct-id user_abc123
```

### Query Group Profiles

```bash
# Fetch company profiles
mp fetch profiles --name companies --group-id companies

# Filter group profiles
mp fetch profiles --name enterprise --group-id accounts --where 'properties["plan"]=="enterprise"'
```

### Filter by Behavior

```bash
# Recent purchasers
mp fetch profiles --name buyers --behaviors 'selector(event == "Purchase", time > now() - 7*24*60*60)'

# With timestamp
mp fetch profiles --behaviors 'selector(event == "Login")' --as-of-timestamp 1704067200
```

### Control Cohort Inclusion

```bash
# Only profiles with data
mp fetch profiles --cohort-id 12345 --no-include-all-users

# All cohort members (default)
mp fetch profiles --cohort-id 12345 --include-all-users
```

## Common Patterns

### Debug a Specific User

```python
# Quick lookup for support tickets
profile = next(ws.stream_profiles(distinct_id="user_abc123"))
print(f"User: {profile.get('$name')}, Plan: {profile.get('plan')}")
```

### Export Churned Users

```python
# Users who haven't logged in for 30 days
result = ws.fetch_profiles(
    name="churned",
    behaviors='selector(not event == "Login", time > now() - 30*24*60*60)'
)
df = ws.sql("SELECT * FROM churned")
df.to_csv("churned_users.csv")
```

### B2B Account Analysis

```python
# Fetch all enterprise accounts
ws.fetch_profiles(
    name="enterprise_companies",
    group_id="companies",
    where='properties["tier"]=="enterprise"'
)

# Analyze revenue by account
df = ws.sql("""
    SELECT
        properties->>'$.name' as company,
        properties->>'$.mrr' as mrr
    FROM enterprise_companies
    ORDER BY CAST(properties->>'$.mrr' AS INTEGER) DESC
""")
```

## Error Handling

```python
# Invalid: both distinct_id and distinct_ids
try:
    ws.fetch_profiles(distinct_id="a", distinct_ids=["b", "c"])
except ValueError as e:
    print(e)  # "Cannot specify both distinct_id and distinct_ids"

# Invalid: behaviors with cohort_id
try:
    ws.fetch_profiles(behaviors="...", cohort_id="12345")
except ValueError as e:
    print(e)  # "Cannot specify both behaviors and cohort_id"

# Invalid: include_all_users without cohort_id
try:
    ws.fetch_profiles(include_all_users=False)
except ValueError as e:
    print(e)  # "include_all_users requires cohort_id"
```

## Next Steps

- See [data-model.md](data-model.md) for complete parameter specifications
- See [research.md](research.md) for design decisions and rationale
- See [contracts/engage-params.yaml](contracts/engage-params.yaml) for API contract
