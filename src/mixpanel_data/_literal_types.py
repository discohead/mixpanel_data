"""Shared Literal type aliases for parameter validation.

These types are exported from the public API and can be used by
library consumers for their own type hints.

Example:
    from mixpanel_data import TimeUnit, Workspace

    def my_query(ws: Workspace, unit: TimeUnit) -> None:
        result = ws.segmentation(
            "event", from_date="2024-01-01", to_date="2024-01-31", unit=unit
        )
"""

from __future__ import annotations

from typing import Literal

# Time units for segmentation, retention, event_counts, property_counts, frequency
TimeUnit = Literal["day", "week", "month"]

# Time units for numeric aggregations (segmentation_numeric, sum, average)
HourDayUnit = Literal["hour", "day"]

# Count/aggregation methods
CountType = Literal["general", "unique", "average"]

# Table types for filtering (events vs profiles)
TableType = Literal["events", "profiles"]

__all__ = ["TimeUnit", "HourDayUnit", "CountType", "TableType"]
