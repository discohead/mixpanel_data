# Implementation Plan: Data Governance CRUD

**Branch**: `027-data-governance-crud` | **Date**: 2026-04-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/027-data-governance-crud/spec.md`

## Summary

Add full CRUD operations for 5 data governance domains (Lexicon/data definitions, custom properties, custom events, drop filters, lookup tables) to achieve Python-Rust parity for Domains 9-13 from the gap analysis. This adds ~38 workspace methods, ~38 API client methods, ~25 Pydantic types, and 5 new CLI command groups (~35 subcommands) following established patterns.

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict)  
**Primary Dependencies**: httpx (HTTP), Pydantic v2 (validation), Typer (CLI), Rich (output)  
**Storage**: N/A (remote CRUD via Mixpanel App API; no DuckDB involvement)  
**Testing**: pytest + httpx.MockTransport + Hypothesis (PBT)  
**Target Platform**: Cross-platform (macOS, Linux, Windows)  
**Project Type**: Library + CLI  
**Performance Goals**: N/A (API-bound operations)  
**Constraints**: All code must pass mypy --strict, ruff check, ruff format, 90% coverage  
**Scale/Scope**: ~2,500 LOC impl + ~2,500 LOC tests across 5 domains

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | PASS | All CRUD exposed as Workspace methods first; CLI wraps library |
| II. Agent-Native | PASS | Non-interactive, structured output (JSON/CSV/table), stderr for errors |
| III. Context Efficiency | PASS | Precise responses, no raw data dumps |
| IV. Two Data Paths | N/A | This feature is App API CRUD only, no local storage |
| V. Explicit Over Implicit | PASS | All mutations require explicit params objects |
| VI. Unix Philosophy | PASS | CLI output pipeable to jq, composable with other tools |
| VII. Secure by Default | PASS | Credentials via config/env, never in CLI args or output |

**Post-Design Re-Check**: All principles continue to pass. No violations identified.

## Project Structure

### Documentation (this feature)

```text
specs/027-data-governance-crud/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Research findings
├── data-model.md        # Entity definitions
├── quickstart.md        # Usage examples
├── contracts/
│   └── library-api.md   # Library + CLI API contract
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── types.py                          # Add ~25 Pydantic models (append to existing)
├── workspace.py                      # Add ~38 methods (append to existing)
├── _internal/
│   └── api_client.py                 # Add ~38 methods (append to existing)
└── cli/
    ├── main.py                       # Register 5 new command groups
    └── commands/
        ├── lexicon.py                # NEW: 15+ subcommands (events, properties, tags, history, export)
        ├── custom_properties.py      # NEW: 6 subcommands
        ├── custom_events.py          # NEW: 3 subcommands
        ├── drop_filters.py           # NEW: 5 subcommands (list, create, update, delete, limits)
        └── lookup_tables.py          # NEW: 7 subcommands

tests/
├── unit/
│   ├── test_types_data_governance.py         # NEW: Type model tests
│   ├── test_api_client_data_governance.py    # NEW: API client method tests
│   ├── test_workspace_data_governance.py     # NEW: Workspace integration tests
│   └── cli/
│       ├── test_lexicon.py                   # NEW: CLI tests
│       ├── test_custom_properties.py         # NEW
│       ├── test_custom_events.py             # NEW
│       ├── test_drop_filters.py              # NEW
│       └── test_lookup_tables.py             # NEW
└── unit/
    └── test_types_data_governance_pbt.py     # NEW: Property-based tests
```

**Structure Decision**: Follows the established single-project pattern. All new code appends to existing files (`types.py`, `workspace.py`, `api_client.py`) or creates new files in existing directories (`cli/commands/`, `tests/unit/`).

## Implementation Phases

### Phase 1: Pydantic Types (~25 models)

Add all data governance types to `types.py`. Order: result types first, then parameter types.

**Files modified**: `src/mixpanel_data/types.py`

**Types to add (by domain)**:

Domain 9 — Data Definitions:
- `EventDefinition` (frozen, extra=allow)
- `PropertyDefinition` (frozen, extra=allow)
- `UpdateEventDefinitionParams`
- `UpdatePropertyDefinitionParams`
- `BulkEventUpdate`
- `BulkUpdateEventsParams`
- `BulkPropertyUpdate`
- `BulkUpdatePropertiesParams`
- `LexiconTag` (frozen, extra=allow)
- `CreateTagParams`
- `UpdateTagParams`

Domain 10 — Custom Properties:
- `ComposedPropertyValue` (frozen, extra=allow)
- `CustomProperty` (frozen, extra=allow)
- `CreateCustomPropertyParams` (with validation: display_formula/behavior mutual exclusion)
- `UpdateCustomPropertyParams`

Domain 12 — Drop Filters:
- `DropFilter` (frozen, extra=allow)
- `CreateDropFilterParams`
- `UpdateDropFilterParams`
- `DropFilterLimitsResponse` (frozen, extra=allow)

Domain 13 — Lookup Tables:
- `LookupTable` (frozen, extra=allow)
- `UploadLookupTableParams`
- `MarkLookupTableReadyParams`
- `LookupTableUploadUrl` (frozen, extra=allow)
- `UpdateLookupTableParams`

**Test file**: `tests/unit/test_types_data_governance.py`
- Frozen immutability for all result types
- Extra field preservation
- `model_dump(exclude_none=True)` serialization for params
- CreateCustomPropertyParams validation rules
- `tests/unit/test_types_data_governance_pbt.py` — Hypothesis round-trip tests

### Phase 2: API Client Methods (~38 methods)

Add all HTTP methods to `_internal/api_client.py`.

**Files modified**: `src/mixpanel_data/_internal/api_client.py`

**Methods to add (by domain)**:

Domain 9 — Data Definitions:
- `get_event_definitions(names, resource_type=None)` — GET `/data-definitions/events/` with `name[]` params
- `update_event_definition(name, body)` — PATCH `/data-definitions/events/`
- `delete_event_definition(name)` — DELETE `/data-definitions/events/` with JSON body
- `get_property_definitions(names, resource_type=None)` — GET `/data-definitions/properties/`
- `update_property_definition(name, body)` — PATCH `/data-definitions/properties/`
- `bulk_update_event_definitions(body)` — PATCH `/data-definitions/events/`
- `bulk_update_property_definitions(body)` — PATCH `/data-definitions/properties/`
- `list_lexicon_tags()` — GET `/data-definitions/tags/`
- `create_lexicon_tag(body)` — POST `/data-definitions/tags/`
- `update_lexicon_tag(tag_id, body)` — PATCH `/data-definitions/tags/{id}/`
- `delete_lexicon_tag(name)` — POST `/data-definitions/tags/` with `{"delete": true, "name": ...}`
- `get_tracking_metadata(event_name)` — GET `/data-definitions/events/tracking-metadata/`
- `get_event_history(event_name)` — GET `/data-definitions/events/{name}/history/`
- `get_property_history(property_name, entity_type)` — GET `/data-definitions/properties/{name}/history/`
- `export_lexicon(export_types=None)` — GET `/data-definitions/export/`

Domain 10 — Custom Properties:
- `list_custom_properties()` — GET `/custom_properties/`
- `create_custom_property(body)` — POST `/custom_properties/`
- `get_custom_property(property_id)` — GET `/custom_properties/{id}/`
- `update_custom_property(property_id, body)` — PUT `/custom_properties/{id}/`
- `delete_custom_property(property_id)` — DELETE `/custom_properties/{id}/`
- `validate_custom_property(body)` — POST `/custom_properties/validate/`

Domain 12 — Drop Filters:
- `list_drop_filters()` — GET `/data-definitions/events/drop-filters/`
- `create_drop_filter(body)` — POST `/data-definitions/events/drop-filters/`
- `update_drop_filter(body)` — PATCH `/data-definitions/events/drop-filters/`
- `delete_drop_filter(drop_filter_id)` — DELETE `/data-definitions/events/drop-filters/`
- `get_drop_filter_limits()` — GET `/data-definitions/events/drop-filters/limits/`

Domain 13 — Lookup Tables:
- `list_lookup_tables(data_group_id=None)` — GET `/data-definitions/lookup-tables/`
- `mark_lookup_table_ready(body)` — POST `/data-definitions/lookup-tables/`
- `update_lookup_table(data_group_id, body)` — PATCH `/data-definitions/lookup-tables/`
- `delete_lookup_tables(data_group_ids)` — DELETE `/data-definitions/lookup-tables/`
- `get_lookup_upload_url(content_type)` — GET `/data-definitions/lookup-tables/upload-url/`
- `get_lookup_upload_status(upload_id)` — GET `/data-definitions/lookup-tables/upload-status/`
- `upload_to_signed_url(url, csv_bytes)` — PUT to external GCS URL (no auth)
- `register_lookup_table(form_data)` — POST `/data-definitions/lookup-tables/` (form-encoded)
- `download_lookup_table(data_group_id, file_name=None, limit=None)` — GET `/data-definitions/lookup-tables/download/` (raw bytes)
- `get_lookup_download_url(data_group_id)` — GET `/data-definitions/lookup-tables/download-url/`

**Special patterns**:
- Tag deletion uses POST with `{"delete": true, "name": ...}`
- Drop filter mutations return the full list
- Lookup table registration uses form-encoded POST
- Custom property update uses PUT (full replacement)
- Lookup table download returns raw bytes, not JSON

**Test file**: `tests/unit/test_api_client_data_governance.py`
- URL construction verification
- Request body/params verification
- Response parsing
- Error handling

### Phase 3: Workspace Methods (~38 methods)

Add all orchestration methods to `workspace.py`.

**Files modified**: `src/mixpanel_data/workspace.py`

**Methods to add**: Mirror the API client methods with:
- Pydantic params → `model_dump(exclude_none=True)` → API client
- API response → `Model.model_validate(raw)` → typed result
- `upload_lookup_table()` — 3-step orchestration (get URL, upload to GCS, register, optional polling)

**Test file**: `tests/unit/test_workspace_data_governance.py`
- End-to-end with mocked transport
- Param serialization verification
- Response deserialization verification

### Phase 4: CLI Commands (5 command groups, ~35 subcommands)

Create 5 new CLI command files and register them in `main.py`.

**Files created**:
- `src/mixpanel_data/cli/commands/lexicon.py` — 15+ subcommands using nested Typer groups (events, properties, tags, plus top-level history/export)
- `src/mixpanel_data/cli/commands/custom_properties.py` — 6 subcommands
- `src/mixpanel_data/cli/commands/custom_events.py` — 3 subcommands
- `src/mixpanel_data/cli/commands/drop_filters.py` — 5 subcommands
- `src/mixpanel_data/cli/commands/lookup_tables.py` — 7 subcommands

**Files modified**: `src/mixpanel_data/cli/main.py` — add 5 `app.add_typer()` calls

**Test files**: `tests/unit/cli/test_lexicon.py`, `test_custom_properties.py`, `test_custom_events.py`, `test_drop_filters.py`, `test_lookup_tables.py`

### Phase 5: Integration & Quality

- Run `just check` (lint + typecheck + tests)
- Verify coverage >= 90%
- Run mutation testing on new code
- Update `__init__.py` exports for new types

## Complexity Tracking

No constitution violations. All implementation follows established patterns.
