# MCP Resources Reference

Resources provide read-only access to cacheable data. MCP clients can read these for context without making tool calls.

## Static Resources

### workspace://info

Workspace configuration and connection status.

**Returns**: JSON with project_id, region, account, path, size_mb, created_at, and tables.

```json
{
  "project_id": 123456,
  "region": "us",
  "account": "production",
  "path": "/path/to/workspace.duckdb",
  "size_mb": 125.5,
  "created_at": "2024-01-01T00:00:00",
  "tables": [
    {"name": "events", "row_count": 50000, "type": "events"},
    {"name": "profiles", "row_count": 1000, "type": "profiles"}
  ]
}
```

---

### workspace://tables

List of locally stored tables.

**Returns**: JSON array of table metadata with names, row counts, and types.

```json
[
  {"name": "events", "row_count": 50000, "type": "events"},
  {"name": "jan_events", "row_count": 10000, "type": "events"},
  {"name": "profiles", "row_count": 1000, "type": "profiles"}
]
```

---

### schema://events

List of event names tracked in the project.

**Returns**: JSON array of event names.

```json
["signup", "login", "purchase", "page_view", "button_click"]
```

---

### schema://funnels

Saved funnel definitions.

**Returns**: JSON array of funnel metadata with funnel_id, name, and step information.

```json
[
  {"funnel_id": 1, "name": "Signup Funnel", "steps": 3},
  {"funnel_id": 2, "name": "Purchase Funnel", "steps": 5}
]
```

---

### schema://cohorts

Saved cohort definitions.

**Returns**: JSON array of cohort metadata with cohort_id, name, and user count.

```json
[
  {"cohort_id": 1, "name": "Active Users", "count": 5000},
  {"cohort_id": 2, "name": "Premium Users", "count": 1200}
]
```

---

### schema://bookmarks

Saved report bookmarks.

**Returns**: JSON array of bookmark metadata with bookmark_id, name, type, and URL.

```json
[
  {"bookmark_id": 1, "name": "Weekly DAU", "type": "insights", "url": "..."},
  {"bookmark_id": 2, "name": "Signup Funnel", "type": "funnels", "url": "..."}
]
```

---

## Dynamic Resource Templates

These resources accept parameters in the URI path.

### analysis://retention/{event}/weekly

12-week retention curve for an event.

**Parameters**:
- `{event}`: Event name for cohort entry (born event)

**Returns**: JSON with event, period, from_date, to_date, weeks, and retention data.

**Example URI**: `analysis://retention/signup/weekly`

```json
{
  "event": "signup",
  "period": "weekly",
  "from_date": "2024-10-15",
  "to_date": "2025-01-13",
  "weeks": 12,
  "data": {
    "cohorts": [...],
    "retention_rates": [100, 45, 32, 28, 25, ...]
  }
}
```

---

### analysis://trends/{event}/{days}

Daily event counts for the specified period.

**Parameters**:
- `{event}`: Event name to analyze
- `{days}`: Number of days to look back (1-365, defaults to 30 if invalid)

**Returns**: JSON with event, days, from_date, to_date, unit, and time series data.

**Example URI**: `analysis://trends/login/30`

```json
{
  "event": "login",
  "days": 30,
  "from_date": "2024-12-14",
  "to_date": "2025-01-13",
  "unit": "day",
  "data": {
    "2024-12-14": 1234,
    "2024-12-15": 1456,
    ...
  }
}
```

---

### users://{id}/journey

User's complete event journey.

**Parameters**:
- `{id}`: User's distinct_id

**Returns**: JSON with distinct_id, period, summary, and events (last 90 days, limited to 100 events).

**Example URI**: `users://user123/journey`

```json
{
  "distinct_id": "user123",
  "period": {
    "from_date": "2024-10-15",
    "to_date": "2025-01-13"
  },
  "summary": {
    "total_events": 256,
    "unique_events": 12,
    "event_breakdown": {
      "page_view": 150,
      "button_click": 50,
      "purchase": 5
    }
  },
  "events": [...],
  "truncated": true
}
```

---

## Recipe Resources

Structured playbooks for common analytics workflows.

### recipes://weekly-review

Weekly analytics review checklist.

**Returns**: JSON with name, description, current_period, comparison_period, checklist, and report_template.

**Checklist Steps**:
1. Core Metrics Review - Compare key metrics WoW
2. Conversion Health - Review funnel performance
3. Retention Check - Analyze user return rates
4. Anomaly Detection - Look for unusual patterns
5. User Feedback - Review qualitative signals

**Suggested Tools**:
- `event_counts` for WAU comparison
- `list_funnels` and `funnel` for conversion
- `retention` for stickiness
- `diagnose_metric_drop` and `top_events` for anomalies
- `activity_feed` and `stream_events` for user sessions

---

### recipes://churn-investigation

Churn investigation playbook.

**Returns**: JSON with name, description, phases, and benchmarks.

**Investigation Phases**:
1. **Define Churn** - Establish clear churn criteria
2. **Measure Baseline** - Quantify current churn rates (D1/D7/D30 retention, weekly/monthly churn)
3. **Identify Patterns** - Find common characteristics of churned users
4. **Analyze Behavior** - Deep dive into churned user journeys
5. **Prioritize Interventions** - Identify highest-impact fixes

**Benchmarks**:
- Good D1 retention: 40-60%
- Good D7 retention: 20-30%
- Good D30 retention: 10-20%
- Acceptable monthly churn: <5% for B2B, <10% for B2C

---

## When to Use Resources vs Tools

| Use Case | Resource | Tool |
|----------|----------|------|
| Quick context lookup | `schema://events` | - |
| Cached schema data | `schema://funnels` | - |
| Standard retention curve | `analysis://retention/{event}/weekly` | - |
| Custom date range | - | `retention(...)` |
| User overview | `users://{id}/journey` | - |
| Full activity history | - | `activity_feed(...)` |
| Workflow guidance | `recipes://weekly-review` | - |
| AI-powered investigation | - | `diagnose_metric_drop(...)` |

**Resources** are best for:
- Read-only, cacheable data
- Standard time periods (last 12 weeks, last N days)
- Context gathering before analysis
- Guided workflow templates

**Tools** are best for:
- Custom parameters and date ranges
- Data modification (fetch, drop)
- Complex queries (SQL, JQL)
- Interactive workflows
