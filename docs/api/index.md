# API Overview

The `mixpanel_headless` Python API provides programmatic access to all library functionality.

!!! tip "Explore on DeepWiki"
    🤖 **[Python API Reference →](https://deepwiki.com/mixpanel/mixpanel-headless/7.2-python-api-reference)**

    Ask questions about API methods, explore usage patterns, or get help with specific functionality.

## Import Patterns

```python
# Recommended: import with alias
import mixpanel_headless as mp

ws = mp.Workspace()
result = ws.query("Login", math="unique", last=30)

# Direct imports
from mixpanel_headless import Workspace, MixpanelHeadlessError

# Insights Query types
from mixpanel_headless import (
    Metric, Filter, Formula, GroupBy, QueryResult,
    MathType, PerUserAggregation, FilterPropertyType,
)

# Cohort Query types (cross-engine)
from mixpanel_headless import (
    CohortBreakdown, CohortMetric,
    CohortDefinition, CohortCriteria,
)

# Advanced Query types (cross-engine)
from mixpanel_headless import TimeComparison, FrequencyBreakdown, FrequencyFilter

# Retention Query types
from mixpanel_headless import RetentionEvent, RetentionQueryResult

# Flow Query types
from mixpanel_headless import FlowStep, FlowTreeNode, FlowQueryResult

# User Profile Query types
from mixpanel_headless import UserQueryResult

# Auth surface — recommended top-level imports
from mixpanel_headless import (
    Account, ServiceAccount, OAuthBrowserAccount, OAuthTokenAccount,
    Session, Project, WorkspaceRef, Region,
    AccountSummary, AccountTestResult, OAuthLoginResult, Target,
)
# Account/Session/WorkspaceRef/account variants are also available from
# mixpanel_headless.auth_types (single source of truth for the auth subsystem);
# the top-level form is canonical throughout the docs.

# Low-level types live only under mixpanel_headless.auth_types
from mixpanel_headless.auth_types import (
    OAuthTokens, OAuthClientInfo, TokenResolver, OnDiskTokenResolver,
    BridgeFile, load_bridge, ActiveSession,
)

# Functional namespaces
from mixpanel_headless import accounts, session, targets

# OAuth and workspace exceptions
from mixpanel_headless import OAuthError, WorkspaceScopeError

# App API types
from mixpanel_headless import PublicWorkspace, CursorPagination, PaginatedResponse

# Entity CRUD types
from mixpanel_headless import (
    Dashboard, CreateDashboardParams, UpdateDashboardParams,
    Bookmark, CreateBookmarkParams, UpdateBookmarkParams,
    Cohort, CreateCohortParams, UpdateCohortParams,
)

# Data governance types
from mixpanel_headless import (
    EventDefinition, UpdateEventDefinitionParams,
    DropFilter, CreateDropFilterParams,
    CustomProperty, CreateCustomPropertyParams,
    LookupTable, UploadLookupTableParams,
)

# Schema governance types
from mixpanel_headless import (
    SchemaEntry, BulkCreateSchemasParams,
    SchemaEnforcementConfig, AuditResponse,
    DataVolumeAnomaly, EventDeletionRequest,
)
```

## Core Components

### Workspace

The main entry point for all operations:

- **Discovery** — Explore events, properties, funnels, cohorts
- **Insights Queries** — Typed analytics queries using the Insights engine (`query()`)
- **Funnel Queries** — Typed funnel conversion analysis (`query_funnel()`)
- **Retention Queries** — Typed retention analysis with event pairs (`query_retention()`)
- **Flow Queries** — Typed flow path analysis (`query_flow()`)
- **User Profile Queries** — Typed user profile queries with filtering, sorting, and aggregation (`query_user()`)
- **Live Queries** — Legacy analytics endpoints (segmentation, funnels, retention, JQL)
- **Streaming** — Stream events and profiles directly from Mixpanel (ETL, pipelines)
- **Entity CRUD & Data Governance** — Create, read, update, delete dashboards, reports, cohorts, feature flags, experiments, plus Lexicon definitions, drop filters, custom properties, custom events, lookup tables, schema registry, schema enforcement, data auditing, volume anomalies, and event deletion requests

[View Workspace API](workspace.md)

### Auth Surface

Three first-class account types and three functional namespaces. Most are re-exported from `mixpanel_headless`; a few low-level types live under `mixpanel_headless.auth_types`:

- **`Account`** — Discriminated union over `ServiceAccount` (Basic Auth), `OAuthBrowserAccount` (PKCE flow, auto-refreshed), `OAuthTokenAccount` (static bearer for CI/agents)
- **`Session` / `Project` / `WorkspaceRef`** — Immutable resolved-state types (top-level)
- **`ActiveSession`** — Persisted `[active]`-block snapshot (only from `mixpanel_headless.auth_types`)
- **`mp.accounts`** — Account lifecycle: `add`, `list`, `use`, `show`, `test`, `login`, `logout`, `token`, `export_bridge`, `remove_bridge`, `update`, `remove`
- **`mp.session`** — Read/write the persisted `[active]` block: `show`, `use`
- **`mp.targets`** — Saved (account, project, optional workspace) cursor positions: `list`, `add`, `use`, `show`, `remove`
- **`AccountSummary` / `AccountTestResult` / `OAuthLoginResult` / `Target`** — Result types
- **`OAuthTokens`** — Low-level token type, available from `mixpanel_headless.auth_types`
- **`BridgeFile` / `load_bridge`** — Cowork bridge v2 integration, available from `mixpanel_headless.auth_types`

[View Auth API](auth.md)

### Exceptions

Structured error handling:

- **MixpanelHeadlessError** — Base exception
- **APIError** — HTTP/API errors
- **ConfigError** — Configuration errors
- **OAuthError** — OAuth authentication errors
- **WorkspaceScopeError** — Workspace resolution errors

[View Exceptions](exceptions.md)

### Result Types

Typed results for all operations:

- **QueryResult** — Insights query results (from `query()`)
- **Metric**, **Filter**, **Formula**, **GroupBy** — Query building blocks
- **CohortBreakdown**, **CohortMetric** — Cohort-scoped query types (cross-engine)
- **TimeComparison**, **FrequencyBreakdown**, **FrequencyFilter** — Advanced cross-engine query types
- **CohortDefinition**, **CohortCriteria** — Inline cohort definition builder
- **FunnelQueryResult**, **FunnelStep**, **Exclusion** — Typed funnel results
- **RetentionQueryResult**, **RetentionEvent**, **RetentionAlignment**, **RetentionMode**, **RetentionMathType** — Typed retention results
- **FlowQueryResult**, **FlowStep**, **FlowTreeNode** — Typed flow analysis results
- **UserQueryResult** — Typed user profile query results
- **SegmentationResult** — Time-series data (legacy)
- **FunnelResult** — Funnel conversion data (legacy)
- **RetentionResult** — Retention cohort data (legacy)
- **Dashboard**, **Bookmark**, **Cohort** — Entity models for CRUD operations
- **EventDefinition**, **DropFilter**, **CustomProperty**, **LookupTable** — Data governance models
- **SchemaEntry**, **SchemaEnforcementConfig**, **AuditResponse**, **DataVolumeAnomaly**, **EventDeletionRequest** — Schema governance models
- And many more...

[View Result Types](types.md)

## Type Aliases

The library exports these type aliases:

```python
from mixpanel_headless import CountType, HourDayUnit, TimeUnit, FilterDateUnit
from mixpanel_headless import FilterOperator, FlowCountType, FlowChartType

# CountType: Literal["general", "unique", "average", "median", "min", "max"]
# HourDayUnit: Literal["hour", "day"]
# TimeUnit: Literal["day", "week", "month", "quarter", "year"]
# FilterDateUnit: Literal["hour", "day", "week", "month"]
# FilterOperator: Literal[26 operator strings — see _literal_types.py]
# FlowCountType: Literal["unique", "total", "session"]
# FlowChartType: Literal["sankey", "paths", "tree"]
```

## Complete API Reference

- [Workspace](workspace.md) — Main facade class
- [Auth](auth.md) — Authentication and configuration
- [Exceptions](exceptions.md) — Error handling
- [Result Types](types.md) — All result dataclasses
