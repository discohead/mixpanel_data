# Python Library API Reference

Complete reference for the `mixpanel_data` Python library.

## Table of Contents
- Workspace Construction
- Discovery Methods
- Fetching Methods
- Streaming Methods
- Local Query Methods
- Live Query Methods
- Introspection Methods
- Table Management
- Escape Hatches

## Workspace Construction

### Workspace()
```python
Workspace(
    path: str | Path | None = None,  # Database path (default: ~/.mp/mixpanel.db)
    account: str | None = None,       # Named account from config
    region: str | None = None,        # Override region (us, eu, in)
)
```
Standard constructor with credentials from config/environment.

### Workspace.ephemeral()
```python
@classmethod
def ephemeral(cls, account: str | None = None, region: str | None = None) -> Workspace
```
Context manager for temporary database that auto-deletes on close.

```python
with Workspace.ephemeral() as ws:
    ws.fetch_events("events", from_date="2024-01-01", to_date="2024-01-01")
    count = ws.sql_scalar("SELECT COUNT(*) FROM events")
# Database automatically deleted
```

### Workspace.memory()
```python
@classmethod
def memory(cls, account: str | None = None, region: str | None = None) -> Workspace
```
In-memory database with zero disk footprint.

### Workspace.open()
```python
@classmethod
def open(cls, path: str | Path, read_only: bool = False) -> Workspace
```
Query-only access to existing database. No credentials needed.

## Discovery Methods

### events()
```python
def events(self) -> list[str]
```
List all event names in the project. Cached.

### properties()
```python
def properties(self, event: str) -> list[str]
```
List properties for a specific event. Cached.

### property_values()
```python
def property_values(
    self,
    property_name: str,
    event: str | None = None,
    limit: int = 100,
) -> list[str]
```
Sample values for a property. Cached.

### funnels()
```python
def funnels(self) -> list[FunnelInfo]
```
List saved funnels. Returns `FunnelInfo(funnel_id, name)`. Cached.

### cohorts()
```python
def cohorts(self) -> list[SavedCohort]
```
List saved cohorts. Returns `SavedCohort(id, name, count, description)`. Cached.

### top_events()
```python
def top_events(
    self,
    type: Literal["general", "unique", "average"] = "general",
    limit: int | None = None,
) -> list[TopEvent]
```
Today's trending events. NOT cached.

### list_bookmarks()
```python
def list_bookmarks(
    self,
    bookmark_type: Literal["insights", "funnels", "retention", "flows", "launch-analysis"] | None = None,
) -> list[BookmarkInfo]
```
List saved reports, optionally filtered by type. NOT cached.

### lexicon_schemas()
```python
def lexicon_schemas(
    self,
    entity_type: Literal["event", "profile", "group", "lookup"] | None = None,
) -> list[LexiconSchema]
```
List Lexicon data dictionary schemas. Cached.

### clear_discovery_cache()
```python
def clear_discovery_cache(self) -> None
```
Force refresh of cached discovery data.

## Fetching Methods

### fetch_events()
```python
def fetch_events(
    self,
    name: str = "events",              # Table name
    from_date: str,                     # Start date (YYYY-MM-DD)
    to_date: str,                       # End date (YYYY-MM-DD)
    events: list[str] | None = None,   # Filter to specific events
    where: str | None = None,           # Mixpanel expression filter
    limit: int | None = None,           # Max events (1-100000)
    progress: bool = True,              # Show progress bar
    append: bool = False,               # Append to existing table
    batch_size: int = 1000,             # Rows per commit (100-100000)
) -> FetchResult
```
Fetch events from Export API into local table.

Returns `FetchResult(table, rows, duration_seconds, from_date, to_date, fetched_at)`.

### fetch_profiles()
```python
def fetch_profiles(
    self,
    name: str = "profiles",
    where: str | None = None,           # Profile property filter
    cohort_id: int | None = None,       # Filter to cohort members
    output_properties: list[str] | None = None,  # Specific properties
    progress: bool = True,
    append: bool = False,
    batch_size: int = 1000,
) -> FetchResult
```
Fetch user profiles from Engage API into local table.

## Streaming Methods

### stream_events()
```python
def stream_events(
    self,
    from_date: str,
    to_date: str,
    events: list[str] | None = None,
    where: str | None = None,
    limit: int | None = None,
) -> Iterator[dict]
```
Stream events without local storage. Memory-efficient for large datasets.

### stream_profiles()
```python
def stream_profiles(
    self,
    where: str | None = None,
    cohort_id: int | None = None,
    output_properties: list[str] | None = None,
) -> Iterator[dict]
```
Stream profiles without local storage.

## Local Query Methods

### sql()
```python
def sql(self, query: str) -> pd.DataFrame
```
Execute SQL query against local database. Returns pandas DataFrame.

### sql_scalar()
```python
def sql_scalar(self, query: str) -> Any
```
Execute SQL query, return single value.

### sql_rows()
```python
def sql_rows(self, query: str) -> list[tuple]
```
Execute SQL query, return list of tuples.

## Live Query Methods

### segmentation()
```python
def segmentation(
    self,
    event: str,
    from_date: str,
    to_date: str,
    on: str | None = None,              # Property to segment by
    unit: Literal["day", "week", "month"] = "day",
    where: str | None = None,           # Filter expression
) -> SegmentationResult
```
Time-series event counts with optional property breakdown.

Returns `SegmentationResult(event, from_date, to_date, unit, segment_property, total, series)`.
Access `.df` for DataFrame.

### funnel()
```python
def funnel(
    self,
    funnel_id: int,
    from_date: str,
    to_date: str,
    unit: Literal["day", "week", "month"] | None = None,
    on: str | None = None,
) -> FunnelResult
```
Conversion analysis through saved funnel steps.

Returns `FunnelResult(funnel_id, from_date, to_date, steps, overall_conversion_rate)`.

### retention()
```python
def retention(
    self,
    born_event: str,                    # Cohort entry event
    return_event: str,                  # Return event
    from_date: str,
    to_date: str,
    born_where: str | None = None,      # Filter for born event
    return_where: str | None = None,    # Filter for return event
    unit: Literal["day", "week", "month"] = "day",
    interval_count: int = 11,           # Number of intervals
) -> RetentionResult
```
Cohort retention analysis.

### jql()
```python
def jql(
    self,
    script: str,
    params: dict[str, Any] | None = None,
) -> JQLResult
```
Execute JavaScript Query Language script.

### event_counts()
```python
def event_counts(
    self,
    events: list[str],
    from_date: str,
    to_date: str,
    type: Literal["general", "unique", "average"] = "general",
    unit: Literal["day", "week", "month"] = "day",
) -> EventCountsResult
```
Multi-event time series comparison.

### property_counts()
```python
def property_counts(
    self,
    event: str,
    property_name: str,
    from_date: str,
    to_date: str,
    type: Literal["general", "unique", "average"] = "general",
    unit: Literal["day", "week", "month"] = "day",
    limit: int = 10,
    values: list[str] | None = None,
) -> PropertyCountsResult
```
Event breakdown by property values.

### activity_feed()
```python
def activity_feed(
    self,
    distinct_ids: list[str],
    from_date: str | None = None,
    to_date: str | None = None,
) -> ActivityFeedResult
```
User event history for specific users.

### query_saved_report()
```python
def query_saved_report(self, bookmark_id: int) -> SavedReportResult
```
Execute a saved Insights, Retention, or Funnel report.

### query_flows()
```python
def query_flows(self, bookmark_id: int) -> FlowsResult
```
Execute a saved Flows report.

### frequency()
```python
def frequency(
    self,
    from_date: str,
    to_date: str,
    unit: Literal["day", "week", "month"] = "day",
    addiction_unit: Literal["hour", "day"] = "hour",
    event: str | None = None,
    where: str | None = None,
) -> FrequencyResult
```
Event frequency distribution (addiction analysis).

### segmentation_numeric()
```python
def segmentation_numeric(
    self,
    event: str,
    from_date: str,
    to_date: str,
    on: str,                            # Numeric property
    unit: Literal["hour", "day"] = "day",
    where: str | None = None,
    type: Literal["general", "unique", "average"] = "general",
) -> NumericBucketResult
```
Bucket events by numeric property ranges.

### segmentation_sum()
```python
def segmentation_sum(
    self,
    event: str,
    from_date: str,
    to_date: str,
    on: str,
    unit: Literal["hour", "day"] = "day",
    where: str | None = None,
) -> NumericSumResult
```
Sum numeric property over time.

### segmentation_average()
```python
def segmentation_average(
    self,
    event: str,
    from_date: str,
    to_date: str,
    on: str,
    unit: Literal["hour", "day"] = "day",
    where: str | None = None,
) -> NumericAverageResult
```
Average numeric property over time.

## Introspection Methods

### info()
```python
def info(self) -> WorkspaceInfo
```
Workspace metadata including path, account, tables, size.

### tables()
```python
def tables(self) -> list[TableInfo]
```
List tables with row counts and fetch timestamps.

### table_schema()
```python
def table_schema(self, table: str) -> TableSchema
```
Column definitions for a table.

### sample()
```python
def sample(self, table: str, n: int = 10) -> pd.DataFrame
```
Random sample of rows.

### summarize()
```python
def summarize(self, table: str) -> SummaryResult
```
Statistical summary of all columns (min/max, quartiles, nulls, cardinality).

### event_breakdown()
```python
def event_breakdown(self, table: str) -> EventBreakdownResult
```
Per-event statistics (counts, users, date ranges, percentages).

### property_keys()
```python
def property_keys(self, table: str, event: str | None = None) -> list[str]
```
List JSON property keys in properties column.

### column_stats()
```python
def column_stats(
    self,
    table: str,
    column: str,
    top_n: int = 10,
) -> ColumnStatsResult
```
Deep single-column analysis. Supports JSON path expressions like `"properties->>'$.country'"`.

## Table Management

### drop()
```python
def drop(self, *names: str) -> None
```
Drop specific tables.

### drop_all()
```python
def drop_all(self, type: Literal["events", "profiles"] | None = None) -> None
```
Drop all tables, optionally filtered by type.

## Escape Hatches

### connection
```python
@property
def connection(self) -> duckdb.DuckDBPyConnection
```
Direct DuckDB connection for advanced queries.

### api
```python
@property
def api(self) -> MixpanelAPIClient
```
Direct API client for custom requests.
