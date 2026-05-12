"""Tests for Phase 024 Pydantic CRUD types in mixpanel_headless.types.

Tests Dashboard, Blueprint, Bookmark, and Cohort types including
frozen immutability, extra field preservation, field aliasing/renaming,
definition flattening, and exclude_none serialization.
"""

# ruff: noqa: ARG001

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from mixpanel_headless.types import (
    BlueprintCard,
    BlueprintConfig,
    BlueprintFinishParams,
    Bookmark,
    BookmarkHistoryResponse,
    BookmarkMetadata,
    BulkUpdateBookmarkEntry,
    BulkUpdateCohortEntry,
    Cohort,
    CohortCreator,
    CreateBookmarkParams,
    CreateCohortParams,
    CreateDashboardParams,
    Dashboard,
    RcaSourceData,
    UpdateBookmarkParams,
    UpdateCohortParams,
    UpdateDashboardParams,
    UpdateReportLinkParams,
)


class TestDashboardTypes:
    """Tests for Dashboard, CreateDashboardParams, and UpdateDashboardParams."""

    def test_dashboard_required_fields_only(self) -> None:
        """Dashboard with only required fields succeeds and has correct defaults."""
        d = Dashboard(id=1, title="X")
        assert d.id == 1
        assert d.title == "X"
        assert d.is_private is False
        assert d.is_favorited is False
        assert d.ancestors == []
        assert d.description is None
        assert d.created is None
        assert d.can_update_basic is False
        assert d.is_shared_with_project is False

    def test_dashboard_all_fields(self) -> None:
        """Dashboard with every field populated stores all values correctly."""
        d = Dashboard(
            id=42,
            title="Full Dashboard",
            description="A complete dashboard",
            is_private=True,
            is_restricted=True,
            creator_id=10,
            creator_name="Alice",
            creator_email="alice@example.com",
            created=datetime(2025, 1, 1, tzinfo=timezone.utc),
            modified=datetime(2025, 6, 1, tzinfo=timezone.utc),
            is_favorited=True,
            pinned_date="2025-03-01",
            layout_version=2,
            unique_view_count=100,
            total_view_count=500,
            last_modified_by_id=11,
            last_modified_by_name="Bob",
            last_modified_by_email="bob@example.com",
            filters=[{"property": "country"}],
            breakdowns=[{"property": "os"}],
            time_filter={"range": "30d"},
            generation_type="manual",
            parent_dashboard_id=5,
            child_dashboards=[{"id": 43}],
            can_update_basic=True,
            can_share=True,
            can_view=True,
            can_update_restricted=True,
            can_update_visibility=True,
            is_superadmin=True,
            allow_staff_override=True,
            can_pin=True,
            is_shared_with_project=True,
            creator="alice",
            ancestors=[{"id": 5}],
            layout={"type": "grid"},
            contents=[{"type": "report"}],
            num_active_public_links=3,
            new_content={"draft": True},
            template_type="onboarding",
        )
        assert d.id == 42
        assert d.title == "Full Dashboard"
        assert d.description == "A complete dashboard"
        assert d.is_private is True
        assert d.creator_name == "Alice"
        assert d.unique_view_count == 100
        assert d.can_update_basic is True
        assert d.template_type == "onboarding"
        assert d.ancestors == [{"id": 5}]
        assert d.num_active_public_links == 3

    def test_dashboard_frozen(self) -> None:
        """Dashboard model is frozen and rejects attribute assignment."""
        d = Dashboard(id=1, title="X")
        with pytest.raises(ValidationError):
            d.title = "new"  # type: ignore[misc]

    def test_dashboard_extra_fields_preserved(self) -> None:
        """Dashboard preserves unknown fields via extra='allow'."""
        d = Dashboard(id=1, title="X", unknown_field="foo")
        assert d.model_extra is not None
        assert d.model_extra["unknown_field"] == "foo"

    def test_dashboard_datetime_lenient_parsing(self) -> None:
        """Dashboard parses ISO 8601 datetime strings leniently."""
        d = Dashboard(id=1, title="X", created="2025-01-01T00:00:00Z")
        assert isinstance(d.created, datetime)
        assert d.created.year == 2025

    def test_dashboard_datetime_none(self) -> None:
        """Dashboard accepts None for datetime fields."""
        d = Dashboard(id=1, title="X", created=None)
        assert d.created is None

    def test_create_dashboard_params_exclude_none(self) -> None:
        """CreateDashboardParams excludes None fields when serializing."""
        params = CreateDashboardParams(title="X")
        data = params.model_dump(exclude_none=True)
        assert data == {"title": "X"}

    def test_update_dashboard_params_empty(self) -> None:
        """UpdateDashboardParams with no fields produces empty dict."""
        params = UpdateDashboardParams()
        data = params.model_dump(exclude_none=True)
        assert data == {}


class TestBlueprintTypes:
    """Tests for BlueprintCard, BlueprintConfig, BlueprintFinishParams, and related types."""

    def test_blueprint_card_type_rename(self) -> None:
        """BlueprintCard serializes card_type as 'type' via by_alias."""
        card = BlueprintCard(card_type="report")
        data = card.model_dump(by_alias=True)
        assert "type" in data
        assert "card_type" not in data
        assert data["type"] == "report"

    def test_blueprint_card_exclude_none(self) -> None:
        """BlueprintCard excludes None fields and renames card_type to type."""
        card = BlueprintCard(card_type="report", bookmark_id=123)
        data = card.model_dump(by_alias=True, exclude_none=True)
        assert data == {"type": "report", "bookmark_id": 123}
        assert "text_card_id" not in data
        assert "markdown" not in data

    def test_rca_source_data_type_rename(self) -> None:
        """RcaSourceData serializes source_type as 'type' via by_alias."""
        rca = RcaSourceData(source_type="anomaly")
        data = rca.model_dump(by_alias=True, exclude_none=True)
        assert "type" in data
        assert "source_type" not in data
        assert data["type"] == "anomaly"

    def test_update_report_link_type_rename(self) -> None:
        """UpdateReportLinkParams serializes link_type as 'type' via by_alias."""
        params = UpdateReportLinkParams(link_type="embedded")
        data = params.model_dump(by_alias=True, exclude_none=True)
        assert "type" in data
        assert "link_type" not in data
        assert data["type"] == "embedded"

    def test_blueprint_finish_params_cards(self) -> None:
        """BlueprintFinishParams serializes cards as list of dicts."""
        params = BlueprintFinishParams(
            dashboard_id=1,
            cards=[BlueprintCard(card_type="report")],
        )
        data = params.model_dump(by_alias=True)
        assert data["dashboard_id"] == 1
        assert isinstance(data["cards"], list)
        assert len(data["cards"]) == 1
        assert data["cards"][0]["type"] == "report"
        assert "card_type" not in data["cards"][0]

    def test_blueprint_config_frozen(self) -> None:
        """BlueprintConfig is frozen and rejects attribute assignment."""
        config = BlueprintConfig(variables={"event": "Signup"})
        with pytest.raises(ValidationError):
            config.variables = {"event": "Login"}  # type: ignore[misc]


class TestBookmarkTypes:
    """Tests for Bookmark, BookmarkMetadata, CreateBookmarkParams, and related types."""

    def test_bookmark_from_api_response(self) -> None:
        """Bookmark parses API response with 'type' aliased to bookmark_type."""
        bookmark = Bookmark.model_validate(
            {"id": 1, "name": "X", "type": "funnels", "params": {}}
        )
        assert bookmark.bookmark_type == "funnels"

    def test_bookmark_from_field_name(self) -> None:
        """Bookmark accepts bookmark_type as field name via populate_by_name."""
        bookmark = Bookmark(id=1, name="X", bookmark_type="funnels", params={})
        assert bookmark.bookmark_type == "funnels"

    def test_bookmark_model_dump_default(self) -> None:
        """Bookmark model_dump uses Python field name 'bookmark_type' by default."""
        bookmark = Bookmark(id=1, name="X", bookmark_type="funnels", params={})
        data = bookmark.model_dump()
        assert "bookmark_type" in data
        assert data["bookmark_type"] == "funnels"

    def test_bookmark_model_dump_by_alias(self) -> None:
        """Bookmark model_dump with by_alias uses 'type' instead of 'bookmark_type'."""
        bookmark = Bookmark(id=1, name="X", bookmark_type="funnels", params={})
        data = bookmark.model_dump(by_alias=True)
        assert "type" in data
        assert "bookmark_type" not in data
        assert data["type"] == "funnels"

    def test_bookmark_frozen(self) -> None:
        """Bookmark model is frozen and rejects attribute assignment."""
        bookmark = Bookmark(id=1, name="X", bookmark_type="funnels", params={})
        with pytest.raises(ValidationError):
            bookmark.name = "new"  # type: ignore[misc]

    def test_bookmark_metadata_extra_fields(self) -> None:
        """BookmarkMetadata preserves unknown fields via extra='allow'."""
        meta = BookmarkMetadata(unknown_x=42)
        assert meta.model_extra is not None
        assert meta.model_extra["unknown_x"] == 42

    def test_create_bookmark_type_rename(self) -> None:
        """CreateBookmarkParams serializes bookmark_type as 'type' via by_alias."""
        params = CreateBookmarkParams(name="X", bookmark_type="funnels", params={})
        data = params.model_dump(by_alias=True, exclude_none=True)
        assert "type" in data
        assert "bookmark_type" not in data
        assert data["type"] == "funnels"

    def test_create_bookmark_exclude_none(self) -> None:
        """CreateBookmarkParams excludes None description from output."""
        params = CreateBookmarkParams(name="X", bookmark_type="funnels", params={})
        data = params.model_dump(by_alias=True, exclude_none=True)
        assert "description" not in data
        assert "icon" not in data

    def test_update_bookmark_params_empty(self) -> None:
        """UpdateBookmarkParams with no fields produces empty dict."""
        params = UpdateBookmarkParams()
        data = params.model_dump(exclude_none=True)
        assert data == {}

    def test_bulk_update_bookmark_entry(self) -> None:
        """BulkUpdateBookmarkEntry with only id produces minimal dict."""
        entry = BulkUpdateBookmarkEntry(id=1)
        data = entry.model_dump(exclude_none=True)
        assert data == {"id": 1}

    def test_bookmark_history_defaults(self) -> None:
        """BookmarkHistoryResponse has empty results and None pagination by default."""
        response = BookmarkHistoryResponse()
        assert response.results == []
        assert response.pagination is None


class TestCohortTypes:
    """Tests for Cohort, CohortCreator, CreateCohortParams, and related types."""

    def test_cohort_required_fields_only(self) -> None:
        """Cohort with only required fields succeeds and has correct defaults."""
        cohort = Cohort(id=1, name="X")
        assert cohort.id == 1
        assert cohort.name == "X"
        assert cohort.description is None
        assert cohort.count is None
        assert cohort.verified is False
        assert cohort.referenced_directly_by == []
        assert cohort.active_integrations == []

    def test_cohort_creator_nested(self) -> None:
        """Cohort parses nested created_by dict into CohortCreator."""
        cohort = Cohort.model_validate(
            {"id": 1, "name": "X", "created_by": {"id": 1, "name": "Alice"}}
        )
        assert cohort.created_by is not None
        assert isinstance(cohort.created_by, CohortCreator)
        assert cohort.created_by.id == 1
        assert cohort.created_by.name == "Alice"

    def test_cohort_extra_fields(self) -> None:
        """Cohort preserves unknown fields via extra='allow'."""
        cohort = Cohort(id=1, name="X", can_edit=True)
        assert cohort.model_extra is not None
        assert cohort.model_extra["can_edit"] is True

    def test_cohort_frozen(self) -> None:
        """Cohort model is frozen and rejects attribute assignment."""
        cohort = Cohort(id=1, name="X")
        with pytest.raises(ValidationError):
            cohort.name = "new"  # type: ignore[misc]

    def test_create_cohort_definition_flattening(self) -> None:
        """CreateCohortParams flattens definition dict into top-level payload."""
        params = CreateCohortParams(
            name="X",
            definition={"behavioral_filter": {"op": "and"}},
        )
        data = params.model_dump(exclude_none=True)
        assert "definition" not in data
        assert data == {"name": "X", "behavioral_filter": {"op": "and"}}

    def test_create_cohort_no_definition(self) -> None:
        """CreateCohortParams without definition has no extra keys."""
        params = CreateCohortParams(name="X")
        data = params.model_dump(exclude_none=True)
        assert data == {"name": "X"}

    def test_create_cohort_empty_definition(self) -> None:
        """CreateCohortParams with empty definition adds no extra keys."""
        params = CreateCohortParams(name="X", definition={})
        data = params.model_dump(exclude_none=True)
        assert data == {"name": "X"}

    def test_update_cohort_definition_flattening(self) -> None:
        """UpdateCohortParams flattens definition dict into top-level payload."""
        params = UpdateCohortParams(
            name="Updated",
            definition={"behavioral_filter": {"op": "or"}},
        )
        data = params.model_dump(exclude_none=True)
        assert "definition" not in data
        assert data == {"name": "Updated", "behavioral_filter": {"op": "or"}}

    def test_bulk_update_cohort_definition_flattening(self) -> None:
        """BulkUpdateCohortEntry flattens definition dict into top-level payload."""
        entry = BulkUpdateCohortEntry(
            id=1,
            definition={"behavioral_filter": {"op": "and"}},
        )
        data = entry.model_dump(exclude_none=True)
        assert "definition" not in data
        assert data == {"id": 1, "behavioral_filter": {"op": "and"}}
