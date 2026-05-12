# Implementation Plan: Mixpanel API Client

**Branch**: `002-api-client` | **Date**: 2025-12-20 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-api-client/spec.md`

## Summary

The Mixpanel API Client (`MixpanelAPIClient`) is a unified HTTP interface for all Mixpanel APIs. It handles service account authentication via HTTP Basic auth, regional endpoint routing (US/EU/India), automatic rate limit handling with exponential backoff, and streaming JSONL parsing for large exports. The client operates as a pure HTTP layer with no storage knowledge, returning raw API responses for upstream services to transform.

## Technical Context

**Language/Version**: Python 3.10+ (Constitution requirement)
**Primary Dependencies**: httpx (HTTP client per Constitution), pydantic (validation)
**Storage**: N/A (client has no storage responsibility; Phase 003 handles DuckDB)
**Testing**: pytest with httpx.MockTransport for deterministic HTTP mocking
**Target Platform**: Cross-platform Python (Linux, macOS, Windows)
**Project Type**: Single project library with CLI wrapper
**Performance Goals**: Stream 1M+ events without memory exhaustion; support 60 requests/hour rate limit
**Constraints**: <300s timeout for exports; constant memory during streaming; credentials never in logs
**Scale/Scope**: Single client instance per Workspace; handles all Mixpanel API endpoints

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | ✅ PASS | `MixpanelAPIClient` is a Python class, not CLI; all methods are importable |
| II. Agent-Native | ✅ PASS | Returns structured dicts/lists; no interactive prompts; streaming for large data |
| III. Context Window Efficiency | ✅ PASS | Streaming iterators for exports; discovery methods for introspection |
| IV. Two Data Paths | ✅ PASS | Client supports both live queries (segmentation) and export APIs |
| V. Explicit Over Implicit | ✅ PASS | No automatic retry beyond configured max; explicit exceptions for all errors |
| VI. Unix Philosophy | ✅ PASS | Client does one thing (HTTP); raw responses composable with other tools |
| VII. Secure by Default | ✅ PASS | FR-004 mandates no credentials in logs/errors; SecretStr for secrets |

**Technology Stack Compliance**:
- [x] httpx for HTTP (not requests) per Constitution
- [x] Pydantic for credential validation (already in Phase 001)
- [x] Type hints throughout
- [x] Depends on existing exceptions from Phase 001

**Gate Result**: ✅ PASSED - Proceed to Phase 0

## Project Structure

### Documentation (this feature)

```text
specs/002-api-client/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api-client.py    # Type stubs / interface contract
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py              # Exports (add MixpanelAPIClient if public)
├── exceptions.py            # ✅ Exists: AuthenticationError, RateLimitError, QueryError
├── types.py                 # ✅ Exists: Result types (used by services, not client)
├── _internal/
│   ├── __init__.py          # ✅ Exists
│   ├── config.py            # ✅ Exists: Credentials class
│   └── api_client.py        # 🆕 NEW: MixpanelAPIClient implementation
└── cli/                     # (Phase 008 - not this phase)

tests/
├── unit/
│   └── test_api_client.py   # 🆕 NEW: Unit tests with mock transport
├── integration/
│   └── test_api_client_integration.py  # 🆕 NEW: Real API tests (optional)
└── conftest.py              # ✅ Exists: Add fixtures for mock client
```

**Structure Decision**: Single project layout (already established in Phase 001). API client is a private implementation detail in `_internal/`, exposed to services but not directly to users.

## Constitution Re-Check (Post-Design)

*Verified after Phase 1 design completion.*

| Principle | Status | Post-Design Evidence |
|-----------|--------|---------------------|
| I. Library-First | ✅ PASS | Contract defines pure Python Protocol; no CLI dependencies |
| II. Agent-Native | ✅ PASS | All methods return Iterator/dict/list; on_batch callback for progress |
| III. Context Window Efficiency | ✅ PASS | data-model.md shows streaming iterators throughout |
| IV. Two Data Paths | ✅ PASS | export_events() + segmentation/funnel/retention methods |
| V. Explicit Over Implicit | ✅ PASS | Contract shows explicit exceptions for all error cases |
| VI. Unix Philosophy | ✅ PASS | Client is pure HTTP; raw responses for composability |
| VII. Secure by Default | ✅ PASS | Contract uses Credentials (SecretStr); no credential exposure |

**Post-Design Gate Result**: ✅ PASSED - Ready for `/speckit.tasks`

## Complexity Tracking

No constitution violations. All requirements align with established principles.

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Rate limiting | Per-instance, not global | Simpler; each client handles its own retry state |
| Streaming | Line-by-line parsing | Memory-efficient; matches JSONL format |
| Error mapping | Exception hierarchy | Reuses Phase 001 exceptions; no new exception types needed |

## Generated Artifacts

| Artifact | Path | Purpose |
|----------|------|---------|
| Research | [research.md](research.md) | Technical decisions and alternatives |
| Data Model | [data-model.md](data-model.md) | Entity definitions and data flow |
| Contract | [contracts/api_client.py](contracts/api_client.py) | Type stubs / interface definition |
| Quickstart | [quickstart.md](quickstart.md) | Developer usage guide |
