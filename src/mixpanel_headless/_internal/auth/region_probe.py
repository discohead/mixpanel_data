"""Pure-functional region probe for ``/api/app/me`` (043 / AIE-114).

Walks a configurable region ordering (default ``us → eu → in``),
issuing GET ``/api/app/me`` against each region's API base URL via a
caller-supplied :data:`ClientFactory`. Returns the first 200 as a
:class:`RegionProbeResult`; raises
:class:`mixpanel_headless.exceptions.RegionProbeError` carrying the
full attempt list when no region accepts the credential.

Design constraints (per ``contracts/python-api.md`` §2.1):

- **No I/O of its own.** All HTTP work goes through ``client_factory``
  so tests can supply a ``MockTransport``-backed client without
  touching the real network.
- **No environment access.** Region order, headers, and timeout are
  parameters — never read from ``os.environ`` here.
- **No logging or stderr writes.** Progress narration is the caller's
  job; the function returns or raises with structured data.

Reference: ``specs/043-frictionless-auth/contracts/python-api.md`` §2.1.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import httpx

from mixpanel_headless._internal.auth.account import Region
from mixpanel_headless.exceptions import RegionProbeError, RegionProbeNetworkError

ClientFactory = Callable[[Region], httpx.Client]
"""Builds an ``httpx.Client`` bound to a given region's API base URL."""


_ME_PATH = "/api/app/me"


@dataclass(frozen=True)
class RegionProbeResult:
    """Outcome of a sequential region probe.

    Attributes:
        region: The first region whose ``/me`` returned 200.
        attempts: Ordered list of ``(region, status_code)`` tuples for
            every probe attempt up to and including the successful one.
            Always non-empty. Useful for telemetry and CLI progress
            narration.

    Example:
        ```python
        result = probe_region(client_factory, headers={"Authorization": "Basic xxx"})
        # RegionProbeResult(region="eu", attempts=[("us", 401), ("eu", 200)])
        for region, status in result.attempts:
            print(f"{region}: {status}")
        ```
    """

    region: Region
    """The first region whose probe returned 200."""

    attempts: list[tuple[Region, int]]
    """Ordered ``(region, status_code)`` log of every attempt."""


def probe_region(
    client_factory: ClientFactory,
    headers: dict[str, str],
    *,
    timeout_seconds: float = 5.0,
    order: tuple[Region, ...] = ("us", "eu", "in"),
) -> RegionProbeResult:
    """Sequentially probe regions until one accepts the credential.

    For each region in ``order``, builds an ``httpx.Client`` via
    ``client_factory(region)``, issues GET ``/api/app/me`` carrying
    ``headers``, and returns on the first 200. Network errors
    (``httpx.RequestError``) are recorded as status code ``0`` with the
    failure reason in the attempt body.

    The function short-circuits at the first 200: subsequent regions in
    ``order`` are NOT probed. This keeps the common case (US works) at
    one round-trip.

    Args:
        client_factory: Callable that returns a region-scoped
            ``httpx.Client``. The returned client is closed before the
            function returns. Allows tests to inject ``MockTransport``
            without monkey-patching.
        headers: Request headers carrying the credential
            (``Authorization: Basic ...`` for SA, ``Bearer ...`` for
            token). Caller assembles these so this function does not
            have to know about credential variants.
        timeout_seconds: Per-region request timeout (float seconds).
            Default ``5.0``. Each region gets its own timeout budget;
            slow regions never block the next probe.
        order: Probe ordering. Default ``("us", "eu", "in")`` per
            spec R-1. Pass a custom tuple to skip regions or change the
            sequence.

    Returns:
        :class:`RegionProbeResult` carrying the resolved region and the
        ordered ``(region, status_code)`` attempt list.

    Raises:
        RegionProbeError: When every region in ``order`` fails to return
            200. ``RegionProbeError.attempts`` carries the full
            ``(region, status_code, error_body)`` list for each probed
            region.

    Example:
        ```python
        from mixpanel_headless._internal.auth.region_probe import probe_region
        import httpx

        def factory(region: str) -> httpx.Client:
            return httpx.Client(base_url=f"https://{region}.mixpanel.com")

        result = probe_region(factory, headers={"Authorization": "Basic xxx"})
        print(result.region)  # "us" (first 200)
        ```
    """
    success_attempts: list[tuple[Region, int]] = []
    failure_attempts: list[tuple[Region, int, str]] = []

    for region in order:
        client = client_factory(region)
        try:
            try:
                response = client.get(
                    _ME_PATH, headers=headers, timeout=timeout_seconds
                )
            except httpx.RequestError as exc:
                # Network-layer failure: DNS, TLS, connect refused, etc.
                # Recorded as status 0 so callers can render it
                # consistently with HTTP failures in the same table.
                failure_attempts.append((region, 0, f"{type(exc).__name__}: {exc}"))
                continue
            if response.status_code == 200:
                success_attempts.append((region, 200))
                # Mirror the failure tail back into success_attempts so
                # the caller sees the full probe history (US 401 → EU 200
                # appears as [("us", 401), ("eu", 200)]).
                full_attempts = [
                    (r, s) for r, s, _ in failure_attempts
                ] + success_attempts
                return RegionProbeResult(region=region, attempts=full_attempts)
            failure_attempts.append((region, response.status_code, response.text))
        finally:
            client.close()

    # Every region failed. Distinguish "credential rejected" from "could
    # not reach any region at the network layer" so the CLI can pick a
    # remediation hint that matches the user's actual problem (a 401
    # tells them to check creds; a string of network errors tells them
    # to check connectivity).
    if all(status == 0 for _, status, _ in failure_attempts):
        raise RegionProbeNetworkError(
            "Could not reach any Mixpanel region — every probe failed at "
            "the network layer (DNS, TLS, or connect refused).",
            attempts=failure_attempts,
        )
    raise RegionProbeError(
        "Credential not valid in any region.",
        attempts=failure_attempts,
    )
