#!/bin/bash
set -e

echo "Setting up mixpanel_data development environment..."

cd /workspace

# Install dependencies (uv sync creates venv automatically if needed)
echo "Installing dependencies..."
uv sync --all-extras

# Install pre-commit hooks if .pre-commit-config.yaml exists
if [ -f "/workspace/.pre-commit-config.yaml" ]; then
    echo "Installing pre-commit hooks..."
    uv run pre-commit install
fi

echo "Development environment ready!"
echo ""
echo "Available commands:"
echo "  uv run pytest      - Run tests"
echo "  uv run ruff check  - Check code style"
echo "  uv run mypy src    - Type check"
echo "  mp                 - CLI (once implemented)"
echo ""
echo "AI Assistants:"
echo "  claude             - Claude Code (runs with --dangerously-skip-permissions)"
echo "  copilot            - GitHub Copilot CLI"
echo "  gh                 - GitHub CLI"
