# Contributing to mixpanel_headless

Thank you for your interest in contributing to mixpanel_headless!

> **Note**: This package is currently in pre-release and not yet published to PyPI. We welcome contributions, but please be aware that APIs may change between versions as we work toward a stable 1.0 release.

## Development Setup

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (package manager)
- [just](https://github.com/casey/just) (command runner)

### Recommended: Use the Devcontainer

The repository includes a devcontainer with Python 3.10, uv, just, and all development tools pre-installed. This is the easiest way to get started.

### Manual Setup

```bash
# Clone the repository
git clone https://github.com/mixpanel/mixpanel-headless.git
cd mixpanel-headless

# Install dependencies
uv sync --all-extras

# Verify setup
just check
```

## Development Commands

This project uses [just](https://github.com/casey/just) as a command runner. Run `just` to see all available commands.

| Command | Description |
|---------|-------------|
| `just` | List all available commands |
| `just check` | Run all checks (lint, typecheck, test) |
| `just test` | Run tests (supports args: `just test -k foo`) |
| `just test-cov` | Run tests with coverage |
| `just lint` | Lint code with ruff |
| `just lint-fix` | Auto-fix lint errors |
| `just fmt` | Format code with ruff |
| `just typecheck` | Type check with mypy |
| `just sync` | Sync dependencies |
| `just clean` | Remove caches and build artifacts |
| `just build` | Build package |
| `just mp` | Run the CLI (supports args: `just mp --help`) |

## Running Tests

```bash
# Run all tests
just test

# Run specific tests
just test -k test_workspace

# Run with coverage
just test-cov
```

## Code Quality

Before submitting a PR, run all checks:

```bash
just check
```

This runs:
- `ruff check` — Linting
- `mypy --strict` — Type checking
- `pytest` — Tests

## Project Structure

```
src/mixpanel_headless/
├── __init__.py              # Public API exports
├── workspace.py             # Workspace facade class
├── auth.py                  # Public auth module
├── exceptions.py            # Exception hierarchy
├── types.py                 # Result types
├── _internal/               # Private implementation
│   ├── config.py            # ConfigManager, Credentials
│   ├── api_client.py        # MixpanelAPIClient
│   └── services/            # Service layer
│       ├── discovery.py     # DiscoveryService
│       └── live_query.py    # LiveQueryService
└── cli/
    ├── main.py              # Typer app entry point
    ├── utils.py             # Error handling, console
    ├── formatters.py        # Output formatters
    ├── validators.py        # Input validation
    └── commands/            # Command implementations
        ├── auth.py
        ├── query.py
        ├── inspect.py
        ├── schemas.py
        └── lexicon.py

tests/
├── conftest.py              # Shared pytest fixtures
├── unit/                    # Unit tests
└── integration/             # Integration tests
```

## Architecture

```
CLI Layer (Typer)           → Argument parsing, output formatting
    ↓
Public API Layer            → Workspace class, auth module
    ↓
Service Layer               → DiscoveryService, LiveQueryService
    ↓
Infrastructure Layer        → ConfigManager, MixpanelAPIClient
```

**Two data paths:**
- **Live queries**: Call Mixpanel API directly (segmentation, funnels, retention)
- **Streaming**: Stream events and profiles directly for ETL or processing

## Design Principles

- **Streaming data access**: API returns iterators for memory-efficient processing
- **Immutable credentials**: Resolved once at Workspace construction
- **Dependency injection**: Services accept dependencies as constructor arguments for testing

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run `just check` to verify quality
5. Commit your changes with a clear message
6. Push to your fork
7. Open a Pull Request

## Questions?

Open an issue on GitHub for questions or discussion.
