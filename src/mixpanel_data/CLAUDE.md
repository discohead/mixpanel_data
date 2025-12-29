# mixpanel_data Package

Public API for the Mixpanel data library. Import from here, not from `_internal`.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Public exports (Workspace, exceptions, types) |
| `workspace.py` | Main facade class orchestrating all operations |
| `auth.py` | Public auth module (ConfigManager, Credentials, AccountInfo) |
| `exceptions.py` | Exception hierarchy with structured error context |
| `types.py` | Result dataclasses (FetchResult, SegmentationResult, etc.) |
| `_literal_types.py` | Literal type aliases (TimeUnit, CountType, HourDayUnit) |
| `_internal/` | Private implementation (do not import directly) |
| `cli/` | Command-line interface |

## Primary Entry Point

```python
from mixpanel_data import Workspace

# Standard usage (credentials from env/config)
ws = Workspace()
ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
df = ws.sql("SELECT * FROM events")
ws.close()

# Ephemeral (auto-cleanup)
with Workspace.ephemeral() as ws:
    ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
    count = ws.sql_scalar("SELECT COUNT(*) FROM events")

# Query-only (no credentials needed)
ws = Workspace.open("existing.db")
```

## Workspace Methods

**Discovery**: `events()`, `properties()`, `property_values()`, `funnels()`, `cohorts()`, `list_bookmarks()`, `top_events()`, `lexicon_schemas()`, `lexicon_schema()`, `clear_discovery_cache()`

**Fetching**: `fetch_events()`, `fetch_profiles()`, `stream_events()`, `stream_profiles()`

**Local Queries**: `sql()`, `sql_scalar()`, `sql_rows()`

**Live Queries**: `segmentation()`, `funnel()`, `retention()`, `jql()`, `event_counts()`, `property_counts()`, `activity_feed()`, `query_saved_report()`, `query_flows()`, `frequency()`, `segmentation_numeric()`, `segmentation_sum()`, `segmentation_average()`

**JQL Discovery**: `property_distribution()`, `numeric_summary()`, `daily_counts()`, `engagement_distribution()`, `property_coverage()`

**Introspection**: `info()`, `tables()`, `table_schema()`, `sample()`, `summarize()`, `event_breakdown()`, `property_keys()`, `column_stats()`

**Table Management**: `drop()`, `drop_all()`

**Escape Hatches**: `connection` (DuckDB), `api` (MixpanelAPIClient)

## Exception Hierarchy

```
MixpanelDataError
├── ConfigError
│   ├── AccountNotFoundError
│   └── AccountExistsError
├── APIError
│   ├── AuthenticationError
│   ├── RateLimitError
│   ├── QueryError
│   │   └── JQLSyntaxError
│   └── ServerError
├── TableExistsError
└── TableNotFoundError
```

All exceptions provide `.to_dict()` for JSON serialization and structured `.details`.

## Result Types

All frozen dataclasses with:
- `.df` property: Lazy DataFrame conversion (cached)
- `.to_dict()`: JSON-serializable output

Key types: `FetchResult`, `SegmentationResult`, `FunnelResult`, `RetentionResult`, `JQLResult`, `SavedReportResult`, `FlowsResult`, `BookmarkInfo`, `PropertyDistributionResult`, `NumericPropertySummaryResult`, `DailyCountsResult`, `EngagementDistributionResult`, `PropertyCoverageResult`, `TableInfo`, `TableSchema`, `WorkspaceInfo`

## Type Aliases

For type hints in consuming code:
- `TimeUnit = Literal["day", "week", "month"]`
- `HourDayUnit = Literal["hour", "day"]`
- `CountType = Literal["general", "unique", "average"]`
