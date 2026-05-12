# ruff: noqa: ARG001
# mypy: warn-unused-ignores=false
"""Tests for Phase 027 Data Governance types.

Tests round-trip serialization, frozen immutability, extra field preservation,
exclude_none behavior, enum values, and validation for all data governance types.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from mixpanel_headless.types import (
    BulkEventUpdate,
    BulkPropertyUpdate,
    BulkUpdateEventsParams,
    BulkUpdatePropertiesParams,
    ComposedPropertyValue,
    CreateCustomEventParams,
    CreateCustomPropertyParams,
    CreateDropFilterParams,
    CreateTagParams,
    CustomEvent,
    CustomEventAlternative,
    CustomProperty,
    CustomPropertyResourceType,
    DropFilter,
    DropFilterLimitsResponse,
    EventDefinition,
    LexiconTag,
    LookupTable,
    LookupTableUploadUrl,
    MarkLookupTableReadyParams,
    PropertyDefinition,
    PropertyResourceType,
    UpdateCustomPropertyParams,
    UpdateDropFilterParams,
    UpdateEventDefinitionParams,
    UpdateLookupTableParams,
    UpdatePropertyDefinitionParams,
    UpdateTagParams,
    UploadLookupTableParams,
)

# =============================================================================
# Enum Tests
# =============================================================================


class TestPropertyResourceTypeEnum:
    """Tests for PropertyResourceType enum values."""

    def test_event_value(self) -> None:
        """PropertyResourceType.EVENT has value 'event'."""
        assert PropertyResourceType.EVENT.value == "event"

    def test_user_value(self) -> None:
        """PropertyResourceType.USER has value 'user'."""
        assert PropertyResourceType.USER.value == "user"

    def test_groupprofile_value(self) -> None:
        """PropertyResourceType.GROUPPROFILE has value 'groupprofile'."""
        assert PropertyResourceType.GROUPPROFILE.value == "groupprofile"

    def test_is_str_subclass(self) -> None:
        """PropertyResourceType members are also strings."""
        assert isinstance(PropertyResourceType.EVENT, str)

    def test_all_members(self) -> None:
        """PropertyResourceType has exactly three members."""
        assert len(PropertyResourceType) == 3


class TestCustomPropertyResourceTypeEnum:
    """Tests for CustomPropertyResourceType enum values."""

    def test_events_value(self) -> None:
        """CustomPropertyResourceType.EVENTS has value 'events'."""
        assert CustomPropertyResourceType.EVENTS.value == "events"

    def test_people_value(self) -> None:
        """CustomPropertyResourceType.PEOPLE has value 'people'."""
        assert CustomPropertyResourceType.PEOPLE.value == "people"

    def test_group_profiles_value(self) -> None:
        """CustomPropertyResourceType.GROUP_PROFILES has value 'group_profiles'."""
        assert CustomPropertyResourceType.GROUP_PROFILES.value == "group_profiles"

    def test_is_str_subclass(self) -> None:
        """CustomPropertyResourceType members are also strings."""
        assert isinstance(CustomPropertyResourceType.EVENTS, str)

    def test_all_members(self) -> None:
        """CustomPropertyResourceType has exactly three members."""
        assert len(CustomPropertyResourceType) == 3


# =============================================================================
# EventDefinition Model Tests
# =============================================================================


class TestEventDefinitionModel:
    """Tests for EventDefinition Pydantic model."""

    def test_required_fields(self) -> None:
        """EventDefinition requires id and name."""
        event = EventDefinition(id=1, name="Signup")
        assert event.id == 1
        assert event.name == "Signup"
        assert event.display_name is None
        assert event.description is None
        assert event.hidden is None
        assert event.dropped is None
        assert event.merged is None
        assert event.verified is None
        assert event.tags is None
        assert event.custom_event_id is None
        assert event.last_modified is None
        assert event.status is None
        assert event.platforms is None
        assert event.created_utc is None
        assert event.modified_utc is None

    def test_all_fields(self) -> None:
        """EventDefinition with all fields stores correctly."""
        event = EventDefinition(
            id=1,
            name="Signup",
            display_name="User Signup",
            description="A user signed up",
            hidden=False,
            dropped=False,
            merged=False,
            verified=True,
            tags=["core", "acquisition"],
            custom_event_id=42,
            last_modified="2026-01-01T00:00:00Z",
            status="active",
            platforms=["web", "ios"],
            created_utc="2025-01-01T00:00:00Z",
            modified_utc="2026-01-01T00:00:00Z",
        )
        assert event.display_name == "User Signup"
        assert event.description == "A user signed up"
        assert event.hidden is False
        assert event.verified is True
        assert event.tags == ["core", "acquisition"]
        assert event.custom_event_id == 42
        assert event.status == "active"
        assert event.platforms == ["web", "ios"]

    def test_frozen(self) -> None:
        """EventDefinition is frozen and rejects attribute assignment."""
        event = EventDefinition(id=1, name="Signup")
        with pytest.raises(ValidationError):
            event.name = "Login"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """EventDefinition preserves unknown fields via extra='allow'."""
        event = EventDefinition(id=1, name="Signup", unknown_field="foo")
        assert event.model_extra is not None
        assert event.model_extra["unknown_field"] == "foo"

    def test_missing_required_raises(self) -> None:
        """EventDefinition raises ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            EventDefinition(id=1)

    def test_model_validate_api_shape(self) -> None:
        """EventDefinition parses a dict matching API response shape."""
        data: dict[str, Any] = {
            "id": 10,
            "name": "Purchase",
            "display_name": "Purchase Event",
            "hidden": False,
            "tags": ["revenue"],
        }
        event = EventDefinition.model_validate(data)
        assert event.id == 10
        assert event.name == "Purchase"
        assert event.tags == ["revenue"]


# =============================================================================
# PropertyDefinition Model Tests
# =============================================================================


class TestPropertyDefinitionModel:
    """Tests for PropertyDefinition Pydantic model."""

    def test_required_fields(self) -> None:
        """PropertyDefinition requires id and name."""
        prop = PropertyDefinition(id=1, name="$browser")
        assert prop.id == 1
        assert prop.name == "$browser"
        assert prop.resource_type is None
        assert prop.description is None
        assert prop.hidden is None
        assert prop.dropped is None
        assert prop.merged is None
        assert prop.sensitive is None
        assert prop.data_group_id is None

    def test_all_fields(self) -> None:
        """PropertyDefinition with all fields stores correctly."""
        prop = PropertyDefinition(
            id=1,
            name="$browser",
            resource_type="event",
            description="Browser name",
            hidden=False,
            dropped=False,
            merged=False,
            sensitive=False,
            data_group_id="group-1",
        )
        assert prop.resource_type == "event"
        assert prop.description == "Browser name"
        assert prop.sensitive is False
        assert prop.data_group_id == "group-1"

    def test_frozen(self) -> None:
        """PropertyDefinition is frozen and rejects attribute assignment."""
        prop = PropertyDefinition(id=1, name="$browser")
        with pytest.raises(ValidationError):
            prop.name = "$os"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """PropertyDefinition preserves unknown fields via extra='allow'."""
        prop = PropertyDefinition(id=1, name="$browser", custom="value")
        assert prop.model_extra is not None
        assert prop.model_extra["custom"] == "value"

    def test_missing_required_raises(self) -> None:
        """PropertyDefinition raises ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            PropertyDefinition(id=1)


# =============================================================================
# UpdateEventDefinitionParams Tests
# =============================================================================


class TestUpdateEventDefinitionParams:
    """Tests for UpdateEventDefinitionParams Pydantic model."""

    def test_all_none_defaults(self) -> None:
        """UpdateEventDefinitionParams defaults all fields to None."""
        params = UpdateEventDefinitionParams()
        assert params.hidden is None
        assert params.dropped is None
        assert params.merged is None
        assert params.verified is None
        assert params.tags is None
        assert params.description is None

    def test_exclude_none_empty(self) -> None:
        """UpdateEventDefinitionParams with no fields produces empty dict."""
        params = UpdateEventDefinitionParams()
        data = params.model_dump(exclude_none=True)
        assert data == {}

    def test_partial_update(self) -> None:
        """UpdateEventDefinitionParams serializes only provided fields."""
        params = UpdateEventDefinitionParams(hidden=True, tags=["important"])
        data = params.model_dump(exclude_none=True)
        assert data == {"hidden": True, "tags": ["important"]}

    def test_all_fields(self) -> None:
        """UpdateEventDefinitionParams with all fields populated stores correctly."""
        params = UpdateEventDefinitionParams(
            hidden=True,
            dropped=False,
            merged=False,
            verified=True,
            tags=["core"],
            description="Updated description",
        )
        data = params.model_dump(exclude_none=True)
        assert data["hidden"] is True
        assert data["verified"] is True
        assert data["description"] == "Updated description"


# =============================================================================
# CustomEventAlternative Tests
# =============================================================================


class TestCustomEventAlternative:
    """Tests for the CustomEventAlternative Pydantic model."""

    def test_construction_with_event_name(self) -> None:
        """CustomEventAlternative stores the underlying event name."""
        alt = CustomEventAlternative(event="Login")
        assert alt.event == "Login"

    def test_serialization_round_trip(self) -> None:
        """CustomEventAlternative serializes to the API's {event: ...} shape."""
        alt = CustomEventAlternative(event="Login")
        assert alt.model_dump() == {"event": "Login"}

    def test_extra_fields_allowed_for_forward_compat(self) -> None:
        """CustomEventAlternative tolerates unknown fields from server."""
        alt = CustomEventAlternative.model_validate(
            {"event": "X", "selector": {"foo": "bar"}}
        )
        assert alt.event == "X"

    def test_frozen_immutable(self) -> None:
        """CustomEventAlternative is frozen (cannot mutate after construction)."""
        alt = CustomEventAlternative(event="X")
        with pytest.raises(ValidationError):
            alt.event = "Y"  # type: ignore[misc]

    def test_missing_event_rejected(self) -> None:
        """CustomEventAlternative requires the event field."""
        with pytest.raises(ValidationError):
            CustomEventAlternative()  # type: ignore[call-arg]

    def test_empty_event_rejected(self) -> None:
        """CustomEventAlternative rejects empty event names."""
        with pytest.raises(ValidationError):
            CustomEventAlternative(event="")


# =============================================================================
# CustomEvent Tests
# =============================================================================


class TestCustomEventModel:
    """Tests for the CustomEvent Pydantic model."""

    def test_construction_with_required_fields(self) -> None:
        """CustomEvent stores id, name, and alternatives."""
        ce = CustomEvent(
            id=42,
            name="Page View",
            alternatives=[
                CustomEventAlternative(event="Home Viewed"),
                CustomEventAlternative(event="Product Viewed"),
            ],
        )
        assert ce.id == 42
        assert ce.name == "Page View"
        assert len(ce.alternatives) == 2
        assert ce.alternatives[0].event == "Home Viewed"

    def test_alternatives_default_empty(self) -> None:
        """CustomEvent allows construction without alternatives (default empty list)."""
        ce = CustomEvent(id=1, name="X")
        assert ce.alternatives == []

    def test_alternatives_parse_from_dict_form(self) -> None:
        """CustomEvent parses alternatives from the [{event: ...}] dict shape."""
        ce = CustomEvent.model_validate(
            {
                "id": 1,
                "name": "X",
                "alternatives": [{"event": "Y"}, {"event": "Z"}],
            }
        )
        assert [a.event for a in ce.alternatives] == ["Y", "Z"]

    def test_accepts_extra_fields_for_forward_compatibility(self) -> None:
        """CustomEvent tolerates extra server-side fields without breaking."""
        ce = CustomEvent.model_validate(
            {
                "id": 1,
                "name": "X",
                "alternatives": [{"event": "Y"}],
                "creator_id": 99,
                "created": "2024-01-01",
                "description": "test",
            }
        )
        assert ce.id == 1
        assert ce.name == "X"

    def test_model_validate_from_snake_case_dict(self) -> None:
        """CustomEvent.model_validate parses the snake_case API response shape."""
        ce = CustomEvent.model_validate({"id": 5, "name": "Y", "alternatives": []})
        assert ce.id == 5
        assert ce.name == "Y"
        assert ce.alternatives == []

    def test_frozen_immutable(self) -> None:
        """CustomEvent is frozen (cannot mutate after construction)."""
        ce = CustomEvent(id=1, name="X")
        with pytest.raises(ValidationError):
            ce.name = "Y"  # type: ignore[misc]

    def test_missing_id_rejected(self) -> None:
        """CustomEvent requires the id field."""
        with pytest.raises(ValidationError):
            CustomEvent(name="X")  # type: ignore[call-arg]

    def test_missing_name_rejected(self) -> None:
        """CustomEvent requires the name field."""
        with pytest.raises(ValidationError):
            CustomEvent(id=1)  # type: ignore[call-arg]


# =============================================================================
# CreateCustomEventParams Tests
# =============================================================================


class TestCreateCustomEventParams:
    """Tests for the CreateCustomEventParams Pydantic model."""

    def test_construction_with_string_alternatives(self) -> None:
        """CreateCustomEventParams accepts a list of bare event names."""
        p = CreateCustomEventParams(
            name="Page View", alternatives=["Home Viewed", "Product Viewed"]
        )
        assert p.name == "Page View"
        assert p.alternatives == ["Home Viewed", "Product Viewed"]

    def test_to_form_body_serializes_alternatives_as_json(self) -> None:
        """to_form_body() emits alternatives as JSON list of {event: name} dicts."""
        import json as _json

        p = CreateCustomEventParams(name="Page View", alternatives=["A", "B"])
        body = p.to_form_body()
        assert body["name"] == "Page View"
        decoded = _json.loads(body["alternatives"])
        assert decoded == [{"event": "A"}, {"event": "B"}]

    def test_to_form_body_returns_strings_only(self) -> None:
        """to_form_body() values must be strings (form-encoding requirement)."""
        body = CreateCustomEventParams(name="X", alternatives=["A"]).to_form_body()
        assert all(isinstance(v, str) for v in body.values())

    def test_to_form_body_preserves_alternative_order(self) -> None:
        """to_form_body() preserves the order of alternatives."""
        import json as _json

        p = CreateCustomEventParams(name="X", alternatives=["C", "A", "B"])
        decoded = _json.loads(p.to_form_body()["alternatives"])
        assert [d["event"] for d in decoded] == ["C", "A", "B"]

    def test_empty_name_rejected(self) -> None:
        """CreateCustomEventParams rejects empty names."""
        with pytest.raises(ValidationError):
            CreateCustomEventParams(name="", alternatives=["A"])

    def test_empty_alternatives_rejected(self) -> None:
        """CreateCustomEventParams rejects empty alternative lists."""
        with pytest.raises(ValidationError):
            CreateCustomEventParams(name="X", alternatives=[])

    def test_empty_string_alternative_rejected(self) -> None:
        """CreateCustomEventParams rejects empty-string alternatives."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCustomEventParams(name="X", alternatives=[""])
        assert "empty" in str(exc_info.value).lower()

    def test_whitespace_only_alternative_rejected(self) -> None:
        """CreateCustomEventParams rejects whitespace-only alternatives."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCustomEventParams(name="X", alternatives=["   "])
        assert (
            "empty" in str(exc_info.value).lower()
            or "whitespace" in str(exc_info.value).lower()
        )

    def test_duplicate_alternatives_rejected(self) -> None:
        """CreateCustomEventParams rejects duplicate alternative entries."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCustomEventParams(name="X", alternatives=["A", "A"])
        assert "unique" in str(exc_info.value).lower()

    def test_frozen_immutable(self) -> None:
        """CreateCustomEventParams is frozen (cannot mutate after construction)."""
        p = CreateCustomEventParams(name="X", alternatives=["A"])
        with pytest.raises(ValidationError):
            p.name = "Y"  # type: ignore[misc]


# =============================================================================
# UpdatePropertyDefinitionParams Tests
# =============================================================================


class TestUpdatePropertyDefinitionParams:
    """Tests for UpdatePropertyDefinitionParams Pydantic model."""

    def test_all_none_defaults(self) -> None:
        """UpdatePropertyDefinitionParams defaults all fields to None."""
        params = UpdatePropertyDefinitionParams()
        assert params.hidden is None
        assert params.dropped is None
        assert params.merged is None
        assert params.sensitive is None
        assert params.description is None

    def test_exclude_none_empty(self) -> None:
        """UpdatePropertyDefinitionParams with no fields produces empty dict."""
        params = UpdatePropertyDefinitionParams()
        data = params.model_dump(exclude_none=True)
        assert data == {}

    def test_partial_update(self) -> None:
        """UpdatePropertyDefinitionParams serializes only provided fields."""
        params = UpdatePropertyDefinitionParams(sensitive=True)
        data = params.model_dump(exclude_none=True)
        assert data == {"sensitive": True}

    def test_all_fields(self) -> None:
        """UpdatePropertyDefinitionParams with all fields populated."""
        params = UpdatePropertyDefinitionParams(
            hidden=True,
            dropped=False,
            merged=False,
            sensitive=True,
            description="PII field",
        )
        data = params.model_dump(exclude_none=True)
        assert data["sensitive"] is True
        assert data["description"] == "PII field"


# =============================================================================
# BulkEventUpdate Tests
# =============================================================================


class TestBulkEventUpdateModel:
    """Tests for BulkEventUpdate Pydantic model."""

    def test_minimal(self) -> None:
        """BulkEventUpdate with no fields defaults all to None."""
        update = BulkEventUpdate()
        assert update.name is None
        assert update.id is None
        assert update.hidden is None
        assert update.dropped is None
        assert update.merged is None
        assert update.verified is None
        assert update.tags is None
        assert update.contacts is None
        assert update.team_contacts is None

    def test_all_fields(self) -> None:
        """BulkEventUpdate with all fields stores correctly."""
        update = BulkEventUpdate(
            name="Signup",
            id=42,
            hidden=False,
            dropped=False,
            merged=False,
            verified=True,
            tags=["core"],
            contacts=["alice@co.com"],
            team_contacts=["team@co.com"],
        )
        assert update.name == "Signup"
        assert update.id == 42
        assert update.tags == ["core"]
        assert update.contacts == ["alice@co.com"]

    def test_model_dump(self) -> None:
        """BulkEventUpdate serializes correctly."""
        update = BulkEventUpdate(name="Signup", hidden=True)
        data = update.model_dump(exclude_none=True)
        assert data == {"name": "Signup", "hidden": True}


# =============================================================================
# BulkUpdateEventsParams Tests
# =============================================================================


class TestBulkUpdateEventsParams:
    """Tests for BulkUpdateEventsParams Pydantic model."""

    def test_required_fields(self) -> None:
        """BulkUpdateEventsParams requires events list."""
        params = BulkUpdateEventsParams(
            events=[BulkEventUpdate(name="Signup", hidden=True)]
        )
        assert len(params.events) == 1
        assert params.events[0].name == "Signup"

    def test_missing_required_raises(self) -> None:
        """BulkUpdateEventsParams raises ValidationError when events missing."""
        with pytest.raises(ValidationError):
            BulkUpdateEventsParams()  # type: ignore[call-arg]

    def test_model_dump(self) -> None:
        """BulkUpdateEventsParams serializes correctly."""
        params = BulkUpdateEventsParams(
            events=[
                BulkEventUpdate(name="Signup", hidden=True),
                BulkEventUpdate(name="Login", verified=True),
            ]
        )
        data = params.model_dump(exclude_none=True)
        assert len(data["events"]) == 2


# =============================================================================
# BulkPropertyUpdate Tests
# =============================================================================


class TestBulkPropertyUpdateModel:
    """Tests for BulkPropertyUpdate Pydantic model."""

    def test_required_fields(self) -> None:
        """BulkPropertyUpdate requires name and resource_type."""
        update = BulkPropertyUpdate(name="$browser", resource_type="event")
        assert update.name == "$browser"
        assert update.resource_type == "event"
        assert update.id is None
        assert update.hidden is None
        assert update.dropped is None
        assert update.sensitive is None
        assert update.data_group_id is None

    def test_all_fields(self) -> None:
        """BulkPropertyUpdate with all fields stores correctly."""
        update = BulkPropertyUpdate(
            name="$browser",
            resource_type="event",
            id=99,
            hidden=False,
            dropped=False,
            sensitive=True,
            data_group_id="group-1",
        )
        assert update.id == 99
        assert update.sensitive is True
        assert update.data_group_id == "group-1"

    def test_missing_required_raises(self) -> None:
        """BulkPropertyUpdate raises ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            BulkPropertyUpdate(name="$browser")


# =============================================================================
# BulkUpdatePropertiesParams Tests
# =============================================================================


class TestBulkUpdatePropertiesParams:
    """Tests for BulkUpdatePropertiesParams Pydantic model."""

    def test_required_fields(self) -> None:
        """BulkUpdatePropertiesParams requires properties list."""
        params = BulkUpdatePropertiesParams(
            properties=[
                BulkPropertyUpdate(name="$browser", resource_type="event", hidden=True)
            ]
        )
        assert len(params.properties) == 1

    def test_missing_required_raises(self) -> None:
        """BulkUpdatePropertiesParams raises ValidationError when properties missing."""
        with pytest.raises(ValidationError):
            BulkUpdatePropertiesParams()  # type: ignore[call-arg]


# =============================================================================
# LexiconTag Model Tests
# =============================================================================


class TestLexiconTagModel:
    """Tests for LexiconTag Pydantic model."""

    def test_required_fields(self) -> None:
        """LexiconTag requires id and name."""
        tag = LexiconTag(id=1, name="core")
        assert tag.id == 1
        assert tag.name == "core"

    def test_frozen(self) -> None:
        """LexiconTag is frozen and rejects attribute assignment."""
        tag = LexiconTag(id=1, name="core")
        with pytest.raises(ValidationError):
            tag.name = "new"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """LexiconTag preserves unknown fields via extra='allow'."""
        tag = LexiconTag(id=1, name="core", custom="value")
        assert tag.model_extra is not None
        assert tag.model_extra["custom"] == "value"

    def test_missing_required_raises(self) -> None:
        """LexiconTag raises ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            LexiconTag(id=1)


# =============================================================================
# CreateTagParams Tests
# =============================================================================


class TestCreateTagParams:
    """Tests for CreateTagParams Pydantic model."""

    def test_required_fields(self) -> None:
        """CreateTagParams requires name."""
        params = CreateTagParams(name="core")
        assert params.name == "core"

    def test_missing_required_raises(self) -> None:
        """CreateTagParams raises ValidationError when name missing."""
        with pytest.raises(ValidationError):
            CreateTagParams()  # type: ignore[call-arg]

    def test_model_dump(self) -> None:
        """CreateTagParams serializes correctly."""
        params = CreateTagParams(name="revenue")
        data = params.model_dump()
        assert data == {"name": "revenue"}


# =============================================================================
# UpdateTagParams Tests
# =============================================================================


class TestUpdateTagParams:
    """Tests for UpdateTagParams Pydantic model."""

    def test_all_none_defaults(self) -> None:
        """UpdateTagParams defaults name to None."""
        params = UpdateTagParams()
        assert params.name is None

    def test_exclude_none_empty(self) -> None:
        """UpdateTagParams with no fields produces empty dict."""
        params = UpdateTagParams()
        data = params.model_dump(exclude_none=True)
        assert data == {}

    def test_with_name(self) -> None:
        """UpdateTagParams with name serializes correctly."""
        params = UpdateTagParams(name="renamed")
        data = params.model_dump(exclude_none=True)
        assert data == {"name": "renamed"}


# =============================================================================
# DropFilter Model Tests
# =============================================================================


class TestDropFilterModel:
    """Tests for DropFilter Pydantic model."""

    def test_required_fields(self) -> None:
        """DropFilter requires id and event_name."""
        df = DropFilter(id=1, event_name="Signup")
        assert df.id == 1
        assert df.event_name == "Signup"
        assert df.filters is None
        assert df.active is None
        assert df.display_name is None
        assert df.created is None

    def test_all_fields(self) -> None:
        """DropFilter with all fields stores correctly."""
        df = DropFilter(
            id=1,
            event_name="Signup",
            filters=[{"property": "$browser", "value": "Chrome"}],
            active=True,
            display_name="Drop Chrome Signups",
            created="2026-01-01T00:00:00Z",
        )
        assert df.filters == [{"property": "$browser", "value": "Chrome"}]
        assert df.active is True
        assert df.display_name == "Drop Chrome Signups"

    def test_frozen(self) -> None:
        """DropFilter is frozen and rejects attribute assignment."""
        df = DropFilter(id=1, event_name="Signup")
        with pytest.raises(ValidationError):
            df.event_name = "Login"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """DropFilter preserves unknown fields via extra='allow'."""
        df = DropFilter(id=1, event_name="Signup", custom="value")
        assert df.model_extra is not None
        assert df.model_extra["custom"] == "value"

    def test_missing_required_raises(self) -> None:
        """DropFilter raises ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            DropFilter(id=1)


# =============================================================================
# CreateDropFilterParams Tests
# =============================================================================


class TestCreateDropFilterParams:
    """Tests for CreateDropFilterParams Pydantic model."""

    def test_required_fields(self) -> None:
        """CreateDropFilterParams requires event_name and filters."""
        params = CreateDropFilterParams(
            event_name="Signup",
            filters=[{"property": "$browser", "value": "Chrome"}],
        )
        assert params.event_name == "Signup"
        assert params.filters == [{"property": "$browser", "value": "Chrome"}]

    def test_missing_required_raises(self) -> None:
        """CreateDropFilterParams raises ValidationError when fields missing."""
        with pytest.raises(ValidationError):
            CreateDropFilterParams(event_name="Signup")  # type: ignore[call-arg]

    def test_model_dump(self) -> None:
        """CreateDropFilterParams serializes correctly."""
        params = CreateDropFilterParams(
            event_name="Signup", filters={"property": "$browser"}
        )
        data = params.model_dump()
        assert data["event_name"] == "Signup"
        assert data["filters"] == {"property": "$browser"}


# =============================================================================
# UpdateDropFilterParams Tests
# =============================================================================


class TestUpdateDropFilterParams:
    """Tests for UpdateDropFilterParams Pydantic model."""

    def test_required_fields(self) -> None:
        """UpdateDropFilterParams requires id."""
        params = UpdateDropFilterParams(id=1)
        assert params.id == 1
        assert params.event_name is None
        assert params.filters is None
        assert params.active is None

    def test_exclude_none(self) -> None:
        """UpdateDropFilterParams excludes None fields when serializing."""
        params = UpdateDropFilterParams(id=1)
        data = params.model_dump(exclude_none=True)
        assert data == {"id": 1}

    def test_all_fields(self) -> None:
        """UpdateDropFilterParams with all fields stores correctly."""
        params = UpdateDropFilterParams(
            id=1,
            event_name="Login",
            filters=[{"property": "$os"}],
            active=False,
        )
        data = params.model_dump(exclude_none=True)
        assert data["event_name"] == "Login"
        assert data["active"] is False

    def test_missing_required_raises(self) -> None:
        """UpdateDropFilterParams raises ValidationError when id missing."""
        with pytest.raises(ValidationError):
            UpdateDropFilterParams()  # type: ignore[call-arg]


# =============================================================================
# DropFilterLimitsResponse Tests
# =============================================================================


class TestDropFilterLimitsResponseModel:
    """Tests for DropFilterLimitsResponse Pydantic model."""

    def test_required_fields(self) -> None:
        """DropFilterLimitsResponse requires filter_limit."""
        resp = DropFilterLimitsResponse(filter_limit=100)
        assert resp.filter_limit == 100

    def test_frozen(self) -> None:
        """DropFilterLimitsResponse is frozen and rejects attribute assignment."""
        resp = DropFilterLimitsResponse(filter_limit=100)
        with pytest.raises(ValidationError):
            resp.filter_limit = 200  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """DropFilterLimitsResponse preserves unknown fields via extra='allow'."""
        resp = DropFilterLimitsResponse(filter_limit=100, custom="value")
        assert resp.model_extra is not None
        assert resp.model_extra["custom"] == "value"

    def test_missing_required_raises(self) -> None:
        """DropFilterLimitsResponse raises ValidationError when filter_limit missing."""
        with pytest.raises(ValidationError):
            DropFilterLimitsResponse()


# =============================================================================
# ComposedPropertyValue Model Tests
# =============================================================================


class TestComposedPropertyValueModel:
    """Tests for ComposedPropertyValue Pydantic model."""

    def test_required_fields(self) -> None:
        """ComposedPropertyValue requires resource_type."""
        cpv = ComposedPropertyValue(resource_type="events")
        assert cpv.resource_type == "events"
        assert cpv.type is None
        assert cpv.type_cast is None
        assert cpv.behavior is None
        assert cpv.join_property_type is None

    def test_all_fields(self) -> None:
        """ComposedPropertyValue with all fields stores correctly."""
        cpv = ComposedPropertyValue(
            type="string",
            type_cast="number",
            resource_type="events",
            behavior={"type": "count"},
            join_property_type="event",
        )
        assert cpv.type == "string"
        assert cpv.type_cast == "number"
        assert cpv.behavior == {"type": "count"}
        assert cpv.join_property_type == "event"

    def test_frozen(self) -> None:
        """ComposedPropertyValue is frozen and rejects attribute assignment."""
        cpv = ComposedPropertyValue(resource_type="events")
        with pytest.raises(ValidationError):
            cpv.resource_type = "people"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """ComposedPropertyValue preserves unknown fields via extra='allow'."""
        cpv = ComposedPropertyValue(resource_type="events", custom="value")
        assert cpv.model_extra is not None
        assert cpv.model_extra["custom"] == "value"


# =============================================================================
# CustomProperty Model Tests
# =============================================================================


class TestCustomPropertyModel:
    """Tests for CustomProperty Pydantic model."""

    def test_required_fields(self) -> None:
        """CustomProperty requires custom_property_id, name, and resource_type."""
        cp = CustomProperty(
            custom_property_id=1, name="Revenue Per User", resource_type="events"
        )
        assert cp.custom_property_id == 1
        assert cp.name == "Revenue Per User"
        assert cp.resource_type == "events"
        assert cp.description is None
        assert cp.property_type is None
        assert cp.display_formula is None
        assert cp.composed_properties is None
        assert cp.is_locked is None
        assert cp.is_visible is None
        assert cp.data_group_id is None
        assert cp.created is None
        assert cp.modified is None
        assert cp.example_value is None

    def test_all_fields(self) -> None:
        """CustomProperty with all fields stores correctly."""
        cp = CustomProperty(
            custom_property_id=1,
            name="Revenue Per User",
            description="Revenue divided by users",
            resource_type="events",
            property_type="number",
            display_formula="A / B",
            composed_properties={
                "A": ComposedPropertyValue(resource_type="events", type="number"),
                "B": ComposedPropertyValue(resource_type="events", type="number"),
            },
            is_locked=False,
            is_visible=True,
            data_group_id="group-1",
            created="2026-01-01T00:00:00Z",
            modified="2026-03-01T00:00:00Z",
            example_value="42.5",
        )
        assert cp.description == "Revenue divided by users"
        assert cp.property_type == "number"
        assert cp.display_formula == "A / B"
        assert cp.composed_properties is not None
        assert "A" in cp.composed_properties
        assert cp.composed_properties["A"].type == "number"
        assert cp.is_visible is True
        assert cp.example_value == "42.5"

    def test_frozen(self) -> None:
        """CustomProperty is frozen and rejects attribute assignment."""
        cp = CustomProperty(custom_property_id=1, name="Test", resource_type="events")
        with pytest.raises(ValidationError):
            cp.name = "new"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """CustomProperty preserves unknown fields via extra='allow'."""
        cp = CustomProperty(
            custom_property_id=1, name="Test", resource_type="events", custom="value"
        )
        assert cp.model_extra is not None
        assert cp.model_extra["custom"] == "value"

    def test_missing_required_raises(self) -> None:
        """CustomProperty raises ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            CustomProperty(custom_property_id=1, name="Test")

    def test_model_validate_api_shape(self) -> None:
        """CustomProperty parses a dict matching API response shape."""
        data: dict[str, Any] = {
            "custom_property_id": 42,
            "name": "Revenue Per User",
            "resource_type": "events",
            "property_type": "number",
            "display_formula": "A / B",
            "composed_properties": {
                "A": {"resource_type": "events", "type": "number"},
            },
        }
        cp = CustomProperty.model_validate(data)
        assert cp.custom_property_id == 42
        assert cp.composed_properties is not None
        assert cp.composed_properties["A"].resource_type == "events"


# =============================================================================
# CreateCustomPropertyParams Tests
# =============================================================================


class TestCreateCustomPropertyParams:
    """Tests for CreateCustomPropertyParams Pydantic model."""

    def test_formula_with_composed_valid(self) -> None:
        """CreateCustomPropertyParams accepts display_formula with composed_properties."""
        params = CreateCustomPropertyParams(
            name="Revenue Per User",
            resource_type="events",
            display_formula="A / B",
            composed_properties={
                "A": ComposedPropertyValue(resource_type="events", type="number"),
                "B": ComposedPropertyValue(resource_type="events", type="number"),
            },
        )
        assert params.name == "Revenue Per User"
        assert params.display_formula == "A / B"
        assert params.composed_properties is not None

    def test_behavior_valid(self) -> None:
        """CreateCustomPropertyParams accepts behavior without formula or composed."""
        params = CreateCustomPropertyParams(
            name="Session Count",
            resource_type="events",
            behavior={"type": "count"},
        )
        assert params.behavior == {"type": "count"}
        assert params.display_formula is None
        assert params.composed_properties is None

    def test_formula_and_behavior_mutually_exclusive(self) -> None:
        """CreateCustomPropertyParams rejects both display_formula and behavior."""
        with pytest.raises(ValidationError):
            CreateCustomPropertyParams(
                name="Invalid",
                resource_type="events",
                display_formula="A / B",
                composed_properties={
                    "A": ComposedPropertyValue(resource_type="events"),
                },
                behavior={"type": "count"},
            )

    def test_behavior_and_composed_mutually_exclusive(self) -> None:
        """CreateCustomPropertyParams rejects both behavior and composed_properties."""
        with pytest.raises(ValidationError):
            CreateCustomPropertyParams(
                name="Invalid",
                resource_type="events",
                behavior={"type": "count"},
                composed_properties={
                    "A": ComposedPropertyValue(resource_type="events"),
                },
            )

    def test_formula_requires_composed(self) -> None:
        """CreateCustomPropertyParams rejects display_formula without composed_properties."""
        with pytest.raises(ValidationError):
            CreateCustomPropertyParams(
                name="Invalid",
                resource_type="events",
                display_formula="A / B",
            )

    def test_exclude_none(self) -> None:
        """CreateCustomPropertyParams excludes None fields when serializing."""
        params = CreateCustomPropertyParams(
            name="Test",
            resource_type="events",
            behavior={"type": "count"},
        )
        data = params.model_dump(exclude_none=True)
        assert "description" not in data
        assert "display_formula" not in data
        assert "composed_properties" not in data
        assert "is_locked" not in data
        assert "is_visible" not in data
        assert "data_group_id" not in data
        assert "property_type" not in data
        assert "example_value" not in data
        assert "name" in data
        assert "resource_type" in data

    def test_json_serialization_mode(self) -> None:
        """CreateCustomPropertyParams serializes enums correctly with mode='json'."""
        params = CreateCustomPropertyParams(
            name="Revenue",
            resource_type="events",
            description="Revenue metric",
            display_formula='number(properties["amount"])',
            composed_properties={
                "amount": ComposedPropertyValue(resource_type="events", type="number"),
            },
        )
        data = params.model_dump(exclude_none=True, by_alias=True, mode="json")
        assert isinstance(data["resourceType"], str)
        assert data["resourceType"] == "events"
        assert data["name"] == "Revenue"
        assert "displayFormula" in data

    def test_missing_required_raises(self) -> None:
        """CreateCustomPropertyParams raises ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            CreateCustomPropertyParams(name="Test")

    def test_all_optional_fields(self) -> None:
        """CreateCustomPropertyParams with all optional fields stores correctly."""
        params = CreateCustomPropertyParams(
            name="Revenue Per User",
            resource_type="events",
            description="Custom revenue metric",
            display_formula="A / B",
            composed_properties={
                "A": ComposedPropertyValue(resource_type="events", type="number"),
                "B": ComposedPropertyValue(resource_type="events", type="number"),
            },
            is_locked=False,
            is_visible=True,
            data_group_id="group-1",
        )
        assert params.description == "Custom revenue metric"
        assert params.is_locked is False
        assert params.is_visible is True
        assert params.data_group_id == "group-1"

    def test_camel_case_input_via_model_validate(self) -> None:
        """CreateCustomPropertyParams validates correctly with camelCase keys."""
        params = CreateCustomPropertyParams.model_validate(
            {
                "name": "Revenue Per User",
                "resourceType": "events",
                "displayFormula": "A / B",
                "composedProperties": {
                    "A": {"resourceType": "events", "type": "number"},
                    "B": {"resourceType": "events", "type": "number"},
                },
            }
        )
        assert params.name == "Revenue Per User"
        assert params.display_formula == "A / B"
        assert params.composed_properties is not None

    def test_camel_case_validation_errors(self) -> None:
        """CreateCustomPropertyParams validator catches errors with camelCase keys."""
        with pytest.raises(ValidationError):
            CreateCustomPropertyParams.model_validate(
                {
                    "name": "Invalid",
                    "resourceType": "events",
                    "displayFormula": "A / B",
                    "composedProperties": {
                        "A": {"resourceType": "events"},
                    },
                    "behavior": {"type": "count"},
                }
            )


# =============================================================================
# UpdateCustomPropertyParams Tests
# =============================================================================


class TestUpdateCustomPropertyParams:
    """Tests for UpdateCustomPropertyParams Pydantic model."""

    def test_all_none_defaults(self) -> None:
        """UpdateCustomPropertyParams defaults all fields to None."""
        params = UpdateCustomPropertyParams()
        assert params.name is None
        assert params.description is None
        assert params.display_formula is None
        assert params.composed_properties is None
        assert params.is_locked is None
        assert params.is_visible is None

    def test_exclude_none_empty(self) -> None:
        """UpdateCustomPropertyParams with no fields produces empty dict."""
        params = UpdateCustomPropertyParams()
        data = params.model_dump(exclude_none=True)
        assert data == {}

    def test_partial_update(self) -> None:
        """UpdateCustomPropertyParams serializes only provided fields."""
        params = UpdateCustomPropertyParams(name="Renamed", is_visible=False)
        data = params.model_dump(exclude_none=True)
        assert data == {"name": "Renamed", "is_visible": False}

    def test_all_fields(self) -> None:
        """UpdateCustomPropertyParams with all fields populated stores correctly."""
        params = UpdateCustomPropertyParams(
            name="Updated",
            description="New description",
            display_formula="A + B",
            composed_properties={
                "A": ComposedPropertyValue(resource_type="events"),
            },
            is_locked=True,
            is_visible=False,
        )
        data = params.model_dump(exclude_none=True)
        assert data["name"] == "Updated"
        assert data["is_locked"] is True


# =============================================================================
# LookupTable Model Tests
# =============================================================================


class TestLookupTableModel:
    """Tests for LookupTable Pydantic model."""

    def test_required_fields(self) -> None:
        """LookupTable requires id and name."""
        lt = LookupTable(id=1, name="Countries")
        assert lt.id == 1
        assert lt.name == "Countries"
        assert lt.token is None
        assert lt.created_at is None
        assert lt.last_modified_at is None
        assert lt.has_mapped_properties is None

    def test_all_fields(self) -> None:
        """LookupTable with all fields stores correctly."""
        lt = LookupTable(
            id=1,
            name="Countries",
            token="abc123",
            created_at="2026-01-01T00:00:00Z",
            last_modified_at="2026-03-01T00:00:00Z",
            has_mapped_properties=True,
        )
        assert lt.token == "abc123"
        assert lt.has_mapped_properties is True

    def test_frozen(self) -> None:
        """LookupTable is frozen and rejects attribute assignment."""
        lt = LookupTable(id=1, name="Countries")
        with pytest.raises(ValidationError):
            lt.name = "Regions"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """LookupTable preserves unknown fields via extra='allow'."""
        lt = LookupTable(id=1, name="Countries", custom="value")
        assert lt.model_extra is not None
        assert lt.model_extra["custom"] == "value"

    def test_missing_required_raises(self) -> None:
        """LookupTable raises ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            LookupTable(id=1)


# =============================================================================
# UploadLookupTableParams Tests
# =============================================================================


class TestUploadLookupTableParams:
    """Tests for UploadLookupTableParams Pydantic model."""

    def test_required_fields(self) -> None:
        """UploadLookupTableParams requires name and file_path."""
        params = UploadLookupTableParams(name="Countries", file_path="/tmp/data.csv")
        assert params.name == "Countries"
        assert params.file_path == "/tmp/data.csv"
        assert params.data_group_id is None

    def test_all_fields(self) -> None:
        """UploadLookupTableParams with all fields stores correctly."""
        params = UploadLookupTableParams(
            name="Countries", file_path="/tmp/data.csv", data_group_id=42
        )
        assert params.data_group_id == 42

    def test_missing_required_raises(self) -> None:
        """UploadLookupTableParams raises ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            UploadLookupTableParams(name="Countries")  # type: ignore[call-arg]

    def test_name_max_length(self) -> None:
        """UploadLookupTableParams rejects names longer than 255 characters."""
        with pytest.raises(ValidationError):
            UploadLookupTableParams(name="A" * 256, file_path="/tmp/data.csv")

    def test_name_within_max_length(self) -> None:
        """UploadLookupTableParams accepts names of exactly 255 characters."""
        params = UploadLookupTableParams(name="A" * 255, file_path="/tmp/data.csv")
        assert len(params.name) == 255

    def test_name_min_length(self) -> None:
        """UploadLookupTableParams accepts names of exactly 1 character."""
        params = UploadLookupTableParams(name="A", file_path="/tmp/data.csv")
        assert params.name == "A"

    def test_exclude_none(self) -> None:
        """UploadLookupTableParams excludes None fields when serializing."""
        params = UploadLookupTableParams(name="Countries", file_path="/tmp/data.csv")
        data = params.model_dump(exclude_none=True)
        assert "data_group_id" not in data
        assert "name" in data
        assert "file_path" in data


# =============================================================================
# MarkLookupTableReadyParams Tests
# =============================================================================


class TestMarkLookupTableReadyParams:
    """Tests for MarkLookupTableReadyParams Pydantic model."""

    def test_required_fields(self) -> None:
        """MarkLookupTableReadyParams requires name and key."""
        params = MarkLookupTableReadyParams(name="Countries", key="country_code")
        assert params.name == "Countries"
        assert params.key == "country_code"
        assert params.data_group_id is None

    def test_all_fields(self) -> None:
        """MarkLookupTableReadyParams with all fields stores correctly."""
        params = MarkLookupTableReadyParams(
            name="Countries", key="country_code", data_group_id=42
        )
        assert params.data_group_id == 42

    def test_missing_required_raises(self) -> None:
        """MarkLookupTableReadyParams raises ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            MarkLookupTableReadyParams(name="Countries")  # type: ignore[call-arg]

    def test_exclude_none(self) -> None:
        """MarkLookupTableReadyParams excludes None fields when serializing."""
        params = MarkLookupTableReadyParams(name="Countries", key="country_code")
        data = params.model_dump(exclude_none=True)
        assert "data_group_id" not in data


# =============================================================================
# LookupTableUploadUrl Model Tests
# =============================================================================


class TestLookupTableUploadUrlModel:
    """Tests for LookupTableUploadUrl Pydantic model."""

    def test_required_fields(self) -> None:
        """LookupTableUploadUrl requires url, path, and key."""
        upload_url = LookupTableUploadUrl(
            url="https://storage.example.com/upload",
            path="/uploads/table.csv",
            key="country_code",
        )
        assert upload_url.url == "https://storage.example.com/upload"
        assert upload_url.path == "/uploads/table.csv"
        assert upload_url.key == "country_code"

    def test_frozen(self) -> None:
        """LookupTableUploadUrl is frozen and rejects attribute assignment."""
        upload_url = LookupTableUploadUrl(
            url="https://example.com", path="/path", key="key"
        )
        with pytest.raises(ValidationError):
            upload_url.url = "new"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """LookupTableUploadUrl preserves unknown fields via extra='allow'."""
        upload_url = LookupTableUploadUrl(
            url="https://example.com", path="/path", key="key", custom="value"
        )
        assert upload_url.model_extra is not None
        assert upload_url.model_extra["custom"] == "value"

    def test_missing_required_raises(self) -> None:
        """LookupTableUploadUrl raises ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            LookupTableUploadUrl(url="https://example.com")


# =============================================================================
# UpdateLookupTableParams Tests
# =============================================================================


class TestUpdateLookupTableParams:
    """Tests for UpdateLookupTableParams Pydantic model."""

    def test_all_none_defaults(self) -> None:
        """UpdateLookupTableParams defaults name to None."""
        params = UpdateLookupTableParams()
        assert params.name is None

    def test_exclude_none_empty(self) -> None:
        """UpdateLookupTableParams with no fields produces empty dict."""
        params = UpdateLookupTableParams()
        data = params.model_dump(exclude_none=True)
        assert data == {}

    def test_with_name(self) -> None:
        """UpdateLookupTableParams with name serializes correctly."""
        params = UpdateLookupTableParams(name="Renamed Table")
        data = params.model_dump(exclude_none=True)
        assert data == {"name": "Renamed Table"}


# =============================================================================
# by_alias=True Serialization Tests
# =============================================================================


class TestByAliasSerialization:
    """Test by_alias=True produces camelCase keys for models using alias_generator=to_camel."""

    def test_bulk_property_update_by_alias(self) -> None:
        """Verify BulkPropertyUpdate serializes to camelCase with by_alias=True."""
        update = BulkPropertyUpdate(
            name="test_prop",
            resource_type="event",
            data_group_id="group-1",
            description="test",
        )
        dumped = update.model_dump(exclude_none=True, by_alias=True)
        assert "resourceType" in dumped
        assert "dataGroupId" in dumped
        assert "resource_type" not in dumped
        assert "data_group_id" not in dumped
        assert dumped["resourceType"] == "event"
        assert dumped["dataGroupId"] == "group-1"
        assert dumped["name"] == "test_prop"

    def test_bulk_property_update_without_alias(self) -> None:
        """Verify BulkPropertyUpdate uses snake_case keys without by_alias."""
        update = BulkPropertyUpdate(
            name="test_prop",
            resource_type="event",
        )
        dumped = update.model_dump(exclude_none=True)
        assert "resource_type" in dumped
        assert "resourceType" not in dumped

    def test_create_custom_property_params_by_alias(self) -> None:
        """Verify CreateCustomPropertyParams serializes to camelCase with by_alias=True."""
        params = CreateCustomPropertyParams(
            name="Revenue Per User",
            resource_type="events",
            display_formula="A / B",
            composed_properties={
                "A": ComposedPropertyValue(resource_type="events", type="number"),
                "B": ComposedPropertyValue(resource_type="events", type="number"),
            },
            is_locked=False,
            is_visible=True,
            data_group_id="group-1",
        )
        dumped = params.model_dump(exclude_none=True, by_alias=True)
        assert "displayFormula" in dumped
        assert "composedProperties" in dumped
        assert "resourceType" in dumped
        assert "isLocked" in dumped
        assert "isVisible" in dumped
        assert "dataGroupId" in dumped
        # Ensure snake_case keys are NOT present
        assert "display_formula" not in dumped
        assert "composed_properties" not in dumped
        assert "resource_type" not in dumped
        assert "is_locked" not in dumped
        assert "is_visible" not in dumped
        assert "data_group_id" not in dumped
        # Verify values
        assert dumped["displayFormula"] == "A / B"
        assert dumped["resourceType"] == "events"
        assert dumped["isLocked"] is False
        assert dumped["isVisible"] is True

    def test_create_custom_property_params_nested_alias(self) -> None:
        """Verify nested ComposedPropertyValue also serializes to camelCase."""
        params = CreateCustomPropertyParams(
            name="Test",
            resource_type="events",
            display_formula="A",
            composed_properties={
                "A": ComposedPropertyValue(
                    resource_type="events",
                    type="number",
                    type_cast="string",
                    join_property_type="event",
                ),
            },
        )
        dumped = params.model_dump(exclude_none=True, by_alias=True)
        nested = dumped["composedProperties"]["A"]
        assert "resourceType" in nested
        assert "typeCast" in nested
        assert "joinPropertyType" in nested
        assert "resource_type" not in nested
        assert "type_cast" not in nested
        assert "join_property_type" not in nested

    def test_update_custom_property_params_by_alias(self) -> None:
        """Verify UpdateCustomPropertyParams serializes to camelCase with by_alias=True."""
        params = UpdateCustomPropertyParams(
            name="Updated",
            description="New description",
            display_formula="A + B",
            composed_properties={
                "A": ComposedPropertyValue(resource_type="events"),
            },
            is_locked=True,
            is_visible=False,
        )
        dumped = params.model_dump(exclude_none=True, by_alias=True)
        assert "displayFormula" in dumped
        assert "composedProperties" in dumped
        assert "isLocked" in dumped
        assert "isVisible" in dumped
        # Ensure snake_case keys are NOT present
        assert "display_formula" not in dumped
        assert "composed_properties" not in dumped
        assert "is_locked" not in dumped
        assert "is_visible" not in dumped
        # Verify values
        assert dumped["displayFormula"] == "A + B"
        assert dumped["isLocked"] is True
        assert dumped["isVisible"] is False

    def test_update_custom_property_params_partial_alias(self) -> None:
        """Verify UpdateCustomPropertyParams partial update uses camelCase with by_alias."""
        params = UpdateCustomPropertyParams(name="Renamed", is_visible=False)
        dumped = params.model_dump(exclude_none=True, by_alias=True)
        assert "isVisible" in dumped
        assert "is_visible" not in dumped
        assert dumped["isVisible"] is False
        assert dumped["name"] == "Renamed"
