# Quickstart: Phase 1 — Shared Infrastructure Extraction

**Date**: 2026-04-05
**Audience**: Library developers building Phases 2-4 (funnels, retention, flows)

## Using the Extracted Builders

### Time Section (for insights, funnels, retention)

```python
from mixpanel_data._internal.bookmark_builders import (
    build_time_section,
    build_filter_section,
    build_group_section,
)

# Relative date range (default)
time = build_time_section(from_date=None, to_date=None, last=30, unit="day")
# [{"dateRangeType": "in the last", "unit": "day", "window": {"unit": "day", "value": 30}}]

# Absolute date range
time = build_time_section(from_date="2026-01-01", to_date="2026-01-31", last=30, unit="day")
# [{"dateRangeType": "between", "unit": "day", "value": ["2026-01-01", "2026-01-31"]}]

# From-date only (through today)
time = build_time_section(from_date="2026-01-01", to_date=None, last=30, unit="week")
# [{"dateRangeType": "between", "unit": "week", "value": ["2026-01-01", "2026-04-05"]}]
```

### Date Range (for flows)

```python
from mixpanel_data._internal.bookmark_builders import build_date_range

# Relative
dr = build_date_range(from_date=None, to_date=None, last=30)
# {"type": "in the last", "from_date": {"unit": "day", "value": 30}, "to_date": "$now"}

# Absolute
dr = build_date_range(from_date="2026-01-01", to_date="2026-01-31", last=30)
# {"type": "between", "from_date": "2026-01-01", "to_date": "2026-01-31"}
```

### Filter Section

```python
from mixpanel_data.types import Filter

# Build sections.filter[] from Filter objects
filters = build_filter_section(where=[
    Filter.equals("country", "US"),
    Filter.greater_than("amount", 50),
])
# [{"resourceType": "events", "filterType": "string", ...}, {...}]

# Single filter
filters = build_filter_section(where=Filter.equals("platform", "iOS"))

# No filters
filters = build_filter_section(where=None)
# []
```

### Group Section

```python
from mixpanel_data.types import GroupBy

# Simple string group-by
groups = build_group_section(group_by="country")
# [{"value": "country", "propertyName": "country", "resourceType": "events", ...}]

# Typed GroupBy with bucketing
groups = build_group_section(group_by=GroupBy("amount", property_type="number",
                                              bucket_size=10, bucket_min=0, bucket_max=100))

# Multiple group-bys
groups = build_group_section(group_by=["country", "platform"])
```

## Using the Segfilter Converter (for flows)

```python
from mixpanel_data._internal.segfilter import build_segfilter_entry
from mixpanel_data.types import Filter

# String equals
sf = build_segfilter_entry(Filter.equals("country", "US"))
# {
#     "property": {"name": "country", "source": "properties", "type": "string"},
#     "type": "string",
#     "selected_property_type": "string",
#     "filter": {"operator": "==", "operand": ["US"]},
# }

# Number comparison (note stringified operand)
sf = build_segfilter_entry(Filter.greater_than("amount", 50))
# {
#     "property": {"name": "amount", "source": "properties", "type": "number"},
#     "type": "number",
#     "selected_property_type": "number",
#     "filter": {"operator": ">", "operand": "50"},
# }

# Boolean
sf = build_segfilter_entry(Filter.is_true("verified"))
# {
#     "property": {"name": "verified", "source": "properties", "type": "boolean"},
#     "type": "boolean",
#     "selected_property_type": "boolean",
#     "filter": {"operand": "true"},
# }
```

## Using the Extracted Validators

```python
from mixpanel_data._internal.validation import (
    validate_time_args,
    validate_group_by_args,
)

# Time validation — returns list[ValidationError]
errors = validate_time_args(from_date="2026-02-01", to_date="2026-01-01", last=30)
# [ValidationError(code="V15_DATE_ORDER", ...)]

errors = validate_time_args(from_date=None, to_date=None, last=-1)
# [ValidationError(code="V7_LAST_POSITIVE", ...)]

# Group-by validation
errors = validate_group_by_args(group_by=GroupBy("x", property_type="string", bucket_size=10))
# [ValidationError(code="V12B_BUCKET_REQUIRES_NUMBER", ...)]
```

## Building a New Report Type (Phase 2-4 Pattern)

```python
def _build_funnel_params(self, *, steps, from_date, to_date, last, unit, group_by, where, ...):
    # Reuse shared builders
    time_section = build_time_section(from_date=from_date, to_date=to_date, last=last, unit=unit)
    filter_section = build_filter_section(where=where)
    group_section = build_group_section(group_by=group_by)

    # Build funnel-specific show section
    show = [self._build_funnel_behavior(steps, ...)]

    return {
        "sections": {
            "show": show,
            "time": time_section,
            "filter": filter_section,
            "group": group_section,
        },
        "displayOptions": {"chartType": "funnel-steps"},
    }

def validate_funnel_args(self, *, steps, from_date, to_date, last, group_by, ...):
    errors = []
    # Reuse shared validators
    errors.extend(validate_time_args(from_date=from_date, to_date=to_date, last=last))
    errors.extend(validate_group_by_args(group_by=group_by))
    # Add funnel-specific rules (F1-F6)
    if len(steps) < 2:
        errors.append(ValidationError(code="F1_MIN_STEPS", ...))
    return errors
```

## New Enum Constants

```python
from mixpanel_data._internal.bookmark_enums import (
    VALID_FUNNEL_ORDER,            # {"loose", "any"}
    VALID_CONVERSION_WINDOW_UNITS, # {"second", "minute", "hour", "day", "week", "month", "session"}
    VALID_RETENTION_UNITS,         # {"day", "week", "month"}
    VALID_RETENTION_ALIGNMENT,     # {"birth", "interval_start"}
    VALID_FLOWS_COUNT_TYPES,       # {"unique", "total", "session"}
    VALID_FLOWS_CHART_TYPES,       # {"sankey", "top-paths"}
    VALID_MATH_FUNNELS,            # Extended with property aggregation types
)
```
