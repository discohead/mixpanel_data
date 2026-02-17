"""Unit tests for FeatureFlagService.

Tests use httpx.MockTransport for deterministic HTTP mocking.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from mixpanel_data._internal.services.feature_flag import (
    FeatureFlagService,
    _parse_flag,
)
from mixpanel_data.types import FeatureFlagListResult, FeatureFlagResult

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def flag_service_factory(
    request: pytest.FixtureRequest,
    mock_client_factory: Callable[
        [Callable[[httpx.Request], httpx.Response]], MixpanelAPIClient
    ],
) -> Callable[[Callable[[httpx.Request], httpx.Response]], FeatureFlagService]:
    """Factory for creating FeatureFlagService with mock API client.

    Usage:
        def test_something(flag_service_factory):
            def handler(request):
                return httpx.Response(200, json={"status": "ok", "results": [...]})

            service = flag_service_factory(handler)
            result = service.list_flags()
    """
    clients: list[MixpanelAPIClient] = []

    def factory(
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> FeatureFlagService:
        client = mock_client_factory(handler)
        client.__enter__()
        clients.append(client)
        return FeatureFlagService(client)

    def cleanup() -> None:
        for client in clients:
            client.__exit__(None, None, None)

    request.addfinalizer(cleanup)
    return factory


# Sample flag data for tests
SAMPLE_FLAG: dict[str, Any] = {
    "id": "abc-123-def",
    "name": "Test Flag",
    "key": "test_flag",
    "description": "A test feature flag",
    "status": "active",
    "tags": ["test", "experiment"],
    "ruleset": {"variants": [{"key": "on", "value": True}]},
    "created": "2024-01-01T00:00:00Z",
    "modified": "2024-06-01T00:00:00Z",
    "creatorName": "Test User",
}

SAMPLE_FLAG_2: dict[str, Any] = {
    "id": "xyz-789-uvw",
    "name": "Another Flag",
    "key": "another_flag",
    "description": None,
    "status": "draft",
    "tags": [],
    "ruleset": {},
    "created": "2024-02-01T00:00:00Z",
    "modified": "2024-02-01T00:00:00Z",
    "creatorName": None,
}


# =============================================================================
# _parse_flag Tests
# =============================================================================


class TestParseFlag:
    """Tests for the _parse_flag helper function."""

    def test_parse_complete_flag(self) -> None:
        """Parse a flag with all fields populated."""
        result = _parse_flag(SAMPLE_FLAG)

        assert isinstance(result, FeatureFlagResult)
        assert result.id == "abc-123-def"
        assert result.name == "Test Flag"
        assert result.key == "test_flag"
        assert result.description == "A test feature flag"
        assert result.status == "active"
        assert result.tags == ["test", "experiment"]
        assert result.ruleset == {"variants": [{"key": "on", "value": True}]}
        assert result.created == "2024-01-01T00:00:00Z"
        assert result.modified == "2024-06-01T00:00:00Z"
        assert result.creator_name == "Test User"
        assert result.raw == SAMPLE_FLAG

    def test_parse_minimal_flag(self) -> None:
        """Parse a flag with minimal fields."""
        data: dict[str, Any] = {"id": "min-id", "name": "Min", "key": "min"}
        result = _parse_flag(data)

        assert result.id == "min-id"
        assert result.name == "Min"
        assert result.key == "min"
        assert result.description is None
        assert result.status == ""
        assert result.tags == []
        assert result.ruleset == {}
        assert result.created is None
        assert result.modified is None
        assert result.creator_name is None

    def test_parse_empty_dict(self) -> None:
        """Parse an empty dict defaults gracefully."""
        result = _parse_flag({})

        assert result.id == ""
        assert result.name == ""
        assert result.key == ""

    def test_parse_preserves_raw(self) -> None:
        """Parse stores complete raw data including extra fields."""
        data = {**SAMPLE_FLAG, "extra_field": "extra_value"}
        result = _parse_flag(data)

        assert result.raw["extra_field"] == "extra_value"


# =============================================================================
# FeatureFlagService Init Tests
# =============================================================================


class TestFeatureFlagServiceInit:
    """Tests for FeatureFlagService initialization."""

    def test_init_stores_api_client(
        self,
        mock_client_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], MixpanelAPIClient
        ],
        success_handler: Callable[[httpx.Request], httpx.Response],
    ) -> None:
        """FeatureFlagService stores its API client."""
        client = mock_client_factory(success_handler)
        service = FeatureFlagService(client)
        assert service._api_client is client


# =============================================================================
# list_flags Tests
# =============================================================================


class TestListFlags:
    """Tests for FeatureFlagService.list_flags()."""

    def test_list_flags_returns_results(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """list_flags() returns a FeatureFlagListResult with parsed flags."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"status": "ok", "results": [SAMPLE_FLAG, SAMPLE_FLAG_2]},
            )

        service = flag_service_factory(handler)
        result = service.list_flags()

        assert isinstance(result, FeatureFlagListResult)
        assert len(result.flags) == 2
        assert result.flags[0].name == "Test Flag"
        assert result.flags[1].name == "Another Flag"

    def test_list_flags_empty(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """list_flags() returns empty list when no flags exist."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok", "results": []})

        service = flag_service_factory(handler)
        result = service.list_flags()

        assert isinstance(result, FeatureFlagListResult)
        assert len(result.flags) == 0

    def test_list_flags_url_construction(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """list_flags() constructs correct URL with project ID."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_url.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        service = flag_service_factory(handler)
        service.list_flags()

        assert len(captured_url) == 1
        assert "/projects/12345/feature-flags" in captured_url[0]

    def test_list_flags_include_archived(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """list_flags(include_archived=True) sends include_archived param."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_url.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        service = flag_service_factory(handler)
        service.list_flags(include_archived=True)

        assert "include_archived=true" in captured_url[0]

    def test_list_flags_no_archived_param_by_default(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """list_flags() does not send include_archived param by default."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_url.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        service = flag_service_factory(handler)
        service.list_flags()

        assert "include_archived" not in captured_url[0]

    def test_list_flags_no_project_id_in_query_params(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """list_flags() does not inject project_id as query param."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_url.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        service = flag_service_factory(handler)
        service.list_flags()

        assert "project_id=" not in captured_url[0]


# =============================================================================
# get_flag Tests
# =============================================================================


class TestGetFlag:
    """Tests for FeatureFlagService.get_flag()."""

    def test_get_flag_returns_result(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """get_flag() returns a parsed FeatureFlagResult."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok", "results": SAMPLE_FLAG})

        service = flag_service_factory(handler)
        result = service.get_flag("abc-123-def")

        assert isinstance(result, FeatureFlagResult)
        assert result.id == "abc-123-def"
        assert result.name == "Test Flag"

    def test_get_flag_url_construction(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """get_flag() constructs correct URL with flag ID."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_url.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": SAMPLE_FLAG})

        service = flag_service_factory(handler)
        service.get_flag("abc-123-def")

        assert "/projects/12345/feature-flags/abc-123-def" in captured_url[0]

    def test_get_flag_not_found(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """get_flag() raises QueryError for 404 responses."""
        from mixpanel_data.exceptions import QueryError

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "Flag not found"})

        service = flag_service_factory(handler)
        with pytest.raises(QueryError):
            service.get_flag("nonexistent-id")


# =============================================================================
# create_flag Tests
# =============================================================================


class TestCreateFlag:
    """Tests for FeatureFlagService.create_flag()."""

    def test_create_flag_returns_result(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """create_flag() returns a parsed FeatureFlagResult."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok", "results": SAMPLE_FLAG})

        service = flag_service_factory(handler)
        result = service.create_flag({"name": "Test Flag", "key": "test_flag"})

        assert isinstance(result, FeatureFlagResult)
        assert result.name == "Test Flag"

    def test_create_flag_sends_post(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """create_flag() uses POST method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": SAMPLE_FLAG})

        service = flag_service_factory(handler)
        service.create_flag({"name": "Test"})

        assert captured_methods[0] == "POST"

    def test_create_flag_sends_payload(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """create_flag() sends payload as JSON body."""
        captured_bodies: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode())
            captured_bodies.append(body)
            return httpx.Response(200, json={"status": "ok", "results": SAMPLE_FLAG})

        service = flag_service_factory(handler)
        payload = {"name": "Test", "key": "test", "ruleset": {"variants": []}}
        service.create_flag(payload)

        assert captured_bodies[0] == payload

    def test_create_flag_bad_request(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """create_flag() raises QueryError for invalid payload."""
        from mixpanel_data.exceptions import QueryError

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "Invalid payload"})

        service = flag_service_factory(handler)
        with pytest.raises(QueryError):
            service.create_flag({})


# =============================================================================
# update_flag Tests
# =============================================================================


class TestUpdateFlag:
    """Tests for FeatureFlagService.update_flag()."""

    def test_update_flag_returns_result(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """update_flag() returns a parsed FeatureFlagResult."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok", "results": SAMPLE_FLAG})

        service = flag_service_factory(handler)
        result = service.update_flag("abc-123-def", {"name": "Updated"})

        assert isinstance(result, FeatureFlagResult)

    def test_update_flag_sends_put(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """update_flag() uses PUT method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": SAMPLE_FLAG})

        service = flag_service_factory(handler)
        service.update_flag("abc-123-def", {"name": "Updated"})

        assert captured_methods[0] == "PUT"

    def test_update_flag_url_includes_id(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """update_flag() includes flag ID in URL."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_url.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": SAMPLE_FLAG})

        service = flag_service_factory(handler)
        service.update_flag("abc-123-def", {"name": "Updated"})

        assert "/feature-flags/abc-123-def" in captured_url[0]


# =============================================================================
# delete_flag Tests
# =============================================================================


class TestDeleteFlag:
    """Tests for FeatureFlagService.delete_flag()."""

    def test_delete_flag_sends_delete(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """delete_flag() uses DELETE method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok"})

        service = flag_service_factory(handler)
        service.delete_flag("abc-123-def")

        assert captured_methods[0] == "DELETE"

    def test_delete_flag_url_includes_id(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """delete_flag() includes flag ID in URL."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_url.append(str(request.url))
            return httpx.Response(200, json={"status": "ok"})

        service = flag_service_factory(handler)
        service.delete_flag("abc-123-def")

        assert "/feature-flags/abc-123-def" in captured_url[0]

    def test_delete_flag_returns_response(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """delete_flag() returns the raw API response."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok", "results": {}})

        service = flag_service_factory(handler)
        result = service.delete_flag("abc-123-def")

        assert result["status"] == "ok"

    def test_delete_enabled_flag_raises_error(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """delete_flag() raises QueryError when flag is enabled."""
        from mixpanel_data.exceptions import QueryError

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={"error": "Cannot delete an enabled flag"},
            )

        service = flag_service_factory(handler)
        with pytest.raises(QueryError):
            service.delete_flag("abc-123-def")


# =============================================================================
# archive_flag Tests
# =============================================================================


class TestArchiveFlag:
    """Tests for FeatureFlagService.archive_flag()."""

    def test_archive_flag_sends_post(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """archive_flag() uses POST method to /archive endpoint."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append((request.method, str(request.url)))
            return httpx.Response(200, json={"status": "ok"})

        service = flag_service_factory(handler)
        service.archive_flag("abc-123-def")

        assert captured[0][0] == "POST"
        assert "/feature-flags/abc-123-def/archive" in captured[0][1]

    def test_archive_flag_returns_response(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """archive_flag() returns the raw API response."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok"})

        service = flag_service_factory(handler)
        result = service.archive_flag("abc-123-def")

        assert result["status"] == "ok"


# =============================================================================
# restore_flag Tests
# =============================================================================


class TestRestoreFlag:
    """Tests for FeatureFlagService.restore_flag()."""

    def test_restore_flag_sends_delete(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """restore_flag() uses DELETE method to /archive endpoint."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append((request.method, str(request.url)))
            return httpx.Response(200, json={"status": "ok"})

        service = flag_service_factory(handler)
        service.restore_flag("abc-123-def")

        assert captured[0][0] == "DELETE"
        assert "/feature-flags/abc-123-def/archive" in captured[0][1]

    def test_restore_flag_returns_response(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """restore_flag() returns the raw API response."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok"})

        service = flag_service_factory(handler)
        result = service.restore_flag("abc-123-def")

        assert result["status"] == "ok"

    def test_restore_nonexistent_flag_raises_error(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """restore_flag() raises QueryError for 404 responses."""
        from mixpanel_data.exceptions import QueryError

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "Flag not found"})

        service = flag_service_factory(handler)
        with pytest.raises(QueryError):
            service.restore_flag("nonexistent-id")


# =============================================================================
# FeatureFlagResult.to_dict Tests
# =============================================================================


class TestFeatureFlagResultToDict:
    """Tests for FeatureFlagResult.to_dict()."""

    def test_to_dict_includes_required_fields(self) -> None:
        """to_dict() includes id, name, key, status, tags, ruleset."""
        flag = _parse_flag(SAMPLE_FLAG)
        result = flag.to_dict()

        assert result["id"] == "abc-123-def"
        assert result["name"] == "Test Flag"
        assert result["key"] == "test_flag"
        assert result["status"] == "active"
        assert result["tags"] == ["test", "experiment"]
        assert result["ruleset"] == {"variants": [{"key": "on", "value": True}]}

    def test_to_dict_includes_optional_fields_when_set(self) -> None:
        """to_dict() includes optional fields when they have values."""
        flag = _parse_flag(SAMPLE_FLAG)
        result = flag.to_dict()

        assert result["description"] == "A test feature flag"
        assert result["created"] == "2024-01-01T00:00:00Z"
        assert result["modified"] == "2024-06-01T00:00:00Z"
        assert result["creator_name"] == "Test User"

    def test_to_dict_omits_none_optional_fields(self) -> None:
        """to_dict() omits optional fields that are None."""
        flag = _parse_flag(SAMPLE_FLAG_2)
        result = flag.to_dict()

        assert "description" not in result
        assert "creator_name" not in result


# =============================================================================
# FeatureFlagListResult Tests
# =============================================================================


class TestFeatureFlagListResult:
    """Tests for FeatureFlagListResult."""

    def test_to_dict_returns_list(self) -> None:
        """to_dict() returns a list of flag dicts."""
        flags = [_parse_flag(SAMPLE_FLAG), _parse_flag(SAMPLE_FLAG_2)]
        result = FeatureFlagListResult(flags=flags)

        dicts = result.to_dict()
        assert isinstance(dicts, list)
        assert len(dicts) == 2
        assert dicts[0]["name"] == "Test Flag"

    def test_df_returns_dataframe(self) -> None:
        """df property returns a DataFrame with flag data."""
        flags = [_parse_flag(SAMPLE_FLAG)]
        result = FeatureFlagListResult(flags=flags)

        df = result.df
        assert len(df) == 1
        assert "name" in df.columns
        assert "key" in df.columns
        assert "status" in df.columns
        assert df.iloc[0]["name"] == "Test Flag"

    def test_df_empty_result(self) -> None:
        """df property returns empty DataFrame with correct columns."""
        result = FeatureFlagListResult(flags=[])

        df = result.df
        assert len(df) == 0
        assert "name" in df.columns
        assert "key" in df.columns

    def test_df_is_cached(self) -> None:
        """df property caches the DataFrame."""
        result = FeatureFlagListResult(flags=[_parse_flag(SAMPLE_FLAG)])

        df1 = result.df
        df2 = result.df
        assert df1 is df2

    def test_to_table_dict_returns_flat_dicts(self) -> None:
        """to_table_dict() returns flat dicts suitable for table display."""
        flags = [_parse_flag(SAMPLE_FLAG)]
        result = FeatureFlagListResult(flags=flags)

        table_dicts = result.to_table_dict()
        assert len(table_dicts) == 1
        assert table_dicts[0]["name"] == "Test Flag"
        assert table_dicts[0]["tags"] == "test, experiment"

    def test_to_table_dict_empty(self) -> None:
        """to_table_dict() returns empty list for empty result."""
        result = FeatureFlagListResult(flags=[])

        table_dicts = result.to_table_dict()
        assert table_dicts == []


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling across service methods."""

    def test_authentication_error(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """Service methods raise AuthenticationError for 401 responses."""
        from mixpanel_data.exceptions import AuthenticationError

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Invalid credentials"})

        service = flag_service_factory(handler)
        with pytest.raises(AuthenticationError):
            service.list_flags()

    def test_server_error(
        self,
        flag_service_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], FeatureFlagService
        ],
    ) -> None:
        """Service methods raise ServerError for 5xx responses."""
        from mixpanel_data.exceptions import ServerError

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "Internal server error"})

        service = flag_service_factory(handler)
        with pytest.raises(ServerError):
            service.get_flag("abc-123-def")
