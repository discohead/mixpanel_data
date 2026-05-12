"""Unit tests for engage_stats() and export_profiles_page() extensions.

TDD tests for:
- T006a: engage_stats() POSTs to /engage with filter_type=stats and correct params
- T006b: export_profiles_page() passes sort_key/sort_order/search/limit/filter_by_cohort
- T006c: filter_by_cohort supports both {"id": N} and {"raw_cohort": {...}} formats

Tests use httpx.MockTransport for deterministic HTTP mocking, matching the
established pattern in tests/unit/test_api_client.py.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.session import Session
from mixpanel_headless.exceptions import QueryError
from tests.conftest import make_session

# =============================================================================
# Helpers
# =============================================================================


def _make_credentials() -> Session:
    """Create test credentials for API client construction.

    Returns:
        Credentials with test values for US region.
    """
    return make_session(
        username="test_user",
        secret="test_secret",
        project_id="12345",
        region="us",
    )


def _create_mock_client(
    credentials: Session,
    handler: Any,
) -> MixpanelAPIClient:
    """Create a MixpanelAPIClient with mock transport.

    Args:
        credentials: Test credentials for authentication.
        handler: Callable that receives httpx.Request and returns httpx.Response.

    Returns:
        MixpanelAPIClient wired to the mock transport.
    """
    transport = httpx.MockTransport(handler)
    return MixpanelAPIClient(session=credentials, _transport=transport)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_credentials() -> Session:
    """Create test credentials for API client construction.

    Returns:
        Credentials with test values for US region.
    """
    return _make_credentials()


# =============================================================================
# T006a: engage_stats() — new method
# =============================================================================


class TestEngageStats:
    """Tests for engage_stats() API method (T006a).

    Verifies that engage_stats() POSTs to /engage with filter_type=stats
    and forwards all parameters correctly.
    """

    def test_posts_to_engage_endpoint(self, test_credentials: Session) -> None:
        """engage_stats() should POST to the /engage endpoint."""
        captured_url: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_url
            captured_url = str(request.url)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats()

        assert "/engage" in captured_url

    def test_posts_to_engage_stats_url(self, test_credentials: Session) -> None:
        """engage_stats() should POST to the /engage/stats URL path."""
        captured_url: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_url
            captured_url = str(request.url)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats()

        assert "/engage/stats" in captured_url

    def test_sends_project_id(self, test_credentials: Session) -> None:
        """engage_stats() should include project_id in request body."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats()

        assert captured_body.get("project_id") == "12345"

    def test_default_action_is_count(self, test_credentials: Session) -> None:
        """engage_stats() should default action to 'count()'."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats()

        assert captured_body.get("action") == "count()"

    def test_custom_action(self, test_credentials: Session) -> None:
        """engage_stats() should send custom action value."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats(action="sum(properties['revenue'])")

        assert captured_body.get("action") == "sum(properties['revenue'])"

    def test_where_sent_as_selector(self, test_credentials: Session) -> None:
        """engage_stats() should send where value as 'selector' param."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats(where='properties["plan"] == "premium"')

        assert captured_body.get("selector") == 'properties["plan"] == "premium"'
        assert "where" not in captured_body

    def test_selector_omitted_when_where_none(self, test_credentials: Session) -> None:
        """engage_stats() should not send selector when where is None."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats()

        assert "selector" not in captured_body

    def test_filter_by_cohort_parameter(self, test_credentials: Session) -> None:
        """engage_stats() should send filter_by_cohort as JSON string."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats(filter_by_cohort="cohort_123")

        assert "filter_by_cohort" in captured_body

    def test_filter_by_cohort_omitted_when_none(
        self, test_credentials: Session
    ) -> None:
        """engage_stats() should not send filter_by_cohort when None."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats()

        assert "filter_by_cohort" not in captured_body

    def test_segment_by_cohorts_parameter(self, test_credentials: Session) -> None:
        """engage_stats() should send segment_by_cohorts as JSON string."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        cohorts = {"cohort_1": True, "cohort_2": False}
        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats(segment_by_cohorts=cohorts)

        raw = captured_body.get("segment_by_cohorts")
        assert raw is not None
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        assert parsed == {"cohort_1": True, "cohort_2": False}

    def test_segment_by_cohorts_omitted_when_none(
        self, test_credentials: Session
    ) -> None:
        """engage_stats() should not send segment_by_cohorts when None."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats()

        assert "segment_by_cohorts" not in captured_body

    def test_group_id_parameter(self, test_credentials: Session) -> None:
        """engage_stats() should send data_group_id when group_id is provided."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats(group_id="companies")

        assert captured_body.get("data_group_id") == "companies"

    def test_group_id_omitted_when_none(self, test_credentials: Session) -> None:
        """engage_stats() should not send data_group_id when group_id is None."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats()

        assert "data_group_id" not in captured_body

    def test_as_of_timestamp_parameter(self, test_credentials: Session) -> None:
        """engage_stats() should send as_of_timestamp when provided."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats(as_of_timestamp=1700000000)

        assert captured_body.get("as_of_timestamp") == 1700000000

    def test_as_of_timestamp_omitted_when_none(self, test_credentials: Session) -> None:
        """engage_stats() should not send as_of_timestamp when None."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats()

        assert "as_of_timestamp" not in captured_body

    def test_include_all_users_false_by_default(
        self, test_credentials: Session
    ) -> None:
        """engage_stats() should not send include_all_users when False (default)."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats()

        assert captured_body.get("include_all_users") is not True

    def test_include_all_users_true(self, test_credentials: Session) -> None:
        """engage_stats() should send include_all_users when cohort filter present."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats(
                filter_by_cohort='{"id": 42}',
                include_all_users=True,
            )

        assert captured_body.get("include_all_users") is True

    def test_returns_raw_dict(self, test_credentials: Session) -> None:
        """engage_stats() should return the raw response dict."""
        expected: dict[str, Any] = {
            "results": [{"count": 42}],
            "total": 42,
        }

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=expected)

        with _create_mock_client(test_credentials, handler) as client:
            result = client.engage_stats()

        assert isinstance(result, dict)
        assert result.get("total") == 42

    def test_uses_post_method(self, test_credentials: Session) -> None:
        """engage_stats() should use HTTP POST method."""
        captured_method: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_method
            captured_method = request.method
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats()

        assert captured_method == "POST"

    def test_all_params_combined(self, test_credentials: Session) -> None:
        """engage_stats() should combine all parameters in a single request."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": [], "total": 0})

        with _create_mock_client(test_credentials, handler) as client:
            client.engage_stats(
                where='properties["country"] == "US"',
                action="sum(properties['revenue'])",
                filter_by_cohort="cohort_99",
                segment_by_cohorts={"c1": True},
                group_id="companies",
                as_of_timestamp=1700000000,
                include_all_users=True,
            )

        assert captured_body.get("selector") == 'properties["country"] == "US"'
        assert "where" not in captured_body
        assert captured_body.get("action") == "sum(properties['revenue'])"
        assert "filter_by_cohort" in captured_body
        assert "segment_by_cohorts" in captured_body
        assert captured_body.get("data_group_id") == "companies"
        assert captured_body.get("as_of_timestamp") == 1700000000
        assert captured_body.get("include_all_users") is True

    def test_non_dict_response_raises_query_error(
        self, test_credentials: Session
    ) -> None:
        """engage_stats() raises QueryError when the API returns a non-dict response."""

        def handler(_request: httpx.Request) -> httpx.Response:
            """Return a JSON list instead of a dict."""
            return httpx.Response(200, json=[1, 2, 3])

        with (
            _create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError, match="unexpected response type"),
        ):
            client.engage_stats()


# =============================================================================
# T006b: export_profiles_page() — new parameters
# =============================================================================


class TestExportProfilesPageNewParams:
    """Tests for new export_profiles_page() parameters (T006b).

    Verifies that export_profiles_page() correctly passes the new
    sort_key, sort_order, search, limit, and filter_by_cohort parameters.
    """

    def test_sort_key_parameter(self, test_credentials: Session) -> None:
        """export_profiles_page() should send sort_key when provided."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(page=0, sort_key="$last_seen")

        assert captured_body.get("sort_key") == "$last_seen"

    def test_sort_key_omitted_when_none(self, test_credentials: Session) -> None:
        """export_profiles_page() should not send sort_key when None."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(page=0)

        assert "sort_key" not in captured_body

    def test_sort_order_parameter(self, test_credentials: Session) -> None:
        """export_profiles_page() should send sort_order when provided."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(page=0, sort_order="descending")

        assert captured_body.get("sort_order") == "descending"

    def test_sort_order_omitted_when_none(self, test_credentials: Session) -> None:
        """export_profiles_page() should not send sort_order when None."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(page=0)

        assert "sort_order" not in captured_body

    def test_search_parameter(self, test_credentials: Session) -> None:
        """export_profiles_page() should send search when provided."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(page=0, search="alice@example.com")

        assert captured_body.get("search") == "alice@example.com"

    def test_search_omitted_when_none(self, test_credentials: Session) -> None:
        """export_profiles_page() should not send search when None."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(page=0)

        assert "search" not in captured_body

    def test_limit_parameter(self, test_credentials: Session) -> None:
        """export_profiles_page() should send limit when provided."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(page=0, limit=50)

        assert captured_body.get("limit") == 50

    def test_limit_omitted_when_none(self, test_credentials: Session) -> None:
        """export_profiles_page() should not send limit when None."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(page=0)

        assert "limit" not in captured_body

    def test_sort_key_and_sort_order_combined(self, test_credentials: Session) -> None:
        """export_profiles_page() should send both sort_key and sort_order together."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(
                page=0,
                sort_key="$last_seen",
                sort_order="descending",
            )

        assert captured_body.get("sort_key") == "$last_seen"
        assert captured_body.get("sort_order") == "descending"

    def test_all_new_params_combined(self, test_credentials: Session) -> None:
        """export_profiles_page() should send all new parameters together."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "results": [{"$distinct_id": "u1"}],
                    "session_id": "sess_1",
                    "total": 100,
                    "page_size": 50,
                },
            )

        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(
                page=0,
                sort_key="$created",
                sort_order="ascending",
                search="bob",
                limit=25,
                filter_by_cohort='{"id": 789}',
            )

        assert captured_body.get("sort_key") == "$created"
        assert captured_body.get("sort_order") == "ascending"
        assert captured_body.get("search") == "bob"
        assert captured_body.get("limit") == 25
        assert "filter_by_cohort" in captured_body

    def test_new_params_coexist_with_existing_params(
        self, test_credentials: Session
    ) -> None:
        """New parameters should coexist with existing where and output_properties."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(
                page=0,
                where='properties["plan"] == "premium"',
                output_properties=["$name", "$email"],
                sort_key="$last_seen",
                search="test",
            )

        assert captured_body.get("where") == 'properties["plan"] == "premium"'
        assert captured_body.get("output_properties") == '["$name", "$email"]'
        assert captured_body.get("sort_key") == "$last_seen"
        assert captured_body.get("search") == "test"


# =============================================================================
# T006c: filter_by_cohort format support
# =============================================================================


class TestExportProfilesPageFilterByCohort:
    """Tests for filter_by_cohort parameter formats (T006c).

    Verifies that export_profiles_page() passes filter_by_cohort as a
    pre-encoded JSON string and supports both {"id": N} and
    {"raw_cohort": {...}} formats.
    """

    def test_filter_by_cohort_id_format(self, test_credentials: Session) -> None:
        """filter_by_cohort should accept {"id": N} format as JSON string."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        cohort_filter = json.dumps({"id": 42})
        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(page=0, filter_by_cohort=cohort_filter)

        raw = captured_body.get("filter_by_cohort")
        assert raw is not None
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        assert parsed == {"id": 42}

    def test_filter_by_cohort_raw_cohort_format(
        self, test_credentials: Session
    ) -> None:
        """filter_by_cohort should accept {"raw_cohort": {...}} format."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        raw_cohort = {
            "raw_cohort": {
                "and_batch": [
                    {
                        "event_selectors": [{"event": "Purchase"}],
                        "filter_type": "selector",
                    }
                ]
            }
        }
        cohort_filter = json.dumps(raw_cohort)
        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(page=0, filter_by_cohort=cohort_filter)

        raw = captured_body.get("filter_by_cohort")
        assert raw is not None
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        assert "raw_cohort" in parsed
        assert (
            parsed["raw_cohort"]["and_batch"][0]["event_selectors"][0]["event"]
            == "Purchase"
        )

    def test_filter_by_cohort_omitted_when_none(
        self, test_credentials: Session
    ) -> None:
        """filter_by_cohort should not be sent when None."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(page=0)

        assert "filter_by_cohort" not in captured_body

    def test_filter_by_cohort_does_not_conflict_with_cohort_id(
        self, test_credentials: Session
    ) -> None:
        """filter_by_cohort param should take precedence when both cohort_id and filter_by_cohort are given."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        cohort_filter = json.dumps({"id": 99})
        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(
                page=0,
                cohort_id="123",
                filter_by_cohort=cohort_filter,
            )

        raw = captured_body.get("filter_by_cohort")
        assert raw is not None
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        # filter_by_cohort should win over cohort_id
        assert parsed.get("id") == 99

    def test_filter_by_cohort_passthrough_preserves_json(
        self, test_credentials: Session
    ) -> None:
        """filter_by_cohort should be passed through as-is without re-encoding."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"results": [], "session_id": None, "total": 0, "page_size": 1000},
            )

        # Already JSON-encoded string
        cohort_filter = '{"id": 55}'
        with _create_mock_client(test_credentials, handler) as client:
            client.export_profiles_page(page=0, filter_by_cohort=cohort_filter)

        raw = captured_body.get("filter_by_cohort")
        assert raw is not None
        # Should be passthrough — the value should be the JSON string itself
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        assert parsed == {"id": 55}
