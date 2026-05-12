# Research: Lexicon Schemas API (Read Operations)

**Feature**: 012-lexicon-schemas
**Date**: 2025-12-24

---

## Research Questions

### RQ-1: Lexicon API Base URL Pattern

**Question**: What is the correct base URL for the Lexicon Schemas API across regions?

**Finding**: The Lexicon API uses `/api/app` as its base path, distinct from Query API (`/api/query`) and Export API (`/api/2.0`).

| Region | Base URL |
|--------|----------|
| US | `https://mixpanel.com/api/app` |
| EU | `https://eu.mixpanel.com/api/app` |
| IN | `https://in.mixpanel.com/api/app` |

**Decision**: Add `"app"` key to `ENDPOINTS` dict in `api_client.py` with these URLs (named after the base path, as multiple APIs use `/api/app`).

**Rationale**: Follows existing regional endpoint pattern; Mixpanel documentation confirms this structure.

**Alternatives Considered**:
- Hardcode URLs in schema methods → Rejected: Inconsistent with existing pattern
- Single URL with region path parameter → Rejected: Not how Mixpanel API works

---

### RQ-2: Authentication for Lexicon API

**Question**: Does the Lexicon API use the same authentication as Query API?

**Finding**: Yes, Service Account authentication via HTTP Basic Auth works identically. The API expects `project_id` in the URL path (not query parameter).

**Decision**: Reuse existing `_get_auth_header()` method; construct URLs with `project_id` in path.

**Rationale**: Consistent with existing authentication infrastructure.

---

### RQ-3: Rate Limiting Behavior

**Question**: How does the Lexicon API rate limit differ from Query API?

**Finding**:
- Lexicon API: **5 requests per minute** (much stricter than Query API)
- Max 4,000 events/properties per minute
- Standard 429 response with Retry-After header

**Decision**: Rely on existing retry logic in `_execute_with_retry()`. Session caching is critical to stay under limits.

**Rationale**: Existing backoff logic handles 429s; caching minimizes requests.

---

### RQ-4: Response Structure Analysis

**Question**: What is the exact response structure for schema endpoints?

**Finding**: Confirmed from initial implementation plan and Mixpanel documentation:

**List Schemas Response:**
```json
{
  "results": [
    {
      "entityType": "event",
      "name": "Purchase",
      "schemaJson": {
        "description": "User completes a purchase",
        "properties": {
          "amount": { "type": "number", "description": "Purchase amount" }
        },
        "metadata": {
          "com.mixpanel": {
            "$source": "api",
            "displayName": "Purchase Event",
            "tags": ["core"],
            "hidden": false,
            "dropped": false,
            "contacts": ["owner@company.com"],
            "teamContacts": ["Analytics"]
          }
        }
      }
    }
  ],
  "status": "ok"
}
```

**Single Schema Response:**
```json
{
  "results": {
    "entityType": "event",
    "name": "Purchase",
    "schemaJson": { ... }
  },
  "status": "ok"
}
```

**Decision**: Parse `results` key; handle both list and object cases.

---

### RQ-5: Error Response Handling

**Question**: How does the API respond to non-existent schemas?

**Finding**:
- Non-existent schema lookup returns HTTP 404
- Invalid entity type returns HTTP 400

**Decision**:
- Map 404 to `None` return value (not an error)
- Map 400 to `QueryError` exception

**Rationale**: Non-existence is not exceptional; matches spec requirement for graceful handling.

---

### RQ-6: Schema Name URL Encoding

**Question**: How should schema names with special characters be handled?

**Finding**:
- httpx automatically URL-encodes path segments
- Tested with names containing spaces, unicode, and special characters

**Decision**: Pass raw name to httpx; rely on automatic encoding.

**Rationale**: Standard HTTP client behavior; no custom encoding needed.

---

### RQ-7: Caching Strategy

**Question**: What caching strategy should be used for schema data?

**Finding**: Existing DiscoveryService uses tuple-based cache keys:
```python
self._cache: dict[tuple[str | int | None, ...], list[Any]] = {}
```

**Decision**: Use cache keys:
- `("list_schemas",)` - All schemas
- `("list_schemas", entity_type)` - Filtered by entity type
- `("get_schema", entity_type, name)` - Single schema

**Rationale**: Consistent with existing caching pattern (funnels, cohorts, events).

---

### RQ-8: API Client Method Design

**Question**: Should there be separate methods for list-all vs list-by-type, or a single method with optional parameter?

**Finding**: Examining existing patterns:
- `get_events()` has no parameters (list all)
- `get_property_values()` has optional `event` parameter

**Decision**:
- API Client: Two methods (`list_schemas()`, `list_schemas_for_entity(entity_type)`) for clear URL construction
- DiscoveryService: Single method (`list_schemas(entity_type=None)`) for simpler public API

**Rationale**: API client maps 1:1 to endpoints; service layer provides convenience.

---

### RQ-9: Type Alias vs Enum for EntityType

**Question**: Should EntityType be a Literal type alias or an Enum?

**Finding**: Existing codebase uses `Literal` for constrained strings:
```python
unit: Literal["day", "week", "month"]
type: Literal["events", "profiles"]
```

**Decision**: Use `Literal["event", "profile"]` type alias.

**Rationale**: Consistent with existing patterns; simpler than Enum for two values.

---

### RQ-10: Nested Dataclass Design

**Question**: How should nested schema structures be represented?

**Finding**: Existing types use composition:
- `FunnelResult` contains `list[FunnelStep]`
- `RetentionResult` contains `list[CohortInfo]`

**Decision**: Create hierarchy:
```
LexiconSchema
├── entity_type: Literal["event", "profile"]
├── name: str
└── schema_json: LexiconDefinition
    ├── description: str | None
    ├── properties: dict[str, LexiconProperty]
    └── metadata: LexiconMetadata | None
        ├── source: str | None
        ├── display_name: str | None
        ├── tags: list[str]
        ├── hidden: bool
        ├── dropped: bool
        ├── contacts: list[str]
        └── team_contacts: list[str]
```

**Rationale**: Type safety, IDE completion, consistent with existing patterns.

---

## Summary of Decisions

| Area | Decision |
|------|----------|
| Endpoint | Add `"app"` to ENDPOINTS with `/api/app` base |
| Authentication | Reuse existing HTTP Basic Auth |
| Rate Limiting | Use existing retry logic; caching critical |
| Response Parsing | Extract from `results` key |
| 404 Handling | Return `None`, not exception |
| URL Encoding | Rely on httpx default behavior |
| Cache Keys | Tuple-based like existing services |
| API Client | Two methods mapping to endpoints |
| DiscoveryService | Single method with optional param |
| Type System | Literal type alias for EntityType |
| Data Model | Nested frozen dataclasses (LexiconSchema, LexiconDefinition, LexiconProperty, LexiconMetadata) with to_dict() |
