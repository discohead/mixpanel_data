"""Shared CLI option definitions.

Provides reusable Annotated type aliases for common CLI options
to avoid duplication across commands.
"""

from __future__ import annotations

from typing import Annotated, Literal

import click
import typer

# Output format type for formatting command output
OutputFormat = Literal["json", "jsonl", "table", "csv", "plain"]

# Reusable Annotated type for --format option
# Used by all commands that produce output
# Uses str + click.Choice for Typer compatibility across versions
# (Literal types cause RuntimeError on older Typer versions)
FormatOption = Annotated[
    str,
    typer.Option(
        "--format",
        "-f",
        help="Output format.",
        click_type=click.Choice(["json", "jsonl", "table", "csv", "plain"]),
    ),
]

# Reusable Annotated type for --jq option
# Used by commands that support JSON output filtering
JqOption = Annotated[
    str | None,
    typer.Option(
        "--jq",
        help="Apply jq filter to JSON output (requires --format json or jsonl).",
    ),
]
