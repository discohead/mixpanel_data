"""Reusable builder functions for bookmark JSON sections.

Extracted from ``Workspace._build_query_params()`` to enable reuse across
insights, funnels, retention, and flows query builders. Each function
produces a fragment of the Mixpanel bookmark ``params`` JSON structure.

These are internal helpers — import from ``mixpanel_headless._internal.bookmark_builders``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any, Literal, cast

from mixpanel_headless._literal_types import QueryTimeUnit
from mixpanel_headless.types import (
    CohortBreakdown,
    CustomPropertyRef,
    Filter,
    FrequencyBreakdown,
    FrequencyFilter,
    GroupBy,
    InlineCustomProperty,
    PropertyInput,
    TimeComparison,
    _sanitize_raw_cohort,
)


def _build_composed_properties(
    inputs: dict[str, PropertyInput],
) -> dict[str, dict[str, str]]:
    """Convert a PropertyInput mapping to bookmark composedProperties format.

    Transforms the user-facing ``inputs`` dict (letter → PropertyInput)
    into the JSON structure expected by Mixpanel's ``customProperty``
    bookmark schema.

    Args:
        inputs: Mapping from single uppercase letters (A-Z) to
            ``PropertyInput`` objects.

    Returns:
        Dict mapping each letter to a dict with ``value``, ``type``,
        and ``resourceType`` keys.

    Example:
        ```python
        from mixpanel_headless._internal.bookmark_builders import (
            _build_composed_properties,
        )
        from mixpanel_headless.types import PropertyInput

        result = _build_composed_properties({
            "A": PropertyInput("price", type="number"),
        })
        # {"A": {"value": "price", "type": "number", "resourceType": "event"}}
        ```
    """
    return {
        key: {
            "value": prop.name,
            "type": prop.type,
            "resourceType": prop.resource_type,
        }
        for key, prop in inputs.items()
    }


def build_time_section(
    *,
    from_date: str | None,
    to_date: str | None,
    last: int,
    unit: QueryTimeUnit,
) -> list[dict[str, Any]]:
    """Build the ``sections.time`` array for bookmark params.

    Produces a single-element list containing one time entry dict.
    Three cases are handled:

    - **Absolute range**: both ``from_date`` and ``to_date`` set.
    - **From-only range**: only ``from_date`` set; ``to_date`` is filled
      with today's date.
    - **Relative range**: neither date set; uses ``last`` days.

    Args:
        from_date: Start date (YYYY-MM-DD) or ``None``.
        to_date: End date (YYYY-MM-DD) or ``None``.
        last: Number of days for relative range (used when no dates given).
        unit: Time granularity (``"hour"``, ``"day"``, ``"week"``,
            ``"month"``, ``"quarter"``).

    Returns:
        Single-element list with one time entry dict. Structure varies
        by case:

        - Absolute: ``{"dateRangeType": "between", "unit": ..., "value": [from, to]}``
        - From-only: same as absolute with ``to_date`` = today
        - Relative: ``{"dateRangeType": "in the last", "unit": ..., "window": {...}}``

    Example:
        ```python
        time = build_time_section(
            from_date="2025-01-01", to_date="2025-01-31",
            last=30, unit="day",
        )
        # [{"dateRangeType": "between", "unit": "day",
        #   "value": ["2025-01-01", "2025-01-31"]}]
        ```
    """
    if from_date is not None:
        effective_to = to_date if to_date is not None else date.today().isoformat()
        time_entry: dict[str, Any] = {
            "dateRangeType": "between",
            "unit": unit,
            "value": [from_date, effective_to],
        }
    else:
        time_entry = {
            "dateRangeType": "in the last",
            "unit": unit,
            "window": {"unit": "day", "value": last},
        }
    return [time_entry]


def build_date_range(
    *,
    from_date: str | None,
    to_date: str | None,
    last: int,
) -> dict[str, Any]:
    """Build a flat date range dict for flows (non-sections format).

    Flows use a flat ``date_range`` object rather than the sections-based
    ``sections.time`` array used by insights.

    Args:
        from_date: Start date (YYYY-MM-DD) or ``None``.
        to_date: End date (YYYY-MM-DD) or ``None``.
        last: Number of days for relative range.

    Returns:
        Date range dict. Structure varies by case:

        - Absolute: ``{"type": "between", "from_date": ..., "to_date": ...}``
        - Relative: ``{"type": "in the last", "from_date": {"unit": "day", "value": N}, "to_date": "$now"}``

    Example:
        ```python
        dr = build_date_range(from_date=None, to_date=None, last=30)
        # {"type": "in the last",
        #  "from_date": {"unit": "day", "value": 30},
        #  "to_date": "$now"}
        ```
    """
    if from_date is not None and to_date is not None:
        return {
            "type": "between",
            "from_date": from_date,
            "to_date": to_date,
        }
    return {
        "type": "in the last",
        "from_date": {"unit": "day", "value": last},
        "to_date": "$now",
    }


def build_filter_section(
    where: Filter | FrequencyFilter | Sequence[Filter | FrequencyFilter] | None,
) -> list[dict[str, Any]]:
    """Build the ``sections.filter`` array for bookmark params.

    Converts ``None``, a single ``Filter`` or ``FrequencyFilter``, or a
    list of ``Filter`` / ``FrequencyFilter`` objects into the list-of-dicts
    format expected by the Mixpanel bookmark API.

    Args:
        where: Filter specification. ``None`` means no filters,
            a single ``Filter`` or ``FrequencyFilter`` is wrapped in a
            list, a list is processed element-by-element.

    Returns:
        List of filter entry dicts (may be empty).

    Example:
        ```python
        filters = build_filter_section(Filter.equals("country", "US"))
        # [{"resourceType": "events", "filterType": "string", ...}]
        ```
    """
    if where is None:
        return []
    filters_list = list(where) if isinstance(where, (list, tuple)) else [where]
    result: list[dict[str, Any]] = []
    for f in filters_list:
        if isinstance(f, FrequencyFilter):
            result.append(build_frequency_filter_entry(f))
        elif isinstance(f, Filter):
            result.append(build_filter_entry(f))
    return result


def patch_custom_property_filters_for_transform(
    filter_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Add ``value`` sentinel to custom property filters for server compat.

    The server's ``transform_insights_filters_to_funnels()`` does a hard
    ``f["value"]`` access on global ``sections.filter`` entries before
    ``arb_selector`` processes them.  Custom property filters identify
    the property via ``customPropertyId`` or ``customProperty`` instead
    of ``value``, causing a ``KeyError`` and HTTP 500.

    Injecting ``"value": None`` satisfies the hard access.  The
    downstream ``arb_selector`` routes on ``is_custom_property()``, not
    ``propertyName``, so the sentinel is harmless.

    This must **not** be applied to per-step or per-metric filters —
    the insights validator rejects ``value: None`` in those positions.

    Args:
        filter_entries: List of filter dicts from ``build_filter_section()``.

    Returns:
        The same list, mutated in-place, with ``"value": None`` added
        to any entry that has ``customPropertyId`` or ``customProperty``
        but no ``value`` key.
    """
    for entry in filter_entries:
        if "value" not in entry and (
            "customPropertyId" in entry or "customProperty" in entry
        ):
            entry["value"] = None
    return filter_entries


def build_group_section(
    group_by: str
    | GroupBy
    | CohortBreakdown
    | FrequencyBreakdown
    | Sequence[str | GroupBy | CohortBreakdown | FrequencyBreakdown]
    | None,
    *,
    data_group_id: int | None = None,
) -> list[dict[str, Any]]:
    """Build the ``sections.group`` array for bookmark params.

    Converts group-by specifications into the list-of-dicts format
    expected by the Mixpanel bookmark API. Supports strings (simple
    property name), ``GroupBy`` objects (with optional bucketing),
    ``CohortBreakdown`` objects (cohort-based segmentation),
    ``FrequencyBreakdown`` objects (event frequency segmentation),
    and lists mixing all four.

    Args:
        group_by: Group-by specification. ``None`` means no grouping.
            Strings produce default string-typed entries. ``GroupBy``
            objects allow custom property types and numeric bucketing.
            ``CohortBreakdown`` objects produce cohort group entries.
            ``FrequencyBreakdown`` objects produce frequency group entries.
        data_group_id: Optional data group ID for group-level analytics.
            Threads into ``dataGroupId`` fields within group entries
            that support it (custom property refs, inline custom
            properties, cohort breakdowns). Default: ``None``.

    Returns:
        List of group entry dicts (may be empty).

    Raises:
        TypeError: If any element is not ``str``, ``GroupBy``,
            ``CohortBreakdown``, or ``FrequencyBreakdown``.

    Example:
        ```python
        groups = build_group_section(CohortBreakdown(123, "Power Users"))
        # [{"value": ["Power Users", "Not In Power Users"],
        #   "resourceType": "events", ...}]
        ```
    """
    if group_by is None:
        return []

    groups = list(group_by) if isinstance(group_by, (list, tuple)) else [group_by]
    group_section: list[dict[str, Any]] = []

    for g in groups:
        if isinstance(g, str):
            group_section.append(
                {
                    "value": g,
                    "propertyName": g,
                    "resourceType": "events",
                    "propertyType": "string",
                    "propertyDefaultType": "string",
                }
            )
        elif isinstance(g, FrequencyBreakdown):
            group_section.append(
                build_frequency_group_entry(g, data_group_id=data_group_id)
            )
        elif isinstance(g, GroupBy):
            prop = g.property
            if isinstance(prop, CustomPropertyRef):
                group_entry: dict[str, Any] = {
                    "customPropertyId": prop.id,
                    "value": None,
                    "resourceType": "events",
                    "profileType": None,
                    "search": "",
                    "dataGroupId": data_group_id,
                    "dataset": "$mixpanel",
                    "propertyType": g.property_type,
                    "typeCast": None,
                    "unit": None,
                    "isHidden": False,
                }
            elif isinstance(prop, InlineCustomProperty):
                effective_type = (
                    prop.property_type
                    if prop.property_type is not None
                    else g.property_type
                )
                composed = _build_composed_properties(prop.inputs)
                group_entry = {
                    "customProperty": {
                        "displayFormula": prop.formula,
                        "composedProperties": composed,
                        "name": "",
                        "description": "",
                        "propertyType": effective_type,
                        "resourceType": prop.resource_type,
                    },
                    "value": None,
                    "resourceType": prop.resource_type,
                    "profileType": None,
                    "search": "",
                    "dataGroupId": data_group_id,
                    "dataset": "$mixpanel",
                    "propertyType": effective_type,
                    "typeCast": None,
                    "unit": None,
                    "isHidden": False,
                }
            elif g._list_item_mode is not None:
                # resourceType is hardcoded "events" and propertyType is
                # hardcoded "object": GroupBy.list_item is event-only —
                # the Mixpanel UI does not support list-of-object
                # breakdowns for people properties, so the classmethod
                # exposes no resource_type parameter. Asymmetric with
                # Filter.list_contains, which DOES accept
                # resource_type="people" because the wire format permits
                # list-object filters on people properties (just not
                # breakdowns).
                mode = g._list_item_mode
                group_entry = {
                    "dataset": "$mixpanel",
                    "value": prop,
                    "resourceType": "events",
                    "joinPropertyType": "list",
                    "propertyType": "object",
                    "listItemGroup": {
                        "resourceType": "event",
                        "propertyName": mode.sub,
                        "propertyDefaultType": mode.sub_type,
                        "propertyType": mode.sub_type,
                    },
                }
            else:
                group_entry = {
                    "value": prop,
                    "propertyName": prop,
                    "resourceType": "events",
                    "propertyType": g.property_type,
                    "propertyDefaultType": g.property_type,
                }
            if g.bucket_size is not None:
                group_entry["customBucket"] = {
                    "bucketSize": g.bucket_size,
                }
                if g.bucket_min is not None:
                    group_entry["customBucket"]["min"] = g.bucket_min
                if g.bucket_max is not None:
                    group_entry["customBucket"]["max"] = g.bucket_max
            group_section.append(group_entry)
        elif isinstance(g, CohortBreakdown):
            group_section.append(
                _build_cohort_group_entry(g, data_group_id=data_group_id)
            )
        else:
            raise TypeError(
                f"group_by elements must be str, GroupBy, CohortBreakdown, "
                f"or FrequencyBreakdown, got {type(g).__name__}: {g!r}"
            )

    return group_section


def _build_cohort_group_entry(
    cb: CohortBreakdown,
    *,
    data_group_id: int | None = None,
) -> dict[str, Any]:
    """Build a single cohort group entry for sections.group[].

    Produces the cohort-specific group dict with ``cohorts`` array
    containing one or two entries (with/without negated) depending
    on ``include_negated``.

    Args:
        cb: CohortBreakdown specification.
        data_group_id: Optional data group ID for group-level analytics.
            Threads into ``data_group_id`` in cohort entries and
            ``dataGroupId`` in the top-level group entry.
            Default: ``None``.

    Returns:
        Group entry dict with ``cohorts`` array.

    Example:
        ```python
        entry = _build_cohort_group_entry(CohortBreakdown(123, "PU"))
        # {"value": ["PU", "Not In PU"], "cohorts": [...], ...}
        ```
    """
    name = cb.name or ""

    # Build cohort entries — saved vs inline use different API schemas:
    # Schema 1 (saved): allows groups, count, description, etc.
    # Schema 2 (inline): allows raw_cohort, dataset, but NOT groups
    base_cohort: dict[str, Any] = {
        "name": name,
        "negated": False,
        "data_group_id": data_group_id,
    }
    if isinstance(cb.cohort, int):
        base_cohort["id"] = cb.cohort
        base_cohort["groups"] = []
    else:
        base_cohort["raw_cohort"] = _sanitize_raw_cohort(cb.cohort.to_dict())

    cohorts: list[dict[str, Any]] = [base_cohort]
    value_labels: list[str] = [name]

    if cb.include_negated:
        cohorts.append({**base_cohort, "negated": True})
        value_labels.append(f"Not In {name}")

    return {
        "value": value_labels,
        "resourceType": "events",
        "profileType": None,
        "search": "",
        "dataGroupId": data_group_id,
        "propertyType": None,
        "typeCast": None,
        "cohorts": cohorts,
        "isHidden": False,
    }


def build_filter_entry(f: Filter) -> dict[str, Any]:
    """Convert a Filter object to a bookmark filter dict.

    Maps the internal Filter fields to the key names expected by the
    Mixpanel bookmark API. Includes ``filterDateUnit`` only for
    relative date filters that have a date unit set.

    Args:
        f: A ``Filter`` object constructed via its class methods.

    Returns:
        Bookmark filter dict with keys: ``resourceType``, ``filterType``,
        ``defaultType``, ``value``, ``filterValue``, ``filterOperator``,
        and optionally ``filterDateUnit``.  For ``CustomPropertyRef``
        properties the dict also contains ``customPropertyId`` and
        ``dataset``.  For ``InlineCustomProperty`` properties it contains
        ``customProperty`` (nested definition) and ``dataset``, and the
        ``filterType``/``defaultType`` are overridden from the inline
        property's ``property_type``.

    Example:
        ```python
        entry = build_filter_entry(Filter.equals("country", "US"))
        # {"resourceType": "events", "filterType": "string",
        #  "defaultType": "string", "value": "country",
        #  "filterValue": ["US"], "filterOperator": "equals"}
        ```
    """
    if f._operator == "list_contains":
        return _build_list_contains_entry(f)
    prop = f._property
    entry: dict[str, Any] = {
        "resourceType": f._resource_type,
        "filterType": f._property_type,
        "defaultType": f._property_type,
        "filterValue": f._value,
        "filterOperator": f._operator,
    }
    if isinstance(prop, CustomPropertyRef):
        entry["customPropertyId"] = prop.id
        entry["dataset"] = "$mixpanel"
    elif isinstance(prop, InlineCustomProperty):
        effective_type = (
            prop.property_type if prop.property_type is not None else f._property_type
        )
        entry["customProperty"] = {
            "displayFormula": prop.formula,
            "composedProperties": _build_composed_properties(prop.inputs),
            "name": "",
            "description": "",
            "propertyType": effective_type,
            "resourceType": prop.resource_type,
        }
        entry["filterType"] = effective_type
        entry["defaultType"] = effective_type
        entry["dataset"] = "$mixpanel"
        entry["resourceType"] = prop.resource_type
    else:
        entry["value"] = prop
    if f._date_unit is not None:
        entry["filterDateUnit"] = f._date_unit
    return entry


def _build_list_contains_entry(f: Filter) -> dict[str, Any]:
    """Build the bookmark entry for a ``Filter.list_contains`` filter.

    Emits the ``listItemFilters`` wire structure used by Mixpanel
    Insights to filter on subproperties of objects nested inside a list
    property (e.g. ``cart`` is a list of ``{"Brand": str, ...}``
    items). Each inner ``Filter`` is serialized via the same
    :func:`build_filter_entry` recursively, then ``dataset`` is
    backfilled to ``"$mixpanel"`` since the wire format requires it on
    inner items even for plain string properties.

    Trusts that ``Filter.__post_init__`` has already validated the
    ``list_contains`` invariants (``_list_item_filters`` and
    ``_list_item_quantifier`` non-None). Direct construction with the
    ``list_contains`` operator that omits either field is rejected at
    Filter construction time, so this builder never sees ``None``.

    Args:
        f: A ``Filter`` constructed via ``Filter.list_contains(...)``.

    Returns:
        Bookmark filter dict carrying ``listItemFilters``,
        ``listQuantifier``, and the constant outer wrapper
        (``filterOperator: "true"``, ``filterValue: True``,
        ``filterType: "object"``, ``filterJoinType: "list"``).
    """
    # Filter.__post_init__ guarantees these are non-None when
    # _operator == "list_contains"; cast (not assert) makes this an
    # explicit type-narrowing claim, not a redundant runtime check.
    list_item_filters = cast(tuple[Filter, ...], f._list_item_filters)
    list_item_quantifier = cast(Literal["any", "all"], f._list_item_quantifier)
    inner: list[dict[str, Any]] = []
    for sub in list_item_filters:
        sub_entry = build_filter_entry(sub)
        sub_entry.setdefault("dataset", "$mixpanel")
        inner.append(sub_entry)
    return {
        "dataset": "$mixpanel",
        "value": f._property,
        "resourceType": f._resource_type,
        "filterType": "object",
        "defaultType": "object",
        "filterJoinType": "list",
        "listQuantifier": list_item_quantifier,
        "listItemFilters": inner,
        "filterOperator": "true",
        "filterValue": True,
    }


def build_flow_property_filter(
    filters: list[Filter],
) -> dict[str, Any]:
    """Build the ``filter_by_event`` dict for flow bookmark params.

    Flows accept global property filters via a ``filter_by_event``
    top-level key containing an ``operator`` (always ``"and"``) and
    a ``children`` array of filter entries. Each child is produced
    by :func:`build_filter_entry` with an added ``propertyName`` key.

    Args:
        filters: List of property ``Filter`` objects. Must not be
            empty — caller should check before calling.

    Returns:
        Dict with ``operator`` and ``children`` keys suitable for
        the ``filter_by_event`` bookmark key.

    Example:
        ```python
        fbe = build_flow_property_filter([Filter.equals("country", "US")])
        # {"operator": "and", "children": [
        #   {"filterOperator": "equals", "filterType": "string",
        #    "propertyName": "country", "filterValue": ["US"],
        #    "resourceType": "events"}
        # ]}
        ```
    """
    if not filters:
        raise ValueError(
            "build_flow_property_filter requires at least one filter; "
            "caller should check before calling"
        )
    children: list[dict[str, Any]] = []
    for f in filters:
        entry = build_filter_entry(f)
        # Add propertyName — flow filters only support string property names
        prop = f._property
        if isinstance(prop, str):
            entry["propertyName"] = prop
        else:
            raise TypeError(
                f"build_flow_property_filter only supports string property "
                f"filters; got {type(prop).__name__} — custom property refs "
                f"are not supported in flow filters"
            )
        # Remove the "value" key since flow filters use propertyName instead
        entry.pop("value", None)
        # Remove defaultType — flow filters don't use it
        entry.pop("defaultType", None)
        children.append(entry)

    return {
        "operator": "and",
        "children": children,
    }


def build_flow_cohort_filter(
    where: Filter | list[Filter],
) -> dict[str, Any] | None:
    """Build the ``filter_by_cohort`` dict for flow bookmark params.

    Flows use a legacy ``filter_by_cohort`` top-level key rather than
    the ``sections.filter`` array used by insights/funnels/retention.
    Only cohort filters (``Filter.in_cohort`` / ``Filter.not_in_cohort``)
    are accepted; non-cohort filters raise ``ValueError``.

    Args:
        where: A single cohort ``Filter`` or list of cohort ``Filter``
            objects. Only the first cohort filter is used (flows
            support a single cohort filter).

    Returns:
        Dict with cohort filter structure for the ``filter_by_cohort``
        key, or ``None`` if ``where`` is empty.

    Raises:
        ValueError: If any filter is not a cohort filter
            (``_property != "$cohorts"``).

    Example:
        ```python
        fbc = build_flow_cohort_filter(Filter.in_cohort(123, "PU"))
        # {"id": 123, "name": "PU", "negated": False}
        ```
    """
    filters = where if isinstance(where, list) else [where]
    if not filters:
        return None

    for f in filters:
        if f._property != "$cohorts":
            raise ValueError(
                "build_flow_cohort_filter only accepts cohort filters "
                "(Filter.in_cohort/not_in_cohort); property filters should "
                "use build_flow_property_filter instead"
            )

    if len(filters) > 1:
        raise ValueError(
            f"query_flow supports a single cohort filter, but {len(filters)} "
            "were provided. Pass only one Filter.in_cohort/not_in_cohort."
        )

    f = filters[0]
    # Extract from the _value structure: [{"cohort": {...}}]
    cohort_value = f._value
    if not isinstance(cohort_value, list) or len(cohort_value) == 0:
        raise ValueError(
            "Internal error: cohort filter _value must be a non-empty list; "
            f"got {type(cohort_value).__name__}. This indicates a bug in "
            "Filter._build_cohort_filter."
        )
    first_item = cohort_value[0]
    if not isinstance(first_item, dict):
        raise ValueError(
            "Internal error: cohort filter _value[0] is not a dict; "
            f"got {type(first_item).__name__}. This indicates a bug in "
            "Filter._build_cohort_filter."
        )
    cohort_data = first_item.get("cohort")
    if not isinstance(cohort_data, dict):
        raise ValueError(
            "Internal error: cohort filter _value[0] is missing 'cohort' key; "
            f"got keys {list(first_item.keys())}. This indicates a bug in "
            "Filter._build_cohort_filter."
        )
    result: dict[str, Any] = {
        "name": cohort_data.get("name", ""),
        "negated": f._operator == "does not contain",
    }
    if "id" in cohort_data:
        result["id"] = cohort_data["id"]
    if "raw_cohort" in cohort_data:
        result["raw_cohort"] = cohort_data["raw_cohort"]
    return result


def build_frequency_group_entry(
    fb: FrequencyBreakdown,
    *,
    data_group_id: int | None = None,
) -> dict[str, Any]:
    """Build a single frequency group entry for sections.group[].

    Produces the frequency-specific group dict matching the Mixpanel
    bookmark API format with ``behaviorType`` inside the ``behavior``
    sub-dict, ``event`` as a ``{label, value}`` object, and bucket
    configuration in a ``customBucket`` object with camelCase keys.

    Args:
        fb: FrequencyBreakdown specification.
        data_group_id: Optional data group ID for group-level analytics.

    Returns:
        Group entry dict matching the Mixpanel bookmark API schema:
        ``dataset``, ``behavior`` (with ``behaviorType``, ``event``
        object, ``aggregationOperator``, ``filters``,
        ``filtersOperator``, ``dateRange``), ``value`` (display
        label), ``resourceType``, ``propertyType``, ``dataGroupId``,
        and ``customBucket`` (with ``bucketSize``, ``min``, ``max``,
        ``disabled``).

    Example:
        ```python
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_group_entry,
        )
        from mixpanel_headless.types import FrequencyBreakdown

        entry = build_frequency_group_entry(FrequencyBreakdown("Purchase"))
        # {"dataset": "$mixpanel", "resourceType": "people",
        #  "behavior": {"behaviorType": "$frequency",
        #               "event": {"label": "Purchase", "value": "Purchase"},
        #               ...},
        #  "customBucket": {"bucketSize": 1, "min": 0, "max": 10, ...}}
        ```
    """
    display_label = fb.label if fb.label is not None else f"{fb.event} Frequency"
    entry: dict[str, Any] = {
        "dataset": "$mixpanel",
        "behavior": {
            "aggregationOperator": "total",
            "event": {"label": fb.event, "value": fb.event},
            "behaviorType": "$frequency",
            "filters": [],
            "filtersOperator": "and",
            "dateRange": None,
        },
        "value": display_label,
        "resourceType": "people",
        "propertyType": "number",
        "dataGroupId": data_group_id,
        "customBucket": {
            "bucketSize": fb.bucket_size,
            "min": fb.bucket_min,
            "max": fb.bucket_max,
            "disabled": False,
        },
    }
    return entry


def build_frequency_filter_entry(ff: FrequencyFilter) -> dict[str, Any]:
    """Build a single frequency filter entry for sections.filter[].

    Produces the frequency-specific filter dict with ``behaviorType``
    set to ``"$frequency"`` and ``resourceType`` set to ``"people"``.

    Args:
        ff: FrequencyFilter specification.

    Returns:
        Filter entry dict with ``customProperty.behavior`` sub-dict
        containing the frequency event, operator, and threshold.
        Optionally includes ``dateRange`` and ``eventFilters``.

    Example:
        ```python
        from mixpanel_headless._internal.bookmark_builders import (
            build_frequency_filter_entry,
        )
        from mixpanel_headless.types import FrequencyFilter

        entry = build_frequency_filter_entry(
            FrequencyFilter("Login", value=5)
        )
        # {"resourceType": "people", "behaviorType": "$frequency",
        #  "customProperty": {"behavior": {"event": "Login", ...}}}
        ```
    """
    behavior: dict[str, Any] = {
        "event": ff.event,
        "aggregation": "total",
        "filterOperator": ff.operator,
        "filterValue": ff.value,
    }
    if ff.date_range_value is not None and ff.date_range_unit is not None:
        behavior["dateRange"] = {
            "value": ff.date_range_value,
            "unit": ff.date_range_unit,
        }
    if ff.event_filters is not None:
        behavior["eventFilters"] = [build_filter_entry(f) for f in ff.event_filters]
    entry: dict[str, Any] = {
        "resourceType": "people",
        "behaviorType": "$frequency",
        "customProperty": {
            "behavior": behavior,
        },
    }
    if ff.label is not None:
        entry["label"] = ff.label
    return entry


def build_time_comparison(tc: TimeComparison) -> dict[str, str]:
    """Build the ``timeComparison`` dict for ``displayOptions``.

    Converts a ``TimeComparison`` dataclass into the JSON dict format
    expected by the Mixpanel bookmark API inside
    ``displayOptions.timeComparison``.

    The output format is ``{"type": <type>, "value": <unit_or_date>}``:

    - For ``type="relative"``: value is the comparison unit
      (day, week, month, quarter, year).
    - For ``type="absolute-start"`` or ``"absolute-end"``: value is
      the ISO date string (YYYY-MM-DD).

    Args:
        tc: A validated ``TimeComparison`` dataclass instance.

    Returns:
        Dict with ``type`` and ``value`` keys, both strings.

    Example:
        ```python
        from mixpanel_headless._internal.bookmark_builders import (
            build_time_comparison,
        )
        from mixpanel_headless.types import TimeComparison

        result = build_time_comparison(TimeComparison.relative("month"))
        # {"type": "relative", "value": "month"}
        ```
    """
    value: str
    if tc.type == "relative":
        # tc.unit guaranteed non-None by __post_init__ TC1
        if tc.unit is None:  # pragma: no cover — guarded by TC1
            raise AssertionError(
                "unreachable: TC1 guarantees unit when type='relative'"
            )
        value = tc.unit
    else:
        # tc.date guaranteed non-None by __post_init__ TC2
        if tc.date is None:  # pragma: no cover — guarded by TC2
            raise AssertionError(
                "unreachable: TC2 guarantees date when type='absolute-*'"
            )
        value = tc.date
    return {"type": tc.type, "value": value}
