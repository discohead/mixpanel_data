# mixpanel_data development commands
# Run `just` to see available commands

# Default: list available commands
default:
    @just --list

# Run all checks (lint, typecheck, test)
check: lint typecheck test

# Run tests
test *args:
    uv run pytest {{ args }}

# Run tests with dev Hypothesis profile (fast, 10 examples)
test-dev *args:
    HYPOTHESIS_PROFILE=dev uv run pytest {{ args }}

# Run tests with CI Hypothesis profile (thorough, 200 examples, deterministic)
test-ci *args:
    HYPOTHESIS_PROFILE=ci uv run pytest {{ args }}

# Run property-based tests only
test-pbt *args:
    uv run pytest -k "_pbt" {{ args }}

# Run property-based tests with dev profile (fast iteration)
test-pbt-dev *args:
    HYPOTHESIS_PROFILE=dev uv run pytest -k "_pbt" {{ args }}

# Run property-based tests with CI profile (thorough)
test-pbt-ci *args:
    HYPOTHESIS_PROFILE=ci uv run pytest -k "_pbt" {{ args }}

# Run tests with coverage (fails if below 90%)
test-cov:
    uv run pytest --cov=src/mixpanel_data --cov-report=term-missing --cov-fail-under=90

# Lint code with ruff
lint *args:
    uv run ruff check src/ tests/ {{ args }}

# Fix lint errors automatically
lint-fix:
    uv run ruff check --fix src/ tests/

# Format code with ruff
fmt:
    uv run ruff format src/ tests/

# Check formatting without applying changes
fmt-check:
    uv run ruff format --check src/ tests/

# Type check with mypy
typecheck:
    uv run mypy src/ tests/

# Sync dependencies
sync:
    uv sync --all-extras

# Clean build artifacts and caches
clean:
    rm -rf .pytest_cache .mypy_cache .ruff_cache
    rm -rf dist build *.egg-info
    rm -rf .coverage htmlcov
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Build package
build: clean
    uv build

# Run the CLI
mp *args:
    uv run mp {{ args }}

# === Documentation ===

# Build documentation
docs:
    uv run mkdocs build

# Serve documentation locally with live reload
docs-serve:
    uv run mkdocs serve

# Deploy docs to GitHub Pages (manual, uses gh-pages branch)
# --force is used because gh-pages contains only build artifacts, not source history
docs-deploy:
    uv run mkdocs gh-deploy --force

# Clean documentation build artifacts
docs-clean:
    rm -rf site/
