"""Unit tests for Workspace facade."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pandas as pd
import pytest
from pydantic import SecretStr

from mixpanel_data import (
    ConfigError,
    TableNotFoundError,
    Workspace,
    WorkspaceInfo,
)
from mixpanel_data._internal.config import ConfigManager, Credentials
from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data.types import (
    ActivityFeedResult,
    EventCountsResult,
    FetchResult,
    FrequencyResult,
    FunnelInfo,
    FunnelResult,
    InsightsResult,
    JQLResult,
    NumericAverageResult,
    NumericBucketResult,
    NumericSumResult,
    PropertyCountsResult,
    RetentionResult,
    SavedCohort,
    SegmentationResult,
    TableSchema,
    TopEvent,
)

if TYPE_CHECKING:
    from collections.abc import Callable


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
def mock_storage() -> StorageEngine:
    """Create ephemeral storage for testing."""
    return StorageEngine.ephemeral()


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create mock API client for testing."""
    from mixpanel_data._internal.api_client import MixpanelAPIClient

    client = MagicMock(spec=MixpanelAPIClient)
    client.close = MagicMock()
    return client


@pytest.fixture
def workspace_factory(
    mock_config_manager: MagicMock,
    mock_storage: StorageEngine,
    mock_api_client: MagicMock,
) -> Callable[..., Workspace]:
    """Factory for creating Workspace instances with mocked dependencies."""

    def factory(**kwargs: Any) -> Workspace:
        defaults = {
            "_config_manager": mock_config_manager,
            "_storage": mock_storage,
            "_api_client": mock_api_client,
        }
        defaults.update(kwargs)
        return Workspace(**defaults)

    return factory


# =============================================================================
# Phase 3: US5 Credential Resolution Tests
# =============================================================================


class TestCredentialResolution:
    """Tests for credential resolution (T014-T017)."""

    def test_env_var_credential_resolution(
        self,
        mock_storage: StorageEngine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """T014: Test env var credential resolution."""
        # Set environment variables
        monkeypatch.setenv("MP_USERNAME", "env_user")
        monkeypatch.setenv("MP_SECRET", "env_secret")
        monkeypatch.setenv("MP_PROJECT_ID", "99999")
        monkeypatch.setenv("MP_REGION", "eu")

        with Workspace(_storage=mock_storage) as ws:
            assert ws._credentials is not None
            assert ws._credentials.username == "env_user"
            assert ws._credentials.project_id == "99999"
            assert ws._credentials.region == "eu"

    def test_named_account_credential_resolution(
        self,
        mock_storage: StorageEngine,
        temp_dir: Path,
    ) -> None:
        """T015: Test named account credential resolution."""
        # Create config with named account
        config_path = temp_dir / "config.toml"
        config_manager = ConfigManager(config_path=config_path)
        config_manager.add_account(
            name="test_account",
            username="named_user",
            secret="named_secret",
            project_id="11111",
            region="us",
        )

        with Workspace(
            account="test_account",
            _config_manager=config_manager,
            _storage=mock_storage,
        ) as ws:
            assert ws._credentials is not None
            assert ws._credentials.username == "named_user"
            assert ws._credentials.project_id == "11111"
            assert ws._account_name == "test_account"

    def test_default_account_credential_resolution(
        self,
        mock_storage: StorageEngine,
        temp_dir: Path,
    ) -> None:
        """T016: Test default account credential resolution."""
        # Create config with default account
        config_path = temp_dir / "config.toml"
        config_manager = ConfigManager(config_path=config_path)
        config_manager.add_account(
            name="default_account",
            username="default_user",
            secret="default_secret",
            project_id="22222",
            region="in",
        )

        with Workspace(
            _config_manager=config_manager,
            _storage=mock_storage,
        ) as ws:
            assert ws._credentials is not None
            assert ws._credentials.username == "default_user"
            assert ws._credentials.region == "in"

    def test_config_error_when_no_credentials(
        self,
        mock_storage: StorageEngine,
        temp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """T017: Test ConfigError when no credentials available."""
        # Clear env vars
        monkeypatch.delenv("MP_USERNAME", raising=False)
        monkeypatch.delenv("MP_SECRET", raising=False)
        monkeypatch.delenv("MP_PROJECT_ID", raising=False)
        monkeypatch.delenv("MP_REGION", raising=False)

        # Empty config
        config_path = temp_dir / "empty_config.toml"
        config_manager = ConfigManager(config_path=config_path)

        with pytest.raises(ConfigError):
            Workspace(_config_manager=config_manager, _storage=mock_storage)


# =============================================================================
# Phase 4: US1 Basic Workflow Tests
# =============================================================================


class TestBasicWorkflow:
    """Tests for basic data workflow (T022-T028)."""

    def test_fetch_events_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T022: Test fetch_events() delegation to FetcherService."""
        ws = workspace_factory()
        try:
            # Mock the fetcher service
            mock_fetcher = MagicMock()
            mock_fetcher.fetch_events.return_value = FetchResult(
                table="events",
                rows=100,
                type="events",
                duration_seconds=1.5,
                date_range=("2024-01-01", "2024-01-31"),
                fetched_at=MagicMock(),
            )
            ws._fetcher = mock_fetcher

            result = ws.fetch_events(
                "events",
                from_date="2024-01-01",
                to_date="2024-01-31",
                progress=False,
            )

            assert result.table == "events"
            assert result.rows == 100
            mock_fetcher.fetch_events.assert_called_once()
        finally:
            ws.close()

    def test_fetch_profiles_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T023: Test fetch_profiles() delegation to FetcherService."""
        ws = workspace_factory()
        try:
            mock_fetcher = MagicMock()
            mock_fetcher.fetch_profiles.return_value = FetchResult(
                table="profiles",
                rows=50,
                type="profiles",
                duration_seconds=0.5,
                date_range=None,
                fetched_at=MagicMock(),
            )
            ws._fetcher = mock_fetcher

            result = ws.fetch_profiles("profiles", progress=False)

            assert result.table == "profiles"
            assert result.rows == 50
            mock_fetcher.fetch_profiles.assert_called_once()
        finally:
            ws.close()

    def test_sql_returns_dataframe(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T024: Test sql() returning DataFrame."""
        ws = workspace_factory()
        try:
            # Create a test table
            ws._storage.connection.execute(
                "CREATE TABLE test_table (id INTEGER, name VARCHAR)"
            )
            ws._storage.connection.execute(
                "INSERT INTO test_table VALUES (1, 'Alice'), (2, 'Bob')"
            )

            df = ws.sql("SELECT * FROM test_table ORDER BY id")

            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert list(df.columns) == ["id", "name"]
        finally:
            ws.close()

    def test_sql_scalar_returns_value(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T025: Test sql_scalar() returning single value."""
        ws = workspace_factory()
        try:
            # Create a test table
            ws._storage.connection.execute("CREATE TABLE count_table (id INTEGER)")
            ws._storage.connection.execute(
                "INSERT INTO count_table VALUES (1), (2), (3)"
            )

            count = ws.sql_scalar("SELECT COUNT(*) FROM count_table")

            assert count == 3
        finally:
            ws.close()

    def test_sql_rows_returns_tuples(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T026: Test sql_rows() returning tuples."""
        ws = workspace_factory()
        try:
            # Create a test table
            ws._storage.connection.execute(
                "CREATE TABLE rows_table (id INTEGER, name VARCHAR)"
            )
            ws._storage.connection.execute(
                "INSERT INTO rows_table VALUES (1, 'A'), (2, 'B')"
            )

            rows = ws.sql_rows("SELECT * FROM rows_table ORDER BY id")

            assert isinstance(rows, list)
            assert len(rows) == 2
            assert rows[0] == (1, "A")
            assert rows[1] == (2, "B")
        finally:
            ws.close()


# =============================================================================
# Phase 5: US2 Ephemeral Workspace Tests
# =============================================================================


class TestEphemeralWorkspace:
    """Tests for ephemeral workspaces (T036-T039)."""

    def test_ephemeral_creates_temporary_storage(
        self,
        mock_config_manager: MagicMock,
        mock_api_client: MagicMock,
    ) -> None:
        """T036: Test ephemeral() creating temporary storage."""
        with Workspace.ephemeral(
            _config_manager=mock_config_manager,
            _api_client=mock_api_client,
        ) as ws:
            assert ws._storage is not None
            # Ephemeral storage should exist
            assert ws._storage._is_ephemeral is True

    def test_ephemeral_cleanup_on_normal_exit(
        self,
        mock_config_manager: MagicMock,
        mock_api_client: MagicMock,
    ) -> None:
        """T037: Test ephemeral cleanup on normal exit."""
        with Workspace.ephemeral(
            _config_manager=mock_config_manager,
            _api_client=mock_api_client,
        ) as ws:
            path = ws._storage.path
            assert path is not None
            assert path.exists()

        # After context exit, file should be cleaned up
        assert not path.exists()

    def test_ephemeral_cleanup_on_exception(
        self,
        mock_config_manager: MagicMock,
        mock_api_client: MagicMock,
    ) -> None:
        """T038: Test ephemeral cleanup on exception."""
        path = None
        try:
            with Workspace.ephemeral(
                _config_manager=mock_config_manager,
                _api_client=mock_api_client,
            ) as ws:
                path = ws._storage.path
                assert path.exists()
                raise ValueError("Test exception")
        except ValueError:
            pass

        # After exception, file should be cleaned up
        assert path is not None
        assert not path.exists()


# =============================================================================
# Phase 6: US3 Live Query Tests
# =============================================================================


class TestLiveQueries:
    """Tests for live query methods (T043-T066)."""

    def test_segmentation_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T043: Test segmentation() delegation."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.segmentation.return_value = SegmentationResult(
                event="Test",
                from_date="2024-01-01",
                to_date="2024-01-31",
                unit="day",
                segment_property=None,
                total=100,
                series={},
            )
            ws._live_query = mock_live_query

            result = ws.segmentation(
                "Test",
                from_date="2024-01-01",
                to_date="2024-01-31",
            )

            assert result.total == 100
            mock_live_query.segmentation.assert_called_once()
        finally:
            ws.close()

    def test_funnel_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T044: Test funnel() delegation."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.funnel.return_value = FunnelResult(
                funnel_id=123,
                funnel_name="Test Funnel",
                from_date="2024-01-01",
                to_date="2024-01-31",
                conversion_rate=0.5,
                steps=[],
            )
            ws._live_query = mock_live_query

            result = ws.funnel(
                123,
                from_date="2024-01-01",
                to_date="2024-01-31",
            )

            assert result.funnel_id == 123
            mock_live_query.funnel.assert_called_once()
        finally:
            ws.close()

    def test_retention_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T045: Test retention() delegation."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.retention.return_value = RetentionResult(
                born_event="Sign Up",
                return_event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                unit="day",
                cohorts=[],
            )
            ws._live_query = mock_live_query

            result = ws.retention(
                born_event="Sign Up",
                return_event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
            )

            assert result.born_event == "Sign Up"
            mock_live_query.retention.assert_called_once()
        finally:
            ws.close()

    def test_jql_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T046: Test jql() delegation."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.jql.return_value = JQLResult(_raw=[{"count": 42}])
            ws._live_query = mock_live_query

            result = ws.jql("function main() { return 42; }")

            assert result.raw == [{"count": 42}]
            mock_live_query.jql.assert_called_once()
        finally:
            ws.close()

    def test_event_counts_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T047: Test event_counts() delegation."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.event_counts.return_value = EventCountsResult(
                events=["A", "B"],
                from_date="2024-01-01",
                to_date="2024-01-31",
                unit="day",
                type="general",
                series={},
            )
            ws._live_query = mock_live_query

            result = ws.event_counts(
                ["A", "B"],
                from_date="2024-01-01",
                to_date="2024-01-31",
            )

            assert result.events == ["A", "B"]
            mock_live_query.event_counts.assert_called_once()
        finally:
            ws.close()

    def test_property_counts_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T048: Test property_counts() delegation."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.property_counts.return_value = PropertyCountsResult(
                event="Test",
                property_name="country",
                from_date="2024-01-01",
                to_date="2024-01-31",
                unit="day",
                type="general",
                series={},
            )
            ws._live_query = mock_live_query

            result = ws.property_counts(
                "Test",
                "country",
                from_date="2024-01-01",
                to_date="2024-01-31",
            )

            assert result.property_name == "country"
            mock_live_query.property_counts.assert_called_once()
        finally:
            ws.close()

    def test_activity_feed_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T049: Test activity_feed() delegation."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.activity_feed.return_value = ActivityFeedResult(
                distinct_ids=["user1"],
                from_date=None,
                to_date=None,
                events=[],
            )
            ws._live_query = mock_live_query

            result = ws.activity_feed(["user1"])

            assert result.distinct_ids == ["user1"]
            mock_live_query.activity_feed.assert_called_once()
        finally:
            ws.close()

    def test_insights_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T050: Test insights() delegation."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.insights.return_value = InsightsResult(
                bookmark_id=12345,
                computed_at="2024-01-01",
                from_date="2024-01-01",
                to_date="2024-01-31",
                headers=[],
                series={},
            )
            ws._live_query = mock_live_query

            result = ws.insights(12345)

            assert result.bookmark_id == 12345
            mock_live_query.insights.assert_called_once()
        finally:
            ws.close()

    def test_frequency_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T051: Test frequency() delegation."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.frequency.return_value = FrequencyResult(
                event=None,
                from_date="2024-01-01",
                to_date="2024-01-31",
                unit="day",
                addiction_unit="hour",
                data={},
            )
            ws._live_query = mock_live_query

            result = ws.frequency(from_date="2024-01-01", to_date="2024-01-31")

            assert result.unit == "day"
            mock_live_query.frequency.assert_called_once()
        finally:
            ws.close()

    def test_segmentation_numeric_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T052: Test segmentation_numeric() delegation."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.segmentation_numeric.return_value = NumericBucketResult(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                property_expr='properties["amount"]',
                unit="day",
                series={},
            )
            ws._live_query = mock_live_query

            result = ws.segmentation_numeric(
                "Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )

            assert result.event == "Purchase"
            mock_live_query.segmentation_numeric.assert_called_once()
        finally:
            ws.close()

    def test_segmentation_sum_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T053: Test segmentation_sum() delegation."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.segmentation_sum.return_value = NumericSumResult(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                property_expr='properties["amount"]',
                unit="day",
                results={},
            )
            ws._live_query = mock_live_query

            result = ws.segmentation_sum(
                "Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )

            assert result.event == "Purchase"
            mock_live_query.segmentation_sum.assert_called_once()
        finally:
            ws.close()

    def test_segmentation_average_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T054: Test segmentation_average() delegation."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.segmentation_average.return_value = NumericAverageResult(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                property_expr='properties["amount"]',
                unit="day",
                results={},
            )
            ws._live_query = mock_live_query

            result = ws.segmentation_average(
                "Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )

            assert result.event == "Purchase"
            mock_live_query.segmentation_average.assert_called_once()
        finally:
            ws.close()


# =============================================================================
# Phase 7: US4 Discovery Tests
# =============================================================================


class TestDiscovery:
    """Tests for discovery methods (T067-T080)."""

    def test_events_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T067: Test events() delegation and caching."""
        ws = workspace_factory()
        try:
            mock_discovery = MagicMock()
            mock_discovery.list_events.return_value = ["Event A", "Event B"]
            ws._discovery = mock_discovery

            result = ws.events()

            assert result == ["Event A", "Event B"]
            mock_discovery.list_events.assert_called_once()
        finally:
            ws.close()

    def test_properties_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T068: Test properties() delegation."""
        ws = workspace_factory()
        try:
            mock_discovery = MagicMock()
            mock_discovery.list_properties.return_value = ["prop_a", "prop_b"]
            ws._discovery = mock_discovery

            result = ws.properties("Event A")

            assert result == ["prop_a", "prop_b"]
            mock_discovery.list_properties.assert_called_once_with("Event A")
        finally:
            ws.close()

    def test_property_values_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T069: Test property_values() delegation."""
        ws = workspace_factory()
        try:
            mock_discovery = MagicMock()
            mock_discovery.list_property_values.return_value = ["val1", "val2"]
            ws._discovery = mock_discovery

            result = ws.property_values("country", event="Purchase", limit=50)

            assert result == ["val1", "val2"]
            mock_discovery.list_property_values.assert_called_once_with(
                "country", event="Purchase", limit=50
            )
        finally:
            ws.close()

    def test_funnels_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T070: Test funnels() delegation."""
        ws = workspace_factory()
        try:
            mock_discovery = MagicMock()
            mock_discovery.list_funnels.return_value = [
                FunnelInfo(funnel_id=1, name="Funnel 1")
            ]
            ws._discovery = mock_discovery

            result = ws.funnels()

            assert len(result) == 1
            assert result[0].funnel_id == 1
            mock_discovery.list_funnels.assert_called_once()
        finally:
            ws.close()

    def test_cohorts_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T071: Test cohorts() delegation."""
        ws = workspace_factory()
        try:
            mock_discovery = MagicMock()
            mock_discovery.list_cohorts.return_value = [
                SavedCohort(
                    id=1,
                    name="Cohort 1",
                    count=100,
                    description="",
                    created="2024-01-01",
                    is_visible=True,
                )
            ]
            ws._discovery = mock_discovery

            result = ws.cohorts()

            assert len(result) == 1
            assert result[0].id == 1
            mock_discovery.list_cohorts.assert_called_once()
        finally:
            ws.close()

    def test_top_events_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T072: Test top_events() delegation (not cached)."""
        ws = workspace_factory()
        try:
            mock_discovery = MagicMock()
            mock_discovery.list_top_events.return_value = [
                TopEvent(event="Event A", count=100, percent_change=0.1)
            ]
            ws._discovery = mock_discovery

            result = ws.top_events(type="general", limit=10)

            assert len(result) == 1
            mock_discovery.list_top_events.assert_called_once_with(
                type="general", limit=10
            )
        finally:
            ws.close()

    def test_clear_discovery_cache(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T073: Test clear_discovery_cache()."""
        ws = workspace_factory()
        try:
            mock_discovery = MagicMock()
            ws._discovery = mock_discovery

            ws.clear_discovery_cache()

            mock_discovery.clear_cache.assert_called_once()
        finally:
            ws.close()


# =============================================================================
# Phase 8: US6 Query-Only Tests
# =============================================================================


class TestQueryOnlyMode:
    """Tests for query-only mode (T081-T087)."""

    def test_workspace_open_creates_query_only(
        self,
        temp_dir: Path,
    ) -> None:
        """T081: Test Workspace.open() creating query-only workspace."""
        # Create a database file first
        db_path = temp_dir / "test.db"
        storage = StorageEngine(path=db_path)
        storage.close()

        ws = Workspace.open(db_path)
        try:
            assert ws._credentials is None
            assert ws._storage is not None
        finally:
            ws.close()

    def test_sql_works_without_credentials(
        self,
        temp_dir: Path,
    ) -> None:
        """T082: Test sql operations working without credentials."""
        # Create a database with data
        db_path = temp_dir / "test.db"
        storage = StorageEngine(path=db_path)
        storage.connection.execute("CREATE TABLE test (id INTEGER)")
        storage.connection.execute("INSERT INTO test VALUES (1), (2)")
        storage.close()

        ws = Workspace.open(db_path)
        try:
            count = ws.sql_scalar("SELECT COUNT(*) FROM test")
            assert count == 2
        finally:
            ws.close()

    def test_api_methods_raise_config_error(
        self,
        temp_dir: Path,
    ) -> None:
        """T083: Test API methods raising ConfigError in query-only mode."""
        # Create a database file
        db_path = temp_dir / "test.db"
        storage = StorageEngine(path=db_path)
        storage.close()

        ws = Workspace.open(db_path)
        try:
            with pytest.raises(ConfigError) as exc_info:
                ws.events()

            assert "API access requires credentials" in str(exc_info.value)
        finally:
            ws.close()


# =============================================================================
# Phase 9: US7 Introspection Tests
# =============================================================================


class TestIntrospection:
    """Tests for introspection methods (T088-T099)."""

    def test_info_returns_workspace_info(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T088: Test info() returning WorkspaceInfo."""
        ws = workspace_factory()
        try:
            info = ws.info()

            assert isinstance(info, WorkspaceInfo)
            assert info.project_id == "12345"
            assert info.region == "us"
        finally:
            ws.close()

    def test_tables_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T089: Test tables() delegation."""
        ws = workspace_factory()
        try:
            # list_tables returns empty list for new storage
            tables = ws.tables()
            assert isinstance(tables, list)
        finally:
            ws.close()

    def test_schema_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T090: Test schema() delegation."""
        ws = workspace_factory()
        try:
            # Create a table
            ws._storage.connection.execute(
                "CREATE TABLE test_schema (id INTEGER, name VARCHAR)"
            )

            schema = ws.schema("test_schema")

            assert isinstance(schema, TableSchema)
            assert schema.table_name == "test_schema"
            assert len(schema.columns) == 2
        finally:
            ws.close()

    def test_drop_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T091: Test drop() delegation."""
        ws = workspace_factory()
        try:
            # Create and then drop a table (need metadata table for drop)
            ws._storage.connection.execute("CREATE TABLE drop_test (id INTEGER)")
            ws._storage.connection.execute(
                """CREATE TABLE IF NOT EXISTS _metadata (
                    table_name VARCHAR PRIMARY KEY,
                    type VARCHAR NOT NULL,
                    fetched_at TIMESTAMP NOT NULL,
                    from_date DATE,
                    to_date DATE,
                    row_count INTEGER NOT NULL
                )"""
            )
            ws._storage.connection.execute(
                """INSERT INTO _metadata VALUES
                ('drop_test', 'events', CURRENT_TIMESTAMP, NULL, NULL, 0)"""
            )

            ws.drop("drop_test")

            assert not ws._storage.table_exists("drop_test")
        finally:
            ws.close()

    def test_drop_all_with_type_filter(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T092: Test drop_all() with type filter."""
        ws = workspace_factory()
        try:
            # Create tables with metadata
            ws._storage.connection.execute("CREATE TABLE events1 (id INTEGER)")
            ws._storage.connection.execute("CREATE TABLE profiles1 (id INTEGER)")
            ws._storage.connection.execute(
                """CREATE TABLE IF NOT EXISTS _metadata (
                    table_name VARCHAR PRIMARY KEY,
                    type VARCHAR NOT NULL,
                    fetched_at TIMESTAMP NOT NULL,
                    from_date DATE,
                    to_date DATE,
                    row_count INTEGER NOT NULL
                )"""
            )
            ws._storage.connection.execute(
                """INSERT INTO _metadata VALUES
                ('events1', 'events', CURRENT_TIMESTAMP, NULL, NULL, 0),
                ('profiles1', 'profiles', CURRENT_TIMESTAMP, NULL, NULL, 0)"""
            )

            ws.drop_all(type="events")

            # events1 should be dropped, profiles1 should remain
            assert not ws._storage.table_exists("events1")
            assert ws._storage.table_exists("profiles1")
        finally:
            ws.close()

    def test_table_not_found_error_on_invalid_drop(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T093: Test TableNotFoundError on invalid drop."""
        ws = workspace_factory()
        try:
            with pytest.raises(TableNotFoundError):
                ws.drop("nonexistent_table")
        finally:
            ws.close()


# =============================================================================
# Phase 10: US8 Escape Hatches Tests
# =============================================================================


class TestEscapeHatches:
    """Tests for escape hatch properties (T100-T104)."""

    def test_connection_property_returns_duckdb_connection(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T100: Test connection property returning DuckDB connection."""
        ws = workspace_factory()
        try:
            conn = ws.connection

            # Should be a DuckDB connection
            import duckdb

            assert isinstance(conn, duckdb.DuckDBPyConnection)
        finally:
            ws.close()

    def test_api_property_returns_client(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """T101: Test api property returning MixpanelAPIClient."""
        ws = workspace_factory()
        try:
            api = ws.api

            # Our mock is a MagicMock, but should satisfy the protocol
            assert api is not None
        finally:
            ws.close()

    def test_api_property_raises_config_error_without_credentials(
        self,
        temp_dir: Path,
    ) -> None:
        """T102: Test api property raising ConfigError when no credentials."""
        # Create a database file
        db_path = temp_dir / "test.db"
        storage = StorageEngine(path=db_path)
        storage.close()

        ws = Workspace.open(db_path)
        try:
            with pytest.raises(ConfigError):
                _ = ws.api
        finally:
            ws.close()


# =============================================================================
# Context Manager Tests
# =============================================================================


class TestContextManager:
    """Tests for context manager protocol."""

    def test_context_manager_enter_returns_self(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Test __enter__ returns self."""
        ws = workspace_factory()
        with ws as entered:
            assert entered is ws

    def test_context_manager_closes_on_exit(
        self,
        mock_config_manager: MagicMock,
        mock_api_client: MagicMock,
    ) -> None:
        """Test __exit__ closes resources."""
        with Workspace.ephemeral(
            _config_manager=mock_config_manager,
            _api_client=mock_api_client,
        ) as ws:
            path = ws._storage.path
            assert path.exists()

        # Should be cleaned up
        assert not path.exists()

    def test_close_calls_api_client_close(
        self,
        mock_config_manager: MagicMock,
        mock_api_client: MagicMock,
        mock_storage: StorageEngine,
    ) -> None:
        """Test that close() calls api_client.close()."""
        ws = Workspace(
            _config_manager=mock_config_manager,
            _api_client=mock_api_client,
            _storage=mock_storage,
        )
        ws.close()
        mock_api_client.close.assert_called_once()
