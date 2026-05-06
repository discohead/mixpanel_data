"""Mixpanel API Client.

Low-level HTTP client for all Mixpanel APIs. Handles:
- Authentication via HTTP Basic auth (service accounts) or OAuth 2.0 Bearer tokens
- Regional endpoint routing (US, EU, India)
- Automatic rate limit handling with exponential backoff
- Streaming JSONL parsing for large exports

This is a private implementation detail. Users should use the Workspace class
or service layer instead of accessing this module directly.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import quote

import httpx

from mixpanel_data._internal.auth.account import (
    Account,
    OAuthBrowserAccount,
    OAuthTokenAccount,
    ServiceAccount,
    TokenResolver,
)
from mixpanel_data._internal.auth.session import (
    Project,
    Session,
    WorkspaceRef,
)
from mixpanel_data._internal.auth.token_resolver import OnDiskTokenResolver
from mixpanel_data.exceptions import (
    AuthenticationError,
    JQLSyntaxError,
    MixpanelDataError,
    QueryError,
    RateLimitError,
    ServerError,
    WorkspaceScopeError,
)
from mixpanel_data.types import ProfilePageResult, PublicWorkspace

if TYPE_CHECKING:
    from types import TracebackType

logger = logging.getLogger(__name__)


def _iter_jsonl_lines(response: httpx.Response) -> Iterator[str]:
    """Iterate over JSONL lines from a streaming response with proper buffering.

    The httpx iter_lines() method can incorrectly split lines at chunk boundaries,
    especially with gzip-compressed responses. This function uses iter_bytes() with
    manual buffering to handle incomplete lines correctly.

    Args:
        response: An httpx streaming Response object (from client.stream()).

    Yields:
        Complete lines from the response, stripped of trailing newlines.
        Empty lines are skipped.

    Example:
        ```python
        with client.stream("GET", url) as response:
            for line in _iter_jsonl_lines(response):
                event = json.loads(line)
        ```
    """
    # Use bytearray for efficient in-place buffer extension (bytes would copy on each +=)
    buffer = bytearray()
    for chunk in response.iter_bytes():
        buffer.extend(chunk)
        # Extract complete lines from buffer
        while True:
            newline_pos = buffer.find(b"\n")
            if newline_pos == -1:
                break
            line = bytes(buffer[:newline_pos])
            del buffer[: newline_pos + 1]
            line_str = line.decode("utf-8", errors="replace").strip()
            if line_str:
                yield line_str
    # Handle any remaining data in buffer (final line without trailing newline)
    if buffer:
        line_str = bytes(buffer).decode("utf-8", errors="replace").strip()
        if line_str:
            yield line_str


# Regional endpoint configuration
# Each region has separate URLs for query APIs and export/data APIs
ENDPOINTS: dict[str, dict[str, str]] = {
    "us": {
        "query": "https://mixpanel.com/api/query",
        "export": "https://data.mixpanel.com/api/2.0",
        "engage": "https://mixpanel.com/api/2.0/engage",
        "app": "https://mixpanel.com/api/app",
    },
    "eu": {
        "query": "https://eu.mixpanel.com/api/query",
        "export": "https://data-eu.mixpanel.com/api/2.0",
        "engage": "https://eu.mixpanel.com/api/2.0/engage",
        "app": "https://eu.mixpanel.com/api/app",
    },
    "in": {
        "query": "https://in.mixpanel.com/api/query",
        "export": "https://data-in.mixpanel.com/api/2.0",
        "engage": "https://in.mixpanel.com/api/2.0/engage",
        "app": "https://in.mixpanel.com/api/app",
    },
}


class MixpanelAPIClient:
    """Low-level HTTP client for Mixpanel APIs.

    Handles authentication, rate limiting, and response parsing. Most users
    won't use this directly—they'll use the Workspace class instead.

    Example:
        ```python
        from mixpanel_data._internal.auth.resolver import resolve_session
        from mixpanel_data._internal.api_client import MixpanelAPIClient

        session = resolve_session()

        with MixpanelAPIClient(session=session) as client:
            events = client.get_events()
            print(events)
        ```
    """

    def __init__(
        self,
        *,
        session: Session,
        timeout: float = 120.0,
        export_timeout: float = 600.0,
        max_retries: int = 3,
        token_resolver: TokenResolver | None = None,
        _transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Initialize the API client.

        Args:
            session: Resolved Session (account + project + optional workspace).
            timeout: Request timeout in seconds for regular requests.
            export_timeout: Request timeout for export operations.
            max_retries: Maximum retry attempts for rate-limited requests.
            token_resolver: For OAuth accounts; defaults to
                :class:`OnDiskTokenResolver`.
            _transport: Internal parameter for testing with MockTransport.
        """
        self._token_resolver: TokenResolver = token_resolver or OnDiskTokenResolver()
        self._session: Session = session
        # Cache the Basic auth header for service accounts so we don't
        # base64-encode on every request. OAuth headers resolve per call
        # via TokenResolver and are not cached here.
        self._cached_basic_header: str | None = (
            session.account.auth_header(token_resolver=self._token_resolver)
            if isinstance(session.account, ServiceAccount)
            else None
        )
        self._timeout = timeout
        self._export_timeout = export_timeout
        self._max_retries = max_retries
        self._client: httpx.Client | None = None
        self._transport = _transport
        self._workspace_id: int | None = (
            session.workspace.id if session.workspace else None
        )
        self._cached_workspace_id: int | None = None
        self._resolved_workspace: WorkspaceRef | None = session.workspace

    def _get_auth_header(self) -> str:
        """Generate the Authorization header value, resolving per request.

        For OAuth accounts (browser or static token), delegates to the bound
        :class:`TokenResolver` on every call so a refreshed bearer is picked
        up without rebuilding the API client. Service accounts return the
        cached ``Basic ...`` header since Basic Auth has no freshness concern.

        Returns:
            Authorization header value appropriate for the auth method.

        Raises:
            OAuthError: An OAuth account's token cannot be re-resolved
                (e.g. on-disk tokens deleted or refresh failed).
        """
        account = self._session.account
        if isinstance(account, ServiceAccount):
            assert self._cached_basic_header is not None
            return self._cached_basic_header
        if isinstance(account, OAuthBrowserAccount):
            token = self._token_resolver.get_browser_token(account.name, account.region)
            return f"Bearer {token}"
        if isinstance(account, OAuthTokenAccount):
            token = self._token_resolver.get_static_token(account)
            return f"Bearer {token}"
        raise TypeError(  # pragma: no cover — Literal exhaustiveness
            f"Unknown Account variant: {type(account).__name__}"
        )

    def _build_url(self, api_type: str, path: str) -> str:
        """Build full URL for the given API type and path.

        Args:
            api_type: One of "query", "export", "engage", or "app".
            path: API endpoint path (e.g., "/segmentation").

        Returns:
            Full URL for the endpoint.
        """
        region = self._session.account.region
        base = ENDPOINTS[region][api_type]
        # Ensure path starts with /
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{base}{path}"

    def _ensure_client(self) -> httpx.Client:
        """Ensure the underlying HTTP client (connection pool) is initialized.

        Headers are NOT cached on the client — they are composed per-request
        by :meth:`_request_headers` so that ``use(account=...)`` swapping the
        ``Session`` instantly affects subsequent requests without forcing a
        connection-pool teardown. See Fix 3 for the per-request rationale.

        Returns:
            The httpx.Client instance (connection pool only).
        """
        if self._client is None:
            self._client = httpx.Client(
                timeout=self._timeout,
                transport=self._transport,
            )
        return self._client

    def _request_headers(self, extra: dict[str, str]) -> dict[str, str]:
        """Compose the per-request header set: env-var → session → caller.

        Each layer overrides the prior on header-name collision:

        1. ``MP_CUSTOM_HEADER_NAME`` / ``MP_CUSTOM_HEADER_VALUE`` env pair.
        2. ``self._session.headers`` (populated from ``[settings].custom_header``
           and bridge ``headers`` per FR-014). The resolver merged env into
           the session earlier; the final session state is authoritative.
        3. ``extra`` — typically ``{"Authorization": auth_header}`` plus any
           per-call ``Accept-Encoding`` etc. supplied by the caller.

        Args:
            extra: Per-call headers (e.g., Authorization). May be empty.

        Returns:
            New dict with all layers merged in precedence order.
        """
        headers: dict[str, str] = {}
        custom_name = os.environ.get("MP_CUSTOM_HEADER_NAME")
        custom_value = os.environ.get("MP_CUSTOM_HEADER_VALUE")
        if custom_name and custom_value:
            headers[custom_name] = custom_value
        if self._session is not None:
            headers.update(self._session.headers)
        headers.update(extra)
        return headers

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> MixpanelAPIClient:
        """Enter context manager."""
        self._ensure_client()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager, closing client."""
        self.close()

    def _handle_response(
        self,
        response: httpx.Response,
        *,
        request_method: str | None = None,
        request_url: str | None = None,
        request_params: dict[str, Any] | None = None,
        request_body: dict[str, Any] | None = None,
        script: str | None = None,
    ) -> Any:
        """Handle API response, raising appropriate exceptions with full context.

        All exceptions include request/response context for debugging and
        autonomous recovery by AI agents.

        Status code handling:
            - 200-299: Parse and return JSON response
            - 400: QueryError with error message from response body
            - 401: AuthenticationError (invalid credentials)
            - 403: QueryError (permission denied)
            - 404: QueryError (resource not found)
            - 412: JQLSyntaxError (JQL script errors with parsed details)
            - 5xx: ServerError with status code and error details

        Note: 429 (rate limit) is handled separately in _request() with retry logic.

        Args:
            response: The HTTP response to handle.
            request_method: HTTP method used (GET, POST).
            request_url: Full request URL.
            request_params: Query parameters sent.
            request_body: Request body sent (for POST).
            script: Optional JQL script for error context (used for 412 errors).

        Returns:
            Parsed JSON response for successful requests.

        Raises:
            AuthenticationError: On 401 response.
            QueryError: On 400 response.
            JQLSyntaxError: On 412 response (JQL script errors).
            ServerError: On 5xx response.
        """
        # Parse response body for error details
        response_body: str | dict[str, Any] | None = None
        try:
            response_body = response.json()
        except json.JSONDecodeError:
            response_body = response.text[:500] if response.text else None

        if response.status_code == 401:
            raise AuthenticationError(
                "Invalid credentials. Check username, secret, and project_id.",
                status_code=response.status_code,
                response_body=response_body,
                request_method=request_method,
                request_url=request_url,
                request_params=request_params,
            )
        if response.status_code == 403:
            error_msg = "Permission denied"
            if isinstance(response_body, dict):
                error_msg = response_body.get("error", "Permission denied")
            elif isinstance(response_body, str):
                error_msg = response_body[:200] or "Permission denied"
            raise QueryError(
                error_msg,
                status_code=response.status_code,
                response_body=response_body,
                request_method=request_method,
                request_url=request_url,
                request_params=request_params,
                request_body=request_body,
            )
        if response.status_code == 400:
            error_msg = "Unknown error"
            if isinstance(response_body, dict):
                error_msg = response_body.get("error", "Unknown error")
            elif isinstance(response_body, str):
                error_msg = response_body[:200]
            raise QueryError(
                error_msg,
                status_code=response.status_code,
                response_body=response_body,
                request_method=request_method,
                request_url=request_url,
                request_params=request_params,
                request_body=request_body,
            )
        if response.status_code == 404:
            error_msg = "Resource not found"
            if isinstance(response_body, dict):
                error_msg = response_body.get("error", "Resource not found")
            elif isinstance(response_body, str):
                error_msg = response_body[:200] or "Resource not found"
            raise QueryError(
                error_msg,
                status_code=response.status_code,
                response_body=response_body,
                request_method=request_method,
                request_url=request_url,
                request_params=request_params,
                request_body=request_body,
            )
        if response.status_code == 412:
            # JQL script errors return 412 Precondition Failed
            if isinstance(response_body, dict):
                raw_error = response_body.get("error", "Unknown JQL error")
                request_path = response_body.get("request")
                raise JQLSyntaxError(
                    raw_error=raw_error,
                    script=script,
                    request_path=request_path,
                )
            else:
                raise QueryError(
                    f"JQL failed: {response_body[:200] if response_body else 'Unknown error'}",
                    status_code=response.status_code,
                    response_body=response_body,
                    request_method=request_method,
                    request_url=request_url,
                    request_body=request_body,
                )
        if response.status_code >= 500:
            # Extract error message from response body if available
            error_msg = f"Server error: {response.status_code}"
            if isinstance(response_body, dict) and "error" in response_body:
                error_msg = f"Server error: {response_body['error']}"
            elif isinstance(response_body, str) and response_body:
                error_msg = f"Server error: {response_body[:200]}"

            raise ServerError(
                error_msg,
                status_code=response.status_code,
                response_body=response_body,
                request_method=request_method,
                request_url=request_url,
                request_params=request_params,
                request_body=request_body,
            )
        response.raise_for_status()
        if response_body is not None and isinstance(response_body, dict | list):
            return response_body
        try:
            return response.json()
        except json.JSONDecodeError as e:
            raise MixpanelDataError(
                f"Non-JSON response from {request_method} {request_url} "
                f"(status {response.status_code}): {response.text[:500]}",
                code="INVALID_RESPONSE",
            ) from e

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter.

        Uses exponential backoff starting at 1 second, doubling each
        attempt up to a maximum of 60 seconds. Adds 0-10% random jitter
        to prevent thundering herd.

        Formula: min(1.0 * 2^attempt, 60.0) + random(0, delay * 0.1)

        Args:
            attempt: Zero-based attempt number (0, 1, 2, ...).

        Returns:
            Delay in seconds including jitter.
        """
        base = 1.0
        max_delay = 60.0
        delay: float = min(base * (2**attempt), max_delay)
        jitter: float = random.uniform(0, delay * 0.1)  # noqa: S311
        return delay + jitter

    def _execute_with_retry(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        form_data: dict[str, Any] | None = None,
        headers: dict[str, str],
        timeout: float | None = None,
        script: str | None = None,
    ) -> Any:
        """Execute HTTP request with retry logic for rate limiting.

        This is the core request execution method used by both _request() and
        request(). Handles rate limiting with exponential backoff and error
        response parsing.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: Full URL to request.
            params: Optional query parameters.
            json_data: Optional JSON request body.
            form_data: Optional form-encoded request body.
            headers: Request headers (must include Authorization).
            timeout: Optional request timeout in seconds.
            script: Optional JQL script for error context.

        Returns:
            Parsed JSON response.

        Raises:
            AuthenticationError: Invalid credentials (401).
            RateLimitError: Rate limit exceeded after max retries (429).
            QueryError: Invalid parameters (400).
            JQLSyntaxError: JQL script syntax/runtime error (412).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.
        """
        client = self._ensure_client()
        request_body = json_data or form_data
        if params is None:
            params = {}
        params["query_origin"] = "mixpanel-data-cli"
        request_headers = self._request_headers(headers)

        for attempt in range(self._max_retries + 1):
            try:
                response = client.request(
                    method,
                    url,
                    params=params,
                    json=json_data,
                    data=form_data,
                    headers=request_headers,
                    timeout=timeout or self._timeout,
                )

                if response.status_code == 429:
                    if attempt >= self._max_retries:
                        retry_after = self._parse_retry_after(response)
                        response_body: str | dict[str, Any] | None = None
                        try:
                            response_body = response.json()
                        except json.JSONDecodeError:
                            response_body = (
                                response.text[:500] if response.text else None
                            )
                        raise RateLimitError(
                            "Rate limit exceeded after max retries",
                            retry_after=retry_after,
                            status_code=response.status_code,
                            response_body=response_body,
                            request_method=method,
                            request_url=url,
                            request_params=params,
                        )
                    retry_after = self._parse_retry_after(response)
                    if retry_after is not None:
                        wait_time = float(retry_after)
                    else:
                        wait_time = self._calculate_backoff(attempt)
                    logger.warning(
                        "Rate limited, retrying in %.1f seconds (attempt %d/%d)",
                        wait_time,
                        attempt + 1,
                        self._max_retries,
                    )
                    time.sleep(wait_time)
                    continue

                return self._handle_response(
                    response,
                    request_method=method,
                    request_url=url,
                    request_params=params,
                    request_body=request_body,
                    script=script,
                )

            except httpx.HTTPError as e:
                raise MixpanelDataError(
                    f"HTTP error: {e}",
                    code="HTTP_ERROR",
                    details={
                        "error": str(e),
                        "request_method": method,
                        "request_url": url,
                        "request_params": params,
                    },
                ) from e

        # Should not reach here, but satisfy type checker
        raise RateLimitError(
            "Rate limit exceeded after max retries",
            request_method=method,
            request_url=url,
            request_params=params,
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        form_data: dict[str, Any] | None = None,
        timeout: float | None = None,
        script: str | None = None,
        inject_project_id: bool = True,
    ) -> Any:
        """Make an authenticated request with optional project_id injection.

        Used internally by API methods. Handles rate limiting with exponential
        backoff.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: Full URL to request.
            params: Query parameters.
            data: Request body as JSON (for POST).
            form_data: Request body as form-encoded (for POST).
            timeout: Override default timeout (uses self._timeout if not specified).
            script: Optional JQL script for error context.
            inject_project_id: If True (default), automatically adds project_id
                to query params. Set to False for APIs where project_id is
                already in the URL path (e.g., Lexicon Schemas API).

        Returns:
            Parsed JSON response.

        Raises:
            AuthenticationError: Invalid credentials (401).
            RateLimitError: Rate limit exceeded after max retries (429).
            QueryError: Invalid parameters (400).
            JQLSyntaxError: JQL script syntax/runtime error (412).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.
        """
        if params is None:
            params = {}
        if inject_project_id:
            params["project_id"] = self._session.project.id

        logger.debug(
            "_request - method: %s, url: %s, final params: %s",
            method,
            url,
            params,
        )

        return self._execute_with_retry(
            method,
            url,
            params=params,
            json_data=data,
            form_data=form_data,
            headers={"Authorization": self._get_auth_header()},
            timeout=timeout,
            script=script,
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Make an authenticated request to any Mixpanel API endpoint.

        This is the escape hatch for calling Mixpanel APIs not covered by the
        Workspace class. Authentication is handled automatically.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.).
            url: Full URL to request.
            params: Optional query parameters.
            json_body: Optional JSON request body.
            headers: Optional additional headers (Authorization is added automatically).
            timeout: Optional request timeout in seconds.

        Returns:
            Parsed JSON response.

        Raises:
            AuthenticationError: Invalid credentials (401).
            RateLimitError: Rate limit exceeded after max retries (429).
            QueryError: Invalid parameters (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            Get event schema from the Lexicon API::

                client = ws.api
                schema = client.request(
                    "GET",
                    f"https://mixpanel.com/api/app/projects/{client.project_id}/schemas/event/Purchase"
                )
        """
        request_headers = {"Authorization": self._get_auth_header()}
        if headers:
            request_headers.update(headers)

        return self._execute_with_retry(
            method,
            url,
            params=params,
            json_data=json_body,
            headers=request_headers,
            timeout=timeout,
        )

    @property
    def project_id(self) -> str:
        """Get the project ID from the bound Session.

        Useful when constructing URLs that require the project ID.

        Returns:
            The Mixpanel project ID.
        """
        return self._session.project.id

    @property
    def region(self) -> str:
        """Get the configured region from the bound Session.

        Useful when constructing regional URLs.

        Returns:
            The region code ('us', 'eu', or 'in').
        """
        return self._session.account.region

    # =========================================================================
    # 042 redesign: session-aware accessors and switching
    # =========================================================================

    @property
    def session(self) -> Session:
        """Return the resolved Session bound to this client.

        Returns:
            The Session passed to ``__init__(session=...)``.
        """
        return self._session

    @property
    def current_auth_header(self) -> str:
        """Return the current ``Authorization`` header value.

        The value is computed on every access — there is no caching at
        this level. Session-bound OAuth accounts re-resolve via the
        :class:`TokenResolver` (so a refreshed bearer surfaces here
        immediately); service accounts return ``Basic`` derived from
        the cached username/secret.

        Returns:
            The header value (``Basic ...`` or ``Bearer ...``) that
            every per-request header set carries.
        """
        return self._get_auth_header()

    @property
    def _http(self) -> httpx.Client:
        """Return the underlying ``httpx.Client``, lazily initializing it.

        Used by tests to verify that ``use()`` switches preserve the
        same HTTP transport / connection pool.
        """
        return self._ensure_client()

    def use(
        self,
        *,
        account: Account | None = None,
        project: Project | str | None = None,
        workspace: WorkspaceRef | int | None = None,
    ) -> None:
        """Swap one or more session axes in place, preserving the HTTP transport.

        Per Research R5:
        - ``use(workspace=W)`` is in-memory only (no cache invalidation).
        - ``use(project=P)`` clears the resolved-workspace cache.
        - ``use(account=A)`` rebuilds the auth header (atomic on success);
          clears the resolved-workspace cache.

        The underlying ``httpx.Client`` instance is preserved; only the
        ``_credentials`` shim and per-axis caches change.

        Args:
            account: Replacement account.
            project: Replacement project (``Project`` object or numeric-string
                project ID).
            workspace: Replacement workspace (``WorkspaceRef`` or positive int).

        Raises:
            RuntimeError: If the client was not constructed with ``session=``.
            OAuthError: If new account auth header construction fails (the
                previous header is preserved on failure).
        """
        project_obj: Project | None = (
            Project(id=project) if isinstance(project, str) else project
        )
        workspace_obj: WorkspaceRef | None = (
            WorkspaceRef(id=workspace) if isinstance(workspace, int) else workspace
        )
        new_session = self._session.replace(
            account=account, project=project_obj, workspace=workspace_obj
        )
        # Atomic-on-success: probe the new account's bearer BEFORE swapping
        # anything. ServiceAccount returns the cached Basic header; OAuth
        # variants delegate to TokenResolver — if no token is available the
        # resolver raises OAuthError and the prior session/header survive.
        new_cached_basic: str | None
        if isinstance(new_session.account, ServiceAccount):
            new_cached_basic = new_session.account.auth_header(
                token_resolver=self._token_resolver
            )
        else:
            # Probe OAuth resolver to surface missing-token errors here
            # rather than at the next request. The result isn't cached.
            new_session.account.auth_header(token_resolver=self._token_resolver)
            new_cached_basic = None
        self._session = new_session
        self._cached_basic_header = new_cached_basic
        if account is not None or project is not None:
            self._resolved_workspace = new_session.workspace
            self._cached_workspace_id = None
            # Sync the int-id pin with the new session — without this,
            # `maybe_scoped_path()` keeps emitting `/workspaces/<old>/…`
            # and routes requests to a workspace that may not exist under
            # the new project / account.
            self._workspace_id = (
                new_session.workspace.id if new_session.workspace else None
            )
        if workspace_obj is not None:
            self._workspace_id = workspace_obj.id
            self._resolved_workspace = workspace_obj

    def resolve_workspace(self) -> WorkspaceRef:
        """Return the workspace for the current session, lazy-resolving once.

        When ``Session.workspace`` is None, this calls the App API's
        ``/projects/{pid}/workspaces/public`` endpoint and picks the
        ``is_default=True`` workspace. The result is cached for the
        session's lifetime; subsequent calls return the cached value
        until ``use(account=...)`` or ``use(project=...)`` invalidates.

        The resolved id is also written to the int-id cache used by
        :meth:`resolve_workspace_id` so the two discovery paths share
        a single network call.

        Returns:
            A :class:`WorkspaceRef` for the current session's project.

        Raises:
            WorkspaceScopeError: If the project has no workspaces.
        """
        if self._resolved_workspace is not None:
            return self._resolved_workspace
        path = f"/projects/{self.project_id}/workspaces/public"
        payload = self.app_request("GET", path)
        items: list[dict[str, Any]]
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict) and isinstance(payload.get("results"), list):
            items = payload["results"]
        else:
            items = []
        if not items:
            raise WorkspaceScopeError(
                f"Project {self.project_id} has no accessible workspaces."
            )
        default = next((w for w in items if w.get("is_default")), items[0])
        ref = WorkspaceRef(
            id=int(default["id"]),
            name=default.get("name"),
            is_default=bool(default.get("is_default")),
        )
        self._resolved_workspace = ref
        self._cached_workspace_id = ref.id
        return ref

    def _parse_retry_after(self, response: httpx.Response) -> int | None:
        """Parse Retry-After header if present.

        Args:
            response: HTTP response.

        Returns:
            Seconds to wait, or None if header not present.
        """
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return int(retry_after)
            except ValueError:
                pass
        return None

    # =========================================================================
    # App API - OAuth/Bearer requests with workspace scoping
    # =========================================================================

    def app_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        form_body: dict[str, str] | None = None,
        _raw: bool = False,
    ) -> Any:
        """Make an authenticated request to the Mixpanel App API.

        Uses Bearer auth (OAuth) or Basic auth depending on credentials.
        Builds the URL from the ``app`` endpoint for the configured region.
        Unwraps the ``results`` field from the response JSON when present.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE, etc.).
            path: API path (e.g., ``/projects/12345/dashboards``).
            params: Optional query parameters.
            json_body: Optional JSON request body. Mutually exclusive with
                ``form_body``.
            form_body: Optional ``application/x-www-form-urlencoded`` request
                body. Used by endpoints like ``custom_events/`` and
                ``data-definitions/lookup-tables/`` that don't accept JSON.
                Mutually exclusive with ``json_body``.
            _raw: If True, return the full response dict without unwrapping
                the ``results`` field. Useful for endpoints that include
                pagination metadata alongside results.

        Returns:
            The ``results`` field from the response JSON if present,
            otherwise the full response body. For 204 No Content responses,
            returns ``{"status": "ok"}``. When ``_raw`` is True, the full
            response dict is returned without unwrapping ``results``.

        Raises:
            ValueError: Both ``json_body`` and ``form_body`` were provided.
            AuthenticationError: Invalid credentials (401).
            RateLimitError: Rate limit exceeded after max retries (429).
            QueryError: Invalid parameters or resource not found (400, 404, 422).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            client = MixpanelAPIClient(session=session)
            with client:
                dashboards = client.app_request(
                    "GET", "/projects/12345/dashboards"
                )
                # form-encoded POST
                ce = client.app_request(
                    "POST",
                    "/projects/12345/custom_events/",
                    form_body={"name": "X", "alternatives": '[{"event": "Y"}]'},
                )
            ```
        """
        if json_body is not None and form_body is not None:
            raise ValueError(
                "app_request: json_body and form_body are mutually exclusive"
            )

        url = self._build_url("app", path)
        # Re-resolve per request via _get_auth_header() so refreshed
        # OAuth tokens (browser refresh / static-token rotation) reach
        # App API calls without rebuilding the client. Service-account
        # Basic Auth has no analogous freshness concern; the helper
        # falls through to the cached credentials in that case.
        auth_header = self._get_auth_header()
        headers = self._request_headers({"Authorization": auth_header})

        client = self._ensure_client()

        # Pass through caller-supplied params only (no query_origin —
        # some App API endpoints reject unknown query parameters).
        request_params: dict[str, str] = {}
        if params:
            request_params.update(params)

        request_body: dict[str, Any] | dict[str, str] | None = (
            form_body if form_body is not None else json_body
        )

        for attempt in range(self._max_retries + 1):
            try:
                if form_body is not None:
                    response = client.request(
                        method,
                        url,
                        params=request_params,
                        data=form_body,
                        headers=headers,
                        timeout=self._timeout,
                    )
                else:
                    response = client.request(
                        method,
                        url,
                        params=request_params,
                        json=json_body,
                        headers=headers,
                        timeout=self._timeout,
                    )

                # Handle 204 No Content
                if response.status_code == 204:
                    return {"status": "ok"}

                # Handle 429 rate limiting with retry
                if response.status_code == 429:
                    if attempt >= self._max_retries:
                        retry_after = self._parse_retry_after(response)
                        response_body: str | dict[str, Any] | None = None
                        try:
                            response_body = response.json()
                        except json.JSONDecodeError:
                            response_body = (
                                response.text[:500] if response.text else None
                            )
                        raise RateLimitError(
                            "Rate limit exceeded after max retries",
                            retry_after=retry_after,
                            status_code=response.status_code,
                            response_body=response_body,
                            request_method=method,
                            request_url=url,
                        )
                    retry_after = self._parse_retry_after(response)
                    if retry_after is not None:
                        wait_time = float(retry_after)
                    else:
                        wait_time = self._calculate_backoff(attempt)
                    logger.warning(
                        "Rate limited, retrying in %.1f seconds (attempt %d/%d)",
                        wait_time,
                        attempt + 1,
                        self._max_retries,
                    )
                    time.sleep(wait_time)
                    continue

                # Handle 422 as QueryError
                if response.status_code == 422:
                    err_body: str | dict[str, Any] | None = None
                    try:
                        err_body = response.json()
                    except json.JSONDecodeError:
                        err_body = response.text[:500] if response.text else None
                    error_msg = "Unprocessable entity"
                    if isinstance(err_body, dict):
                        error_msg = str(err_body.get("error", error_msg))
                    raise QueryError(
                        error_msg,
                        status_code=422,
                        response_body=err_body,
                        request_method=method,
                        request_url=url,
                        request_body=request_body,
                    )

                # Delegate other error codes to _handle_response
                result = self._handle_response(
                    response,
                    request_method=method,
                    request_url=url,
                    request_params=request_params,
                    request_body=request_body,
                )

                # Unwrap results field if present (unless _raw requested)
                if not _raw and isinstance(result, dict) and "results" in result:
                    return result["results"]
                return result

            except httpx.HTTPError as e:
                raise MixpanelDataError(
                    f"HTTP error: {e}",
                    code="HTTP_ERROR",
                    details={
                        "error": str(e),
                        "request_method": method,
                        "request_url": url,
                    },
                ) from e

        # Should not reach here, but satisfy type checker
        raise RateLimitError(
            "Rate limit exceeded after max retries",
            request_method=method,
            request_url=url,
        )

    @property
    def workspace_id(self) -> int | None:
        """Return the explicit workspace ID, if set.

        Returns:
            The workspace ID set via ``set_workspace_id()``, or None.
        """
        return self._workspace_id

    def set_workspace_id(self, workspace_id: int | None) -> None:
        """Set or clear the explicit workspace ID for scoped requests.

        When set, ``maybe_scoped_path()`` will use workspace-scoped paths.
        Setting to ``None`` clears both the explicit ID and the cached
        auto-discovered ID, reverting to project-scoped paths.

        Args:
            workspace_id: Workspace ID to use, or None to clear.

        Example:
            ```python
            client.set_workspace_id(789)
            path = client.maybe_scoped_path("dashboards")
            # "/workspaces/789/dashboards"

            client.set_workspace_id(None)
            path = client.maybe_scoped_path("dashboards")
            # "/projects/12345/dashboards"
            ```
        """
        self._workspace_id = workspace_id
        if workspace_id is None:
            self._cached_workspace_id = None

    def resolve_workspace_id(self) -> int:
        """Resolve the workspace ID to use for scoped requests.

        Resolution order:
        1. Explicit workspace ID (set via ``set_workspace_id()``)
        2. Cached auto-discovered workspace ID
        3. Auto-discover by calling ``list_workspaces()`` and finding
           the default workspace (``is_default=True``), falling back
           to the first workspace.

        Returns:
            The resolved workspace ID.

        Raises:
            WorkspaceScopeError: If no workspaces are found for the project.

        Example:
            ```python
            client.set_workspace_id(42)
            assert client.resolve_workspace_id() == 42

            # Or auto-discover:
            ws_id = client.resolve_workspace_id()
            ```
        """
        if self._workspace_id is not None:
            return self._workspace_id

        if self._cached_workspace_id is not None:
            return self._cached_workspace_id

        workspaces = self.list_workspaces()
        if not workspaces:
            raise WorkspaceScopeError(
                "No workspaces found for project "
                f"'{self._session.project.id}'. "
                "Ensure you have access to at least one workspace.",
                code="NO_WORKSPACES",
                details={"project_id": self._session.project.id},
            )

        # Prefer the default workspace
        for ws in workspaces:
            if ws.is_default:
                self._cached_workspace_id = ws.id
                return ws.id

        # Fall back to first workspace
        self._cached_workspace_id = workspaces[0].id
        return workspaces[0].id

    def maybe_scoped_path(self, domain_path: str) -> str:
        """Build an optionally workspace-scoped API path.

        If a workspace ID is set (via ``set_workspace_id()``), returns a
        workspace-scoped path. Otherwise returns a project-scoped path.

        Args:
            domain_path: Domain-relative path (e.g., ``"dashboards"``).

        Returns:
            Workspace-scoped path ``/workspaces/{wid}/{domain_path}`` if
            workspace is set, otherwise ``/projects/{pid}/{domain_path}``.

        Example:
            ```python
            # No workspace set:
            client.maybe_scoped_path("dashboards")
            # "/projects/12345/dashboards"

            # With workspace:
            client.set_workspace_id(789)
            client.maybe_scoped_path("dashboards")
            # "/workspaces/789/dashboards"
            ```
        """
        if self._workspace_id is not None:
            return f"/workspaces/{self._workspace_id}/{domain_path}"
        return f"/projects/{self._session.project.id}/{domain_path}"

    def require_scoped_path(self, domain_path: str) -> str:
        """Build a workspace-scoped API path, auto-discovering if needed.

        Always returns a path scoped to both project and workspace. If no
        workspace ID is set, auto-discovers one via ``resolve_workspace_id()``.

        Args:
            domain_path: Domain-relative path (e.g., ``"feature-flags"``).

        Returns:
            Path in format ``/projects/{pid}/workspaces/{wid}/{domain_path}``.

        Raises:
            WorkspaceScopeError: If no workspaces are found for the project.

        Example:
            ```python
            client.set_workspace_id(789)
            client.require_scoped_path("feature-flags")
            # "/projects/12345/workspaces/789/feature-flags"

            # Auto-discovers workspace if not set:
            client.require_scoped_path("experiments")
            # "/projects/12345/workspaces/100/experiments"
            ```
        """
        ws_id = self.resolve_workspace_id()
        pid = self._session.project.id
        return f"/projects/{pid}/workspaces/{ws_id}/{domain_path}"

    def with_project(
        self,
        project_id: str,
        workspace_id: int | None = None,
    ) -> MixpanelAPIClient:
        """Create a new client for a different project, sharing HTTP transport.

        Builds a new :class:`Session` (via :meth:`Session.replace`) with the
        given ``project_id`` but keeps the same authentication (account) and
        region. The underlying transport is shared via the ``_transport``
        kwarg so no extra TCP connections are created; a fresh
        ``httpx.Client`` wrapping that transport is constructed lazily on
        first request. (For in-session axis swaps that preserve the existing
        ``httpx.Client`` instance itself, use :meth:`Workspace.use` instead.)

        Args:
            project_id: The project ID to target.
            workspace_id: Optional workspace ID within the new project.

        Returns:
            A new ``MixpanelAPIClient`` bound to ``project_id``.

        Example:
            ```python
            original = MixpanelAPIClient(session=session)
            other = original.with_project("9999999", workspace_id=42)
            other.me()  # still uses the same auth
            ```
        """
        new_session = self._session.replace(
            project=Project(id=project_id),
            workspace=WorkspaceRef(id=workspace_id) if workspace_id else None,
        )
        # Share the existing HTTP transport when available
        transport: httpx.BaseTransport | None = self._transport
        new_client = MixpanelAPIClient(
            session=new_session,
            timeout=self._timeout,
            export_timeout=self._export_timeout,
            max_retries=self._max_retries,
            token_resolver=self._token_resolver,
            _transport=transport,
        )
        if workspace_id is not None:
            new_client.set_workspace_id(workspace_id)
        return new_client

    def me(self) -> dict[str, Any]:
        """Call GET /api/app/me to retrieve the authenticated user's profile.

        The ``/me`` endpoint is NOT project-scoped — it returns information
        about the authenticated user, including all accessible organizations,
        projects, and workspaces.

        Returns:
            Raw JSON response dict from ``/api/app/me``.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Permission denied or API error (403, 400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(session=session) as client:
                me_data = client.me()
                print(me_data.get("user_email"))
            ```
        """
        result = self.app_request("GET", "/me")
        if not isinstance(result, dict):
            return {"results": result}
        return result

    def list_workspaces(self) -> list[PublicWorkspace]:
        """List all public workspaces for the current project.

        Calls ``GET /api/app/projects/{pid}/workspaces/public``.

        Returns:
            List of PublicWorkspace models for the project.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400, 404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                workspaces = client.list_workspaces()
                for ws in workspaces:
                    print(f"{ws.name} (id={ws.id}, default={ws.is_default})")
            ```
        """
        pid = self._session.project.id
        path = f"/projects/{pid}/workspaces/public"
        results = self.app_request("GET", path)

        if not isinstance(results, list):
            raise MixpanelDataError(
                f"Unexpected response format from list_workspaces: "
                f"expected list, got {type(results).__name__}",
            )
        return [PublicWorkspace.model_validate(ws) for ws in results]

    # =========================================================================
    # Export API - Streaming
    # =========================================================================

    def export_events(
        self,
        from_date: str,
        to_date: str,
        *,
        events: list[str] | None = None,
        where: str | None = None,
        limit: int | None = None,
        on_batch: Callable[[int], None] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Stream events from the Export API.

        Streams events line by line from Mixpanel's JSONL export endpoint.
        Memory-efficient for large exports since events are yielded one at a time.

        Args:
            from_date: Start date (YYYY-MM-DD, inclusive).
            to_date: End date (YYYY-MM-DD, inclusive).
            events: Optional list of event names to filter.
            where: Optional filter expression.
            limit: Optional maximum number of events to return (max 100000).
            on_batch: Optional callback invoked with cumulative count every
                1000 events, and once at the end for any remaining events.

        Yields:
            Event dictionaries with 'event' and 'properties' keys.
            Malformed JSON lines are logged and skipped (not raised).

        Raises:
            AuthenticationError: Invalid credentials.
            RateLimitError: Rate limit exceeded after max retries.
            QueryError: Invalid parameters.
            ServerError: Server-side errors (5xx).
        """
        url = self._build_url("export", "/export")

        params: dict[str, Any] = {
            "project_id": self._session.project.id,
            "from_date": from_date,
            "to_date": to_date,
        }
        if events:
            params["event"] = json.dumps(events)
        if where:
            params["where"] = where
        if limit is not None:
            params["limit"] = limit

        client = self._ensure_client()
        headers = self._request_headers(
            {
                "Authorization": self._get_auth_header(),
                "Accept-Encoding": "gzip",
            }
        )

        # Stream with retry logic
        for attempt in range(self._max_retries + 1):
            batch_count = 0  # Reset on each attempt
            try:
                with client.stream(
                    "GET",
                    url,
                    params=params,
                    headers=headers,
                    timeout=self._export_timeout,
                ) as response:
                    if response.status_code == 429:
                        if attempt >= self._max_retries:
                            retry_after = self._parse_retry_after(response)
                            raise RateLimitError(
                                "Rate limit exceeded after max retries",
                                retry_after=retry_after,
                                status_code=response.status_code,
                                request_method="GET",
                                request_url=url,
                                request_params=params,
                            )
                        retry_after = self._parse_retry_after(response)
                        if retry_after is not None:
                            wait_time = float(retry_after)
                        else:
                            wait_time = self._calculate_backoff(attempt)
                        time.sleep(wait_time)
                        continue

                    if response.status_code == 401:
                        raise AuthenticationError(
                            "Invalid credentials. Check username, secret, and project_id.",
                            status_code=response.status_code,
                            request_method="GET",
                            request_url=url,
                            request_params=params,
                        )
                    if response.status_code == 400:
                        # Need to read body for error
                        body = response.read()
                        response_body: str | dict[str, Any] | None = None
                        error_msg = "Unknown error"
                        try:
                            response_body = json.loads(body)
                            if isinstance(response_body, dict):
                                error_msg = response_body.get("error", "Unknown error")
                        except json.JSONDecodeError:
                            response_body = body.decode()[:500] if body else None
                            error_msg = body.decode()[:200] if body else "Unknown error"
                        raise QueryError(
                            error_msg,
                            status_code=response.status_code,
                            response_body=response_body,
                            request_method="GET",
                            request_url=url,
                            request_params=params,
                        )

                    response.raise_for_status()

                    # Use buffered JSONL reader instead of iter_lines().
                    # httpx iter_lines() can incorrectly split lines at gzip
                    # decompression chunk boundaries, causing JSON parse errors.
                    # See: _iter_jsonl_lines docstring for implementation details.
                    for line in _iter_jsonl_lines(response):
                        try:
                            event = json.loads(line)
                            yield event
                            batch_count += 1
                            if on_batch and batch_count % 1000 == 0:
                                on_batch(batch_count)
                        except json.JSONDecodeError:
                            logger.warning("Skipping malformed line: %s", line[:100])

                    # Call on_batch with final count if there was a partial batch
                    if on_batch and batch_count % 1000 != 0:
                        on_batch(batch_count)
                    return  # Success, exit retry loop

            except httpx.HTTPError as e:
                # Network/connection errors - retry if attempts remain
                if attempt >= self._max_retries:
                    raise MixpanelDataError(
                        f"HTTP error during export: {e}",
                        code="HTTP_ERROR",
                        details={"error": str(e)},
                    ) from e
                time.sleep(self._calculate_backoff(attempt))

    def export_profiles(
        self,
        *,
        where: str | None = None,
        cohort_id: str | None = None,
        output_properties: list[str] | None = None,
        on_batch: Callable[[int], None] | None = None,
        distinct_id: str | None = None,
        distinct_ids: list[str] | None = None,
        group_id: str | None = None,
        behaviors: list[dict[str, Any]] | None = None,
        as_of_timestamp: int | None = None,
        include_all_users: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """Stream profiles from the Engage API.

        Paginates through all user profiles using Mixpanel's session-based
        pagination. Each page is a separate API request.

        Args:
            where: Optional filter expression.
            cohort_id: Optional cohort ID to filter by. Only profiles that are
                members of this cohort will be returned.
            output_properties: Optional list of property names to include in
                the response. If None, all properties are returned.
            on_batch: Optional callback invoked with cumulative count after
                each page is processed.
            distinct_id: Optional single user ID to fetch. Mutually exclusive
                with distinct_ids.
            distinct_ids: Optional list of user IDs to fetch. Mutually exclusive
                with distinct_id. Duplicates are automatically removed.
            group_id: Optional group type identifier (e.g., "companies") to fetch
                group profiles instead of user profiles.
            behaviors: Optional list of behavioral filters. Each dict should have
                'window' (e.g., "30d"), 'name' (identifier), and 'event_selectors'
                (list of {"event": "Name"}). Use with `where` parameter to filter,
                e.g., where='(behaviors["name"] > 0)'. Mutually exclusive with
                cohort_id.
            as_of_timestamp: Optional Unix timestamp to query profile state at
                a specific point in time. Must be in the past.
            include_all_users: If True, include all users and mark cohort membership.
                Only valid when cohort_id is provided.

        Yields:
            Profile dictionaries with '$distinct_id' and '$properties' keys.

        Raises:
            ValueError: If mutually exclusive parameters are provided together,
                or if include_all_users is used without cohort_id.
            AuthenticationError: Invalid credentials.
            RateLimitError: Rate limit exceeded after max retries.
            ServerError: Server-side errors (5xx).
        """
        # Validate mutually exclusive parameters
        if distinct_id is not None and distinct_ids is not None:
            raise ValueError(
                "distinct_id and distinct_ids are mutually exclusive. "
                "Provide only one to fetch specific profiles."
            )

        if behaviors is not None and cohort_id is not None:
            raise ValueError(
                "behaviors and cohort_id are mutually exclusive. "
                "Use behaviors for behavioral filtering or cohort_id for cohort membership."
            )

        if include_all_users and cohort_id is None:
            raise ValueError(
                "include_all_users requires cohort_id. "
                "This parameter is only valid for cohort membership queries."
            )

        # Validate behaviors type
        if behaviors is not None and not isinstance(behaviors, list):
            raise ValueError(
                "behaviors must be a list of behavioral filter dictionaries."
            )

        # Validate as_of_timestamp is not in the future
        if as_of_timestamp is not None:
            current_time = int(time.time())
            if as_of_timestamp > current_time:
                raise ValueError(
                    "as_of_timestamp cannot be in the future. "
                    "Provide a Unix timestamp in the past to query historical profile state."
                )

        # Handle empty distinct_ids list - return early without API call
        if distinct_ids is not None and len(distinct_ids) == 0:
            return

        # Deduplicate distinct_ids if provided
        if distinct_ids is not None:
            distinct_ids = list(dict.fromkeys(distinct_ids))  # Preserves order

        url = self._build_url("engage", "")

        session_id: str | None = None
        page = 0
        total_count = 0

        while True:
            params: dict[str, Any] = {
                "project_id": self._session.project.id,
                "page": page,
            }
            if session_id:
                params["session_id"] = session_id
            if where:
                params["where"] = where
            if cohort_id:
                params["filter_by_cohort"] = json.dumps({"id": cohort_id})
            if output_properties:
                params["output_properties"] = json.dumps(output_properties)
            if distinct_id:
                params["distinct_id"] = distinct_id
            if distinct_ids:
                params["distinct_ids"] = json.dumps(distinct_ids)
            if group_id:
                params["data_group_id"] = group_id
            if behaviors:
                params["behaviors"] = json.dumps(behaviors)
            if as_of_timestamp is not None:
                params["as_of_timestamp"] = as_of_timestamp
            # Only send include_all_users when cohort_id is set (it's meaningless otherwise)
            # Must send explicitly because API defaults to True
            if cohort_id:
                params["include_all_users"] = include_all_users

            response = self._request("POST", url, data=params)

            results = response.get("results", [])
            if not results:
                break

            for profile in results:
                yield profile
                total_count += 1

            if on_batch:
                on_batch(total_count)

            session_id = response.get("session_id")
            if not session_id:
                break
            page += 1

    def export_profiles_page(
        self,
        page: int,
        session_id: str | None = None,
        *,
        where: str | None = None,
        cohort_id: str | None = None,
        output_properties: list[str] | None = None,
        group_id: str | None = None,
        behaviors: list[dict[str, Any]] | None = None,
        as_of_timestamp: int | None = None,
        include_all_users: bool = False,
        sort_key: str | None = None,
        sort_order: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        filter_by_cohort: str | None = None,
        distinct_id: str | None = None,
        distinct_ids: list[str] | None = None,
    ) -> ProfilePageResult:
        """Fetch a single page of profiles from the Engage API.

        This method fetches exactly one page from the Engage API, enabling
        parallel fetching of multiple pages. For sequential fetching of
        all profiles, use export_profiles() instead.

        Args:
            page: Zero-based page index to fetch.
            session_id: Session ID from previous page (None for first page).
            where: Filter expression (e.g., 'properties["plan"] == "premium"').
            cohort_id: Filter to specific cohort by ID. Ignored when
                filter_by_cohort is also provided.
            output_properties: Properties to include (None for all).
            group_id: Group analytics group identifier.
            behaviors: Behavioral filter definitions.
            as_of_timestamp: Unix timestamp for point-in-time query.
            include_all_users: Include non-members in cohort results.
                Sent when either cohort_id or filter_by_cohort is set.
            sort_key: Sort expression in selector format (e.g.,
                'properties["$last_seen"]' or 'properties["revenue"]').
            sort_order: Sort direction — "ascending" or "descending".
            search: Full-text search string applied to profile properties.
            limit: Server-side result cap per page.
            filter_by_cohort: Pre-encoded JSON cohort filter string.
                Supports both ``{"id": N}`` and ``{"raw_cohort": {...}}``
                formats. Takes precedence over cohort_id when both are set.
            distinct_id: Optional single user ID to fetch. Mutually exclusive
                with distinct_ids.
            distinct_ids: Optional list of user IDs to fetch. Mutually
                exclusive with distinct_id.

        Returns:
            ProfilePageResult with profiles, session_id, page, and has_more.

        Raises:
            AuthenticationError: Invalid credentials.
            RateLimitError: API rate limit exceeded.
            APIError: Other API errors.

        Example:
            ```python
            # Fetch first page
            result = client.export_profiles_page(page=0)

            # Continue fetching if more pages
            while result.has_more:
                result = client.export_profiles_page(
                    page=result.page + 1,
                    session_id=result.session_id,
                )

            # Sorted, filtered query
            result = client.export_profiles_page(
                page=0,
                sort_key='properties["$last_seen"]',
                sort_order="descending",
                search="alice",
                limit=50,
            )
            ```
        """
        url = self._build_url("engage", "")

        params: dict[str, Any] = {
            "project_id": self._session.project.id,
            "page": page,
        }
        if session_id:
            params["session_id"] = session_id
        if where:
            params["where"] = where
        # filter_by_cohort takes precedence over cohort_id
        if filter_by_cohort:
            params["filter_by_cohort"] = filter_by_cohort
        elif cohort_id:
            params["filter_by_cohort"] = json.dumps({"id": cohort_id})
        if output_properties:
            params["output_properties"] = json.dumps(output_properties)
        if group_id:
            params["data_group_id"] = group_id
        if behaviors:
            params["behaviors"] = json.dumps(behaviors)
        if as_of_timestamp is not None:
            params["as_of_timestamp"] = as_of_timestamp
        # Send include_all_users when cohort_id or filter_by_cohort is set
        # Must send explicitly because API defaults to True
        if cohort_id or filter_by_cohort:
            params["include_all_users"] = include_all_users
        if sort_key:
            params["sort_key"] = sort_key
        if sort_order:
            params["sort_order"] = sort_order
        if search:
            params["search"] = search
        if limit is not None:
            params["limit"] = limit
        if distinct_id:
            params["distinct_id"] = distinct_id
        if distinct_ids:
            params["distinct_ids"] = json.dumps(distinct_ids)

        response = self._request("POST", url, data=params)

        profiles = response.get("results", [])
        returned_session_id = response.get("session_id")
        has_more = returned_session_id is not None

        # Extract pagination metadata for pre-computed page approach
        total = response.get("total", 0)
        page_size = response.get("page_size", 1000)

        return ProfilePageResult(
            profiles=profiles,
            session_id=returned_session_id,
            page=page,
            has_more=has_more,
            total=total,
            page_size=page_size,
        )

    def engage_stats(
        self,
        *,
        where: str | None = None,
        action: str = "count()",
        filter_by_cohort: str | None = None,
        segment_by_cohorts: dict[str, bool] | None = None,
        group_id: str | None = None,
        as_of_timestamp: int | None = None,
        include_all_users: bool = False,
    ) -> dict[str, Any]:
        """Fetch aggregate statistics from the Engage API.

        POSTs to ``/api/2.0/engage/stats`` to retrieve aggregate metrics
        over the user/group population.

        Args:
            where: Filter expression (e.g., 'properties["plan"] == "premium"').
            action: Aggregation expression. Defaults to ``"count()"``.
                Supported: ``'extremes(properties["name"])'``,
                ``'percentile(properties["name"], N)'``,
                ``'numeric_summary(properties["name"])'``.
            filter_by_cohort: Pre-encoded JSON cohort filter string.
                Supports both ``{"id": N}`` and ``{"raw_cohort": {...}}``
                formats.
            segment_by_cohorts: Mapping of cohort ID to boolean indicating
                whether to include or exclude the cohort in segmentation.
                Serialized as JSON in the request.
            group_id: Group analytics group identifier.
            as_of_timestamp: Unix timestamp for point-in-time query.
            include_all_users: Include non-members in cohort results.

        Returns:
            Raw response dict from the Engage API containing aggregate results.

        Raises:
            AuthenticationError: Invalid credentials.
            RateLimitError: API rate limit exceeded.
            APIError: Other API errors.

        Example:
            ```python
            # Count all profiles
            stats = client.engage_stats()

            # Revenue extremes for premium users
            stats = client.engage_stats(
                where='properties["plan"] == "premium"',
                action='extremes(properties["revenue"])',
            )

            # Count profiles in a cohort
            stats = client.engage_stats(
                filter_by_cohort='{"id": 42}',
                include_all_users=False,
            )
            ```
        """
        url = self._build_url("engage", "stats")

        params: dict[str, Any] = {
            "project_id": self._session.project.id,
            "action": action,
        }
        if where:
            # Stats endpoint accepts "selector", not "where"
            params["selector"] = where
        if filter_by_cohort:
            params["filter_by_cohort"] = filter_by_cohort
        if segment_by_cohorts is not None:
            params["segment_by_cohorts"] = json.dumps(segment_by_cohorts)
        if group_id:
            params["data_group_id"] = group_id
        if as_of_timestamp is not None:
            params["as_of_timestamp"] = as_of_timestamp
        if filter_by_cohort:
            # Must send explicitly because API defaults to True
            params["include_all_users"] = include_all_users

        response = self._request("POST", url, data=params)
        if not isinstance(response, dict):
            raise QueryError(
                message=(
                    f"engage_stats returned unexpected response type "
                    f"{type(response).__name__}: {response!r}"
                ),
                status_code=200,
                response_body=str(response),
            )
        return response

    # =========================================================================
    # Discovery API
    # =========================================================================

    def get_events(self) -> list[str]:
        """List all event names in the project.

        Returns:
            List of event name strings.

        Raises:
            AuthenticationError: Invalid credentials.
        """
        url = self._build_url("query", "/events/names")
        response = self._request("GET", url, params={"type": "general"})
        # Response is a list of event names
        if isinstance(response, list):
            return [str(e) for e in response]
        return []

    def get_event_properties(self, event: str) -> list[str]:
        """List properties for a specific event.

        Args:
            event: Event name.

        Returns:
            List of property name strings.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid event name.
        """
        url = self._build_url("query", "/events/properties/top")
        response = self._request("GET", url, params={"event": event})
        # Response is a dict with property names as keys and counts as values
        if isinstance(response, dict):
            return list(response.keys())
        return []

    def get_property_values(
        self,
        property_name: str,
        *,
        event: str | None = None,
        limit: int = 255,
    ) -> list[str]:
        """List sample values for a property.

        Args:
            property_name: Property name.
            event: Optional event name to scope the property.
            limit: Maximum number of values to return.

        Returns:
            List of property value strings.

        Raises:
            AuthenticationError: Invalid credentials.
        """
        url = self._build_url("query", "/events/properties/values")
        params: dict[str, Any] = {
            "name": property_name,
            "limit": limit,
        }
        if event:
            params["event"] = event
        response = self._request("GET", url, params=params)
        if isinstance(response, list):
            return [str(v) for v in response]
        return []

    def list_funnels(self) -> list[dict[str, Any]]:
        """List all saved funnels in the project.

        Returns:
            List of funnel dictionaries with keys: funnel_id (int), name (str).

        Raises:
            AuthenticationError: Invalid credentials.
            RateLimitError: Rate limit exceeded after retries.
        """
        url = self._build_url("query", "/funnels/list")
        response = self._request("GET", url)
        if isinstance(response, list):
            return response
        return []

    def list_cohorts(self) -> list[dict[str, Any]]:
        """List all saved cohorts in the project.

        Returns:
            List of cohort dictionaries with keys:
            id (int), name (str), count (int), description (str),
            created (str), is_visible (int), project_id (int).

        Raises:
            AuthenticationError: Invalid credentials.
            RateLimitError: Rate limit exceeded after retries.
        """
        # Note: POST method is unusual for read-only, but per API spec
        url = self._build_url("query", "/cohorts/list")
        response = self._request("POST", url)
        if isinstance(response, list):
            return response
        return []

    def get_top_events(
        self,
        *,
        type: str = "general",
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Get today's top events with counts and trends.

        Args:
            type: Counting method - "general", "unique", or "average".
            limit: Maximum events to return (default: 100).

        Returns:
            Dictionary with keys:
            - events: list of {amount: int, event: str, percent_change: float}
            - type: str

        Raises:
            AuthenticationError: Invalid credentials.
            RateLimitError: Rate limit exceeded after retries.
        """
        url = self._build_url("query", "/events/top")
        params: dict[str, Any] = {"type": type}
        if limit is not None:
            params["limit"] = limit
        response = self._request("GET", url, params=params)
        if isinstance(response, dict):
            return response
        return {"events": [], "type": type}

    def event_counts(
        self,
        events: list[str],
        from_date: str,
        to_date: str,
        *,
        type: str = "general",
        unit: str = "day",
    ) -> dict[str, Any]:
        """Get aggregate counts for multiple events over time.

        Args:
            events: List of event names to query.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            type: Counting method - "general", "unique", or "average".
            unit: Time unit - "day", "week", or "month".

        Returns:
            Dictionary with keys:
            - data.series: list of date strings
            - data.values: {event_name: {date: count}}
            - legend_size: int

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters.
            RateLimitError: Rate limit exceeded after retries.
        """
        url = self._build_url("query", "/events")
        params: dict[str, Any] = {
            "event": json.dumps(events),
            "type": type,
            "unit": unit,
            "from_date": from_date,
            "to_date": to_date,
        }
        result: dict[str, Any] = self._request("GET", url, params=params)
        return result

    def property_counts(
        self,
        event: str,
        property_name: str,
        from_date: str,
        to_date: str,
        *,
        type: str = "general",
        unit: str = "day",
        values: list[str] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Get aggregate counts by property values over time.

        Args:
            event: Event name to query.
            property_name: Property to segment by.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            type: Counting method - "general", "unique", or "average".
            unit: Time unit - "day", "week", or "month".
            values: Optional list of specific property values to include.
            limit: Maximum property values to return (default: 255).

        Returns:
            Dictionary with keys:
            - data.series: list of date strings
            - data.values: {property_value: {date: count}}
            - legend_size: int

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters.
            RateLimitError: Rate limit exceeded after retries.
        """
        url = self._build_url("query", "/events/properties")
        params: dict[str, Any] = {
            "event": event,
            "name": property_name,
            "type": type,
            "unit": unit,
            "from_date": from_date,
            "to_date": to_date,
        }
        if values is not None:
            params["values"] = json.dumps(values)
        if limit is not None:
            params["limit"] = limit
        result: dict[str, Any] = self._request("GET", url, params=params)
        return result

    # =========================================================================
    # Query API - Raw Responses
    # =========================================================================

    def segmentation(
        self,
        event: str,
        from_date: str,
        to_date: str,
        *,
        on: str | None = None,
        unit: str = "day",
        type: str = "general",
        where: str | None = None,
    ) -> dict[str, Any]:
        """Run a segmentation query.

        Args:
            event: Event name to segment.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            on: Optional property to segment by.
            unit: Time unit (minute, hour, day, week, month).
            type: Aggregation type (general, unique, average).
            where: Optional filter expression.

        Returns:
            Raw API response dictionary.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid query parameters.
            RateLimitError: Rate limit exceeded.
        """
        url = self._build_url("query", "/segmentation")
        params: dict[str, Any] = {
            "event": event,
            "from_date": from_date,
            "to_date": to_date,
            "unit": unit,
            "type": type,
        }
        if on:
            params["on"] = on
        if where:
            params["where"] = where
        result: dict[str, Any] = self._request("GET", url, params=params)
        return result

    def funnel(
        self,
        funnel_id: int,
        from_date: str,
        to_date: str,
        *,
        unit: str | None = None,
        on: str | None = None,
        where: str | None = None,
        length: int | None = None,
        length_unit: str | None = None,
    ) -> dict[str, Any]:
        """Run a funnel analysis query.

        Args:
            funnel_id: Funnel identifier.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            unit: Time unit for grouping.
            on: Optional property to segment by.
            where: Optional filter expression.
            length: Conversion window length.
            length_unit: Conversion window unit.

        Returns:
            Raw API response dictionary.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid funnel ID or parameters.
            RateLimitError: Rate limit exceeded.
        """
        url = self._build_url("query", "/funnels")
        params: dict[str, Any] = {
            "funnel_id": funnel_id,
            "from_date": from_date,
            "to_date": to_date,
        }
        if unit:
            params["unit"] = unit
        if on:
            params["on"] = on
        if where:
            params["where"] = where
        if length is not None:
            params["length"] = length
        if length_unit:
            params["length_unit"] = length_unit
        result: dict[str, Any] = self._request("GET", url, params=params)
        return result

    def retention(
        self,
        born_event: str,
        event: str,
        from_date: str,
        to_date: str,
        *,
        retention_type: str = "birth",
        born_where: str | None = None,
        where: str | None = None,
        interval: int = 1,
        interval_count: int = 8,
        unit: str = "day",
    ) -> dict[str, Any]:
        """Run a retention analysis query.

        Args:
            born_event: Event that defines cohort membership.
            event: Event that defines return.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            retention_type: Retention type (birth, compounded).
            born_where: Optional filter for born event.
            where: Optional filter for return event.
            interval: Retention interval size.
            interval_count: Number of intervals to track.
            unit: Interval unit (day, week, month).

        Returns:
            Raw API response dictionary.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters.
            RateLimitError: Rate limit exceeded.
        """
        url = self._build_url("query", "/retention")
        params: dict[str, Any] = {
            "born_event": born_event,
            "event": event,
            "from_date": from_date,
            "to_date": to_date,
            "retention_type": retention_type,
            "interval_count": interval_count,
        }
        # Mixpanel API doesn't allow both 'unit' and 'interval' together.
        # Use 'interval' for custom intervals, 'unit' for standard periods.
        if interval != 1:
            params["interval"] = interval
        else:
            params["unit"] = unit
        if born_where:
            params["born_where"] = born_where
        if where:
            params["where"] = where
        result: dict[str, Any] = self._request("GET", url, params=params)
        return result

    def jql(
        self,
        script: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> list[Any]:
        """Execute a JQL (JavaScript Query Language) script.

        Args:
            script: JQL script code.
            params: Optional parameters to pass to the script.

        Returns:
            List of results from script execution.

        Raises:
            AuthenticationError: Invalid credentials.
            JQLSyntaxError: Script syntax or runtime error.
            RateLimitError: Rate limit exceeded.
        """
        url = self._build_url("query", "/jql")
        # JQL API expects form-encoded data with params as JSON string
        form: dict[str, Any] = {"script": script}
        if params:
            form["params"] = json.dumps(params)
        # Pass script for error context in case of JQL syntax errors
        response = self._request("POST", url, form_data=form, script=script)
        if isinstance(response, list):
            return response
        return []

    # =========================================================================
    # Phase 008: Query Service Enhancements
    # =========================================================================

    def activity_feed(
        self,
        distinct_ids: list[str],
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        """Query activity feed for specific users.

        Args:
            distinct_ids: List of user identifiers to query.
            from_date: Optional start date (YYYY-MM-DD).
            to_date: Optional end date (YYYY-MM-DD).

        Returns:
            Raw API response with events under results.events.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters.
            RateLimitError: Rate limit exceeded.
        """
        url = self._build_url("query", "/stream/query")
        params: dict[str, Any] = {
            "distinct_ids": json.dumps(distinct_ids),
        }
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        result: dict[str, Any] = self._request("GET", url, params=params)
        return result

    def query_saved_report(
        self,
        bookmark_id: int,
        *,
        bookmark_type: Literal[
            "insights", "funnels", "retention", "flows"
        ] = "insights",
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        """Query a saved report by bookmark type.

        Routes to the appropriate Mixpanel API endpoint based on bookmark_type
        and returns the raw API response.

        Args:
            bookmark_id: Saved report identifier (from Mixpanel URL or list_bookmarks).
            bookmark_type: Type of bookmark to query. Determines which API endpoint
                is called. Defaults to 'insights'.
            from_date: Start date (YYYY-MM-DD). Required for funnels, optional otherwise.
                If not provided for funnels, defaults to 30 days ago.
            to_date: End date (YYYY-MM-DD). Required for funnels, optional otherwise.
                If not provided for funnels, defaults to today.

        Returns:
            Raw API response with report data. Structure varies by bookmark_type:
            - insights: {headers, computed_at, date_range, series}
            - funnels: {computed_at, data, meta}
            - retention: {date: {first, counts, rates}}
            - flows: {computed_at, steps, breakdowns, overallConversionRate}

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid bookmark_id or report not found.
            RateLimitError: Rate limit exceeded.
        """
        if bookmark_type == "insights":
            url = self._build_url("query", "/insights")
            params: dict[str, Any] = {"bookmark_id": bookmark_id}
        elif bookmark_type == "funnels":
            url = self._build_url("query", "/funnels")
            # Funnels uses funnel_id instead of bookmark_id
            # Default to 30-day window, deriving missing date from the provided one
            if from_date is None and to_date is None:
                # Neither provided: use last 30 days from today
                to_date = datetime.now().strftime("%Y-%m-%d")
                from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            elif from_date is None and to_date is not None:
                # Only to_date provided: derive from_date as 30 days before to_date
                to_date_parsed = datetime.strptime(to_date, "%Y-%m-%d")
                from_date = (to_date_parsed - timedelta(days=30)).strftime("%Y-%m-%d")
            elif to_date is None and from_date is not None:
                # Only from_date provided: derive to_date as 30 days after from_date
                # but cap at today to avoid querying future dates
                from_date_parsed = datetime.strptime(from_date, "%Y-%m-%d")
                computed_to = from_date_parsed + timedelta(days=30)
                to_date = min(computed_to, datetime.now()).strftime("%Y-%m-%d")
            params = {
                "funnel_id": bookmark_id,
                "from_date": from_date,
                "to_date": to_date,
            }
        elif bookmark_type == "retention":
            url = self._build_url("query", "/retention")
            params = {"bookmark_id": bookmark_id}
        elif bookmark_type == "flows":
            url = self._build_url("query", "/arb_funnels")
            params = {
                "bookmark_id": bookmark_id,
                "query_type": "flows_sankey",
            }
        else:
            # This shouldn't happen due to Literal type, but handle gracefully
            url = self._build_url("query", "/insights")
            params = {"bookmark_id": bookmark_id}

        result: dict[str, Any] = self._request("GET", url, params=params)
        return result

    def list_bookmarks(
        self,
        bookmark_type: str | None = None,
    ) -> dict[str, Any]:
        """List all saved reports (bookmarks) in the project.

        Retrieves metadata for all saved Insights, Funnel, Retention, and
        Flows reports in the project.

        Args:
            bookmark_type: Optional filter by report type. Valid values are
                'insights', 'funnels', 'retention', 'flows', 'launch-analysis'.
                If None, returns all bookmark types.

        Returns:
            Raw API response with 'results' array containing bookmark metadata.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Permission denied or invalid parameters.
            RateLimitError: Rate limit exceeded.
        """
        url = self._build_url(
            "app",
            f"/projects/{self._session.project.id}/bookmarks",
        )
        params: dict[str, Any] = {"v": "2"}
        if bookmark_type is not None:
            params["type"] = bookmark_type
        result: dict[str, Any] = self._request("GET", url, params=params)
        return result

    def insights_query(
        self,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an inline insights query via POST.

        Posts bookmark params directly to the insights query endpoint
        without creating a saved report. The project_id is included
        in the request body, not in query params.

        Args:
            body: Request body containing 'bookmark' (params dict),
                'project_id' (int), and 'queryLimits' (dict).

        Returns:
            Raw API response with computed_at, date_range, headers,
            series, and meta fields.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid bookmark params.
            RateLimitError: Rate limit exceeded.
        """
        url = self._build_url("query", "/insights")
        result: dict[str, Any] = self._request(
            "POST",
            url,
            data=body,
            inject_project_id=False,
        )
        return result

    def query_saved_flows(
        self,
        bookmark_id: int,
    ) -> dict[str, Any]:
        """Query a saved flows report by bookmark ID.

        Retrieves data from a saved Flows report using the arb_funnels
        endpoint with flows_sankey query type.

        Args:
            bookmark_id: Saved flows report identifier.

        Returns:
            Raw API response with steps, breakdowns, and conversion rate.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid bookmark_id or report not found.
            RateLimitError: Rate limit exceeded.
        """
        url = self._build_url("query", "/arb_funnels")
        params: dict[str, Any] = {
            "bookmark_id": bookmark_id,
            "query_type": "flows_sankey",
        }
        result: dict[str, Any] = self._request("GET", url, params=params)
        return result

    def arb_funnels_query(self, body: dict[str, Any]) -> dict[str, Any]:
        """Execute an inline flow/funnel query via the arb_funnels endpoint.

        Posts bookmark params directly to ``/arb_funnels`` with a
        ``query_type`` field that selects between flows_sankey and
        flows_top_paths. Unlike ``query_saved_flows`` which queries
        a saved report by ID, this method executes ad-hoc flow queries
        from programmatically built bookmark params.

        Args:
            body: Request body containing ``bookmark`` (params dict),
                ``project_id`` (int), and ``query_type`` (str — one of
                ``"flows_sankey"`` or ``"flows_top_paths"``).

        Returns:
            Raw API response with steps, flows, breakdowns, and
            conversion rate fields.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid bookmark params.
            RateLimitError: Rate limit exceeded.
        """
        url = self._build_url("query", "/arb_funnels")
        result: dict[str, Any] = self._request(
            "POST",
            url,
            data=body,
            inject_project_id=False,
        )
        return result

    def frequency(
        self,
        from_date: str,
        to_date: str,
        unit: str,
        addiction_unit: str,
        *,
        event: str | None = None,
        where: str | None = None,
        on: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Query event frequency distribution (addiction analysis).

        Args:
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            unit: Overall time period ("day", "week", "month").
            addiction_unit: Measurement granularity ("hour", "day").
            event: Optional event name to filter.
            where: Optional filter expression.
            on: Optional property to segment by.
            limit: Optional maximum segmentation values.

        Returns:
            Raw API response with frequency arrays in data key.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters.
            RateLimitError: Rate limit exceeded.
        """
        url = self._build_url("query", "/retention/addiction")
        params: dict[str, Any] = {
            "from_date": from_date,
            "to_date": to_date,
            "unit": unit,
            "addiction_unit": addiction_unit,
        }
        if event:
            params["event"] = event
        if where:
            params["where"] = where
        if on:
            params["on"] = on
        if limit is not None:
            params["limit"] = limit
        result: dict[str, Any] = self._request("GET", url, params=params)
        return result

    def segmentation_numeric(
        self,
        event: str,
        from_date: str,
        to_date: str,
        on: str,
        *,
        unit: str = "day",
        where: str | None = None,
        type: str = "general",
    ) -> dict[str, Any]:
        """Query events bucketed by numeric property ranges.

        Args:
            event: Event name to analyze.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            on: Numeric property expression to bucket.
            unit: Time aggregation unit ("hour", "day").
            where: Optional filter expression.
            type: Counting method ("general", "unique", "average").

        Returns:
            Raw API response with bucketed time-series in data.values.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters or non-numeric property.
            RateLimitError: Rate limit exceeded.
        """
        url = self._build_url("query", "/segmentation/numeric")
        params: dict[str, Any] = {
            "event": event,
            "from_date": from_date,
            "to_date": to_date,
            "on": on,
            "unit": unit,
            "type": type,
        }
        if where:
            params["where"] = where
        result: dict[str, Any] = self._request("GET", url, params=params)
        return result

    def segmentation_sum(
        self,
        event: str,
        from_date: str,
        to_date: str,
        on: str,
        *,
        unit: str = "day",
        where: str | None = None,
    ) -> dict[str, Any]:
        """Query sum of numeric property values.

        Args:
            event: Event name to analyze.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            on: Numeric property expression to sum.
            unit: Time aggregation unit ("hour", "day").
            where: Optional filter expression.

        Returns:
            Raw API response with sum values in results key.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters or non-numeric property.
            RateLimitError: Rate limit exceeded.
        """
        url = self._build_url("query", "/segmentation/sum")
        params: dict[str, Any] = {
            "event": event,
            "from_date": from_date,
            "to_date": to_date,
            "on": on,
            "unit": unit,
        }
        if where:
            params["where"] = where
        result: dict[str, Any] = self._request("GET", url, params=params)
        return result

    def segmentation_average(
        self,
        event: str,
        from_date: str,
        to_date: str,
        on: str,
        *,
        unit: str = "day",
        where: str | None = None,
    ) -> dict[str, Any]:
        """Query average of numeric property values.

        Args:
            event: Event name to analyze.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            on: Numeric property expression to average.
            unit: Time aggregation unit ("hour", "day").
            where: Optional filter expression.

        Returns:
            Raw API response with average values in results key.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters or non-numeric property.
            RateLimitError: Rate limit exceeded.
        """
        url = self._build_url("query", "/segmentation/average")
        params: dict[str, Any] = {
            "event": event,
            "from_date": from_date,
            "to_date": to_date,
            "on": on,
            "unit": unit,
        }
        if where:
            params["where"] = where
        result: dict[str, Any] = self._request("GET", url, params=params)
        return result

    # =========================================================================
    # Lexicon Schemas API
    # =========================================================================

    def get_schemas(
        self,
        *,
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all Lexicon schemas in the project.

        Retrieves documented event and profile property schemas from the
        Mixpanel Lexicon (data dictionary).

        Args:
            entity_type: Optional filter by type ("event", "profile", etc.).
                If None, returns all schemas.

        Returns:
            List of raw schema dictionaries from the API, each containing:
                - entityType: "event", "profile", "custom_event", etc.
                - name: Entity name
                - schemaJson: Full schema definition with properties and metadata

        Raises:
            AuthenticationError: Invalid credentials.
            RateLimitError: Rate limit exceeded after max retries.
        """
        # entity_type is a path parameter, not a query parameter
        # URL structure: /api/app/projects/{projectId}/schemas/{entity_type}
        if entity_type is not None:
            path = f"/projects/{self._session.project.id}/schemas/{entity_type}"
        else:
            path = f"/projects/{self._session.project.id}/schemas"

        url = self._build_url("app", path)

        logger.debug(
            "get_schemas request - URL: %s, entity_type filter: %s",
            url,
            entity_type,
        )

        result: dict[str, Any] = self._request("GET", url, inject_project_id=False)

        schemas: list[dict[str, Any]] = result.get("results", [])
        entity_types_returned = {s.get("entityType") for s in schemas}
        logger.debug(
            "get_schemas response - %d schemas returned, entity types: %s",
            len(schemas),
            entity_types_returned,
        )

        return schemas

    def get_schema(
        self,
        entity_type: str,
        name: str,
    ) -> dict[str, Any]:
        """Get a single Lexicon schema by entity type and name.

        Args:
            entity_type: Entity type ("event", "profile", "custom_event", etc.).
            name: Entity name.

        Returns:
            Schema dictionary normalized to match list response format:
                - entityType: The entity type from request
                - name: The entity name from request
                - schemaJson: Full schema definition with properties and metadata

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Schema not found (404 mapped to QueryError).
            RateLimitError: Rate limit exceeded after max retries.
        """
        # URL structure: /api/app/projects/{projectId}/schemas/{entity_type}?entity_name={name}
        url = self._build_url(
            "app",
            f"/projects/{self._session.project.id}/schemas/{entity_type}",
        )
        params = {"entity_name": name}

        logger.debug(
            "get_schema request - URL: %s, entity_type: %s, name: %s",
            url,
            entity_type,
            name,
        )

        result: dict[str, Any] = self._request(
            "GET", url, params=params, inject_project_id=False
        )

        # Single schema response format is: {status: "ok", results: <schemaJson>}
        # Normalize to match list response format: {entityType, name, schemaJson}
        schema_json = result.get("results", result)
        return {
            "entityType": entity_type,
            "name": name,
            "schemaJson": schema_json,
        }

    # =========================================================================
    # Schema Registry CRUD (Phase 028)
    # =========================================================================

    def list_schema_registry(
        self,
        *,
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List schema registry entries.

        Calls ``GET /api/app/.../schemas/`` or ``schemas/{entity_type}/``.

        Args:
            entity_type: Optional filter by type ("event", "custom_event",
                "profile"). If None, returns all schemas.

        Returns:
            List of schema entry dictionaries with ``entityType``, ``name``,
            ``schemaJson`` fields.

        Raises:
            AuthenticationError: Invalid credentials (401).
            RateLimitError: Rate limit exceeded (429).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                schemas = client.list_schema_registry(entity_type="event")
            ```
        """
        if entity_type is not None:
            path = self.maybe_scoped_path(f"schemas/{quote(entity_type, safe='')}")
        else:
            path = self.maybe_scoped_path("schemas")
        result = self.app_request("GET", path)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_schema_registry: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def create_schema(
        self,
        entity_type: str,
        entity_name: str,
        schema_json: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a single schema definition.

        Calls ``POST /api/app/.../schemas/{entity_type}/{entity_name}/``.

        Args:
            entity_type: Entity type ("event", "custom_event", "profile").
            entity_name: Entity name (event name or "$user" for profile).
            schema_json: JSON Schema Draft 7 definition.

        Returns:
            Created schema as dict.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error or entity already exists (400).
            RateLimitError: Rate limit exceeded (429).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                schema = client.create_schema(
                    "event", "Purchase",
                    {"properties": {"amount": {"type": "number"}}},
                )
            ```
        """
        et = quote(entity_type, safe="")
        en = quote(entity_name, safe="")
        path = self.maybe_scoped_path(f"schemas/{et}/{en}")
        result = self.app_request("POST", path, json_body=schema_json)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_schema: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def create_schemas_bulk(
        self,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Bulk create schemas.

        Calls ``POST /api/app/.../schemas/``.

        Args:
            body: Bulk creation payload from
                ``BulkCreateSchemasParams.model_dump()``.

        Returns:
            Dict with ``added`` and ``deleted`` counts.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            RateLimitError: Rate limit exceeded (429).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                resp = client.create_schemas_bulk({
                    "entries": [...], "truncate": True
                })
            ```
        """
        path = self.maybe_scoped_path("schemas")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_schemas_bulk: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_schema(
        self,
        entity_type: str,
        entity_name: str,
        schema_json: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a single schema definition (merge semantics).

        Calls ``PATCH /api/app/.../schemas/{entity_type}/{entity_name}/``.

        Args:
            entity_type: Entity type.
            entity_name: Entity name.
            schema_json: Partial JSON Schema to merge with existing.

        Returns:
            Updated schema as dict.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Entity not found or validation error (400, 404).
            RateLimitError: Rate limit exceeded (429).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.update_schema(
                    "event", "Purchase",
                    {"properties": {"tax": {"type": "number"}}},
                )
            ```
        """
        et = quote(entity_type, safe="")
        en = quote(entity_name, safe="")
        path = self.maybe_scoped_path(f"schemas/{et}/{en}")
        result = self.app_request("PATCH", path, json_body=schema_json)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_schema: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_schemas_bulk(
        self,
        body: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Bulk update schemas (merge semantics per entry).

        Calls ``PATCH /api/app/.../schemas/``.

        Args:
            body: Bulk update payload from
                ``BulkCreateSchemasParams.model_dump()``.

        Returns:
            List of per-entry results with ``status`` ("ok" or "error").

        Raises:
            AuthenticationError: Invalid credentials (401).
            RateLimitError: Rate limit exceeded (429).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                results = client.update_schemas_bulk({"entries": [...]})
            ```
        """
        path = self.maybe_scoped_path("schemas")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from update_schemas_bulk: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def delete_schemas(
        self,
        *,
        entity_type: str | None = None,
        entity_name: str | None = None,
    ) -> dict[str, Any]:
        """Delete schemas by entity type and/or name.

        Calls ``DELETE /api/app/.../schemas/[{et}/[{en}/]]``.

        If both provided, deletes a single schema. If only entity_type,
        deletes all schemas of that type. If neither, deletes all schemas.

        Args:
            entity_type: Filter by entity type.
            entity_name: Filter by entity name (requires entity_type).

        Returns:
            Dict with ``deleteCount`` field.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid parameters (400).
            RateLimitError: Rate limit exceeded (429).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                resp = client.delete_schemas(
                    entity_type="event", entity_name="Purchase"
                )
            ```
        """
        if entity_name is not None and entity_type is None:
            raise MixpanelDataError(
                "entity_name requires entity_type: providing entity_name "
                "without entity_type would delete all schemas",
            )
        base = "schemas"
        if entity_type is not None:
            base = f"schemas/{quote(entity_type, safe='')}"
            if entity_name is not None:
                base = f"{base}/{quote(entity_name, safe='')}"
        path = self.maybe_scoped_path(base)
        result = self.app_request("DELETE", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from delete_schemas: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    # =========================================================================
    # Dashboard CRUD (Phase 024)
    # =========================================================================

    def list_dashboards(self, *, ids: list[int] | None = None) -> list[dict[str, Any]]:
        """List dashboards for the current project/workspace.

        Calls ``GET /api/app/projects/{pid}/dashboards`` (or workspace-scoped).

        Args:
            ids: Optional list of dashboard IDs to filter. When provided, only
                dashboards matching these IDs are returned.

        Returns:
            List of dashboard dictionaries. Each dictionary contains at minimum
            ``id``, ``title``, and ``created`` fields.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400, 404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                dashboards = client.list_dashboards()
                for d in dashboards:
                    print(f"{d['id']}: {d['title']}")
            ```
        """
        path = self.maybe_scoped_path("dashboards")
        params: dict[str, str] = {}
        if ids:
            params["ids"] = ",".join(str(i) for i in ids)
        result = self.app_request("GET", path, params=params if params else None)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_dashboards: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def create_dashboard(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a new dashboard.

        Calls ``POST /api/app/projects/{pid}/dashboards`` (or workspace-scoped).

        Args:
            body: Dashboard creation payload. Must include ``title`` at minimum.
                May also include ``description``, ``layout``, and ``reports``.

        Returns:
            Dictionary representing the newly created dashboard, including
            its ``id`` and other metadata.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid payload or missing required fields (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                dashboard = client.create_dashboard({"title": "My Dashboard"})
                print(f"Created dashboard {dashboard['id']}")
            ```
        """
        path = self.maybe_scoped_path("dashboards")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_dashboard: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def get_dashboard(self, dashboard_id: int) -> dict[str, Any]:
        """Get a single dashboard by ID.

        Calls ``GET /api/app/projects/{pid}/dashboards/{dashboard_id}``
        (or workspace-scoped).

        Args:
            dashboard_id: The numeric dashboard identifier.

        Returns:
            Dictionary representing the dashboard, including ``id``, ``title``,
            ``description``, ``layout``, and ``reports``.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404) or invalid ID (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                dashboard = client.get_dashboard(12345)
                print(dashboard["title"])
            ```
        """
        path = self.maybe_scoped_path(f"dashboards/{dashboard_id}")
        result = self.app_request("GET", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_dashboard: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_dashboard(
        self, dashboard_id: int, body: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing dashboard (partial update).

        Calls ``PATCH /api/app/projects/{pid}/dashboards/{dashboard_id}``
        (or workspace-scoped).

        Args:
            dashboard_id: The numeric dashboard identifier.
            body: Partial update payload. May include ``title``, ``description``,
                ``layout``, or other mutable dashboard fields.

        Returns:
            Dictionary representing the updated dashboard.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404) or invalid payload (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.update_dashboard(12345, {"title": "New Title"})
                print(updated["title"])
            ```
        """
        path = self.maybe_scoped_path(f"dashboards/{dashboard_id}")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_dashboard: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def delete_dashboard(self, dashboard_id: int) -> None:
        """Delete a single dashboard.

        Calls ``DELETE /api/app/projects/{pid}/dashboards/{dashboard_id}``
        (or workspace-scoped).

        Args:
            dashboard_id: The numeric dashboard identifier.

        Returns:
            None.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404) or invalid ID (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.delete_dashboard(12345)
            ```
        """
        path = self.maybe_scoped_path(f"dashboards/{dashboard_id}")
        self.app_request("DELETE", path)

    def bulk_delete_dashboards(self, ids: list[int]) -> None:
        """Delete multiple dashboards at once.

        Calls ``DELETE /api/app/projects/{pid}/dashboards``
        (or workspace-scoped) with a JSON body containing the IDs.

        Args:
            ids: List of dashboard IDs to delete.

        Returns:
            None.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid IDs or API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.bulk_delete_dashboards([111, 222, 333])
            ```
        """
        path = self.maybe_scoped_path("dashboards/bulk-delete")
        self.app_request("POST", path, json_body={"dashboard_ids": ids})

    def favorite_dashboard(self, dashboard_id: int) -> None:
        """Mark a dashboard as a favorite for the current user.

        Calls ``POST /api/app/projects/{pid}/dashboards/{dashboard_id}/favorites``
        (or workspace-scoped).

        Args:
            dashboard_id: The numeric dashboard identifier.

        Returns:
            None.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.favorite_dashboard(12345)
            ```
        """
        path = self.maybe_scoped_path(f"dashboards/{dashboard_id}/favorites")
        self.app_request("POST", path)

    def unfavorite_dashboard(self, dashboard_id: int) -> None:
        """Remove a dashboard from the current user's favorites.

        Calls ``DELETE /api/app/projects/{pid}/dashboards/{dashboard_id}/favorites``
        (or workspace-scoped).

        Args:
            dashboard_id: The numeric dashboard identifier.

        Returns:
            None.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.unfavorite_dashboard(12345)
            ```
        """
        path = self.maybe_scoped_path(f"dashboards/{dashboard_id}/favorites")
        self.app_request("DELETE", path)

    def pin_dashboard(self, dashboard_id: int) -> None:
        """Pin a dashboard for the current project/workspace.

        Calls ``POST /api/app/projects/{pid}/dashboards/{dashboard_id}/pin``
        (or workspace-scoped).

        Args:
            dashboard_id: The numeric dashboard identifier.

        Returns:
            None.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.pin_dashboard(12345)
            ```
        """
        path = self.maybe_scoped_path(f"dashboards/{dashboard_id}/pin")
        self.app_request("POST", path)

    def unpin_dashboard(self, dashboard_id: int) -> None:
        """Unpin a dashboard from the current project/workspace.

        Calls ``DELETE /api/app/projects/{pid}/dashboards/{dashboard_id}/pin``
        (or workspace-scoped).

        Args:
            dashboard_id: The numeric dashboard identifier.

        Returns:
            None.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.unpin_dashboard(12345)
            ```
        """
        path = self.maybe_scoped_path(f"dashboards/{dashboard_id}/pin")
        self.app_request("DELETE", path)

    def remove_report_from_dashboard(
        self, dashboard_id: int, bookmark_id: int
    ) -> dict[str, Any] | None:
        """Remove a report (bookmark) from a dashboard.

        Calls ``PATCH /api/app/projects/{pid}/dashboards/{dashboard_id}``
        (or workspace-scoped) with a ``delete`` content action.

        Args:
            dashboard_id: The numeric dashboard identifier.
            bookmark_id: The numeric bookmark/report identifier to remove.

        Returns:
            Dictionary representing the updated dashboard after report removal,
            or None if the API returned 204 No Content.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard or report not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.remove_report_from_dashboard(12345, 67890)
            ```
        """
        path = self.maybe_scoped_path(f"dashboards/{dashboard_id}")
        body: dict[str, Any] = {
            "content": {
                "action": "delete",
                "content_type": "report",
                "content_id": bookmark_id,
            }
        }
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from remove_report_from_dashboard: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def add_report_to_dashboard(
        self, dashboard_id: int, bookmark_id: int
    ) -> dict[str, Any]:
        """Add a report (bookmark) to a dashboard.

        Clones the specified bookmark onto the dashboard by calling
        ``PATCH /api/app/projects/{pid}/dashboards/{dashboard_id}``
        (or workspace-scoped) with a ``create`` content action.

        Args:
            dashboard_id: The numeric dashboard identifier.
            bookmark_id: The numeric bookmark/report identifier to add.

        Returns:
            Dictionary representing the updated dashboard after report addition.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard or bookmark not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.add_report_to_dashboard(12345, 67890)
            ```
        """
        path = self.maybe_scoped_path(f"dashboards/{dashboard_id}")
        body: dict[str, Any] = {
            "content": {
                "action": "create",
                "content_type": "report",
                "content_params": {"source_bookmark_id": bookmark_id},
            }
        }
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from add_report_to_dashboard: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def list_blueprint_templates(
        self, *, include_reports: bool = False
    ) -> list[dict[str, Any]]:
        """List available dashboard blueprint templates.

        Calls ``GET /api/app/projects/{pid}/dashboards/blueprints``
        (or workspace-scoped).

        Args:
            include_reports: When True, include report details in each
                blueprint template. Defaults to False.

        Returns:
            List of blueprint template dictionaries, each containing
            ``template_type`` and template metadata.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                templates = client.list_blueprint_templates(include_reports=True)
                for t in templates:
                    print(t["template_type"])
            ```
        """
        path = self.maybe_scoped_path("dashboards/blueprints-all")
        params: dict[str, str] = {}
        if include_reports:
            params["include_reports"] = "true"
        result = self.app_request("GET", path, params=params if params else None)
        # The blueprints-all endpoint returns {"templates": {name: data, ...}}
        if isinstance(result, dict) and "templates" in result:
            templates = result["templates"]
            if isinstance(templates, dict):
                # Convert {name: data} to [{...data, "name": name}, ...]
                results: list[dict[str, Any]] = []
                for name, data in templates.items():
                    if isinstance(data, dict):
                        results.append({**data, "name": name})
                    else:
                        logger.warning(
                            "Skipping blueprint template %r: expected dict, got %s",
                            name,
                            type(data).__name__,
                        )
                return results
            if isinstance(templates, list):
                return templates
        if isinstance(result, list):
            return result
        raise MixpanelDataError(
            f"Unexpected response from list_blueprint_templates: "
            f"expected templates dict, got {type(result).__name__}",
        )

    def create_blueprint(self, template_type: str) -> dict[str, Any]:
        """Create a dashboard from a blueprint template.

        Calls ``POST /api/app/projects/{pid}/dashboards/blueprints``
        (or workspace-scoped).

        Args:
            template_type: The blueprint template type identifier
                (e.g., ``"company_kpis"``, ``"marketing"``).

        Returns:
            Dictionary representing the newly created dashboard from the
            blueprint, including its ``id`` and populated reports.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid template type (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                dashboard = client.create_blueprint("company_kpis")
                print(f"Created blueprint dashboard {dashboard['id']}")
            ```
        """
        path = self.maybe_scoped_path("dashboards/blueprints")
        result = self.app_request(
            "POST", path, json_body={"template_type": template_type}
        )
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_blueprint: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def get_blueprint_config(self, dashboard_id: int) -> dict[str, Any]:
        """Get the blueprint configuration for a dashboard.

        Calls ``GET /api/app/projects/{pid}/dashboards/{dashboard_id}/blueprint-config``
        (or workspace-scoped).

        Args:
            dashboard_id: The numeric dashboard identifier.

        Returns:
            Dictionary containing the blueprint configuration, including
            template type and customization settings.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found or not a blueprint (404/400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                config = client.get_blueprint_config(12345)
                print(config["template_type"])
            ```
        """
        path = self.maybe_scoped_path(f"dashboards/{dashboard_id}/blueprint-config")
        result = self.app_request("GET", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_blueprint_config: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_blueprint_cohorts(self, cohorts: list[dict[str, Any]]) -> None:
        """Update cohort mappings for blueprint dashboards.

        Calls ``PUT /api/app/projects/{pid}/dashboards/blueprints/cohorts``
        (or workspace-scoped).

        Args:
            cohorts: List of cohort mapping dictionaries. Each entry maps a
                blueprint cohort placeholder to an actual cohort ID.

        Returns:
            None.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid cohort mappings (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.update_blueprint_cohorts([
                    {"placeholder": "new_users", "cohort_id": 42}
                ])
            ```
        """
        path = self.maybe_scoped_path("dashboards/blueprints/cohorts")
        self.app_request("PUT", path, json_body={"cohorts": cohorts})

    def finalize_blueprint(self, body: dict[str, Any]) -> dict[str, Any]:
        """Finalize a blueprint dashboard after configuration.

        Calls ``POST /api/app/projects/{pid}/dashboards/blueprints/finish``
        (or workspace-scoped).

        Args:
            body: Finalization payload containing the blueprint dashboard ID
                and any final configuration overrides.

        Returns:
            Dictionary representing the finalized dashboard.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid payload or blueprint not found (400/404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                result = client.finalize_blueprint({"dashboard_id": 12345})
                print(f"Finalized: {result['id']}")
            ```
        """
        path = self.maybe_scoped_path("dashboards/blueprints/finish")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from finalize_blueprint: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def create_rca_dashboard(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a root-cause-analysis (RCA) dashboard.

        Calls ``POST /api/app/projects/{pid}/dashboards/rca``
        (or workspace-scoped).

        Args:
            body: RCA dashboard creation payload, typically including the
                metric event, time range, and analysis parameters.

        Returns:
            Dictionary representing the newly created RCA dashboard.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid payload (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                rca = client.create_rca_dashboard({
                    "event": "purchase",
                    "from_date": "2025-01-01",
                    "to_date": "2025-01-31",
                })
                print(f"RCA dashboard: {rca['id']}")
            ```
        """
        path = self.maybe_scoped_path("dashboards/rca")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_rca_dashboard: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def get_bookmark_dashboard_ids(self, bookmark_id: int) -> list[int]:
        """Get dashboard IDs that contain a specific bookmark/report.

        Calls ``GET /api/app/projects/{pid}/dashboards/bookmarks/{bookmark_id}/dashboard-ids``
        (or workspace-scoped).

        Args:
            bookmark_id: The numeric bookmark/report identifier.

        Returns:
            List of integer dashboard IDs that contain the specified bookmark.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Bookmark not found (404) or invalid ID (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                dashboard_ids = client.get_bookmark_dashboard_ids(67890)
                print(f"Report is on dashboards: {dashboard_ids}")
            ```
        """
        path = self.maybe_scoped_path(
            f"dashboards/bookmarks/{bookmark_id}/dashboard-ids"
        )
        result = self.app_request("GET", path)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from get_bookmark_dashboard_ids: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def get_dashboard_erf(self, dashboard_id: int) -> dict[str, Any]:
        """Get ERF data for a dashboard.

        Calls ``GET /api/app/projects/{pid}/dashboards/{dashboard_id}/erf``
        (or workspace-scoped).

        Args:
            dashboard_id: The numeric dashboard identifier.

        Returns:
            Dictionary containing the ERF data for the dashboard, describing
            the ERF metrics for the dashboard.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404) or invalid ID (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                erf = client.get_dashboard_erf(12345)
                print(erf)
            ```
        """
        path = self.maybe_scoped_path(f"dashboards/{dashboard_id}/erf")
        result = self.app_request("GET", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_dashboard_erf: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_report_link(
        self, dashboard_id: int, report_link_id: int, body: dict[str, Any]
    ) -> None:
        """Update a report link on a dashboard.

        Calls ``PATCH /api/app/projects/{pid}/dashboards/{dashboard_id}/report-links/{report_link_id}``
        (or workspace-scoped).

        Args:
            dashboard_id: The numeric dashboard identifier.
            report_link_id: The numeric report link identifier.
            body: Partial update payload for the report link (e.g., position,
                size, or display settings).

        Returns:
            None.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard or report link not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.update_report_link(12345, 99, {"position": {"x": 0, "y": 1}})
            ```
        """
        path = self.maybe_scoped_path(
            f"dashboards/{dashboard_id}/report-links/{report_link_id}"
        )
        self.app_request("PATCH", path, json_body=body)

    def update_text_card(
        self, dashboard_id: int, text_card_id: int, body: dict[str, Any]
    ) -> None:
        """Update a text card on a dashboard.

        Calls ``PATCH /api/app/projects/{pid}/dashboards/{dashboard_id}/text-cards/{text_card_id}``
        (or workspace-scoped).

        Args:
            dashboard_id: The numeric dashboard identifier.
            text_card_id: The numeric text card identifier.
            body: Partial update payload for the text card (e.g., ``text``,
                ``position``, or ``size``).

        Returns:
            None.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard or text card not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.update_text_card(12345, 55, {"text": "Updated heading"})
            ```
        """
        path = self.maybe_scoped_path(
            f"dashboards/{dashboard_id}/text-cards/{text_card_id}"
        )
        self.app_request("PATCH", path, json_body=body)

    # =========================================================================
    # Bookmark/Report CRUD (Phase 024)
    # =========================================================================

    def list_bookmarks_v2(
        self,
        *,
        bookmark_type: str | None = None,
        ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """List bookmarks (saved reports) via the App API.

        Retrieves metadata for saved Insights, Funnels, Retention, Flows,
        and other report types. Supports filtering by type and by explicit
        bookmark IDs.

        Args:
            bookmark_type: Optional report-type filter (e.g., ``"insights"``,
                ``"funnels"``, ``"retention"``).
            ids: Optional list of bookmark IDs to retrieve.

        Returns:
            A list of bookmark dicts, each containing keys such as ``id``,
            ``name``, ``type``, and ``params``.

        Raises:
            AuthenticationError: Invalid or expired credentials (401).
            QueryError: Invalid parameters (400/403).
            RateLimitError: Rate limit exceeded after max retries (429).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                bookmarks = client.list_bookmarks_v2(bookmark_type="funnels")
            ```
        """
        path = self.maybe_scoped_path("bookmarks")
        params: dict[str, str] = {"v": "2"}
        if bookmark_type:
            params["type"] = bookmark_type
        if ids:
            params["ids"] = ",".join(str(i) for i in ids)
        result = self.app_request("GET", path, params=params)
        # v2 envelope: {"results": {"results": [...]}}
        if isinstance(result, dict) and "results" in result:
            inner = result["results"]
            if isinstance(inner, list):
                return inner
        if isinstance(result, list):
            return result
        raise MixpanelDataError(
            f"Unexpected response from list_bookmarks_v2: "
            f"expected list or v2 envelope, got {type(result).__name__}",
        )

    def create_bookmark(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a new bookmark (saved report).

        Args:
            body: Bookmark creation payload with ``name``, ``type``, and
                ``params`` fields.

        Returns:
            The newly created bookmark dict with assigned ``id``.

        Raises:
            AuthenticationError: Invalid or expired credentials (401).
            QueryError: Invalid payload (400/422).
            RateLimitError: Rate limit exceeded after max retries (429).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                bookmark = client.create_bookmark({
                    "name": "Daily Active Users",
                    "type": "insights",
                    "params": {"event": ["login"]},
                })
            ```
        """
        path = self.maybe_scoped_path("bookmarks")
        body_v2 = {**body, "v": 2}
        result = self.app_request("POST", path, json_body=body_v2)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_bookmark: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def get_bookmark(self, bookmark_id: int) -> dict[str, Any]:
        """Retrieve a single bookmark by ID.

        Args:
            bookmark_id: Unique identifier of the bookmark.

        Returns:
            Bookmark dict with ``id``, ``name``, ``type``, and ``params``.

        Raises:
            AuthenticationError: Invalid or expired credentials (401).
            QueryError: Bookmark not found (404).
            RateLimitError: Rate limit exceeded after max retries (429).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                bookmark = client.get_bookmark(12345)
            ```
        """
        path = self.maybe_scoped_path(f"bookmarks/{bookmark_id}")
        result = self.app_request("GET", path, params={"v": "2"})
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_bookmark: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_bookmark(self, bookmark_id: int, body: dict[str, Any]) -> dict[str, Any]:
        """Update an existing bookmark (partial update via PATCH).

        Args:
            bookmark_id: Unique identifier of the bookmark.
            body: Fields to update (e.g., ``name``, ``description``).

        Returns:
            The updated bookmark dict.

        Raises:
            AuthenticationError: Invalid or expired credentials (401).
            QueryError: Bookmark not found or invalid payload (400/404/422).
            RateLimitError: Rate limit exceeded after max retries (429).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.update_bookmark(12345, {"name": "Renamed"})
            ```
        """
        path = self.maybe_scoped_path(f"bookmarks/{bookmark_id}")
        body_v2 = {**body, "v": 2}
        result = self.app_request("PATCH", path, json_body=body_v2)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_bookmark: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def delete_bookmark(self, bookmark_id: int) -> None:
        """Delete a bookmark (saved report).

        Args:
            bookmark_id: Unique identifier of the bookmark to delete.

        Raises:
            AuthenticationError: Invalid or expired credentials (401).
            QueryError: Bookmark not found (404).
            RateLimitError: Rate limit exceeded after max retries (429).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.delete_bookmark(12345)
            ```
        """
        path = self.maybe_scoped_path(f"bookmarks/{bookmark_id}")
        self.app_request("DELETE", path)

    def bulk_delete_bookmarks(self, ids: list[int]) -> None:
        """Delete multiple bookmarks in a single request.

        Args:
            ids: List of bookmark IDs to delete.

        Raises:
            AuthenticationError: Invalid or expired credentials (401).
            QueryError: One or more IDs not found (400/404).
            RateLimitError: Rate limit exceeded after max retries (429).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.bulk_delete_bookmarks([123, 456])
            ```
        """
        path = self.maybe_scoped_path("bookmarks/bulk-delete")
        self.app_request("POST", path, json_body={"bookmark_ids": ids})

    def bulk_update_bookmarks(self, entries: list[dict[str, Any]]) -> None:
        """Update multiple bookmarks in a single request.

        Args:
            entries: List of update dicts, each with ``id`` and fields to update.

        Raises:
            AuthenticationError: Invalid or expired credentials (401).
            QueryError: Invalid entries or IDs not found (400/404/422).
            RateLimitError: Rate limit exceeded after max retries (429).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.bulk_update_bookmarks([
                    {"id": 123, "name": "Updated Report"},
                ])
            ```
        """
        path = self.maybe_scoped_path("bookmarks/bulk-update")
        self.app_request("POST", path, json_body={"bookmarks": entries})

    def bookmark_linked_dashboard_ids(self, bookmark_id: int) -> list[int]:
        """Get dashboard IDs linked to a bookmark.

        Args:
            bookmark_id: Unique identifier of the bookmark.

        Returns:
            List of integer dashboard IDs. Empty list if not linked.

        Raises:
            AuthenticationError: Invalid or expired credentials (401).
            QueryError: Bookmark not found (404).
            RateLimitError: Rate limit exceeded after max retries (429).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                dash_ids = client.bookmark_linked_dashboard_ids(12345)
            ```
        """
        path = self.maybe_scoped_path(f"bookmarks/{bookmark_id}/linked-dashboard-ids")
        result = self.app_request("GET", path)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from bookmark_linked_dashboard_ids: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def get_bookmark_history(
        self,
        bookmark_id: int,
        *,
        cursor: str | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        """Get the change history for a bookmark.

        Args:
            bookmark_id: Unique identifier of the bookmark.
            cursor: Opaque pagination cursor from a previous call.
            page_size: Maximum entries per page.

        Returns:
            Dict with ``results`` (history entries) and ``pagination``.

        Raises:
            AuthenticationError: Invalid or expired credentials (401).
            QueryError: Bookmark not found (404).
            RateLimitError: Rate limit exceeded after max retries (429).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                page = client.get_bookmark_history(12345, page_size=10)
            ```
        """
        path = self.maybe_scoped_path(f"bookmarks/{bookmark_id}/history")
        params: dict[str, str] = {}
        if cursor:
            params["cursor"] = cursor
        if page_size is not None:
            params["page_size"] = str(page_size)
        result = self.app_request(
            "GET", path, params=params if params else None, _raw=True
        )
        if isinstance(result, dict):
            # The raw response is {"status": "ok", "results": <inner>}.
            # <inner> may be the history dict {"results": [...], "pagination": {...}}
            # or already a list if the API returns results directly.
            inner = result.get("results", result)
            if isinstance(inner, dict) and "results" in inner:
                # inner is {"results": [...], "pagination": {...}} — use as-is
                if "pagination" not in inner:
                    inner["pagination"] = None
                return inner
            if isinstance(inner, list):
                # Flat list of history entries — wrap with pagination
                return {"results": inner, "pagination": None}
            # Unexpected dict shape — return with defaults
            return {"results": inner, "pagination": None}
        if isinstance(result, list):
            return {"results": result, "pagination": None}
        raise MixpanelDataError(
            f"Unexpected response from get_bookmark_history: "
            f"expected dict, got {type(result).__name__}",
        )

    # =========================================================================
    # Cohort CRUD (Phase 024)
    # =========================================================================

    def list_cohorts_app(
        self,
        *,
        data_group_id: str | None = None,
        ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """List cohorts via the App API.

        Args:
            data_group_id: Optional data group filter.
            ids: Optional list of cohort IDs to retrieve.

        Returns:
            List of cohort dictionaries with ``id``, ``name``, ``count``, etc.

        Raises:
            AuthenticationError: Invalid or missing credentials (401).
            RateLimitError: Rate limit exceeded after max retries (429).
            QueryError: Bad request (400/404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                cohorts = client.list_cohorts_app()
            ```
        """
        path = self.maybe_scoped_path("cohorts")
        params: dict[str, str] = {}
        if data_group_id:
            params["data_group_id"] = data_group_id
        if ids:
            params["ids"] = ",".join(str(i) for i in ids)
        result = self.app_request("GET", path, params=params if params else None)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_cohorts_app: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def get_cohort(self, cohort_id: int) -> dict[str, Any]:
        """Get a single cohort by ID via the App API.

        Args:
            cohort_id: Numeric identifier of the cohort.

        Returns:
            Cohort dict with ``id``, ``name``, ``description``, ``count``, etc.

        Raises:
            AuthenticationError: Invalid or missing credentials (401).
            RateLimitError: Rate limit exceeded after max retries (429).
            QueryError: Cohort not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                cohort = client.get_cohort(12345)
            ```
        """
        path = self.maybe_scoped_path(f"cohorts/{cohort_id}")
        result = self.app_request("GET", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_cohort: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def create_cohort(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a new cohort via the App API.

        Args:
            body: Cohort definition with ``name`` and optional fields.

        Returns:
            The newly created cohort dict with assigned ``id``.

        Raises:
            AuthenticationError: Invalid or missing credentials (401).
            RateLimitError: Rate limit exceeded after max retries (429).
            QueryError: Invalid cohort definition (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                cohort = client.create_cohort({"name": "Power Users"})
            ```
        """
        path = self.maybe_scoped_path("cohorts")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_cohort: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_cohort(self, cohort_id: int, body: dict[str, Any]) -> dict[str, Any]:
        """Update an existing cohort via the App API.

        Args:
            cohort_id: Numeric identifier of the cohort.
            body: Fields to update (e.g., ``name``, ``description``).

        Returns:
            The updated cohort dict.

        Raises:
            AuthenticationError: Invalid or missing credentials (401).
            RateLimitError: Rate limit exceeded after max retries (429).
            QueryError: Cohort not found or invalid update (400/404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.update_cohort(12345, {"name": "Renamed"})
            ```
        """
        path = self.maybe_scoped_path(f"cohorts/{cohort_id}")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_cohort: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def delete_cohort(self, cohort_id: int) -> None:
        """Delete a single cohort via the App API.

        Args:
            cohort_id: Numeric identifier of the cohort to delete.

        Raises:
            AuthenticationError: Invalid or missing credentials (401).
            RateLimitError: Rate limit exceeded after max retries (429).
            QueryError: Cohort not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.delete_cohort(12345)
            ```
        """
        path = self.maybe_scoped_path(f"cohorts/{cohort_id}")
        self.app_request("DELETE", path)

    def bulk_delete_cohorts(self, ids: list[int]) -> None:
        """Delete multiple cohorts in a single request.

        Args:
            ids: List of cohort IDs to delete.

        Raises:
            AuthenticationError: Invalid or missing credentials (401).
            RateLimitError: Rate limit exceeded after max retries (429).
            QueryError: One or more IDs not found (400/404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.bulk_delete_cohorts([123, 456])
            ```
        """
        path = self.maybe_scoped_path("cohorts/bulk-delete")
        self.app_request("POST", path, json_body={"cohort_ids": ids})

    def bulk_update_cohorts(self, entries: list[dict[str, Any]]) -> None:
        """Update multiple cohorts in a single request.

        Args:
            entries: List of cohort update dicts, each with ``id`` and
                fields to update.

        Raises:
            AuthenticationError: Invalid or missing credentials (401).
            RateLimitError: Rate limit exceeded after max retries (429).
            QueryError: Invalid entries or IDs not found (400/404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.bulk_update_cohorts([
                    {"id": 123, "name": "Renamed Cohort"},
                ])
            ```
        """
        path = self.maybe_scoped_path("cohorts/bulk-update")
        self.app_request("POST", path, json_body={"cohorts": entries})

    # =========================================================================
    # Feature Flag CRUD (Phase 025)
    # =========================================================================

    def list_feature_flags(
        self, *, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        """List feature flags for the current project/workspace.

        Calls ``GET /api/app/projects/{pid}/workspaces/{wid}/feature-flags/``.

        Args:
            include_archived: When True, include archived flags in results.

        Returns:
            List of feature flag dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400, 404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                flags = client.list_feature_flags()
            ```
        """
        path = self.require_scoped_path("feature-flags/")
        params: dict[str, str] = {}
        if include_archived:
            params["include_archived"] = "true"
        result = self.app_request("GET", path, params=params if params else None)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_feature_flags: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def create_feature_flag(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a new feature flag.

        Calls ``POST /api/app/projects/{pid}/workspaces/{wid}/feature-flags/``.

        Args:
            body: Flag creation payload with ``name`` and ``key`` required.

        Returns:
            Dictionary representing the newly created flag.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Duplicate key or invalid payload (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                flag = client.create_feature_flag({"name": "X", "key": "x"})
            ```
        """
        path = self.require_scoped_path("feature-flags/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_feature_flag: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def get_feature_flag(self, flag_id: str) -> dict[str, Any]:
        """Get a single feature flag by ID.

        Calls ``GET /api/app/projects/{pid}/workspaces/{wid}/feature-flags/{id}/``.

        Args:
            flag_id: Feature flag UUID.

        Returns:
            Dictionary representing the flag.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404) or invalid ID (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                flag = client.get_feature_flag("abc-123")
            ```
        """
        path = self.require_scoped_path(f"feature-flags/{flag_id}/")
        result = self.app_request("GET", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_feature_flag: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_feature_flag(self, flag_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Update a feature flag (full replacement).

        Calls ``PUT /api/app/projects/{pid}/workspaces/{wid}/feature-flags/{id}/``.

        Args:
            flag_id: Feature flag UUID.
            body: Complete flag configuration (PUT semantics).

        Returns:
            Dictionary representing the updated flag.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404) or invalid payload (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.update_feature_flag("abc-123", body)
            ```
        """
        path = self.require_scoped_path(f"feature-flags/{flag_id}/")
        result = self.app_request("PUT", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_feature_flag: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def delete_feature_flag(self, flag_id: str) -> None:
        """Delete a feature flag.

        Calls ``DELETE /api/app/projects/{pid}/workspaces/{wid}/feature-flags/{id}/``.

        Args:
            flag_id: Feature flag UUID.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.delete_feature_flag("abc-123")
            ```
        """
        path = self.require_scoped_path(f"feature-flags/{flag_id}/")
        self.app_request("DELETE", path)

    def archive_feature_flag(self, flag_id: str) -> None:
        """Archive a feature flag (soft-delete).

        Calls ``POST /api/app/projects/{pid}/workspaces/{wid}/feature-flags/{id}/archive/``.

        Args:
            flag_id: Feature flag UUID.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.archive_feature_flag("abc-123")
            ```
        """
        path = self.require_scoped_path(f"feature-flags/{flag_id}/archive/")
        self.app_request("POST", path)

    def restore_feature_flag(self, flag_id: str) -> dict[str, Any]:
        """Restore an archived feature flag.

        Calls ``DELETE /api/app/projects/{pid}/workspaces/{wid}/feature-flags/{id}/archive/``.

        Args:
            flag_id: Feature flag UUID.

        Returns:
            Dictionary representing the restored flag.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                flag = client.restore_feature_flag("abc-123")
            ```
        """
        path = self.require_scoped_path(f"feature-flags/{flag_id}/archive/")
        result = self.app_request("DELETE", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from restore_feature_flag: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def duplicate_feature_flag(self, flag_id: str) -> dict[str, Any]:
        """Duplicate a feature flag.

        Calls ``POST /api/app/projects/{pid}/workspaces/{wid}/feature-flags/{id}/duplicate/``.

        Args:
            flag_id: Feature flag UUID.

        Returns:
            Dictionary representing the new duplicate flag.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                dup = client.duplicate_feature_flag("abc-123")
            ```
        """
        path = self.require_scoped_path(f"feature-flags/{flag_id}/duplicate/")
        result = self.app_request("POST", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from duplicate_feature_flag: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def set_flag_test_users(self, flag_id: str, body: dict[str, Any]) -> None:
        """Set test user variant overrides for a feature flag.

        Calls ``PUT /api/app/projects/{pid}/workspaces/{wid}/feature-flags/{id}/test-users/``.

        Args:
            flag_id: Feature flag UUID.
            body: Test user mapping (variant key → user distinct ID).

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404) or invalid payload (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.set_flag_test_users("abc-123", {"users": {"on": "uid"}})
            ```
        """
        path = self.require_scoped_path(f"feature-flags/{flag_id}/test-users/")
        self.app_request("PUT", path, json_body=body)

    def get_flag_history(
        self, flag_id: str, *, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Get change history for a feature flag.

        Calls ``GET /api/app/projects/{pid}/workspaces/{wid}/feature-flags/{id}/history/``.

        Args:
            flag_id: Feature flag UUID.
            params: Optional query parameters (page, page_size).

        Returns:
            Dictionary with ``events`` and ``count`` fields.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                history = client.get_flag_history("abc-123")
            ```
        """
        path = self.require_scoped_path(f"feature-flags/{flag_id}/history/")
        result = self.app_request("GET", path, params=params)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_flag_history: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def get_flag_limits(self) -> dict[str, Any]:
        """Get account-level feature flag limits and usage.

        Calls ``GET /api/app/projects/{pid}/feature-flags/limits/``
        (always project-scoped; does not require a workspace ID).

        Returns:
            Dictionary with ``limit``, ``is_trial``, ``current_usage``,
            ``contract_status`` fields.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                limits = client.get_flag_limits()
            ```
        """
        pid = self._session.project.id
        path = f"/projects/{pid}/feature-flags/limits/"
        result = self.app_request("GET", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_flag_limits: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    # =========================================================================
    # Experiment CRUD & Lifecycle (Phase 025)
    # =========================================================================

    def list_experiments(
        self, *, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        """List experiments for the current project.

        Calls ``GET /api/app/projects/{pid}/experiments/``
        (optionally workspace-scoped).

        Args:
            include_archived: When True, include archived experiments.

        Returns:
            List of experiment dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400, 404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                experiments = client.list_experiments()
            ```
        """
        path = self.maybe_scoped_path("experiments/")
        params: dict[str, str] = {}
        if include_archived:
            params["include_archived"] = "true"
        result = self.app_request("GET", path, params=params if params else None)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_experiments: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def create_experiment(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a new experiment.

        Calls ``POST /api/app/projects/{pid}/experiments/``
        (optionally workspace-scoped).

        Args:
            body: Experiment creation payload with ``name`` required.

        Returns:
            Dictionary representing the newly created experiment.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid payload (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                exp = client.create_experiment({"name": "Test"})
            ```
        """
        path = self.maybe_scoped_path("experiments/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_experiment: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def get_experiment(self, experiment_id: str) -> dict[str, Any]:
        """Get a single experiment by ID.

        Calls ``GET /api/app/projects/{pid}/experiments/{id}``
        (no trailing slash).

        Args:
            experiment_id: Experiment UUID.

        Returns:
            Dictionary representing the experiment.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Experiment not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                exp = client.get_experiment("xyz-456")
            ```
        """
        path = self.maybe_scoped_path(f"experiments/{experiment_id}")
        result = self.app_request("GET", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_experiment: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_experiment(
        self, experiment_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an experiment (partial update).

        Calls ``PATCH /api/app/projects/{pid}/experiments/{id}``
        (no trailing slash).

        Args:
            experiment_id: Experiment UUID.
            body: Partial update payload (PATCH semantics).

        Returns:
            Dictionary representing the updated experiment.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Experiment not found (404) or invalid payload (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.update_experiment("xyz-456", {"name": "New"})
            ```
        """
        path = self.maybe_scoped_path(f"experiments/{experiment_id}")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_experiment: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def delete_experiment(self, experiment_id: str) -> None:
        """Delete an experiment.

        Calls ``DELETE /api/app/projects/{pid}/experiments/{id}``
        (no trailing slash).

        Args:
            experiment_id: Experiment UUID.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Experiment not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.delete_experiment("xyz-456")
            ```
        """
        path = self.maybe_scoped_path(f"experiments/{experiment_id}")
        self.app_request("DELETE", path)

    def launch_experiment(self, experiment_id: str) -> dict[str, Any]:
        """Launch an experiment (Draft → Active).

        Calls ``PUT /api/app/projects/{pid}/experiments/{id}/launch``
        (no trailing slash).

        Args:
            experiment_id: Experiment UUID.

        Returns:
            Dictionary representing the launched experiment.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid state transition (400) or not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                launched = client.launch_experiment("xyz-456")
            ```
        """
        path = self.maybe_scoped_path(f"experiments/{experiment_id}/launch")
        result = self.app_request("PUT", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from launch_experiment: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def conclude_experiment(
        self, experiment_id: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Conclude an experiment (Active → Concluded).

        Always sends a JSON body (empty ``{}`` if no params provided).
        Calls ``PUT /api/app/projects/{pid}/experiments/{id}/force_conclude``
        (no trailing slash).

        Args:
            experiment_id: Experiment UUID.
            body: Optional conclude parameters. Defaults to empty dict.

        Returns:
            Dictionary representing the concluded experiment.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid state transition (400) or not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                concluded = client.conclude_experiment("xyz-456")
            ```
        """
        path = self.maybe_scoped_path(f"experiments/{experiment_id}/force_conclude")
        result = self.app_request("PUT", path, json_body=body or {})
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from conclude_experiment: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def decide_experiment(
        self, experiment_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """Record an experiment decision (Concluded → Success/Fail).

        Calls ``PATCH /api/app/projects/{pid}/experiments/{id}/decide``
        (no trailing slash).

        Args:
            experiment_id: Experiment UUID.
            body: Decision payload with ``success`` required.

        Returns:
            Dictionary representing the decided experiment.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid state transition (400) or not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                decided = client.decide_experiment("xyz-456", {"success": True})
            ```
        """
        path = self.maybe_scoped_path(f"experiments/{experiment_id}/decide")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from decide_experiment: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def archive_experiment(self, experiment_id: str) -> None:
        """Archive an experiment.

        Calls ``POST /api/app/projects/{pid}/experiments/{id}/archive``
        (no trailing slash).

        Args:
            experiment_id: Experiment UUID.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Experiment not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.archive_experiment("xyz-456")
            ```
        """
        path = self.maybe_scoped_path(f"experiments/{experiment_id}/archive")
        self.app_request("POST", path)

    def restore_experiment(self, experiment_id: str) -> dict[str, Any]:
        """Restore an archived experiment.

        Calls ``DELETE /api/app/projects/{pid}/experiments/{id}/archive``
        (no trailing slash).

        Args:
            experiment_id: Experiment UUID.

        Returns:
            Dictionary representing the restored experiment.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Experiment not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                exp = client.restore_experiment("xyz-456")
            ```
        """
        path = self.maybe_scoped_path(f"experiments/{experiment_id}/archive")
        result = self.app_request("DELETE", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from restore_experiment: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def duplicate_experiment(
        self, experiment_id: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Duplicate an experiment.

        Calls ``POST /api/app/projects/{pid}/experiments/{id}/duplicate``
        (no trailing slash).

        Args:
            experiment_id: Experiment UUID.
            body: Optional duplication parameters (e.g. new name).

        Returns:
            Dictionary representing the duplicated experiment.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Experiment not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                dup = client.duplicate_experiment("xyz-456", {"name": "Copy"})
            ```
        """
        path = self.maybe_scoped_path(f"experiments/{experiment_id}/duplicate")
        result = self.app_request("POST", path, json_body=body if body else None)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from duplicate_experiment: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def list_erf_experiments(self) -> list[dict[str, Any]]:
        """List experiments in ERF (Experiment Results Framework) format.

        Calls ``GET /api/app/projects/{pid}/experiments/erf/``
        (optionally workspace-scoped).

        Returns:
            List of experiment dictionaries in ERF format.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                erf = client.list_erf_experiments()
            ```
        """
        path = self.maybe_scoped_path("experiments/erf/")
        result = self.app_request("GET", path)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_erf_experiments: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    # =========================================================================
    # Annotations (Phase 026)
    # =========================================================================

    def list_annotations(
        self,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        tags: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """List timeline annotations for the project.

        Calls ``GET /api/app/projects/{pid}/annotations/``
        (optionally workspace-scoped).

        Args:
            from_date: Start date filter (ISO format, e.g. ``"2026-01-01"``).
            to_date: End date filter (ISO format, e.g. ``"2026-03-31"``).
            tags: Tag IDs to filter by.

        Returns:
            List of annotation dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                annotations = client.list_annotations(from_date="2026-01-01")
            ```
        """
        path = self.maybe_scoped_path("annotations/")
        params: dict[str, str] = {}
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        if tags:
            params["tags"] = ",".join(str(t) for t in tags)
        result = self.app_request("GET", path, params=params if params else None)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_annotations: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def create_annotation(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a new timeline annotation.

        Calls ``POST /api/app/projects/{pid}/annotations/``
        (optionally workspace-scoped).

        Args:
            body: Annotation data (date, description, optional tags/user_id).

        Returns:
            Dictionary representing the created annotation.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                ann = client.create_annotation(
                    {"date": "2026-03-31", "description": "v2.5 release"}
                )
            ```
        """
        path = self.maybe_scoped_path("annotations/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_annotation: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def get_annotation(self, annotation_id: int) -> dict[str, Any]:
        """Get a single annotation by ID.

        Calls ``GET /api/app/projects/{pid}/annotations/{id}/``
        (optionally workspace-scoped).

        Args:
            annotation_id: Annotation ID.

        Returns:
            Dictionary representing the annotation.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Annotation not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                ann = client.get_annotation(42)
            ```
        """
        path = self.maybe_scoped_path(f"annotations/{annotation_id}/")
        result = self.app_request("GET", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_annotation: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_annotation(
        self, annotation_id: int, body: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an annotation (PATCH semantics).

        Calls ``PATCH /api/app/projects/{pid}/annotations/{id}/``
        (optionally workspace-scoped).

        Args:
            annotation_id: Annotation ID.
            body: Fields to update (description, tags).

        Returns:
            Dictionary representing the updated annotation.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Annotation not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                ann = client.update_annotation(42, {"description": "Updated"})
            ```
        """
        path = self.maybe_scoped_path(f"annotations/{annotation_id}/")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_annotation: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def delete_annotation(self, annotation_id: int) -> None:
        """Delete an annotation.

        Calls ``DELETE /api/app/projects/{pid}/annotations/{id}/``
        (optionally workspace-scoped).

        Args:
            annotation_id: Annotation ID.

        Returns:
            None.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Annotation not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.delete_annotation(42)
            ```
        """
        path = self.maybe_scoped_path(f"annotations/{annotation_id}/")
        self.app_request("DELETE", path)

    def list_annotation_tags(self) -> list[dict[str, Any]]:
        """List annotation tags for the project.

        Calls ``GET /api/app/projects/{pid}/annotations/tags/``
        (optionally workspace-scoped).

        Returns:
            List of annotation tag dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                tags = client.list_annotation_tags()
            ```
        """
        path = self.maybe_scoped_path("annotations/tags/")
        result = self.app_request("GET", path)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_annotation_tags: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def create_annotation_tag(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a new annotation tag.

        Calls ``POST /api/app/projects/{pid}/annotations/tags/``
        (optionally workspace-scoped).

        Args:
            body: Tag data (name).

        Returns:
            Dictionary representing the created tag.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                tag = client.create_annotation_tag({"name": "releases"})
            ```
        """
        path = self.maybe_scoped_path("annotations/tags/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_annotation_tag: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    # =========================================================================
    # Webhook CRUD (Phase 026)
    # =========================================================================

    def list_webhooks(self) -> list[dict[str, Any]]:
        """List all webhooks for the current project.

        Calls ``GET /api/app/projects/{pid}/webhooks/``
        (optionally workspace-scoped).

        Returns:
            List of webhook dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400, 404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                webhooks = client.list_webhooks()
            ```
        """
        path = self.maybe_scoped_path("webhooks/")
        result = self.app_request("GET", path)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_webhooks: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def create_webhook(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a new webhook.

        Calls ``POST /api/app/projects/{pid}/webhooks/``
        (optionally workspace-scoped).

        Args:
            body: Webhook creation parameters (name, url, auth_type, etc.).

        Returns:
            Dictionary with the created webhook's id and name.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                result = client.create_webhook({"name": "My Hook", "url": "https://..."})
            ```
        """
        path = self.maybe_scoped_path("webhooks/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_webhook: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_webhook(self, webhook_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Update an existing webhook.

        Calls ``PATCH /api/app/projects/{pid}/webhooks/{webhook_id}/``
        (optionally workspace-scoped).

        Args:
            webhook_id: Webhook UUID string.
            body: Fields to update.

        Returns:
            Dictionary with the updated webhook's id and name.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Webhook not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                result = client.update_webhook("wh-uuid", {"name": "Renamed"})
            ```
        """
        path = self.maybe_scoped_path(f"webhooks/{webhook_id}/")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_webhook: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook.

        Calls ``DELETE /api/app/projects/{pid}/webhooks/{webhook_id}/``
        (optionally workspace-scoped).

        Args:
            webhook_id: Webhook UUID string.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Webhook not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.delete_webhook("wh-uuid")
            ```
        """
        path = self.maybe_scoped_path(f"webhooks/{webhook_id}/")
        self.app_request("DELETE", path)

    def test_webhook(self, body: dict[str, Any]) -> dict[str, Any]:
        """Test webhook connectivity.

        Calls ``POST /api/app/projects/{pid}/webhooks/test/``
        (optionally workspace-scoped).

        Args:
            body: Webhook test parameters (url, auth_type, etc.).

        Returns:
            Dictionary with test results (success, status_code, message).

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                result = client.test_webhook({"url": "https://example.com/hook"})
            ```
        """
        path = self.maybe_scoped_path("webhooks/test/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from test_webhook: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    # =========================================================================
    # Alert CRUD (Phase 026)
    # =========================================================================

    def list_alerts(
        self,
        *,
        bookmark_id: int | None = None,
        skip_user_filter: bool | None = None,
    ) -> list[dict[str, Any]]:
        """List custom alerts for the current project.

        Calls ``GET /api/app/projects/{pid}/alerts/custom/``
        (optionally workspace-scoped).

        Args:
            bookmark_id: Filter alerts by linked bookmark ID.
            skip_user_filter: If True, list alerts for all users.

        Returns:
            List of alert dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                alerts = client.list_alerts()
            ```
        """
        path = self.maybe_scoped_path("alerts/custom/")
        params: dict[str, str] = {}
        if bookmark_id is not None:
            params["bookmark_id"] = str(bookmark_id)
        if skip_user_filter is not None:
            params["skip_user_filter"] = str(skip_user_filter).lower()
        result = self.app_request("GET", path, params=params if params else None)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_alerts: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def create_alert(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a new custom alert.

        Calls ``POST /api/app/projects/{pid}/alerts/custom/``
        (optionally workspace-scoped).

        Args:
            body: Alert creation parameters (name, condition, frequency, etc.).

        Returns:
            Dictionary representing the created alert.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                alert = client.create_alert({"name": "Drop", "frequency": 86400})
            ```
        """
        path = self.maybe_scoped_path("alerts/custom/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_alert: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def get_alert(self, alert_id: int) -> dict[str, Any]:
        """Get a single custom alert by ID.

        Calls ``GET /api/app/projects/{pid}/alerts/custom/{alert_id}/``
        (optionally workspace-scoped).

        Args:
            alert_id: Alert ID (integer).

        Returns:
            Dictionary representing the alert.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Alert not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                alert = client.get_alert(42)
            ```
        """
        path = self.maybe_scoped_path(f"alerts/custom/{alert_id}/")
        result = self.app_request("GET", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_alert: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_alert(self, alert_id: int, body: dict[str, Any]) -> dict[str, Any]:
        """Update a custom alert (PATCH semantics).

        Calls ``PATCH /api/app/projects/{pid}/alerts/custom/{alert_id}/``
        (optionally workspace-scoped).

        Args:
            alert_id: Alert ID (integer).
            body: Fields to update.

        Returns:
            Dictionary representing the updated alert.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Alert not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.update_alert(42, {"name": "Renamed"})
            ```
        """
        path = self.maybe_scoped_path(f"alerts/custom/{alert_id}/")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_alert: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def delete_alert(self, alert_id: int) -> None:
        """Delete a custom alert.

        Calls ``DELETE /api/app/projects/{pid}/alerts/custom/{alert_id}/``
        (optionally workspace-scoped).

        Args:
            alert_id: Alert ID (integer).

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Alert not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.delete_alert(42)
            ```
        """
        path = self.maybe_scoped_path(f"alerts/custom/{alert_id}/")
        self.app_request("DELETE", path)

    def bulk_delete_alerts(self, ids: list[int]) -> None:
        """Bulk-delete custom alerts.

        Calls ``POST /api/app/projects/{pid}/alerts/custom/bulk-delete/``
        (optionally workspace-scoped).

        Args:
            ids: List of alert IDs to delete.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.bulk_delete_alerts([1, 2, 3])
            ```
        """
        path = self.maybe_scoped_path("alerts/custom/bulk-delete/")
        self.app_request("POST", path, json_body={"alert_ids": ids})

    def get_alert_count(self, *, alert_type: str | None = None) -> dict[str, Any]:
        """Get alert count and limits.

        Calls ``GET /api/app/projects/{pid}/alerts/custom/alert-count/``
        (optionally workspace-scoped).

        Args:
            alert_type: Optional filter by alert type.

        Returns:
            Dictionary with count and limit info.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                count = client.get_alert_count()
            ```
        """
        path = self.maybe_scoped_path("alerts/custom/alert-count/")
        params: dict[str, str] = {}
        if alert_type is not None:
            params["type"] = alert_type
        result = self.app_request("GET", path, params=params if params else None)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_alert_count: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def get_alert_history(
        self,
        alert_id: int,
        *,
        page_size: int | None = None,
        next_cursor: str | None = None,
        previous_cursor: str | None = None,
    ) -> dict[str, Any]:
        """Get alert trigger history (paginated).

        Calls ``GET /api/app/projects/{pid}/alerts/custom/{alert_id}/history/``
        (optionally workspace-scoped). Uses ``_raw=True`` to preserve
        pagination metadata alongside results.

        Args:
            alert_id: Alert ID (integer).
            page_size: Number of results per page.
            next_cursor: Cursor for the next page.
            previous_cursor: Cursor for the previous page.

        Returns:
            Dictionary with ``results`` list and ``pagination`` metadata.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Alert not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                history = client.get_alert_history(42, page_size=10)
            ```
        """
        path = self.maybe_scoped_path(f"alerts/custom/{alert_id}/history/")
        params: dict[str, str] = {}
        if page_size is not None:
            params["page_size"] = str(page_size)
        if next_cursor is not None:
            params["next_cursor"] = next_cursor
        if previous_cursor is not None:
            params["previous_cursor"] = previous_cursor
        result = self.app_request(
            "GET", path, params=params if params else None, _raw=True
        )
        if isinstance(result, dict):
            if "results" not in result:
                raise MixpanelDataError(
                    "Unexpected response from get_alert_history: "
                    "dict missing 'results' key",
                )
            inner = result["results"]
            if isinstance(inner, dict) and "results" in inner:
                if "pagination" not in inner:
                    inner["pagination"] = None
                return inner
            if isinstance(inner, list):
                return {"results": inner, "pagination": None}
        elif isinstance(result, list):
            return {"results": result, "pagination": None}

        raise MixpanelDataError(
            f"Unexpected response from get_alert_history: "
            f"got {type(result).__name__} without results list",
        )

    def test_alert(self, body: dict[str, Any]) -> dict[str, Any]:
        """Send a test alert notification.

        Calls ``POST /api/app/projects/{pid}/alerts/custom/test/``
        (optionally workspace-scoped).

        Args:
            body: Alert parameters for the test (same shape as create).

        Returns:
            Dictionary with test result status.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                result = client.test_alert({"name": "Test", "frequency": 86400})
            ```
        """
        path = self.maybe_scoped_path("alerts/custom/test/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from test_alert: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def get_alert_screenshot_url(self, gcs_key: str) -> dict[str, Any]:
        """Get a signed URL for an alert screenshot.

        Calls ``GET /api/app/projects/{pid}/alerts/custom/screenshot/``
        (optionally workspace-scoped).

        Args:
            gcs_key: GCS object key for the screenshot.

        Returns:
            Dictionary with ``signed_url`` field.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Screenshot not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                url = client.get_alert_screenshot_url("screenshots/abc.png")
            ```
        """
        path = self.maybe_scoped_path("alerts/custom/screenshot/")
        result = self.app_request("GET", path, params={"gcs_key": gcs_key})
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_alert_screenshot_url: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def validate_alerts_for_bookmark(self, body: dict[str, Any]) -> dict[str, Any]:
        """Validate alerts against a bookmark configuration.

        Calls ``POST /api/app/projects/{pid}/alerts/custom/validate-alerts-for-bookmark/``
        (optionally workspace-scoped).

        Args:
            body: Validation parameters (alert_ids, bookmark_type, bookmark_params).

        Returns:
            Dictionary with ``alert_validations`` list and ``invalid_count``.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                result = client.validate_alerts_for_bookmark({
                    "alert_ids": [1, 2],
                    "bookmark_type": "insights",
                    "bookmark_params": {"event": "Signup"},
                })
            ```
        """
        path = self.maybe_scoped_path("alerts/custom/validate-alerts-for-bookmark/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from validate_alerts_for_bookmark: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    # =========================================================================
    # Data Governance — Data Definitions / Lexicon (Phase 027)
    # =========================================================================

    def get_event_definitions(self, names: list[str]) -> list[dict[str, Any]]:
        """Get event definitions by name from the Lexicon.

        Calls ``GET /api/app/projects/{pid}/data-definitions/events/``
        (optionally workspace-scoped).

        Args:
            names: List of event names to look up.

        Returns:
            List of event definition dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400/404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                defs = client.get_event_definitions(["Signup", "Login"])
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/")
        params: dict[str, str | list[str]] = {"name[]": names}
        result = self.app_request("GET", path, params=params)  # type: ignore[arg-type]
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from get_event_definitions: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def update_event_definition(
        self, name: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an event definition in the Lexicon.

        Calls ``PATCH /api/app/projects/{pid}/data-definitions/events/``
        (optionally workspace-scoped).

        Args:
            name: Event name to update.
            body: Fields to update (description, hidden, dropped, tags, etc.).

        Returns:
            Dictionary representing the updated event definition.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400) or not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.update_event_definition(
                    "Signup", {"description": "User signs up"}
                )
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/")
        payload = {**body, "name": name}
        result = self.app_request("PATCH", path, json_body=payload)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_event_definition: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def delete_event_definition(self, name: str) -> None:
        """Delete an event definition from the Lexicon.

        Calls ``DELETE /api/app/projects/{pid}/data-definitions/events/``
        (optionally workspace-scoped).

        Args:
            name: Event name to delete.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Event not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.delete_event_definition("OldEvent")
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/")
        self.app_request("DELETE", path, json_body={"name": name})

    def bulk_update_event_definitions(
        self, body: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Bulk-update event definitions in the Lexicon.

        Calls ``PATCH /api/app/projects/{pid}/data-definitions/events/``
        (optionally workspace-scoped).

        Args:
            body: Dictionary with ``events`` key containing a list of
                event definition updates.

        Returns:
            List of updated event definition dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.bulk_update_event_definitions({
                    "events": [
                        {"event_name": "Signup", "description": "Sign up"},
                        {"event_name": "Login", "description": "Log in"},
                    ]
                })
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from bulk_update_event_definitions: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def get_property_definitions(
        self,
        names: list[str],
        resource_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get property definitions by name from the Lexicon.

        Calls ``GET /api/app/projects/{pid}/data-definitions/properties/``
        (optionally workspace-scoped).

        Args:
            names: List of property names to look up.
            resource_type: Optional resource type filter
                (e.g., ``"event"``, ``"user"``, ``"groupprofile"``).

        Returns:
            List of property definition dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400/404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                props = client.get_property_definitions(["plan", "country"])
            ```
        """
        path = self.maybe_scoped_path("data-definitions/properties/")
        params: dict[str, str | list[str]] = {"name[]": names}
        if resource_type is not None:
            params["resource_type"] = resource_type
        result = self.app_request("GET", path, params=params)  # type: ignore[arg-type]
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from get_property_definitions: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def update_property_definition(
        self, name: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a property definition in the Lexicon.

        Calls ``PATCH /api/app/projects/{pid}/data-definitions/properties/``
        (optionally workspace-scoped).

        Args:
            name: Property name to update.
            body: Fields to update (description, hidden, dropped, tags, etc.).

        Returns:
            Dictionary representing the updated property definition.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400) or not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.update_property_definition(
                    "plan", {"description": "Subscription plan"}
                )
            ```
        """
        path = self.maybe_scoped_path("data-definitions/properties/")
        payload = {**body, "name": name}
        result = self.app_request("PATCH", path, json_body=payload)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_property_definition: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def bulk_update_property_definitions(
        self, body: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Bulk-update property definitions in the Lexicon.

        Calls ``PATCH /api/app/projects/{pid}/data-definitions/properties/``
        (optionally workspace-scoped).

        Args:
            body: Dictionary with ``properties`` key containing a list of
                property definition updates.

        Returns:
            List of updated property definition dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.bulk_update_property_definitions({
                    "properties": [
                        {"property_name": "plan", "description": "Plan"},
                        {"property_name": "country", "description": "Country"},
                    ]
                })
            ```
        """
        path = self.maybe_scoped_path("data-definitions/properties/")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from bulk_update_property_definitions: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def list_lexicon_tags(self) -> list[dict[str, Any]]:
        """List all Lexicon tags for the project.

        Calls ``GET /api/app/projects/{pid}/data-definitions/tags/``
        (optionally workspace-scoped).

        Returns:
            List of tag dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                tags = client.list_lexicon_tags()
            ```
        """
        path = self.maybe_scoped_path("data-definitions/tags/")
        result = self.app_request("GET", path)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_lexicon_tags: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def create_lexicon_tag(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a new Lexicon tag.

        Calls ``POST /api/app/projects/{pid}/data-definitions/tags/``
        (optionally workspace-scoped).

        Args:
            body: Tag creation parameters (name).

        Returns:
            Dictionary representing the created tag.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                tag = client.create_lexicon_tag({"name": "Core Events"})
            ```
        """
        path = self.maybe_scoped_path("data-definitions/tags/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_lexicon_tag: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_lexicon_tag(self, tag_id: int, body: dict[str, Any]) -> dict[str, Any]:
        """Update a Lexicon tag.

        Calls ``PATCH /api/app/projects/{pid}/data-definitions/tags/{tag_id}/``
        (optionally workspace-scoped).

        Args:
            tag_id: Tag ID (integer).
            body: Fields to update (name).

        Returns:
            Dictionary representing the updated tag.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Tag not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.update_lexicon_tag(1, {"name": "Renamed"})
            ```
        """
        path = self.maybe_scoped_path(f"data-definitions/tags/{tag_id}/")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_lexicon_tag: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def delete_lexicon_tag(self, name: str) -> None:
        """Delete a Lexicon tag by name.

        Uses ``POST /api/app/projects/{pid}/data-definitions/tags/``
        with ``delete: True`` (the API uses POST, not DELETE, for tag removal).

        Args:
            name: Name of the tag to delete.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Tag not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.delete_lexicon_tag("Old Tag")
            ```
        """
        path = self.maybe_scoped_path("data-definitions/tags/")
        self.app_request("POST", path, json_body={"delete": True, "name": name})

    def get_tracking_metadata(self, event_name: str) -> dict[str, Any]:
        """Get tracking metadata for an event.

        Calls ``GET /api/app/projects/{pid}/data-definitions/events/tracking-metadata/``
        (optionally workspace-scoped).

        Args:
            event_name: Name of the event.

        Returns:
            Dictionary with tracking metadata (volumes, first/last seen, etc.).

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Event not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                meta = client.get_tracking_metadata("Signup")
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/tracking-metadata/")
        result = self.app_request("GET", path, params={"event_name": event_name})
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_tracking_metadata: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def get_event_history(self, event_name: str) -> list[dict[str, Any]]:
        """Get change history for an event definition.

        Calls ``GET /api/app/projects/{pid}/data-definitions/events/{event_name}/history/``
        (optionally workspace-scoped).

        Args:
            event_name: Name of the event.

        Returns:
            List of history entry dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Event not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                history = client.get_event_history("Signup")
            ```
        """
        path = self.maybe_scoped_path(
            f"data-definitions/events/{quote(event_name, safe='')}/history/"
        )
        result = self.app_request("GET", path)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from get_event_history: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def get_property_history(
        self, property_name: str, entity_type: str
    ) -> list[dict[str, Any]]:
        """Get change history for a property definition.

        Calls ``GET /api/app/projects/{pid}/data-definitions/properties/{property_name}/history/``
        (optionally workspace-scoped).

        Args:
            property_name: Name of the property.
            entity_type: Entity type (e.g., ``"event"``, ``"user"``, ``"groupprofile"``).

        Returns:
            List of history entry dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Property not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                history = client.get_property_history("plan", "event")
            ```
        """
        path = self.maybe_scoped_path(
            f"data-definitions/properties/{quote(property_name, safe='')}/history/"
        )
        result = self.app_request("GET", path, params={"entity_type": entity_type})
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from get_property_history: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def export_lexicon(self, export_types: list[str] | None = None) -> dict[str, Any]:
        """Export Lexicon data definitions.

        Calls ``GET /api/app/projects/{pid}/data-definitions/export/``
        (optionally workspace-scoped).

        Args:
            export_types: Optional list of types to export. Valid values:
                ``"All Events and Properties"``,
                ``"All User Profile Properties"``.

        Returns:
            Dictionary containing exported definitions.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                export = client.export_lexicon(
                    ["All Events and Properties"]
                )
            ```
        """
        path = self.maybe_scoped_path("data-definitions/export/")
        _default_types = [
            "All Events and Properties",
            "All User Profile Properties",
        ]
        types_to_export = export_types if export_types is not None else _default_types
        params = {"export_type": json.dumps(types_to_export)}
        result = self.app_request("GET", path, params=params)
        if isinstance(result, str):
            # Async export — returns status message
            return {"status": "pending", "message": result}
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from export_lexicon: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    # =========================================================================
    # Data Governance — Drop Filters (Phase 027)
    # =========================================================================

    def list_drop_filters(self) -> list[dict[str, Any]]:
        """List all drop filters for the project.

        Calls ``GET /api/app/projects/{pid}/data-definitions/events/drop-filters/``
        (optionally workspace-scoped).

        Returns:
            List of drop filter dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                filters = client.list_drop_filters()
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/drop-filters/")
        result = self.app_request("GET", path)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_drop_filters: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def create_drop_filter(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        """Create a new drop filter.

        Calls ``POST /api/app/projects/{pid}/data-definitions/events/drop-filters/``
        (optionally workspace-scoped).

        Args:
            body: Drop filter creation parameters (event_name, filters, etc.).

        Returns:
            List of all drop filter dictionaries after creation.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                filters = client.create_drop_filter({
                    "event_name": "Noise", "query": {}
                })
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/drop-filters/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from create_drop_filter: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def update_drop_filter(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        """Update an existing drop filter.

        Calls ``PATCH /api/app/projects/{pid}/data-definitions/events/drop-filters/``
        (optionally workspace-scoped).

        Args:
            body: Drop filter update parameters (id, filters, etc.).

        Returns:
            List of all drop filter dictionaries after update.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400) or not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                filters = client.update_drop_filter({
                    "id": 1, "query": {"property": "bot"}
                })
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/drop-filters/")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from update_drop_filter: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def delete_drop_filter(self, drop_filter_id: int) -> list[dict[str, Any]]:
        """Delete a drop filter by ID.

        Calls ``DELETE /api/app/projects/{pid}/data-definitions/events/drop-filters/``
        (optionally workspace-scoped).

        Args:
            drop_filter_id: ID of the drop filter to delete.

        Returns:
            List of all drop filter dictionaries after deletion.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Drop filter not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                filters = client.delete_drop_filter(42)
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/drop-filters/")
        result = self.app_request("DELETE", path, json_body={"id": drop_filter_id})
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from delete_drop_filter: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def get_drop_filter_limits(self) -> dict[str, Any]:
        """Get drop filter usage limits for the project.

        Calls ``GET /api/app/projects/{pid}/data-definitions/events/drop-filters/limits/``
        (optionally workspace-scoped).

        Returns:
            Dictionary with limit information (max filters, current count, etc.).

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                limits = client.get_drop_filter_limits()
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/drop-filters/limits/")
        result = self.app_request("GET", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_drop_filter_limits: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    # =========================================================================
    # Data Governance — Custom Properties (Phase 027)
    # =========================================================================

    def list_custom_properties(self) -> list[dict[str, Any]]:
        """List all custom properties for the project.

        Calls ``GET /api/app/projects/{pid}/custom_properties/``
        (optionally workspace-scoped).

        Returns:
            List of custom property dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                props = client.list_custom_properties()
            ```
        """
        path = self.maybe_scoped_path("custom_properties/")
        result = self.app_request("GET", path)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_custom_properties: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def create_custom_property(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a new custom property.

        Calls ``POST /api/app/projects/{pid}/custom_properties/``
        (optionally workspace-scoped).

        Args:
            body: Custom property definition (name, expression, type, etc.).

        Returns:
            Dictionary representing the created custom property.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                prop = client.create_custom_property({
                    "name": "Is Paying",
                    "expression": "...",
                })
            ```
        """
        path = self.maybe_scoped_path("custom_properties/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_custom_property: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def get_custom_property(self, property_id: str) -> dict[str, Any]:
        """Get a single custom property by ID.

        Calls ``GET /api/app/projects/{pid}/custom_properties/{property_id}/``
        (optionally workspace-scoped).

        Args:
            property_id: Custom property ID (string).

        Returns:
            Dictionary representing the custom property.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Property not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                prop = client.get_custom_property("abc-123")
            ```
        """
        path = self.maybe_scoped_path(f"custom_properties/{property_id}/")
        result = self.app_request("GET", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_custom_property: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_custom_property(
        self, property_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a custom property (full replacement).

        Calls ``PUT /api/app/projects/{pid}/custom_properties/{property_id}/``
        (optionally workspace-scoped). Uses PUT (full replacement), not PATCH.

        Args:
            property_id: Custom property ID (string).
            body: Full custom property definition to replace.

        Returns:
            Dictionary representing the updated custom property.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Property not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.update_custom_property(
                    "abc-123", {"name": "Is Paying", "expression": "..."}
                )
            ```
        """
        path = self.maybe_scoped_path(f"custom_properties/{property_id}/")
        result = self.app_request("PUT", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_custom_property: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def delete_custom_property(self, property_id: str) -> None:
        """Delete a custom property.

        Calls ``DELETE /api/app/projects/{pid}/custom_properties/{property_id}/``
        (optionally workspace-scoped).

        Args:
            property_id: Custom property ID (string).

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Property not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.delete_custom_property("abc-123")
            ```
        """
        path = self.maybe_scoped_path(f"custom_properties/{property_id}/")
        self.app_request("DELETE", path)

    def validate_custom_property(self, body: dict[str, Any]) -> dict[str, Any]:
        """Validate a custom property expression without creating it.

        Calls ``POST /api/app/projects/{pid}/custom_properties/validate/``
        (optionally workspace-scoped).

        Args:
            body: Custom property definition to validate.

        Returns:
            Dictionary with validation result (valid, errors, etc.).

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                result = client.validate_custom_property({
                    "name": "Is Paying",
                    "expression": "...",
                })
            ```
        """
        path = self.maybe_scoped_path("custom_properties/validate/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from validate_custom_property: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    # =========================================================================
    # Data Governance — Lookup Tables (Phase 027)
    # =========================================================================

    def list_lookup_tables(
        self, *, data_group_id: int | None = None
    ) -> list[dict[str, Any]]:
        """List lookup tables for the project.

        Calls ``GET /api/app/projects/{pid}/data-definitions/lookup-tables/``
        (optionally workspace-scoped).

        Args:
            data_group_id: Optional filter by data group ID.

        Returns:
            List of lookup table dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                tables = client.list_lookup_tables()
            ```
        """
        path = self.maybe_scoped_path("data-definitions/lookup-tables/")
        params: dict[str, str] = {}
        if data_group_id is not None:
            params["data-group-id"] = str(data_group_id)
        result = self.app_request("GET", path, params=params if params else None)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_lookup_tables: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def get_lookup_upload_url(self, content_type: str = "text/csv") -> dict[str, Any]:
        """Get a signed upload URL for lookup table CSV data.

        Calls ``GET /api/app/projects/{pid}/data-definitions/lookup-tables/upload-url/``
        (optionally workspace-scoped).

        Args:
            content_type: MIME type of the upload (default ``"text/csv"``).

        Returns:
            Dictionary with ``url``, ``path``, and ``key`` fields.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors or missing fields.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                info = client.get_lookup_upload_url()
                # info["url"], info["path"], info["key"]
            ```
        """
        path = self.maybe_scoped_path("data-definitions/lookup-tables/upload-url/")
        result = self.app_request("GET", path, params={"content-type": content_type})
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_lookup_upload_url: "
                f"expected dict, got {type(result).__name__}",
            )
        for required_key in ("url", "path", "key"):
            if required_key not in result:
                raise MixpanelDataError(
                    f"get_lookup_upload_url response missing required "
                    f"field '{required_key}': {result}",
                    code="MISSING_FIELD",
                )
        return result

    def upload_to_signed_url(self, url: str, csv_bytes: bytes) -> None:
        """Upload CSV data to a signed GCS URL.

        Performs a direct ``PUT`` to the external signed URL (no Mixpanel auth).
        Uses a fresh HTTP client to avoid sending default headers
        (e.g., custom headers from ``MP_CUSTOM_HEADER_*`` env vars) that
        would invalidate the GCS signature.

        Args:
            url: Signed upload URL (from ``get_lookup_upload_url()``).
            csv_bytes: Raw CSV content as bytes.

        Raises:
            MixpanelDataError: Upload failed (non-2xx response).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                info = client.get_lookup_upload_url()
                client.upload_to_signed_url(info["url"], b"id,name\\n1,foo")
            ```
        """
        # Use a clean client without default headers — the shared client
        # may have custom headers (via MP_CUSTOM_HEADER_* env vars) that
        # GCS includes in signature validation, causing
        # SignatureDoesNotMatch errors.
        if self._transport is not None:
            # Test mode: use the mock transport
            upload_client = httpx.Client(
                transport=self._transport, timeout=self._timeout
            )
        else:
            upload_client = httpx.Client(timeout=self._timeout)
        try:
            response = upload_client.put(
                url,
                content=csv_bytes,
                headers={"Content-Type": "text/csv"},
            )
        except httpx.HTTPError as e:
            raise MixpanelDataError(
                f"Upload to signed URL failed: {e}",
                code="UPLOAD_ERROR",
                details={"url": url},
            ) from e
        finally:
            upload_client.close()
        if response.status_code >= 300:
            raise MixpanelDataError(
                f"Upload to signed URL failed with status "
                f"{response.status_code}: {response.text[:500]}",
                code="UPLOAD_ERROR",
                details={
                    "status_code": response.status_code,
                    "url": url,
                },
            )

    def register_lookup_table(self, form_data: dict[str, str]) -> dict[str, Any]:
        """Register a lookup table with form-encoded data.

        Calls ``POST /api/app/projects/{pid}/data-definitions/lookup-tables/``
        (optionally workspace-scoped) with form-encoded body.

        Args:
            form_data: Form fields for table registration
                (name, path, key, and optionally data-group-id).

        Returns:
            Dictionary representing the registered lookup table.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                table = client.register_lookup_table({
                    "name": "Plans",
                    "path": "gs://bucket/path",
                    "key": "id",
                })
            ```
        """
        path = self.maybe_scoped_path("data-definitions/lookup-tables/")
        url = self._build_url("app", path)
        auth_header = self._get_auth_header()
        client = self._ensure_client()
        response = client.request(
            "POST",
            url,
            data=form_data,
            headers=self._request_headers({"Authorization": auth_header}),
            timeout=self._timeout,
        )
        if response.status_code >= 400:
            self._handle_response(
                response,
                request_method="POST",
                request_url=url,
                request_params=None,
                request_body=form_data,
            )
        try:
            body: Any = response.json()
        except json.JSONDecodeError as e:
            raise MixpanelDataError(
                f"register_lookup_table returned non-JSON response "
                f"(status {response.status_code}): {response.text[:500]}",
                code="INVALID_RESPONSE",
            ) from e
        if isinstance(body, dict) and "results" in body:
            body = body["results"]
        if not isinstance(body, dict):
            raise MixpanelDataError(
                f"Unexpected response from register_lookup_table: "
                f"expected dict, got {type(body).__name__}",
            )
        return body

    def mark_lookup_table_ready(self, form_data: dict[str, str]) -> dict[str, Any]:
        """Mark a lookup table upload as ready with form-encoded data.

        Uses the same endpoint as ``register_lookup_table()`` — calls
        ``POST /api/app/projects/{pid}/data-definitions/lookup-tables/``
        with form-encoded body containing the ``ready`` flag.

        Args:
            form_data: Form fields including ready status and upload metadata.

        Returns:
            Dictionary representing the lookup table status.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                result = client.mark_lookup_table_ready({
                    "upload_id": "abc-123",
                    "ready": "true",
                })
            ```
        """
        return self.register_lookup_table(form_data)

    def get_lookup_upload_status(self, upload_id: str) -> dict[str, Any]:
        """Get the upload status for a lookup table upload.

        Calls ``GET /api/app/projects/{pid}/data-definitions/lookup-tables/upload-status/``
        (optionally workspace-scoped).

        Args:
            upload_id: Upload ID (from ``get_lookup_upload_url()``).

        Returns:
            Dictionary with upload status information.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Upload not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                status = client.get_lookup_upload_status("abc-123")
            ```
        """
        path = self.maybe_scoped_path("data-definitions/lookup-tables/upload-status/")
        result = self.app_request("GET", path, params={"upload-id": upload_id})
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_lookup_upload_status: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_lookup_table(
        self, data_group_id: int, body: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a lookup table's metadata.

        Calls ``PATCH /api/app/projects/{pid}/data-definitions/lookup-tables/``
        (optionally workspace-scoped).

        Args:
            data_group_id: Data group ID of the lookup table.
            body: Fields to update (name, description, etc.).

        Returns:
            Dictionary representing the updated lookup table.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Table not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.update_lookup_table(
                    42, {"name": "Renamed Table"}
                )
            ```
        """
        path = self.maybe_scoped_path("data-definitions/lookup-tables/")
        payload = {**body, "data-group-id": data_group_id}
        result = self.app_request("PATCH", path, json_body=payload)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_lookup_table: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def delete_lookup_tables(self, data_group_ids: list[int]) -> None:
        """Delete one or more lookup tables.

        Calls ``DELETE /api/app/projects/{pid}/data-definitions/lookup-tables/``
        (optionally workspace-scoped).

        Args:
            data_group_ids: List of data group IDs to delete.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Table(s) not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.delete_lookup_tables([1, 2, 3])
            ```
        """
        path = self.maybe_scoped_path("data-definitions/lookup-tables/")
        self.app_request("DELETE", path, json_body={"data-group-ids": data_group_ids})

    def download_lookup_table(
        self,
        data_group_id: int,
        *,
        file_name: str | None = None,
        limit: int | None = None,
    ) -> bytes:
        """Download lookup table data as CSV bytes.

        Calls ``GET /api/app/projects/{pid}/data-definitions/lookup-tables/download/``
        (optionally workspace-scoped). Returns raw bytes (not JSON).

        Args:
            data_group_id: Data group ID of the lookup table.
            file_name: Optional file name filter.
            limit: Optional row limit.

        Returns:
            Raw CSV content as bytes.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Table not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                csv_data = client.download_lookup_table(42)
                with open("table.csv", "wb") as f:
                    f.write(csv_data)
            ```
        """
        path = self.maybe_scoped_path("data-definitions/lookup-tables/download/")
        url = self._build_url("app", path)
        auth_header = self._get_auth_header()
        client = self._ensure_client()
        params: dict[str, str] = {
            "data-group-id": str(data_group_id),
        }
        if file_name is not None:
            params["file-name"] = file_name
        if limit is not None:
            params["limit"] = str(limit)
        response = client.request(
            "GET",
            url,
            params=params,
            headers=self._request_headers({"Authorization": auth_header}),
            timeout=self._timeout,
        )
        if response.status_code >= 400:
            # Delegate error handling
            self._handle_response(
                response,
                request_method="GET",
                request_url=url,
                request_params=params,
                request_body=None,
            )
        return response.content

    def get_lookup_download_url(self, data_group_id: int) -> str:
        """Get a download URL for lookup table data.

        Calls ``GET /api/app/projects/{pid}/data-definitions/lookup-tables/download-url/``
        (optionally workspace-scoped).

        Args:
            data_group_id: Data group ID of the lookup table.

        Returns:
            Signed download URL string.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Table not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                url = client.get_lookup_download_url(42)
            ```
        """
        path = self.maybe_scoped_path("data-definitions/lookup-tables/download-url/")
        result = self.app_request(
            "GET",
            path,
            params={"data-group-id": str(data_group_id)},
        )
        if isinstance(result, dict):
            # Extract URL from response dict
            url = result.get("url") or result.get("download_url", "")
            if isinstance(url, str) and url:
                return url
            raise MixpanelDataError(
                "No download URL found in response",
                code="MISSING_URL",
                details={"response": result},
            )
        if isinstance(result, str):
            return result
        raise MixpanelDataError(
            f"Unexpected response from get_lookup_download_url: "
            f"expected dict or str, got {type(result).__name__}",
        )

    # =============================================================================
    # Data Governance — Custom Events (Phase 027)
    # =============================================================================

    def create_custom_event(self, body: dict[str, str]) -> dict[str, Any]:
        """Create a new custom event.

        Calls ``POST /api/app/projects/{pid}/custom_events/`` (optionally
        workspace-scoped) with a form-encoded body via :meth:`app_request`,
        so it inherits the same 429 retry, ``httpx.HTTPError`` wrapping, and
        error mapping as JSON callsites. Unwraps the ``{custom_event: ...}``
        envelope before returning the inner custom event dict.

        Args:
            body: Form-encoded fields. Must include ``name`` (the custom
                event display name) and ``alternatives`` (a JSON-encoded
                list of ``{"event": <name>}`` dicts naming the underlying
                events to alias).

        Returns:
            Dictionary representing the created custom event (``id``,
            ``name``, ``alternatives``, plus any server-side fields).

        Raises:
            AuthenticationError: Invalid credentials (401).
            RateLimitError: Rate limit exceeded after max retries (429).
            QueryError: Validation error (400, 422) — for example, duplicate
                custom event name or unknown underlying event.
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network failure or unexpected response shape.

        Example:
            ```python
            with MixpanelAPIClient(creds) as client:
                ce = client.create_custom_event({
                    "name": "Page View",
                    "alternatives": '[{"event": "Home Viewed"}]',
                })
            ```
        """
        path = self.maybe_scoped_path("custom_events/")
        payload: Any = self.app_request("POST", path, form_body=body)
        # The /custom_events/ endpoint nests the entity under {custom_event: ...}
        # inside the standard {results: ...} envelope that app_request already
        # unwrapped — peel the inner wrapper here.
        if isinstance(payload, dict) and "custom_event" in payload:
            payload = payload["custom_event"]
        if not isinstance(payload, dict):
            raise MixpanelDataError(
                f"Unexpected response from create_custom_event: "
                f"expected dict, got {type(payload).__name__}",
            )
        return payload

    def list_custom_events(self) -> list[dict[str, Any]]:
        """List custom events for the current project.

        Calls ``GET /api/app/projects/{pid}/data-definitions/events/``
        with a filter for custom events (optionally workspace-scoped).

        Returns:
            List of custom event definition dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                events = client.list_custom_events()
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/")
        result = self.app_request("GET", path, params={"custom_event": "true"})
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_custom_events: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def update_custom_event(
        self, custom_event_id: int, body: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a custom event's lexicon entry.

        Calls ``PATCH /api/app/projects/{pid}/data-definitions/events/``
        (optionally workspace-scoped). The endpoint matches the entry to
        update by the most specific identifier in the body; for custom
        events that's ``customEventId``. Sending only ``name`` would create
        an orphan lexicon entry rather than updating the existing one.

        Args:
            custom_event_id: Server-assigned custom event ID (the
                ``custom_event_id`` field on a custom event's lexicon entry,
                or the ``id`` field on the ``CustomEvent`` returned by
                :meth:`create_custom_event`).
            body: Fields to update. See
                :class:`mixpanel_data.types.UpdateEventDefinitionParams`
                for the full list of supported fields.

        Returns:
            Dictionary representing the updated lexicon entry.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Event not found (404) or validation error (400, 422).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors, or the server
                returned an entry with a different ``customEventId`` than
                the one requested (``code="UPDATE_TARGET_MISMATCH"``) —
                indicates the lexicon entry may have been created instead
                of updated.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                updated = client.update_custom_event(
                    42, {"hidden": True}
                )
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/")
        payload = {**body, "customEventId": custom_event_id}
        result = self.app_request("PATCH", path, json_body=payload)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_custom_event: "
                f"expected dict, got {type(result).__name__}",
            )
        # Defense-in-depth: the data-definitions endpoint has a known
        # silent-write history (responding 200 with a freshly-created entry
        # when given the wrong identifier). If the server echoes back a
        # different customEventId than we requested, treat it as a failure
        # rather than silently returning an unrelated entity.
        returned_id = result.get("customEventId")
        if returned_id is not None and returned_id != custom_event_id:
            raise MixpanelDataError(
                f"update_custom_event: server returned customEventId="
                f"{returned_id!r} but {custom_event_id} was requested. "
                f"The lexicon entry may have been created instead of "
                f"updated.",
                code="UPDATE_TARGET_MISMATCH",
            )
        return result

    def delete_custom_event(self, custom_event_id: int) -> None:
        """Delete a custom event definition.

        Calls ``DELETE /api/app/projects/{pid}/data-definitions/events/``
        (optionally workspace-scoped). Identifies the entry by
        ``customEventId`` (not name) for the same reason
        :meth:`update_custom_event` does: the data-definitions endpoint
        matches by the most specific identifier, and a name-only DELETE
        is ambiguous when multiple entries share a display name (it may
        delete the wrong row, an auto-derived orphan, or no-op silently
        while reporting success).

        Args:
            custom_event_id: Server-assigned custom event ID (the
                ``custom_event_id`` field on a custom event's lexicon entry,
                or the ``id`` field on the ``CustomEvent`` returned by
                :meth:`create_custom_event`).

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Event not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors.

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                client.delete_custom_event(42)
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/")
        self.app_request("DELETE", path, json_body={"customEventId": custom_event_id})

    # =========================================================================
    # Schema Enforcement (Phase 028)
    # =========================================================================

    def get_schema_enforcement(
        self,
        *,
        fields: str | None = None,
    ) -> dict[str, Any]:
        """Get current schema enforcement configuration.

        Calls ``GET /api/app/.../data-definitions/schema/``.

        Args:
            fields: Comma-separated field names to return (e.g.,
                "ruleEvent,state"). If None, returns all fields.

        Returns:
            Enforcement configuration dict.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: No enforcement configured (404).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                config = client.get_schema_enforcement()
            ```
        """
        path = self.maybe_scoped_path("data-definitions/schema/")
        params: dict[str, str] | None = None
        if fields is not None:
            params = {"fields": fields}
        result = self.app_request("GET", path, params=params)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_schema_enforcement: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def init_schema_enforcement(
        self,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Initialize schema enforcement.

        Calls ``POST /api/app/.../data-definitions/schema/``.

        Args:
            body: Init payload from
                ``InitSchemaEnforcementParams.model_dump()``.

        Returns:
            Raw API response as dict.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Already initialized or invalid rule_event (400).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                result = client.init_schema_enforcement(
                    {"ruleEvent": "Warn and Accept"}
                )
            ```
        """
        path = self.maybe_scoped_path("data-definitions/schema/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from init_schema_enforcement: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def update_schema_enforcement(
        self,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Partially update enforcement configuration.

        Calls ``PATCH /api/app/.../data-definitions/schema/``.

        Args:
            body: Partial update payload from
                ``UpdateSchemaEnforcementParams.model_dump()``.

        Returns:
            Raw API response as dict.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: No enforcement configured or validation error (400).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                result = client.update_schema_enforcement(
                    {"ruleEvent": "Warn and Drop"}
                )
            ```
        """
        path = self.maybe_scoped_path("data-definitions/schema/")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_schema_enforcement: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def replace_schema_enforcement(
        self,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Fully replace enforcement configuration.

        Calls ``PUT /api/app/.../data-definitions/schema/``.

        Args:
            body: Complete replacement payload from
                ``ReplaceSchemaEnforcementParams.model_dump()``.

        Returns:
            Raw API response as dict.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                result = client.replace_schema_enforcement({...})
            ```
        """
        path = self.maybe_scoped_path("data-definitions/schema/")
        result = self.app_request("PUT", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from replace_schema_enforcement: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def delete_schema_enforcement(self) -> dict[str, Any]:
        """Delete enforcement configuration.

        Calls ``DELETE /api/app/.../data-definitions/schema/``.

        Returns:
            Raw API response as dict.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: No enforcement configured (404).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                result = client.delete_schema_enforcement()
            ```
        """
        path = self.maybe_scoped_path("data-definitions/schema/")
        result = self.app_request("DELETE", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from delete_schema_enforcement: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    # =========================================================================
    # Data Auditing (Phase 028)
    # =========================================================================

    def run_audit(self) -> list[Any]:
        """Run a full data audit (events + properties).

        Calls ``GET /api/app/.../data-definitions/audit/``.
        Uses ``_raw=True`` because the response is a 2-element array:
        ``[violations_list, metadata_dict]``.

        Returns:
            Raw 2-element array: ``[violations, {"computed_at": ...}]``.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: No schemas defined (400).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                raw = client.run_audit()
                violations, metadata = raw[0], raw[1]
            ```
        """
        path = self.maybe_scoped_path("data-definitions/audit/")
        result = self.app_request("GET", path, _raw=True)
        # The response has {"status": "ok", "results": [violations, metadata]}
        if isinstance(result, dict) and "results" in result:
            inner = result["results"]
            if not isinstance(inner, list):
                raise MixpanelDataError(
                    f"Unexpected audit results type: expected list, "
                    f"got {type(inner).__name__}",
                )
            return inner
        if isinstance(result, list):
            return result
        raise MixpanelDataError(
            f"Unexpected audit response format: {type(result).__name__}",
        )

    def run_audit_events_only(self) -> list[Any]:
        """Run an events-only data audit (faster).

        Calls ``GET /api/app/.../data-definitions/audit-events-only/``.
        Same response format as ``run_audit()``.

        Returns:
            Raw 2-element array: ``[violations, {"computed_at": ...}]``.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: No schemas defined (400).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                raw = client.run_audit_events_only()
            ```
        """
        path = self.maybe_scoped_path("data-definitions/audit-events-only/")
        result = self.app_request("GET", path, _raw=True)
        if isinstance(result, dict) and "results" in result:
            inner = result["results"]
            if not isinstance(inner, list):
                raise MixpanelDataError(
                    f"Unexpected audit results type: expected list, "
                    f"got {type(inner).__name__}",
                )
            return inner
        if isinstance(result, list):
            return result
        raise MixpanelDataError(
            f"Unexpected audit response format: {type(result).__name__}",
        )

    # =========================================================================
    # Data Volume Anomalies (Phase 028)
    # =========================================================================

    def list_data_volume_anomalies(
        self,
        *,
        query_params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """List detected data volume anomalies.

        Calls ``GET /api/app/.../data-definitions/data-volume-anomalies/``.
        Extracts anomalies from ``results.anomalies`` using ``_raw=True``.

        Args:
            query_params: Optional filters (status, limit, event_id,
                prop_id, include_property_anomalies,
                include_metric_anomalies).

        Returns:
            List of anomaly dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                anomalies = client.list_data_volume_anomalies(
                    query_params={"status": "open"}
                )
            ```
        """
        path = self.maybe_scoped_path("data-definitions/data-volume-anomalies/")
        result = self.app_request("GET", path, params=query_params, _raw=True)
        # Response: {"status":"ok","results":{"anomalies":[...]}}
        if isinstance(result, dict):
            results = result.get("results", result)
            if isinstance(results, dict):
                if "anomalies" not in results:
                    raise MixpanelDataError(
                        "Unexpected response from list_data_volume_anomalies: "
                        "missing 'anomalies' key in results",
                    )
                anomalies = results["anomalies"]
                if isinstance(anomalies, list):
                    return anomalies
        raise MixpanelDataError(
            "Unexpected response format from list_data_volume_anomalies",
        )

    def update_anomaly(
        self,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Update the status of a single anomaly.

        Calls ``PATCH /api/app/.../data-definitions/data-volume-anomalies/``.

        Args:
            body: Update payload from ``UpdateAnomalyParams.model_dump()``.

        Returns:
            Raw API response as dict.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Anomaly not found or invalid parameters (400).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                result = client.update_anomaly(
                    {"id": 123, "status": "dismissed", "anomalyClass": "Event"}
                )
            ```
        """
        path = self.maybe_scoped_path("data-definitions/data-volume-anomalies/")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from update_anomaly: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def bulk_update_anomalies(
        self,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Bulk update anomaly statuses.

        Calls ``PATCH /api/app/.../data-definitions/data-volume-anomalies/bulk/``.

        Args:
            body: Bulk update payload from
                ``BulkUpdateAnomalyParams.model_dump()``.

        Returns:
            Raw API response as dict.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid parameters (400).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                result = client.bulk_update_anomalies({
                    "anomalies": [...], "status": "dismissed"
                })
            ```
        """
        path = self.maybe_scoped_path("data-definitions/data-volume-anomalies/bulk/")
        result = self.app_request("PATCH", path, json_body=body)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from bulk_update_anomalies: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    # =========================================================================
    # Event Deletion Requests (Phase 028)
    # =========================================================================

    def list_deletion_requests(self) -> list[dict[str, Any]]:
        """List all event deletion requests.

        Calls ``GET /api/app/.../data-definitions/events/deletion-requests/``.

        Returns:
            List of deletion request dictionaries.

        Raises:
            AuthenticationError: Invalid credentials (401).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                requests = client.list_deletion_requests()
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/deletion-requests/")
        result = self.app_request("GET", path)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from list_deletion_requests: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def create_deletion_request(
        self,
        body: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Create a new event deletion request.

        Calls ``POST /api/app/.../data-definitions/events/deletion-requests/``.

        Args:
            body: Creation payload from
                ``CreateDeletionRequestParams.model_dump()``.

        Returns:
            Updated full list of deletion requests.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                requests = client.create_deletion_request({
                    "eventName": "Test", "fromDate": "2026-01-01",
                    "toDate": "2026-01-31",
                })
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/deletion-requests/")
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from create_deletion_request: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def cancel_deletion_request(self, request_id: int) -> list[dict[str, Any]]:
        """Cancel a pending deletion request.

        Calls ``DELETE /api/app/.../data-definitions/events/deletion-requests/``
        with JSON body ``{"id": request_id}``.

        Args:
            request_id: Deletion request ID to cancel.

        Returns:
            Updated full list of deletion requests.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Request not found or not cancellable (400).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                requests = client.cancel_deletion_request(42)
            ```
        """
        path = self.maybe_scoped_path("data-definitions/events/deletion-requests/")
        result = self.app_request("DELETE", path, json_body={"id": request_id})
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from cancel_deletion_request: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    def preview_deletion_filters(
        self,
        body: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Preview what events a deletion filter would match.

        Calls ``POST .../data-definitions/events/deletion-requests/preview-filters/``.

        Args:
            body: Preview payload from
                ``PreviewDeletionFiltersParams.model_dump()``.

        Returns:
            List of expanded/normalized filters.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid filter parameters (400).

        Example:
            ```python
            with MixpanelAPIClient(credentials) as client:
                filters = client.preview_deletion_filters({
                    "eventName": "Test", "fromDate": "2026-01-01",
                    "toDate": "2026-01-31",
                })
            ```
        """
        path = self.maybe_scoped_path(
            "data-definitions/events/deletion-requests/preview-filters/"
        )
        result = self.app_request("POST", path, json_body=body)
        if not isinstance(result, list):
            raise MixpanelDataError(
                f"Unexpected response from preview_deletion_filters: "
                f"expected list, got {type(result).__name__}",
            )
        return result

    # =========================================================================
    # Business Context (AIE-147)
    # =========================================================================

    def get_business_context(
        self, *, organization_id: int | None = None
    ) -> dict[str, Any]:
        """Fetch business context content for an organization or project.

        Calls ``GET /api/app/projects/{pid}/business-context`` (project
        scope) or ``GET /api/app/organizations/{org_id}/business-context``
        (organization scope). The endpoint always returns 200 with
        ``{"content": ""}`` when no context has been set.

        Path is constructed directly (NOT via ``maybe_scoped_path``)
        because the endpoint is project-scoped, not workspace-scoped.

        Args:
            organization_id: When provided, fetches the org-level context
                under ``/organizations/{organization_id}/business-context``.
                When omitted, fetches the project-level context under
                ``/projects/{pid}/business-context`` for the current
                session's project.

        Returns:
            Dictionary of the form ``{"content": "<markdown>"}``. The
            ``content`` field is the empty string when no context is set.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Caller lacks access to the project / organization
                (403, 404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors or unexpected
                response shape.

        Example:
            ```python
            with MixpanelAPIClient(session=sess) as client:
                # Project-level context for the active project.
                project = client.get_business_context()
                print(project["content"])

                # Org-level context for org id 100.
                org = client.get_business_context(organization_id=100)
                print(org["content"])
            ```
        """
        if organization_id is not None:
            path = f"/organizations/{organization_id}/business-context"
        else:
            path = f"/projects/{self._session.project.id}/business-context"
        result = self.app_request("GET", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_business_context: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def set_business_context(
        self, content: str, *, organization_id: int | None = None
    ) -> dict[str, Any]:
        """Replace business context content at the given scope.

        Calls ``PUT /api/app/projects/{pid}/business-context`` (project
        scope) or ``PUT /api/app/organizations/{org_id}/business-context``
        (organization scope). The PUT is full-replace — pass an empty
        string to clear.

        The Mixpanel server enforces a 50,000-character limit and
        returns HTTP 400 ``"content exceeds maximum length of 50000
        characters"`` above that threshold; callers should validate
        client-side first to avoid the wasted round-trip (the
        ``Workspace`` facade does this automatically).

        Path is constructed directly (NOT via ``maybe_scoped_path``)
        because the endpoint is project-scoped, not workspace-scoped.

        Args:
            content: New markdown content. Empty string clears the
                context at this scope.
            organization_id: When provided, writes the org-level context.
                When omitted, writes the project-level context for the
                current session's project.

        Returns:
            Dictionary of the form ``{"content": "<saved markdown>"}``
            echoing what the server stored.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Content exceeds 50,000 chars (400), caller lacks
                ``edit_project_info`` permission (403), or invalid JSON
                body (400).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors or unexpected
                response shape.

        Example:
            ```python
            with MixpanelAPIClient(session=sess) as client:
                client.set_business_context("# About Acme\\n...")
                client.set_business_context("", organization_id=100)  # clear org
            ```
        """
        if organization_id is not None:
            path = f"/organizations/{organization_id}/business-context"
        else:
            path = f"/projects/{self._session.project.id}/business-context"
        result = self.app_request("PUT", path, json_body={"content": content})
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from set_business_context: "
                f"expected dict, got {type(result).__name__}",
            )
        return result

    def get_business_context_chain(self) -> dict[str, Any]:
        """Fetch both organization and project business context together.

        Calls ``GET /api/app/projects/{pid}/business-context/chain`` —
        a server-side convenience that returns both scopes in a single
        round-trip, scoped to the current session's project. The org
        context returned is the one that owns the project.

        Returns:
            Dictionary of the form
            ``{"org_context": "<markdown>", "project_context": "<markdown>"}``.
            Either field may be the empty string when no context is set
            at that scope.

        Raises:
            AuthenticationError: Invalid credentials (401).
            QueryError: Caller lacks project access (403, 404).
            ServerError: Server-side errors (5xx).
            MixpanelDataError: Network/connection errors or unexpected
                response shape.

        Example:
            ```python
            with MixpanelAPIClient(session=sess) as client:
                chain = client.get_business_context_chain()
                print("ORG:", chain["org_context"])
                print("PROJECT:", chain["project_context"])
            ```
        """
        path = f"/projects/{self._session.project.id}/business-context/chain"
        result = self.app_request("GET", path)
        if not isinstance(result, dict):
            raise MixpanelDataError(
                f"Unexpected response from get_business_context_chain: "
                f"expected dict, got {type(result).__name__}",
            )
        return result
