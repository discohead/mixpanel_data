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
        from mp_mcp_server.resources import _get_date_range

        from_date, to_date = _get_date_range(30)
        assert from_date < to_date
        assert len(from_date) == 10  # YYYY-MM-DD
        assert len(to_date) == 10

    def test_get_date_range_7_days(self) -> None:
        """_get_date_range should work for 7 days."""
        from mp_mcp_server.resources import _get_date_range

        from_date, to_date = _get_date_range(7)
        assert from_date < to_date

    def test_get_date_range_90_days(self) -> None:
        """_get_date_range should work for 90 days."""
        from mp_mcp_server.resources import _get_date_range

        from_date, to_date = _get_date_range(90)
        assert from_date < to_date

    def test_get_date_range_1_day(self) -> None:
        """_get_date_range should work for 1 day."""
        from mp_mcp_server.resources import _get_date_range

        from_date, to_date = _get_date_range(1)
        assert from_date < to_date

    def test_get_date_range_365_days(self) -> None:
        """_get_date_range should work for 365 days."""
        from mp_mcp_server.resources import _get_date_range

        from_date, to_date = _get_date_range(365)
        assert from_date < to_date


class TestResourceTemplateRegistration:
    """Tests for dynamic resource template registration."""

    def test_retention_weekly_registered(self) -> None:
        """Retention weekly resource template should be registered."""
        from mp_mcp_server.server import mcp

        template_keys = list(mcp._resource_manager._templates)
        assert any("retention" in str(k) for k in template_keys)

    def test_trends_registered(self) -> None:
        """Trends resource template should be registered."""
        from mp_mcp_server.server import mcp

        template_keys = list(mcp._resource_manager._templates)
        assert any("trends" in str(k) for k in template_keys)

    def test_user_journey_registered(self) -> None:
        """User journey resource template should be registered."""
        from mp_mcp_server.server import mcp

        template_keys = list(mcp._resource_manager._templates)
        assert any("journey" in str(k) for k in template_keys)

    def test_weekly_review_registered(self) -> None:
        """Weekly review recipe should be registered."""
        from mp_mcp_server.server import mcp

        resource_keys = list(mcp._resource_manager._resources.keys())
        assert any("weekly-review" in str(k) for k in resource_keys)

    def test_churn_investigation_registered(self) -> None:
        """Churn investigation recipe should be registered."""
        from mp_mcp_server.server import mcp

        resource_keys = list(mcp._resource_manager._resources.keys())
        assert any("churn-investigation" in str(k) for k in resource_keys)


class TestStaticResourceRegistration:
    """Tests for static resource registration."""

    def test_workspace_info_registered(self) -> None:
        """workspace://info resource should be registered."""
        from mp_mcp_server.server import mcp

        resource_keys = list(mcp._resource_manager._resources.keys())
        assert "workspace://info" in resource_keys

    def test_tables_registered(self) -> None:
        """workspace://tables resource should be registered."""
        from mp_mcp_server.server import mcp

        resource_keys = list(mcp._resource_manager._resources.keys())
        assert "workspace://tables" in resource_keys

    def test_events_registered(self) -> None:
        """schema://events resource should be registered."""
        from mp_mcp_server.server import mcp

        resource_keys = list(mcp._resource_manager._resources.keys())
        assert "schema://events" in resource_keys

    def test_funnels_registered(self) -> None:
        """schema://funnels resource should be registered."""
        from mp_mcp_server.server import mcp

        resource_keys = list(mcp._resource_manager._resources.keys())
        assert "schema://funnels" in resource_keys

    def test_cohorts_registered(self) -> None:
        """schema://cohorts resource should be registered."""
        from mp_mcp_server.server import mcp

        resource_keys = list(mcp._resource_manager._resources.keys())
        assert "schema://cohorts" in resource_keys

    def test_bookmarks_registered(self) -> None:
        """schema://bookmarks resource should be registered."""
        from mp_mcp_server.server import mcp

        resource_keys = list(mcp._resource_manager._resources.keys())
        assert "schema://bookmarks" in resource_keys


class TestResourceTemplatePatterns:
    """Tests for resource template URI patterns."""

    def test_retention_template_has_event_param(self) -> None:
        """Retention template should have event parameter."""
        from mp_mcp_server.server import mcp

        template_keys = [str(k) for k in mcp._resource_manager._templates]
        retention_templates = [k for k in template_keys if "retention" in k]
        assert any("{event}" in k for k in retention_templates)

    def test_trends_template_has_event_and_days(self) -> None:
        """Trends template should have event and days parameters."""
        from mp_mcp_server.server import mcp

        template_keys = [str(k) for k in mcp._resource_manager._templates]
        trends_templates = [k for k in template_keys if "trends" in k]
        assert any("{event}" in k and "{days}" in k for k in trends_templates)

    def test_user_journey_template_has_id(self) -> None:
        """User journey template should have id parameter."""
        from mp_mcp_server.server import mcp

        template_keys = [str(k) for k in mcp._resource_manager._templates]
        journey_templates = [k for k in template_keys if "journey" in k]
        assert any("{id}" in k for k in journey_templates)


class TestResourceModuleExports:
    """Tests for resource module exports."""

    def test_handle_resource_errors_exported(self) -> None:
        """handle_resource_errors decorator should be exported."""
        from mp_mcp_server.resources import handle_resource_errors

        assert callable(handle_resource_errors)

    def test_get_date_range_exported(self) -> None:
        """_get_date_range helper should be accessible."""
        from mp_mcp_server.resources import _get_date_range

        assert callable(_get_date_range)

    def test_workspace_info_resource_exported(self) -> None:
        """workspace_info_resource should be accessible."""
        from mp_mcp_server.resources import workspace_info_resource

        # It's a FunctionResource, not directly callable
        assert workspace_info_resource is not None

    def test_retention_weekly_resource_exported(self) -> None:
        """retention_weekly_resource should be accessible."""
        from mp_mcp_server.resources import retention_weekly_resource

        assert retention_weekly_resource is not None

    def test_trends_resource_exported(self) -> None:
        """trends_resource should be accessible."""
        from mp_mcp_server.resources import trends_resource

        assert trends_resource is not None

    def test_user_journey_resource_exported(self) -> None:
        """user_journey_resource should be accessible."""
        from mp_mcp_server.resources import user_journey_resource

        assert user_journey_resource is not None

    def test_weekly_review_recipe_exported(self) -> None:
        """weekly_review_recipe should be accessible."""
        from mp_mcp_server.resources import weekly_review_recipe

        assert weekly_review_recipe is not None

    def test_churn_investigation_recipe_exported(self) -> None:
        """churn_investigation_recipe should be accessible."""
        from mp_mcp_server.resources import churn_investigation_recipe

        assert churn_investigation_recipe is not None
