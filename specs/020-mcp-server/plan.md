# Implementation Plan: MCP Server for mixpanel_data

**Branch**: `020-mcp-server` | **Date**: 2026-01-12 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/020-mcp-server/spec.md`
**Reference**: [Detailed TDD Implementation Plan](../../context/implementation-plans/2026-01-12-mcp-server-implementation-plan.md)

## Summary

Create a production-ready MCP (Model Context Protocol) server that exposes `mixpanel_data` library capabilities to AI assistants like Claude Desktop. The server enables natural language analytics workflows: schema discovery, live queries (segmentation, funnels, retention), data fetching, and local SQL analysis—all through MCP tools, resources, and prompts.

## Technical Context

**Language/Version**: Python 3.11+ (matches mixpanel_data requirements)
**Primary Dependencies**:
- `fastmcp>=2.0,<3` - MCP server framework
- `mixpanel_data>=0.1.0` - Analytics library (local dependency)

**Storage**: DuckDB (via mixpanel_data Workspace - shared session state)
**Testing**: pytest with FastMCP in-memory Client for integration tests
**Target Platform**:
- Local: stdio transport (Claude Desktop, subprocess-based clients)
- Remote: HTTP transport (web service deployments)

**Project Type**: Single package (sibling to mixpanel_data)
**Performance Goals**: Tool responses within Mixpanel API latency bounds
**Constraints**:
- No new external dependencies beyond FastMCP
- Must follow mixpanel_data quality standards (90% coverage, mypy --strict)
- MCP protocol compliance for all transports

**Scale/Scope**: 39 MCP tools, 9 resources, 4 prompts

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| I. Library-First | ✅ PASS | MCP server wraps Workspace methods directly; all logic in library |
| II. Agent-Native Design | ✅ PASS | MCP protocol is inherently structured; JSON outputs from `.to_dict()` |
| III. Context Window Efficiency | ✅ PASS | Resources for cacheable schema; tools for on-demand queries |
| IV. Two Data Paths | ✅ PASS | Live query tools + fetch/SQL tools both exposed |
| V. Explicit Over Implicit | ✅ PASS | TableExistsError preserved; no implicit overwrites |
| VI. Unix Philosophy | ✅ PASS | Tools do one thing; composable via MCP protocol |
| VII. Secure by Default | ✅ PASS | Credentials resolved at server startup via env/config; not in protocol |

**Technology Stack Compliance**:
| Component | Constitution | This Feature | Status |
|-----------|--------------|--------------|--------|
| Language | Python 3.11+ | Python 3.11+ | ✅ |
| CLI Framework | Typer | argparse (for mp-mcp-server only) | ⚠️ See note |
| Validation | Pydantic v2 | FastMCP handles | ✅ |
| Database | DuckDB | Via mixpanel_data | ✅ |
| HTTP Client | httpx | Via mixpanel_data | ✅ |

**Note on CLI**: The `mp-mcp-server` command uses `argparse` as it's a simple entry point (3 flags), not a full CLI experience. Typer overhead not justified for `--account`, `--transport`, `--port`.

## Project Structure

### Documentation (this feature)

```text
specs/020-mcp-server/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (MCP tool schemas)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
mp-mcp-server/
├── pyproject.toml                    # Package configuration
├── README.md                         # User documentation
├── claude_desktop_config.json        # Example configuration
├── src/mp_mcp_server/
│   ├── __init__.py                   # Package initialization
│   ├── server.py                     # FastMCP server + lifespan
│   ├── context.py                    # get_workspace() helper
│   ├── errors.py                     # Exception → ToolError conversion
│   ├── cli.py                        # Entry point
│   ├── resources.py                  # MCP resources
│   ├── prompts.py                    # MCP prompts
│   └── tools/
│       ├── __init__.py
│       ├── discovery.py              # 9 discovery tools
│       ├── live_query.py             # 14 live query tools
│       ├── fetch.py                  # 4 fetch tools
│       └── local.py                  # 12 local analysis tools
└── tests/
    ├── conftest.py                   # Shared fixtures
    ├── unit/
    │   ├── test_server.py
    │   ├── test_context.py
    │   ├── test_errors.py
    │   ├── test_cli.py
    │   ├── test_resources.py
    │   ├── test_prompts.py
    │   └── test_tools_*.py           # Per-category tool tests
    └── integration/
        └── test_server_integration.py
```

**Structure Decision**: Separate `mp-mcp-server` package at repository root, sibling to `src/mixpanel_data`. This keeps MCP concerns isolated while depending on the library. Installation: `pip install ./mp-mcp-server` (or publish to PyPI separately).

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| argparse instead of Typer | mp-mcp-server CLI has only 3 flags | Typer adds dependencies for trivial use case |
