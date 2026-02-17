"""Feature Flag Service for Mixpanel feature flag management.

Provides CRUD operations for feature flags via the Mixpanel Feature Flags API.
Supports listing, creating, updating, deleting, archiving, and restoring flags.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mixpanel_data.types import FeatureFlagListResult, FeatureFlagResult

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient

_logger = logging.getLogger(__name__)


def _parse_flag(data: dict[str, Any]) -> FeatureFlagResult:
    """Parse a single feature flag from API response data.

    Extracts known fields from the raw API response and stores the
    complete response in the ``raw`` field for access to any additional
    fields not represented in the dataclass.

    Args:
        data: Raw feature flag dictionary from API response.

    Returns:
        FeatureFlagResult with parsed fields.
    """
    return FeatureFlagResult(
        id=str(data.get("id", "")),
        name=data.get("name", ""),
        key=data.get("key", ""),
        description=data.get("description"),
        status=data.get("status", ""),
        tags=data.get("tags", []),
        ruleset=data.get("ruleset", {}),
        created=data.get("created"),
        modified=data.get("modified"),
        creator_name=data.get("creatorName"),
        raw=data,
    )


class FeatureFlagService:
    """Service for managing Mixpanel feature flags.

    Provides methods for CRUD operations on feature flags using the
    Mixpanel Feature Flags API. Uses the ``app`` base URL with
    project-scoped paths.

    All methods unwrap the ``{"status": "ok", "results": ...}`` response
    envelope, returning clean data to callers.

    Args:
        api_client: Authenticated MixpanelAPIClient instance.

    Example:
        ```python
        service = FeatureFlagService(api_client)
        flags = service.list_flags()
        flag = service.get_flag("flag-uuid-123")
        ```
    """

    def __init__(self, api_client: MixpanelAPIClient) -> None:
        """Initialize the FeatureFlagService.

        Args:
            api_client: Authenticated MixpanelAPIClient for API requests.
        """
        self._api_client = api_client

    def _base_url(self) -> str:
        """Build the base URL for feature flag API requests.

        Returns:
            Full URL for the feature flags endpoint including project ID.
        """
        return self._api_client._build_url(
            "app",
            f"/projects/{self._api_client.project_id}/feature-flags",
        )

    def _flag_url(self, flag_id: str) -> str:
        """Build the URL for a specific feature flag.

        Args:
            flag_id: UUID of the feature flag.

        Returns:
            Full URL for the specific feature flag endpoint.
        """
        return f"{self._base_url()}/{flag_id}"

    def list_flags(self, *, include_archived: bool = False) -> FeatureFlagListResult:
        """List all feature flags in the project.

        Args:
            include_archived: If True, include archived flags in the response.
                Defaults to False.

        Returns:
            FeatureFlagListResult containing all matching flags.

        Raises:
            AuthenticationError: Invalid credentials.
            RateLimitError: Rate limit exceeded after retries.
            QueryError: Permission denied or invalid parameters.
        """
        url = self._base_url()
        params: dict[str, Any] = {}
        if include_archived:
            params["include_archived"] = "true"

        _logger.debug("list_flags - URL: %s, params: %s", url, params)

        response: dict[str, Any] = self._api_client._request(
            "GET",
            url,
            params=params if params else None,
            inject_project_id=False,
        )

        raw_flags: list[dict[str, Any]] = response.get("results", [])
        flags = [_parse_flag(f) for f in raw_flags]
        return FeatureFlagListResult(flags=flags)

    def get_flag(self, flag_id: str) -> FeatureFlagResult:
        """Get a single feature flag by ID.

        Args:
            flag_id: UUID of the feature flag to retrieve.

        Returns:
            FeatureFlagResult for the requested flag.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Flag not found (404) or invalid parameters.
            RateLimitError: Rate limit exceeded after retries.
        """
        url = self._flag_url(flag_id)

        _logger.debug("get_flag - URL: %s", url)

        response: dict[str, Any] = self._api_client._request(
            "GET", url, inject_project_id=False
        )

        raw_flag: dict[str, Any] = response.get("results", response)
        return _parse_flag(raw_flag)

    def create_flag(self, payload: dict[str, Any]) -> FeatureFlagResult:
        """Create a new feature flag.

        Args:
            payload: Feature flag configuration including name, key, and ruleset.

        Returns:
            FeatureFlagResult for the newly created flag.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid payload or duplicate key (400).
            RateLimitError: Rate limit exceeded after retries.
        """
        url = self._base_url()

        _logger.debug("create_flag - URL: %s", url)

        response: dict[str, Any] = self._api_client._request(
            "POST", url, data=payload, inject_project_id=False
        )

        raw_flag: dict[str, Any] = response.get("results", response)
        return _parse_flag(raw_flag)

    def update_flag(self, flag_id: str, payload: dict[str, Any]) -> FeatureFlagResult:
        """Update an existing feature flag.

        This is a full replacement (PUT), not a partial update.

        Args:
            flag_id: UUID of the feature flag to update.
            payload: Complete feature flag configuration to replace the existing one.

        Returns:
            FeatureFlagResult for the updated flag.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Flag not found (404) or invalid payload (400).
            RateLimitError: Rate limit exceeded after retries.
        """
        url = self._flag_url(flag_id)

        _logger.debug("update_flag - URL: %s", url)

        response: dict[str, Any] = self._api_client._request(
            "PUT", url, data=payload, inject_project_id=False
        )

        raw_flag: dict[str, Any] = response.get("results", response)
        return _parse_flag(raw_flag)

    def delete_flag(self, flag_id: str) -> dict[str, Any]:
        """Delete a feature flag.

        Cannot delete flags that are currently enabled.

        Args:
            flag_id: UUID of the feature flag to delete.

        Returns:
            Raw API response (typically empty on success).

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Flag not found (404) or flag is enabled (400).
            RateLimitError: Rate limit exceeded after retries.
        """
        url = self._flag_url(flag_id)

        _logger.debug("delete_flag - URL: %s", url)

        result: dict[str, Any] = self._api_client._request(
            "DELETE", url, inject_project_id=False
        )
        return result

    def archive_flag(self, flag_id: str) -> dict[str, Any]:
        """Archive a feature flag (soft delete).

        Archived flags are hidden by default but can be restored.

        Args:
            flag_id: UUID of the feature flag to archive.

        Returns:
            Raw API response.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Flag not found (404).
            RateLimitError: Rate limit exceeded after retries.
        """
        url = f"{self._flag_url(flag_id)}/archive"

        _logger.debug("archive_flag - URL: %s", url)

        result: dict[str, Any] = self._api_client._request(
            "POST", url, inject_project_id=False
        )
        return result

    def restore_flag(self, flag_id: str) -> dict[str, Any]:
        """Restore an archived feature flag.

        Undoes a previous archive operation, making the flag visible again.

        Args:
            flag_id: UUID of the feature flag to restore.

        Returns:
            Raw API response.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Flag not found (404).
            RateLimitError: Rate limit exceeded after retries.
        """
        url = f"{self._flag_url(flag_id)}/archive"

        _logger.debug("restore_flag - URL: %s", url)

        result: dict[str, Any] = self._api_client._request(
            "DELETE", url, inject_project_id=False
        )
        return result
