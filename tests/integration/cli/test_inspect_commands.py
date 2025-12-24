"""Integration tests for inspect CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_data.cli.main import app
from mixpanel_data.types import (
    ColumnInfo,
    FunnelInfo,
    LexiconDefinition,
    LexiconProperty,
    LexiconSchema,
    SavedCohort,
    TableInfo,
    TableSchema,
    TopEvent,
    WorkspaceInfo,
)


class TestInspectEvents:
    """Tests for mp inspect events command."""

    def test_events_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing events in JSON format."""
        mock_workspace.events.return_value = ["Event A", "Event B", "Event C"]

        with patch(
            "mixpanel_data.cli.commands.inspect.get_workspace",
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
            "mixpanel_data.cli.commands.inspect.get_workspace",
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
            "mixpanel_data.cli.commands.inspect.get_workspace",
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
            "mixpanel_data.cli.commands.inspect.get_workspace",
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
            "mixpanel_data.cli.commands.inspect.get_workspace",
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
            "mixpanel_data.cli.commands.inspect.get_workspace",
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
            "mixpanel_data.cli.commands.inspect.get_workspace",
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
            "mixpanel_data.cli.commands.inspect.get_workspace",
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
            "mixpanel_data.cli.commands.inspect.get_workspace",
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


class TestInspectInfo:
    """Tests for mp inspect info command."""

    def test_info_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test showing workspace info in JSON format."""
        mock_workspace.info.return_value = WorkspaceInfo(
            path="/tmp/test.db",
            account="production",
            project_id="12345",
            region="us",
            tables=["events", "profiles", "other"],
            size_mb=10.5,
            created_at=None,
        )

        with patch(
            "mixpanel_data.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["inspect", "info", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["path"] == "/tmp/test.db"
        assert data["project_id"] == "12345"
        assert data["tables"] == ["events", "profiles", "other"]


class TestInspectTables:
    """Tests for mp inspect tables command."""

    def test_tables_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing tables in JSON format."""
        mock_workspace.tables.return_value = [
            TableInfo(
                name="events_jan",
                type="events",
                row_count=1000,
                fetched_at="2024-01-31T12:00:00Z",
            ),
            TableInfo(
                name="profiles",
                type="profiles",
                row_count=500,
                fetched_at="2024-01-30T10:00:00Z",
            ),
        ]

        with patch(
            "mixpanel_data.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["inspect", "tables", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 2
        assert data[0]["name"] == "events_jan"
        assert data[0]["row_count"] == 1000


class TestInspectSchema:
    """Tests for mp inspect schema command."""

    def test_schema_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test showing table schema in JSON format."""
        mock_workspace.table_schema.return_value = TableSchema(
            table_name="events",
            columns=[
                ColumnInfo(name="event", type="VARCHAR", nullable=False),
                ColumnInfo(name="time", type="TIMESTAMP", nullable=False),
                ColumnInfo(name="properties", type="JSON", nullable=True),
            ],
        )

        with patch(
            "mixpanel_data.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["inspect", "schema", "--table", "events", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["table"] == "events"
        assert len(data["columns"]) == 3
        assert data["columns"][0]["name"] == "event"
        assert data["columns"][0]["type"] == "VARCHAR"


class TestInspectDrop:
    """Tests for mp inspect drop command."""

    def test_drop_with_force_flag(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test dropping table with --force flag skips confirmation."""
        with patch(
            "mixpanel_data.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "inspect",
                    "drop",
                    "--table",
                    "old_events",
                    "--force",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["dropped"] == "old_events"
        mock_workspace.drop.assert_called_once_with("old_events")

    def test_drop_confirms_with_user(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test dropping table prompts for confirmation."""
        with patch(
            "mixpanel_data.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            # Simulate user confirming 'y'
            result = cli_runner.invoke(
                app,
                ["inspect", "drop", "--table", "test_table", "--format", "json"],
                input="y\n",
            )

        assert result.exit_code == 0
        mock_workspace.drop.assert_called_once_with("test_table")

    def test_drop_cancelled_by_user(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test dropping table cancelled when user declines."""
        with patch(
            "mixpanel_data.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            # Simulate user declining 'n'
            result = cli_runner.invoke(
                app,
                ["inspect", "drop", "--table", "test_table"],
                input="n\n",
            )

        assert result.exit_code == 2  # Cancelled
        mock_workspace.drop.assert_not_called()


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
            "mixpanel_data.cli.commands.inspect.get_workspace",
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
            "mixpanel_data.cli.commands.inspect.get_workspace",
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
            "mixpanel_data.cli.commands.inspect.get_workspace",
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
            "mixpanel_data.cli.commands.inspect.get_workspace",
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
            "mixpanel_data.cli.commands.inspect.get_workspace",
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
