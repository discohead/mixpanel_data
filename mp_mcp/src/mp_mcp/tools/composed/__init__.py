"""Composed (Tier 2) tools for Mixpanel analytics.

This package contains tools that orchestrate multiple primitive tools:

- dashboard: product_health_dashboard - AARRR product health metrics
- gqm: gqm_investigation - Goal-Question-Metric structured investigation
- cohort: cohort_comparison - Compare two cohorts across dimensions

These tools compose multiple Tier 1 (primitive) tools to provide
higher-level analytical capabilities.

Example:
    Ask Claude: "Show me a product health dashboard for signups"
    Claude uses: product_health_dashboard(acquisition_event="signup")
"""

# Import tool modules to register them with the server
# These imports happen when this package is imported by server.py
from mp_mcp.tools.composed import cohort, dashboard, gqm  # noqa: F401

__all__ = [
    "cohort",
    "dashboard",
    "gqm",
]
