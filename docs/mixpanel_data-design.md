# mixpanel_data Project Design Document

> A Python library for working with Mixpanel data, designed for AI coding agents and data analysis workflows.

## Executive Summary

### Problem

AI coding agents consume context window tokens when receiving Mixpanel API responses. A single query can return 30KB of JSON, leaving less room for reasoning and iteration.

### Solution

`mixpanel_data` enables agents to fetch data once, store it locally in DuckDB, and query repeatedly without consuming additional context. Data lives outside the context window; only precise answers flow back in.

### Core Capabilities

1. **Local Data Store**: Fetch events/profiles from Mixpanel, store in DuckDB, query with SQL
2. **Live Query Access**: Run Mixpanel reports (segmentation, funnels, retention) directly
3. **Data Discovery**: Introspect events, properties, and values before querying
4. **Python Library**: Import and use programmatically in scripts and notebooks
5. **CLI**: Compose into Unix pipelines, invoke from agents without Python

### Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | DuckDB/Pandas ecosystem |
| CLI | Typer | Type hints, auto-generated help |
| Output | Rich | Tables, progress bars |
| Validation | Pydantic | API response validation |
| Database | DuckDB | Embedded, analytical, JSON support |
| HTTP | httpx | Async support, connection pooling |

---

## Design Principles

**Library-First**: CLI wraps library functions with argument parsing—nothing more. Every capability is accessible programmatically.

**Agent-Native**: Non-interactive commands. Structured output (JSON, CSV). Composable into Unix pipelines.

**Context Window Efficiency**: Fetch once, query many times. Return precise answers, not raw dumps. Introspection before querying.

**Two Data Paths**: Live queries for quick answers; local storage for iterative analysis.

**Unix Philosophy**: Do one thing well. Compose with other tools. Exit with meaningful codes.

**Explicit Over Implicit**: No global state. Table creation fails if table exists. Destruction requires explicit `drop()`.

**Secure by Default**: Credentials in config file or environment variables, never in code.

---

## System Architecture

### Pattern: Layered Architecture with Facade

The `Workspace` class serves as a facade providing a unified interface. Internally, layers have single responsibilities and depend only on layers below.

```
┌─────────────────────────────────────────────────────────┐
│                      CLI Layer                          │
│                 (Typer commands, I/O)                   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   Public API Layer                      │
│               (Workspace, auth module)                  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Service Layer                        │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│   │ Discovery  │  │  Fetcher   │  │ LiveQuery  │       │
│   │  Service   │  │  Service   │  │  Service   │       │
│   └────────────┘  └────────────┘  └────────────┘       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 Infrastructure Layer                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │  Config  │  │   API    │  │ Storage  │  │ Result │  │
│  │ Manager  │  │  Client  │  │  Engine  │  │ Types  │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Components | Responsibility |
|-------|------------|----------------|
| CLI | Typer commands, formatters | Argument parsing, output formatting |
| Public API | Workspace, auth module | Unified interface, service orchestration |
| Service | Discovery, Fetcher, LiveQuery | Domain logic, API/storage coordination |
| Infrastructure | ConfigManager, APIClient, StorageEngine | Credentials, HTTP, database operations |

---

## Component Specifications

### ConfigManager

**Responsibility**: Credential storage, resolution, and validation. Owns config file format and environment variable precedence. No knowledge of HTTP or Mixpanel.

```python
class ConfigManager:
    def __init__(self, config_path: Path | None = None): ...
    def resolve_credentials(self, account: str | None = None) -> Credentials: ...
    def list_accounts(self) -> list[AccountInfo]: ...
    def add_account(self, name: str, username: str, secret: str, 
                    project_id: str, region: str) -> None: ...
    def remove_account(self, name: str) -> None: ...
    def set_default(self, name: str) -> None: ...
    def get_account(self, name: str) -> AccountInfo: ...

@dataclass(frozen=True)
class Credentials:
    username: str
    secret: str
    project_id: str
    region: str
```

**Credential Resolution Order**:
1. Environment variables (MP_USERNAME, MP_SECRET, MP_PROJECT_ID, MP_REGION)
2. Named account from config file (if `account` parameter specified)
3. Default account from config file

**Config File Format** (`~/.mp/config.toml`):
```toml
default = "production"

[accounts.production]
username = "sa_abc123..."
secret = "..."
project_id = "12345"
region = "us"

[accounts.staging]
username = "sa_xyz789..."
secret = "..."
project_id = "67890"
region = "eu"
```

### MixpanelAPIClient

**Responsibility**: HTTP communication with Mixpanel including authentication, regional endpoint routing, rate limiting, and response parsing. No knowledge of local storage.

```python
class MixpanelAPIClient:
    def __init__(self, credentials: Credentials): ...
    
    # Low-level HTTP
    def get(self, endpoint: str, params: dict | None = None) -> Any: ...
    def post(self, endpoint: str, data: dict | None = None) -> Any: ...
    
    # Export API (streaming)
    def export_events(self, from_date: str, to_date: str, 
                      events: list[str] | None = None,
                      where: str | None = None,
                      on_batch: Callable[[list[dict]], None] | None = None
                      ) -> Iterator[dict]: ...
    def export_profiles(self, where: str | None = None,
                        on_batch: Callable[[list[dict]], None] | None = None
                        ) -> Iterator[dict]: ...
    
    # Discovery APIs
    def get_events(self) -> list[str]: ...
    def get_event_properties(self, event: str) -> list[str]: ...
    def get_property_values(self, event: str, prop: str, limit: int) -> list[str]: ...

    # Discovery APIs (Phase 007 enhancements)
    def list_funnels(self) -> list[dict]: ...
    def list_cohorts(self) -> list[dict]: ...
    def get_top_events(self, type: str = "general", limit: int | None = None) -> dict: ...

    # Query APIs
    def segmentation(self, ...) -> dict: ...
    def funnel(self, ...) -> dict: ...
    def retention(self, ...) -> dict: ...
    def jql(self, script: str, params: dict | None = None) -> list: ...

    # Query APIs (Phase 007 enhancements)
    def event_counts(self, events: list[str], from_date: str, to_date: str, ...) -> dict: ...
    def property_counts(self, event: str, property_name: str, from_date: str, to_date: str, ...) -> dict: ...

    # Query APIs (Phase 008 enhancements)
    def activity_feed(self, distinct_ids: list[str], ...) -> dict: ...
    def insights(self, bookmark_id: int) -> dict: ...
    def frequency(self, from_date: str, to_date: str, unit: str, addiction_unit: str, ...) -> dict: ...
    def segmentation_numeric(self, event: str, from_date: str, to_date: str, on: str, ...) -> dict: ...
    def segmentation_sum(self, event: str, from_date: str, to_date: str, on: str, ...) -> dict: ...
    def segmentation_average(self, event: str, from_date: str, to_date: str, on: str, ...) -> dict: ...
```

**Regional Endpoints**:

| Region | Ingestion | Query | Export |
|--------|-----------|-------|--------|
| US | api.mixpanel.com | mixpanel.com/api | data.mixpanel.com |
| EU | api-eu.mixpanel.com | eu.mixpanel.com/api | data-eu.mixpanel.com |
| India | api-in.mixpanel.com | in.mixpanel.com/api | data-in.mixpanel.com |

**Rate Limiting**: Exponential backoff with jitter on 429 responses.

### StorageEngine

**Responsibility**: DuckDB database lifecycle, schema management, query execution. No knowledge of Mixpanel APIs.

```python
class StorageEngine:
    def __init__(self, path: Path | None = None): ...
    
    @classmethod
    def ephemeral(cls) -> StorageEngine: ...
    
    @classmethod
    def open_existing(cls, path: Path) -> StorageEngine: ...
    
    # Table management
    def create_events_table(self, name: str, data: Iterator[dict],
                            metadata: TableMetadata) -> int: ...
    def create_profiles_table(self, name: str, data: Iterator[dict],
                              metadata: TableMetadata) -> int: ...
    def drop_table(self, name: str) -> None: ...
    def table_exists(self, name: str) -> bool: ...
    
    # Query execution
    def execute(self, sql: str) -> duckdb.DuckDBPyRelation: ...
    def execute_df(self, sql: str) -> pd.DataFrame: ...
    def execute_scalar(self, sql: str) -> Any: ...
    def execute_rows(self, sql: str) -> list[tuple]: ...
    
    # Introspection
    def list_tables(self) -> list[TableInfo]: ...
    def get_schema(self, table: str) -> TableSchema: ...
    def get_metadata(self, table: str) -> TableMetadata: ...
    
    # Lifecycle
    def close(self) -> None: ...
    def cleanup(self) -> None: ...
    
    @property
    def connection(self) -> duckdb.DuckDBPyConnection: ...
    
    @property
    def path(self) -> Path | None: ...

@dataclass
class TableMetadata:
    type: Literal["events", "profiles"]
    fetched_at: datetime
    from_date: str | None = None
    to_date: str | None = None
    filter_events: list[str] | None = None
    filter_where: str | None = None
```

**Database Schema**:

Events table:
| Column | Type | Description |
|--------|------|-------------|
| event_name | VARCHAR | Name of the event |
| event_time | TIMESTAMP | When the event occurred |
| distinct_id | VARCHAR | User identifier |
| insert_id | VARCHAR | Unique event identifier |
| properties | JSON | All event properties |

Profiles table:
| Column | Type | Description |
|--------|------|-------------|
| distinct_id | VARCHAR | User identifier |
| properties | JSON | All profile properties |
| last_seen | TIMESTAMP | Last activity timestamp |

Metadata table (`_metadata`):
| Column | Type | Description |
|--------|------|-------------|
| table_name | VARCHAR | Name of fetched table |
| type | VARCHAR | "events" or "profiles" |
| fetched_at | TIMESTAMP | When fetch occurred |
| from_date | DATE | Start of date range |
| to_date | DATE | End of date range |
| row_count | INTEGER | Number of rows |

### Service Layer

**DiscoveryService**: Retrieves schema information from Mixpanel.

```python
class DiscoveryService:
    def __init__(self, api_client: MixpanelAPIClient): ...

    # Event/property discovery (cached)
    def list_events(self) -> list[str]: ...
    def list_properties(self, event: str) -> list[str]: ...
    def list_property_values(self, event: str, prop: str,
                             limit: int = 100) -> list[str]: ...

    # Resource discovery (Phase 007 enhancements)
    def list_funnels(self) -> list[FunnelInfo]: ...  # Cached
    def list_cohorts(self) -> list[SavedCohort]: ...  # Cached
    def list_top_events(self, type: Literal["general", "average", "unique"] = "general",
                        limit: int | None = None) -> list[TopEvent]: ...  # NOT cached

    def clear_cache(self) -> None: ...
```

**FetcherService**: Coordinates data fetches from API to storage.

```python
class FetcherService:
    def __init__(self, api_client: MixpanelAPIClient, 
                 storage: StorageEngine): ...
    def fetch_events(self, name: str, from_date: str, to_date: str,
                     events: list[str] | None = None,
                     where: str | None = None,
                     progress_callback: Callable[[int], None] | None = None
                     ) -> FetchResult: ...
    def fetch_profiles(self, name: str, where: str | None = None,
                       progress_callback: Callable[[int], None] | None = None
                       ) -> FetchResult: ...
```

**LiveQueryService**: Executes queries against Mixpanel API.

```python
class LiveQueryService:
    def __init__(self, api_client: MixpanelAPIClient): ...

    # Core analytics queries
    def segmentation(self, ...) -> SegmentationResult: ...
    def funnel(self, ...) -> FunnelResult: ...
    def retention(self, ...) -> RetentionResult: ...
    def jql(self, script: str, params: dict | None = None) -> JQLResult: ...

    # Event breakdown queries (Phase 007 enhancements)
    def event_counts(self, events: list[str], from_date: str, to_date: str,
                     type: Literal["general", "unique", "average"] = "general",
                     unit: Literal["day", "week", "month"] = "day") -> EventCountsResult: ...
    def property_counts(self, event: str, property_name: str,
                        from_date: str, to_date: str,
                        type: Literal["general", "unique", "average"] = "general",
                        unit: Literal["day", "week", "month"] = "day",
                        values: list[str] | None = None,
                        limit: int | None = None) -> PropertyCountsResult: ...

    # Advanced analytics queries (Phase 008 enhancements)
    def activity_feed(self, distinct_ids: list[str],
                      from_date: str | None = None,
                      to_date: str | None = None) -> ActivityFeedResult: ...
    def insights(self, bookmark_id: int) -> InsightsResult: ...
    def frequency(self, from_date: str, to_date: str,
                  unit: Literal["day", "week", "month"] = "day",
                  addiction_unit: Literal["hour", "day"] = "hour",
                  event: str | None = None,
                  where: str | None = None) -> FrequencyResult: ...
    def segmentation_numeric(self, event: str, from_date: str, to_date: str,
                             on: str, unit: Literal["hour", "day"] = "day",
                             where: str | None = None,
                             type: Literal["general", "unique", "average"] = "general") -> NumericBucketResult: ...
    def segmentation_sum(self, event: str, from_date: str, to_date: str,
                         on: str, unit: Literal["hour", "day"] = "day",
                         where: str | None = None) -> NumericSumResult: ...
    def segmentation_average(self, event: str, from_date: str, to_date: str,
                             on: str, unit: Literal["hour", "day"] = "day",
                             where: str | None = None) -> NumericAverageResult: ...
```

### Workspace (Facade)

Orchestrates all services, translates high-level user intents into service calls.

```python
class Workspace:
    def __init__(
        self,
        account: str | None = None,
        project_id: str | None = None,
        region: str | None = None,
        path: str | Path | None = None,
        # Dependency injection for testing
        _config_manager: ConfigManager | None = None,
        _api_client: MixpanelAPIClient | None = None,
        _storage: StorageEngine | None = None,
    ): ...

    @classmethod
    def ephemeral(cls, account: str | None = None, ...) -> ContextManager[Workspace]: ...

    @classmethod
    def open(cls, path: str | Path) -> Workspace: ...

    # Context manager protocol
    def __enter__(self) -> Workspace: ...
    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...
    def close(self) -> None: ...

    # Discovery (delegates to DiscoveryService)
    def events(self) -> list[str]: ...
    def properties(self, event: str) -> list[str]: ...
    def property_values(self, property_name: str, *, event: str | None = None,
                        limit: int = 100) -> list[str]: ...
    def funnels(self) -> list[FunnelInfo]: ...
    def cohorts(self) -> list[SavedCohort]: ...
    def top_events(self, *, type: Literal["general", "average", "unique"] = "general",
                   limit: int | None = None) -> list[TopEvent]: ...
    def clear_discovery_cache(self) -> None: ...

    # Fetching (delegates to FetcherService)
    def fetch_events(self, name: str = "events", *, from_date: str, to_date: str,
                     events: list[str] | None = None, where: str | None = None,
                     progress: bool = True) -> FetchResult: ...
    def fetch_profiles(self, name: str = "profiles", *, where: str | None = None,
                       progress: bool = True) -> FetchResult: ...

    # Local Queries (delegates to StorageEngine)
    def sql(self, query: str) -> pd.DataFrame: ...
    def sql_scalar(self, query: str) -> Any: ...
    def sql_rows(self, query: str) -> list[tuple]: ...

    # Live Queries (delegates to LiveQueryService)
    def segmentation(self, event: str, *, from_date: str, to_date: str,
                     on: str | None = None,
                     unit: Literal["day", "week", "month"] = "day",
                     where: str | None = None) -> SegmentationResult: ...
    def funnel(self, funnel_id: int, *, from_date: str, to_date: str,
               unit: str | None = None, on: str | None = None) -> FunnelResult: ...
    def retention(self, *, born_event: str, return_event: str, from_date: str,
                  to_date: str, born_where: str | None = None,
                  return_where: str | None = None, interval: int = 1,
                  interval_count: int = 10,
                  unit: Literal["day", "week", "month"] = "day") -> RetentionResult: ...
    def jql(self, script: str, params: dict | None = None) -> JQLResult: ...
    def event_counts(self, events: list[str], *, from_date: str, to_date: str,
                     type: Literal["general", "unique", "average"] = "general",
                     unit: Literal["day", "week", "month"] = "day") -> EventCountsResult: ...
    def property_counts(self, event: str, property_name: str, *, from_date: str,
                        to_date: str,
                        type: Literal["general", "unique", "average"] = "general",
                        unit: Literal["day", "week", "month"] = "day",
                        values: list[str] | None = None,
                        limit: int | None = None) -> PropertyCountsResult: ...
    def activity_feed(self, distinct_ids: list[str], *, from_date: str | None = None,
                      to_date: str | None = None) -> ActivityFeedResult: ...
    def insights(self, bookmark_id: int) -> InsightsResult: ...
    def frequency(self, *, from_date: str, to_date: str,
                  unit: Literal["day", "week", "month"] = "day",
                  addiction_unit: Literal["hour", "day"] = "hour",
                  event: str | None = None,
                  where: str | None = None) -> FrequencyResult: ...
    def segmentation_numeric(self, event: str, *, from_date: str, to_date: str,
                             on: str, unit: Literal["hour", "day"] = "day",
                             where: str | None = None,
                             type: Literal["general", "unique", "average"] = "general"
                             ) -> NumericBucketResult: ...
    def segmentation_sum(self, event: str, *, from_date: str, to_date: str,
                         on: str, unit: Literal["hour", "day"] = "day",
                         where: str | None = None) -> NumericSumResult: ...
    def segmentation_average(self, event: str, *, from_date: str, to_date: str,
                             on: str, unit: Literal["hour", "day"] = "day",
                             where: str | None = None) -> NumericAverageResult: ...

    # Introspection
    def info(self) -> WorkspaceInfo: ...
    def tables(self) -> list[TableInfo]: ...
    def schema(self, table: str) -> TableSchema: ...

    # Table Management
    def drop(self, *names: str) -> None: ...
    def drop_all(self, type: Literal["events", "profiles"] | None = None) -> None: ...

    # Escape Hatches
    @property
    def connection(self) -> duckdb.DuckDBPyConnection: ...
    @property
    def api(self) -> MixpanelAPIClient: ...
```

---

## Public API Reference

### Workspace Methods

**Construction**:
| Method | Description |
|--------|-------------|
| `Workspace()` | Create workspace using stored credentials |
| `Workspace.ephemeral()` | Create temporary workspace deleted on exit |
| `Workspace.open(path)` | Open existing database without credentials |

**Discovery** (queries Mixpanel API):
| Method | Description |
|--------|-------------|
| `events()` | List all event names in project |
| `properties(event)` | List all properties for an event |
| `property_values(prop, event=None, limit=100)` | List sample values for a property |
| `funnels()` | List saved funnels (cached) |
| `cohorts()` | List saved cohorts (cached) |
| `top_events(type, limit)` | List today's top events (not cached) |
| `clear_discovery_cache()` | Clear cached discovery data |

**Fetching** (API → local storage):
| Method | Description |
|--------|-------------|
| `fetch_events(name, from_date, to_date, events, where, progress)` | Fetch events into local table |
| `fetch_profiles(name, where, progress)` | Fetch profiles into local table |

**Local Queries** (queries DuckDB):
| Method | Description |
|--------|-------------|
| `sql(query)` | Execute SQL, return DataFrame |
| `sql_scalar(query)` | Execute SQL, return single value |
| `sql_rows(query)` | Execute SQL, return list of tuples |

**Live Queries** (queries Mixpanel API directly):
| Method | Description |
|--------|-------------|
| `segmentation(event, from_date, to_date, on, unit, where)` | Run segmentation query |
| `funnel(funnel_id, from_date, to_date, unit, on)` | Run funnel analysis |
| `retention(born_event, return_event, from_date, to_date, ...)` | Run retention analysis |
| `jql(script, params)` | Execute JQL query |
| `event_counts(events, from_date, to_date, type, unit)` | Multi-event time series |
| `property_counts(event, property, from_date, to_date, ...)` | Property breakdown time series |
| `activity_feed(distinct_ids, from_date, to_date)` | User event history |
| `insights(bookmark_id)` | Query saved Insights report |
| `frequency(from_date, to_date, unit, addiction_unit, ...)` | Event frequency distribution |
| `segmentation_numeric(event, from_date, to_date, on, ...)` | Numeric property bucketing |
| `segmentation_sum(event, from_date, to_date, on, ...)` | Sum numeric property over time |
| `segmentation_average(event, from_date, to_date, on, ...)` | Average numeric property over time |

**Introspection**:
| Method | Description |
|--------|-------------|
| `info()` | Get workspace summary |
| `tables()` | List all tables in local database |
| `schema(table)` | Get schema for specific table |

**Table Management**:
| Method | Description |
|--------|-------------|
| `drop(*names)` | Drop one or more tables |
| `drop_all(type=None)` | Drop all tables, optionally filtered |

**Escape Hatches**:
| Property | Description |
|----------|-------------|
| `connection` | Direct DuckDB connection access |
| `api` | Direct Mixpanel API client access |

**Lifecycle**:
| Method | Description |
|--------|-------------|
| `close()` | Close database connection and release resources |
| `__enter__()` | Context manager entry (returns self) |
| `__exit__()` | Context manager exit (calls close) |

### Result Types

```python
@dataclass(frozen=True)
class FetchResult:
    table: str              # Name of created table
    rows: int               # Number of rows fetched
    type: str               # "events" or "profiles"
    duration_seconds: float
    date_range: tuple[str, str] | None
    fetched_at: datetime

@dataclass(frozen=True)
class SegmentationResult:
    event: str
    from_date: str
    to_date: str
    unit: str
    segment_property: str | None
    total: int
    df: pd.DataFrame  # Lazy conversion

@dataclass(frozen=True)
class FunnelResult:
    funnel_id: int
    funnel_name: str
    from_date: str
    to_date: str
    conversion_rate: float  # 0-1
    steps: list[FunnelStep]
    df: pd.DataFrame

@dataclass(frozen=True)
class RetentionResult:
    born_event: str
    return_event: str
    from_date: str
    to_date: str
    unit: str
    cohorts: list[CohortInfo]
    df: pd.DataFrame

@dataclass(frozen=True)
class JQLResult:
    df: pd.DataFrame
    raw: list[Any]

# Discovery enhancement types (Phase 007)
@dataclass(frozen=True)
class FunnelInfo:
    funnel_id: int
    name: str

@dataclass(frozen=True)
class SavedCohort:
    id: int
    name: str
    count: int
    description: str
    created: str
    is_visible: bool

@dataclass(frozen=True)
class TopEvent:
    event: str
    count: int
    percent_change: float

@dataclass(frozen=True)
class EventCountsResult:
    events: list[str]
    from_date: str
    to_date: str
    unit: str
    type: str
    series: dict[str, dict[str, int]]  # {event: {date: count}}
    df: pd.DataFrame  # Lazy conversion

@dataclass(frozen=True)
class PropertyCountsResult:
    event: str
    property_name: str
    from_date: str
    to_date: str
    unit: str
    type: str
    series: dict[str, dict[str, int]]  # {value: {date: count}}
    df: pd.DataFrame  # Lazy conversion

# Advanced analytics types (Phase 008)
@dataclass(frozen=True)
class UserEvent:
    event: str
    time: datetime
    properties: dict[str, Any]

@dataclass(frozen=True)
class ActivityFeedResult:
    distinct_ids: list[str]
    from_date: str | None
    to_date: str | None
    events: list[UserEvent]
    df: pd.DataFrame  # Lazy conversion

@dataclass(frozen=True)
class InsightsResult:
    bookmark_id: int
    computed_at: str
    from_date: str
    to_date: str
    headers: list[str]
    series: dict[str, dict[str, int]]  # {event: {date: count}}
    df: pd.DataFrame  # Lazy conversion

@dataclass(frozen=True)
class FrequencyResult:
    event: str | None
    from_date: str
    to_date: str
    unit: str
    addiction_unit: str
    data: dict[str, list[int]]  # {date: [count_at_1, count_at_2, ...]}
    df: pd.DataFrame  # Lazy conversion

@dataclass(frozen=True)
class NumericBucketResult:
    event: str
    from_date: str
    to_date: str
    property_expr: str
    unit: str
    series: dict[str, dict[str, int]]  # {bucket_range: {date: count}}
    df: pd.DataFrame  # Lazy conversion

@dataclass(frozen=True)
class NumericSumResult:
    event: str
    from_date: str
    to_date: str
    property_expr: str
    unit: str
    results: dict[str, float]  # {date: sum_value}
    computed_at: str | None
    df: pd.DataFrame  # Lazy conversion

@dataclass(frozen=True)
class NumericAverageResult:
    event: str
    from_date: str
    to_date: str
    property_expr: str
    unit: str
    results: dict[str, float]  # {date: average_value}
    df: pd.DataFrame  # Lazy conversion

# Workspace types
@dataclass(frozen=True)
class WorkspaceInfo:
    path: Path | None           # Database file path (None for ephemeral)
    project_id: str             # Mixpanel project ID
    region: str                 # Data residency region (us, eu, in)
    account: str | None         # Named account used (None if from env)
    tables: list[str]           # Table names in the database
    size_mb: float              # Database file size in MB
    created_at: datetime | None # When database was created
```

### Exceptions

| Exception | Description |
|-----------|-------------|
| `MixpanelDataError` | Base exception for all library errors |
| `TableExistsError` | Table with this name already exists |
| `TableNotFoundError` | Referenced table does not exist |
| `AuthenticationError` | API credentials invalid or missing |
| `ConfigError` | Problem with config file |
| `AccountNotFoundError` | Named account doesn't exist |
| `AccountExistsError` | Account with name already exists |
| `RateLimitError` | Mixpanel rate limit exceeded |
| `QueryError` | SQL or API query failed |

---

## CLI Specification

### Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--account` | `-a` | Use specific named account |
| `--project` | `-p` | Override project ID |
| `--format` | `-f` | Output: json (default), table, csv, jsonl |
| `--quiet` | `-q` | Suppress progress/status |
| `--verbose` | `-v` | Show detailed output |

### Commands

**Authentication** (`mp auth`):
| Command | Description |
|---------|-------------|
| `mp auth list` | List configured accounts |
| `mp auth add <name>` | Add account (--username, --secret, --project, --region) |
| `mp auth remove <name>` | Remove account |
| `mp auth switch <name>` | Set default account |
| `mp auth show <name>` | Show account details (secret redacted) |
| `mp auth test [name]` | Test credentials with API call |

**Fetching** (`mp fetch`):
| Command | Description |
|---------|-------------|
| `mp fetch events [name] --from DATE --to DATE` | Fetch events (--events, --where) |
| `mp fetch profiles [name]` | Fetch profiles (--where) |

**Queries**:
| Command | Description |
|---------|-------------|
| `mp sql QUERY` | Execute SQL (--file, --scalar) |
| `mp segmentation --event E --from D --to D` | Run segmentation (--on, --unit, --where) |
| `mp funnel ID --from D --to D` | Run funnel (--unit, --on) |
| `mp retention --born E --return E --from D --to D` | Run retention |
| `mp jql FILE` | Execute JQL (--code, --param) |

**Inspection**:
| Command | Description |
|---------|-------------|
| `mp events` | List event names in Mixpanel |
| `mp properties EVENT` | List properties for event |
| `mp values EVENT PROP` | List sample values |
| `mp info` | Show workspace info |
| `mp tables` | List local tables |
| `mp schema TABLE` | Show table schema |
| `mp drop TABLE...` | Drop tables (--all, --type, --force) |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Authentication error |
| 3 | Invalid arguments |
| 4 | Resource not found |
| 5 | Rate limit exceeded |
| 130 | Interrupted (Ctrl+C) |

---

## Data Flow Diagrams

### Fetch Events Flow

```
Workspace.fetch_events(name, from_date, to_date, events, where)
    │
    ├─► storage.table_exists(name) → raises TableExistsError if true
    │
    ▼
FetcherService.fetch_events(...)
    │
    ├─► api_client.export_events(...) → Iterator[dict] (streaming)
    │
    └─► storage.create_events_table(name, iterator, metadata)
            └─► Batch inserts to DuckDB
    │
    ▼
Returns FetchResult
```

### SQL Query Flow

```
Workspace.sql(query)
    │
    ▼
StorageEngine.execute_df(query)
    │
    ▼
DuckDB Connection
    │
    ▼
Returns pd.DataFrame
```

### Live Query Flow

```
Workspace.segmentation(event, from_date, to_date, ...)
    │
    ▼
LiveQueryService.segmentation(...)
    │
    ▼
api_client.segmentation(...) → Transform response
    │
    ▼
Returns SegmentationResult
```

---

## Package Structure

```
mixpanel_data/
├── __init__.py              # Public API exports
├── workspace.py             # Workspace class
├── auth.py                  # Public auth module
├── exceptions.py            # All exception classes
├── types.py                 # Result types, dataclasses
│
├── _internal/               # Private implementation
│   ├── config.py            # ConfigManager
│   ├── api_client.py        # MixpanelAPIClient
│   ├── storage.py           # StorageEngine
│   ├── services/
│   │   ├── discovery.py     # DiscoveryService
│   │   ├── fetcher.py       # FetcherService
│   │   └── live_query.py    # LiveQueryService
│   └── utils.py
│
└── cli/
    ├── main.py              # Typer app entry point
    ├── commands/
    │   ├── auth.py
    │   ├── fetch.py
    │   ├── query.py
    │   └── inspect.py
    └── formatters.py        # Output formatting
```

---

## Key Design Decisions

**Immutable Credentials**: Resolved once at Workspace construction, stored in frozen dataclass. Prevents mutation bugs.

**Streaming Ingestion**: API client returns iterators; storage engine accepts iterators. Enables processing datasets larger than memory.

**Explicit Table Management**: Tables never implicitly overwritten. `TableExistsError` if exists; must `drop()` first. Prevents data loss, makes agent behavior predictable.

**Lazy DataFrame Conversion**: Result objects store raw data internally, convert to DataFrame only when `df` property accessed. Avoids unnecessary pandas overhead.

**Dependency Injection**: Services accept dependencies as constructor arguments. Workspace constructor accepts optional private parameters for test doubles.

**JSON Property Storage**: Properties stored as JSON columns, not flattened. Accommodates Mixpanel's dynamic schema. Query with `properties->>'$.field'`.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MP_USERNAME` | Service account username |
| `MP_SECRET` | Service account secret |
| `MP_PROJECT_ID` | Project ID |
| `MP_REGION` | Data residency region (us, eu, in) |
| `MP_CONFIG_PATH` | Override config file location |
| `MP_DATA_DIR` | Override database directory |
| `MP_FORMAT` | Default output format |
| `NO_COLOR` | Disable colored output |

---

## DuckDB JSON Query Syntax

```sql
-- Extract string property
properties->>'$.country'

-- Extract numeric (must cast)
CAST(properties->>'$.amount' AS DECIMAL)

-- Nested property
properties->>'$.user.plan'

-- Filter on JSON property
WHERE properties->>'$.country' = 'US'

-- Check property exists
WHERE properties->>'$.coupon' IS NOT NULL
```

---

## Usage Examples

### Basic Analysis

```python
from mixpanel_data import Workspace

ws = Workspace()
ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")

df = ws.sql("""
    SELECT 
        DATE_TRUNC('day', event_time) as day,
        event_name,
        COUNT(*) as count
    FROM events
    GROUP BY 1, 2
    ORDER BY 1, 3 DESC
""")
```

### Ephemeral Analysis

```python
with Workspace.ephemeral() as ws:
    ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
    total = ws.sql_scalar("SELECT COUNT(*) FROM events")
# Database automatically deleted
```

### Live Query

```python
ws = Workspace()
result = ws.segmentation(
    event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31",
    on="properties.country"
)
print(f"Total: {result.total}")
result.df.head(10)
```

### CLI Workflow

```bash
# Configure
mp auth add production --username sa_xxx --secret xxx --project 12345 --region us

# Fetch
mp fetch events --from 2024-01-01 --to 2024-01-31

# Query
mp sql "SELECT event_name, COUNT(*) FROM events GROUP BY 1" --format table

# Export
mp sql "SELECT * FROM events" --format csv > events.csv
```

---

## Implementation Phases

1. **Foundation**: ConfigManager, MixpanelAPIClient, StorageEngine, exceptions, result types
2. **Core Functionality**: FetcherService, DiscoveryService, Workspace orchestration, auth module
3. **Live Queries**: LiveQueryService, segmentation/funnel/retention methods, JQL support
4. **Discovery Enhancements**: Funnels, cohorts, top events discovery; event/property counts queries
5. **Query Service Enhancements**: Advanced analytics queries (activity feed, insights, frequency, numeric aggregations)
6. **Workspace Facade**: Unified Workspace class orchestrating all services
7. **CLI**: Typer application, all command groups, formatters, progress bars
8. **Polish**: SKILL.md, documentation, integration tests, PyPI release
