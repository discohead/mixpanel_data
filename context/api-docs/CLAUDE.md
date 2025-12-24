# Mixpanel API Documentation

This directory contains comprehensive Mixpanel API documentation in multiple formats, serving as the **primary reference for building mixpanel_data**.

## Directory Structure

```
api-docs/
├── API-QUICK-REFERENCE.md       # Quick reference guide
├── mixpanel-api-reference.md    # Consolidated API reference
├── api_references/              # OpenAPI spec management (internal tooling)
├── openapi/                     # Production OpenAPI specs (10 APIs)
└── reference/                   # Human-readable Markdown docs (15 API categories)
```

## Quick Navigation

| Need | Location |
|------|----------|
| API overview | [API-QUICK-REFERENCE.md](API-QUICK-REFERENCE.md) |
| Full reference | [mixpanel-api-reference.md](mixpanel-api-reference.md) |
| OpenAPI specs | [openapi/src/](openapi/src/) |
| Markdown docs | [reference/](reference/) |

## Key APIs for mixpanel_data

### Primary (Must Implement)

| API | Purpose | Docs |
|-----|---------|------|
| **Event Export API** | Fetch raw events → local DuckDB | [reference/Event Export API/](reference/Event%20Export%20API/) |
| **Query API** | Live queries (segmentation, funnels, retention) | [reference/Query API/](reference/Query%20API/) |
| **Ingestion API** | Understand event/profile structure | [reference/Ingestion API/](reference/Ingestion%20API/) |

### Secondary (Data Discovery)

| API | Purpose | Docs |
|-----|---------|------|
| **Lexicon Schemas API** | Event/property definitions | [reference/Lexicon Schemas API/](reference/Lexicon%20Schemas%20API/) |

### Tertiary (Future)

- Annotations API, GDPR API, Feature Flags API

## Authentication Methods

| Method | Usage | Notes |
|--------|-------|-------|
| **Service Account** | Most APIs | HTTP Basic - preferred |
| **Project Token** | Client-side ingestion | Public endpoints |
| **Project Secret** | Legacy | Deprecated, avoid |
| **OAuth Token** | GDPR/privacy | Bearer token |

## Data Residency

All APIs support regional endpoints:
- **US (default)**: `api.mixpanel.com`
- **EU**: `api-eu.mixpanel.com`
- **India**: `api-in.mixpanel.com`

## Rate Limits

| API | Limit |
|-----|-------|
| Event ingestion | 2GB/min (~30k events/sec) |
| Export API | Project-specific |
| Query API | Varies by endpoint |
| GDPR API | 1 req/sec |

## OpenAPI Spec Workflow

```bash
# In openapi/ directory
npm run api:lint     # Validate specs
npm run api:build    # Compile YAML → JSON
```

## For mixpanel_data Development

### Event Export API
Read [reference/Event Export API/](reference/Event%20Export%20API/) for:
- Authentication requirements
- Date range parameters
- Response format (JSONL)
- Rate limits and pagination

### Query API Endpoints
Read [reference/Query API/](reference/Query%20API/) subdirectories:
- `segmentation/` - Time-series event data
- `funnels/` - Conversion analysis
- `retention/` - User retention
- `insights/` - Report builder queries
- `jql/` - Custom JavaScript queries

### Data Model Understanding
Read [reference/Ingestion API/](reference/Ingestion%20API/) for:
- Event structure (`event`, `properties`, `$distinct_id`, `time`)
- Profile structure (`$set`, `$append`, `$unset`)
- Reserved properties (`$insert_id`, `$device_id`, etc.)

## File Patterns

```bash
# Find all Query API docs
fd . "reference/Query API" --type f

# Search for authentication info
rg "ServiceAccount|authentication" reference/

# Find rate limit documentation
rg "rate.?limit" reference/ -i
```
