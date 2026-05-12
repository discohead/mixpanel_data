# ruff: noqa: ARG001, ARG005
"""Tests for ``mp business-context`` CLI commands.

Covers all four subcommands plus the input-source mutex on ``set``:

- ``get``:   project + organization, --organization-id forwarding,
  error mapping, --jq smoke test
- ``set``:   --content / --file / stdin input modes, mutual exclusion,
  oversize content, error mapping
- ``clear``: forwards level + organization_id; outputs cleared state
- ``chain``: returns BusinessContextChain JSON with both scopes
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import typer.testing

from mixpanel_headless.cli.main import app
from mixpanel_headless.exceptions import (
    AuthenticationError,
    BusinessContextValidationError,
    QueryError,
    WorkspaceScopeError,
)

runner = typer.testing.CliRunner()


# =============================================================================
# Helpers
# =============================================================================


def _ctx_mock(
    *,
    level: str = "project",
    content: str = "# Hello",
    organization_id: int | None = None,
    project_id: str | None = "12345",
) -> MagicMock:
    """Build a MagicMock that mimics a BusinessContext.model_dump()."""
    payload: dict[str, object] = {
        "level": level,
        "content": content,
        "organization_id": organization_id,
        "project_id": project_id,
    }
    mock = MagicMock()
    mock.model_dump = lambda: payload
    return mock


def _chain_mock() -> MagicMock:
    """Build a MagicMock that mimics a BusinessContextChain.model_dump()."""
    payload: dict[str, object] = {
        "organization": {
            "level": "organization",
            "content": "# Org",
            "organization_id": 100,
            "project_id": None,
        },
        "project": {
            "level": "project",
            "content": "# Project",
            "organization_id": None,
            "project_id": "12345",
        },
    }
    mock = MagicMock()
    mock.model_dump = lambda: payload
    return mock


# =============================================================================
# get
# =============================================================================


class TestGet:
    """``mp business-context get`` behavior."""

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_default_level_is_project(self, mock_get_ws: MagicMock) -> None:
        """No --level → project-scope GET, JSON includes project_id."""
        ws = MagicMock()
        ws.get_business_context.return_value = _ctx_mock(level="project")
        mock_get_ws.return_value = ws

        result = runner.invoke(app, ["business-context", "get"])
        assert result.exit_code == 0
        ws.get_business_context.assert_called_once_with(
            level="project",
            organization_id=None,
        )
        data = json.loads(result.stdout)
        assert data["level"] == "project"
        assert data["project_id"] == "12345"
        assert data["content"] == "# Hello"

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_organization_level_with_explicit_id(self, mock_get_ws: MagicMock) -> None:
        """--level organization --organization-id forwards both."""
        ws = MagicMock()
        ws.get_business_context.return_value = _ctx_mock(
            level="organization",
            content="# Org info",
            organization_id=42,
            project_id=None,
        )
        mock_get_ws.return_value = ws

        result = runner.invoke(
            app,
            [
                "business-context",
                "get",
                "--level",
                "organization",
                "--organization-id",
                "42",
            ],
        )
        assert result.exit_code == 0
        ws.get_business_context.assert_called_once_with(
            level="organization",
            organization_id=42,
        )
        data = json.loads(result.stdout)
        assert data["organization_id"] == 42

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_jq_filter_extracts_content(self, mock_get_ws: MagicMock) -> None:
        """--jq '.content' produces the markdown body only."""
        ws = MagicMock()
        ws.get_business_context.return_value = _ctx_mock(content="markdown!")
        mock_get_ws.return_value = ws

        result = runner.invoke(
            app,
            ["business-context", "get", "--jq", ".content"],
        )
        assert result.exit_code == 0
        assert "markdown!" in result.stdout

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_invalid_level_exits_2(self, mock_get_ws: MagicMock) -> None:
        """Bogus --level value exits with Click's usage error code (2).

        ``--level`` is now a ``click.Choice`` so Click validates it
        before our handler runs and exits with its standard usage-error
        code 2 (``UsageError`` → ``SystemExit(2)``), matching every
        other ``click.Choice``-validated option in the CLI (e.g.
        ``--format``).
        """
        mock_get_ws.return_value = MagicMock()

        result = runner.invoke(
            app,
            ["business-context", "get", "--level", "bogus"],
        )
        assert result.exit_code == 2

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_auth_error_exits_2(self, mock_get_ws: MagicMock) -> None:
        """AuthenticationError from workspace → AUTH_ERROR (2)."""
        ws = MagicMock()
        ws.get_business_context.side_effect = AuthenticationError(
            "bad token", request_url="/api/app/projects/12345/business-context"
        )
        mock_get_ws.return_value = ws

        result = runner.invoke(app, ["business-context", "get"])
        assert result.exit_code == 2

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_workspace_scope_error_exits_1(self, mock_get_ws: MagicMock) -> None:
        """WorkspaceScopeError → GENERAL_ERROR (1)."""
        ws = MagicMock()
        ws.get_business_context.side_effect = WorkspaceScopeError(
            "ambiguous org",
            code="ORGANIZATION_AMBIGUOUS",
        )
        mock_get_ws.return_value = ws

        result = runner.invoke(
            app,
            ["business-context", "get", "--level", "organization"],
        )
        assert result.exit_code == 1


# =============================================================================
# set
# =============================================================================


class TestSet:
    """``mp business-context set`` behavior."""

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_inline_content(self, mock_get_ws: MagicMock) -> None:
        """--content forwards the literal string to set_business_context."""
        ws = MagicMock()
        ws.set_business_context.return_value = _ctx_mock(content="# Inline")
        mock_get_ws.return_value = ws

        result = runner.invoke(
            app,
            ["business-context", "set", "--content", "# Inline"],
        )
        assert result.exit_code == 0
        ws.set_business_context.assert_called_once_with(
            "# Inline",
            level="project",
            organization_id=None,
        )

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_file_input(self, mock_get_ws: MagicMock, tmp_path: Path) -> None:
        """--file reads from disk and forwards content."""
        ws = MagicMock()
        ws.set_business_context.return_value = _ctx_mock(content="from file")
        mock_get_ws.return_value = ws

        ctx_file = tmp_path / "ctx.md"
        ctx_file.write_text("from file", encoding="utf-8")

        result = runner.invoke(
            app,
            ["business-context", "set", "--file", str(ctx_file)],
        )
        assert result.exit_code == 0
        ws.set_business_context.assert_called_once_with(
            "from file",
            level="project",
            organization_id=None,
        )

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_stdin_input(self, mock_get_ws: MagicMock) -> None:
        """Piped stdin (no flags, non-tty) is forwarded as content."""
        ws = MagicMock()
        ws.set_business_context.return_value = _ctx_mock(content="from stdin")
        mock_get_ws.return_value = ws

        result = runner.invoke(
            app,
            ["business-context", "set"],
            input="from stdin",
        )
        assert result.exit_code == 0
        ws.set_business_context.assert_called_once_with(
            "from stdin",
            level="project",
            organization_id=None,
        )

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_content_and_file_mutex_exits_3(
        self, mock_get_ws: MagicMock, tmp_path: Path
    ) -> None:
        """--content + --file together → INVALID_ARGS (3)."""
        mock_get_ws.return_value = MagicMock()
        ctx_file = tmp_path / "ctx.md"
        ctx_file.write_text("hi", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "business-context",
                "set",
                "--content",
                "x",
                "--file",
                str(ctx_file),
            ],
        )
        assert result.exit_code == 3

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_empty_stdin_refuses_silent_clear(self, mock_get_ws: MagicMock) -> None:
        """Empty / whitespace-only stdin → INVALID_ARGS (3) deterministically.

        Regression guard for the CI/cron `</dev/null` footgun: we must
        never silently send `{"content": ""}` from an empty stdin.
        Clearing context must be explicit (`clear` subcommand, or
        `--content ""`).
        """
        ws = MagicMock()
        mock_get_ws.return_value = ws

        result = runner.invoke(app, ["business-context", "set"], input="")
        assert result.exit_code == 3
        ws.set_business_context.assert_not_called()

        # Whitespace-only stdin is also rejected (no real intent to write).
        result = runner.invoke(app, ["business-context", "set"], input="   \n")
        assert result.exit_code == 3
        ws.set_business_context.assert_not_called()

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_explicit_empty_content_clears(self, mock_get_ws: MagicMock) -> None:
        """`--content ""` is the explicit way to clear via `set`."""
        ws = MagicMock()
        ws.set_business_context.return_value = _ctx_mock(content="")
        mock_get_ws.return_value = ws

        result = runner.invoke(
            app,
            ["business-context", "set", "--content", ""],
        )
        assert result.exit_code == 0
        ws.set_business_context.assert_called_once_with(
            "",
            level="project",
            organization_id=None,
        )

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_missing_file_exits_3(self, mock_get_ws: MagicMock) -> None:
        """--file pointing at a non-existent path → INVALID_ARGS (3)."""
        mock_get_ws.return_value = MagicMock()

        result = runner.invoke(
            app,
            ["business-context", "set", "--file", "/nonexistent/ctx.md"],
        )
        assert result.exit_code == 3

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_oversize_content_exits_invalid_args(self, mock_get_ws: MagicMock) -> None:
        """BusinessContextValidationError from set → INVALID_ARGS (3).

        @handle_errors has an explicit branch for
        BusinessContextValidationError that maps to INVALID_ARGS,
        because the failure is client-side input validation rather
        than an unknown library error.
        """
        ws = MagicMock()
        ws.set_business_context.side_effect = BusinessContextValidationError(
            "too long",
            details={"length": 60_000, "max": 50_000},
        )
        mock_get_ws.return_value = ws

        result = runner.invoke(
            app,
            ["business-context", "set", "--content", "x" * 60_000],
        )
        assert result.exit_code == 3

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_org_level_set_forwards_org_id(self, mock_get_ws: MagicMock) -> None:
        """--level organization --organization-id forwards the int."""
        ws = MagicMock()
        ws.set_business_context.return_value = _ctx_mock(
            level="organization",
            content="# Org",
            organization_id=42,
            project_id=None,
        )
        mock_get_ws.return_value = ws

        result = runner.invoke(
            app,
            [
                "business-context",
                "set",
                "--level",
                "organization",
                "--organization-id",
                "42",
                "--content",
                "# Org",
            ],
        )
        assert result.exit_code == 0
        ws.set_business_context.assert_called_once_with(
            "# Org",
            level="organization",
            organization_id=42,
        )


# =============================================================================
# clear
# =============================================================================


class TestClear:
    """``mp business-context clear`` behavior."""

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_clear_default_level(self, mock_get_ws: MagicMock) -> None:
        """clear with no flags clears project-level."""
        ws = MagicMock()
        ws.clear_business_context.return_value = _ctx_mock(content="")
        mock_get_ws.return_value = ws

        result = runner.invoke(app, ["business-context", "clear"])
        assert result.exit_code == 0
        ws.clear_business_context.assert_called_once_with(
            level="project",
            organization_id=None,
        )
        data = json.loads(result.stdout)
        assert data["content"] == ""

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_clear_organization(self, mock_get_ws: MagicMock) -> None:
        """clear --level organization --organization-id forwards both."""
        ws = MagicMock()
        ws.clear_business_context.return_value = _ctx_mock(
            level="organization",
            content="",
            organization_id=42,
            project_id=None,
        )
        mock_get_ws.return_value = ws

        result = runner.invoke(
            app,
            [
                "business-context",
                "clear",
                "--level",
                "organization",
                "--organization-id",
                "42",
            ],
        )
        assert result.exit_code == 0
        ws.clear_business_context.assert_called_once_with(
            level="organization",
            organization_id=42,
        )


# =============================================================================
# chain
# =============================================================================


class TestChain:
    """``mp business-context chain`` behavior."""

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_chain_returns_both_scopes(self, mock_get_ws: MagicMock) -> None:
        """chain returns JSON with `organization` and `project` blocks."""
        ws = MagicMock()
        ws.get_business_context_chain.return_value = _chain_mock()
        mock_get_ws.return_value = ws

        result = runner.invoke(app, ["business-context", "chain"])
        assert result.exit_code == 0
        ws.get_business_context_chain.assert_called_once_with()
        data = json.loads(result.stdout)
        assert data["organization"]["organization_id"] == 100
        assert data["project"]["project_id"] == "12345"

    @patch("mixpanel_headless.cli.commands.business_context.get_workspace")
    def test_chain_query_error_exits_3(self, mock_get_ws: MagicMock) -> None:
        """QueryError from chain → INVALID_ARGS (3)."""
        ws = MagicMock()
        ws.get_business_context_chain.side_effect = QueryError(
            "boom",
            status_code=400,
            request_url="/api/app/projects/12345/business-context/chain",
        )
        mock_get_ws.return_value = ws

        result = runner.invoke(app, ["business-context", "chain"])
        assert result.exit_code == 3
