<!--
SYNC IMPACT REPORT
==================
Version Change: (new) -> 1.0.0
Bump Rationale: Initial ratification - first constitution for greenfield project

Added Principles:
- I. Library-First
- II. Agent-Native Design
- III. Context Window Efficiency
- IV. Two Data Paths
- V. Explicit Over Implicit
- VI. Unix Philosophy
- VII. Secure by Default

Added Sections:
- Technology Stack (constraints and requirements)
- Development Workflow (phases and quality gates)
- Governance (amendment procedures)

Removed Sections: None (initial version)

Templates Requiring Updates:
- .specify/templates/plan-template.md: ✅ Compatible (Constitution Check section exists)
- .specify/templates/spec-template.md: ✅ Compatible (requirements structure aligns)
- .specify/templates/tasks-template.md: ✅ Compatible (phased approach aligns)
- .specify/templates/checklist-template.md: ✅ Compatible (generic structure)
- .specify/templates/agent-file-template.md: ✅ Compatible (generated from plans)

Follow-up TODOs: None
-->

# mixpanel-headless Constitution

## Core Principles

### I. Library-First

Every capability MUST be accessible programmatically before being exposed via CLI.

- The Python library (`mixpanel_headless`) is the source of truth; the CLI is a thin wrapper
- Library functions MUST be independently usable in scripts, notebooks, and other tools
- CLI commands MUST delegate to library functions for all logic; CLI handles only I/O formatting
- All public API methods MUST have type hints and docstrings

**Rationale**: Agents can import the library directly for complex analysis; humans get CLI convenience. Neither is privileged over the other.

### II. Agent-Native Design

All commands and library methods MUST be non-interactive and produce structured output.

- No interactive prompts, confirmations, or REPLs in the default path
- Output MUST be structured (JSON, CSV, JSONL) and composable into Unix pipelines
- Progress and status output MUST go to stderr; data MUST go to stdout
- Exit codes MUST be meaningful: 0=success, 1=error, 2=auth, 3=invalid args, 4=not found, 5=rate limit

**Rationale**: AI coding agents cannot respond to prompts or parse unstructured output. Agent-native design ensures both agents and automation scripts work reliably.

### III. Context Window Efficiency

The primary design goal MUST be minimizing tokens consumed by data retrieval.

- Data MUST be fetchable once and stored locally for repeated querying
- Responses MUST be precise answers, not raw data dumps
- Introspection commands MUST exist for agents to understand data shape before querying
- Large result sets MUST support pagination, limits, and streaming

**Rationale**: The context window is the agent's working memory. Every token consumed by data is a token not available for reasoning.

### IV. Two Data Paths

The system MUST support both live queries and local analysis.

- **Live queries**: Call Mixpanel API directly for quick, fresh answers (segmentation, funnels, retention)
- **Local analysis**: Fetch data to DuckDB, query with SQL, iterate without API calls
- Users MUST be able to choose the appropriate path for each task
- Both paths MUST share authentication and configuration

**Rationale**: Not every question needs local storage; not every analysis fits a standard report. The right tool for the job.

### V. Explicit Over Implicit

All operations that modify state MUST be explicit; no magic or hidden behavior.

- Table creation MUST fail with `TableExistsError` if table already exists
- Table destruction MUST require explicit `drop()` call
- Credentials MUST be resolved once at construction, stored immutably
- No global mutable state; all state lives in `Workspace` instances
- No implicit overwrites, merges, or upserts without explicit parameters

**Rationale**: Predictable behavior enables agent autonomy. Surprises break automated workflows.

### VI. Unix Philosophy

Do one thing well; compose with other tools.

- Output MUST be clean data suitable for piping to `jq`, `grep`, `awk`, etc.
- Errors MUST go to stderr with appropriate exit codes
- Large operations MUST support streaming (stdin/stdout)
- The tool MUST NOT attempt to do everything; integration points are first-class

**Rationale**: The ecosystem of Unix tools and Python libraries is vast. Composability multiplies capability.

### VII. Secure by Default

Credentials MUST never appear in code, logs, or output.

- Credentials MUST be stored in config files (`~/.mp/config.toml`) or environment variables
- Secrets MUST be redacted in all logging and error messages
- Config files MUST have restrictive permissions (600)
- No credential values in command-line arguments (use env vars or config refs)

**Rationale**: Security breaches from exposed credentials are preventable. Defense in depth.

## Technology Stack

The following technology choices are architectural constraints:

| Component         | Choice       | Constraint                              |
| ----------------- | ------------ | --------------------------------------- |
| Language          | Python 3.10+ | MUST use type hints throughout          |
| CLI Framework     | Typer        | MUST NOT use Click or argparse directly |
| Output Formatting | Rich         | MUST use for tables, progress bars      |
| Validation        | Pydantic v2  | MUST use for all API response models    |
| Database          | DuckDB       | MUST use for local storage; no SQLite   |
| HTTP Client       | httpx        | MUST use for all HTTP; no requests      |
| DataFrames        | pandas       | MUST support DataFrame conversion       |

**Dependency Policy**:

- Core dependencies MUST be minimal (Typer, Rich, Pydantic, DuckDB, httpx, pandas)
- Optional dependencies (notebooks, visualization) MUST be in `[project.optional-dependencies]`
- All dependencies MUST be pinned with minimum versions, not exact versions

## Development Workflow

### Implementation Phases

All development MUST follow this phased approach:

1. **Foundation**: ConfigManager, MixpanelAPIClient, StorageEngine, exceptions, result types
2. **Core**: FetcherService, DiscoveryService, Workspace orchestration, auth module
3. **Live Queries**: LiveQueryService, segmentation/funnel/retention methods, JQL support
4. **CLI**: Typer application, all command groups, formatters, progress bars
5. **Polish**: SKILL.md, documentation, integration tests, PyPI release

### Quality Gates

Before any PR merge:

- [ ] All public functions MUST have type hints
- [ ] All public functions MUST have docstrings (Google style)
- [ ] All new code MUST pass `ruff check` and `ruff format`
- [ ] All new code MUST pass `mypy --strict`
- [ ] Tests MUST exist for new functionality (pytest)
- [ ] CLI commands MUST have `--help` with examples

### Package Structure

```text
src/mixpanel_headless/
├── __init__.py              # Public API exports only
├── workspace.py             # Workspace facade class
├── auth.py                  # Public auth module
├── exceptions.py            # All exception classes
├── types.py                 # Result types, dataclasses
├── _internal/               # Private implementation (underscore prefix)
│   ├── config.py
│   ├── api_client.py
│   ├── storage.py
│   └── services/
└── cli/
    ├── main.py              # Typer app entry point
    └── commands/
```

## Governance

### Amendment Process

This Constitution supersedes all other development practices for mixpanel-headless.

1. **Proposal**: Create issue describing proposed amendment with rationale
2. **Discussion**: Allow minimum 48 hours for review
3. **Approval**: Amendments require explicit owner approval
4. **Migration**: If amendment affects existing code, include migration plan
5. **Version Bump**: Update constitution version per semantic versioning

### Versioning Policy

- **MAJOR**: Removal or redefinition of core principles
- **MINOR**: New principle added or significant expansion
- **PATCH**: Clarifications, typos, non-semantic refinements

### Compliance

- All PRs MUST reference applicable principles when making architectural decisions
- Violations MUST be documented with explicit justification in Complexity Tracking
- Periodic review (quarterly) to assess constitution fitness

**Version**: 1.0.0 | **Ratified**: 2025-12-19 | **Last Amended**: 2025-12-19
