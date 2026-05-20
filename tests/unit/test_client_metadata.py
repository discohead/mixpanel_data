"""Unit tests for the client_metadata helper module."""

from __future__ import annotations

import sys
from collections.abc import Iterator

import pytest

from mixpanel_headless import __version__
from mixpanel_headless._internal import client_metadata
from mixpanel_headless._internal.client_metadata import (
    QUERY_ORIGIN,
    get_entry_point,
    get_user_agent,
    set_entry_point,
)


@pytest.fixture(autouse=True)
def _reset_entry_point() -> Iterator[None]:
    """Force ``"lib"`` for each test, then restore the prior value.

    The entry point is a process-wide constant that any prior CLI import
    (in this test session or another) may have flipped to ``"cli"``. To
    keep these tests deterministic, set ``"lib"`` at start; restore the
    original at end so test ordering can't leak state out.
    """
    original = get_entry_point()
    set_entry_point("lib")
    yield
    set_entry_point(original)


class TestQueryOrigin:
    """Static constant used to attribute Query API traffic."""

    def test_query_origin_value(self) -> None:
        """QUERY_ORIGIN identifies this library."""
        assert QUERY_ORIGIN == "mixpanel-headless"


class TestEntryPoint:
    """Entry-point flag flipped by the CLI on startup."""

    def test_default_entry_point_is_lib(self) -> None:
        """Library callers see entry=lib by default."""
        assert get_entry_point() == "lib"

    def test_set_entry_point_to_cli(self) -> None:
        """CLI startup flips the entry point."""
        set_entry_point("cli")
        assert get_entry_point() == "cli"

    def test_set_entry_point_round_trip(self) -> None:
        """Flipping cli then back to lib restores the default."""
        set_entry_point("cli")
        set_entry_point("lib")
        assert get_entry_point() == "lib"


class TestUserAgent:
    """User-Agent string composition."""

    def test_user_agent_starts_with_package_name(self) -> None:
        """User-Agent leads with the package name and version."""
        ua = get_user_agent()
        assert ua.startswith(f"mixpanel-headless/{__version__}")

    def test_user_agent_includes_entry_tag(self) -> None:
        """User-Agent surfaces the current entry point."""
        set_entry_point("lib")
        assert "entry=lib" in get_user_agent()
        set_entry_point("cli")
        assert "entry=cli" in get_user_agent()

    def test_user_agent_includes_python_version(self) -> None:
        """User-Agent surfaces the running Python's major.minor."""
        py = f"python/{sys.version_info.major}.{sys.version_info.minor}"
        assert py in get_user_agent()

    def test_user_agent_format(self) -> None:
        """Full format matches: name/ver (entry=...; python/x.y)."""
        set_entry_point("lib")
        py = f"{sys.version_info.major}.{sys.version_info.minor}"
        expected = f"mixpanel-headless/{__version__} (entry=lib; python/{py})"
        assert get_user_agent() == expected

    def test_user_agent_reflects_entry_point_flip(self) -> None:
        """A flip after import is reflected on the next call (no caching)."""
        set_entry_point("lib")
        first = get_user_agent()
        set_entry_point("cli")
        second = get_user_agent()
        assert first != second
        assert "entry=lib" in first
        assert "entry=cli" in second


class TestModuleStateIsolation:
    """The autouse fixture must force ``"lib"`` regardless of prior state."""

    def test_fixture_forces_lib_during_test(self) -> None:
        """During a test body, the entry point is ``"lib"``."""
        assert client_metadata.get_entry_point() == "lib"
