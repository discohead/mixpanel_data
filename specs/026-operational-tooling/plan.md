# Implementation Plan: Operational Tooling — Alerts, Annotations, and Webhooks

**Branch**: `026-operational-tooling` | **Date**: 2026-03-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/026-operational-tooling/spec.md`

## Summary

Add full CRUD for custom alerts (11 methods), timeline annotations (7 methods), and project webhooks (5 methods) to the Python `mixpanel_data` library and CLI. All three domains follow the established three-layer pattern (API client → Workspace → CLI) using the existing App API infrastructure with `maybe_scoped_path()` routing. Implementation adds ~20 Pydantic models to `types.py`, ~23 API client methods, ~23 Workspace methods, and 3 new CLI command files with ~23 subcommands total.

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict)
**Primary Dependencies**: httpx (HTTP), Pydantic v2 (validation), Typer (CLI), Rich (output)
**Storage**: N/A (remote CRUD via Mixpanel App API; no DuckDB involvement)
**Testing**: pytest + respx (HTTP mocking) + Hypothesis (property-based) + mutmut (mutation)
**Target Platform**: Cross-platform (macOS, Linux, Windows)
**Project Type**: Library + CLI
**Performance Goals**: N/A — bounded by Mixpanel API latency
**Constraints**: Must follow existing three-layer CRUD patterns exactly; 90% test coverage; mypy --strict
**Scale/Scope**: 23 new API endpoints, ~20 Pydantic models, 3 CLI command files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | PASS | All 23 operations exposed as Workspace methods before CLI commands |
| II. Agent-Native Design | PASS | All CLI commands non-interactive, structured output, meaningful exit codes |
| III. Context Window Efficiency | PASS | CRUD responses are precise objects, not data dumps; alert history supports pagination |
| IV. Two Data Paths | N/A | These are remote CRUD operations, no local storage path |
| V. Explicit Over Implicit | PASS | No implicit state changes; all operations require explicit parameters |
| VI. Unix Philosophy | PASS | JSON/CSV/table/plain/JSONL output; jq filtering; composable with pipes |
| VII. Secure by Default | PASS | Webhook passwords handled as sensitive data; no secrets in logs/output |

**Gate Result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/026-operational-tooling/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── types.py                          # ADD: ~20 Pydantic models (alerts, annotations, webhooks)
├── workspace.py                      # ADD: ~23 methods (alerts, annotations, webhooks)
├── _internal/
│   └── api_client.py                 # ADD: ~23 API methods (alerts, annotations, webhooks)
└── cli/
    ├── main.py                       # MODIFY: register 3 new command groups
    └── commands/
        ├── alerts.py                 # CREATE: 11 subcommands
        ├── annotations.py           # CREATE: 7 subcommands
        └── webhooks.py              # CREATE: 5 subcommands

tests/
├── test_types_alerts.py              # CREATE: Alert Pydantic model tests
├── test_types_annotations.py         # CREATE: Annotation Pydantic model tests
├── test_types_webhooks.py            # CREATE: Webhook Pydantic model tests
├── test_api_client_alerts.py         # CREATE: Alert API client tests (respx)
├── test_api_client_annotations.py    # CREATE: Annotation API client tests (respx)
├── test_api_client_webhooks.py       # CREATE: Webhook API client tests (respx)
├── test_workspace_alerts.py          # CREATE: Alert workspace method tests
├── test_workspace_annotations.py     # CREATE: Annotation workspace method tests
├── test_workspace_webhooks.py        # CREATE: Webhook workspace method tests
└── integration/cli/
    ├── test_alert_commands.py        # CREATE: Alert CLI tests
    ├── test_annotation_commands.py   # CREATE: Annotation CLI tests
    └── test_webhook_commands.py      # CREATE: Webhook CLI tests
```

**Structure Decision**: Follows established single-project pattern. Types stay in `types.py` (additive). API client and workspace are extended (not new files). CLI gets 3 new command files matching existing pattern (dashboards.py, reports.py, cohorts.py, flags.py, experiments.py).
