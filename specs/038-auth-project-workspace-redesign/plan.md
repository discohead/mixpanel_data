# Implementation Plan: Auth, Project & Workspace Management Redesign

**Branch**: `038-auth-project-workspace-redesign` | **Date**: 2026-04-07 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/038-auth-project-workspace-redesign/spec.md`

## Summary

Redesign `mixpanel_data`'s authentication system to decouple credentials (identity) from project selection (context). Add `/me`-based project and workspace discovery with disk caching, persistent active context across sessions, in-session project switching, config migration from v1 to v2, and new CLI commands (`mp projects`, `mp workspaces`, `mp context`). All changes maintain full backward compatibility with existing v1 configs and `Workspace(account="name")` usage.

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict compliant)  
**Primary Dependencies**: Pydantic v2 (validation/models), httpx (HTTP client), Typer (CLI), Rich (output), tomli/tomli_w (TOML read/write)  
**Storage**: TOML config file (`~/.mp/config.toml`), JSON cache files (`~/.mp/oauth/me_{region}.json`), JSON OAuth token files (`~/.mp/oauth/tokens_{region}.json`)  
**Testing**: pytest + Hypothesis (property-based) + mutmut (mutation testing)  
**Target Platform**: Cross-platform (macOS, Linux, Windows)  
**Project Type**: Library + CLI  
**Performance Goals**: Cached /me responses return in <100ms; first /me API call acceptable at 2-5s with progress indicator  
**Constraints**: Full backward compatibility with v1 config format; mypy --strict; ruff format/check; 90% test coverage minimum  
**Scale/Scope**: ~12 new files, ~10 modified files, 7 implementation phases (A-G)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | All features have Python API (`discover_projects()`, `switch_project()`, `me()`) before CLI (`mp projects list`, etc.) |
| II. Agent-Native | PASS | All new methods are non-interactive, return structured data; CLI outputs JSON/table/CSV |
| III. Context Window Efficiency | PASS | `/me` cache avoids repeated 2-5s API calls; discovery methods return precise typed objects, not raw dumps |
| IV. Two Data Paths | PASS | Auth redesign is path-agnostic — both live queries and local analysis share the same credential/project resolution |
| V. Explicit Over Implicit | PASS | Active context is explicitly persisted in `[active]` config section; no magic fallback from OAuth token's project_id; `switch_project()` is an explicit action |
| VI. Unix Philosophy | PASS | CLI commands output clean structured data (JSON/table); composable with jq, grep, etc. |
| VII. Secure by Default | PASS | Secrets stay in config files (0o600); cached /me responses use 0o600 permissions; no credentials in CLI args or logs |

**Gate Result**: PASS — No violations. Proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/038-auth-project-workspace-redesign/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── python-api.md    # Library API contracts
│   └── cli-commands.md  # CLI command contracts
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py                      # Add new public exports
├── workspace.py                     # Add switch_project, discover_projects, etc.
├── auth.py                          # Re-export new types
├── exceptions.py                    # Add ProjectNotFoundError
├── _internal/
│   ├── config.py                    # Add v2 support, resolve_session, migration
│   ├── api_client.py                # Accept ResolvedSession, add with_project, me()
│   ├── auth_credential.py           # NEW: AuthCredential, ProjectContext, ResolvedSession
│   ├── me.py                        # NEW: MeResponse types, MeCache, MeService
│   └── auth/
│       └── storage.py               # Add /me cache management
└── cli/
    ├── main.py                      # Register new command groups, global options
    ├── utils.py                     # Update get_workspace for new resolution
    └── commands/
        ├── auth.py                  # Simplify add, add migrate
        ├── projects.py              # NEW: mp projects command group
        ├── workspaces_cmd.py        # NEW: mp workspaces command group
        └── context.py              # NEW: mp context command group

tests/
├── unit/
│   ├── test_auth_credential.py      # NEW: AuthCredential, ProjectContext, ResolvedSession
│   ├── test_me.py                   # NEW: MeCache, MeService, MeResponse types
│   ├── test_config_v2.py            # NEW: v2 config CRUD, resolve_session
│   ├── test_migration.py            # NEW: v1→v2 migration
│   └── cli/
│       ├── test_projects_cli.py     # NEW: mp projects commands
│       ├── test_workspaces_cli.py   # NEW: mp workspaces commands
│       └── test_context_cli.py      # NEW: mp context commands
└── pbt/
    └── test_config_pbt.py           # NEW: Config round-trip property tests
```

**Structure Decision**: Extends the existing single-project layout. New modules go into `_internal/` (private implementation) with public types re-exported via `auth.py` and `__init__.py`. CLI commands follow existing `commands/` directory pattern.

## Complexity Tracking

> No violations found — section intentionally left empty.
