# Mixpanel API Reference Documentation

Human-readable Markdown documentation for all Mixpanel APIs. Navigation controlled by `_order.yaml` files at each directory level.

## API Categories (15 total)

| API | Path | Description |
|-----|------|-------------|
| **Mixpanel APIs** | `Mixpanel APIs/` | Hub - overview, auth, rate limits |
| **Ingestion API** | `Ingestion API/` | Event tracking, user/group profiles, lookup tables |
| **Query API** | `Query API/` | Segmentation, Funnels, Retention, JQL, Insights |
| **Event Export API** | `Event Export API/` | Raw data export |
| **Data Pipelines API** | `Data Pipelines API/` | Pipeline CRUD operations |
| **Identity API** | `Identity API/` | Identity management |
| **Lexicon Schemas API** | `Lexicon Schemas API/` | Schema definitions |
| **Service Accounts API** | `Service Accounts API/` | Account management |
| **Annotations API** | `Annotations API/` | Project annotations |
| **GDPR API** | `GDPR API/` | Privacy compliance (retrieval, deletion) |
| **Warehouse Connectors API** | `Warehouse Connectors API/` | Warehouse integration |
| **Feature Flags API** | `Feature Flags API/` | Feature flags/experiments |
| **Partner Integrations** | `Partner Integrations/` | Third-party cohort integrations |

## Directory Structure Pattern

```
{API Name}/
├── _order.yaml                      # Navigation ordering
├── {api-name}.md                    # Overview documentation
├── {api-name}-authentication.md     # Auth methods
├── {operation-category}/            # Grouped endpoints
│   ├── _order.yaml
│   └── {endpoint}.md
└── [supplementary].md               # Rate limits, etc.
```

## Frontmatter Format

All markdown files use consistent YAML frontmatter:
```yaml
---
title: [Page Title]
category:
  uri: [API Category Name]
content:
  excerpt: '[Short description]'
privacy:
  view: public
---
```

## Key APIs for mixpanel_data Project

### Query API (Most Relevant)
Primary target for live queries. Subdirectories:
- `segmentation/` - Segmentation queries
- `funnels/` - Funnel analysis
- `retention/` - Retention analysis
- `insights/` - General insights
- `jql/` - JQL query language
- `cohorts/` - Cohort operations
- `engage/` - User engagement
- `activity-feed/` - Activity queries

### Event Export API (Most Relevant)
Primary target for local data fetching:
- `export/` - Raw event export endpoint

### Ingestion API
Reference for understanding event/profile structure:
- `events/` - Event tracking (track, import, deduplication)
- `user-profiles/` - User profile operations
- `group-profiles/` - Group profiles
- `lookup-tables/` - Lookup table operations

## Data Residency Endpoints

Documented across APIs:
- **Standard**: `api.mixpanel.com` / `mixpanel.com/api`
- **EU**: `api-eu.mixpanel.com` / `eu.mixpanel.com/api`
- **India**: `api-in.mixpanel.com` / `in.mixpanel.com/api`

## Rate Limits (from docs)

- **Event ingestion**: 2GB uncompressed/minute (~30k events/second)
- **GDPR API**: 1 request/second
- **Export API**: Project-specific limits

## Special Markdown Elements

```markdown
# Callout blocks
<Callout icon="..." theme="info|warning|error">
  Content here
</Callout>

# Cross-references
[Link Text](ref:reference-id)

# Code blocks with language
```json JSON
{ "example": "value" }
```
```

## When Working Here

- Check `_order.yaml` to understand navigation structure
- Maintain frontmatter consistency when adding docs
- Use `ref:` syntax for cross-references
- Include regional endpoint variations where applicable
- File naming: overview → `{api}-api.md`, auth → `{api}-api-authentication.md`
