"""Schema documentation generator for CLI help output.

This module provides utilities to generate JSON schema examples from result types,
making it easy for users to understand command output structure and write jq filters.

The generator introspects dataclass types to produce realistic JSON examples that:
- Are valid, copy-pasteable JSON
- Use realistic example values based on field names
- Show nested structures expanded (e.g., funnel steps, retention cohorts)
- Help users understand what fields are available for jq filtering
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints


def _type_to_example(tp: Any, field_name: str = "") -> Any:
    """Convert a type annotation to a realistic example value.

    Uses field name heuristics to generate contextually appropriate examples.
    For example, a field named 'from_date' gets '2025-01-01' instead of 'string'.

    Args:
        tp: The type annotation to convert.
        field_name: The field name, used for heuristic example selection.

    Returns:
        A realistic example value appropriate for the type.
    """
    origin = get_origin(tp)

    # Handle Optional (Union with None) - use the non-None type
    if origin is Union:
        args = [a for a in get_args(tp) if a is not type(None)]
        if args:
            return _type_to_example(args[0], field_name)
        return None

    # Handle Literal - use the first allowed value
    if origin is Literal:
        return get_args(tp)[0]

    # Handle dict - expand nested dicts for series-like structures
    if origin is dict:
        k, v = get_args(tp)
        # Nested dict (e.g., dict[str, dict[str, int]] for time series)
        if get_origin(v) is dict:
            return {
                "US": {"2025-01-01": 150, "2025-01-02": 200},
                "UK": {"2025-01-01": 75, "2025-01-02": 90},
            }
        return {"<key>": _type_to_example(v, field_name)}

    # Handle list - expand nested dataclasses
    if origin is list:
        inner = get_args(tp)[0]
        if hasattr(inner, "__dataclass_fields__"):
            return [_dataclass_to_example(inner)]
        return [_type_to_example(inner, field_name)]

    # Handle tuple - convert to list for JSON
    if origin is tuple:
        return [_type_to_example(a, field_name) for a in get_args(tp)]

    # Handle primitive types with field-name heuristics
    if tp is str:
        field_lower = field_name.lower()
        if "date" in field_lower:
            return "2025-01-01"
        if "event" in field_lower:
            return "Sign Up"
        if "property" in field_lower:
            return "country"
        if "name" in field_lower:
            return "Example Name"
        if "table" in field_lower:
            return "events"
        return "string"

    if tp is int:
        field_lower = field_name.lower()
        if "total" in field_lower or "count" in field_lower or "rows" in field_lower:
            return 15234
        if "id" in field_lower:
            return 12345
        if "size" in field_lower:
            return 500
        return 100

    if tp is float:
        field_lower = field_name.lower()
        if "rate" in field_lower or "percentage" in field_lower:
            return 0.73
        if "duration" in field_lower or "seconds" in field_lower:
            return 12.5
        return 0.85

    if tp is bool:
        return True

    # Handle nested dataclasses
    if hasattr(tp, "__dataclass_fields__"):
        return _dataclass_to_example(tp)

    # Handle datetime
    if hasattr(tp, "__name__") and tp.__name__ == "datetime":
        return "2025-01-15T10:30:00Z"

    return None


def _dataclass_to_example(cls: type[Any]) -> dict[str, Any]:
    """Convert a dataclass to a JSON-ready dict with example values.

    Skips private fields (those starting with underscore).

    Args:
        cls: The dataclass type to convert.

    Returns:
        A dictionary with example values for each public field.
    """
    hints = get_type_hints(cls)
    result: dict[str, Any] = {}
    for field in dataclasses.fields(cls):
        if field.name.startswith("_"):
            continue
        tp = hints.get(field.name, field.type)
        result[field.name] = _type_to_example(tp, field.name)
    return result


def generate_schema_json(result_type: type[Any], indent: int = 2) -> str:
    """Generate a JSON schema example from a result type.

    Args:
        result_type: The dataclass result type to document.
        indent: JSON indentation level.

    Returns:
        Formatted JSON string showing the output structure.
    """
    example = _dataclass_to_example(result_type)
    return json.dumps(example, indent=indent)


# =============================================================================
# Curated Examples for Common Result Types
# =============================================================================
# Some types benefit from hand-crafted examples that show more realistic data
# than auto-generation can provide (e.g., multiple funnel steps).


def get_funnel_example() -> str:
    """Get a curated funnel result example with multiple steps.

    Returns:
        JSON string showing a realistic 4-step funnel.
    """
    example = {
        "funnel_id": 12345,
        "funnel_name": "Onboarding Funnel",
        "from_date": "2025-01-01",
        "to_date": "2025-01-31",
        "conversion_rate": 0.23,
        "steps": [
            {"event": "Sign Up", "count": 10000, "conversion_rate": 1.0},
            {"event": "Verify Email", "count": 7500, "conversion_rate": 0.75},
            {"event": "Complete Profile", "count": 4200, "conversion_rate": 0.56},
            {"event": "First Purchase", "count": 2300, "conversion_rate": 0.55},
        ],
    }
    return json.dumps(example, indent=2)


def get_retention_example() -> str:
    """Get a curated retention result example with multiple cohorts.

    Returns:
        JSON string showing retention cohorts with decay.
    """
    example = {
        "born_event": "Sign Up",
        "return_event": "Login",
        "from_date": "2025-01-01",
        "to_date": "2025-01-31",
        "unit": "day",
        "cohorts": [
            {"date": "2025-01-01", "size": 500, "retention": [1.0, 0.65, 0.45, 0.38]},
            {"date": "2025-01-02", "size": 480, "retention": [1.0, 0.62, 0.41, 0.35]},
            {"date": "2025-01-03", "size": 520, "retention": [1.0, 0.68, 0.48, 0.40]},
        ],
    }
    return json.dumps(example, indent=2)


def get_segmentation_example() -> str:
    """Get a curated segmentation result example.

    Returns:
        JSON string showing segmented time series data.
    """
    example = {
        "event": "Sign Up",
        "from_date": "2025-01-01",
        "to_date": "2025-01-07",
        "unit": "day",
        "segment_property": "country",
        "total": 1850,
        "series": {
            "US": {
                "2025-01-01": 150,
                "2025-01-02": 175,
                "2025-01-03": 160,
            },
            "UK": {
                "2025-01-01": 75,
                "2025-01-02": 80,
                "2025-01-03": 70,
            },
        },
    }
    return json.dumps(example, indent=2)


def get_fetch_events_example() -> str:
    """Get a curated fetch events result example.

    Returns:
        JSON string showing fetch result metadata.
    """
    example = {
        "table": "events",
        "rows": 15234,
        "type": "events",
        "duration_seconds": 12.5,
        "date_range": ["2025-01-01", "2025-01-31"],
        "fetched_at": "2025-01-15T10:30:00Z",
    }
    return json.dumps(example, indent=2)


# =============================================================================
# jq Examples Registry
# =============================================================================
# Curated jq filter examples for each command, showing common use cases.

JQ_EXAMPLES: dict[str, list[tuple[str, str]]] = {
    "query segmentation": [
        (".total", "Total event count"),
        (".series | keys", "List segment names"),
        ('.series["US"] | add', "Sum counts for one segment"),
        (
            "[.series | to_entries[] | {segment: .key, total: (.value | add)}]",
            "Totals per segment",
        ),
    ],
    "query funnel": [
        (".conversion_rate", "Overall conversion rate"),
        (".steps | length", "Number of funnel steps"),
        (".steps[-1].count", "Users completing the funnel"),
        (".steps[] | {event, rate: .conversion_rate}", "Event and rate per step"),
    ],
    "query retention": [
        (".cohorts | length", "Number of cohorts"),
        (".cohorts[0].retention", "First cohort retention curve"),
        (
            ".cohorts[] | {date, size, day7: .retention[7]}",
            "Day 7 retention per cohort",
        ),
    ],
    "fetch events": [
        (".rows", "Number of events fetched"),
        (".duration_seconds | round", "Fetch duration in seconds"),
        (".date_range", "Date range fetched"),
    ],
    "fetch profiles": [
        (".rows", "Number of profiles fetched"),
        (".table", "Table name created"),
    ],
    "inspect events": [
        (".[:5]", "First 5 event names"),
        (". | length", "Total number of event types"),
    ],
    "inspect funnels": [
        (".[] | {id: .funnel_id, name}", "Funnel IDs and names"),
        (".[:3]", "First 3 funnels"),
    ],
}


def get_jq_examples(command: str) -> list[tuple[str, str]] | None:
    """Get curated jq examples for a command.

    Args:
        command: The command name (e.g., 'query segmentation').

    Returns:
        List of (filter, description) tuples, or None if no examples.
    """
    return JQ_EXAMPLES.get(command)


def format_jq_examples(command: str) -> str:
    """Format jq examples as help text.

    Args:
        command: The command name.

    Returns:
        Formatted string for inclusion in docstring, or empty string.
    """
    examples = get_jq_examples(command)
    if not examples:
        return ""

    lines = ["jq Examples:"]
    for filter_expr, description in examples:
        lines.append(f"    --jq '{filter_expr}'")
        lines.append(f"        {description}")
    return "\n".join(lines)
