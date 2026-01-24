# MCP Tools Reference

Complete reference for all 40+ tools in the Mixpanel MCP server.

## Discovery Tools

Schema exploration tools for understanding available data.

### list_events

List all event names tracked in the Mixpanel project.

```
list_events() -> list[str]
```

**Returns**: List of event names sorted alphabetically.

**Example**: "What events do I have?" -> `["login", "purchase", "signup", ...]`

---

### list_properties

List properties for a specific event.

```
list_properties(event: str) -> list[dict]
```

**Parameters**:
- `event`: Event name to get properties for

**Returns**: List of property definitions with name and type (type is always "unknown" as Mixpanel API doesn't expose types).

**Example**: "What properties does the signup event have?" -> `[{"name": "browser", "type": "unknown"}, ...]`

---

### list_property_values

List sample values for a specific property.

```
list_property_values(
    event: str,
    property_name: str,
    limit: int = 100
) -> list[Any]
```

**Parameters**:
- `event`: Event name containing the property
- `property_name`: Property name to get values for
- `limit`: Maximum number of values to return (default 100)

**Returns**: List of sample values for the property.

**Example**: "What values does the browser property have?" -> `["Chrome", "Firefox", "Safari", ...]`

---

### list_funnels

List saved funnels in the Mixpanel project.

```
list_funnels() -> list[dict]
```

**Returns**: List of funnel metadata dictionaries with funnel_id, name, and step count.

**Example**: "Show me my saved funnels" -> `[{"funnel_id": 1, "name": "Signup Funnel", "steps": 3}, ...]`

---

### list_cohorts

List saved cohorts (user segments) in the Mixpanel project.

```
list_cohorts() -> list[dict]
```

**Returns**: List of cohort metadata dictionaries with cohort_id, name, and user count.

**Example**: "What cohorts do I have?" -> `[{"cohort_id": 1, "name": "Active Users", "count": 1000}, ...]`

---

### list_bookmarks

List saved reports (bookmarks) in the Mixpanel project.

```
list_bookmarks(
    bookmark_type: str | None = None,
    limit: int = 100
) -> dict
```

**Parameters**:
- `bookmark_type`: Optional filter by type (insights, funnels, retention, flows, launch-analysis). RECOMMENDED for large projects.
- `limit`: Maximum number of bookmarks to return (default 100). Set to 0 for unlimited.

**Returns**: Dictionary with bookmarks list, truncated flag, and total_count.

**Example**: "Show me my saved funnel reports" -> `list_bookmarks(bookmark_type="funnels")`

---

### top_events

List events ranked by activity volume.

```
top_events(
    limit: int = 10,
    type: Literal["general", "average", "unique"] = "general"
) -> list[dict]
```

**Parameters**:
- `limit`: Maximum number of events to return (default 10)
- `type`: Count type - general (total), average, or unique users

**Returns**: List of events with their activity counts, sorted by volume.

**Example**: "What are my most popular events by unique users?" -> `top_events(limit=10, type="unique")`

---

### workspace_info

Get current workspace state and configuration.

```
workspace_info() -> dict
```

**Returns**: Dictionary with project_id, region, and table information.

**Example**: "What project am I connected to?" -> `{"project_id": 123456, "region": "us", "tables": [...]}`

---

## Live Query Tools

Real-time analytics queries against Mixpanel API.

### segmentation

Run a segmentation query to analyze event trends over time.

```
segmentation(
    event: str,
    from_date: str,
    to_date: str,
    segment_property: str | None = None,
    unit: Literal["day", "week", "month"] = "day",
    where: str | None = None
) -> dict
```

**Parameters**:
- `event`: Event name to analyze
- `from_date`: Start date (YYYY-MM-DD format)
- `to_date`: End date (YYYY-MM-DD format)
- `segment_property`: Optional property to segment by
- `unit`: Time unit for aggregation (day, week, month)
- `where`: Optional filter expression (e.g., `'properties["country"] == "US"'`)

**Returns**: Dictionary with time series data.

**Example**:
```
segmentation(
    event="login",
    from_date="2024-01-01",
    to_date="2024-01-07",
    where='properties["platform"] == "mobile"'
)
```

---

### funnel

Analyze conversion through a saved funnel.

```
funnel(
    funnel_id: int,
    from_date: str,
    to_date: str,
    unit: Literal["day", "week", "month"] = "day",
    on: str | None = None
) -> dict
```

**Parameters**:
- `funnel_id`: ID of the saved funnel to analyze
- `from_date`: Start date (YYYY-MM-DD format)
- `to_date`: End date (YYYY-MM-DD format)
- `unit`: Time unit for cohort grouping
- `on`: Optional property to segment funnel by. Must use property accessor format (e.g., `'properties["country"]'`)

**Returns**: Dictionary with funnel conversion data.

**Example**:
```
funnel(
    funnel_id=1,
    from_date="2024-01-01",
    to_date="2024-01-31",
    on='properties["country"]'
)
```

---

### retention

Analyze user retention over time.

```
retention(
    born_event: str,
    from_date: str,
    to_date: str,
    return_event: str | None = None,
    born_where: str | None = None,
    return_where: str | None = None,
    interval: int = 1,
    interval_count: int = 7,
    unit: Literal["day", "week", "month"] = "day"
) -> dict
```

**Parameters**:
- `born_event`: Event that defines cohort entry
- `from_date`: Start date (YYYY-MM-DD format)
- `to_date`: End date (YYYY-MM-DD format)
- `return_event`: Event to measure return (defaults to born_event)
- `born_where`: Optional filter for born event
- `return_where`: Optional filter for return event
- `interval`: Length of each retention interval (default: 1)
- `interval_count`: Number of retention intervals to analyze
- `unit`: Time unit for intervals (day, week, month)

**Returns**: Dictionary with retention cohort data.

**Example**:
```
retention(
    born_event="signup",
    from_date="2024-01-01",
    to_date="2024-01-31",
    born_where='properties["platform"] == "mobile"'
)
```

---

### jql

Execute a JQL (JavaScript Query Language) script.

```
jql(
    script: str,
    params: dict | None = None
) -> list[Any]
```

**Parameters**:
- `script`: JQL script to execute
- `params`: Optional parameters to pass to the script

**Returns**: List of result dictionaries from the JQL execution.

**Example**:
```
jql(
    script="function main() { return Events({...}).groupBy(...) }",
    params={"from_date": "2024-01-01"}
)
```

---

### event_counts

Get counts for multiple events in a single query.

```
event_counts(
    events: list[str],
    from_date: str,
    to_date: str,
    unit: Literal["day", "week", "month"] = "day",
    type: Literal["general", "unique", "average"] = "general"
) -> dict
```

**Parameters**:
- `events`: List of event names to count
- `from_date`: Start date (YYYY-MM-DD format)
- `to_date`: End date (YYYY-MM-DD format)
- `unit`: Time unit for aggregation
- `type`: Count type - general (total), unique (unique users), or average

**Returns**: Dictionary with counts for each event.

**Example**: "Compare unique login and signup users this month" -> `event_counts(events=["login", "signup"], ..., type="unique")`

---

### property_counts

Get event counts broken down by property value.

```
property_counts(
    event: str,
    property_name: str,
    from_date: str,
    to_date: str,
    type: Literal["general", "unique", "average"] = "general",
    unit: Literal["day", "week", "month"] = "day",
    values: list[str] | None = None,
    limit: int | None = None
) -> dict
```

**Parameters**:
- `event`: Event name to analyze
- `property_name`: Property to break down by
- `from_date`: Start date (YYYY-MM-DD format)
- `to_date`: End date (YYYY-MM-DD format)
- `type`: Count type - general, unique, or average
- `unit`: Time unit for aggregation
- `values`: Optional list of specific property values to include
- `limit`: Optional maximum number of property values to return

**Returns**: Dictionary with counts per property value.

**Example**: "What are the top 5 browsers users log in with?" -> `property_counts(event="login", property_name="browser", ..., limit=5)`

---

### activity_feed

Get activity feed for a specific user.

```
activity_feed(
    distinct_id: str,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 100
) -> dict
```

**Parameters**:
- `distinct_id`: User identifier to look up
- `from_date`: Optional start date (YYYY-MM-DD)
- `to_date`: Optional end date (YYYY-MM-DD)
- `limit`: Maximum number of events to return (default 100). Set to 0 for unlimited.

**Returns**: Dictionary with user events, truncated flag, and total_events count.

**Example**: "What has user alice done recently?" -> `activity_feed(distinct_id="alice")`

---

### frequency

Analyze how often users perform events (addiction analysis).

```
frequency(
    from_date: str,
    to_date: str,
    event: str | None = None,
    unit: Literal["day", "week", "month"] = "day",
    addiction_unit: Literal["hour", "day"] = "hour",
    where: str | None = None
) -> dict
```

**Parameters**:
- `from_date`: Start date (YYYY-MM-DD format)
- `to_date`: End date (YYYY-MM-DD format)
- `event`: Optional event name to filter (None = all events)
- `unit`: Time unit for aggregation
- `addiction_unit`: Time unit for measuring frequency (hour or day)
- `where`: Optional filter expression

**Returns**: Dictionary with frequency distribution data.

---

## Fetch Tools

Download data from Mixpanel to local DuckDB storage.

### fetch_events

Fetch events from Mixpanel and store in local database.

```
fetch_events(
    from_date: str,
    to_date: str,
    table: str | None = None,
    events: list[str] | None = None,
    where: str | None = None,
    limit: int | None = None,
    append: bool = False,
    parallel: bool = False,
    workers: int = 4
) -> dict
```

**Parameters**:
- `from_date`: Start date (YYYY-MM-DD format)
- `to_date`: End date (YYYY-MM-DD format)
- `table`: Optional table name (auto-generated if not provided)
- `events`: Optional list of event names to filter by
- `where`: Optional filter expression
- `limit`: Optional maximum number of events to fetch
- `append`: Append to existing table instead of creating new one
- `parallel`: Use parallel fetching for large date ranges
- `workers`: Number of parallel workers (if parallel=True)

**Returns**: Dictionary with table_name, row_count, and status.

**Note**: This is a task-enabled tool with progress reporting and cancellation support.

**Example**: "Download last week's login events" -> `fetch_events(from_date="2024-01-01", to_date="2024-01-07", events=["login"])`

---

### fetch_profiles

Fetch user profiles from Mixpanel and store in local database.

```
fetch_profiles(
    table: str | None = None,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
    distinct_id: str | None = None,
    distinct_ids: list[str] | None = None,
    group_id: str | None = None,
    behaviors: list[dict] | None = None,
    as_of_timestamp: int | None = None,
    include_all_users: bool = False,
    append: bool = False,
    parallel: bool = False,
    workers: int = 4
) -> dict
```

**Parameters**:
- `table`: Optional table name (default: "profiles")
- `where`: Optional filter expression
- `cohort_id`: Optional cohort ID to filter profiles by
- `output_properties`: Optional list of properties to include
- `distinct_id`: Optional single user ID to fetch
- `distinct_ids`: Optional list of user IDs to fetch
- `group_id`: Optional group ID for group profiles
- `behaviors`: Optional list of behavioral filter conditions
- `as_of_timestamp`: Optional Unix timestamp for point-in-time profile state
- `include_all_users`: Include all users with cohort membership markers
- `append`: Append to existing table
- `parallel`: Use parallel fetching
- `workers`: Number of parallel workers

**Returns**: Dictionary with table_name, row_count, and status.

**Example**: "Download profiles from the 'Active Users' cohort" -> `fetch_profiles(cohort_id="12345")`

---

### stream_events

Stream events directly without storing them.

```
stream_events(
    from_date: str,
    to_date: str,
    events: list[str] | None = None,
    where: str | None = None,
    limit: int = 1000
) -> list[dict]
```

**Parameters**:
- `from_date`: Start date (YYYY-MM-DD format)
- `to_date`: End date (YYYY-MM-DD format)
- `events`: Optional list of event names to filter by
- `where`: Optional filter expression
- `limit`: Maximum events to return

**Returns**: List of event dictionaries.

---

### stream_profiles

Stream profiles directly without storing them.

```
stream_profiles(
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
    distinct_id: str | None = None,
    distinct_ids: list[str] | None = None,
    group_id: str | None = None,
    behaviors: list[dict] | None = None,
    as_of_timestamp: int | None = None,
    include_all_users: bool = False
) -> list[dict]
```

**Returns**: List of profile dictionaries.

---

## Local Query Tools

SQL analysis on locally stored data.

### sql

Execute a SQL query against local data.

```
sql(query: str) -> list[dict]
```

**Parameters**:
- `query`: SQL query to execute

**Returns**: List of result rows as dictionaries.

**Example**: "Count events by name" -> `sql(query="SELECT event_name, COUNT(*) as cnt FROM events GROUP BY event_name")`

---

### sql_scalar

Execute a SQL query that returns a single value.

```
sql_scalar(query: str) -> int | float | str | bool | None
```

**Parameters**:
- `query`: SQL query returning a single value

**Returns**: The scalar result value.

**Example**: "How many events are there?" -> `sql_scalar(query="SELECT COUNT(*) FROM events")`

---

### list_tables

List all tables in the local database.

```
list_tables() -> list[dict]
```

**Returns**: List of table metadata dictionaries with name, row_count, and type.

---

### table_schema

Get the schema (column definitions) for a table.

```
table_schema(table: str) -> list[dict]
```

**Parameters**:
- `table`: Name of the table

**Returns**: List of column definitions.

---

### sample

Get a random sample of rows from a table.

```
sample(table: str, limit: int = 10) -> list[dict]
```

**Parameters**:
- `table`: Name of the table
- `limit`: Number of rows to return

**Returns**: List of sample rows.

---

### summarize

Get summary statistics for a table.

```
summarize(table: str) -> dict
```

**Parameters**:
- `table`: Name of the table

**Returns**: Dictionary with table, row_count, and columns statistics.

---

### event_breakdown

Get event counts by name from a local table.

```
event_breakdown(table: str) -> list[dict]
```

**Parameters**:
- `table`: Name of the events table

**Returns**: List of event names with counts.

---

### property_keys

Extract unique property keys from event properties.

```
property_keys(table: str, event: str | None = None) -> list[str]
```

**Parameters**:
- `table`: Name of the events table
- `event`: Optional event name to filter by

**Returns**: List of unique property key names.

---

### column_stats

Get detailed statistics for a specific column.

```
column_stats(table: str, column: str) -> dict
```

**Parameters**:
- `table`: Name of the table
- `column`: Name of the column or JSON path expression (e.g., `"properties->>'$.field'"`)

**Returns**: Dictionary with count, distinct_count, min_value, and max_value.

---

### drop_table

Remove a table from the local database.

```
drop_table(table: str) -> dict
```

**Parameters**:
- `table`: Name of the table to drop

**Returns**: Dictionary with success status.

---

### drop_all_tables

Remove all tables from the local database.

```
drop_all_tables() -> dict
```

**Returns**: Dictionary with success status.

---

## Composed Tools

Higher-level tools that orchestrate multiple primitive tools.

### cohort_comparison

Compare two user cohorts across behavioral dimensions.

```
cohort_comparison(
    cohort_a_filter: str,
    cohort_b_filter: str,
    cohort_a_name: str = "Cohort A",
    cohort_b_name: str = "Cohort B",
    from_date: str | None = None,
    to_date: str | None = None,
    acquisition_event: str = "signup",
    compare_dimensions: list[str] | None = None
) -> dict
```

**Parameters**:
- `cohort_a_filter`: Filter expression for cohort A (e.g., `'properties["sessions"] >= 10'`)
- `cohort_b_filter`: Filter expression for cohort B
- `cohort_a_name`: Display name for cohort A
- `cohort_b_name`: Display name for cohort B
- `from_date`: Start date for analysis (defaults to 30 days ago)
- `to_date`: End date for analysis (defaults to today)
- `acquisition_event`: Event for retention analysis (default: signup)
- `compare_dimensions`: Dimensions to compare (event_frequency, retention, top_events)

**Returns**: Dictionary with cohort metrics, comparisons, statistical_significance, and key_differences.

**Example**:
```
cohort_comparison(
    cohort_a_filter='properties["sessions"] >= 10',
    cohort_b_filter='properties["sessions"] < 3',
    cohort_a_name="Power Users",
    cohort_b_name="Casual Users"
)
```

---

### product_health_dashboard

Generate a comprehensive AARRR product health dashboard.

```
product_health_dashboard(
    acquisition_event: str = "signup",
    activation_event: str | None = None,
    retention_event: str | None = None,
    revenue_event: str | None = None,
    referral_event: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    segment_by: str | None = None
) -> dict
```

**Parameters**:
- `acquisition_event`: Event indicating acquisition (default: "signup")
- `activation_event`: Event indicating activation/first value moment
- `retention_event`: Event for retention analysis
- `revenue_event`: Event indicating revenue (e.g., "purchase")
- `referral_event`: Event indicating referral (e.g., "invite_sent")
- `from_date`: Start date (defaults to 30 days ago)
- `to_date`: End date (defaults to today)
- `segment_by`: Optional property to segment acquisition by

**Returns**: Dictionary with acquisition, activation, retention, revenue, referral metrics and health_score (1-10) for each.

---

### gqm_investigation

Perform structured investigation using GQM methodology.

```
gqm_investigation(
    goal: str,
    from_date: str | None = None,
    to_date: str | None = None,
    acquisition_event: str = "signup",
    max_questions: int = 5
) -> dict
```

**Parameters**:
- `goal`: High-level goal to investigate (e.g., "understand why retention is declining")
- `from_date`: Start date (defaults to 30 days ago)
- `to_date`: End date (defaults to today)
- `acquisition_event`: Event to use for analysis (default: "signup")
- `max_questions`: Maximum questions to generate (default: 5)

**Returns**: Dictionary with interpreted_goal, aarrr_category, questions, findings, synthesis, and next_steps.

---

## Intelligent Tools

AI-powered analysis with LLM synthesis.

### ask_mixpanel

Answer natural language analytics questions.

```
ask_mixpanel(
    question: str,
    from_date: str | None = None,
    to_date: str | None = None
) -> dict
```

**Parameters**:
- `question`: Natural language question about your analytics data
- `from_date`: Optional start date (defaults to 30 days ago)
- `to_date`: Optional end date (defaults to today)

**Returns**: Dictionary with status, answer, plan, and results.

**Example**: "What features do our best users engage with?" -> `ask_mixpanel(question="What features do our best users engage with?")`

---

### diagnose_metric_drop

Diagnose a metric drop with AI-powered analysis.

```
diagnose_metric_drop(
    event: str,
    date: str,
    dimensions: list[str] | None = None
) -> dict
```

**Parameters**:
- `event`: Event name to analyze (e.g., "signup", "login")
- `date`: Date of the observed drop (YYYY-MM-DD format)
- `dimensions`: Optional list of property dimensions to analyze (defaults to common dimensions)

**Returns**: Dictionary with findings, raw_data, and analysis_hints.

**Example**: "Why did signups drop on January 7th?" -> `diagnose_metric_drop(event="signup", date="2026-01-07")`

---

### funnel_optimization_report

Generate comprehensive funnel optimization report.

```
funnel_optimization_report(
    funnel_id: int,
    from_date: str | None = None,
    to_date: str | None = None,
    segment_properties: list[str] | None = None
) -> dict
```

**Parameters**:
- `funnel_id`: ID of the saved funnel to analyze
- `from_date`: Start date (defaults to 30 days ago)
- `to_date`: End date (defaults to today)
- `segment_properties`: Properties to segment by (defaults to browser and OS)

**Returns**: Dictionary with executive_summary, overall_conversion_rate, bottleneck analysis, top/underperforming segments, and recommendations.

---

## Interactive Tools

Guided workflows with user interaction.

### guided_analysis

Interactive guided analysis with multi-step workflow.

```
guided_analysis(
    focus_area: Literal["conversion", "retention", "engagement", "revenue"] | None = None,
    time_period: Literal["last_7_days", "last_30_days", "last_90_days", "custom"] | None = None,
    from_date: str | None = None,
    to_date: str | None = None
) -> dict
```

**Parameters**:
- `focus_area`: Pre-selected focus area (conversion, retention, engagement, revenue)
- `time_period`: Pre-selected time period
- `from_date`: Custom start date for analysis
- `to_date`: Custom end date for analysis

**Returns**: Dictionary with status, focus_area, initial_analysis, segment_analysis, and suggestions.

---

### safe_large_fetch

Safely fetch events with confirmation for large operations.

```
safe_large_fetch(
    from_date: str | None = None,
    to_date: str | None = None,
    events: list[str] | None = None,
    table: str | None = None,
    confirmation_threshold: int = 100000
) -> dict
```

**Parameters**:
- `from_date`: Start date (defaults to 30 days ago)
- `to_date`: End date (defaults to today)
- `events`: Optional list of specific events to fetch
- `table`: Optional table name for storing results
- `confirmation_threshold`: Number of events above which to require confirmation (default: 100,000)

**Returns**: Dictionary with status, estimated_count, actual_count, table_name, and message.
