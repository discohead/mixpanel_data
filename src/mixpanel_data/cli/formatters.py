"""Output formatters for CLI commands.

This module provides formatting functions for different output formats:
- JSON: Pretty-printed JSON
- JSONL: Newline-delimited JSON (one object per line)
- Table: Rich ASCII table
- CSV: Comma-separated values with headers
- Plain: Minimal text output (one item per line)
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from typing import Any

from rich.table import Table


def _json_serializer(obj: Any) -> str:
    """Custom JSON serializer for non-standard types."""
    if isinstance(obj, datetime | date):
        return obj.isoformat()
    return str(obj)


def format_json(data: dict[str, Any] | list[Any]) -> str:
    """Format data as pretty-printed JSON.

    Args:
        data: Data to format (dict or list).

    Returns:
        Pretty-printed JSON string with 2-space indentation.
    """
    return json.dumps(data, indent=2, default=_json_serializer, ensure_ascii=False)


def format_jsonl(data: dict[str, Any] | list[Any]) -> str:
    """Format data as newline-delimited JSON (JSONL).

    For lists, outputs one JSON object per line.
    For dicts, outputs a single JSON object.

    Args:
        data: Data to format (dict or list).

    Returns:
        JSONL string with one object per line.
    """
    if isinstance(data, list):
        lines = [
            json.dumps(item, default=_json_serializer, ensure_ascii=False)
            for item in data
        ]
        return "\n".join(lines)
    return json.dumps(data, default=_json_serializer, ensure_ascii=False)


def format_table(
    data: dict[str, Any] | list[Any],
    columns: list[str] | None = None,
) -> Table:
    """Format data as a Rich ASCII table.

    Args:
        data: Data to format (dict or list of dicts).
        columns: Column names to display. If None, auto-detected from data.

    Returns:
        Rich Table object ready for printing.
    """
    table = Table(show_header=True, header_style="bold")

    # Handle single dict as a list of one item
    if isinstance(data, dict):
        data = [data]

    if not data:
        return table

    # Auto-detect columns from first item if not specified
    if columns is None:
        first_item = data[0]
        columns = list(first_item.keys()) if isinstance(first_item, dict) else ["value"]

    # Add columns to table
    for col in columns:
        table.add_column(col.upper().replace("_", " "))

    # Add rows
    for item in data:
        if isinstance(item, dict):
            row = [_format_cell(item.get(col, "")) for col in columns]
        else:
            row = [_format_cell(item)]
        table.add_row(*row)

    return table


def _format_cell(value: Any) -> str:
    """Format a single cell value for table display."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, list | dict):
        return json.dumps(value, default=_json_serializer, ensure_ascii=False)
    return str(value)


def format_csv(data: dict[str, Any] | list[Any]) -> str:
    """Format data as comma-separated values with headers.

    Args:
        data: Data to format (dict or list of dicts).

    Returns:
        CSV string with header row and data rows.
    """
    # Handle single dict as a list of one item
    if isinstance(data, dict):
        data = [data]

    if not data:
        return ""

    output = io.StringIO()

    # Determine fieldnames from first item
    first_item = data[0]
    if isinstance(first_item, dict):
        fieldnames = list(first_item.keys())
        dict_writer = csv.DictWriter(
            output, fieldnames=fieldnames, extrasaction="ignore"
        )
        dict_writer.writeheader()
        for item in data:
            if isinstance(item, dict):
                # Convert non-string values to strings
                row = {k: _csv_value(v) for k, v in item.items()}
                dict_writer.writerow(row)
    else:
        # For non-dict items, use single "value" column
        list_writer = csv.writer(output)
        list_writer.writerow(["value"])
        for item in data:
            list_writer.writerow([_csv_value(item)])

    return output.getvalue()


def _csv_value(value: Any) -> str:
    """Format a value for CSV output."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, list | dict):
        return json.dumps(value, default=_json_serializer, ensure_ascii=False)
    return str(value)


def format_plain(data: dict[str, Any] | list[Any]) -> str:
    """Format data as minimal plain text.

    For lists, outputs one item per line.
    For dicts with a "name" or "value" key, outputs that value.
    For other dicts, outputs key=value pairs.

    Args:
        data: Data to format (dict or list).

    Returns:
        Plain text string with one item per line.
    """
    if isinstance(data, list):
        lines = []
        for item in data:
            if isinstance(item, dict):
                # Try common keys first
                for key in ("name", "value", "event", "id"):
                    if key in item:
                        lines.append(str(item[key]))
                        break
                else:
                    # Fall back to first value
                    if item:
                        lines.append(str(next(iter(item.values()))))
                    else:
                        lines.append("")
            else:
                lines.append(str(item))
        return "\n".join(lines)

    if isinstance(data, dict):
        # For single dict, try common keys or format as key=value
        for key in ("name", "value", "event", "id"):
            if key in data:
                return str(data[key])
        # Format as key=value pairs
        return "\n".join(f"{k}={v}" for k, v in data.items())

    return str(data)
