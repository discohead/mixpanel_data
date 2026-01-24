# Tools Reference

Complete reference for all MCP tools exposed by the server.

!!! tip "Explore on DeepWiki"
    🤖 **[Tools Reference →](https://deepwiki.com/jaredmcfarland/mixpanel_data/3.4.2-composed-analytics-tools)**

    Ask about specific tools, explore parameters, or get usage examples.

## Tool Tier System

Tools are organized into tiers based on their complexity and MCP features:

| Tier | Count | Description | MCP Feature |
|------|-------|-------------|-------------|
| **Tier 1** | 31 | Primitive tools (direct API calls) | Standard tools |
| **Tier 2** | 3 | Composed tools (multi-query orchestration) | Standard tools |
| **Tier 3** | 3 | Intelligent tools (AI synthesis) | `ctx.sample()` |
| **Interactive** | 2 | Elicitation workflows | `ctx.elicit()` |

**Total: 39 tools**

---

## Discovery Tools (8)

Explore your Mixpanel project's schema and metadata.

### list_events

List all tracked events in the project.

**Returns:** Event names with optional metadata (descriptions, volume)

**Example prompt:** "What events are tracked in my project?"

---

### list_properties

Get properties for a specific event.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event` | string | Yes | Event name |

**Returns:** Property names, types, and descriptions

**Example prompt:** "What properties are on the Purchase event?"

---

### list_property_values

Get sample values for a property.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event` | string | Yes | Event name |
| `property_name` | string | Yes | Property name |
| `limit` | int | No | Maximum values to return (default: 100) |

**Returns:** Sample values for the property

**Example prompt:** "What countries do Purchase events come from?"

---

### list_funnels

List saved funnels in the project.

**Returns:** Funnel IDs, names, and step counts

**Example prompt:** "What funnels are defined in my project?"

---

### list_cohorts

List saved cohorts in the project.

**Returns:** Cohort IDs, names, and descriptions

**Example prompt:** "What user cohorts exist?"

---

### list_bookmarks

List saved reports (Insights, Funnels, Retention, Flows).

**Returns:** Bookmark IDs, names, types, and creation dates

**Example prompt:** "Show me my saved reports"

---

### top_events

Get the most active events by volume.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | int | No | Number of events to return (default: 10) |

**Returns:** Top events with counts

**Example prompt:** "What are my highest-volume events?"

---

### workspace_info

Get workspace configuration details.

**Returns:** Project ID, region, account name, storage path

**Example prompt:** "Show my Mixpanel workspace configuration"

---

## Live Query Tools (8)

Execute queries against the Mixpanel API.

### segmentation

Time series event analysis with grouping and filtering.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event` | string | Yes | Event to analyze |
| `from_date` | string | Yes | Start date (YYYY-MM-DD) |
| `to_date` | string | Yes | End date (YYYY-MM-DD) |
| `on` | string | No | Property to group by |
| `where` | string | No | Filter expression |
| `unit` | string | No | Time unit (hour, day, week, month) |

**Returns:** Time series data with optional grouping

**Example prompt:** "How many Purchase events happened each day last week, grouped by country?"

---

### funnel

Conversion funnel analysis.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `funnel_id` | int | Yes | Saved funnel ID |
| `from_date` | string | Yes | Start date (YYYY-MM-DD) |
| `to_date` | string | Yes | End date (YYYY-MM-DD) |
| `on` | string | No | Property to segment by |

**Returns:** Step-by-step conversion rates

**Example prompt:** "What's the conversion rate for my signup funnel this month?"

---

### retention

User retention analysis.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `born_event` | string | Yes | Initial event (cohort definition) |
| `from_date` | string | Yes | Start date (YYYY-MM-DD) |
| `to_date` | string | Yes | End date (YYYY-MM-DD) |
| `return_event` | string | No | Return event (default: same as born_event) |
| `retention_type` | string | No | Type (birth, compounding) |
| `interval_count` | int | No | Number of intervals |
| `interval` | string | No | Interval size (day, week, month) |

**Returns:** Retention rates by cohort and interval

**Example prompt:** "Show day-7 retention for users who signed up last month"

---

### jql

Execute JQL (JavaScript Query Language) scripts.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `script` | string | Yes | JQL script to execute |

**Returns:** JQL query results

**Example prompt:** "Run this JQL to count events by hour of day"

---

### event_counts

Count multiple events in a single query.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `events` | list[string] | Yes | Event names to count |
| `from_date` | string | Yes | Start date |
| `to_date` | string | Yes | End date |
| `unit` | string | No | Time unit |

**Returns:** Time series for each event

**Example prompt:** "Compare Login and Signup counts this week"

---

### property_counts

Property value breakdown over time.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event` | string | Yes | Event name |
| `property` | string | Yes | Property to break down |
| `from_date` | string | Yes | Start date |
| `to_date` | string | Yes | End date |

**Returns:** Time series by property value

**Example prompt:** "Show Purchase counts by payment method"

---

### activity_feed

Get event history for a specific user.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `distinct_id` | string | Yes | User identifier |
| `from_date` | string | Yes | Start date |
| `to_date` | string | No | End date |
| `limit` | int | No | Maximum events |

**Returns:** Chronological event list for the user

**Example prompt:** "Show me the last 50 events for user user@example.com"

---

### frequency

Event frequency distribution.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event` | string | Yes | Event name |
| `from_date` | string | Yes | Start date |
| `to_date` | string | Yes | End date |

**Returns:** Distribution of events per user

**Example prompt:** "How many times do users typically trigger the Purchase event?"

---

## Fetch Tools (4)

Download data to local DuckDB storage for SQL analysis.

### fetch_events

Download events to local storage with progress reporting.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `table` | string | No | Target table name (auto-generated when omitted) |
| `from_date` | string | Yes | Start date |
| `to_date` | string | Yes | End date |
| `events` | list[string] | No | Filter to specific events |
| `where` | string | No | Filter expression |
| `parallel` | bool | No | Use parallel fetching (faster for large date ranges) |

**Returns:** Fetch summary with row count

**Example prompt:** "Fetch all events from January to the jan_events table"

!!! note "Progress Reporting"
    This tool reports progress during long-running fetches using MCP tasks.

---

### fetch_profiles

Download user profiles to local storage with progress reporting.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `table` | string | No | Target table name (auto-generated when omitted) |
| `cohort_id` | int | No | Filter by cohort |
| `where` | string | No | Filter expression |
| `output_properties` | list[string] | No | Specific properties to include |
| `parallel` | bool | No | Use parallel fetching |

**Returns:** Fetch summary with profile count

**Example prompt:** "Fetch all premium user profiles"

---

### stream_events

Stream events without storing locally.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_date` | string | Yes | Start date |
| `to_date` | string | Yes | End date |
| `events` | list[string] | No | Filter to specific events |
| `limit` | int | No | Maximum events |

**Returns:** Event data directly (not persisted)

---

### stream_profiles

Stream profiles without storing locally.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cohort_id` | int | No | Filter by cohort |
| `where` | string | No | Filter expression |
| `limit` | int | No | Maximum profiles |

**Returns:** Profile data directly (not persisted)

---

## Local SQL Tools (11)

Query and manage local DuckDB storage.

### sql

Execute SQL queries against local tables.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | SQL query |

**Returns:** Query results as a list of rows

**Example prompt:** "Count events by name in the jan_events table"

---

### sql_scalar

Execute SQL returning a single value.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | SQL query returning one value |

**Returns:** Single scalar value

**Example prompt:** "How many total events are in jan_events?"

---

### list_tables

List all local tables.

**Returns:** Table names with types (events/profiles)

**Example prompt:** "What tables do I have locally?"

---

### table_schema

Get column information for a table.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `table` | string | Yes | Table to describe |

**Returns:** Column names, types, and descriptions

**Example prompt:** "What columns are in the jan_events table?"

---

### sample

Get random sample rows from a table.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `table` | string | Yes | Table to sample |
| `limit` | int | No | Number of rows (default: 10) |

**Returns:** Sample rows

**Example prompt:** "Show me 5 sample events from jan_events"

---

### summarize

Get statistical summary of all columns.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `table_name` | string | Yes | Table to summarize |

**Returns:** Column statistics (nulls, unique values, min/max)

**Example prompt:** "Summarize the jan_events table"

---

### event_breakdown

Count events by name.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `table_name` | string | Yes | Events table |

**Returns:** Event counts sorted by frequency

**Example prompt:** "What's the distribution of event types in jan_events?"

---

### property_keys

Extract unique property keys from JSON column.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `table_name` | string | Yes | Table to analyze |
| `column` | string | No | JSON column (default: properties) |

**Returns:** Unique property keys

**Example prompt:** "What properties are present in the jan_events data?"

---

### column_stats

Get detailed statistics for a column.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `table_name` | string | Yes | Table name |
| `column` | string | Yes | Column to analyze |

**Returns:** Detailed column statistics

---

### drop_table

Remove a local table.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `table_name` | string | Yes | Table to drop |

**Returns:** Confirmation

---

### drop_all_tables

Remove all local tables.

**Returns:** Confirmation with count of dropped tables

!!! warning "Destructive Operation"
    This permanently removes all local data.

---

## Intelligent Tools (3) — Tier 3

AI-powered analysis tools using `ctx.sample()` for LLM synthesis.

!!! note "Graceful Degradation"
    When sampling is unavailable, these tools return raw query results with manual analysis hints instead of AI-synthesized findings.

### diagnose_metric_drop

Analyze sudden metric declines with AI synthesis.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event` | string | Yes | Event to analyze |
| `date` | string | Yes | Date of the drop (YYYY-MM-DD) |
| `dimensions` | list[string] | No | Properties to investigate |

**Returns:** AI-synthesized analysis of the metric drop with probable causes

**Example prompt:** "Why did signups drop on January 7th?"

---

### ask_mixpanel

Natural language analytics queries.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `question` | string | Yes | Natural language question |

**Returns:** AI-synthesized answer based on executed queries

**Example prompt:** "What features do our best users engage with?"

---

### funnel_optimization_report

Comprehensive funnel analysis with recommendations.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `funnel_id` | int | Yes | Funnel to analyze |
| `from_date` | string | Yes | Start date |
| `to_date` | string | Yes | End date |

**Returns:** AI-synthesized funnel analysis with optimization recommendations

**Example prompt:** "Generate a funnel optimization report for my signup funnel"

---

## Composed Tools (3) — Tier 2

Multi-query orchestration tools for comprehensive analysis.

### product_health_dashboard

AARRR metrics (Acquisition, Activation, Retention, Revenue, Referral) in one request.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_date` | string | Yes | Start date |
| `to_date` | string | Yes | End date |
| `acquisition_event` | string | No | Acquisition event (default: Signup) |
| `activation_event` | string | No | Activation event |
| `revenue_event` | string | No | Revenue event (default: Purchase) |

**Returns:** Complete AARRR dashboard with all metrics

**Example prompt:** "Show me a product health dashboard for the last month"

---

### gqm_investigation

Goal-Question-Metric framework for structured investigation.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `goal` | string | Yes | Business goal to investigate |
| `questions` | list[string] | No | Specific questions to answer |

**Returns:** Structured investigation with metrics for each question

**Example prompt:** "Investigate why user retention is declining"

---

### cohort_comparison

Compare user cohorts across behavioral dimensions.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cohort_a` | int | Yes | First cohort ID |
| `cohort_b` | int | Yes | Second cohort ID |
| `events` | list[string] | No | Events to compare |
| `from_date` | string | Yes | Start date |
| `to_date` | string | Yes | End date |

**Returns:** Side-by-side behavioral comparison

**Example prompt:** "Compare power users vs churned users"

---

## Interactive Tools (2) — Elicitation-Powered

Tools using `ctx.elicit()` for user confirmation and multi-step workflows.

### safe_large_fetch

Volume estimation with user confirmation before large fetches.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_date` | string | Yes | Start date |
| `to_date` | string | Yes | End date |
| `events` | list[string] | No | Events to fetch |

**Workflow:**

1. Estimates data volume
2. Requests user confirmation if volume is large
3. Executes fetch with progress reporting

**Example prompt:** "Safely fetch all events from the last 90 days"

---

### guided_analysis

Interactive step-by-step analysis workflow.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `goal` | string | No | Analysis goal (optional, will be asked) |

**Workflow:**

1. Asks user to define analysis goal
2. Proposes analysis approach
3. Executes queries with confirmation at each step
4. Synthesizes findings

**Example prompt:** "Help me analyze my data"
