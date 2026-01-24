"""Intelligent (Tier 3) tools for Mixpanel analytics.

This package contains tools that use LLM sampling for synthesis:

- diagnose: diagnose_metric_drop - Analyze metric drops with AI synthesis
- ask: ask_mixpanel - Natural language analytics queries
- funnel_report: funnel_optimization_report - Funnel analysis with recommendations

These tools use ctx.sample() for LLM synthesis and gracefully degrade
to raw data when sampling is unavailable.

Example:
    Ask Claude: "Why did signups drop on January 7th?"
    Claude uses: diagnose_metric_drop(event="signup", date="2026-01-07")
"""

# Import tool modules to register them with the server
# These imports happen when this package is imported by server.py
from mp_mcp.tools.intelligent import ask, diagnose, funnel_report  # noqa: F401

__all__ = [
    "ask",
    "diagnose",
    "funnel_report",
]
