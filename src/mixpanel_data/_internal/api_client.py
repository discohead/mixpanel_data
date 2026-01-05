"""Mixpanel API Client.

Low-level HTTP client for all Mixpanel APIs. Handles:
- Service account authentication via HTTP Basic auth
- Regional endpoint routing (US, EU, India)
- Automatic rate limit handling with exponential backoff
- Streaming JSONL parsing for large exports

This is a private implementation detail. Users should use the Workspace class
or service layer instead of accessing this module directly.
"""

from __future__ import annotations

import base64
import json
import logging
import random
import time
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

import httpx

from mixpanel_data._internal.config import Credentials
from mixpanel_data.exceptions import (
    AuthenticationError,
    JQLSyntaxError,
    MixpanelDataError,
    QueryError,
    RateLimitError,
    ServerError,
)

if TYPE_CHECKING:
    from types import TracebackType

logger = logging.getLogger(__name__)

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
        from mixpanel_data._internal.config import ConfigManager
        from mixpanel_data._internal.api_client import MixpanelAPIClient

        config = ConfigManager()
        credentials = config.resolve_credentials()

        with MixpanelAPIClient(credentials) as client:
            events = client.get_events()
            print(events)
        ```
    """

    def __init__(
        self,
        credentials: Credentials,
        *,
        timeout: float = 120.0,
        export_timeout: float = 600.0,
        max_retries: int = 3,
        _transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Initialize the API client.

        Args:
            credentials: Immutable authentication credentials.
            timeout: Request timeout in seconds for regular requests.
            export_timeout: Request timeout for export operations.
            max_retries: Maximum retry attempts for rate-limited requests.
            _transport: Internal parameter for testing with MockTransport.
        """
        self._credentials = credentials
        self._timeout = timeout
        self._export_timeout = export_timeout
        self._max_retries = max_retries
        self._client: httpx.Client | None = None
        self._transport = _transport

    def _get_auth_header(self) -> str:
        """Generate HTTP Basic auth header value.

        Returns:
            Base64-encoded "username:secret" prefixed with "Basic ".
        """
        secret = self._credentials.secret.get_secret_value()
        auth_string = f"{self._credentials.username}:{secret}"
        encoded = base64.b64encode(auth_string.encode()).decode()
        return f"Basic {encoded}"

    def _build_url(self, api_type: str, path: str) -> str:
        """Build full URL for the given API type and path.

        Args:
            api_type: One of "query", "export", or "engage".
            path: API endpoint path (e.g., "/segmentation").

        Returns:
            Full URL for the endpoint.
        """
        region = self._credentials.region
        base = ENDPOINTS[region][api_type]
        # Ensure path starts with /
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{base}{path}"

    def _ensure_client(self) -> httpx.Client:
        """Ensure HTTP client is initialized.

        Returns:
            The httpx.Client instance.
        """
        if self._client is None:
            self._client = httpx.Client(
                timeout=self._timeout,
                transport=self._transport,
            )
        return self._client

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
        return response.json()

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

        for attempt in range(self._max_retries + 1):
            try:
                response = client.request(
                    method,
                    url,
                    params=params,
                    json=json_data,
                    data=form_data,
                    headers=headers,
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
            params["project_id"] = self._credentials.project_id

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
        """Get the project ID from credentials.

        Useful when constructing URLs that require the project ID.

        Returns:
            The Mixpanel project ID.
        """
        return self._credentials.project_id

    @property
    def region(self) -> str:
        """Get the configured region.

        Useful when constructing regional URLs.

        Returns:
            The region code ('us', 'eu', or 'in').
        """
        return self._credentials.region

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
            "project_id": self._credentials.project_id,
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
        headers = {
            "Authorization": self._get_auth_header(),
            "Accept-Encoding": "gzip",
        }

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

                    for line in response.iter_lines():
                        if not line.strip():
                            continue
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
                "project_id": self._credentials.project_id,
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
    ) -> dict[str, Any]:
        """Query a saved report (Insights, Retention, or Funnel).

        Executes a saved report by its bookmark ID. The report type is
        automatically detected from the response headers.

        Args:
            bookmark_id: Saved report identifier (from Mixpanel URL or list_bookmarks).

        Returns:
            Raw API response with time-series data and metadata.
            The response structure varies by report type.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid bookmark_id or report not found.
            RateLimitError: Rate limit exceeded.
        """
        url = self._build_url("query", "/insights")
        params: dict[str, Any] = {"bookmark_id": bookmark_id}
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
            f"/projects/{self._credentials.project_id}/bookmarks",
        )
        params: dict[str, Any] = {"v": "2"}
        if bookmark_type is not None:
            params["type"] = bookmark_type
        result: dict[str, Any] = self._request("GET", url, params=params)
        return result

    def query_flows(
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
            path = f"/projects/{self._credentials.project_id}/schemas/{entity_type}"
        else:
            path = f"/projects/{self._credentials.project_id}/schemas"

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
            f"/projects/{self._credentials.project_id}/schemas/{entity_type}",
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
