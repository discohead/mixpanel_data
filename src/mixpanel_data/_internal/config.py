"""Configuration management for mixpanel_data.

Handles credential storage, resolution, and account management.
Configuration is stored in TOML format at ~/.mp/config.toml by default.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found,unused-ignore]
from pathlib import Path
from typing import Any, Literal, cast

import tomli_w
from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from mixpanel_data.exceptions import (
    AccountExistsError,
    AccountNotFoundError,
    ConfigError,
)

# Valid regions for Mixpanel data residency
VALID_REGIONS = ("us", "eu", "in")
RegionType = Literal["us", "eu", "in"]


class Credentials(BaseModel):
    """Immutable credentials for Mixpanel API authentication.

    This is a frozen Pydantic model that ensures:
    - All fields are validated on construction
    - The secret is never exposed in repr/str output
    - The object cannot be modified after creation
    """

    model_config = ConfigDict(frozen=True)

    username: str
    """Service account username."""

    secret: SecretStr
    """Service account secret (redacted in output)."""

    project_id: str
    """Mixpanel project identifier."""

    region: RegionType
    """Data residency region (us, eu, or in)."""

    @field_validator("region", mode="before")
    @classmethod
    def validate_region(cls, v: str) -> str:
        """Validate and normalize region to lowercase."""
        if not isinstance(v, str):
            raise ValueError(f"Region must be a string. Got: {type(v).__name__}")
        v_lower = v.lower()
        if v_lower not in VALID_REGIONS:
            valid = ", ".join(VALID_REGIONS)
            raise ValueError(f"Region must be one of: {valid}. Got: {v}")
        return v_lower

    @field_validator("username", "project_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """Validate string fields are non-empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v

    def __repr__(self) -> str:
        """Return string representation with redacted secret."""
        return (
            f"Credentials(username={self.username!r}, secret=***, "
            f"project_id={self.project_id!r}, region={self.region!r})"
        )

    def __str__(self) -> str:
        """Return string representation with redacted secret."""
        return self.__repr__()


@dataclass(frozen=True)
class AccountInfo:
    """Information about a configured account (without secret).

    Used for listing accounts without exposing sensitive credentials.
    """

    name: str
    """Account display name."""

    username: str
    """Service account username."""

    project_id: str
    """Mixpanel project identifier."""

    region: str
    """Data residency region."""

    is_default: bool
    """Whether this is the default account."""


class ConfigManager:
    """Manages Mixpanel project credentials and configuration.

    Handles:
    - Adding, removing, and listing project accounts
    - Setting the default account
    - Resolving credentials from environment variables or config file

    Config file location (in priority order):
    1. Explicit config_path parameter
    2. MP_CONFIG_PATH environment variable
    3. Default: ~/.mp/config.toml
    """

    DEFAULT_CONFIG_PATH = Path.home() / ".mp" / "config.toml"

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize ConfigManager.

        Args:
            config_path: Override config file location.
                         Default: ~/.mp/config.toml
        """
        if config_path is not None:
            self._config_path = config_path
        elif "MP_CONFIG_PATH" in os.environ:
            self._config_path = Path(os.environ["MP_CONFIG_PATH"])
        else:
            self._config_path = self.DEFAULT_CONFIG_PATH

    @property
    def config_path(self) -> Path:
        """Return the config file path."""
        return self._config_path

    def _read_config(self) -> dict[str, Any]:
        """Read and parse the config file.

        Returns:
            Parsed config dictionary, or empty dict if file doesn't exist.
        """
        if not self._config_path.exists():
            return {}

        try:
            with self._config_path.open("rb") as f:
                return dict(tomllib.load(f))
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(
                f"Invalid TOML in config file: {e}",
                details={"path": str(self._config_path)},
            ) from e

    def _write_config(self, config: dict[str, Any]) -> None:
        """Write config to file, creating directory if needed.

        Args:
            config: Configuration dictionary to write.
        """
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with self._config_path.open("wb") as f:
            tomli_w.dump(config, f)

    def _get_available_account_names(self) -> list[str]:
        """Get list of configured account names."""
        config = self._read_config()
        accounts = config.get("accounts", {})
        return list(accounts.keys())

    def resolve_credentials(self, account: str | None = None) -> Credentials:
        """Resolve credentials using priority order.

        Resolution order:
        1. Environment variables (MP_USERNAME, MP_SECRET, MP_PROJECT_ID, MP_REGION)
        2. Named account from config file (if account parameter provided)
        3. Default account from config file

        Args:
            account: Optional account name to use instead of default.

        Returns:
            Immutable Credentials object.

        Raises:
            ConfigError: If no credentials can be resolved.
            AccountNotFoundError: If named account doesn't exist.
        """
        # Priority 1: Environment variables
        env_creds = self._resolve_from_env()
        if env_creds is not None:
            return env_creds

        # Priority 2 & 3: Config file (named account or default)
        config = self._read_config()
        accounts = config.get("accounts", {})

        if not accounts:
            raise ConfigError(
                "No credentials configured. "
                "Set MP_USERNAME, MP_SECRET, MP_PROJECT_ID, MP_REGION environment variables, "
                "or add an account with add_account()."
            )

        # Determine which account to use
        account_name: str
        if account is not None:
            account_name = account
        else:
            default_account = config.get("default")
            if default_account is not None and isinstance(default_account, str):
                account_name = default_account
            else:
                # Use the first account if no default set
                account_name = next(iter(accounts.keys()))

        if account_name not in accounts:
            raise AccountNotFoundError(
                account_name,
                available_accounts=list(accounts.keys()),
            )

        account_data = accounts[account_name]
        return Credentials(
            username=account_data["username"],
            secret=SecretStr(account_data["secret"]),
            project_id=account_data["project_id"],
            region=account_data["region"],
        )

    def _resolve_from_env(self) -> Credentials | None:
        """Attempt to resolve credentials from environment variables.

        Returns:
            Credentials if all env vars are set, None otherwise.
        """
        username = os.environ.get("MP_USERNAME")
        secret = os.environ.get("MP_SECRET")
        project_id = os.environ.get("MP_PROJECT_ID")
        region = os.environ.get("MP_REGION")

        # All four must be set to use env vars
        if username and secret and project_id and region:
            if region not in VALID_REGIONS:
                raise ConfigError(
                    f"Invalid MP_REGION: '{region}'. Must be 'us', 'eu', or 'in'."
                )
            return Credentials(
                username=username,
                secret=SecretStr(secret),
                project_id=project_id,
                region=cast(RegionType, region),
            )
        return None

    def list_accounts(self) -> list[AccountInfo]:
        """List all configured accounts.

        Returns:
            List of AccountInfo objects (secrets not included).
        """
        config = self._read_config()
        accounts = config.get("accounts", {})
        default_name = config.get("default")

        result: list[AccountInfo] = []
        for name, data in accounts.items():
            result.append(
                AccountInfo(
                    name=name,
                    username=data.get("username", ""),
                    project_id=data.get("project_id", ""),
                    region=data.get("region", ""),
                    is_default=(name == default_name),
                )
            )

        return result

    def add_account(
        self,
        name: str,
        username: str,
        secret: str,
        project_id: str,
        region: str,
    ) -> None:
        """Add a new account configuration.

        Args:
            name: Display name for the account.
            username: Service account username.
            secret: Service account secret.
            project_id: Mixpanel project ID.
            region: Data residency region (us, eu, in).

        Raises:
            AccountExistsError: If account name already exists.
            ValueError: If region is invalid.
        """
        # Validate region
        region_lower = region.lower()
        if region_lower not in VALID_REGIONS:
            valid = ", ".join(VALID_REGIONS)
            raise ValueError(f"Region must be one of: {valid}. Got: {region}")

        config = self._read_config()
        accounts = config.setdefault("accounts", {})

        if name in accounts:
            raise AccountExistsError(name)

        accounts[name] = {
            "username": username,
            "secret": secret,
            "project_id": project_id,
            "region": region_lower,
        }

        # If this is the first account, make it the default
        if "default" not in config:
            config["default"] = name

        self._write_config(config)

    def remove_account(self, name: str) -> None:
        """Remove an account configuration.

        Args:
            name: Account name to remove.

        Raises:
            AccountNotFoundError: If account doesn't exist.
        """
        config = self._read_config()
        accounts = config.get("accounts", {})

        if name not in accounts:
            raise AccountNotFoundError(name, available_accounts=list(accounts.keys()))

        del accounts[name]

        # If we removed the default, clear it or set to another account
        if config.get("default") == name:
            if accounts:
                config["default"] = next(iter(accounts.keys()))
            else:
                config.pop("default", None)

        self._write_config(config)

    def set_default(self, name: str) -> None:
        """Set the default account.

        Args:
            name: Account name to set as default.

        Raises:
            AccountNotFoundError: If account doesn't exist.
        """
        config = self._read_config()
        accounts = config.get("accounts", {})

        if name not in accounts:
            raise AccountNotFoundError(name, available_accounts=list(accounts.keys()))

        config["default"] = name
        self._write_config(config)

    def get_account(self, name: str) -> AccountInfo:
        """Get information about a specific account.

        Args:
            name: Account name.

        Returns:
            AccountInfo object (secret not included).

        Raises:
            AccountNotFoundError: If account doesn't exist.
        """
        config = self._read_config()
        accounts = config.get("accounts", {})

        if name not in accounts:
            raise AccountNotFoundError(name, available_accounts=list(accounts.keys()))

        data = accounts[name]
        default_name = config.get("default")

        return AccountInfo(
            name=name,
            username=data.get("username", ""),
            project_id=data.get("project_id", ""),
            region=data.get("region", ""),
            is_default=(name == default_name),
        )
