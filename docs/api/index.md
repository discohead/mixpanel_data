# API Overview

The `mixpanel_data` Python API provides programmatic access to all library functionality.

## Import Patterns

```python
# Recommended: import with alias
import mixpanel_data as mp

ws = mp.Workspace()
result = ws.segmentation(...)

# Direct imports
from mixpanel_data import Workspace, FetchResult, MixpanelDataError

# Auth utilities
from mixpanel_data.auth import ConfigManager, Credentials
```

## Core Components

### Workspace

The main entry point for all operations:

- **Discovery** — Explore events, properties, funnels, cohorts
- **Fetching** — Download events and profiles to local storage
- **Local Queries** — SQL queries against DuckDB
- **Live Queries** — Real-time analytics from Mixpanel API
- **Introspection** — Examine local tables and schemas

[View Workspace API](workspace.md)

### Auth Module

Credential and account management:

- **ConfigManager** — Manage accounts in config file
- **Credentials** — Credential container with secrets
- **AccountInfo** — Account metadata (without secrets)

[View Auth API](auth.md)

### Exceptions

Structured error handling:

- **MixpanelDataError** — Base exception
- **APIError** — HTTP/API errors
- **ConfigError** — Configuration errors
- **TableExistsError** / **TableNotFoundError** — Storage errors

[View Exceptions](exceptions.md)

### Result Types

Typed results for all operations:

- **FetchResult** — Fetch operation results
- **SegmentationResult** — Time-series data
- **FunnelResult** — Funnel conversion data
- **RetentionResult** — Retention cohort data
- And many more...

[View Result Types](types.md)

## Type Aliases

The library exports these type aliases:

```python
from mixpanel_data import CountType, HourDayUnit, TimeUnit

# CountType: Literal["general", "unique", "average", "median", "min", "max"]
# HourDayUnit: Literal["hour", "day"]
# TimeUnit: Literal["day", "week", "month", "quarter", "year"]
```

## Complete API Reference

- [Workspace](workspace.md) — Main facade class
- [Auth](auth.md) — Authentication and configuration
- [Exceptions](exceptions.md) — Error handling
- [Result Types](types.md) — All result dataclasses
