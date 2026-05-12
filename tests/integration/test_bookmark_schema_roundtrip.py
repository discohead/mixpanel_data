"""Live integration tests: ``create_bookmark`` → ``get_bookmark`` → ``delete``.

Catches Mixpanel **bookmark-storage** schema drift end-to-end. For each
query type that has a canonical root model in our schema mirror, we:

1. Create a minimal-valid bookmark via ``Workspace.create_bookmark``
   (asserts both our client-side Pydantic check and the server's
   create-time validation accept the payload)
2. Read it back via ``Workspace.get_bookmark`` to confirm persistence
3. Delete the bookmark to keep the workspace clean (best-effort)

We intentionally **do not** call ``query_saved_report`` here — the
query-execution endpoint runs separate (legacy voluptuous-based)
validation that diverges from the bookmark-storage Pydantic schema we
mirror. A query-time rejection signals upstream Mixpanel-internal
schema drift, not a bug in our mirror, and conflating the two would
make these tests flaky against the wrong target.

If our local schema drifts from the server's bookmark-storage schema
(e.g. they add a required field, change a discriminator value, etc.),
the ``create_bookmark`` call will fail and these tests will surface it.

Skipped by default — opt in with ``MP_LIVE_TESTS=1``. Run via:

```
MP_LIVE_TESTS=1 just test tests/integration/test_bookmark_schema_roundtrip.py
```

Requires a real Mixpanel account configured in ``~/.mp/config.toml``
with write access to a dashboard. Uses a dedicated scratch dashboard so
nothing important gets deleted on cleanup.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Generator
from typing import Any

import pytest

import mixpanel_headless as mp
from mixpanel_headless import (
    CreateBookmarkParams,
    CreateDashboardParams,
)

# =============================================================================
# Minimal-valid params per query type
#
# Mirrored from tests/unit/test_workspace_crud.py module-level fixtures.
# Re-declared here so the live test doesn't pull in unit-test machinery.
# =============================================================================

MINIMAL_INSIGHTS_PARAMS: dict[str, Any] = {
    "displayOptions": {"chartType": "bar"},
    "sections": {
        "show": [
            {
                "type": "metric",
                "behavior": {"type": "event", "name": "$identify"},
            }
        ],
        "time": [
            {
                "dateRangeType": "in the last",
                "unit": "day",
                "window": {"unit": "day", "value": 30},
            }
        ],
    },
}

MINIMAL_FUNNEL_PARAMS: dict[str, Any] = {
    "displayOptions": {"chartType": "funnel-steps"},
    "sections": {
        "show": [
            {
                "type": "metric",
                "behavior": {
                    "type": "funnel",
                    "behaviors": [
                        {"type": "event", "name": "$identify"},
                        {"type": "event", "name": "$identify"},
                    ],
                },
            }
        ],
        "time": [
            {
                "dateRangeType": "in the last",
                "unit": "day",
                "window": {"unit": "day", "value": 30},
            }
        ],
    },
}

MINIMAL_RETENTION_PARAMS: dict[str, Any] = {
    "displayOptions": {"chartType": "retention-curve"},
    "sections": {
        "show": [
            {
                "type": "metric",
                "behavior": {
                    "type": "retention",
                    "behaviors": [
                        {"type": "event", "name": "$identify"},
                        {"type": "event", "name": "$identify"},
                    ],
                },
            }
        ],
        "time": [
            {
                "dateRangeType": "in the last",
                "unit": "day",
                "window": {"unit": "day", "value": 30},
            }
        ],
    },
}

MINIMAL_FLOWS_PARAMS: dict[str, Any] = {
    "steps": [{"event": "$identify", "forward": 3, "reverse": 0}],
    "date_range": {
        "from_date": "2025-01-01",
        "to_date": "2025-01-31",
    },
    "chartType": "sankey",
}


_LIVE_GUARD = pytest.mark.skipif(
    os.environ.get("MP_LIVE_TESTS") != "1",
    reason="Set MP_LIVE_TESTS=1 to run live bookmark round-trip tests.",
)


@pytest.fixture(scope="module")
def live_workspace() -> mp.Workspace:
    """Real Workspace using whatever account ``~/.mp/config.toml`` resolves.

    Module-scoped so all four query types share one dashboard + one
    HTTP client. The dashboard is created lazily on first use.
    """
    return mp.Workspace()


@pytest.fixture
def scratch_dashboard_id(
    live_workspace: mp.Workspace,
) -> Generator[int, None, None]:
    """Create a private scratch dashboard for the test, then delete it.

    Each test gets its own dashboard so failures don't leave stale
    bookmarks lying around.
    """
    dash = live_workspace.create_dashboard(
        CreateDashboardParams(
            title=("[mixpanel_headless CI] schema-roundtrip — safe to delete"),
            description=(
                "Auto-created by tests/integration/"
                "test_bookmark_schema_roundtrip.py. Auto-deleted on teardown."
            ),
            is_private=True,
        )
    )
    try:
        yield dash.id
    finally:
        # Best-effort cleanup; don't fail the test if cleanup fails.
        with contextlib.suppress(Exception):
            live_workspace.delete_dashboard(dash.id)


def _create_get_delete_roundtrip(
    ws: mp.Workspace,
    *,
    bookmark_type: str,
    name: str,
    params: dict[str, Any],
    dashboard_id: int,
) -> None:
    """Run the create → get → delete round-trip for one bookmark.

    Asserts the server accepts our payload at the bookmark-storage
    layer (which is what our schema mirror reflects). We deliberately
    skip ``query_saved_report`` because the query-execution endpoint
    runs separate (legacy voluptuous-based) validation that diverges
    from the bookmark-storage Pydantic schema we mirror — its failures
    indicate Mixpanel-internal schema drift, not problems in our
    client-side mirror.

    Asserts:

    1. ``create_bookmark`` succeeds (no client-side schema rejection,
       and the server's create-time Pydantic validation accepts it).
    2. ``get_bookmark`` returns a stored payload — proves persistence.
    3. ``delete_bookmark`` cleans up (best-effort; server returns 500
       on bookmark deletion in some workspaces, which is upstream
       and not the test's concern).
    """
    bm = ws.create_bookmark(
        CreateBookmarkParams(
            name=name,
            bookmark_type=bookmark_type,
            params=params,
            dashboard_id=dashboard_id,
        )
    )
    try:
        # Read back to confirm storage. The returned dict may include
        # server-applied migrations and normalized shapes (e.g.
        # ``behavior.type=event`` → ``simple`` wrapper); we only assert
        # that get returned a non-empty payload.
        fresh = ws.get_bookmark(bm.id)
        assert fresh.id == bm.id
        assert fresh.params is not None
    finally:
        with contextlib.suppress(Exception):
            ws.delete_bookmark(bm.id)


# =============================================================================
# Round-trip tests, one per query type with a canonical root model
# =============================================================================


@_LIVE_GUARD
@pytest.mark.live
def test_insights_roundtrip(
    live_workspace: mp.Workspace, scratch_dashboard_id: int
) -> None:
    """Insights bookmark round-trips against the live API."""
    _create_get_delete_roundtrip(
        live_workspace,
        bookmark_type="insights",
        name="[CI] insights schema roundtrip",
        params=MINIMAL_INSIGHTS_PARAMS,
        dashboard_id=scratch_dashboard_id,
    )


@_LIVE_GUARD
@pytest.mark.live
def test_funnel_roundtrip(
    live_workspace: mp.Workspace, scratch_dashboard_id: int
) -> None:
    """Funnel bookmark round-trips against the live API."""
    _create_get_delete_roundtrip(
        live_workspace,
        bookmark_type="funnels",
        name="[CI] funnel schema roundtrip",
        params=MINIMAL_FUNNEL_PARAMS,
        dashboard_id=scratch_dashboard_id,
    )


@_LIVE_GUARD
@pytest.mark.live
def test_retention_roundtrip(
    live_workspace: mp.Workspace, scratch_dashboard_id: int
) -> None:
    """Retention bookmark round-trips against the live API."""
    _create_get_delete_roundtrip(
        live_workspace,
        bookmark_type="retention",
        name="[CI] retention schema roundtrip",
        params=MINIMAL_RETENTION_PARAMS,
        dashboard_id=scratch_dashboard_id,
    )


@_LIVE_GUARD
@pytest.mark.live
def test_flows_roundtrip(
    live_workspace: mp.Workspace, scratch_dashboard_id: int
) -> None:
    """Flows bookmark round-trips against the live API.

    Flows uses a flat schema (no ``sections`` wrapper); the canonical
    root is ``FlowsBookmarkParams``.
    """
    _create_get_delete_roundtrip(
        live_workspace,
        bookmark_type="flows",
        name="[CI] flows schema roundtrip",
        params=MINIMAL_FLOWS_PARAMS,
        dashboard_id=scratch_dashboard_id,
    )
