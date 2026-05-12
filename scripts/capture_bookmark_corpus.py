#!/usr/bin/env python3
"""Read-only one-shot script to capture a real-bookmark corpus for parity smoke testing.

Walks ``Workspace.list_bookmarks_v2()`` for each query type, fetches the
full payload via ``Workspace.get_bookmark()``, and dumps to
``tests/fixtures/bookmark_corpus/{type}/{id}.json``. The corpus then
becomes input to ``scripts/validate_corpus.py`` (or a future
``test_bookmark_corpus_parity.py`` test) which runs the new
``bookmark_schema`` Pydantic models against every captured payload to
detect false-rejections before we tighten the schema further.

This script is **not** in CI — it touches the live Mixpanel API and
writes files into the repo. Run manually before bumping schema versions
or expanding ``extra="forbid"`` coverage.

Usage:

```
uv run python scripts/capture_bookmark_corpus.py [--limit N] [--out DIR]
```

Defaults:

- ``--limit 30``: capture up to 30 bookmarks per query type
- ``--out tests/fixtures/bookmark_corpus``: output directory

Requires authenticated ``~/.mp/config.toml`` (or env-var account).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import mixpanel_headless as mp

_BOOKMARK_TYPES: tuple[str, ...] = (
    "insights",
    "funnels",
    "retention",
    "flows",
)
"""Query types we have a canonical schema mirror for. ``user`` excluded —
it has no canonical bookmark schema in the analytics source we mirror."""


def _capture_one_type(
    ws: mp.Workspace,
    bookmark_type: str,
    limit: int,
    out_dir: Path,
) -> tuple[int, int]:
    """Capture up to ``limit`` bookmarks of one type to ``out_dir/{type}/``.

    Args:
        ws: Authenticated Workspace.
        bookmark_type: One of ``"insights"``, ``"funnels"``,
            ``"retention"``, ``"flows"``.
        limit: Maximum number of bookmarks to capture.
        out_dir: Root output directory. Files land in
            ``out_dir/{bookmark_type}/{id}.json``.

    Returns:
        ``(captured, errored)`` tuple of counts.
    """
    type_dir = out_dir / bookmark_type
    type_dir.mkdir(parents=True, exist_ok=True)

    print(f"  {bookmark_type}: listing...", flush=True)
    bookmarks = ws.list_bookmarks_v2(bookmark_type=bookmark_type)
    targets = bookmarks[:limit]
    print(
        f"  {bookmark_type}: fetching {len(targets)} of {len(bookmarks)} bookmarks..."
    )

    captured = 0
    errored = 0
    for bm in targets:
        try:
            full = ws.get_bookmark(bm.id)
            # Preserve original params shape — let validate_corpus.py
            # flag malformed entries explicitly. Coercing None/falsy → {}
            # would silently corrupt the parity evidence.
            params: Any = full.params
            if isinstance(params, str):
                params = json.loads(params)
            payload: dict[str, Any] = {
                "id": full.id,
                "name": full.name,
                "bookmark_type": full.bookmark_type,
                "params": params,
            }
            (type_dir / f"{full.id}.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            captured += 1
        except Exception as e:  # noqa: BLE001
            print(f"    {bm.id}: failed: {type(e).__name__}: {e}")
            errored += 1

    return captured, errored


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Capture a real-bookmark corpus from the live Mixpanel API. "
            "Used to smoke-test bookmark_schema parity before bumping "
            "schema strictness."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Max bookmarks to capture per query type (default: 30).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("tests/fixtures/bookmark_corpus"),
        help="Output directory (default: tests/fixtures/bookmark_corpus).",
    )
    args = parser.parse_args()

    print("Capturing bookmark corpus from live Mixpanel API...")
    print(f"  Output: {args.out}")
    print(f"  Limit per type: {args.limit}")
    print()

    ws = mp.Workspace()
    print(
        f"Authenticated as: {ws.account.username if hasattr(ws.account, 'username') else ws.account.name}"
    )
    print(f"Project: {ws.project.id}")
    print()

    args.out.mkdir(parents=True, exist_ok=True)

    total_captured = 0
    total_errored = 0
    for bt in _BOOKMARK_TYPES:
        captured, errored = _capture_one_type(ws, bt, args.limit, args.out)
        print(f"    captured={captured} errored={errored}")
        total_captured += captured
        total_errored += errored

    print()
    print(f"Done. {total_captured} bookmarks captured, {total_errored} errored.")
    print(f"Files: {args.out}/{{insights,funnels,retention,flows}}/*.json")
    print()
    print("Next: run the validator over the corpus to surface schema gaps:")
    print("  uv run python scripts/validate_corpus.py")
    return 0 if total_errored == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
