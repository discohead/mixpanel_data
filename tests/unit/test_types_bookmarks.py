"""Tests for bookmark-related types in mixpanel_data.types.

Tests SavedReportResult, FlowsResult, and BookmarkInfo dataclasses
including report_type detection and DataFrame conversion.
"""

from __future__ import annotations

import pandas as pd
import pytest

from mixpanel_data.types import (
    BookmarkInfo,
    BookmarkType,
    FlowsResult,
    SavedReportResult,
    SavedReportType,
)


class TestSavedReportResult:
    """Tests for SavedReportResult dataclass."""

    def test_create_insights_report(self) -> None:
        """Test creating an insights report result."""
        result = SavedReportResult(
            bookmark_id=12345,
            computed_at="2024-01-15T10:30:00",
            from_date="2024-01-01",
            to_date="2024-01-14",
            headers=["$event"],
            series={
                "Page View": {"2024-01-01": 100, "2024-01-02": 150},
                "Sign Up": {"2024-01-01": 10, "2024-01-02": 15},
            },
        )

        assert result.bookmark_id == 12345
        assert result.computed_at == "2024-01-15T10:30:00"
        assert result.from_date == "2024-01-01"
        assert result.to_date == "2024-01-14"
        assert result.headers == ["$event"]

    def test_report_type_insights(self) -> None:
        """Test report_type detection for insights reports."""
        result = SavedReportResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            from_date="2024-01-01",
            to_date="2024-01-31",
            headers=["$event", "Date"],
            series={},
        )

        assert result.report_type == "insights"

    def test_report_type_retention(self) -> None:
        """Test report_type detection for retention reports."""
        result = SavedReportResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            from_date="2024-01-01",
            to_date="2024-01-31",
            headers=["$retention"],
            series={},
        )

        assert result.report_type == "retention"

    def test_report_type_retention_case_insensitive(self) -> None:
        """Test report_type detection is case-insensitive for retention."""
        result = SavedReportResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            from_date="2024-01-01",
            to_date="2024-01-31",
            headers=["$RETENTION"],
            series={},
        )

        assert result.report_type == "retention"

    def test_report_type_funnel(self) -> None:
        """Test report_type detection for funnel reports."""
        result = SavedReportResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            from_date="2024-01-01",
            to_date="2024-01-31",
            headers=["$funnel"],
            series={},
        )

        assert result.report_type == "funnel"

    def test_report_type_funnel_case_insensitive(self) -> None:
        """Test report_type detection is case-insensitive for funnel."""
        result = SavedReportResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            from_date="2024-01-01",
            to_date="2024-01-31",
            headers=["$FUNNEL"],
            series={},
        )

        assert result.report_type == "funnel"

    def test_report_type_empty_headers(self) -> None:
        """Test report_type defaults to insights when headers are empty."""
        result = SavedReportResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            from_date="2024-01-01",
            to_date="2024-01-31",
            headers=[],
            series={},
        )

        assert result.report_type == "insights"

    def test_df_property_insights(self) -> None:
        """Test DataFrame conversion for insights reports."""
        result = SavedReportResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            from_date="2024-01-01",
            to_date="2024-01-02",
            headers=["$event"],
            series={
                "Page View": {"2024-01-01": 100, "2024-01-02": 150},
                "Sign Up": {"2024-01-01": 10, "2024-01-02": 15},
            },
        )

        df = result.df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 4
        assert set(df.columns) == {"date", "event", "count"}

    def test_df_property_cached(self) -> None:
        """Test that DataFrame is cached after first access."""
        result = SavedReportResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            from_date="2024-01-01",
            to_date="2024-01-02",
            headers=[],
            series={"Event": {"2024-01-01": 100}},
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2  # Same object (cached)

    def test_df_property_empty_series(self) -> None:
        """Test DataFrame conversion with empty series."""
        result = SavedReportResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            from_date="2024-01-01",
            to_date="2024-01-31",
            headers=[],
            series={},
        )

        df = result.df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert list(df.columns) == ["date", "event", "count"]

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        result = SavedReportResult(
            bookmark_id=12345,
            computed_at="2024-01-15T10:30:00",
            from_date="2024-01-01",
            to_date="2024-01-14",
            headers=["$event"],
            series={"Event": {"2024-01-01": 100}},
        )

        d = result.to_dict()
        assert d["bookmark_id"] == 12345
        assert d["computed_at"] == "2024-01-15T10:30:00"
        assert d["from_date"] == "2024-01-01"
        assert d["to_date"] == "2024-01-14"
        assert d["headers"] == ["$event"]
        assert d["series"] == {"Event": {"2024-01-01": 100}}
        assert d["report_type"] == "insights"

    def test_frozen_dataclass(self) -> None:
        """Test that SavedReportResult is immutable."""
        result = SavedReportResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            from_date="2024-01-01",
            to_date="2024-01-31",
            headers=[],
            series={},
        )

        with pytest.raises(AttributeError):
            result.bookmark_id = 999  # type: ignore[misc]


class TestFlowsResult:
    """Tests for FlowsResult dataclass."""

    def test_create_flows_result(self) -> None:
        """Test creating a flows result."""
        result = FlowsResult(
            bookmark_id=12345,
            computed_at="2024-01-15T10:30:00",
            steps=[
                {"step": 1, "event": "Page View", "count": 1000},
                {"step": 2, "event": "Add to Cart", "count": 500},
            ],
            breakdowns=[
                {"path": "Page View -> Add to Cart", "count": 500},
            ],
            overall_conversion_rate=0.5,
            metadata={"version": "1.0"},
        )

        assert result.bookmark_id == 12345
        assert result.computed_at == "2024-01-15T10:30:00"
        assert len(result.steps) == 2
        assert len(result.breakdowns) == 1
        assert result.overall_conversion_rate == 0.5
        assert result.metadata == {"version": "1.0"}

    def test_df_property(self) -> None:
        """Test DataFrame conversion for flows results."""
        result = FlowsResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            steps=[
                {"step": 1, "event": "Page View", "count": 1000},
                {"step": 2, "event": "Add to Cart", "count": 500},
            ],
            breakdowns=[],
            overall_conversion_rate=0.5,
        )

        df = result.df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "step" in df.columns
        assert "event" in df.columns
        assert "count" in df.columns

    def test_df_property_cached(self) -> None:
        """Test that DataFrame is cached after first access."""
        result = FlowsResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            steps=[{"step": 1, "event": "Event", "count": 100}],
            breakdowns=[],
            overall_conversion_rate=1.0,
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2  # Same object (cached)

    def test_df_property_empty_steps(self) -> None:
        """Test DataFrame conversion with empty steps."""
        result = FlowsResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            steps=[],
            breakdowns=[],
            overall_conversion_rate=0.0,
        )

        df = result.df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        result = FlowsResult(
            bookmark_id=12345,
            computed_at="2024-01-15T10:30:00",
            steps=[{"step": 1, "event": "Event", "count": 100}],
            breakdowns=[{"path": "A -> B", "count": 50}],
            overall_conversion_rate=0.5,
            metadata={"key": "value"},
        )

        d = result.to_dict()
        assert d["bookmark_id"] == 12345
        assert d["computed_at"] == "2024-01-15T10:30:00"
        assert d["steps"] == [{"step": 1, "event": "Event", "count": 100}]
        assert d["breakdowns"] == [{"path": "A -> B", "count": 50}]
        assert d["overall_conversion_rate"] == 0.5
        assert d["metadata"] == {"key": "value"}

    def test_frozen_dataclass(self) -> None:
        """Test that FlowsResult is immutable."""
        result = FlowsResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            steps=[],
            breakdowns=[],
            overall_conversion_rate=0.0,
        )

        with pytest.raises(AttributeError):
            result.bookmark_id = 999  # type: ignore[misc]

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        result = FlowsResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
        )

        assert result.steps == []
        assert result.breakdowns == []
        assert result.overall_conversion_rate == 0.0
        assert result.metadata == {}


class TestBookmarkInfo:
    """Tests for BookmarkInfo dataclass."""

    def test_create_bookmark_info(self) -> None:
        """Test creating a bookmark info."""
        info = BookmarkInfo(
            id=12345,
            name="Weekly Active Users",
            type="insights",
            project_id=100,
            created="2024-01-01T00:00:00",
            modified="2024-01-15T10:30:00",
        )

        assert info.id == 12345
        assert info.name == "Weekly Active Users"
        assert info.type == "insights"
        assert info.project_id == 100
        assert info.created == "2024-01-01T00:00:00"
        assert info.modified == "2024-01-15T10:30:00"

    def test_create_with_optional_fields(self) -> None:
        """Test creating a bookmark info with optional fields."""
        info = BookmarkInfo(
            id=12345,
            name="User Funnel",
            type="funnels",
            project_id=100,
            created="2024-01-01T00:00:00",
            modified="2024-01-15T10:30:00",
            workspace_id=1,
            dashboard_id=5,
            description="Main conversion funnel",
            creator_id=42,
            creator_name="John Doe",
        )

        assert info.workspace_id == 1
        assert info.dashboard_id == 5
        assert info.description == "Main conversion funnel"
        assert info.creator_id == 42
        assert info.creator_name == "John Doe"

    def test_default_optional_fields(self) -> None:
        """Test that optional fields default to None."""
        info = BookmarkInfo(
            id=1,
            name="Test",
            type="insights",
            project_id=100,
            created="2024-01-01T00:00:00",
            modified="2024-01-01T00:00:00",
        )

        assert info.workspace_id is None
        assert info.dashboard_id is None
        assert info.description is None
        assert info.creator_id is None
        assert info.creator_name is None

    def test_to_dict_minimal(self) -> None:
        """Test serialization to dictionary with minimal fields."""
        info = BookmarkInfo(
            id=12345,
            name="Test Report",
            type="retention",
            project_id=100,
            created="2024-01-01T00:00:00",
            modified="2024-01-15T10:30:00",
        )

        d = info.to_dict()
        assert d["id"] == 12345
        assert d["name"] == "Test Report"
        assert d["type"] == "retention"
        assert d["project_id"] == 100
        assert d["created"] == "2024-01-01T00:00:00"
        assert d["modified"] == "2024-01-15T10:30:00"
        # Optional fields should not be in dict when None
        assert "workspace_id" not in d
        assert "dashboard_id" not in d
        assert "description" not in d
        assert "creator_id" not in d
        assert "creator_name" not in d

    def test_to_dict_with_optional_fields(self) -> None:
        """Test serialization includes optional fields when set."""
        info = BookmarkInfo(
            id=12345,
            name="Test Report",
            type="flows",
            project_id=100,
            created="2024-01-01T00:00:00",
            modified="2024-01-15T10:30:00",
            workspace_id=1,
            dashboard_id=5,
            description="A test",
            creator_id=42,
            creator_name="Test User",
        )

        d = info.to_dict()
        assert d["workspace_id"] == 1
        assert d["dashboard_id"] == 5
        assert d["description"] == "A test"
        assert d["creator_id"] == 42
        assert d["creator_name"] == "Test User"

    def test_frozen_dataclass(self) -> None:
        """Test that BookmarkInfo is immutable."""
        info = BookmarkInfo(
            id=1,
            name="Test",
            type="insights",
            project_id=100,
            created="2024-01-01T00:00:00",
            modified="2024-01-01T00:00:00",
        )

        with pytest.raises(AttributeError):
            info.id = 999  # type: ignore[misc]

    def test_all_bookmark_types(self) -> None:
        """Test that all valid bookmark types can be used."""
        bookmark_types: list[BookmarkType] = [
            "insights",
            "funnels",
            "retention",
            "flows",
            "launch-analysis",
        ]

        for bm_type in bookmark_types:
            info = BookmarkInfo(
                id=1,
                name="Test",
                type=bm_type,
                project_id=100,
                created="2024-01-01T00:00:00",
                modified="2024-01-01T00:00:00",
            )
            assert info.type == bm_type


class TestTypeAliases:
    """Tests for type aliases."""

    def test_bookmark_type_values(self) -> None:
        """Test that BookmarkType accepts all valid values."""
        valid_types: list[BookmarkType] = [
            "insights",
            "funnels",
            "retention",
            "flows",
            "launch-analysis",
        ]
        # This test verifies the type alias at runtime
        for t in valid_types:
            assert isinstance(t, str)

    def test_saved_report_type_values(self) -> None:
        """Test that SavedReportType accepts all valid values."""
        valid_types: list[SavedReportType] = [
            "insights",
            "retention",
            "funnel",
        ]
        # This test verifies the type alias at runtime
        for t in valid_types:
            assert isinstance(t, str)
