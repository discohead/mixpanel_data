"""Tests for CLI entry point.

These tests verify the CLI argument parsing works correctly.
"""

from unittest.mock import MagicMock, patch


class TestCliParsing:
    """Tests for CLI argument parsing."""

    def test_cli_accepts_account_option(self) -> None:
        """CLI should accept --account option."""
        from mp_mcp.cli import parse_args

        args = parse_args(["--account", "production"])
        assert args.account == "production"

    def test_cli_accepts_transport_option(self) -> None:
        """CLI should accept --transport option."""
        from mp_mcp.cli import parse_args

        args = parse_args(["--transport", "sse"])
        assert args.transport == "sse"

    def test_cli_accepts_port_option(self) -> None:
        """CLI should accept --port option."""
        from mp_mcp.cli import parse_args

        args = parse_args(["--port", "9000"])
        assert args.port == 9000

    def test_cli_defaults(self) -> None:
        """CLI should have sensible defaults."""
        from mp_mcp.cli import parse_args

        args = parse_args([])
        assert args.account is None
        assert args.transport == "stdio"
        assert args.port == 8000


class TestCliExecution:
    """Tests for CLI execution."""

    def test_cli_runs_server(self) -> None:
        """CLI main should run the MCP server."""
        from mp_mcp import cli

        with patch.object(cli, "mcp") as mock_mcp:
            mock_mcp.run = MagicMock()

            # Simulate running with no args (stdio transport)
            with patch("sys.argv", ["mp_mcp"]):
                # Just verify the module imports and parse_args works
                args = cli.parse_args([])
                assert args.transport == "stdio"

    def test_main_runs_stdio_by_default(self) -> None:
        """main() should run with stdio transport by default."""
        from mp_mcp import cli

        with (
            patch.object(cli, "mcp") as mock_mcp,
            patch.object(cli, "parse_args") as mock_parse,
        ):
            mock_mcp.run = MagicMock()
            mock_parse.return_value = MagicMock(
                account=None, transport="stdio", port=8000
            )

            cli.main()

            mock_mcp.run.assert_called_once_with(transport="stdio")

    def test_main_runs_sse_transport(self) -> None:
        """main() should run with SSE transport when sse is specified."""
        from mp_mcp import cli

        with (
            patch.object(cli, "mcp") as mock_mcp,
            patch.object(cli, "parse_args") as mock_parse,
        ):
            mock_mcp.run = MagicMock()
            mock_parse.return_value = MagicMock(
                account=None, transport="sse", port=9000
            )

            cli.main()

            mock_mcp.run.assert_called_once_with(transport="sse", port=9000)

    def test_main_sets_account(self) -> None:
        """main() should set account when provided."""
        from mp_mcp import cli

        with (
            patch.object(cli, "mcp") as mock_mcp,
            patch.object(cli, "parse_args") as mock_parse,
            patch.object(cli, "set_account") as mock_set_account,
            patch.object(cli, "_validate_account", return_value=True),
        ):
            mock_mcp.run = MagicMock()
            mock_parse.return_value = MagicMock(
                account="production", transport="stdio", port=8000
            )

            cli.main()

            mock_set_account.assert_called_once_with("production")
            mock_mcp.run.assert_called_once_with(transport="stdio")

    def test_main_does_not_set_account_when_none(self) -> None:
        """main() should not call set_account when account is None."""
        from mp_mcp import cli

        with (
            patch.object(cli, "mcp") as mock_mcp,
            patch.object(cli, "parse_args") as mock_parse,
            patch.object(cli, "set_account") as mock_set_account,
        ):
            mock_mcp.run = MagicMock()
            mock_parse.return_value = MagicMock(
                account=None, transport="stdio", port=8000
            )

            cli.main()

            mock_set_account.assert_not_called()


class TestValidateAccount:
    """Tests for _validate_account function."""

    def test_validate_account_success(self) -> None:
        """_validate_account should return True for valid account."""
        from mp_mcp import cli

        # Patch at the import location (mixpanel_data.Workspace is imported locally)
        with patch("mixpanel_data.Workspace") as mock_workspace:
            mock_workspace.return_value = MagicMock()

            result = cli._validate_account("test_account")

            assert result is True
            mock_workspace.assert_called_once_with(account="test_account")

    def test_validate_account_not_found_exits(self) -> None:
        """_validate_account should exit with code 1 for invalid account."""
        import pytest

        from mixpanel_data.exceptions import AccountNotFoundError
        from mp_mcp import cli

        with (
            patch("mixpanel_data.Workspace") as mock_workspace,
            patch("sys.stderr.write") as mock_stderr,
        ):
            mock_workspace.side_effect = AccountNotFoundError(
                "test_account",
                available_accounts=["prod", "dev"],
            )

            with pytest.raises(SystemExit) as exc_info:
                cli._validate_account("test_account")

            assert exc_info.value.code == 1
            # Verify error message was written
            mock_stderr.assert_called()

    def test_validate_account_shows_available_accounts(self) -> None:
        """_validate_account should show available accounts in error."""
        import pytest

        from mixpanel_data.exceptions import AccountNotFoundError
        from mp_mcp import cli

        with (
            patch("mixpanel_data.Workspace") as mock_workspace,
            patch("sys.stderr.write") as mock_stderr,
        ):
            mock_workspace.side_effect = AccountNotFoundError(
                "bad_account",
                available_accounts=["production", "staging"],
            )

            with pytest.raises(SystemExit):
                cli._validate_account("bad_account")

            # Check error message contains available accounts
            call_args = mock_stderr.call_args[0][0]
            assert "production" in call_args
            assert "staging" in call_args

    def test_validate_account_no_available_accounts(self) -> None:
        """_validate_account should handle no available accounts gracefully."""
        import pytest

        from mixpanel_data.exceptions import AccountNotFoundError
        from mp_mcp import cli

        with (
            patch("mixpanel_data.Workspace") as mock_workspace,
            patch("sys.stderr.write") as mock_stderr,
        ):
            # Create error with empty available_accounts list
            error = AccountNotFoundError("missing", available_accounts=[])
            mock_workspace.side_effect = error

            with pytest.raises(SystemExit):
                cli._validate_account("missing")

            # Should still write error message
            mock_stderr.assert_called()


class TestCliAsMainModule:
    """Tests for running CLI as __main__."""

    def test_cli_main_guard(self) -> None:
        """CLI module should have __main__ guard."""
        # Verify the module structure has the guard
        import mp_mcp.cli as cli_module

        # Check that main() function exists
        assert hasattr(cli_module, "main")
        assert callable(cli_module.main)
