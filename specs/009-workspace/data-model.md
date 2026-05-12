# Data Model: Workspace Facade

**Feature**: 009-workspace
**Date**: 2025-12-23

## Overview

The Workspace facade introduces no new persistent data models. It orchestrates existing entities from the underlying services. This document describes the Workspace class structure and its relationships to existing types.

---

## Primary Entity: Workspace

The `Workspace` class is the unified entry point for all Mixpanel data operations.

### Instance Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `_credentials` | `Credentials | None` | Resolved authentication (None for opened workspaces) |
| `_account_name` | `str | None` | Named account used (for info()) |
| `_storage` | `StorageEngine` | DuckDB storage instance |
| `_api_client` | `MixpanelAPIClient | None` | Lazy-initialized HTTP client |
| `_discovery` | `DiscoveryService | None` | Lazy-initialized discovery service |
| `_fetcher` | `FetcherService | None` | Lazy-initialized fetcher service |
| `_live_query` | `LiveQueryService | None` | Lazy-initialized query service |
| `_config_manager` | `ConfigManager` | For credential resolution |

### State Transitions

```
                 ┌──────────────┐
                 │   __init__   │
                 └──────┬───────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   Workspace   │ │   ephemeral   │ │     open      │
│  (persistent) │ │   (context)   │ │  (query-only) │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                 │                 │
        │                 │                 │
        ▼                 ▼                 ▼
┌─────────────────────────────────────────────────┐
│                    ACTIVE                        │
│  - All methods available (or subset for open)   │
│  - Services initialized on first use            │
└────────────────────────┬────────────────────────┘
                         │
                         │ close() or __exit__
                         ▼
                 ┌───────────────┐
                 │    CLOSED     │
                 │  - Resources  │
                 │   released    │
                 └───────────────┘
```

### Validation Rules

| Rule | Enforcement |
|------|-------------|
| Credentials required for API operations | `_require_api_client()` raises ConfigError |
| Storage required for all operations | Always created at construction |
| Table name required for drop/schema | Raises TableNotFoundError if missing |
| From/to dates required for fetch | Enforced by method signatures |

---

## Supporting Entity: WorkspaceInfo

Returned by `Workspace.info()`. Already defined in `types.py`.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `path` | `Path | None` | Database file path (None for ephemeral) |
| `project_id` | `str` | Mixpanel project ID |
| `region` | `str` | Data residency region (us, eu, in) |
| `account` | `str | None` | Named account used (None if from env) |
| `tables` | `list[str]` | Table names in the database |
| `size_mb` | `float` | Database file size (0.0 for ephemeral) |
| `created_at` | `datetime | None` | Database creation time |

### Computed From

```python
WorkspaceInfo(
    path=self._storage.path,
    project_id=self._credentials.project_id if self._credentials else "unknown",
    region=self._credentials.region if self._credentials else "unknown",
    account=self._account_name,
    tables=[t.name for t in self._storage.list_tables()],
    size_mb=self._storage.path.stat().st_size / 1_000_000 if self._storage.path else 0.0,
    created_at=self._get_db_created_at(),
)
```

---

## Existing Entities (Delegated)

The Workspace delegates to these existing types without modification:

### From `_internal/config.py`

| Entity | Description |
|--------|-------------|
| `Credentials` | Frozen Pydantic model with username, secret (SecretStr), project_id, region |
| `ConfigManager` | TOML-based account management |
| `AccountInfo` | Account metadata (name, username, project_id, region, is_default) |

### From `types.py`

| Entity | Returned By |
|--------|-------------|
| `FetchResult` | `fetch_events()`, `fetch_profiles()` |
| `SegmentationResult` | `segmentation()` |
| `FunnelResult` | `funnel()` |
| `RetentionResult` | `retention()` |
| `JQLResult` | `jql()` |
| `EventCountsResult` | `event_counts()` |
| `PropertyCountsResult` | `property_counts()` |
| `ActivityFeedResult` | `activity_feed()` |
| `InsightsResult` | `insights()` |
| `FrequencyResult` | `frequency()` |
| `NumericBucketResult` | `segmentation_numeric()` |
| `NumericSumResult` | `segmentation_sum()` |
| `NumericAverageResult` | `segmentation_average()` |
| `FunnelInfo` | `funnels()` |
| `SavedCohort` | `cohorts()` |
| `TopEvent` | `top_events()` |
| `TableInfo` | `tables()` |
| `TableSchema` | `schema()` |
| `ColumnInfo` | Part of TableSchema |

### From `exceptions.py`

| Exception | Raised When |
|-----------|-------------|
| `ConfigError` | Credential resolution fails |
| `AccountNotFoundError` | Named account doesn't exist |
| `AuthenticationError` | API credentials invalid |
| `RateLimitError` | Mixpanel rate limit exceeded |
| `QueryError` | SQL or API query fails |
| `TableExistsError` | Fetch to existing table |
| `TableNotFoundError` | Drop/schema for missing table |

---

## Entity Relationships

```
┌─────────────────────────────────────────────────────────────────┐
│                         Workspace                                │
│                                                                  │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────────┐  │
│  │ Credentials │  │  StorageEngine   │  │ MixpanelAPIClient  │  │
│  │  (frozen)   │  │   (required)     │  │    (optional)      │  │
│  └─────────────┘  └──────────────────┘  └────────────────────┘  │
│                           │                      │               │
│                           │                      │               │
│                           ▼                      ▼               │
│               ┌───────────────────────────────────────────────┐ │
│               │               Services (lazy)                  │ │
│               │  DiscoveryService  FetcherService  LiveQuery  │ │
│               └───────────────────────────────────────────────┘ │
│                           │                                      │
│                           ▼                                      │
│               ┌───────────────────────────────────────────────┐ │
│               │            Return Types                        │ │
│               │  FetchResult  SegmentationResult  TableInfo   │ │
│               │  FunnelResult  RetentionResult  WorkspaceInfo │ │
│               └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## No Database Schema Changes

The Workspace facade does not modify the DuckDB schema. Tables created by FetcherService follow the existing schema:

**Events Table**:
- `event_name` (VARCHAR NOT NULL)
- `event_time` (TIMESTAMP NOT NULL)
- `distinct_id` (VARCHAR NOT NULL)
- `insert_id` (VARCHAR PRIMARY KEY)
- `properties` (JSON)

**Profiles Table**:
- `distinct_id` (VARCHAR PRIMARY KEY)
- `properties` (JSON)
- `last_seen` (TIMESTAMP)

**_metadata Table** (internal):
- `table_name` (VARCHAR PRIMARY KEY)
- `type` (VARCHAR NOT NULL)
- `fetched_at` (TIMESTAMP NOT NULL)
- `from_date` (DATE)
- `to_date` (DATE)
- `row_count` (INTEGER NOT NULL)
