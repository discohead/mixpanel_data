"""Tests for authentication and account management tools.

These tests verify the auth tools work correctly with ConfigManager.
Unlike other tool tests, auth tools do NOT use the mock_context fixture's
workspace since they create their own ConfigManager to manage credentials.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError

from mixpanel_data.auth import AccountInfo
from mixpanel_data.exceptions import (
    AccountNotFoundError,
    AuthenticationError,
    ConfigError,
)


class TestListAccountsTool:
    """Tests for the list_accounts tool."""

    def test_list_accounts_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """list_accounts tool should be registered with the MCP server."""
        assert "list_accounts" in registered_tool_names

    def test_list_accounts_returns_empty_list(self) -> None:
        """list_accounts should return empty list when no accounts configured."""
        from mp_mcp.tools.auth import list_accounts

        mock_ctx = MagicMock()

        with patch("mp_mcp.tools.auth.ConfigManager") as mock_config_cls:
            mock_config = mock_config_cls.return_value
            mock_config.list_accounts.return_value = []

            result = list_accounts(mock_ctx)  # type: ignore[operator]

            assert result == []
            mock_config.list_accounts.assert_called_once()

    def test_list_accounts_returns_account_info(self) -> None:
        """list_accounts should return account info for all accounts."""
        from mp_mcp.tools.auth import list_accounts

        mock_ctx = MagicMock()
        mock_accounts = [
            AccountInfo(
                name="prod",
                username="svc-prod",
                project_id="123",
                region="us",
                is_default=True,
            ),
            AccountInfo(
                name="dev",
                username="svc-dev",
                project_id="456",
                region="eu",
                is_default=False,
            ),
        ]

        with patch("mp_mcp.tools.auth.ConfigManager") as mock_config_cls:
            mock_config = mock_config_cls.return_value
            mock_config.list_accounts.return_value = mock_accounts

            result = list_accounts(mock_ctx)  # type: ignore[operator]

            assert len(result) == 2
            assert result[0]["name"] == "prod"
            assert result[0]["username"] == "svc-prod"
            assert result[0]["project_id"] == "123"
            assert result[0]["region"] == "us"
            assert result[0]["is_default"] is True
            assert result[1]["name"] == "dev"
            assert result[1]["is_default"] is False


class TestShowAccountTool:
    """Tests for the show_account tool."""

    def test_show_account_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """show_account tool should be registered with the MCP server."""
        assert "show_account" in registered_tool_names

    def test_show_account_returns_account_with_redacted_secret(self) -> None:
        """show_account should return account info with secret redacted."""
        from mp_mcp.tools.auth import show_account

        mock_ctx = MagicMock()
        mock_account = AccountInfo(
            name="prod",
            username="svc-prod",
            project_id="123456",
            region="us",
            is_default=True,
        )

        with patch("mp_mcp.tools.auth.ConfigManager") as mock_config_cls:
            mock_config = mock_config_cls.return_value
            mock_config.get_account.return_value = mock_account

            result = show_account(mock_ctx, name="prod")  # type: ignore[operator]

            assert result["name"] == "prod"
            assert result["username"] == "svc-prod"
            assert result["secret"] == "********"
            assert result["project_id"] == "123456"
            assert result["region"] == "us"
            assert result["is_default"] is True
            mock_config.get_account.assert_called_once_with("prod")

    def test_show_account_raises_on_not_found(self) -> None:
        """show_account should raise ToolError when account not found."""
        from mp_mcp.tools.auth import show_account

        mock_ctx = MagicMock()

        with patch("mp_mcp.tools.auth.ConfigManager") as mock_config_cls:
            mock_config = mock_config_cls.return_value
            mock_config.get_account.side_effect = AccountNotFoundError(
                "nonexistent", available_accounts=["prod", "dev"]
            )

            with pytest.raises(ToolError) as exc_info:
                show_account(mock_ctx, name="nonexistent")  # type: ignore[operator]

            assert "nonexistent" in str(exc_info.value)


class TestSwitchAccountTool:
    """Tests for the switch_account tool."""

    def test_switch_account_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """switch_account tool should be registered with the MCP server."""
        assert "switch_account" in registered_tool_names

    def test_switch_account_sets_default(self) -> None:
        """switch_account should set the default account."""
        from mp_mcp.tools.auth import switch_account

        mock_ctx = MagicMock()

        with patch("mp_mcp.tools.auth.ConfigManager") as mock_config_cls:
            mock_config = mock_config_cls.return_value
            mock_config.set_default.return_value = None

            result = switch_account(mock_ctx, name="staging")  # type: ignore[operator]

            assert result == {"default": "staging"}
            mock_config.set_default.assert_called_once_with("staging")

    def test_switch_account_raises_on_not_found(self) -> None:
        """switch_account should raise ToolError when account not found."""
        from mp_mcp.tools.auth import switch_account

        mock_ctx = MagicMock()

        with patch("mp_mcp.tools.auth.ConfigManager") as mock_config_cls:
            mock_config = mock_config_cls.return_value
            mock_config.set_default.side_effect = AccountNotFoundError(
                "nonexistent", available_accounts=["prod", "dev"]
            )

            with pytest.raises(ToolError) as exc_info:
                switch_account(mock_ctx, name="nonexistent")  # type: ignore[operator]

            assert "nonexistent" in str(exc_info.value)


class TestTestCredentialsTool:
    """Tests for the test_credentials tool."""

    def test_test_credentials_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """test_credentials tool should be registered with the MCP server."""
        assert "test_credentials" in registered_tool_names

    def test_test_credentials_returns_success(self) -> None:
        """test_credentials should return success result."""
        from mp_mcp.tools.auth import test_credentials

        mock_ctx = MagicMock()
        mock_result: dict[str, Any] = {
            "success": True,
            "account": "prod",
            "project_id": "123456",
            "region": "us",
            "events_found": 42,
        }

        with patch("mp_mcp.tools.auth.Workspace") as mock_workspace_cls:
            mock_workspace_cls.test_credentials.return_value = mock_result

            result = test_credentials(mock_ctx, account="prod")  # type: ignore[operator]

            assert result["success"] is True
            assert result["account"] == "prod"
            assert result["events_found"] == 42
            mock_workspace_cls.test_credentials.assert_called_once_with(account="prod")

    def test_test_credentials_without_account_uses_default(self) -> None:
        """test_credentials should test default account when none specified."""
        from mp_mcp.tools.auth import test_credentials

        mock_ctx = MagicMock()
        mock_result: dict[str, Any] = {
            "success": True,
            "account": None,
            "project_id": "123456",
            "region": "us",
            "events_found": 10,
        }

        with patch("mp_mcp.tools.auth.Workspace") as mock_workspace_cls:
            mock_workspace_cls.test_credentials.return_value = mock_result

            result = test_credentials(mock_ctx)  # type: ignore[operator]

            assert result["success"] is True
            mock_workspace_cls.test_credentials.assert_called_once_with(account=None)

    def test_test_credentials_raises_on_auth_error(self) -> None:
        """test_credentials should raise ToolError on authentication failure."""
        from mp_mcp.tools.auth import test_credentials

        mock_ctx = MagicMock()

        with patch("mp_mcp.tools.auth.Workspace") as mock_workspace_cls:
            mock_workspace_cls.test_credentials.side_effect = AuthenticationError(
                "Invalid credentials"
            )

            with pytest.raises(ToolError) as exc_info:
                test_credentials(mock_ctx, account="prod")  # type: ignore[operator]

            assert "Authentication failed" in str(exc_info.value)

    def test_test_credentials_raises_on_account_not_found(self) -> None:
        """test_credentials should raise ToolError when account not found."""
        from mp_mcp.tools.auth import test_credentials

        mock_ctx = MagicMock()

        with patch("mp_mcp.tools.auth.Workspace") as mock_workspace_cls:
            mock_workspace_cls.test_credentials.side_effect = AccountNotFoundError(
                "nonexistent", available_accounts=["prod", "dev"]
            )

            with pytest.raises(ToolError) as exc_info:
                test_credentials(mock_ctx, account="nonexistent")  # type: ignore[operator]

            assert "nonexistent" in str(exc_info.value)

    def test_test_credentials_raises_on_config_error(self) -> None:
        """test_credentials should raise ToolError on config error."""
        from mp_mcp.tools.auth import test_credentials

        mock_ctx = MagicMock()

        with patch("mp_mcp.tools.auth.Workspace") as mock_workspace_cls:
            mock_workspace_cls.test_credentials.side_effect = ConfigError(
                "No credentials found"
            )

            with pytest.raises(ToolError) as exc_info:
                test_credentials(mock_ctx)  # type: ignore[operator]

            assert "No credentials found" in str(exc_info.value)
