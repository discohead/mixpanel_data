#!/bin/bash
# Claude Code PreToolUse hook: runs ruff format/check before git commit
#
# This hook intercepts Bash tool calls, checks if they're git commit commands,
# and runs linting/formatting on staged files first. If files are modified,
# they are automatically re-staged so the commit can proceed.

set -e

# Read hook input from stdin
input=$(cat)

# Extract the command being run
command=$(echo "$input" | jq -r '.tool_input.command // ""')

# Only process git commit commands
if [[ ! "$command" =~ ^git[[:space:]]+(commit|&& git commit) ]] && [[ ! "$command" =~ "git commit" ]]; then
  exit 0  # Not a git commit, allow it
fi

# Get list of staged Python files
staged_files=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.py$' || true)

if [ -z "$staged_files" ]; then
  exit 0  # No Python files staged, allow commit
fi

# Run ruff format on staged files only
echo "$staged_files" | xargs ruff format --quiet 2>/dev/null || true

# Run ruff check with auto-fix on staged files only
echo "$staged_files" | xargs ruff check --fix --quiet 2>/dev/null || true

# Re-stage any modified files
echo "$staged_files" | xargs git add 2>/dev/null || true

# All clean, allow the commit
exit 0
