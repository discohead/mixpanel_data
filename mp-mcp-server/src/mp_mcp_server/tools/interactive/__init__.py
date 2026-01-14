"""Interactive tools for Mixpanel analytics with user elicitation.

This package contains tools that use ctx.elicit() for user interaction:

- safe_fetch: safe_large_fetch - Confirm large data fetches before execution
- guided: guided_analysis - Multi-step guided analysis workflow

These tools use ctx.elicit() to request user input mid-execution,
enabling interactive workflows and confirmation dialogs.

Example:
    Ask Claude: "Fetch all events from the last 90 days"
    Claude uses: safe_large_fetch(from_date="...", to_date="...")
    Claude prompts: "This will fetch ~1M events. Proceed?"
"""

# Import tool modules to register them with the server
# These imports happen when this package is imported by server.py
from mp_mcp_server.tools.interactive import guided, safe_fetch  # noqa: F401

__all__ = [
    "guided",
    "safe_fetch",
]
