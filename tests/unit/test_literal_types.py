"""Tests for public type alias exports."""

from __future__ import annotations

from typing import get_args


def test_type_aliases_exported_from_public_api() -> None:
    """Type aliases should be importable from mixpanel_headless."""
    from mixpanel_headless import CountType, HourDayUnit, TimeUnit

    # Verify they are the correct types
    assert get_args(TimeUnit) == ("day", "week", "month")
    assert get_args(HourDayUnit) == ("hour", "day")
    assert get_args(CountType) == ("general", "unique", "average")


def test_time_unit_alias() -> None:
    """TimeUnit should be Literal['day', 'week', 'month']."""
    from mixpanel_headless import TimeUnit

    assert get_args(TimeUnit) == ("day", "week", "month")


def test_hour_day_unit_alias() -> None:
    """HourDayUnit should be Literal['hour', 'day']."""
    from mixpanel_headless import HourDayUnit

    assert get_args(HourDayUnit) == ("hour", "day")


def test_count_type_alias() -> None:
    """CountType should be Literal['general', 'unique', 'average']."""
    from mixpanel_headless import CountType

    assert get_args(CountType) == ("general", "unique", "average")
