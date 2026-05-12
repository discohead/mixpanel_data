# Architecture

mixpanel_headless follows a layered architecture with clear separation of concerns.

!!! tip "Explore on DeepWiki"
    🤖 **[Architecture Deep Dive →](https://deepwiki.com/mixpanel/mixpanel-headless/5-architecture)**

    Ask questions about the architecture, trace data flows, or explore component relationships interactively.

## Layer Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI Layer (Typer)                      │
│         Argument parsing, output formatting, progress       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Public API Layer                          │
│   Workspace · Account/Session · accounts/session/targets    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer                           │
│            DiscoveryService, LiveQueryService               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                       │
│            ConfigManager, MixpanelAPIClient                 │
└─────────────────────────────────────────────────────────────┘
```

## Components

### Workspace (Facade)

The `Workspace` class is the unified entry point that coordinates all services:

- **Session resolution** — Three independent axes resolved via `env > param > target > bridge > [active] > default_project`. Single resolver in `_internal/auth/resolver.py`; no silent cross-axis fallback.
- **In-session switching** — `Workspace.use(account=, project=, workspace=, target=)` returns `self` for chaining and preserves the underlying `httpx.Client` and per-account `/me` cache (O(1) per swap).
- **Service Orchestration** — Creates and manages service instances
- **Entity CRUD** — Direct App API access for dashboards, reports, cohorts (workspace-scoped) and feature flags, experiments (project-scoped)
- **Data Governance** — Schema registry, enforcement, auditing, volume anomalies, event deletion requests, Lexicon definitions, drop filters, custom properties, custom events, and lookup tables
- **Resource Management** — Context manager support for cleanup

### Services

#### DiscoveryService

Schema introspection with session-scoped caching:

- `list_events()` — All event names (cached)
- `list_properties(event)` — Properties for an event (cached per event)
- `list_property_values(property, event)` — Sample values (cached)
- `list_funnels()` — Saved funnels (cached)
- `list_cohorts()` — Saved cohorts (cached)
- `list_top_events()` — Today's top events (NOT cached, real-time)

#### LiveQueryService

Executes live analytics queries against Mixpanel Query API:

- Segmentation, funnels, retention, JQL
- Event counts, property counts
- Activity feed, saved reports, flows, frequency
- Numeric aggregations (bucket, sum, average)

### Infrastructure

#### ConfigManager

TOML-based account management at `~/.mp/config.toml` (single schema; legacy v1/v2 do not load):

- Account CRUD over `[accounts.NAME]` blocks
- Target CRUD over `[targets.NAME]` blocks
- Active-session read/write over the `[active]` block (account + optional workspace)
- Atomic writes via temp-file + rename

#### MixpanelAPIClient

HTTP client with Mixpanel-specific features:

- Service account authentication
- Regional endpoint routing (US, EU, India)
- Automatic rate limit handling with exponential backoff
- Streaming JSONL parsing for large exports

### Three-Axis Hierarchy

Auth is organized around three independent axes:

- **Account** — *who* is authenticating. Three first-class types managed through one surface: `service_account` (Basic Auth), `oauth_browser` (PKCE flow, tokens auto-refreshed), `oauth_token` (static bearer for CI/agents).
- **Project** — *which Mixpanel project* the calls run against. Lives on the active account as `default_project`; can be overridden per call.
- **Workspace** — *which workspace inside the project*. Optional; lazy-resolves to the project's default workspace on first workspace-scoped call.

Persisted (account, project, optional workspace) bundles are called **targets** and act as named cursor positions: `mp target add ecom --account team --project 3018488` then `mp target use ecom`.

## Data Paths

### Live Query Path

```
User Request → Workspace → LiveQueryService → MixpanelAPIClient → Mixpanel API
                                                      ↓
                                              Typed Result (e.g., SegmentationResult)
```

Best for:

- Real-time data needs
- One-off analysis
- Pre-computed Mixpanel reports

### Streaming Path

```
User Request → Workspace → MixpanelAPIClient → Mixpanel Export API
                                    ↓
                          Iterator[dict] (no storage)
                                    ↓
                          Process each record inline
```

Best for:

- ETL pipelines to external systems
- One-time processing without storage
- Memory-constrained environments
- Unix pipeline integration (CLI `--stdout`)

## Key Design Decisions

### Streaming Data Access

The API client returns iterators for memory-efficient processing of large datasets without loading everything into memory.

### Immutable Session

A `Session` (account + project + optional workspace) is resolved once at `Workspace` construction; `Workspace.use()` swaps in a new `Session` atomically. The `httpx.Client` and per-account `/me` cache are preserved across swaps, so cross-project iteration is O(1) per turn.

### Dependency Injection

All services accept their dependencies as constructor arguments. This enables:

- Easy testing with mocks
- Flexible composition
- Clear dependency relationships

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Language | Python 3.10+ | Type hints, modern syntax |
| CLI Framework | Typer | Declarative CLI building |
| Output Formatting | Rich | Tables, progress bars, colors |
| Validation | Pydantic | Data validation, settings |
| HTTP Client | httpx | Async-capable HTTP |

## Package Structure

```
src/mixpanel_headless/
├── __init__.py              # Public exports (Workspace, Account, Session, namespaces, exceptions, types)
├── workspace.py             # Workspace facade with Workspace.use()
├── auth_types.py            # Public auth surface (Account union, Session, Region, OAuthTokens, BridgeFile, ...)
├── accounts.py              # mp.accounts namespace (add/list/use/login/test/...)
├── session.py               # mp.session namespace (show/use)
├── targets.py               # mp.targets namespace (saved cursors)
├── exceptions.py            # Exception hierarchy (incl. AccountInUseError, WorkspaceScopeError)
├── types.py                 # Result dataclasses (SegmentationResult, AccountSummary, Target, ...)
├── py.typed                 # PEP 561 marker
├── _internal/
│   ├── config.py            # ConfigManager (single TOML schema)
│   ├── api_client.py        # MixpanelAPIClient
│   ├── me.py                # MeService + per-account MeCache
│   ├── pagination.py        # Cursor-based App API pagination
│   ├── auth/
│   │   ├── account.py       # Account variants (ServiceAccount/OAuthBrowserAccount/OAuthTokenAccount)
│   │   ├── session.py       # Session, Project, WorkspaceRef, ActiveSession
│   │   ├── resolver.py      # env > param > target > bridge > [active] resolver
│   │   ├── token_resolver.py# OnDiskTokenResolver
│   │   ├── token.py         # OAuthTokens, OAuthClientInfo
│   │   ├── flow.py          # OAuth PKCE browser flow
│   │   ├── bridge.py        # Cowork bridge file v2
│   │   ├── storage.py       # account_dir, ensure_account_dir (atomic 0o600 writes)
│   │   ├── pkce.py          # PKCE challenge generation (RFC 7636)
│   │   ├── callback_server.py # Local HTTP callback server
│   │   └── client_registration.py # Dynamic Client Registration (RFC 7591)
│   └── services/
│       ├── discovery.py     # DiscoveryService
│       └── live_query.py    # LiveQueryService
└── cli/
    ├── main.py              # Typer app + global flags (-a / -p / -w / -t)
    ├── commands/            # account / project / workspace / target / session + query / inspect / ...
    ├── formatters.py        # Output formatters
    └── utils.py             # CLI utilities
```
