#!/bin/bash
set -e

# Only run in remote (Claude Code on the web) environments
if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then
  exit 0
fi

echo "Setting up Claude Code remote environment..."

# Install uv if not available (not in Anthropic universal image by default)
if ! command -v uv &> /dev/null; then
  echo "Installing uv package manager..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# Install just if not available (command runner used by this project)
if ! command -v just &> /dev/null; then
  echo "Installing just command runner..."
  curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to "$HOME/.local/bin"
fi

# Install dependencies
uv sync --all-extras

# Persist paths for subsequent commands (uv and venv)
if [ -n "$CLAUDE_ENV_FILE" ]; then
  echo "PATH=$HOME/.local/bin:/workspace/.venv/bin:\$PATH" >> "$CLAUDE_ENV_FILE"
fi

echo "Environment ready!"
