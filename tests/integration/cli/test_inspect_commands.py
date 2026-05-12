"""Integration tests for inspect CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_headless.cli.main import app
from mixpanel_headless.types import (
    DailyCount,
    DailyCountsResult,
    EngagementBucket,
    EngagementDistributionResult,
    FunnelInfo,
    LexiconDefinition,
    LexiconProperty,
    LexiconSchema,
    NumericPropertySummaryResult,
    PropertyCoverage,
    PropertyCoverageResult,
    PropertyDistributionResult,
    PropertyValueCount,
    SavedCohort,
    TopEvent,
)


class TestInspectEvents:
    """Tests for mp inspect events command."""

    def test_events_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing events in JSON format."""
        mock_workspace.events.return_value = ["Event A", "Event B", "Event C"]

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["inspect", "events", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == ["Event A", "Event B", "Event C"]

    def test_events_plain_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing events in plain format."""
        mock_workspace.events.return_value = ["Event A", "Event B"]

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["inspect", "events", "--format", "plain"])

        assert result.exit_code == 0
        assert "Event A" in result.stdout
        assert "Event B" in result.stdout


class TestInspectProperties:
    """Tests for mp inspect properties command."""

    def test_properties_for_event(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing properties for an event."""
        mock_workspace.properties.return_value = ["prop1", "prop2", "prop3"]

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["inspect", "properties", "--event", "Sign Up", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == ["prop1", "prop2", "prop3"]
        mock_workspace.properties.assert_called_once_with("Sign Up")


class TestInspectValues:
    """Tests for mp inspect values command."""

    def test_values_with_all_options(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing values with event and limit options."""
        mock_workspace.property_values.return_value = ["value1", "value2"]

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "inspect",
                    "values",
                    "--property",
                    "country",
                    "--event",
                    "Purchase",
                    "--limit",
                    "50",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == ["value1", "value2"]
        mock_workspace.property_values.assert_called_once_with(
            property_name="country", event="Purchase", limit=50
        )

    def test_values_without_event(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing values without event filter."""
        mock_workspace.property_values.return_value = ["US", "EU", "APAC"]

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["inspect", "values", "--property", "region", "--format", "json"],
            )

        assert result.exit_code == 0
        mock_workspace.property_values.assert_called_once_with(
            property_name="region", event=None, limit=100
        )


class TestInspectFunnels:
    """Tests for mp inspect funnels command."""

    def test_funnels_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing funnels in JSON format."""
        mock_workspace.funnels.return_value = [
            FunnelInfo(funnel_id=123, name="Checkout Funnel"),
            FunnelInfo(funnel_id=456, name="Signup Flow"),
        ]

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["inspect", "funnels", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 2
        assert data[0]["funnel_id"] == 123
        assert data[0]["name"] == "Checkout Funnel"


class TestInspectCohorts:
    """Tests for mp inspect cohorts command."""

    def test_cohorts_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing cohorts in JSON format."""
        mock_workspace.cohorts.return_value = [
            SavedCohort(
                id=1,
                name="Power Users",
                count=1000,
                description="Active users",
                created="2024-01-01 12:00:00",
                is_visible=True,
            ),
            SavedCohort(
                id=2,
                name="New Users",
                count=500,
                description="Recent signups",
                created="2024-01-15 10:00:00",
                is_visible=True,
            ),
        ]

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["inspect", "cohorts", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 2
        assert data[0]["id"] == 1
        assert data[0]["name"] == "Power Users"
        assert data[0]["count"] == 1000


class TestInspectTopEvents:
    """Tests for mp inspect top-events command."""

    def test_top_events_default_options(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing top events with default options."""
        mock_workspace.top_events.return_value = [
            TopEvent(event="Page View", count=10000, percent_change=5.2),
            TopEvent(event="Sign Up", count=500, percent_change=-2.1),
        ]

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["inspect", "top-events", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 2
        assert data[0]["event"] == "Page View"
        assert data[0]["count"] == 10000
        mock_workspace.top_events.assert_called_once_with(type="general", limit=10)

    def test_top_events_with_type_and_limit(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing top events with custom type and limit."""
        mock_workspace.top_events.return_value = []

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "inspect",
                    "top-events",
                    "--type",
                    "unique",
                    "--limit",
                    "5",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        mock_workspace.top_events.assert_called_once_with(type="unique", limit=5)


class TestInspectLexiconSchemas:
    """Tests for mp inspect lexicon-schemas command."""

    def test_lexicon_schemas_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing Lexicon schemas in JSON format."""
        mock_workspace.lexicon_schemas.return_value = [
            LexiconSchema(
                entity_type="event",
                name="Purchase",
                schema_json=LexiconDefinition(
                    description="User made a purchase",
                    properties={
                        "amount": LexiconProperty(
                            type="number", description="Amount", metadata=None
                        ),
                    },
                    metadata=None,
                ),
            ),
            LexiconSchema(
                entity_type="profile",
                name="Plan Type",
                schema_json=LexiconDefinition(
                    description="User subscription plan",
                    properties={},
                    metadata=None,
                ),
            ),
        ]

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["inspect", "lexicon-schemas", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 2
        assert data[0]["entity_type"] == "event"
        assert data[0]["name"] == "Purchase"
        assert data[0]["property_count"] == 1
        assert data[1]["entity_type"] == "profile"

    def test_lexicon_schemas_with_type_filter(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test filtering Lexicon schemas by entity type."""
        mock_workspace.lexicon_schemas.return_value = [
            LexiconSchema(
                entity_type="event",
                name="Login",
                schema_json=LexiconDefinition(
                    description="User logged in",
                    properties={},
                    metadata=None,
                ),
            ),
        ]

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["inspect", "lexicon-schemas", "--type", "event", "--format", "json"],
            )

        assert result.exit_code == 0
        mock_workspace.lexicon_schemas.assert_called_once_with(entity_type="event")

    def test_lexicon_schemas_invalid_type(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test invalid entity type returns error."""
        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["inspect", "lexicon-schemas", "--type", "invalid"]
            )

        assert result.exit_code == 3  # INVALID_ARGS


class TestInspectLexiconSchema:
    """Tests for mp inspect lexicon-schema command."""

    def test_lexicon_schema_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test getting single Lexicon schema in JSON format."""
        mock_workspace.lexicon_schema.return_value = LexiconSchema(
            entity_type="event",
            name="Purchase",
            schema_json=LexiconDefinition(
                description="User made a purchase",
                properties={
                    "amount": LexiconProperty(
                        type="number", description="Purchase amount", metadata=None
                    ),
                    "currency": LexiconProperty(
                        type="string", description="Currency code", metadata=None
                    ),
                },
                metadata=None,
            ),
        )

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "inspect",
                    "lexicon-schema",
                    "--type",
                    "event",
                    "--name",
                    "Purchase",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["entity_type"] == "event"
        assert data["name"] == "Purchase"
        assert "amount" in data["schema_json"]["properties"]
        assert "currency" in data["schema_json"]["properties"]
        mock_workspace.lexicon_schema.assert_called_once_with("event", "Purchase")

    def test_lexicon_schema_invalid_type(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test invalid entity type returns error."""
        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "inspect",
                    "lexicon-schema",
                    "--type",
                    "invalid",
                    "--name",
                    "Test",
                ],
            )

        assert result.exit_code == 3  # INVALID_ARGS


# =============================================================================
# JQL-based Discovery Command Tests
# =============================================================================


class TestInspectDistribution:
    """Tests for mp inspect distribution command."""

    def test_distribution_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test property distribution in JSON format."""
        mock_workspace.property_distribution.return_value = PropertyDistributionResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_count=1000,
            values=(
                PropertyValueCount(value="US", count=500, percentage=50.0),
                PropertyValueCount(value="UK", count=300, percentage=30.0),
                PropertyValueCount(value="DE", count=200, percentage=20.0),
            ),
        )

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "inspect",
                    "distribution",
                    "--event",
                    "Purchase",
                    "--property",
                    "country",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["event"] == "Purchase"
        assert data["property_name"] == "country"
        assert data["total_count"] == 1000
        assert len(data["values"]) == 3
        assert data["values"][0]["value"] == "US"
        mock_workspace.property_distribution.assert_called_once_with(
            event="Purchase",
            property="country",
            from_date="2024-01-01",
            to_date="2024-01-31",
            limit=20,
        )


class TestInspectNumeric:
    """Tests for mp inspect numeric command."""

    def test_numeric_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test numeric property summary in JSON format."""
        mock_workspace.numeric_summary.return_value = NumericPropertySummaryResult(
            event="Purchase",
            property_name="amount",
            from_date="2024-01-01",
            to_date="2024-01-31",
            count=5000,
            min=9.99,
            max=999.99,
            sum=125000.50,
            avg=25.00,
            stddev=45.75,
            percentiles={25: 12.99, 50: 19.99, 75: 49.99, 90: 99.99},
        )

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "inspect",
                    "numeric",
                    "--event",
                    "Purchase",
                    "--property",
                    "amount",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["event"] == "Purchase"
        assert data["property_name"] == "amount"
        assert data["count"] == 5000
        assert data["min"] == 9.99
        assert data["max"] == 999.99
        assert data["avg"] == 25.00
        mock_workspace.numeric_summary.assert_called_once_with(
            event="Purchase",
            property="amount",
            from_date="2024-01-01",
            to_date="2024-01-31",
            percentiles=None,
        )


class TestInspectDaily:
    """Tests for mp inspect daily command."""

    def test_daily_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test daily counts in JSON format."""
        mock_workspace.daily_counts.return_value = DailyCountsResult(
            from_date="2024-01-01",
            to_date="2024-01-07",
            events=None,
            counts=(
                DailyCount(date="2024-01-01", event="Page View", count=500),
                DailyCount(date="2024-01-01", event="Sign Up", count=50),
                DailyCount(date="2024-01-02", event="Page View", count=550),
                DailyCount(date="2024-01-02", event="Sign Up", count=45),
            ),
        )

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "inspect",
                    "daily",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-07",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["from_date"] == "2024-01-01"
        assert data["to_date"] == "2024-01-07"
        assert len(data["counts"]) == 4
        assert data["counts"][0]["date"] == "2024-01-01"
        mock_workspace.daily_counts.assert_called_once_with(
            from_date="2024-01-01",
            to_date="2024-01-07",
            events=None,
        )


class TestInspectEngagement:
    """Tests for mp inspect engagement command."""

    def test_engagement_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test engagement distribution in JSON format."""
        mock_workspace.engagement_distribution.return_value = (
            EngagementDistributionResult(
                from_date="2024-01-01",
                to_date="2024-01-31",
                events=None,
                total_users=8500,
                buckets=(
                    EngagementBucket(
                        bucket_min=1, bucket_label="1", user_count=2500, percentage=29.4
                    ),
                    EngagementBucket(
                        bucket_min=2,
                        bucket_label="2-5",
                        user_count=3200,
                        percentage=37.6,
                    ),
                    EngagementBucket(
                        bucket_min=6,
                        bucket_label="6-10",
                        user_count=1800,
                        percentage=21.2,
                    ),
                    EngagementBucket(
                        bucket_min=11,
                        bucket_label="11+",
                        user_count=1000,
                        percentage=11.8,
                    ),
                ),
            )
        )

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "inspect",
                    "engagement",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["from_date"] == "2024-01-01"
        assert data["to_date"] == "2024-01-31"
        assert data["total_users"] == 8500
        assert len(data["buckets"]) == 4
        assert data["buckets"][0]["bucket_label"] == "1"
        mock_workspace.engagement_distribution.assert_called_once_with(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=None,
            buckets=None,
        )


class TestInspectCoverage:
    """Tests for mp inspect coverage command."""

    def test_coverage_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test property coverage in JSON format."""
        mock_workspace.property_coverage.return_value = PropertyCoverageResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_events=5000,
            coverage=(
                PropertyCoverage(
                    property="amount",
                    defined_count=5000,
                    null_count=0,
                    coverage_percentage=100.0,
                ),
                PropertyCoverage(
                    property="coupon_code",
                    defined_count=1250,
                    null_count=3750,
                    coverage_percentage=25.0,
                ),
            ),
        )

        with patch(
            "mixpanel_headless.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "inspect",
                    "coverage",
                    "--event",
                    "Purchase",
                    "--properties",
                    "amount,coupon_code",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["event"] == "Purchase"
        assert data["total_events"] == 5000
        assert len(data["coverage"]) == 2
        assert data["coverage"][0]["property"] == "amount"
        assert data["coverage"][0]["coverage_percentage"] == 100.0
        mock_workspace.property_coverage.assert_called_once_with(
            event="Purchase",
            properties=["amount", "coupon_code"],
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
