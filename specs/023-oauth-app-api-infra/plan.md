# Implementation Plan: OAuth PKCE & App API Infrastructure

**Branch**: `023-oauth-app-api-infra` | **Date**: 2026-03-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/023-oauth-app-api-infra/spec.md`

## Summary

Add OAuth 2.0 PKCE authentication and App API request infrastructure to `mixpanel_data`, enabling all future CRUD operations across 15+ Mixpanel entity domains. This creates a 7-file `_internal/auth/` module (PKCE, token management, DCR, callback server, flow orchestrator), extends the API client with `app_request()` + workspace scoping + cursor pagination, adds `OAuthError`/`WorkspaceScopeError` exceptions, and provides `mp auth login/logout/status/token` CLI commands with a global `--workspace-id` option.

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict)
**Primary Dependencies**: httpx (HTTP client), Pydantic v2 (validation), Typer (CLI), Rich (output)
**Storage**: JSON files at `~/.mp/oauth/` (token + client info persistence); DuckDB unchanged
**Testing**: pytest + respx (HTTP mocking) + Hypothesis (PBT); 90% coverage target
**Target Platform**: macOS / Linux (Unix file permissions)
**Project Type**: Library + CLI
**Performance Goals**: OAuth login < 60s; token refresh transparent; pagination fetches all pages
**Constraints**: No new external dependencies (stdlib for crypto, threading, http.server)
**Scale/Scope**: ~1,500 LOC implementation + ~1,500 LOC tests across ~15 new/modified files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| **I. Library-First** | PASS | All OAuth + App API methods exposed on Workspace class first. CLI delegates to library. |
| **II. Agent-Native Design** | PASS | No interactive prompts in default path. `mp auth login` opens browser non-interactively. All output structured JSON. Exit codes follow convention. |
| **III. Context Window Efficiency** | PASS | Workspace auto-discovery cached after first call. Pagination aggregates results. No raw data dumps. |
| **IV. Two Data Paths** | PASS | App API is a new live query path. No local storage changes needed. Shares auth/config. |
| **V. Explicit Over Implicit** | PASS | Auth method selection is explicit (endpoint category). Workspace ID settable explicitly. Token refresh is the one implicit behavior — justified by usability. |
| **VI. Unix Philosophy** | PASS | `mp auth token` outputs raw token for piping. All commands support `--format json`. Errors to stderr. |
| **VII. Secure by Default** | PASS | Tokens stored with 0o600 perms. Secrets use `SecretStr`. Never logged. `mp auth token` is intentional exception (explicit user action). |

**Gate result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/023-oauth-app-api-infra/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0: research findings
├── data-model.md        # Phase 1: entity definitions
├── quickstart.md        # Phase 1: usage guide
├── contracts/
│   └── library-api.md   # Phase 1: public API contract
├── checklists/
│   └── requirements.md  # Spec quality validation
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py                          # Add: OAuthError, WorkspaceScopeError, PublicWorkspace exports
├── workspace.py                         # Add: list_workspaces(), resolve_workspace_id(), set_workspace_id()
├── exceptions.py                        # Add: OAuthError, WorkspaceScopeError
├── types.py                             # Add: PublicWorkspace, CursorPagination, PaginatedResponse
├── _internal/
│   ├── config.py                        # Modify: AuthMethod enum, extend Credentials
│   ├── api_client.py                    # Modify: app_request(), workspace scoping, pagination
│   ├── pagination.py                    # NEW: paginate_all() helper
│   └── auth/                            # NEW: OAuth module (7 files)
│       ├── __init__.py                  # Module re-exports
│       ├── pkce.py                      # PkceChallenge (S256)
│       ├── token.py                     # OAuthTokens model
│       ├── storage.py                   # OAuthStorage (JSON files, perms)
│       ├── callback_server.py           # Ephemeral HTTP server
│       ├── client_registration.py       # DCR (RFC 7591)
│       └── flow.py                      # OAuthFlow orchestrator
└── cli/
    ├── main.py                          # Modify: --workspace-id global option
    └── commands/
        └── auth.py                      # Modify: add login, logout, status, token

tests/
├── test_auth_pkce.py                    # PKCE challenge generation
├── test_auth_token.py                   # Token model, expiry logic
├── test_auth_storage.py                 # Storage permissions, load/save
├── test_auth_callback.py               # Callback server behavior
├── test_auth_registration.py            # DCR request/response
├── test_auth_flow.py                    # Full flow orchestration (mocked)
├── test_app_api_client.py               # app_request(), workspace scoping
├── test_pagination.py                   # Cursor pagination helper
├── test_workspace_oauth.py              # Workspace OAuth integration
├── test_cli_auth.py                     # CLI auth commands
├── test_types_pbt.py                    # Update: PBT for new types
└── test_config_oauth.py                 # Extended credential resolution
```

**Structure Decision**: Extends existing single-project layout. New `_internal/auth/` module mirrors Rust's `auth/` structure. All other changes are modifications to existing files.

## Complexity Tracking

> No constitution violations — this section is empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)* | — | — |
