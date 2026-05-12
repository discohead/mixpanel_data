# mixpanel_headless development commands
# Run `just` to see available commands

# Default: list available commands
default:
    @just --list

# Run all checks — must be a strict superset of CI (.github/workflows/ci.yml).
# CI runs the same commands plus HYPOTHESIS_PROFILE=ci for tests; that
# profile is the only documented difference (deterministic seed, 200 examples
# vs default 100). Locally we use the default profile for faster iteration.
check: lint fmt-check typecheck docstring-cov test-cov build

# Install git hooks so commits are blocked on lint/format failures BEFORE
# they reach CI. Run once after cloning the repo.
install-hooks:
    uv run --group dev pre-commit install

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

# Run the auth-subsystem fast iteration suite (042 redesign)
test-auth *args:
    uv run pytest tests/unit/test_account.py tests/unit/test_session.py \
        tests/unit/test_resolver.py tests/unit/test_workspace_use.py \
        tests/unit/test_config_v3.py tests/pbt/test_account_pbt.py \
        tests/pbt/test_resolver_pbt.py tests/pbt/test_session_pbt.py \
        -v {{ args }}

# Run the 042 live auth QA against real Mixpanel API (requires creds)
# Set env vars before running:
#   MP_LIVE_SA_USERNAME / _SA_SECRET / _SA_PROJECT_ID / _SA_REGION  (Cat A, D, G)
#   MP_LIVE_OAUTH_TOKEN / _PROJECT_ID / _REGION                     (Cat C, D, G)
#   (Cat B uses ~/.mp/oauth/tokens_us.json automatically)
test-live-auth *args:
    MP_LIVE_TESTS=1 uv run pytest tests/live/test_042_auth_redesign_live.py -v -m live {{ args }}

# === Mutation Testing ===

# Run mutation testing on entire codebase
mutate *args:
    uv run mutmut run {{ args }}

# Show mutation testing results
mutate-results:
    uv run mutmut results

# Show details for a specific mutant (e.g., just mutate-show 1)
mutate-show id:
    uv run mutmut show {{ id }}

# Apply a mutant to see the change (use 0 to reset)
mutate-apply id:
    uv run mutmut apply {{ id }}

# Check mutation score meets threshold (default 80%)
mutate-check threshold="80":
    #!/usr/bin/env bash
    set -euo pipefail
    RESULTS=$(uv run mutmut results 2>/dev/null | tail -1)
    KILLED=$(echo "$RESULTS" | grep -oP 'Killed \K\d+' || echo 0)
    SURVIVED=$(echo "$RESULTS" | grep -oP 'Survived \K\d+' || echo 0)
    TOTAL=$((KILLED + SURVIVED))
    if [ "$TOTAL" -eq 0 ]; then
        echo "No mutants found"
        exit 1
    fi
    SCORE=$((KILLED * 100 / TOTAL))
    echo "Mutation score: $SCORE% (killed $KILLED/$TOTAL, threshold {{ threshold }}%)"
    if [ "$SCORE" -lt {{ threshold }} ]; then
        echo "FAIL: Mutation score below threshold"
        exit 1
    fi
    echo "PASS: Mutation score meets threshold"

# Run tests with coverage (fails if below 90%)
test-cov:
    uv run pytest --cov=src/mixpanel_headless --cov-report=term-missing --cov-fail-under=90

# === Hypothesis CLI ===

# Refactor deprecated Hypothesis code (e.g., just hypo-codemod src/)
hypo-codemod *args:
    uv run hypothesis codemod {{ args }}

# Generate property-based tests for a module (e.g., just hypo-write mixpanel_headless.types)
hypo-write *args:
    uv run hypothesis write {{ args }}

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

# Docstring coverage — src is gated at 99% (see [tool.interrogate] in
# pyproject.toml); tests is gated at 95% via the second invocation. Bump
# either threshold up if coverage rises and you want to lock the gain in.
docstring-cov:
    uv run interrogate src/
    uv run interrogate tests/ --fail-under=95

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

# === Documentation ===

# Generate man pages for the CLI
man:
    uv run python -c "from typer.main import get_command; from mixpanel_headless.cli.main import app; from click_man.core import write_man_pages; write_man_pages('mp', get_command(app), target_dir='./man')"

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

# === Plugin Development ===

# Validate plugin structure (JSON, YAML, references)
plugin-validate:
    @./mixpanel-plugin/scripts/validate.sh mixpanel-plugin

# Check version sync between plugin.json and marketplace.json
plugin-check-version:
    #!/usr/bin/env bash
    set -euo pipefail
    PLUGIN_VERSION=$(jq -r '.version' mixpanel-plugin/.claude-plugin/plugin.json)
    MARKETPLACE_VERSION=$(jq -r '.plugins[0].version' mixpanel-plugin/.claude-plugin/marketplace.json)
    if [ "$PLUGIN_VERSION" = "$MARKETPLACE_VERSION" ]; then
        echo "✓ Versions match: $PLUGIN_VERSION"
    else
        echo "✗ Version mismatch:"
        echo "  plugin.json:            $PLUGIN_VERSION"
        echo "  marketplace.json (dev): $MARKETPLACE_VERSION"
        exit 1
    fi

# Plugin statistics
plugin-stats:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📊 Plugin statistics:"
    echo ""

    # Commands
    CMD_COUNT=$(ls -1 mixpanel-plugin/commands/*.md 2>/dev/null | wc -l)
    CMD_LINES=$(wc -l mixpanel-plugin/commands/*.md 2>/dev/null | tail -1 | awk '{print $1}')
    echo "Commands:    $CMD_COUNT files, $CMD_LINES lines"

    # Skills
    SKILL_COUNT=$(find mixpanel-plugin/skills -name "*.md" -type f 2>/dev/null | wc -l)
    SKILL_LINES=$(find mixpanel-plugin/skills -name "*.md" -type f 2>/dev/null | xargs wc -l | tail -1 | awk '{print $1}')
    echo "Skills:      $SKILL_COUNT files, $SKILL_LINES lines"

    # Agents (if any)
    AGENT_LINES=0
    if [ -d mixpanel-plugin/agents ]; then
        AGENT_COUNT=$(find mixpanel-plugin/agents -name "*.md" -type f 2>/dev/null | wc -l)
        if [ "$AGENT_COUNT" -gt 0 ]; then
            AGENT_LINES=$(find mixpanel-plugin/agents -name "*.md" -type f | xargs wc -l | tail -1 | awk '{print $1}')
            echo "Agents:      $AGENT_COUNT files, $AGENT_LINES lines"
        fi
    fi

    # Total
    TOTAL_LINES=$((CMD_LINES + SKILL_LINES + AGENT_LINES))
    echo ""
    echo "Total:       $TOTAL_LINES lines"
