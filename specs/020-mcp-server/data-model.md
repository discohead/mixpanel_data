# Data Model: MCP Server for mixpanel_data

**Feature Branch**: `020-mcp-server`
**Created**: 2026-01-12
**Source**: [spec.md](spec.md) Key Entities section

## Entity Definitions

### Workspace

The central analytics session containing connection to Mixpanel and local database state.

| Attribute | Type | Description |
|-----------|------|-------------|
| `project_id` | `int` | Mixpanel project identifier |
| `region` | `Literal["us", "eu", "in"]` | Data residency region |
| `db_path` | `Path \| None` | Path to DuckDB file (None = in-memory) |
| `tables` | `list[TableInfo]` | Locally stored tables |

**Lifecycle**: Created at MCP server startup via lifespan pattern. Persists for session duration.

**Relationships**:
- Contains zero or more `Table` instances
- Connects to one Mixpanel project
- Manages one DuckDB connection

---

### Event

A tracked user action with name, timestamp, distinct_id, and properties.

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Event name (e.g., "signup", "purchase") |
| `time` | `datetime` | When the event occurred |
| `distinct_id` | `str` | User identifier |
| `insert_id` | `str \| None` | Deduplication key |
| `properties` | `dict[str, Any]` | Event-specific attributes |

**Source**: Mixpanel Export API or local DuckDB table

**Relationships**:
- Has many `Property` instances (embedded as JSON)
- Belongs to one user (via `distinct_id`)

---

### Property

A key-value attribute attached to an event or user profile.

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Property key |
| `type` | `Literal["string", "number", "boolean", "datetime", "list", "object"]` | Value type |
| `description` | `str \| None` | Human-readable description |
| `sample_values` | `list[Any]` | Example values from data |

**Source**: Mixpanel Schema API

**Relationships**:
- Belongs to one `Event` (event properties) or user profile (profile properties)

---

### Funnel

A saved sequence of events measuring conversion through steps.

| Attribute | Type | Description |
|-----------|------|-------------|
| `funnel_id` | `int` | Unique identifier |
| `name` | `str` | Human-readable name |
| `steps` | `list[FunnelStep]` | Ordered conversion steps |
| `created_at` | `datetime` | When funnel was created |

**Source**: Mixpanel Funnels API

**Relationships**:
- Has many `FunnelStep` instances (ordered)
- Each step references an `Event` name

---

### FunnelStep

A single step within a funnel definition.

| Attribute | Type | Description |
|-----------|------|-------------|
| `event` | `str` | Event name for this step |
| `selector` | `str \| None` | Optional property filter |
| `order` | `int` | Step position (0-indexed) |

---

### Cohort

A saved group of users defined by criteria.

| Attribute | Type | Description |
|-----------|------|-------------|
| `cohort_id` | `int` | Unique identifier |
| `name` | `str` | Human-readable name |
| `description` | `str \| None` | What this cohort represents |
| `count` | `int` | Number of users in cohort |
| `created_at` | `datetime` | When cohort was created |

**Source**: Mixpanel Cohorts API

**Relationships**:
- Contains many users (by `distinct_id`)

---

### Bookmark

A saved report configuration (insights, flows, etc.).

| Attribute | Type | Description |
|-----------|------|-------------|
| `bookmark_id` | `int` | Unique identifier |
| `name` | `str` | Human-readable name |
| `report_type` | `str` | Type of report (insights, funnels, etc.) |
| `url` | `str` | Deep link to report in Mixpanel UI |
| `created_at` | `datetime` | When bookmark was created |

**Source**: Mixpanel Bookmarks API

---

### Table

A locally stored collection of fetched events or profiles.

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Table name in DuckDB |
| `type` | `Literal["events", "profiles"]` | What data the table contains |
| `row_count` | `int` | Number of rows |
| `size_bytes` | `int` | Storage size |
| `created_at` | `datetime` | When table was created |
| `date_range` | `tuple[date, date] \| None` | For events: date range covered |

**Storage**: DuckDB database (in-memory or file-based)

**Relationships**:
- Contains many `Event` or profile records
- Belongs to one `Workspace`

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Workspace                                │
│  (MCP Server Session)                                           │
├─────────────────────────────────────────────────────────────────┤
│  project_id: int                                                │
│  region: "us" | "eu" | "in"                                     │
│  db_path: Path | None                                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ contains
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                          Table                                   │
│  (Local DuckDB Storage)                                         │
├─────────────────────────────────────────────────────────────────┤
│  name: str                                                      │
│  type: "events" | "profiles"                                    │
│  row_count: int                                                 │
│  size_bytes: int                                                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ stores
                             ▼
┌──────────────────────────────────┐    ┌─────────────────────────┐
│             Event                │    │       Property          │
├──────────────────────────────────┤    ├─────────────────────────┤
│  name: str                       │◄───│  name: str              │
│  time: datetime                  │    │  type: str              │
│  distinct_id: str                │    │  sample_values: list    │
│  properties: dict                │    └─────────────────────────┘
└──────────────────────────────────┘

┌──────────────────────────────────┐    ┌─────────────────────────┐
│            Funnel                │    │      FunnelStep         │
├──────────────────────────────────┤    ├─────────────────────────┤
│  funnel_id: int                  │◄───│  event: str             │
│  name: str                       │    │  selector: str | None   │
│  steps: list[FunnelStep]         │    │  order: int             │
│  created_at: datetime            │    └─────────────────────────┘
└──────────────────────────────────┘

┌──────────────────────────────────┐    ┌─────────────────────────┐
│            Cohort                │    │        Bookmark         │
├──────────────────────────────────┤    ├─────────────────────────┤
│  cohort_id: int                  │    │  bookmark_id: int       │
│  name: str                       │    │  name: str              │
│  count: int                      │    │  report_type: str       │
│  created_at: datetime            │    │  url: str               │
└──────────────────────────────────┘    └─────────────────────────┘
```

## MCP Protocol Mapping

| Entity | MCP Concept | URI Pattern |
|--------|-------------|-------------|
| Event schema | Resource | `schema://events` |
| Property schema | Resource | `schema://properties/{event}` |
| Funnel list | Resource | `schema://funnels` |
| Cohort list | Resource | `schema://cohorts` |
| Table list | Resource | `workspace://tables` |
| Event query | Tool | `segmentation`, `funnel`, `retention` |
| Data fetch | Tool | `fetch_events`, `fetch_profiles` |
| SQL query | Tool | `sql`, `sql_scalar` |
