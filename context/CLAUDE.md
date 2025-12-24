# mixpanel_data Documentation

This directory contains all design documentation, specifications, and reference materials for building the `mixpanel_data` library.

## Document Hierarchy

```
docs/
├── CLAUDE.md                              # This file
├── mixpanel_data-project-brief.md         # Vision, goals, why we're building this
├── mixpanel_data-design.md                # Architecture and technical design
├── mixpanel_data-api-specification.md     # Python library API spec
├── mp-cli-api-specification.md            # CLI command specification
├── mp-cli-project-spec.md                 # Full project specification
├── MIXPANEL_DATA_MODEL_REFERENCE.md       # Mixpanel data model (events, profiles)
├── mixpanel-query-expression-language.md  # Query expression syntax
├── jql.md                                 # JQL (deprecated, maintenance mode)
└── api-docs/                              # Mixpanel API documentation
```

## Reading Order

For understanding the project:
1. **[mixpanel_data-project-brief.md](mixpanel_data-project-brief.md)** - Start here. Vision, goals, design principles
2. **[mixpanel_data-design.md](mixpanel_data-design.md)** - Architecture, layers, system design
3. **[mp-cli-project-spec.md](mp-cli-project-spec.md)** - Full specification with command hierarchy

For implementation:
1. **[mixpanel_data-api-specification.md](mixpanel_data-api-specification.md)** - Python API design
2. **[mp-cli-api-specification.md](mp-cli-api-specification.md)** - CLI commands and options
3. **[MIXPANEL_DATA_MODEL_REFERENCE.md](MIXPANEL_DATA_MODEL_REFERENCE.md)** - Data model for Pydantic/DuckDB mapping

## Key Concepts

### The Core Insight

```
MCP Approach:   Agent → API call → 30KB JSON in context → repeat → context exhausted
mp Approach:    Agent → fetch once → DuckDB → SQL queries → minimal tokens → reasoning preserved
```

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  CLI Layer (thin)                                           │
│  mp/cli/ - Typer commands, Rich output                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Public API Layer                                           │
│  Workspace class - facade for all operations                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Service Layer                                              │
│  DiscoveryService | FetcherService | LiveQueryService       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Infrastructure Layer                                       │
│  MixpanelClient (httpx) | DuckDBConnection                  │
└─────────────────────────────────────────────────────────────┘
```

### Naming Convention

| Context | Name | Example |
|---------|------|---------|
| PyPI | `mixpanel_data` | `pip install mixpanel_data` |
| Python | `mixpanel_data` | `import mixpanel_data as mp` |
| CLI | `mp` | `mp fetch events --from 2024-01-01` |

## Design Principles

1. **Library-First** - CLI wraps library; every capability is programmatic
2. **Agent-Native** - Non-interactive, structured output, composable
3. **Context Efficient** - Fetch once, query many times
4. **Two Data Paths** - Live queries (quick) vs local DB (deep analysis)
5. **Unix Philosophy** - One thing well, compose with other tools
6. **Explicit Over Implicit** - No global state, explicit table creation/deletion
7. **Secure by Default** - Credentials in config file, never in code

## Key Files by Purpose

### Python Library API
- **Workspace class** - Single entry point: `from mixpanel_data import Workspace`
- **Authentication** - `~/.mp/config.toml` with named accounts
- **Core methods**: `fetch_events()`, `sql()`, `segmentation()`, `funnels()`, `retention()`

### CLI Commands
```bash
mp auth add/switch/list/remove    # Credential management
mp fetch events/profiles          # Fetch to local DB
mp sql "SELECT ..."               # Query local DB
mp segmentation/funnels/retention # Live Mixpanel queries
mp explore events/properties      # Data discovery
mp db info/tables/drop            # Database management
```

### Data Model
- **Events** - Timestamped actions (`event`, `distinct_id`, `time`, `properties`)
- **User Profiles** - Mutable user state (`$set`, `$append`, `$unset`)
- **Group Profiles** - Organization/account attributes
- **Lookup Tables** - Arbitrary entity enrichment

## Reference Documentation

### Mixpanel API Docs ([api-docs/](api-docs/))
- **Event Export API** - Raw event fetching (primary for local DB)
- **Query API** - Segmentation, funnels, retention (live queries)
- **Lexicon Schemas API** - Event/property discovery

### Query Languages
- **[mixpanel-query-expression-language.md](mixpanel-query-expression-language.md)** - Filter expressions, operators, functions
- **[jql.md](jql.md)** - JavaScript Query Language (⚠️ deprecated, maintenance mode)

## Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | DuckDB/Pandas ecosystem |
| CLI | Typer | Type hints, auto-generated help |
| Output | Rich | Tables, progress bars |
| Validation | Pydantic | API response validation |
| Database | DuckDB | Embedded, analytical, JSON support |
| HTTP | httpx | Async support, connection pooling |

## When Working in This Directory

### Adding New Documentation
- Follow existing naming: `mixpanel_data-*.md` or `mp-cli-*.md`
- Update this CLAUDE.md with the new file
- Cross-reference from related documents

### Updating Specifications
- Keep version numbers in sync across related docs
- Update "Last Updated" dates
- Ensure CLI spec matches library API spec

### Using API Docs
- Start with [api-docs/CLAUDE.md](api-docs/CLAUDE.md) for navigation
- OpenAPI specs in `api-docs/openapi/src/` are source of truth
- Reference docs in `api-docs/reference/` are human-readable
