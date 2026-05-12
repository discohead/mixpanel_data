# ruff: noqa: ARG001
"""Tests for Phase 026 Alert types.

Tests round-trip serialization, frozen immutability, extra field preservation,
exclude_none behavior, and enum values for all alert types.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from mixpanel_headless.types import (
    AlertBookmark,
    AlertCount,
    AlertCreator,
    AlertFrequencyPreset,
    AlertHistoryPagination,
    AlertHistoryResponse,
    AlertProject,
    AlertScreenshotResponse,
    AlertValidation,
    AlertWorkspace,
    CreateAlertParams,
    CustomAlert,
    UpdateAlertParams,
    ValidateAlertsForBookmarkParams,
    ValidateAlertsForBookmarkResponse,
)

# =============================================================================
# Enum Tests
# =============================================================================


class TestAlertFrequencyPresetEnum:
    """Tests for AlertFrequencyPreset enum values."""

    def test_hourly_value(self) -> None:
        """AlertFrequencyPreset.HOURLY has value 3600."""
        assert AlertFrequencyPreset.HOURLY.value == 3600

    def test_daily_value(self) -> None:
        """AlertFrequencyPreset.DAILY has value 86400."""
        assert AlertFrequencyPreset.DAILY.value == 86400

    def test_weekly_value(self) -> None:
        """AlertFrequencyPreset.WEEKLY has value 604800."""
        assert AlertFrequencyPreset.WEEKLY.value == 604800

    def test_is_int_subclass(self) -> None:
        """AlertFrequencyPreset members are also integers."""
        assert isinstance(AlertFrequencyPreset.HOURLY, int)

    def test_all_members(self) -> None:
        """AlertFrequencyPreset has exactly three members."""
        assert len(AlertFrequencyPreset) == 3


# =============================================================================
# Nested Model Tests
# =============================================================================


class TestAlertBookmarkModel:
    """Tests for AlertBookmark nested model."""

    def test_required_fields(self) -> None:
        """AlertBookmark requires only id."""
        bm = AlertBookmark(id=42)
        assert bm.id == 42
        assert bm.name is None
        assert bm.type is None

    def test_all_fields(self) -> None:
        """AlertBookmark with all fields stores correctly."""
        bm = AlertBookmark(id=42, name="Daily Signups", type="insights")
        assert bm.name == "Daily Signups"
        assert bm.type == "insights"

    def test_frozen(self) -> None:
        """AlertBookmark is frozen."""
        bm = AlertBookmark(id=1)
        with pytest.raises(ValidationError):
            bm.id = 2  # type: ignore[misc]

    def test_extra_fields(self) -> None:
        """AlertBookmark preserves extra fields."""
        bm = AlertBookmark(id=1, custom="value")
        assert bm.model_extra is not None
        assert bm.model_extra["custom"] == "value"


class TestAlertCreatorModel:
    """Tests for AlertCreator nested model."""

    def test_required_fields(self) -> None:
        """AlertCreator requires only id."""
        creator = AlertCreator(id=10)
        assert creator.id == 10
        assert creator.first_name is None
        assert creator.email is None

    def test_all_fields(self) -> None:
        """AlertCreator with all fields stores correctly."""
        creator = AlertCreator(
            id=10, first_name="Alice", last_name="Smith", email="alice@co.com"
        )
        assert creator.first_name == "Alice"
        assert creator.email == "alice@co.com"

    def test_frozen(self) -> None:
        """AlertCreator is frozen."""
        creator = AlertCreator(id=1)
        with pytest.raises(ValidationError):
            creator.id = 2  # type: ignore[misc]


class TestAlertWorkspaceModel:
    """Tests for AlertWorkspace nested model."""

    def test_required_fields(self) -> None:
        """AlertWorkspace requires only id."""
        ws = AlertWorkspace(id=100)
        assert ws.id == 100
        assert ws.name is None

    def test_all_fields(self) -> None:
        """AlertWorkspace with all fields stores correctly."""
        ws = AlertWorkspace(id=100, name="Production")
        assert ws.name == "Production"


class TestAlertProjectModel:
    """Tests for AlertProject nested model."""

    def test_required_fields(self) -> None:
        """AlertProject requires only id."""
        proj = AlertProject(id=12345)
        assert proj.id == 12345
        assert proj.name is None

    def test_all_fields(self) -> None:
        """AlertProject with all fields stores correctly."""
        proj = AlertProject(id=12345, name="My App")
        assert proj.name == "My App"


# =============================================================================
# CustomAlert Model Tests
# =============================================================================


class TestCustomAlertModel:
    """Tests for CustomAlert Pydantic model."""

    def test_required_fields_only(self) -> None:
        """CustomAlert with only required fields succeeds and has defaults."""
        alert = CustomAlert(id=1, name="Test Alert")
        assert alert.id == 1
        assert alert.name == "Test Alert"
        assert alert.bookmark is None
        assert alert.condition == {}
        assert alert.frequency == 0
        assert alert.paused is False
        assert alert.subscriptions == []
        assert alert.notification_windows is None
        assert alert.creator is None
        assert alert.workspace is None
        assert alert.project is None
        assert alert.created == ""
        assert alert.modified == ""
        assert alert.last_checked is None
        assert alert.last_fired is None
        assert alert.valid is True
        assert alert.results is None

    def test_all_fields(self) -> None:
        """CustomAlert with all fields stores correctly."""
        alert = CustomAlert(
            id=1,
            name="Drop Alert",
            bookmark=AlertBookmark(id=42, name="Signups"),
            condition={"operator": "less_than", "value": 100},
            frequency=86400,
            paused=True,
            subscriptions=[{"type": "email", "value": "team@co.com"}],
            notification_windows={"start": "09:00", "end": "17:00"},
            creator=AlertCreator(id=10, email="alice@co.com"),
            workspace=AlertWorkspace(id=100, name="Prod"),
            project=AlertProject(id=12345, name="My App"),
            created="2026-01-01T00:00:00Z",
            modified="2026-03-01T00:00:00Z",
            last_checked="2026-03-30T12:00:00Z",
            last_fired="2026-03-25T08:00:00Z",
            valid=False,
            results={"current_value": 50},
        )
        assert alert.bookmark is not None
        assert alert.bookmark.id == 42
        assert alert.condition["operator"] == "less_than"
        assert alert.paused is True
        assert alert.creator is not None
        assert alert.creator.email == "alice@co.com"
        assert alert.valid is False

    def test_frozen(self) -> None:
        """CustomAlert is frozen and rejects attribute assignment."""
        alert = CustomAlert(id=1, name="Test")
        with pytest.raises(ValidationError):
            alert.name = "new"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """CustomAlert preserves unknown fields via extra='allow'."""
        alert = CustomAlert(id=1, name="Test", unknown_field="foo")
        assert alert.model_extra is not None
        assert alert.model_extra["unknown_field"] == "foo"

    def test_model_validate_api_shape(self) -> None:
        """CustomAlert parses a dict matching API response shape."""
        data: dict[str, Any] = {
            "id": 42,
            "name": "Signups Drop",
            "bookmark": {"id": 100, "name": "Daily Signups", "type": "insights"},
            "condition": {"operator": "less_than", "value": 50},
            "frequency": 86400,
            "paused": False,
            "subscriptions": [{"type": "email", "value": "team@co.com"}],
            "created": "2026-01-01T00:00:00Z",
            "modified": "2026-01-01T00:00:00Z",
            "valid": True,
        }
        alert = CustomAlert.model_validate(data)
        assert alert.id == 42
        assert alert.bookmark is not None
        assert alert.bookmark.name == "Daily Signups"
        assert alert.frequency == 86400


# =============================================================================
# CreateAlertParams Tests
# =============================================================================


class TestCreateAlertParams:
    """Tests for CreateAlertParams Pydantic model."""

    def test_required_fields(self) -> None:
        """CreateAlertParams requires all mandatory fields."""
        params = CreateAlertParams(
            bookmark_id=123,
            name="Test",
            condition={"operator": "less_than", "value": 100},
            frequency=86400,
            paused=False,
            subscriptions=[{"type": "email", "value": "test@co.com"}],
        )
        assert params.bookmark_id == 123
        assert params.name == "Test"
        assert params.frequency == 86400
        assert params.notification_windows is None

    def test_exclude_none(self) -> None:
        """CreateAlertParams excludes None fields when serializing."""
        params = CreateAlertParams(
            bookmark_id=1,
            name="X",
            condition={},
            frequency=3600,
            paused=False,
            subscriptions=[],
        )
        data = params.model_dump(exclude_none=True)
        assert "notification_windows" not in data
        assert "bookmark_id" in data
        assert "name" in data

    def test_with_notification_windows(self) -> None:
        """CreateAlertParams includes notification_windows when set."""
        params = CreateAlertParams(
            bookmark_id=1,
            name="X",
            condition={},
            frequency=3600,
            paused=False,
            subscriptions=[],
            notification_windows={"start": "09:00"},
        )
        data = params.model_dump(exclude_none=True)
        assert "notification_windows" in data

    def test_name_max_length(self) -> None:
        """CreateAlertParams rejects names longer than 50 characters."""
        with pytest.raises(ValidationError):
            CreateAlertParams(
                bookmark_id=1,
                name="A" * 51,
                condition={},
                frequency=3600,
                paused=False,
                subscriptions=[],
            )

    def test_missing_required_raises(self) -> None:
        """CreateAlertParams raises ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            CreateAlertParams(name="X")  # type: ignore[call-arg]


# =============================================================================
# UpdateAlertParams Tests
# =============================================================================


class TestUpdateAlertParams:
    """Tests for UpdateAlertParams Pydantic model."""

    def test_all_none_defaults(self) -> None:
        """UpdateAlertParams defaults all fields to None."""
        params = UpdateAlertParams()
        assert params.name is None
        assert params.bookmark_id is None
        assert params.condition is None
        assert params.frequency is None
        assert params.paused is None
        assert params.subscriptions is None
        assert params.notification_windows is None

    def test_exclude_none_empty(self) -> None:
        """UpdateAlertParams with no fields produces empty dict."""
        params = UpdateAlertParams()
        data = params.model_dump(exclude_none=True)
        assert data == {}

    def test_partial_update(self) -> None:
        """UpdateAlertParams serializes only provided fields."""
        params = UpdateAlertParams(name="Renamed", paused=True)
        data = params.model_dump(exclude_none=True)
        assert data == {"name": "Renamed", "paused": True}

    def test_all_fields(self) -> None:
        """UpdateAlertParams with all fields populated stores correctly."""
        params = UpdateAlertParams(
            name="Full",
            bookmark_id=999,
            condition={"operator": "greater_than", "value": 200},
            frequency=604800,
            paused=False,
            subscriptions=[{"type": "slack"}],
            notification_windows={"timezone": "UTC"},
        )
        data = params.model_dump(exclude_none=True)
        assert data["name"] == "Full"
        assert data["bookmark_id"] == 999
        assert data["frequency"] == 604800


# =============================================================================
# AlertCount Tests
# =============================================================================


class TestAlertCountModel:
    """Tests for AlertCount Pydantic model."""

    def test_required_fields(self) -> None:
        """AlertCount requires all three fields."""
        count = AlertCount(anomaly_alerts_count=5, alert_limit=100, is_below_limit=True)
        assert count.anomaly_alerts_count == 5
        assert count.alert_limit == 100
        assert count.is_below_limit is True

    def test_frozen(self) -> None:
        """AlertCount is frozen and rejects attribute assignment."""
        count = AlertCount(anomaly_alerts_count=5, alert_limit=100, is_below_limit=True)
        with pytest.raises(ValidationError):
            count.anomaly_alerts_count = 10  # type: ignore[misc]

    def test_model_validate(self) -> None:
        """AlertCount parses from dict."""
        count = AlertCount.model_validate(
            {"anomaly_alerts_count": 10, "alert_limit": 50, "is_below_limit": True}
        )
        assert count.anomaly_alerts_count == 10
        assert count.alert_limit == 50

    def test_missing_required_raises(self) -> None:
        """AlertCount raises ValidationError when fields are missing."""
        with pytest.raises(ValidationError):
            AlertCount(anomaly_alerts_count=5)  # type: ignore[call-arg]


# =============================================================================
# AlertHistoryResponse Tests
# =============================================================================


class TestAlertHistoryPaginationModel:
    """Tests for AlertHistoryPagination model."""

    def test_defaults(self) -> None:
        """AlertHistoryPagination defaults correctly."""
        pagination = AlertHistoryPagination()
        assert pagination.next_cursor is None
        assert pagination.previous_cursor is None
        assert pagination.page_size == 20

    def test_with_cursors(self) -> None:
        """AlertHistoryPagination stores cursor values."""
        pagination = AlertHistoryPagination(
            next_cursor="abc", previous_cursor="xyz", page_size=50
        )
        assert pagination.next_cursor == "abc"
        assert pagination.previous_cursor == "xyz"
        assert pagination.page_size == 50

    def test_frozen(self) -> None:
        """AlertHistoryPagination is frozen."""
        pagination = AlertHistoryPagination()
        with pytest.raises(ValidationError):
            pagination.page_size = 100  # type: ignore[misc]


class TestAlertHistoryResponseModel:
    """Tests for AlertHistoryResponse model."""

    def test_defaults(self) -> None:
        """AlertHistoryResponse defaults to empty results and None pagination."""
        response = AlertHistoryResponse()
        assert response.results == []
        assert response.pagination is None

    def test_with_results(self) -> None:
        """AlertHistoryResponse stores results and pagination."""
        response = AlertHistoryResponse(
            results=[{"timestamp": "2026-01-01", "fired": True}],
            pagination=AlertHistoryPagination(page_size=10, next_cursor="abc"),
        )
        assert len(response.results) == 1
        assert response.pagination is not None
        assert response.pagination.next_cursor == "abc"

    def test_frozen(self) -> None:
        """AlertHistoryResponse is frozen."""
        response = AlertHistoryResponse()
        with pytest.raises(ValidationError):
            response.results = []  # type: ignore[misc]

    def test_model_validate(self) -> None:
        """AlertHistoryResponse parses from dict."""
        data: dict[str, Any] = {
            "results": [{"fired": True}],
            "pagination": {"page_size": 50},
        }
        response = AlertHistoryResponse.model_validate(data)
        assert len(response.results) == 1
        assert response.pagination is not None
        assert response.pagination.page_size == 50


# =============================================================================
# AlertScreenshotResponse Tests
# =============================================================================


class TestAlertScreenshotResponseModel:
    """Tests for AlertScreenshotResponse model."""

    def test_required_fields(self) -> None:
        """AlertScreenshotResponse requires signed_url."""
        resp = AlertScreenshotResponse(
            signed_url="https://storage.googleapis.com/screenshot.png"
        )
        assert resp.signed_url == "https://storage.googleapis.com/screenshot.png"

    def test_frozen(self) -> None:
        """AlertScreenshotResponse is frozen."""
        resp = AlertScreenshotResponse(signed_url="https://example.com")
        with pytest.raises(ValidationError):
            resp.signed_url = "new"  # type: ignore[misc]

    def test_missing_required_raises(self) -> None:
        """AlertScreenshotResponse raises ValidationError when signed_url missing."""
        with pytest.raises(ValidationError):
            AlertScreenshotResponse()  # type: ignore[call-arg]


# =============================================================================
# AlertValidation Tests
# =============================================================================


class TestAlertValidationModel:
    """Tests for AlertValidation model."""

    def test_valid_alert(self) -> None:
        """AlertValidation for a valid alert."""
        v = AlertValidation(alert_id=1, alert_name="Test", valid=True)
        assert v.alert_id == 1
        assert v.valid is True
        assert v.reason is None

    def test_invalid_alert_with_reason(self) -> None:
        """AlertValidation for an invalid alert with reason."""
        v = AlertValidation(
            alert_id=2, alert_name="Bad", valid=False, reason="Incompatible"
        )
        assert v.valid is False
        assert v.reason == "Incompatible"

    def test_frozen(self) -> None:
        """AlertValidation is frozen."""
        v = AlertValidation(alert_id=1, alert_name="X", valid=True)
        with pytest.raises(ValidationError):
            v.valid = False  # type: ignore[misc]


# =============================================================================
# ValidateAlertsForBookmarkParams Tests
# =============================================================================


class TestValidateAlertsForBookmarkParams:
    """Tests for ValidateAlertsForBookmarkParams model."""

    def test_required_fields(self) -> None:
        """ValidateAlertsForBookmarkParams requires all fields."""
        params = ValidateAlertsForBookmarkParams(
            alert_ids=[1, 2],
            bookmark_type="insights",
            bookmark_params={"event": "Signup"},
        )
        assert params.alert_ids == [1, 2]
        assert params.bookmark_type == "insights"
        assert params.bookmark_params == {"event": "Signup"}

    def test_model_dump(self) -> None:
        """ValidateAlertsForBookmarkParams serializes correctly."""
        params = ValidateAlertsForBookmarkParams(
            alert_ids=[1],
            bookmark_type="funnels",
            bookmark_params={"steps": []},
        )
        data = params.model_dump()
        assert data["alert_ids"] == [1]
        assert data["bookmark_type"] == "funnels"

    def test_missing_required_raises(self) -> None:
        """ValidateAlertsForBookmarkParams raises when fields missing."""
        with pytest.raises(ValidationError):
            ValidateAlertsForBookmarkParams(alert_ids=[1])  # type: ignore[call-arg]

    def test_empty_alert_ids_raises(self) -> None:
        """ValidateAlertsForBookmarkParams rejects empty alert_ids."""
        with pytest.raises(ValidationError):
            ValidateAlertsForBookmarkParams(
                alert_ids=[],
                bookmark_type="insights",
                bookmark_params={"event": "Signup"},
            )

    def test_invalid_bookmark_type_raises(self) -> None:
        """ValidateAlertsForBookmarkParams rejects invalid bookmark_type."""
        with pytest.raises(ValidationError):
            ValidateAlertsForBookmarkParams(
                alert_ids=[1],
                bookmark_type="retention",
                bookmark_params={},
            )


# =============================================================================
# ValidateAlertsForBookmarkResponse Tests
# =============================================================================


class TestValidateAlertsForBookmarkResponseModel:
    """Tests for ValidateAlertsForBookmarkResponse model."""

    def test_defaults(self) -> None:
        """ValidateAlertsForBookmarkResponse defaults correctly."""
        resp = ValidateAlertsForBookmarkResponse()
        assert resp.alert_validations == []
        assert resp.invalid_count == 0

    def test_with_validations(self) -> None:
        """ValidateAlertsForBookmarkResponse stores validation results."""
        resp = ValidateAlertsForBookmarkResponse(
            alert_validations=[
                AlertValidation(alert_id=1, alert_name="OK", valid=True),
                AlertValidation(
                    alert_id=2, alert_name="Bad", valid=False, reason="Incompatible"
                ),
            ],
            invalid_count=1,
        )
        assert len(resp.alert_validations) == 2
        assert resp.invalid_count == 1
        assert resp.alert_validations[1].reason == "Incompatible"

    def test_frozen(self) -> None:
        """ValidateAlertsForBookmarkResponse is frozen."""
        resp = ValidateAlertsForBookmarkResponse()
        with pytest.raises(ValidationError):
            resp.invalid_count = 5  # type: ignore[misc]

    def test_model_validate(self) -> None:
        """ValidateAlertsForBookmarkResponse parses from dict."""
        data: dict[str, Any] = {
            "alert_validations": [
                {"alert_id": 1, "alert_name": "X", "valid": True},
            ],
            "invalid_count": 0,
        }
        resp = ValidateAlertsForBookmarkResponse.model_validate(data)
        assert len(resp.alert_validations) == 1
        assert resp.alert_validations[0].alert_id == 1
