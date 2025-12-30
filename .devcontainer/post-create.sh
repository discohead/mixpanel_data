#!/bin/bash
set -e

echo "Setting up mixpanel_data development environment..."

cd /workspace

# Clean up any stale virtual environment that might cause issues
if [ -d ".venv" ] && [ ! -f ".venv/bin/python" ]; then
    echo "Removing incomplete .venv directory..."
    rm -rf .venv
fi

# Install dependencies (uv sync creates venv automatically if needed)
echo "Installing dependencies..."
uv sync --all-extras

# Install pre-commit hooks if .pre-commit-config.yaml exists
if [ -f "/workspace/.pre-commit-config.yaml" ]; then
    echo "Installing pre-commit hooks..."
    uv run pre-commit install
fi

# Register the venv as a Jupyter kernel for JupyterLab
echo "Registering Jupyter kernel..."
uv run python -m ipykernel install --user --name mixpanel_data --display-name "mixpanel_data"

echo "Development environment ready!"
echo ""
echo "Run 'just' to see available commands, or use:"
echo "  just check    - Run all checks (lint, typecheck, test)"
echo "  just test     - Run tests"
echo "  just lint     - Lint code"
echo "  just fmt      - Format code"
echo "  just typecheck - Type check"
echo ""
echo "AI Assistants:"
echo "  claude        - Claude Code"
echo "  gh            - GitHub CLI"
