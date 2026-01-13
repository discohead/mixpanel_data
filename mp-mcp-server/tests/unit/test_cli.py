"""Tests for CLI entry point.

These tests verify the CLI argument parsing works correctly.
"""

from unittest.mock import MagicMock, patch


class TestCliParsing:
    """Tests for CLI argument parsing."""

    def test_cli_accepts_account_option(self) -> None:
        """CLI should accept --account option."""
        from mp_mcp_server.cli import parse_args

        args = parse_args(["--account", "production"])
        assert args.account == "production"

    def test_cli_accepts_transport_option(self) -> None:
        """CLI should accept --transport option."""
        from mp_mcp_server.cli import parse_args

        args = parse_args(["--transport", "http"])
        assert args.transport == "http"

    def test_cli_accepts_port_option(self) -> None:
        """CLI should accept --port option."""
        from mp_mcp_server.cli import parse_args

        args = parse_args(["--port", "9000"])
        assert args.port == 9000

    def test_cli_defaults(self) -> None:
        """CLI should have sensible defaults."""
        from mp_mcp_server.cli import parse_args

        args = parse_args([])
        assert args.account is None
        assert args.transport == "stdio"
        assert args.port == 8000


class TestCliExecution:
    """Tests for CLI execution."""

    def test_cli_runs_server(self) -> None:
        """CLI main should run the MCP server."""
        from mp_mcp_server import cli

        with patch.object(cli, "mcp") as mock_mcp:
            mock_mcp.run = MagicMock()

            # Simulate running with no args (stdio transport)
            with patch("sys.argv", ["mp-mcp-server"]):
                # Just verify the module imports and parse_args works
                args = cli.parse_args([])
                assert args.transport == "stdio"

    def test_main_runs_stdio_by_default(self) -> None:
        """main() should run with stdio transport by default."""
        from mp_mcp_server import cli

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

    def test_main_runs_http_transport(self) -> None:
        """main() should run with SSE transport when http is specified."""
        from mp_mcp_server import cli

        with (
            patch.object(cli, "mcp") as mock_mcp,
            patch.object(cli, "parse_args") as mock_parse,
        ):
            mock_mcp.run = MagicMock()
            mock_parse.return_value = MagicMock(
                account=None, transport="http", port=9000
            )

            cli.main()

            mock_mcp.run.assert_called_once_with(transport="sse", port=9000)

    def test_main_sets_account(self) -> None:
        """main() should set account when provided."""
        from mp_mcp_server import cli

        with (
            patch.object(cli, "mcp") as mock_mcp,
            patch.object(cli, "parse_args") as mock_parse,
            patch.object(cli, "set_account") as mock_set_account,
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
        from mp_mcp_server import cli

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
