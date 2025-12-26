"""Integration tests for Workspace facade."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_data import Workspace, WorkspaceInfo
from mixpanel_data._internal.config import ConfigManager, Credentials
from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data.types import TableMetadata

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_credentials() -> Credentials:
    """Create mock credentials for testing."""
    return Credentials(
        username="test_user",
        secret=SecretStr("test_secret"),
        project_id="12345",
        region="us",
    )


@pytest.fixture
def mock_config_manager(mock_credentials: Credentials) -> MagicMock:
    """Create mock ConfigManager that returns credentials."""
    manager = MagicMock(spec=ConfigManager)
    manager.resolve_credentials.return_value = mock_credentials
    return manager


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create mock API client for testing."""
    from mixpanel_data._internal.api_client import MixpanelAPIClient

    client = MagicMock(spec=MixpanelAPIClient)
    client.close = MagicMock()

    # Set up common mock responses
    client.export_events.return_value = iter([])
    client.export_profiles.return_value = iter([])

    return client


# =============================================================================
# US1: Fetch-Query Workflow Integration Tests
# =============================================================================


class TestFetchQueryWorkflow:
    """Integration tests for fetch → query workflow (T027-T028)."""

    def test_fetch_query_workflow(
        self,
        mock_config_manager: MagicMock,
        mock_api_client: MagicMock,
        temp_dir: Path,
    ) -> None:
        """T027: Integration test for fetch-query workflow.

        This test verifies the complete workflow of fetching events
        and querying them with SQL.
        """
        # Set up mock to return events
        events = [
            {
                "event": "Page View",
                "properties": {
                    "distinct_id": "user1",
                    "time": 1704067200,  # 2024-01-01 00:00:00 UTC
                    "$insert_id": "insert1",
                    "page": "/home",
                },
            },
            {
                "event": "Page View",
                "properties": {
                    "distinct_id": "user2",
                    "time": 1704153600,  # 2024-01-02 00:00:00 UTC
                    "$insert_id": "insert2",
                    "page": "/about",
                },
            },
        ]
        mock_api_client.export_events.return_value = iter(events)

        db_path = temp_dir / "test_workflow.db"
        storage = StorageEngine(path=db_path)

        with Workspace(
            _config_manager=mock_config_manager,
            _api_client=mock_api_client,
            _storage=storage,
        ) as ws:
            # Fetch events
            result = ws.fetch_events(
                "events",
                from_date="2024-01-01",
                to_date="2024-01-31",
                progress=False,
            )

            assert result.table == "events"
            assert result.rows == 2
            assert result.type == "events"

            # Query the data
            df = ws.sql("SELECT event_name, COUNT(*) as cnt FROM events GROUP BY 1")
            assert len(df) == 1
            assert df.iloc[0]["event_name"] == "Page View"
            assert df.iloc[0]["cnt"] == 2

            # Scalar query
            count = ws.sql_scalar("SELECT COUNT(*) FROM events")
            assert count == 2

    def test_data_persistence_across_sessions(
        self,
        mock_config_manager: MagicMock,
        mock_api_client: MagicMock,
        temp_dir: Path,
    ) -> None:
        """T028: Integration test for data persistence across sessions.

        This test verifies that data persists when reopening a workspace.
        """
        db_path = temp_dir / "persistent.db"

        # Session 1: Create and populate
        events = [
            {
                "event": "Purchase",
                "properties": {
                    "distinct_id": "user1",
                    "time": 1704067200,
                    "$insert_id": "purchase1",
                    "amount": 99.99,
                },
            },
        ]
        mock_api_client.export_events.return_value = iter(events)

        storage1 = StorageEngine(path=db_path)
        ws1 = Workspace(
            _config_manager=mock_config_manager,
            _api_client=mock_api_client,
            _storage=storage1,
        )
        ws1.fetch_events(
            "purchases",
            from_date="2024-01-01",
            to_date="2024-01-31",
            progress=False,
        )
        ws1.close()

        # Session 2: Reopen and verify
        ws2 = Workspace.open(db_path)
        try:
            count = ws2.sql_scalar("SELECT COUNT(*) FROM purchases")
            assert count == 1

            tables = ws2.tables()
            assert len(tables) == 1
            assert tables[0].name == "purchases"
        finally:
            ws2.close()


# =============================================================================
# US2: Ephemeral Workflow Integration Tests
# =============================================================================


class TestEphemeralWorkflow:
    """Integration tests for ephemeral workspace workflow (T039)."""

    def test_ephemeral_fetch_query_cleanup_workflow(
        self,
        mock_config_manager: MagicMock,
        mock_api_client: MagicMock,
    ) -> None:
        """T039: Integration test for ephemeral fetch-query-cleanup workflow.

        This test verifies the complete ephemeral workflow including
        automatic cleanup on exit.
        """
        # Set up mock events
        events = [
            {
                "event": "Sign Up",
                "properties": {
                    "distinct_id": "user1",
                    "time": 1704067200,
                    "$insert_id": "signup1",
                },
            },
        ]
        mock_api_client.export_events.return_value = iter(events)

        db_path = None
        with Workspace.ephemeral(
            _config_manager=mock_config_manager,
            _api_client=mock_api_client,
        ) as ws:
            db_path = ws.storage.path
            assert db_path is not None
            assert db_path.exists()

            # Fetch and query
            ws.fetch_events(
                "signups",
                from_date="2024-01-01",
                to_date="2024-01-31",
                progress=False,
            )

            count = ws.sql_scalar("SELECT COUNT(*) FROM signups")
            assert count == 1

        # Verify cleanup
        assert not db_path.exists()


# =============================================================================
# US6: Query-Only Access Integration Tests
# =============================================================================


class TestQueryOnlyIntegration:
    """Integration tests for query-only access (T084)."""

    def test_open_existing_database(
        self,
        temp_dir: Path,
    ) -> None:
        """T084: Integration test for opening existing database.

        This test verifies that Workspace.open() can open an existing
        database and query its contents.
        """
        db_path = temp_dir / "existing.db"

        # Create database with data
        storage = StorageEngine(path=db_path)
        storage.connection.execute("CREATE TABLE test_data (id INTEGER, value VARCHAR)")
        storage.connection.execute(
            "INSERT INTO test_data VALUES (1, 'one'), (2, 'two')"
        )
        storage.close()

        # Open with Workspace.open()
        ws = Workspace.open(db_path)
        try:
            df = ws.sql("SELECT * FROM test_data ORDER BY id")
            assert len(df) == 2
            assert df.iloc[0]["value"] == "one"
            assert df.iloc[1]["value"] == "two"
        finally:
            ws.close()


# =============================================================================
# US7: Table Management Integration Tests
# =============================================================================


class TestTableManagementIntegration:
    """Integration tests for table management (T094)."""

    def test_table_management_workflow(
        self,
        mock_config_manager: MagicMock,
        mock_api_client: MagicMock,
        temp_dir: Path,
    ) -> None:
        """T094: Integration test for table management workflow.

        This test verifies the complete table management workflow:
        create, list, get schema, and drop tables.
        """
        db_path = temp_dir / "management.db"
        storage = StorageEngine(path=db_path)

        # Create events using the storage directly (simulating fetch)
        events = [
            {
                "event_name": "Event A",
                "event_time": datetime.now(UTC),
                "distinct_id": "user1",
                "insert_id": "id1",
                "properties": {"foo": "bar"},
            },
        ]
        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        storage.create_events_table("table1", iter(events), metadata)
        storage.create_events_table("table2", iter([]), metadata)

        with Workspace(
            _config_manager=mock_config_manager,
            _api_client=mock_api_client,
            _storage=storage,
        ) as ws:
            # List tables
            tables = ws.tables()
            assert len(tables) == 2
            table_names = {t.name for t in tables}
            assert "table1" in table_names
            assert "table2" in table_names

            # Get schema
            schema = ws.table_schema("table1")
            assert schema.table_name == "table1"
            column_names = {c.name for c in schema.columns}
            assert "event_name" in column_names
            assert "distinct_id" in column_names

            # Drop one table
            ws.drop("table2")
            tables = ws.tables()
            assert len(tables) == 1
            assert tables[0].name == "table1"

            # Drop remaining table
            ws.drop_all()
            tables = ws.tables()
            assert len(tables) == 0


# =============================================================================
# Workspace Info Integration Tests
# =============================================================================


class TestWorkspaceInfoIntegration:
    """Integration tests for workspace info."""

    def test_info_returns_complete_metadata(
        self,
        mock_config_manager: MagicMock,
        mock_api_client: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test info() returns complete workspace metadata."""
        db_path = temp_dir / "info_test.db"
        storage = StorageEngine(path=db_path)

        # Create a table
        storage.connection.execute("CREATE TABLE test (id INTEGER)")
        storage.connection.execute(
            """CREATE TABLE IF NOT EXISTS _metadata (
                table_name VARCHAR PRIMARY KEY,
                type VARCHAR NOT NULL,
                fetched_at TIMESTAMP NOT NULL,
                from_date DATE,
                to_date DATE,
                row_count INTEGER NOT NULL
            )"""
        )
        storage.connection.execute(
            """INSERT INTO _metadata VALUES
            ('test', 'events', CURRENT_TIMESTAMP, NULL, NULL, 0)"""
        )

        with Workspace(
            _config_manager=mock_config_manager,
            _api_client=mock_api_client,
            _storage=storage,
        ) as ws:
            info = ws.info()

            assert isinstance(info, WorkspaceInfo)
            assert info.path == db_path
            assert info.project_id == "12345"
            assert info.region == "us"
            assert "test" in info.tables
            assert info.size_mb > 0
