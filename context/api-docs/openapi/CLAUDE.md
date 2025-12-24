# OpenAPI Specifications

This directory manages **10 production Mixpanel API specifications** with validation and publishing to ReadMe.com documentation portal.

## API Specifications

| Spec | File | Size | Description |
|------|------|------|-------------|
| Query | `query.openapi.yaml` | 1747 lines | Segmentation, Funnels, Retention, JQL, Insights |
| Data Pipelines | `data-pipelines.openapi.yaml` | 1750 lines | Pipeline configuration |
| Ingestion | `ingestion.openapi.yaml` | 1337 lines | Event tracking, user profiles |
| Annotations | `annotations.openapi.yaml` | - | Project annotation labeling |
| Export | `export.openapi.yaml` | - | Event export functionality |
| Feature Flags | `feature-flags.openapi.yaml` | - | Feature flag evaluation |
| GDPR | `gdpr.openapi.yaml` | - | GDPR compliance operations |
| Identity | `identity.openapi.yaml` | - | User identity management |
| Lexicon Schemas | `lexicon-schemas.openapi.yaml` | - | Schema definitions |
| Service Accounts | `service-accounts.openapi.yaml` | - | Service account management |
| Warehouse Connectors | `warehouse-connectors.openapi.yaml` | 52 lines | Warehouse integration |

## Directory Structure

```
openapi/
├── openapi.config.yaml          # Central registry (spec → output mapping)
├── publish.js                   # Node.js publication script
├── test.sh                      # Validation pipeline
├── .redocly.lint-ignore.yaml    # Lint exceptions
└── src/                         # Source specifications
    ├── *.openapi.yaml           # Individual API specs
    └── common/                  # Shared components
        ├── app-api.yaml         # Server config (US, EU, India)
        ├── parameters.yaml      # Shared parameters
        ├── responses.yaml       # Standard HTTP responses (400, 401, 403, 404)
        ├── securitySchemes.yaml # Three auth methods
        ├── schemas.yaml         # Primitive types
        ├── ingestion-api.yaml   # Ingestion parameters
        └── feature-flags-api.yaml
```

## Build Pipeline

```bash
npm run api:lint     # Redocly linting
npm run api:build    # Compile YAML → JSON (output to out/)
```

## Publishing

Requires environment variables:
- `README_API_KEY` - ReadMe.com API key
- `README_VERSION` - Target version (e.g., v2)

```bash
node publish.js      # Validates and publishes all specs
```

The script:
1. Validates each spec with `rdme openapi:validate`
2. Uploads via `rdme openapi upload`
3. Matches filenames to ReadMe slugs

## Authentication Methods (src/common/securitySchemes.yaml)

| Method | Type | Usage |
|--------|------|-------|
| ServiceAccount | HTTP Basic | Primary - most APIs |
| ProjectSecret | HTTP Basic | Legacy |
| OAuthToken | Bearer | GDPR/privacy APIs |

## Key Patterns

### Spec Structure (OpenAPI 3.0.2/3.0.3)
```yaml
openapi: 3.0.2
info:
  title: [API Name]
  version: 1.0.0
  license: MIT
servers:
  - $ref: ./common/app-api.yaml#/server
security:
  - ServiceAccount: []
paths:
  /...
```

### Regional Endpoints
All APIs support dynamic region selection via server variables:
- Standard: `api.mixpanel.com`
- EU: `api-eu.mixpanel.com`
- India: `api-in.mixpanel.com`

## When Working Here

- Source specs in `src/`, compiled output in `out/`
- Add shared components to `src/common/` to avoid duplication
- Run `npm run api:lint` before committing
- Check `.redocly.lint-ignore.yaml` for known exceptions
- Specs must exist in ReadMe before first publish
