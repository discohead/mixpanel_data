"""Shared fixtures for integration tests in the auth architecture redesign.

Provides hermetic temporary `~/.mp/` homes, mock-response harnesses, and
opt-in markers for live-API tests. Pulls Hypothesis profile registration in
through the project-wide ``tests/conftest.py``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def tmp_mp_home(monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """Yield a temporary ``$HOME`` with isolated ``~/.mp/`` and ``MP_CONFIG_PATH``.

    Sets both ``HOME`` and ``MP_CONFIG_PATH`` so any code that derives paths
    from either source lands inside the tmp directory. The ``~/.mp/`` parent
    is created with mode ``0o700`` to mirror production permissions.

    Yields:
        Path to the temporary ``$HOME`` directory; the canonical config lives
        at ``<home>/.mp/config.toml``.
    """
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_home = Path(tmp_str)
        mp_dir = tmp_home / ".mp"
        mp_dir.mkdir(mode=0o700)
        monkeypatch.setenv("HOME", str(tmp_home))
        monkeypatch.setenv("MP_CONFIG_PATH", str(mp_dir / "config.toml"))
        yield tmp_home


@pytest.fixture
def recorded_responses() -> dict[str, object]:
    """Return an empty dict for tests to register mock HTTP response payloads.

    Tests should populate this dict keyed by URL path and assert calls via
    ``httpx.MockTransport`` constructed from the dict. Pre-baked here so
    every contract-layer test starts from the same scaffold.

    Returns:
        Empty mutable dict that the caller fills with ``{path: payload}``.
    """
    return {}


@pytest.fixture
def live_marker() -> bool:
    """Return whether live API tests are enabled via ``MP_LIVE_TESTS=1``.

    Tests marked ``@pytest.mark.live`` should call this fixture (or check
    ``os.environ`` themselves) to decide whether to run real API calls or
    skip with a clear reason. The pytest config already deselects ``live``
    by default; this fixture provides a programmatic gate for tests that
    want to make their own runtime decision.

    Returns:
        ``True`` if ``MP_LIVE_TESTS`` env var is set to ``"1"``.
    """
    return os.environ.get("MP_LIVE_TESTS") == "1"
