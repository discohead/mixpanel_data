# ruff: noqa: ARG001, ARG005
"""Tests for lookup-tables CLI commands.

Tests cover all lookup-tables subcommands:
- list: List lookup tables
- upload: Upload a CSV file as a new lookup table
- update: Update a lookup table
- delete: Delete lookup tables
- upload-url: Get a signed upload URL
- download: Download lookup table data
- download-url: Get a signed download URL
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import typer.testing

from mixpanel_headless.cli.main import app

runner = typer.testing.CliRunner()


class TestLookupTablesList:
    """Tests for mp lookup-tables list."""

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_returns_json_list(self, mock_get_ws: MagicMock) -> None:
        """Successful list returns JSON list of lookup tables."""
        mock_ws = MagicMock()
        mock_ws.list_lookup_tables.return_value = [
            MagicMock(
                model_dump=lambda: {
                    "data_group_id": 1,
                    "name": "countries",
                    "row_count": 200,
                }
            ),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["lookup-tables", "list"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["name"] == "countries"

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_list_with_data_group_id(self, mock_get_ws: MagicMock) -> None:
        """List with --data-group-id passes it to workspace."""
        mock_ws = MagicMock()
        mock_ws.list_lookup_tables.return_value = []
        mock_get_ws.return_value = mock_ws

        runner.invoke(app, ["lookup-tables", "list", "--data-group-id", "42"])
        mock_ws.list_lookup_tables.assert_called_once_with(data_group_id=42)

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_list_without_data_group_id(self, mock_get_ws: MagicMock) -> None:
        """List without --data-group-id passes None."""
        mock_ws = MagicMock()
        mock_ws.list_lookup_tables.return_value = []
        mock_get_ws.return_value = mock_ws

        runner.invoke(app, ["lookup-tables", "list"])
        mock_ws.list_lookup_tables.assert_called_once_with(data_group_id=None)


class TestLookupTablesUpload:
    """Tests for mp lookup-tables upload."""

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_upload_returns_json(self, mock_get_ws: MagicMock, tmp_path: Path) -> None:
        """Successful upload returns JSON."""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id,name\n1,foo\n2,bar\n")

        mock_ws = MagicMock()
        mock_ws.upload_lookup_table.return_value = MagicMock(
            model_dump=lambda: {
                "data_group_id": 10,
                "name": "my-table",
                "row_count": 2,
            }
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "lookup-tables",
                "upload",
                "--name",
                "my-table",
                "--file",
                str(csv_file),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "my-table"

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_upload_missing_file_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Missing CSV file exits with code 3 (INVALID_ARGS)."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "lookup-tables",
                "upload",
                "--name",
                "my-table",
                "--file",
                "/nonexistent/path/data.csv",
            ],
        )
        assert result.exit_code == 3

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_upload_with_data_group_id(
        self, mock_get_ws: MagicMock, tmp_path: Path
    ) -> None:
        """Upload with --data-group-id includes it in params."""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id,name\n1,foo\n")

        mock_ws = MagicMock()
        mock_ws.upload_lookup_table.return_value = MagicMock(
            model_dump=lambda: {
                "data_group_id": 5,
                "name": "replace-table",
            }
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "lookup-tables",
                "upload",
                "--name",
                "replace-table",
                "--file",
                str(csv_file),
                "--data-group-id",
                "5",
            ],
        )
        assert result.exit_code == 0


class TestLookupTablesUpdate:
    """Tests for mp lookup-tables update."""

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_update_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful update returns JSON."""
        mock_ws = MagicMock()
        mock_ws.update_lookup_table.return_value = MagicMock(
            model_dump=lambda: {"data_group_id": 1, "name": "renamed-table"}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "lookup-tables",
                "update",
                "--data-group-id",
                "1",
                "--name",
                "renamed-table",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "renamed-table"

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_update_passes_params(self, mock_get_ws: MagicMock) -> None:
        """Update passes data_group_id and params to workspace."""
        mock_ws = MagicMock()
        mock_ws.update_lookup_table.return_value = MagicMock(
            model_dump=lambda: {"data_group_id": 7, "name": "new-name"}
        )
        mock_get_ws.return_value = mock_ws

        runner.invoke(
            app,
            [
                "lookup-tables",
                "update",
                "--data-group-id",
                "7",
                "--name",
                "new-name",
            ],
        )
        args, kwargs = mock_ws.update_lookup_table.call_args
        assert args[0] == 7


class TestLookupTablesDelete:
    """Tests for mp lookup-tables delete."""

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_delete_succeeds(self, mock_get_ws: MagicMock) -> None:
        """Successful delete exits with code 0."""
        mock_ws = MagicMock()
        mock_ws.delete_lookup_tables.return_value = None
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app, ["lookup-tables", "delete", "--data-group-ids", "1,2,3"]
        )
        assert result.exit_code == 0
        mock_ws.delete_lookup_tables.assert_called_once_with([1, 2, 3])

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_delete_invalid_ids_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Non-integer data group IDs exit with code 3."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app, ["lookup-tables", "delete", "--data-group-ids", "abc,def"]
        )
        assert result.exit_code == 3


class TestLookupTablesUploadUrl:
    """Tests for mp lookup-tables upload-url."""

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_upload_url_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful upload-url returns JSON with URL info."""
        mock_ws = MagicMock()
        mock_ws.get_lookup_upload_url.return_value = MagicMock(
            model_dump=lambda: {
                "url": "https://storage.example.com/upload",
                "path": "/uploads/abc",
                "key": "xyz",
            }
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["lookup-tables", "upload-url"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "url" in data

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_upload_url_with_content_type(self, mock_get_ws: MagicMock) -> None:
        """Upload-url with --content-type passes it to workspace."""
        mock_ws = MagicMock()
        mock_ws.get_lookup_upload_url.return_value = MagicMock(
            model_dump=lambda: {"url": "https://example.com"}
        )
        mock_get_ws.return_value = mock_ws

        runner.invoke(
            app, ["lookup-tables", "upload-url", "--content-type", "application/json"]
        )
        mock_ws.get_lookup_upload_url.assert_called_once_with("application/json")


class TestLookupTablesDownload:
    """Tests for mp lookup-tables download."""

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_download_to_stdout(self, mock_get_ws: MagicMock) -> None:
        """Download without --output prints CSV to stdout."""
        mock_ws = MagicMock()
        mock_ws.download_lookup_table.return_value = b"id,name\n1,foo\n2,bar\n"
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app, ["lookup-tables", "download", "--data-group-id", "1"]
        )
        assert result.exit_code == 0
        assert "id,name" in result.stdout

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_download_to_file(self, mock_get_ws: MagicMock, tmp_path: Path) -> None:
        """Download with --output writes CSV to file."""
        mock_ws = MagicMock()
        mock_ws.download_lookup_table.return_value = b"id,name\n1,foo\n"
        mock_get_ws.return_value = mock_ws

        out_file = tmp_path / "output.csv"
        result = runner.invoke(
            app,
            [
                "lookup-tables",
                "download",
                "--data-group-id",
                "1",
                "--output",
                str(out_file),
            ],
        )
        assert result.exit_code == 0
        assert out_file.exists()
        assert out_file.read_text() == "id,name\n1,foo\n"

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_download_with_options(self, mock_get_ws: MagicMock) -> None:
        """Download passes file_name and limit to workspace."""
        mock_ws = MagicMock()
        mock_ws.download_lookup_table.return_value = b"data"
        mock_get_ws.return_value = mock_ws

        runner.invoke(
            app,
            [
                "lookup-tables",
                "download",
                "--data-group-id",
                "5",
                "--file-name",
                "countries.csv",
                "--limit",
                "100",
            ],
        )
        mock_ws.download_lookup_table.assert_called_once_with(
            5, file_name="countries.csv", limit=100
        )


class TestLookupTablesDownloadUrl:
    """Tests for mp lookup-tables download-url."""

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_download_url_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful download-url returns JSON with url field."""
        mock_ws = MagicMock()
        mock_ws.get_lookup_download_url.return_value = (
            "https://storage.example.com/download/abc"
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app, ["lookup-tables", "download-url", "--data-group-id", "1"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["url"] == "https://storage.example.com/download/abc"

    @patch("mixpanel_headless.cli.commands.lookup_tables.get_workspace")
    def test_download_url_passes_id(self, mock_get_ws: MagicMock) -> None:
        """Download-url passes data_group_id to workspace."""
        mock_ws = MagicMock()
        mock_ws.get_lookup_download_url.return_value = "https://example.com"
        mock_get_ws.return_value = mock_ws

        runner.invoke(app, ["lookup-tables", "download-url", "--data-group-id", "99"])
        mock_ws.get_lookup_download_url.assert_called_once_with(99)
