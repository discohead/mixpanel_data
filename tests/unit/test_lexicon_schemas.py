"""Unit tests for Lexicon Schemas API.

Tests cover:
- API client methods: get_schemas(), get_schema()
- Discovery service methods: list_schemas(), get_schema()
- Parser functions: _parse_lexicon_metadata(), _parse_lexicon_property(),
  _parse_lexicon_definition(), _parse_lexicon_schema()
- Type classes: LexiconMetadata, LexiconProperty, LexiconDefinition, LexiconSchema
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from mixpanel_data._internal.api_client import ENDPOINTS
from mixpanel_data._internal.services.discovery import (
    DiscoveryService,
    _parse_lexicon_definition,
    _parse_lexicon_metadata,
    _parse_lexicon_property,
    _parse_lexicon_schema,
)
from mixpanel_data.exceptions import AuthenticationError, QueryError
from mixpanel_data.types import (
    LexiconDefinition,
    LexiconMetadata,
    LexiconProperty,
    LexiconSchema,
)

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient


# =============================================================================
# ENDPOINTS Configuration Tests
# =============================================================================


class TestEndpointsApp:
    """Test ENDPOINTS configuration for app API."""

    def test_us_app_endpoint_defined(self) -> None:
        """US app endpoint should be defined."""
        assert "app" in ENDPOINTS["us"]
        assert ENDPOINTS["us"]["app"] == "https://mixpanel.com/api/app"

    def test_eu_app_endpoint_defined(self) -> None:
        """EU app endpoint should be defined."""
        assert "app" in ENDPOINTS["eu"]
        assert ENDPOINTS["eu"]["app"] == "https://eu.mixpanel.com/api/app"

    def test_india_app_endpoint_defined(self) -> None:
        """India app endpoint should be defined."""
        assert "app" in ENDPOINTS["in"]
        assert ENDPOINTS["in"]["app"] == "https://in.mixpanel.com/api/app"


# =============================================================================
# Parser Function Tests
# =============================================================================


class TestParseLexiconMetadata:
    """Tests for _parse_lexicon_metadata()."""

    def test_parse_metadata_with_com_mixpanel(self) -> None:
        """Should parse metadata from com.mixpanel key."""
        data = {
            "com.mixpanel": {
                "$source": "api",
                "displayName": "Purchase Event",
                "tags": ["core", "monetization"],
                "hidden": False,
                "dropped": False,
                "contacts": ["owner@example.com"],
                "teamContacts": ["analytics"],
            }
        }
        result = _parse_lexicon_metadata(data)
        assert result is not None
        assert result.source == "api"
        assert result.display_name == "Purchase Event"
        assert result.tags == ["core", "monetization"]
        assert result.hidden is False
        assert result.dropped is False
        assert result.contacts == ["owner@example.com"]
        assert result.team_contacts == ["analytics"]

    def test_parse_metadata_with_missing_fields(self) -> None:
        """Should use defaults for missing fields."""
        data = {"com.mixpanel": {"displayName": "Test"}}
        result = _parse_lexicon_metadata(data)
        assert result is not None
        assert result.source is None
        assert result.display_name == "Test"
        assert result.tags == []
        assert result.hidden is False
        assert result.dropped is False
        assert result.contacts == []
        assert result.team_contacts == []

    def test_parse_metadata_with_none(self) -> None:
        """Should return None for None input."""
        assert _parse_lexicon_metadata(None) is None

    def test_parse_metadata_with_empty_dict(self) -> None:
        """Should return None for empty dict."""
        assert _parse_lexicon_metadata({}) is None

    def test_parse_metadata_without_com_mixpanel(self) -> None:
        """Should return None if no com.mixpanel key."""
        data = {"other": "value"}
        assert _parse_lexicon_metadata(data) is None


class TestParseLexiconProperty:
    """Tests for _parse_lexicon_property()."""

    def test_parse_property_basic(self) -> None:
        """Should parse basic property definition."""
        data = {"type": "string", "description": "User's country"}
        result = _parse_lexicon_property(data)
        assert result.type == "string"
        assert result.description == "User's country"
        assert result.metadata is None

    def test_parse_property_with_metadata(self) -> None:
        """Should parse property with metadata."""
        data = {
            "type": "number",
            "description": "Purchase amount",
            "metadata": {
                "com.mixpanel": {
                    "displayName": "Amount",
                    "hidden": False,
                }
            },
        }
        result = _parse_lexicon_property(data)
        assert result.type == "number"
        assert result.metadata is not None
        assert result.metadata.display_name == "Amount"

    def test_parse_property_defaults_to_string(self) -> None:
        """Should default to string type if not specified."""
        data: dict[str, Any] = {}
        result = _parse_lexicon_property(data)
        assert result.type == "string"
        assert result.description is None


class TestParseLexiconDefinition:
    """Tests for _parse_lexicon_definition()."""

    def test_parse_definition_with_properties(self) -> None:
        """Should parse definition with properties."""
        data = {
            "description": "User completed a purchase",
            "properties": {
                "amount": {"type": "number", "description": "Purchase amount"},
                "currency": {"type": "string", "description": "Currency code"},
            },
        }
        result = _parse_lexicon_definition(data)
        assert result.description == "User completed a purchase"
        assert len(result.properties) == 2
        assert "amount" in result.properties
        assert result.properties["amount"].type == "number"

    def test_parse_definition_with_metadata(self) -> None:
        """Should parse definition with metadata."""
        data = {
            "properties": {},
            "metadata": {
                "com.mixpanel": {
                    "displayName": "Purchase",
                    "tags": ["core"],
                }
            },
        }
        result = _parse_lexicon_definition(data)
        assert result.metadata is not None
        assert result.metadata.display_name == "Purchase"
        assert result.metadata.tags == ["core"]

    def test_parse_definition_empty(self) -> None:
        """Should parse empty definition."""
        result = _parse_lexicon_definition({})
        assert result.description is None
        assert result.properties == {}
        assert result.metadata is None


class TestParseLexiconSchema:
    """Tests for _parse_lexicon_schema()."""

    def test_parse_schema_event(self) -> None:
        """Should parse event schema."""
        data = {
            "entityType": "event",
            "name": "Purchase",
            "schemaJson": {
                "description": "User completed a purchase",
                "properties": {
                    "amount": {"type": "number"},
                },
            },
        }
        result = _parse_lexicon_schema(data)
        assert result.entity_type == "event"
        assert result.name == "Purchase"
        assert result.schema_json.description == "User completed a purchase"
        assert "amount" in result.schema_json.properties

    def test_parse_schema_profile(self) -> None:
        """Should parse profile schema."""
        data = {
            "entityType": "profile",
            "name": "Plan Type",
            "schemaJson": {
                "properties": {
                    "plan": {"type": "string"},
                },
            },
        }
        result = _parse_lexicon_schema(data)
        assert result.entity_type == "profile"
        assert result.name == "Plan Type"


# =============================================================================
# Type Classes Tests
# =============================================================================


class TestLexiconMetadata:
    """Tests for LexiconMetadata dataclass."""

    def test_frozen(self) -> None:
        """LexiconMetadata should be immutable."""
        metadata = LexiconMetadata(
            source="api",
            display_name="Test",
            tags=[],
            hidden=False,
            dropped=False,
            contacts=[],
            team_contacts=[],
        )
        with pytest.raises(AttributeError):
            metadata.source = "new"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        """to_dict() should serialize all fields."""
        metadata = LexiconMetadata(
            source="api",
            display_name="Test Event",
            tags=["core"],
            hidden=True,
            dropped=False,
            contacts=["test@example.com"],
            team_contacts=["analytics"],
        )
        result = metadata.to_dict()
        assert result == {
            "source": "api",
            "display_name": "Test Event",
            "tags": ["core"],
            "hidden": True,
            "dropped": False,
            "contacts": ["test@example.com"],
            "team_contacts": ["analytics"],
        }


class TestLexiconProperty:
    """Tests for LexiconProperty dataclass."""

    def test_frozen(self) -> None:
        """LexiconProperty should be immutable."""
        prop = LexiconProperty(type="string", description=None, metadata=None)
        with pytest.raises(AttributeError):
            prop.type = "number"  # type: ignore[misc]

    def test_to_dict_minimal(self) -> None:
        """to_dict() should include only type for minimal property."""
        prop = LexiconProperty(type="boolean", description=None, metadata=None)
        result = prop.to_dict()
        assert result == {"type": "boolean"}

    def test_to_dict_with_description(self) -> None:
        """to_dict() should include description if present."""
        prop = LexiconProperty(
            type="string",
            description="User's country",
            metadata=None,
        )
        result = prop.to_dict()
        assert result == {"type": "string", "description": "User's country"}


class TestLexiconDefinition:
    """Tests for LexiconDefinition dataclass."""

    def test_frozen(self) -> None:
        """LexiconDefinition should be immutable."""
        definition = LexiconDefinition(description=None, properties={}, metadata=None)
        with pytest.raises(AttributeError):
            definition.description = "New"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        """to_dict() should serialize correctly."""
        prop = LexiconProperty(type="number", description="Amount", metadata=None)
        definition = LexiconDefinition(
            description="Purchase event",
            properties={"amount": prop},
            metadata=None,
        )
        result = definition.to_dict()
        assert result == {
            "description": "Purchase event",
            "properties": {
                "amount": {"type": "number", "description": "Amount"},
            },
        }


class TestLexiconSchema:
    """Tests for LexiconSchema dataclass."""

    def test_frozen(self) -> None:
        """LexiconSchema should be immutable."""
        definition = LexiconDefinition(description=None, properties={}, metadata=None)
        schema = LexiconSchema(
            entity_type="event",
            name="Test",
            schema_json=definition,
        )
        with pytest.raises(AttributeError):
            schema.name = "New"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        """to_dict() should serialize correctly."""
        definition = LexiconDefinition(
            description="Test event",
            properties={},
            metadata=None,
        )
        schema = LexiconSchema(
            entity_type="event",
            name="Test Event",
            schema_json=definition,
        )
        result = schema.to_dict()
        assert result == {
            "entity_type": "event",
            "name": "Test Event",
            "schema_json": {
                "description": "Test event",
                "properties": {},
            },
        }


# =============================================================================
# API Client Tests
# =============================================================================


@pytest.fixture
def discovery_factory(
    request: pytest.FixtureRequest,
    mock_client_factory: Callable[
        [Callable[[httpx.Request], httpx.Response]], MixpanelAPIClient
    ],
) -> Callable[[Callable[[httpx.Request], httpx.Response]], DiscoveryService]:
    """Factory for creating DiscoveryService with mock API client."""
    clients: list[MixpanelAPIClient] = []

    def factory(
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> DiscoveryService:
        client = mock_client_factory(handler)
        client.__enter__()
        clients.append(client)
        return DiscoveryService(client)

    def cleanup() -> None:
        for client in clients:
            client.__exit__(None, None, None)

    request.addfinalizer(cleanup)
    return factory


class TestAPIClientGetSchemas:
    """Tests for MixpanelAPIClient.get_schemas()."""

    def test_get_schemas_returns_list(
        self,
        mock_client_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], MixpanelAPIClient
        ],
    ) -> None:
        """get_schemas() should return list of schema dicts."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "entityType": "event",
                            "name": "Purchase",
                            "schemaJson": {"properties": {}},
                        },
                    ]
                },
            )

        client = mock_client_factory(handler)
        with client:
            schemas = client.get_schemas()
            assert len(schemas) == 1
            assert schemas[0]["name"] == "Purchase"

    def test_get_schemas_with_entity_type_filter(
        self,
        mock_client_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], MixpanelAPIClient
        ],
    ) -> None:
        """get_schemas() should include entityType in URL path."""

        def handler(request: httpx.Request) -> httpx.Response:
            # entity_type is a path parameter, not query parameter
            # URL: /api/app/projects/{projectId}/schemas/{entity_type}
            assert "/schemas/event" in str(request.url)
            return httpx.Response(200, json={"results": []})

        client = mock_client_factory(handler)
        with client:
            client.get_schemas(entity_type="event")

    def test_get_schemas_empty_results(
        self,
        mock_client_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], MixpanelAPIClient
        ],
    ) -> None:
        """get_schemas() should handle empty results."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"results": []})

        client = mock_client_factory(handler)
        with client:
            schemas = client.get_schemas()
            assert schemas == []


class TestAPIClientGetSchema:
    """Tests for MixpanelAPIClient.get_schema()."""

    def test_get_schema_returns_dict(
        self,
        mock_client_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], MixpanelAPIClient
        ],
    ) -> None:
        """get_schema() should return normalized schema dict."""
        # API returns: {status: "ok", results: <schemaJson>}
        # Client normalizes to: {entityType, name, schemaJson}

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"properties": {}},
                },
            )

        client = mock_client_factory(handler)
        with client:
            schema = client.get_schema("event", "Purchase")
            # Client normalizes response to include entityType and name
            assert schema["entityType"] == "event"
            assert schema["name"] == "Purchase"
            assert schema["schemaJson"] == {"properties": {}}

    def test_get_schema_passes_entity_name_param(
        self,
        mock_client_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], MixpanelAPIClient
        ],
    ) -> None:
        """get_schema() should pass entity_name as query param."""

        def handler(request: httpx.Request) -> httpx.Response:
            # entity_name should be passed as query param
            # URL: /schemas/{entity_type}?entity_name={name}
            url_str = str(request.url)
            assert "/schemas/event" in url_str
            # httpx may encode spaces as + or %20
            assert (
                "entity_name=Added+To+Cart" in url_str
                or "entity_name=Added%20To%20Cart" in url_str
            )
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"properties": {}},
                },
            )

        client = mock_client_factory(handler)
        with client:
            client.get_schema("event", "Added To Cart")


# =============================================================================
# Discovery Service Tests
# =============================================================================


class TestDiscoveryServiceListSchemas:
    """Tests for DiscoveryService.list_schemas()."""

    def test_list_schemas_returns_sorted_list(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_schemas() should return schemas sorted by (entity_type, name)."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "entityType": "profile",
                            "name": "Plan",
                            "schemaJson": {"properties": {}},
                        },
                        {
                            "entityType": "event",
                            "name": "Purchase",
                            "schemaJson": {"properties": {}},
                        },
                        {
                            "entityType": "event",
                            "name": "Login",
                            "schemaJson": {"properties": {}},
                        },
                    ]
                },
            )

        discovery = discovery_factory(handler)
        schemas = discovery.list_schemas()

        assert len(schemas) == 3
        # Sorted by (entity_type, name)
        assert schemas[0].entity_type == "event"
        assert schemas[0].name == "Login"
        assert schemas[1].entity_type == "event"
        assert schemas[1].name == "Purchase"
        assert schemas[2].entity_type == "profile"
        assert schemas[2].name == "Plan"

    def test_list_schemas_caching(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_schemas() should cache results."""
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"results": []})

        discovery = discovery_factory(handler)

        discovery.list_schemas()
        assert call_count == 1

        discovery.list_schemas()
        assert call_count == 1  # Still 1, cached

    def test_list_schemas_filter_caching_separate(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_schemas() should cache per entity_type filter."""
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"results": []})

        discovery = discovery_factory(handler)

        discovery.list_schemas()
        assert call_count == 1

        discovery.list_schemas(entity_type="event")
        assert call_count == 2  # Different cache key

        discovery.list_schemas(entity_type="event")
        assert call_count == 2  # Cached

    def test_list_schemas_with_auth_error(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_schemas() should propagate AuthenticationError."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Invalid credentials"})

        discovery = discovery_factory(handler)

        with pytest.raises(AuthenticationError):
            discovery.list_schemas()


class TestDiscoveryServiceGetSchema:
    """Tests for DiscoveryService.get_schema()."""

    def test_get_schema_returns_lexicon_schema(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """get_schema() should return LexiconSchema."""
        # API returns: {status: "ok", results: <schemaJson>}
        # Client normalizes to: {entityType, name, schemaJson}

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "description": "User made a purchase",
                        "properties": {},
                    },
                },
            )

        discovery = discovery_factory(handler)
        schema = discovery.get_schema("event", "Purchase")

        assert isinstance(schema, LexiconSchema)
        assert schema.entity_type == "event"
        assert schema.name == "Purchase"
        assert schema.schema_json.description == "User made a purchase"

    def test_get_schema_caching(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """get_schema() should cache results."""
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"properties": {}},
                },
            )

        discovery = discovery_factory(handler)

        discovery.get_schema("event", "Test")
        assert call_count == 1

        discovery.get_schema("event", "Test")
        assert call_count == 1  # Cached

    def test_get_schema_with_query_error(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """get_schema() should propagate QueryError for not found."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "Schema not found"})

        discovery = discovery_factory(handler)

        with pytest.raises(QueryError):
            discovery.get_schema("event", "NonExistent")
