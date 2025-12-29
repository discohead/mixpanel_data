"""CLI parameter validators for Literal types.

Validates string inputs from Typer against Literal types before
passing to Workspace methods, providing early error feedback.
"""

from __future__ import annotations

from typing import Any, TypeVar, cast, get_args

import typer

from mixpanel_data._literal_types import CountType, HourDayUnit, TableType, TimeUnit
from mixpanel_data.cli.utils import ExitCode, err_console
from mixpanel_data.types import EntityType

T = TypeVar("T")


def validate_literal(value: str, literal_type: Any, param_name: str) -> Any:
    """Validate a CLI string against a Literal type.

    Args:
        value: String value from CLI.
        literal_type: The Literal type to validate against.
        param_name: Parameter name for error message.

    Returns:
        The validated value, cast to the Literal type.

    Raises:
        typer.Exit: With code 3 (INVALID_ARGS) if invalid.
    """
    valid_values = get_args(literal_type)
    if value not in valid_values:
        err_console.print(
            f"[red]Error:[/red] Invalid value for {param_name}: '{value}'"
        )
        err_console.print(f"Valid options: {', '.join(valid_values)}")
        raise typer.Exit(ExitCode.INVALID_ARGS)
    return value


def validate_time_unit(value: str, param_name: str = "--unit") -> TimeUnit:
    """Validate time unit for aggregation.

    Args:
        value: String value from CLI (should be "day", "week", or "month").
        param_name: Parameter name for error message. Default: "--unit".

    Returns:
        Validated value as TimeUnit literal type.

    Raises:
        typer.Exit: With code 3 (INVALID_ARGS) if value is invalid.
    """
    validate_literal(value, TimeUnit, param_name)
    return cast(TimeUnit, value)


def validate_hour_day_unit(value: str, param_name: str = "--unit") -> HourDayUnit:
    """Validate hour/day unit for numeric queries.

    Args:
        value: String value from CLI (should be "hour" or "day").
        param_name: Parameter name for error message. Default: "--unit".

    Returns:
        Validated value as HourDayUnit literal type.

    Raises:
        typer.Exit: With code 3 (INVALID_ARGS) if value is invalid.
    """
    validate_literal(value, HourDayUnit, param_name)
    return cast(HourDayUnit, value)


def validate_count_type(value: str, param_name: str = "--type") -> CountType:
    """Validate count type for event counting.

    Args:
        value: String value from CLI (should be "general", "unique", or "average").
        param_name: Parameter name for error message. Default: "--type".

    Returns:
        Validated value as CountType literal type.

    Raises:
        typer.Exit: With code 3 (INVALID_ARGS) if value is invalid.
    """
    validate_literal(value, CountType, param_name)
    return cast(CountType, value)


def validate_entity_type(value: str, param_name: str = "--type") -> EntityType:
    """Validate Lexicon entity type.

    Args:
        value: String value from CLI. Valid types: "event", "profile".
        param_name: Parameter name for error message. Default: "--type".

    Returns:
        Validated value as EntityType literal type.

    Raises:
        typer.Exit: With code 3 (INVALID_ARGS) if value is invalid.
    """
    validate_literal(value, EntityType, param_name)
    return cast(EntityType, value)


def validate_table_type(value: str, param_name: str = "--type") -> TableType:
    """Validate table type for filtering.

    Args:
        value: String value from CLI. Valid types: "events", "profiles".
        param_name: Parameter name for error message. Default: "--type".

    Returns:
        Validated value as TableType literal type.

    Raises:
        typer.Exit: With code 3 (INVALID_ARGS) if value is invalid.
    """
    validate_literal(value, TableType, param_name)
    return cast(TableType, value)
