"""Unit tests for ConfigManager and Credentials."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from pydantic import ValidationError

from mixpanel_data._internal.config import (
    AccountInfo,
    ConfigManager,
    Credentials,
)
from mixpanel_data.exceptions import (
    AccountExistsError,
    AccountNotFoundError,
    ConfigError,
)


class TestCredentials:
    """Tests for the Credentials model."""

    def test_valid_credentials(self) -> None:
        """Test creating valid credentials."""
        creds = Credentials(
            username="sa_test",
            secret="secret123",  # type: ignore[arg-type]
            project_id="12345",
            region="us",
        )

        assert creds.username == "sa_test"
        assert creds.project_id == "12345"
        assert creds.region == "us"
        assert creds.secret.get_secret_value() == "secret123"

    def test_region_validation(self) -> None:
        """Test region validation."""
        # Valid regions
        for region in ("us", "eu", "in", "US", "EU", "IN"):
            creds = Credentials(
                username="user",
                secret="secret",  # type: ignore[arg-type]
                project_id="123",
                region=region,  # type: ignore[arg-type]
            )
            assert creds.region == region.lower()

        # Invalid region
        with pytest.raises(ValueError, match="Region must be one of"):
            Credentials(
                username="user",
                secret="secret",  # type: ignore[arg-type]
                project_id="123",
                region="invalid",  # type: ignore[arg-type]
            )

    def test_empty_field_validation(self) -> None:
        """Test that empty fields are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Credentials(
                username="",
                secret="secret",  # type: ignore[arg-type]
                project_id="123",
                region="us",
            )

        with pytest.raises(ValueError, match="cannot be empty"):
            Credentials(
                username="user",
                secret="secret",  # type: ignore[arg-type]
                project_id="   ",
                region="us",
            )

    def test_secret_not_in_repr(self) -> None:
        """Secret should never appear in repr/str output."""
        creds = Credentials(
            username="sa_test",
            secret="my_super_secret_value",  # type: ignore[arg-type]
            project_id="12345",
            region="us",
        )

        repr_str = repr(creds)
        str_str = str(creds)

        assert "my_super_secret_value" not in repr_str
        assert "my_super_secret_value" not in str_str
        assert "***" in repr_str
        assert "***" in str_str
        assert "sa_test" in repr_str  # Other fields should be visible

    def test_credentials_immutable(self) -> None:
        """Credentials should be immutable (frozen)."""
        creds = Credentials(
            username="sa_test",
            secret="secret123",  # type: ignore[arg-type]
            project_id="12345",
            region="us",
        )

        with pytest.raises(ValidationError):  # Frozen Pydantic model
            creds.username = "different"  # type: ignore[misc]


class TestAccountInfo:
    """Tests for AccountInfo dataclass."""

    def test_account_info_creation(self) -> None:
        """Test AccountInfo creation."""
        info = AccountInfo(
            name="production",
            username="sa_prod",
            project_id="12345",
            region="us",
            is_default=True,
        )

        assert info.name == "production"
        assert info.username == "sa_prod"
        assert info.project_id == "12345"
        assert info.region == "us"
        assert info.is_default is True

    def test_account_info_immutable(self) -> None:
        """AccountInfo should be immutable (frozen dataclass)."""
        info = AccountInfo(
            name="test",
            username="user",
            project_id="123",
            region="us",
            is_default=False,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            info.name = "different"  # type: ignore[misc]


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_default_path(self) -> None:
        """Test default config path."""
        config = ConfigManager()
        assert config.config_path == Path.home() / ".mp" / "config.toml"

    def test_custom_path(self, config_path: Path) -> None:
        """Test custom config path."""
        config = ConfigManager(config_path=config_path)
        assert config.config_path == config_path

    def test_env_path_override(
        self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test MP_CONFIG_PATH environment variable override."""
        custom_path = temp_dir / "custom_config.toml"
        monkeypatch.setenv("MP_CONFIG_PATH", str(custom_path))

        config = ConfigManager()
        assert config.config_path == custom_path

    def test_list_accounts_empty(self, config_manager: ConfigManager) -> None:
        """Test listing accounts when no config exists."""
        accounts = config_manager.list_accounts()
        assert accounts == []

    def test_add_account_stores_correctly(
        self, config_manager: ConfigManager, sample_credentials: dict[str, str]
    ) -> None:
        """Test that add_account stores credentials correctly."""
        config_manager.add_account(**sample_credentials)

        accounts = config_manager.list_accounts()
        assert len(accounts) == 1
        assert accounts[0].name == "test_account"
        assert accounts[0].username == "sa_test_user"
        assert accounts[0].project_id == "12345"
        assert accounts[0].region == "us"

    def test_add_account_first_becomes_default(
        self, config_manager: ConfigManager, sample_credentials: dict[str, str]
    ) -> None:
        """First added account should become default."""
        config_manager.add_account(**sample_credentials)

        accounts = config_manager.list_accounts()
        assert accounts[0].is_default is True

    def test_add_account_duplicate_raises(
        self, config_manager: ConfigManager, sample_credentials: dict[str, str]
    ) -> None:
        """Adding duplicate account should raise AccountExistsError."""
        config_manager.add_account(**sample_credentials)

        with pytest.raises(AccountExistsError) as exc_info:
            config_manager.add_account(**sample_credentials)

        assert exc_info.value.account_name == "test_account"

    def test_add_account_invalid_region_raises(
        self, config_manager: ConfigManager
    ) -> None:
        """Invalid region should raise ValueError."""
        with pytest.raises(ValueError, match="Region must be one of"):
            config_manager.add_account(
                name="test",
                username="user",
                secret="secret",
                project_id="123",
                region="invalid",
            )

    def test_remove_account(
        self, config_manager: ConfigManager, sample_credentials: dict[str, str]
    ) -> None:
        """Test removing an account."""
        config_manager.add_account(**sample_credentials)
        config_manager.remove_account("test_account")

        accounts = config_manager.list_accounts()
        assert len(accounts) == 0

    def test_remove_account_not_found_raises(
        self, config_manager: ConfigManager
    ) -> None:
        """Removing non-existent account should raise AccountNotFoundError."""
        with pytest.raises(AccountNotFoundError) as exc_info:
            config_manager.remove_account("nonexistent")

        assert exc_info.value.account_name == "nonexistent"

    def test_remove_default_updates_default(
        self, config_manager: ConfigManager
    ) -> None:
        """Removing default account should update the default."""
        config_manager.add_account(
            name="first", username="u1", secret="s1", project_id="1", region="us"
        )
        config_manager.add_account(
            name="second", username="u2", secret="s2", project_id="2", region="eu"
        )

        config_manager.remove_account("first")

        accounts = config_manager.list_accounts()
        assert len(accounts) == 1
        assert accounts[0].name == "second"
        # Should have a default (either the remaining one or none)

    def test_set_default(
        self, config_manager: ConfigManager, sample_credentials: dict[str, str]
    ) -> None:
        """Test setting the default account."""
        config_manager.add_account(**sample_credentials)
        config_manager.add_account(
            name="other",
            username="other_user",
            secret="other_secret",
            project_id="67890",
            region="eu",
        )

        config_manager.set_default("other")

        accounts = config_manager.list_accounts()
        default_accounts = [a for a in accounts if a.is_default]
        assert len(default_accounts) == 1
        assert default_accounts[0].name == "other"

    def test_set_default_not_found_raises(
        self, config_manager: ConfigManager, sample_credentials: dict[str, str]
    ) -> None:
        """Setting non-existent account as default should raise."""
        config_manager.add_account(**sample_credentials)

        with pytest.raises(AccountNotFoundError):
            config_manager.set_default("nonexistent")

    def test_get_account(
        self, config_manager: ConfigManager, sample_credentials: dict[str, str]
    ) -> None:
        """Test getting a specific account."""
        config_manager.add_account(**sample_credentials)

        account = config_manager.get_account("test_account")
        assert account.name == "test_account"
        assert account.username == "sa_test_user"

    def test_get_account_not_found_raises(self, config_manager: ConfigManager) -> None:
        """Getting non-existent account should raise AccountNotFoundError."""
        with pytest.raises(AccountNotFoundError):
            config_manager.get_account("nonexistent")


class TestCredentialResolution:
    """Tests for credential resolution logic."""

    def test_resolve_from_env_vars(
        self, config_manager: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Environment variables should take precedence."""
        monkeypatch.setenv("MP_USERNAME", "env_user")
        monkeypatch.setenv("MP_SECRET", "env_secret")
        monkeypatch.setenv("MP_PROJECT_ID", "env_project")
        monkeypatch.setenv("MP_REGION", "eu")

        # Even with a config file account, env vars take precedence
        config_manager.add_account(
            name="file_account",
            username="file_user",
            secret="file_secret",
            project_id="file_project",
            region="us",
        )

        creds = config_manager.resolve_credentials()

        assert creds.username == "env_user"
        assert creds.secret.get_secret_value() == "env_secret"
        assert creds.project_id == "env_project"
        assert creds.region == "eu"

    def test_resolve_falls_back_to_default(
        self, config_manager: ConfigManager, sample_credentials: dict[str, str]
    ) -> None:
        """Should fall back to default account from config."""
        config_manager.add_account(**sample_credentials)

        creds = config_manager.resolve_credentials()

        assert creds.username == "sa_test_user"
        assert creds.project_id == "12345"

    def test_resolve_named_account(self, config_manager: ConfigManager) -> None:
        """Should resolve specific named account."""
        config_manager.add_account(
            name="production",
            username="prod_user",
            secret="prod_secret",
            project_id="prod_123",
            region="us",
        )
        config_manager.add_account(
            name="staging",
            username="staging_user",
            secret="staging_secret",
            project_id="staging_456",
            region="eu",
        )

        creds = config_manager.resolve_credentials(account="staging")

        assert creds.username == "staging_user"
        assert creds.project_id == "staging_456"
        assert creds.region == "eu"

    def test_resolve_named_account_not_found(
        self, config_manager: ConfigManager, sample_credentials: dict[str, str]
    ) -> None:
        """Named account not found should raise AccountNotFoundError."""
        config_manager.add_account(**sample_credentials)

        with pytest.raises(AccountNotFoundError) as exc_info:
            config_manager.resolve_credentials(account="nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "test_account" in exc_info.value.available_accounts

    def test_resolve_no_credentials_raises(self, config_manager: ConfigManager) -> None:
        """No credentials available should raise ConfigError."""
        with pytest.raises(ConfigError) as exc_info:
            config_manager.resolve_credentials()

        assert "No credentials configured" in str(exc_info.value)

    def test_account_not_found_lists_available(
        self, config_manager: ConfigManager
    ) -> None:
        """AccountNotFoundError should list available accounts."""
        config_manager.add_account(
            name="alpha", username="u", secret="s", project_id="1", region="us"
        )
        config_manager.add_account(
            name="beta", username="u", secret="s", project_id="2", region="us"
        )

        with pytest.raises(AccountNotFoundError) as exc_info:
            config_manager.resolve_credentials(account="gamma")

        exc = exc_info.value
        assert exc.available_accounts == ["alpha", "beta"]
        assert "'alpha'" in str(exc)
        assert "'beta'" in str(exc)


class TestConfigFilePersistence:
    """Tests for config file reading/writing."""

    def test_config_persists_across_instances(
        self, config_path: Path, sample_credentials: dict[str, str]
    ) -> None:
        """Config should persist across ConfigManager instances."""
        # First instance adds account
        config1 = ConfigManager(config_path=config_path)
        config1.add_account(**sample_credentials)

        # Second instance should see it
        config2 = ConfigManager(config_path=config_path)
        accounts = config2.list_accounts()

        assert len(accounts) == 1
        assert accounts[0].name == "test_account"

    def test_config_directory_created(self, temp_dir: Path) -> None:
        """Config directory should be created if it doesn't exist."""
        config_path = temp_dir / "subdir" / "deep" / "config.toml"
        config = ConfigManager(config_path=config_path)

        config.add_account(
            name="test",
            username="user",
            secret="secret",
            project_id="123",
            region="us",
        )

        assert config_path.exists()
        assert config_path.parent.exists()
