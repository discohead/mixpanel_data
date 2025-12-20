"""Integration tests for the foundation layer.

These tests verify the full workflow described in quickstart.md.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from mixpanel_data import (
    AccountExistsError,
    AccountNotFoundError,
    AuthenticationError,
    FetchResult,
    FunnelResult,
    FunnelStep,
    MixpanelDataError,
    RateLimitError,
    TableExistsError,
)
from mixpanel_data._internal.config import ConfigManager


class TestFoundationLayerWorkflow:
    """Integration tests per quickstart.md."""

    def test_config_manager_workflow(self) -> None:
        """Test ConfigManager add and retrieve credentials."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config = ConfigManager(config_path=config_path)

            # Add an account
            config.add_account(
                name="production",
                username="sa_test_user",
                secret="test_secret_123",
                project_id="12345",
                region="us",
            )

            # List accounts
            accounts = config.list_accounts()
            assert len(accounts) == 1
            assert accounts[0].name == "production"

            # Retrieve credentials
            creds = config.resolve_credentials()
            assert creds.username == "sa_test_user"
            assert creds.project_id == "12345"

            # Verify secret is redacted in output
            creds_str = str(creds)
            assert "test_secret_123" not in creds_str

    def test_env_variable_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test environment variable priority over config file."""
        monkeypatch.setenv("MP_USERNAME", "env_user")
        monkeypatch.setenv("MP_SECRET", "env_secret")
        monkeypatch.setenv("MP_PROJECT_ID", "env_project")
        monkeypatch.setenv("MP_REGION", "eu")

        config = ConfigManager()
        creds = config.resolve_credentials()

        assert creds.username == "env_user"
        assert creds.region == "eu"

    def test_exception_hierarchy(self) -> None:
        """Test all exceptions inherit from MixpanelDataError."""
        exceptions: list[MixpanelDataError] = [
            AccountNotFoundError("missing", available_accounts=["a", "b"]),
            AccountExistsError("duplicate"),
            AuthenticationError("invalid"),
            TableExistsError("events"),
            RateLimitError("slow down", retry_after=60),
        ]

        for exc in exceptions:
            assert isinstance(exc, MixpanelDataError)
            assert exc.code is not None

            # to_dict should be JSON serializable
            data = exc.to_dict()
            json.dumps(data)  # Should not raise

    def test_fetch_result_workflow(self) -> None:
        """Test FetchResult creation and serialization."""
        result = FetchResult(
            table="january_events",
            rows=10000,
            type="events",
            duration_seconds=5.23,
            date_range=("2024-01-01", "2024-01-31"),
            fetched_at=datetime.now(),
        )

        # Immutable
        with pytest.raises((TypeError, AttributeError)):
            result.rows = 20000  # type: ignore[misc]

        # JSON serializable
        data = result.to_dict()
        json_str = json.dumps(data)
        assert "january_events" in json_str

        # DataFrame conversion
        df = result.df
        assert len(df) >= 0  # Empty if no data attached

    def test_funnel_result_workflow(self) -> None:
        """Test FunnelResult creation and step iteration."""
        steps = [
            FunnelStep(event="View", count=1000, conversion_rate=1.0),
            FunnelStep(event="Click", count=500, conversion_rate=0.5),
            FunnelStep(event="Purchase", count=100, conversion_rate=0.2),
        ]

        result = FunnelResult(
            funnel_id=12345,
            funnel_name="Checkout",
            from_date="2024-01-01",
            to_date="2024-01-31",
            conversion_rate=0.1,
            steps=steps,
        )

        # Step iteration
        assert len(result.steps) == 3
        assert result.steps[0].event == "View"
        assert result.steps[2].count == 100

        # DataFrame
        df = result.df
        assert "step" in df.columns
        assert "event" in df.columns
        assert len(df) == 3

    def test_catch_all_library_errors(self) -> None:
        """Verify catch-all pattern works."""

        def might_raise(exc_class: type) -> None:
            if exc_class == AccountNotFoundError:
                raise AccountNotFoundError("x")
            elif exc_class == TableExistsError:
                raise TableExistsError("t")
            else:
                raise exc_class("error")

        exception_classes = [
            AccountNotFoundError,
            TableExistsError,
            RateLimitError,
            AuthenticationError,
        ]

        for exc_class in exception_classes:
            try:
                might_raise(exc_class)
            except MixpanelDataError as e:
                assert e.code is not None
                assert e.to_dict() is not None
            else:
                pytest.fail(f"Exception {exc_class.__name__} should have been raised")


class TestPublicAPIImports:
    """Test that public API imports work correctly."""

    def test_top_level_imports(self) -> None:
        """Test imports from mixpanel_data package."""
        from mixpanel_data import (
            ConfigError,
            FetchResult,
            FunnelStep,
            MixpanelDataError,
        )

        # All should be importable
        assert MixpanelDataError is not None
        assert ConfigError is not None
        assert FetchResult is not None
        assert FunnelStep is not None

    def test_auth_module_imports(self) -> None:
        """Test imports from mixpanel_data.auth module."""
        from mixpanel_data.auth import AccountInfo, ConfigManager, Credentials

        assert ConfigManager is not None
        assert Credentials is not None
        assert AccountInfo is not None
