"""Shared minimal-valid bookmark ``params`` fixtures for unit tests.

Each constant is the smallest dict that passes the canonical schema mirror
in ``mixpanel_data._internal.bookmark_schema``. CRUD tests pass these
instead of empty/garbage dicts so they exercise the full code path
(including client-side Pydantic validation) without false-rejection.

Imported by ``test_workspace_crud.py`` and ``test_workspace_crud_edge.py``.
Lives in a private module (leading underscore) so pytest doesn't try to
collect it as a test file.
"""

from __future__ import annotations

from typing import Any

MINIMAL_INSIGHTS_PARAMS: dict[str, Any] = {
    "displayOptions": {"chartType": "bar"},
    "sections": {
        "show": [
            {
                "type": "metric",
                "behavior": {"type": "event", "name": "Login"},
            }
        ],
        "time": [],
    },
}
"""Minimal valid insights bookmark params dict."""

MINIMAL_FUNNEL_PARAMS: dict[str, Any] = {
    "displayOptions": {"chartType": "funnel-steps"},
    "sections": {
        "show": [
            {
                "type": "metric",
                "behavior": {
                    "type": "funnel",
                    "behaviors": [
                        {"type": "event", "name": "Signup"},
                        {"type": "event", "name": "Purchase"},
                    ],
                },
            }
        ],
        "time": [],
    },
}
"""Minimal valid funnel bookmark params dict."""

MINIMAL_RETENTION_PARAMS: dict[str, Any] = {
    "displayOptions": {"chartType": "retention-curve"},
    "sections": {
        "show": [
            {
                "type": "metric",
                "behavior": {
                    "type": "retention",
                    "behaviors": [
                        {"type": "event", "name": "Signup"},
                        {"type": "event", "name": "Login"},
                    ],
                },
            }
        ],
        "time": [],
    },
}
"""Minimal valid retention bookmark params dict."""
