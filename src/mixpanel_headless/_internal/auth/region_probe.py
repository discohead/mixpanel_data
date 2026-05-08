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
- **`probe_region` itself takes no environment access.** Region order,
  headers, and timeout are parameters. The thin convenience wrapper
  ``probe_region_for_credential`` does read ``os.environ[token_env]``
  when wiring the ``oauth_token`` Authorization header — that single
  read is the documented exception, scoped to the wrapper.
- **No logging or stderr writes.** Progress narration is the caller's
  job; the function returns or raises with structured data.

Reference: ``specs/043-frictionless-auth/contracts/python-api.md`` §2.1.
"""

from __future__ import annotations

import base64
import os
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from pydantic import SecretStr

from mixpanel_headless._internal.auth.account import AccountType, Region
from mixpanel_headless.exceptions import (
    ConfigError,
    RegionProbeError,
    RegionProbeNetworkError,
)

ClientFactory = Callable[[Region], httpx.Client]
"""Builds an ``httpx.Client`` bound to a given region's API base URL."""


_ME_PATH = "/api/app/me"

# Cap each captured response body so a misconfigured server returning
# multi-MB HTML cannot bloat the in-memory ``RegionProbeError``
# (`.attempts` and `.details["attempts"]`) or any downstream JSON
# serialization. 4 KiB is enough room to keep a typical JSON error
# envelope intact while bounding the worst case.
_MAX_RESPONSE_BODY_CHARS = 4096


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
            failure_attempts.append(
                (
                    region,
                    response.status_code,
                    response.text[:_MAX_RESPONSE_BODY_CHARS],
                )
            )
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


def probe_region_for_credential(
    *,
    account_type: AccountType,
    username: str | None,
    secret: SecretStr | None,
    token: SecretStr | None,
    token_env: str | None,
    narrate: Callable[[str], None] | None = None,
) -> Region:
    """Build the credential header, probe ``us → eu → in``, return the region.

    Replaces the two near-identical inlined blocks that
    ``cli/commands/account.py::_probe_region_for_credential`` and
    ``accounts.py::_login_unified_new_credential`` used to carry. Both
    sites now call into this single helper; CLI passes ``narrate=`` to
    surface per-attempt progress on stderr, the library defaults to
    silent.

    Args:
        account_type: ``"service_account"`` or ``"oauth_token"``. Other
            types are rejected because there is no credential to test.
        username: Service-account username (required when
            ``account_type == "service_account"``).
        secret: Service-account secret (required when
            ``account_type == "service_account"``).
        token: Inline ``oauth_token`` bearer (mutually exclusive with
            ``token_env``).
        token_env: Env-var name carrying the ``oauth_token`` bearer
            (mutually exclusive with ``token``). The env-var lookup
            runs at call time; an unset value raises ``ConfigError``.
        narrate: Optional callback invoked with one human-readable
            message per probe step. CLI passes ``err_console.print``
            or ``sys.stderr.write``-style helpers; library callers
            leave it ``None`` for silent operation.

    Returns:
        The first region whose ``/me`` returned 200.

    Raises:
        ConfigError: Missing credential material for the given
            ``account_type``, or ``token_env`` points at an unset
            variable.
        RegionProbeError / RegionProbeNetworkError: Propagated from
            :func:`probe_region` when no region accepts the credential.
    """
    from mixpanel_headless._internal.api_client import ENDPOINTS

    if account_type == "service_account":
        if username is None or secret is None:
            raise ConfigError(
                "service_account region probe requires `username` and `secret`."
            )
        raw = f"{username}:{secret.get_secret_value()}".encode()
        headers = {"Authorization": f"Basic {base64.b64encode(raw).decode('ascii')}"}
    elif account_type == "oauth_token":
        if token is not None:
            bearer = token.get_secret_value()
        elif token_env is not None:
            bearer = os.environ.get(token_env, "")
            if not bearer:
                raise ConfigError(
                    f"--token-env {token_env!r} is unset; cannot probe region."
                )
        else:  # pragma: no cover — caller validated upstream
            raise ConfigError(
                "oauth_token region probe requires `token` or `token_env`."
            )
        headers = {"Authorization": f"Bearer {bearer}"}
    else:  # pragma: no cover — typed signature gates this
        raise ConfigError(
            f"Region probe is not defined for account type {account_type!r}."
        )

    def _factory(region: Region) -> httpx.Client:
        """Build a region-scoped ``httpx.Client`` bound to the API host."""
        app_url = ENDPOINTS[region]["app"]
        # ``ENDPOINTS[*]["app"]`` is currently
        # ``https://mixpanel.com/api/app`` — strip the path so
        # ``probe_region`` can issue ``/api/app/me`` against the host
        # root. ``urlsplit`` handles trailing slashes, future version
        # segments, query strings, and fragments without a fragile
        # substring search.
        parts = urllib.parse.urlsplit(app_url)
        base = urllib.parse.urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        return httpx.Client(base_url=base)

    if narrate is not None:
        narrate("Probing regions for /me access ...")
    result = probe_region(_factory, headers)
    if narrate is not None:
        for region_name, status in result.attempts:
            marker = "✓" if status == 200 else "✗"
            narrate(f"  {region_name}: {status} {marker}")
    return result.region
