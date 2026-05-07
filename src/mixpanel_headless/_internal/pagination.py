"""Cursor-based pagination helper for Mixpanel App API.

Provides a generic paginator that follows cursor-based pagination
through App API responses. Used by domain-specific methods to iterate
through all pages of results.

This is a private implementation detail. Users should use the Workspace
class methods instead of accessing this module directly.
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import httpx

from mixpanel_headless.exceptions import (
    AuthenticationError,
    MixpanelDataError,
    RateLimitError,
    ServerError,
)

if TYPE_CHECKING:
    from mixpanel_headless._internal.api_client import MixpanelAPIClient

logger = logging.getLogger(__name__)

#: Maximum number of pages to fetch before raising an error.
#: Prevents infinite loops when the server returns a non-null cursor indefinitely.
MAX_PAGES: int = 10000

#: Maximum number of retries for rate-limited (429) responses per page request.
MAX_RATE_LIMIT_RETRIES: int = 3

#: Base delay in seconds for exponential backoff on 429 retries.
_BACKOFF_BASE: float = 1.0

#: Maximum backoff delay in seconds.
_BACKOFF_MAX: float = 60.0


def paginate_all(
    client: MixpanelAPIClient,
    path: str,
    *,
    params: dict[str, str] | None = None,
    page_size: int = 100,
) -> Iterator[Any]:
    """Iterate through all pages of a paginated App API response.

    Makes repeated calls to ``client.app_request("GET", path, ...)`` following
    the ``next_cursor`` field in pagination metadata until all pages are
    exhausted.

    The App API returns paginated responses in this shape::

        {
            "status": "ok",
            "results": [...],
            "pagination": {
                "page_size": 100,
                "next_cursor": "abc123" | null
            }
        }

    Since ``app_request()`` unwraps the ``results`` field, this function
    makes a raw request to get the full response including pagination metadata.

    Args:
        client: MixpanelAPIClient instance to use for requests.
        path: App API path (e.g., ``/projects/12345/dashboards``).
        params: Optional additional query parameters to include in each request.
        page_size: Number of items per page (default 100).

    Yields:
        Individual items from across all pages of results.

    Raises:
        AuthenticationError: Invalid credentials (401).
        RateLimitError: Rate limit exceeded after max retries (429).
        ServerError: Server-side errors (5xx).
        MixpanelDataError: Client errors (400, 404, 422), network/connection
            errors, or pagination limit exceeded.

    Example:
        ```python
        with MixpanelAPIClient(credentials) as client:
            all_dashboards = list(paginate_all(
                client,
                "/projects/12345/dashboards",
                page_size=50,
            ))
        ```
    """
    next_cursor: str | None = None
    page_count = 0

    while True:
        page_count += 1

        if page_count > MAX_PAGES:
            raise MixpanelDataError(
                "Pagination exceeded maximum page limit",
                code="PAGINATION_LIMIT",
                details={"max_pages": MAX_PAGES, "path": path},
            )

        # Build request params with query_origin
        request_params: dict[str, str] = {
            "page_size": str(page_size),
            "query_origin": "mixpanel-headless-cli",
        }
        if params:
            request_params.update(params)
        if next_cursor is not None:
            request_params["cursor"] = next_cursor

        # Make the raw request to get full response with pagination
        url = client._build_url("app", path)
        auth_header = client._get_auth_header()
        headers = {"Authorization": auth_header}

        http_client = client._ensure_client()
        response: httpx.Response | None = None

        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            try:
                response = http_client.request(
                    "GET",
                    url,
                    params=request_params,
                    headers=headers,
                    timeout=client._timeout,
                )
            except httpx.HTTPError as exc:
                raise MixpanelDataError(
                    f"Network error during pagination: {exc}",
                    code="NETWORK_ERROR",
                    details={"path": path, "error": str(exc)},
                ) from exc

            # Handle 429 with retry/backoff
            if response.status_code == 429:
                if attempt >= MAX_RATE_LIMIT_RETRIES:
                    retry_after_raw = response.headers.get("Retry-After")
                    retry_after: int | None = None
                    if retry_after_raw:
                        with contextlib.suppress(ValueError):
                            retry_after = int(retry_after_raw)
                    raise RateLimitError(
                        "Rate limit exceeded after max retries during pagination",
                        retry_after=retry_after,
                        status_code=429,
                        response_body=response.text,
                        request_method="GET",
                        request_url=url,
                    )
                retry_after_raw = response.headers.get("Retry-After")
                wait_time: float
                if retry_after_raw:
                    try:
                        wait_time = float(retry_after_raw)
                    except ValueError:
                        wait_time = min(_BACKOFF_BASE * (2**attempt), _BACKOFF_MAX)
                else:
                    wait_time = min(_BACKOFF_BASE * (2**attempt), _BACKOFF_MAX)
                logger.warning(
                    "Rate limited during pagination, retrying in %.1f seconds "
                    "(attempt %d/%d)",
                    wait_time,
                    attempt + 1,
                    MAX_RATE_LIMIT_RETRIES,
                )
                time.sleep(wait_time)
                continue

            # Not a 429 — break out of retry loop
            break

        # At this point response is guaranteed non-None
        assert response is not None  # noqa: S101

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body = exc.response.text
            if status == 401:
                raise AuthenticationError(
                    f"Authentication failed during pagination: {body}",
                    status_code=status,
                    response_body=body,
                    request_method="GET",
                    request_url=url,
                ) from exc
            if status >= 500:
                raise ServerError(
                    f"Server error during pagination: {body}",
                    status_code=status,
                    response_body=body,
                    request_method="GET",
                    request_url=url,
                ) from exc
            raise MixpanelDataError(
                f"HTTP {status} during pagination: {body}",
                code="API_ERROR",
                details={"status_code": status, "response_body": body},
            ) from exc

        try:
            data = response.json()
        except Exception as exc:
            raise MixpanelDataError(
                f"Non-JSON response during pagination (content-type: "
                f"{response.headers.get('content-type', 'unknown')})",
                code="INVALID_RESPONSE",
                details={"content_type": response.headers.get("content-type")},
            ) from exc

        # Extract results
        results: list[Any] = []
        if isinstance(data, dict):
            results = data.get("results", [])
        elif isinstance(data, list):
            results = data

        yield from results

        # Check for next page
        pagination = data.get("pagination") if isinstance(data, dict) else None
        if pagination and isinstance(pagination, dict):
            next_cursor = pagination.get("next_cursor")
        else:
            next_cursor = None

        if next_cursor is None:
            break
