"""Tests for dynamic MCP resources.

These tests verify the dynamic resource templates are registered correctly
and that helper functions work as expected.

Note: Resource function execution is tested in integration tests
(test_server_integration.py) due to FastMCP's async context handling.
"""


class TestDateRangeHelper:
    """Tests for _get_date_range helper function."""

    def test_get_date_range(self) -> None:
        """_get_date_range should return valid date strings."""
        from mp_mcp.resources import _get_date_range

        from_date, to_date = _get_date_range(30)
        assert from_date < to_date
        assert len(from_date) == 10  # YYYY-MM-DD
        assert len(to_date) == 10

    def test_get_date_range_7_days(self) -> None:
        """_get_date_range should work for 7 days."""
        from mp_mcp.resources import _get_date_range

        from_date, to_date = _get_date_range(7)
        assert from_date < to_date

    def test_get_date_range_90_days(self) -> None:
        """_get_date_range should work for 90 days."""
        from mp_mcp.resources import _get_date_range

        from_date, to_date = _get_date_range(90)
        assert from_date < to_date

    def test_get_date_range_1_day(self) -> None:
        """_get_date_range should work for 1 day."""
        from mp_mcp.resources import _get_date_range

        from_date, to_date = _get_date_range(1)
        assert from_date < to_date

    def test_get_date_range_365_days(self) -> None:
        """_get_date_range should work for 365 days."""
        from mp_mcp.resources import _get_date_range

        from_date, to_date = _get_date_range(365)
        assert from_date < to_date


class TestResourceTemplateRegistration:
    """Tests for dynamic resource template registration."""

    def test_retention_weekly_registered(
        self, registered_resource_template_uris: list[str]
    ) -> None:
        """Retention weekly resource template should be registered."""
        assert any("retention" in uri for uri in registered_resource_template_uris)

    def test_trends_registered(
        self, registered_resource_template_uris: list[str]
    ) -> None:
        """Trends resource template should be registered."""
        assert any("trends" in uri for uri in registered_resource_template_uris)

    def test_user_journey_registered(
        self, registered_resource_template_uris: list[str]
    ) -> None:
        """User journey resource template should be registered."""
        assert any("journey" in uri for uri in registered_resource_template_uris)

    def test_weekly_review_registered(
        self, registered_resource_uris: list[str]
    ) -> None:
        """Weekly review recipe should be registered."""
        assert any("weekly-review" in uri for uri in registered_resource_uris)

    def test_churn_investigation_registered(
        self, registered_resource_uris: list[str]
    ) -> None:
        """Churn investigation recipe should be registered."""
        assert any("churn-investigation" in uri for uri in registered_resource_uris)


class TestStaticResourceRegistration:
    """Tests for static resource registration."""

    def test_workspace_info_registered(
        self, registered_resource_uris: list[str]
    ) -> None:
        """workspace://info resource should be registered."""
        assert "workspace://info" in registered_resource_uris

    def test_tables_registered(self, registered_resource_uris: list[str]) -> None:
        """workspace://tables resource should be registered."""
        assert "workspace://tables" in registered_resource_uris

    def test_events_registered(self, registered_resource_uris: list[str]) -> None:
        """schema://events resource should be registered."""
        assert "schema://events" in registered_resource_uris

    def test_funnels_registered(self, registered_resource_uris: list[str]) -> None:
        """schema://funnels resource should be registered."""
        assert "schema://funnels" in registered_resource_uris

    def test_cohorts_registered(self, registered_resource_uris: list[str]) -> None:
        """schema://cohorts resource should be registered."""
        assert "schema://cohorts" in registered_resource_uris

    def test_bookmarks_registered(self, registered_resource_uris: list[str]) -> None:
        """schema://bookmarks resource should be registered."""
        assert "schema://bookmarks" in registered_resource_uris


class TestResourceTemplatePatterns:
    """Tests for resource template URI patterns."""

    def test_retention_template_has_event_param(
        self, registered_resource_template_uris: list[str]
    ) -> None:
        """Retention template should have event parameter."""
        retention_templates = [
            uri for uri in registered_resource_template_uris if "retention" in uri
        ]
        assert any("{event}" in uri for uri in retention_templates)

    def test_trends_template_has_event_and_days(
        self, registered_resource_template_uris: list[str]
    ) -> None:
        """Trends template should have event and days parameters."""
        trends_templates = [
            uri for uri in registered_resource_template_uris if "trends" in uri
        ]
        assert any("{event}" in uri and "{days}" in uri for uri in trends_templates)

    def test_user_journey_template_has_id(
        self, registered_resource_template_uris: list[str]
    ) -> None:
        """User journey template should have id parameter."""
        journey_templates = [
            uri for uri in registered_resource_template_uris if "journey" in uri
        ]
        assert any("{id}" in uri for uri in journey_templates)


class TestResourceModuleExports:
    """Tests for resource module exports."""

    def test_handle_resource_errors_exported(self) -> None:
        """handle_resource_errors decorator should be exported."""
        from mp_mcp.resources import handle_resource_errors

        assert callable(handle_resource_errors)

    def test_get_date_range_exported(self) -> None:
        """_get_date_range helper should be accessible."""
        from mp_mcp.resources import _get_date_range

        assert callable(_get_date_range)

    def test_workspace_info_resource_exported(self) -> None:
        """workspace_info_resource should be accessible."""
        from mp_mcp.resources import workspace_info_resource

        # It's a FunctionResource, not directly callable
        assert workspace_info_resource is not None

    def test_retention_weekly_resource_exported(self) -> None:
        """retention_weekly_resource should be accessible."""
        from mp_mcp.resources import retention_weekly_resource

        assert retention_weekly_resource is not None

    def test_trends_resource_exported(self) -> None:
        """trends_resource should be accessible."""
        from mp_mcp.resources import trends_resource

        assert trends_resource is not None

    def test_user_journey_resource_exported(self) -> None:
        """user_journey_resource should be accessible."""
        from mp_mcp.resources import user_journey_resource

        assert user_journey_resource is not None

    def test_weekly_review_recipe_exported(self) -> None:
        """weekly_review_recipe should be accessible."""
        from mp_mcp.resources import weekly_review_recipe

        assert weekly_review_recipe is not None

    def test_churn_investigation_recipe_exported(self) -> None:
        """churn_investigation_recipe should be accessible."""
        from mp_mcp.resources import churn_investigation_recipe

        assert churn_investigation_recipe is not None
