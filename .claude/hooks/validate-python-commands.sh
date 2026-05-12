#!/bin/bash
set -euo pipefail

# Read hook input from stdin
input=$(cat)

# Extract the command from the tool input
command=$(echo "$input" | jq -r '.tool_input.command // ""')

# Check if command contains bare python or python3
if echo "$command" | grep -qE '(^|[;&|]\s*)(python3?)\b' && ! echo "$command" | grep -q 'uv run python'; then
  # Deny the command
  cat >&2 <<'EOF'
{
  "hookSpecificOutput": {
    "permissionDecision": "deny"
  },
  "systemMessage": "🚫 **Bare python command blocked**\n\nThis project uses uv for dependency management. Please use 'uv run python' instead of bare 'python' or 'python3' commands.\n\n**Examples:**\n- ❌ python script.py → ✅ uv run python script.py\n- ❌ python3 -m pytest → ✅ uv run python -m pytest\n- ❌ python -c 'code' → ✅ uv run python -c 'code'\n\n**Why?** Bare python/python3 won't have access to project dependencies installed via uv."
}
EOF
  exit 2
fi

# Check if command contains bare pytest
if echo "$command" | grep -qE '(^|[;&|]\s*)(pytest)\b' && ! echo "$command" | grep -qE 'uv run (python -m )?pytest'; then
  # Deny the command
  cat >&2 <<'EOF'
{
  "hookSpecificOutput": {
    "permissionDecision": "deny"
  },
  "systemMessage": "🚫 **Bare pytest command blocked**\n\nThis project uses uv for dependency management. Please use 'uv run pytest' instead of bare 'pytest' commands.\n\n**Examples:**\n- ❌ pytest → ✅ uv run pytest\n- ❌ pytest tests/ → ✅ uv run pytest tests/\n- ❌ pytest -k test_name → ✅ uv run pytest -k test_name\n\n**Why?** Bare pytest won't have access to project dependencies installed via uv."
}
EOF
  exit 2
fi

# Approve the command
cat <<'EOF'
{
  "hookSpecificOutput": {
    "permissionDecision": "allow"
  }
}
EOF
exit 0
