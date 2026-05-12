# Quickstart: Core Entity CRUD

**Feature**: 024-core-entity-crud

## Prerequisites

- `mixpanel_data` installed with OAuth or service account credentials configured
- Workspace ID set (via `MP_WORKSPACE_ID` env var or `ws.set_workspace_id()`)

## Library Usage

### Dashboard CRUD

```python
import mixpanel_data as mp
from mixpanel_data.types import CreateDashboardParams, UpdateDashboardParams

ws = mp.Workspace()

# List all dashboards
dashboards = ws.list_dashboards()

# Create a dashboard
new_dash = ws.create_dashboard(CreateDashboardParams(title="Q1 Metrics", description="KPIs"))

# Update it
updated = ws.update_dashboard(new_dash.id, UpdateDashboardParams(title="Q1 Metrics v2"))

# Favorite and pin
ws.favorite_dashboard(new_dash.id)
ws.pin_dashboard(new_dash.id)

# Delete
ws.delete_dashboard(new_dash.id)
```

### Report/Bookmark CRUD

```python
from mixpanel_data.types import CreateBookmarkParams

# List reports (optionally filter by type)
reports = ws.list_bookmarks_v2(bookmark_type="funnels")

# Create a report
report = ws.create_bookmark(CreateBookmarkParams(
    name="Signup Funnel",
    bookmark_type="funnels",
    params={"events": [{"event": "Signup"}, {"event": "Purchase"}]},
))

# Check which dashboards contain this report
dashboard_ids = ws.bookmark_linked_dashboard_ids(report.id)

# View change history
history = ws.get_bookmark_history(report.id)
```

### Cohort CRUD

```python
from mixpanel_data.types import CreateCohortParams

# List cohorts (full detail via App API)
cohorts = ws.list_cohorts_full()

# Create a cohort
cohort = ws.create_cohort(CreateCohortParams(name="Power Users"))

# Bulk delete
ws.bulk_delete_cohorts(ids=[cohort.id])
```

## CLI Usage

```bash
# Dashboards
mp dashboards list
mp dashboards create --title "New Dashboard"
mp dashboards get 12345 --format table
mp dashboards delete 12345

# Reports
mp reports list --type funnels --format json
mp reports create --name "Signup Funnel" --type funnels --params '{"events": [...]}'
mp reports history 12345

# Cohorts
mp cohorts list --format csv
mp cohorts create --name "Power Users"
mp cohorts bulk-delete --ids 111,222,333
```

## Development Setup

```bash
# Install dependencies
uv sync

# Run tests
just test -k test_dashboards

# Run all checks
just check

# Type check
just typecheck
```
