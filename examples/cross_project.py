"""Cross-project iteration patterns (US7 / T083).

Demonstrates the two supported flows for working across multiple Mixpanel
projects within a single Python session:

1. **Sequential mode** — mutate a single :class:`mixpanel_headless.Workspace`
   in place via ``ws.use(project=...)``. The connection pool, auth header
   (when account is unchanged), and ``/me`` cache are all reused — each
   iteration is O(1) per FR-061 / SC-008.
2. **Snapshot mode** — derive immutable :class:`mixpanel_headless.Session`
   snapshots via ``base_session.replace(project=...)`` and dispatch
   them across worker threads with :class:`ThreadPoolExecutor`. Each
   thread builds its own ``Workspace`` from the snapshot; nothing
   mutates shared state.

The sequential pattern is the right default — switching is cheap, the
HTTP client is shared, and the ``/me`` cache populates once. Snapshot
mode is the parallel-execution escape hatch.

Reference:
    specs/042-auth-architecture-redesign/spec.md US7
    specs/042-auth-architecture-redesign/research.md R5
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import mixpanel_headless as mp


def sequential_iteration() -> None:
    """Walk every accessible project, count events in each."""
    ws = mp.Workspace()
    try:
        # First call populates the per-account /me cache.
        for project in ws.projects():
            ws.use(project=project.id)
            count = len(ws.events())
            name = project.name or "(unnamed)"
            print(f"{name:20s} ({project.id}): {count} events")
    finally:
        ws.close()


def snapshot_parallel_iteration() -> None:
    """Run per-project queries in parallel using Session snapshots."""
    ws = mp.Workspace()
    try:
        base_session = ws.session
        snapshots = [
            base_session.replace(project=mp.Project(id=project.id))
            for project in ws.projects()
        ]
    finally:
        ws.close()

    def _per_snapshot(session: mp.Session) -> tuple[str, int]:
        """Build a Workspace from the snapshot and run one read."""
        worker_ws = mp.Workspace(session=session)
        try:
            return session.project.id, len(worker_ws.events())
        finally:
            worker_ws.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        for project_id, count in pool.map(_per_snapshot, snapshots):
            print(f"  {project_id}: {count} events")


if __name__ == "__main__":
    print("Sequential:")
    sequential_iteration()
    print("\nSnapshot (parallel):")
    snapshot_parallel_iteration()
