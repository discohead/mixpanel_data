"""Unit tests for the pure-functional region probe (043 / AIE-114).

The probe walks a configurable ordering (default ``us → eu → in``)
against ``/api/app/me``, stops at the first 200, and raises
:class:`RegionProbeError` when no region accepts the credential. The
caller injects a ``client_factory`` so tests can supply ``httpx.Client``
instances bound to ``MockTransport`` instead of hitting the real network.

Reference: ``specs/043-frictionless-auth/contracts/python-api.md`` §2.1.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from mixpanel_headless._internal.auth.account import Region
from mixpanel_headless._internal.auth.region_probe import (
    RegionProbeResult,
    probe_region,
)
from mixpanel_headless.exceptions import RegionProbeError

# ---- helpers ---------------------------------------------------------


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    """Build an ``httpx.Client`` bound to a ``MockTransport``.

    Sets a placeholder ``base_url`` so the probe's relative
    ``/api/app/me`` request resolves to a valid absolute URL — mirrors
    the real ``client_factory`` contract where each returned client is
    pre-bound to the region's API base URL.

    Args:
        handler: The mock response handler.

    Returns:
        An ``httpx.Client`` with the mock transport and a placeholder
        base URL attached.
    """
    return httpx.Client(
        base_url="https://test.invalid",
        transport=httpx.MockTransport(handler),
    )


def _factory_for(
    handlers: dict[Region, Callable[[httpx.Request], httpx.Response]],
    *,
    visited: list[Region] | None = None,
) -> Callable[[Region], httpx.Client]:
    """Build a region → client factory backed by per-region handlers.

    The optional ``visited`` list captures the order of ``client_factory``
    invocations so tests can assert short-circuit behavior.
    """

    def _factory(region: Region) -> httpx.Client:
        if visited is not None:
            visited.append(region)
        return _client(handlers[region])

    return _factory


def _ok_handler(request: httpx.Request) -> httpx.Response:
    """Return 200 with a minimal /me payload."""
    return httpx.Response(200, json={"user_id": 1})


def _unauth_handler(request: httpx.Request) -> httpx.Response:
    """Return 401 Unauthorized."""
    return httpx.Response(401, text="Unauthorized")


def _network_error_handler(request: httpx.Request) -> httpx.Response:
    """Raise an httpx network error."""
    raise httpx.ConnectError("DNS lookup failed")


# ---- tests -----------------------------------------------------------


class TestProbeRegionHappyPaths:
    """First-200-wins behavior across the default ordering."""

    def test_us_succeeds_first_short_circuits(self) -> None:
        """US 200 → returns immediately; EU and IN are never probed."""
        visited: list[Region] = []
        factory = _factory_for(
            {"us": _ok_handler, "eu": _ok_handler, "in": _ok_handler},
            visited=visited,
        )
        result = probe_region(factory, headers={"Authorization": "Basic xxx"})
        assert isinstance(result, RegionProbeResult)
        assert result.region == "us"
        assert result.attempts == [("us", 200)]
        assert visited == ["us"], "EU/IN should not be probed after US success"

    def test_eu_succeeds_after_us_fails(self) -> None:
        """US 401 then EU 200 → EU returned; IN never probed."""
        visited: list[Region] = []
        factory = _factory_for(
            {"us": _unauth_handler, "eu": _ok_handler, "in": _ok_handler},
            visited=visited,
        )
        result = probe_region(factory, headers={"Authorization": "Basic xxx"})
        assert result.region == "eu"
        assert result.attempts == [("us", 401), ("eu", 200)]
        assert visited == ["us", "eu"]

    def test_in_succeeds_after_us_and_eu_fail(self) -> None:
        """US 401 + EU 401 + IN 200 → IN returned."""
        visited: list[Region] = []
        factory = _factory_for(
            {"us": _unauth_handler, "eu": _unauth_handler, "in": _ok_handler},
            visited=visited,
        )
        result = probe_region(factory, headers={"Authorization": "Basic xxx"})
        assert result.region == "in"
        assert result.attempts == [("us", 401), ("eu", 401), ("in", 200)]
        assert visited == ["us", "eu", "in"]


class TestProbeRegionErrorPaths:
    """Failure modes — all-region failure and network errors."""

    def test_all_regions_401_raises_with_full_attempts(self) -> None:
        """All 401 → ``RegionProbeError`` carrying every attempt."""
        factory = _factory_for(
            {
                "us": _unauth_handler,
                "eu": _unauth_handler,
                "in": _unauth_handler,
            }
        )
        with pytest.raises(RegionProbeError) as exc_info:
            probe_region(factory, headers={"Authorization": "Basic xxx"})
        # Three attempts, in order; each carries the response body.
        assert len(exc_info.value.attempts) == 3
        regions = [a[0] for a in exc_info.value.attempts]
        codes = [a[1] for a in exc_info.value.attempts]
        bodies = [a[2] for a in exc_info.value.attempts]
        assert regions == ["us", "eu", "in"]
        assert codes == [401, 401, 401]
        assert all("Unauthorized" in b for b in bodies)

    def test_network_error_rendered_as_status_zero(self) -> None:
        """``httpx.ConnectError`` → recorded as status ``0`` with reason."""
        factory = _factory_for(
            {
                "us": _network_error_handler,
                "eu": _unauth_handler,
                "in": _unauth_handler,
            }
        )
        with pytest.raises(RegionProbeError) as exc_info:
            probe_region(factory, headers={"Authorization": "Basic xxx"})
        attempts = exc_info.value.attempts
        # First attempt is the network error.
        assert attempts[0][0] == "us"
        assert attempts[0][1] == 0
        # Body carries the network error reason for diagnostic use.
        assert "DNS lookup failed" in attempts[0][2] or "ConnectError" in attempts[0][2]


class TestProbeRegionOrdering:
    """The ``order`` parameter is honored verbatim."""

    def test_custom_order_eu_first(self) -> None:
        """``order=('eu', 'us')`` probes EU first."""
        visited: list[Region] = []
        factory = _factory_for(
            {"eu": _ok_handler, "us": _ok_handler, "in": _ok_handler},
            visited=visited,
        )
        result = probe_region(
            factory,
            headers={"Authorization": "Basic xxx"},
            order=("eu", "us"),
        )
        assert result.region == "eu"
        assert visited == ["eu"]

    def test_custom_order_skips_unlisted_regions(self) -> None:
        """``order=('eu',)`` probes only EU; doesn't fall through to others."""
        factory = _factory_for(
            {"eu": _unauth_handler, "us": _ok_handler, "in": _ok_handler}
        )
        with pytest.raises(RegionProbeError) as exc_info:
            probe_region(
                factory,
                headers={"Authorization": "Basic xxx"},
                order=("eu",),
            )
        assert [a[0] for a in exc_info.value.attempts] == ["eu"]


class TestProbeRegionTimeout:
    """The ``timeout_seconds`` parameter is plumbed into ``client.get``."""

    def test_timeout_is_passed_to_request(self) -> None:
        """The probe sends ``timeout=timeout_seconds`` on the GET call."""
        captured_timeouts: list[object] = []

        def _capture_handler(request: httpx.Request) -> httpx.Response:
            # httpx attaches the per-request timeout to the request.extensions
            # dict under the ``timeout`` key. The exact representation is an
            # implementation detail of httpx — we only assert it's not the
            # default-sentinel value (None / a sentinel for "use client default").
            captured_timeouts.append(request.extensions.get("timeout"))
            return httpx.Response(200, json={"user_id": 1})

        factory = _factory_for(
            {"us": _capture_handler, "eu": _ok_handler, "in": _ok_handler}
        )
        result = probe_region(
            factory,
            headers={"Authorization": "Basic xxx"},
            timeout_seconds=2.5,
        )
        assert result.region == "us"
        assert len(captured_timeouts) == 1
        # The captured timeout should reflect the 2.5-second value across
        # at least one of httpx's connect/read/write/pool axes.
        timeout_value = captured_timeouts[0]
        assert timeout_value is not None
        # ``timeout_value`` is an httpx-internal dict in recent versions.
        # We just confirm a 2.5-second figure is present somewhere.
        assert any(
            v == 2.5
            for v in (
                timeout_value.values()
                if isinstance(timeout_value, dict)
                else [timeout_value]
            )
        )


class TestProbeRegionSendsHeaders:
    """The supplied headers reach the request unchanged."""

    def test_authorization_header_forwarded(self) -> None:
        """The probe forwards the caller's ``Authorization`` header."""
        captured: list[str | None] = []

        def _capture_handler(request: httpx.Request) -> httpx.Response:
            captured.append(request.headers.get("Authorization"))
            return httpx.Response(200, json={"user_id": 1})

        factory = _factory_for(
            {"us": _capture_handler, "eu": _ok_handler, "in": _ok_handler}
        )
        probe_region(factory, headers={"Authorization": "Basic SECRET"})
        assert captured == ["Basic SECRET"]

    def test_request_targets_me_endpoint(self) -> None:
        """The probe issues GET against ``/api/app/me`` on each region's base URL."""
        captured_paths: list[str] = []

        def _capture_handler(request: httpx.Request) -> httpx.Response:
            captured_paths.append(request.url.path)
            return httpx.Response(200, json={"user_id": 1})

        factory = _factory_for(
            {"us": _capture_handler, "eu": _ok_handler, "in": _ok_handler}
        )
        probe_region(factory, headers={})
        assert captured_paths == ["/api/app/me"]
