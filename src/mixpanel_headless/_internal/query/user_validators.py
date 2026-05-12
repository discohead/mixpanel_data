"""Validation rules for query_user() arguments and parameters.

Two validation functions following the two-layer pattern:

- ``validate_user_args()``: Validates Python-level arguments before
  engage param construction (Layer 1, rules U1-U28).
- ``validate_user_params()``: Validates the engage params dict after
  construction (Layer 2, rules UP1-UP4).

Both return ``list[ValidationError]``. Callers decide whether to raise
``BookmarkValidationError``.
"""

from __future__ import annotations

import contextlib
import json
import re
from datetime import date
from typing import Any, Literal

from mixpanel_headless._internal.query.user_builders import _is_cohort_filter
from mixpanel_headless.exceptions import ValidationError
from mixpanel_headless.types import CohortDefinition, Filter

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ACTION_RE = re.compile(
    r"^("
    r"count\(\)"
    r'|extremes\(properties\[".+"\]\)'
    r'|percentile\(properties\[".+"\],\s*[\d.]+\)'
    r'|numeric_summary\(properties\[".+"\]\)'
    r")$"
)


def _normalize_filters(
    where: Filter | list[Filter] | str | None,
) -> list[Filter]:
    """Normalize the where argument into a flat list of Filter objects.

    String expressions and None are returned as an empty list since
    they don't contain Filter objects to inspect.

    Args:
        where: Raw where argument from the caller.

    Returns:
        List of Filter objects (possibly empty).
    """
    if where is None or isinstance(where, str):
        return []
    if isinstance(where, Filter):
        return [where]
    return list(where)


def validate_user_args(
    *,
    where: Filter | list[Filter] | str | None = None,
    cohort: int | CohortDefinition | None = None,
    properties: list[str] | None = None,
    sort_by: str | None = None,
    sort_order: Literal["ascending", "descending"] = "descending",  # noqa: ARG001
    limit: int | None = 1,
    search: str | None = None,
    distinct_id: str | None = None,
    distinct_ids: list[str] | None = None,
    group_id: str | None = None,  # noqa: ARG001
    as_of: str | int | None = None,
    mode: Literal["profiles", "aggregate"] = "aggregate",
    aggregate: Literal["count", "extremes", "percentile", "numeric_summary"] = "count",
    aggregate_property: str | None = None,
    percentile: float | None = None,
    segment_by: list[int] | None = None,
    parallel: bool = False,
    workers: int = 5,
    include_all_users: bool = False,
) -> list[ValidationError]:
    """Validate query_user() arguments before engage param construction.

    Implements rules U0-U28 (U9 enforced at call site). Returns all errors found in a single pass,
    enabling callers to fix multiple issues at once.

    Args:
        where: Filter profiles by property values.
        cohort: Filter by cohort membership.
        properties: Output properties to include.
        sort_by: Property to sort by.
        sort_order: Sort direction.
        limit: Maximum profiles to return.
        search: Full-text search term.
        distinct_id: Single user lookup.
        distinct_ids: Batch user lookup.
        group_id: Group profile query.
        as_of: Point-in-time query date or timestamp.
        mode: Output mode.
        aggregate: Aggregation function.
        aggregate_property: Property to aggregate on.
        percentile: Percentile value (0-100, exclusive). Required when
            ``aggregate="percentile"``.
        segment_by: Cohort IDs for segmented aggregation.
        parallel: Enable concurrent fetching.
        workers: Max concurrent workers.
        include_all_users: Include non-members in cohort queries.

    Returns:
        List of ValidationError objects. Empty list means all arguments
        are valid.

    Example:
        ```python
        errors = validate_user_args(
            distinct_id="user1",
            distinct_ids=["user2"],
        )
        # [ValidationError(path="distinct_id", message="...", code="U1")]
        ```
    """
    errors: list[ValidationError] = []
    filters = _normalize_filters(where)

    # U1: distinct_id and distinct_ids mutually exclusive
    if distinct_id is not None and distinct_ids is not None:
        errors.append(
            ValidationError(
                path="distinct_id",
                message=(
                    "distinct_id and distinct_ids are mutually exclusive; "
                    "provide one or the other, not both"
                ),
                code="U1",
            )
        )

    # U0: where list items must be Filter instances
    for i, item in enumerate(filters):
        if not isinstance(item, Filter):
            errors.append(
                ValidationError(
                    path=f"where[{i}]",
                    message=(f"expected Filter instance, got {type(item).__name__}"),
                    code="U0",
                )
            )
    # Filter down to valid Filter instances for subsequent checks
    filters = [f for f in filters if isinstance(f, Filter)]

    # U2: cohort param and Filter.in_cohort() in where mutually exclusive
    in_cohort_count = sum(
        1 for f in filters if _is_cohort_filter(f) and f._operator == "contains"
    )
    if cohort is not None and in_cohort_count > 0:
        errors.append(
            ValidationError(
                path="cohort",
                message=(
                    "cohort param and Filter.in_cohort() in where are "
                    "mutually exclusive; use one or the other"
                ),
                code="U2",
            )
        )

    # U3: limit must be positive (None means fetch all)
    if limit is not None and limit <= 0:
        errors.append(
            ValidationError(
                path="limit",
                message=f"limit must be a positive integer (got {limit})",
                code="U3",
            )
        )

    # U4: distinct_ids must be non-empty list
    if distinct_ids is not None and len(distinct_ids) == 0:
        errors.append(
            ValidationError(
                path="distinct_ids",
                message="distinct_ids must be a non-empty list",
                code="U4",
            )
        )

    # U5: sort_by must be non-empty string
    if sort_by is not None and sort_by.strip() == "":
        errors.append(
            ValidationError(
                path="sort_by",
                message="sort_by must be a non-empty string",
                code="U5",
            )
        )

    # U6 + U8: as_of string validation (single parse)
    if isinstance(as_of, str):
        parsed_date: date | None = None
        if _DATE_RE.match(as_of):
            with contextlib.suppress(ValueError):
                parsed_date = date.fromisoformat(as_of)
        if parsed_date is None:
            errors.append(
                ValidationError(
                    path="as_of",
                    message=(
                        f"as_of must be a valid YYYY-MM-DD date string (got {as_of!r})"
                    ),
                    code="U6",
                )
            )
        elif parsed_date > date.today():
            errors.append(
                ValidationError(
                    path="as_of",
                    message=(
                        f"as_of must not be in the future "
                        f"(got {as_of}, today is {date.today().isoformat()})"
                    ),
                    code="U8",
                )
            )

    # U7: include_all_users requires cohort (param or Filter.in_cohort in where)
    if include_all_users and cohort is None and in_cohort_count == 0:
        errors.append(
            ValidationError(
                path="include_all_users",
                message=("include_all_users=True requires a cohort parameter"),
                code="U7",
            )
        )

    # U9: Enforced at runtime in _resolve_and_build_user_params (type guard)

    # U10: Filter property names must be non-empty
    for i, f in enumerate(filters):
        if isinstance(f._property, str) and f._property.strip() == "":
            errors.append(
                ValidationError(
                    path=f"where[{i}]._property",
                    message="filter property name must be a non-empty string",
                    code="U10",
                )
            )

    # U25: Filter property must be a string for engage queries
    for i, f in enumerate(filters):
        if not _is_cohort_filter(f) and not isinstance(f._property, str):
            errors.append(
                ValidationError(
                    path=f"where[{i}]._property",
                    message=(
                        f"filter property must be a string for query_user() "
                        f"(got {type(f._property).__name__})"
                    ),
                    code="U25",
                )
            )

    # U29: properties must be non-empty list (if provided)
    if properties is not None and len(properties) == 0:
        errors.append(
            ValidationError(
                path="properties",
                message="properties must be a non-empty list",
                code="U29",
            )
        )

    # U11: properties items must be non-empty strings
    if properties is not None:
        for i, prop in enumerate(properties):
            if prop.strip() == "":
                errors.append(
                    ValidationError(
                        path=f"properties[{i}]",
                        message="property name must be a non-empty string",
                        code="U11",
                    )
                )

    # U12: Filter.not_in_cohort() not supported
    for i, f in enumerate(filters):
        if _is_cohort_filter(f) and f._operator == "does not contain":
            errors.append(
                ValidationError(
                    path=f"where[{i}]",
                    message=(
                        "Filter.not_in_cohort() is not supported in "
                        "query_user() where clauses"
                    ),
                    code="U12",
                )
            )

    # U13: At most one Filter.in_cohort() in where list
    if in_cohort_count > 1:
        errors.append(
            ValidationError(
                path="where",
                message=(
                    f"at most one Filter.in_cohort() is allowed in where "
                    f"(found {in_cohort_count})"
                ),
                code="U13",
            )
        )

    # U14: aggregate_property required when aggregate is not "count"
    if mode == "aggregate" and aggregate != "count" and aggregate_property is None:
        errors.append(
            ValidationError(
                path="aggregate_property",
                message=(
                    f"aggregate_property is required when aggregate "
                    f"is {aggregate!r} (not 'count')"
                ),
                code="U14",
            )
        )

    # U15: aggregate_property must not be set when aggregate is "count"
    if mode == "aggregate" and aggregate == "count" and aggregate_property is not None:
        errors.append(
            ValidationError(
                path="aggregate_property",
                message=(
                    "aggregate_property must not be set when aggregate is 'count'"
                ),
                code="U15",
            )
        )

    # U16: segment_by requires mode="aggregate"
    if segment_by is not None and mode != "aggregate":
        errors.append(
            ValidationError(
                path="segment_by",
                message="segment_by requires mode='aggregate'",
                code="U16",
            )
        )

    # U17: segment_by IDs must be positive integers
    if segment_by is not None:
        for i, sid in enumerate(segment_by):
            if sid <= 0:
                errors.append(
                    ValidationError(
                        path=f"segment_by[{i}]",
                        message=(
                            f"segment_by IDs must be positive integers (got {sid})"
                        ),
                        code="U17",
                    )
                )

    # U26: percentile required when aggregate is "percentile"
    if mode == "aggregate" and aggregate == "percentile" and percentile is None:
        errors.append(
            ValidationError(
                path="percentile",
                message=("percentile is required when aggregate is 'percentile'"),
                code="U26",
            )
        )

    # U27: percentile must not be set when aggregate is not "percentile"
    if mode == "aggregate" and aggregate != "percentile" and percentile is not None:
        errors.append(
            ValidationError(
                path="percentile",
                message=(
                    f"percentile must not be set when aggregate is "
                    f"{aggregate!r} (only valid for aggregate='percentile')"
                ),
                code="U27",
            )
        )

    # U28: percentile must be between 0 and 100 (exclusive)
    if percentile is not None and not (0 < percentile < 100):
        errors.append(
            ValidationError(
                path="percentile",
                message=(
                    f"percentile must be between 0 and 100 exclusive (got {percentile})"
                ),
                code="U28",
            )
        )

    # U18: parallel only applies to mode="profiles"
    if parallel and mode != "profiles":
        errors.append(
            ValidationError(
                path="parallel",
                message="parallel=True only applies to mode='profiles'",
                code="U18",
            )
        )

    # U19: sort_by only applies to mode="profiles"
    if sort_by is not None and mode != "profiles":
        errors.append(
            ValidationError(
                path="sort_by",
                message="sort_by only applies to mode='profiles'",
                code="U19",
            )
        )

    # U20: search only applies to mode="profiles"
    if search is not None and mode != "profiles":
        errors.append(
            ValidationError(
                path="search",
                message="search only applies to mode='profiles'",
                code="U20",
            )
        )

    # U21: distinct_id/distinct_ids only apply to mode="profiles"
    if (distinct_id is not None or distinct_ids is not None) and mode != "profiles":
        errors.append(
            ValidationError(
                path="distinct_id",
                message=("distinct_id/distinct_ids only apply to mode='profiles'"),
                code="U21",
            )
        )

    # U22: properties only applies to mode="profiles"
    if properties is not None and mode != "profiles":
        errors.append(
            ValidationError(
                path="properties",
                message="properties only applies to mode='profiles'",
                code="U22",
            )
        )

    # U30: as_of only applies to mode="profiles"
    if as_of is not None and mode != "profiles":
        errors.append(
            ValidationError(
                path="as_of",
                message="as_of only applies to mode='profiles'",
                code="U30",
            )
        )

    # U23: workers must be between 1 and 5
    if workers < 1 or workers > 5:
        errors.append(
            ValidationError(
                path="workers",
                message=(f"workers must be between 1 and 5 (got {workers})"),
                code="U23",
            )
        )

    # U24: CohortDefinition.to_dict() must succeed
    if isinstance(cohort, CohortDefinition):
        try:
            cohort.to_dict()
        except (ValueError, TypeError, RuntimeError) as exc:
            errors.append(
                ValidationError(
                    path="cohort",
                    message=(f"CohortDefinition.to_dict() failed: {exc}"),
                    code="U24",
                )
            )

    return errors


def validate_user_params(
    params: dict[str, Any],
) -> list[ValidationError]:
    """Validate engage params dict after construction.

    Implements rules UP1-UP4. Checks the generated params dict for
    structural correctness.

    Args:
        params: Engage API params dict to validate.

    Returns:
        List of ValidationError objects. Empty list means all params
        are valid.

    Example:
        ```python
        errors = validate_user_params({
            "sort_order": "invalid",
        })
        # [ValidationError(path="sort_order", message="...", code="UP1")]
        ```
    """
    errors: list[ValidationError] = []

    # UP1: sort_order must be "ascending" or "descending"
    if "sort_order" in params and params["sort_order"] not in (
        "ascending",
        "descending",
    ):
        errors.append(
            ValidationError(
                path="sort_order",
                message=(
                    f"sort_order must be 'ascending' or 'descending' "
                    f"(got {params['sort_order']!r})"
                ),
                code="UP1",
            )
        )

    # UP2: filter_by_cohort must have "id" or "raw_cohort" key
    if "filter_by_cohort" in params:
        fbc = params["filter_by_cohort"]
        if isinstance(fbc, str):
            try:
                fbc = json.loads(fbc)
            except (json.JSONDecodeError, TypeError) as exc:
                errors.append(
                    ValidationError(
                        path="filter_by_cohort",
                        message=f"filter_by_cohort is not valid JSON: {exc}",
                        code="UP2",
                    )
                )
                return errors
        if isinstance(fbc, dict) and "id" not in fbc and "raw_cohort" not in fbc:
            errors.append(
                ValidationError(
                    path="filter_by_cohort",
                    message=(
                        "filter_by_cohort must contain an 'id' or 'raw_cohort' key"
                    ),
                    code="UP2",
                )
            )

    # UP3: output_properties must be non-empty array if present
    if "output_properties" in params:
        op_val = params["output_properties"]
        # Handle both raw list and JSON-encoded string forms
        if isinstance(op_val, str):
            with contextlib.suppress(json.JSONDecodeError):
                op_val = json.loads(op_val)
        if isinstance(op_val, list) and len(op_val) == 0:
            errors.append(
                ValidationError(
                    path="output_properties",
                    message="output_properties must be a non-empty array",
                    code="UP3",
                )
            )

    # UP4: action must be valid aggregation expression
    if "action" in params:
        action = params["action"]
        if not isinstance(action, str) or not _ACTION_RE.match(action):
            errors.append(
                ValidationError(
                    path="action",
                    message=(
                        f"action must be a valid aggregation expression "
                        f'like count(), extremes(properties["prop"]), '
                        f'percentile(properties["prop"], N), '
                        f'or numeric_summary(properties["prop"]) '
                        f"(got {action!r})"
                    ),
                    code="UP4",
                )
            )

    return errors
