# API References - OpenAPI Specification Management

This directory contains Mixpanel's **centralized OpenAPI specification management system** - language-agnostic interface definitions for Mixpanel APIs designed for documentation and API explorer publishing.

## Directory Structure

```
api_references/
├── README.md                    # Brief overview
├── publish_oas.sh               # Publishing script wrapper
└── openapi/                     # Main OpenAPI specifications hub
    ├── README.md                # Workflow documentation
    ├── openapi.config.yaml      # Spectacle/Redocly configuration
    ├── publish_oas.sh           # Publish script for readme.com
    ├── explorer/index.html      # Readme.io API explorer interface
    ├── src/                     # Source specifications (modular)
    │   ├── data-definitions.internal.openapi.yaml
    │   └── common/              # Reusable components library
    │       ├── app-api.yaml           # Server definitions
    │       ├── export-api.yaml        # Export API servers
    │       ├── ingestion-api.yaml     # Ingestion parameters
    │       ├── parameters.yaml        # Reusable parameters
    │       ├── responses.yaml         # Standard HTTP responses
    │       ├── schemas.yaml           # Common schemas
    │       └── securitySchemes.yaml   # Auth definitions
    └── out/                     # Compiled/bundled specifications
```

## Key Patterns

### DRY Architecture
All specs use `$ref` to reference components in `src/common/`:
```yaml
security:
  - ServiceAccount: []
servers:
  - $ref: ./common/app-api.yaml#/server
parameters:
  - $ref: ./common/parameters.yaml#/path/projectId
```

### Multi-Regional Support
Server configs support US, EU, and India data residency via OpenAPI server variables.

### Authentication Methods
- **ServiceAccount** - HTTP Basic (primary)
- **ProjectSecret** - HTTP Basic (legacy)

## Commands

```bash
npm run lint:api-refs      # Validate spec templates in /src
npm run build:api-refs     # Bundle /src specs → /out directory
npm run publish:api-refs   # Publish to readme.com (requires VERSION env var)
```

## When Working Here

- Modify source specs in `src/`, never edit `out/` directly
- Add shared components to `src/common/` for reuse
- Run `npm run lint:api-refs` before committing changes
- The `*.internal.openapi.yaml` files are excluded from publication
