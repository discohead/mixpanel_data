# ruff: noqa: ARG001
"""Property-based tests for Phase 028 Schema Governance types.

These tests verify invariants that should hold for all possible inputs
for the governance Pydantic models introduced in Phase 028.

Properties tested:
- AuditResponse serialization round-trip via model_dump / model_validate
- AuditResponse alias round-trip via model_dump(by_alias=True) / model_validate
- AuditResponse frozen immutability
- AuditResponse extra field preservation
- AuditViolation serialization round-trip
- AuditViolation alias round-trip
- AuditViolation frozen immutability
- AuditViolation extra field preservation
- SchemaEnforcementConfig serialization round-trip
- SchemaEnforcementConfig alias round-trip
- SchemaEnforcementConfig frozen immutability
- SchemaEnforcementConfig extra field preservation
- DataVolumeAnomaly serialization round-trip
- DataVolumeAnomaly alias round-trip
- DataVolumeAnomaly frozen immutability
- DataVolumeAnomaly extra field preservation
- EventDeletionRequest serialization round-trip
- EventDeletionRequest alias round-trip
- EventDeletionRequest frozen immutability
- EventDeletionRequest extra field preservation

Usage:
    pytest tests/unit/test_types_governance_pbt.py
    HYPOTHESIS_PROFILE=dev pytest tests/unit/test_types_governance_pbt.py
    HYPOTHESIS_PROFILE=ci pytest tests/unit/test_types_governance_pbt.py
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_headless.types import (
    AuditResponse,
    AuditViolation,
    DataVolumeAnomaly,
    EventDeletionRequest,
    SchemaEnforcementConfig,
)

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for non-empty printable strings (names, keys, etc.)
_non_empty_text = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

# Strategy for optional non-empty strings
_optional_text = st.none() | _non_empty_text

# Strategy for positive integers (IDs)
_positive_ints = st.integers(min_value=1, max_value=10000)

# Strategy for optional positive ints
_optional_positive_ints = st.none() | _positive_ints

# Strategy for optional booleans
_optional_bools = st.none() | st.booleans()

# Strategy for ISO 8601 timestamps
_timestamps = st.datetimes().map(lambda dt: dt.isoformat() + "Z")

# Strategy for optional timestamps
_optional_timestamps = st.none() | _timestamps

# Strategy for simple string-keyed dicts (requesting_user, etc.)
_string_dicts = st.dictionaries(
    _non_empty_text,
    _non_empty_text,
    min_size=1,
    max_size=5,
)

# Strategy for optional string-keyed dicts
_optional_string_dicts = st.none() | _string_dicts

# Strategy for optional lists of dicts (events, properties rules)
_optional_dict_lists = st.none() | st.lists(
    st.fixed_dictionaries({"key": _non_empty_text, "value": _non_empty_text}),
    min_size=0,
    max_size=3,
)

# Strategy for optional string lists (notification_emails)
_optional_string_lists = st.none() | st.lists(_non_empty_text, min_size=0, max_size=3)

# Strategy for extra fields (unknown kwargs that models with extra="allow" accept)
_extra_fields = st.dictionaries(
    st.text(
        alphabet=st.characters(categories=["L"]),
        min_size=3,
        max_size=10,
    ).map(lambda s: f"xtra_{s}"),
    _non_empty_text,
    min_size=1,
    max_size=3,
)


# =============================================================================
# AuditViolation Property Tests
# =============================================================================


class TestAuditViolationProperties:
    """Property-based tests for AuditViolation Pydantic model."""

    @given(
        violation=_non_empty_text,
        name=_non_empty_text,
        platform=_optional_text,
        version=_optional_text,
        count=st.integers(),
        event=_optional_text,
        sensitive=_optional_bools,
        property_type_error=_optional_text,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        violation: str,
        name: str,
        platform: str | None,
        version: str | None,
        count: int,
        event: str | None,
        sensitive: bool | None,
        property_type_error: str | None,
    ) -> None:
        """AuditViolation survives model_dump / model_validate round-trip.

        Args:
            violation: Violation type.
            name: Property or event name.
            platform: Optional platform.
            version: Optional version string.
            count: Number of occurrences.
            event: Optional event name.
            sensitive: Optional sensitive flag.
            property_type_error: Optional type mismatch description.
        """
        obj = AuditViolation(
            violation=violation,
            name=name,
            platform=platform,
            version=version,
            count=count,
            event=event,
            sensitive=sensitive,
            property_type_error=property_type_error,
        )
        data = obj.model_dump()
        restored = AuditViolation.model_validate(data)
        assert restored == obj

    @given(
        violation=_non_empty_text,
        name=_non_empty_text,
        count=st.integers(),
    )
    @settings(max_examples=50)
    def test_alias_round_trip(
        self,
        violation: str,
        name: str,
        count: int,
    ) -> None:
        """AuditViolation round-trips through model_dump(by_alias=True).

        Args:
            violation: Violation type.
            name: Property or event name.
            count: Number of occurrences.
        """
        obj = AuditViolation(
            violation=violation,
            name=name,
            count=count,
            property_type_error="mismatch",
        )
        data = obj.model_dump(by_alias=True)
        restored = AuditViolation.model_validate(data)
        assert restored == obj

    @given(violation=_non_empty_text, name=_non_empty_text, count=st.integers())
    @settings(max_examples=50)
    def test_frozen_immutability(self, violation: str, name: str, count: int) -> None:
        """AuditViolation instances are immutable (frozen=True).

        Args:
            violation: Violation type.
            name: Property or event name.
            count: Number of occurrences.
        """
        obj = AuditViolation(violation=violation, name=name, count=count)
        with pytest.raises(Exception):  # noqa: B017
            obj.name = "mutated"  # type: ignore[misc]

    @given(
        violation=_non_empty_text,
        name=_non_empty_text,
        count=st.integers(),
        extras=_extra_fields,
    )
    @settings(max_examples=50)
    def test_extra_field_preservation(
        self,
        violation: str,
        name: str,
        count: int,
        extras: dict[str, str],
    ) -> None:
        """AuditViolation preserves unknown extra fields (extra='allow').

        Args:
            violation: Violation type.
            name: Property or event name.
            count: Number of occurrences.
            extras: Extra keyword arguments.
        """
        obj = AuditViolation(violation=violation, name=name, count=count, **extras)
        dumped = obj.model_dump()
        for key, value in extras.items():
            assert dumped[key] == value


# =============================================================================
# AuditResponse Property Tests
# =============================================================================


class TestAuditResponseProperties:
    """Property-based tests for AuditResponse Pydantic model."""

    @given(
        computed_at=_non_empty_text,
        violation_count=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        computed_at: str,
        violation_count: int,
    ) -> None:
        """AuditResponse survives model_dump / model_validate round-trip.

        Args:
            computed_at: Timestamp of audit computation.
            violation_count: Number of violations to generate.
        """
        violations = [
            AuditViolation(violation=f"v{i}", name=f"n{i}", count=i)
            for i in range(violation_count)
        ]
        obj = AuditResponse(violations=violations, computed_at=computed_at)
        data = obj.model_dump()
        restored = AuditResponse.model_validate(data)
        assert restored == obj

    @given(computed_at=_non_empty_text)
    @settings(max_examples=50)
    def test_alias_round_trip(self, computed_at: str) -> None:
        """AuditResponse round-trips through model_dump(by_alias=True).

        Args:
            computed_at: Timestamp of audit computation.
        """
        obj = AuditResponse(
            violations=[AuditViolation(violation="test", name="ev", count=1)],
            computed_at=computed_at,
        )
        data = obj.model_dump(by_alias=True)
        restored = AuditResponse.model_validate(data)
        assert restored == obj

    @given(computed_at=_non_empty_text)
    @settings(max_examples=50)
    def test_frozen_immutability(self, computed_at: str) -> None:
        """AuditResponse instances are immutable (frozen=True).

        Args:
            computed_at: Timestamp of audit computation.
        """
        obj = AuditResponse(violations=[], computed_at=computed_at)
        with pytest.raises(Exception):  # noqa: B017
            obj.computed_at = "mutated"  # type: ignore[misc]

    @given(computed_at=_non_empty_text, extras=_extra_fields)
    @settings(max_examples=50)
    def test_extra_field_preservation(
        self, computed_at: str, extras: dict[str, str]
    ) -> None:
        """AuditResponse preserves unknown extra fields (extra='allow').

        Args:
            computed_at: Timestamp of audit computation.
            extras: Extra keyword arguments.
        """
        obj = AuditResponse(violations=[], computed_at=computed_at, **extras)
        dumped = obj.model_dump()
        for key, value in extras.items():
            assert dumped[key] == value


# =============================================================================
# SchemaEnforcementConfig Property Tests
# =============================================================================


class TestSchemaEnforcementConfigProperties:
    """Property-based tests for SchemaEnforcementConfig Pydantic model."""

    @given(
        id=_optional_positive_ints,
        rule_event=_optional_text,
        state=_optional_text,
        last_modified=_optional_text,
        initialized_from=_optional_text,
        initialized_to=_optional_text,
        notification_emails=_optional_string_lists,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        id: int | None,
        rule_event: str | None,
        state: str | None,
        last_modified: str | None,
        initialized_from: str | None,
        initialized_to: str | None,
        notification_emails: list[str] | None,
    ) -> None:
        """SchemaEnforcementConfig survives model_dump / model_validate round-trip.

        Args:
            id: Optional config ID.
            rule_event: Optional enforcement action.
            state: Optional enforcement state.
            last_modified: Optional modification timestamp.
            initialized_from: Optional initialization start.
            initialized_to: Optional initialization end.
            notification_emails: Optional notification recipients.
        """
        obj = SchemaEnforcementConfig(
            id=id,
            rule_event=rule_event,
            state=state,
            last_modified=last_modified,
            initialized_from=initialized_from,
            initialized_to=initialized_to,
            notification_emails=notification_emails,
        )
        data = obj.model_dump()
        restored = SchemaEnforcementConfig.model_validate(data)
        assert restored == obj

    @given(
        id=_optional_positive_ints,
        rule_event=_optional_text,
        state=_optional_text,
    )
    @settings(max_examples=50)
    def test_alias_round_trip(
        self,
        id: int | None,
        rule_event: str | None,
        state: str | None,
    ) -> None:
        """SchemaEnforcementConfig round-trips through model_dump(by_alias=True).

        Args:
            id: Optional config ID.
            rule_event: Optional enforcement action.
            state: Optional enforcement state.
        """
        obj = SchemaEnforcementConfig(id=id, rule_event=rule_event, state=state)
        data = obj.model_dump(by_alias=True)
        restored = SchemaEnforcementConfig.model_validate(data)
        assert restored == obj

    @given(id=_optional_positive_ints)
    @settings(max_examples=50)
    def test_frozen_immutability(self, id: int | None) -> None:
        """SchemaEnforcementConfig instances are immutable (frozen=True).

        Args:
            id: Optional config ID.
        """
        obj = SchemaEnforcementConfig(id=id)
        with pytest.raises(Exception):  # noqa: B017
            obj.state = "mutated"  # type: ignore[misc]

    @given(extras=_extra_fields)
    @settings(max_examples=50)
    def test_extra_field_preservation(self, extras: dict[str, str]) -> None:
        """SchemaEnforcementConfig preserves unknown extra fields (extra='allow').

        Args:
            extras: Extra keyword arguments.
        """
        obj = SchemaEnforcementConfig(**extras)
        dumped = obj.model_dump()
        for key, value in extras.items():
            assert dumped[key] == value


# =============================================================================
# DataVolumeAnomaly Property Tests
# =============================================================================


class TestDataVolumeAnomalyProperties:
    """Property-based tests for DataVolumeAnomaly Pydantic model."""

    @given(
        id=st.integers(),
        actual_count=st.integers(),
        predicted_upper=st.integers(),
        predicted_lower=st.integers(),
        percent_variance=_non_empty_text,
        status=_non_empty_text,
        project=st.integers(),
        anomaly_class=_non_empty_text,
        timestamp=_optional_text,
        event=_optional_positive_ints,
        event_name=_optional_text,
        property_id=_optional_positive_ints,
        property_name=_optional_text,
        metric=_optional_positive_ints,
        metric_name=_optional_text,
        metric_type=_optional_text,
        primary_type=_optional_text,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        id: int,
        actual_count: int,
        predicted_upper: int,
        predicted_lower: int,
        percent_variance: str,
        status: str,
        project: int,
        anomaly_class: str,
        timestamp: str | None,
        event: int | None,
        event_name: str | None,
        property_id: int | None,
        property_name: str | None,
        metric: int | None,
        metric_name: str | None,
        metric_type: str | None,
        primary_type: str | None,
    ) -> None:
        """DataVolumeAnomaly survives model_dump / model_validate round-trip.

        Args:
            id: Anomaly ID.
            actual_count: Actual observed count.
            predicted_upper: Upper bound of prediction.
            predicted_lower: Lower bound of prediction.
            percent_variance: Variance percentage.
            status: Anomaly status.
            project: Project ID.
            anomaly_class: Anomaly class.
            timestamp: Optional detection timestamp.
            event: Optional event ID.
            event_name: Optional event name.
            property_id: Optional property ID.
            property_name: Optional property name.
            metric: Optional metric ID.
            metric_name: Optional metric name.
            metric_type: Optional metric type.
            primary_type: Optional primary anomaly type.
        """
        kwargs: dict[str, Any] = {
            "id": id,
            "actual_count": actual_count,
            "predicted_upper": predicted_upper,
            "predicted_lower": predicted_lower,
            "percent_variance": percent_variance,
            "status": status,
            "project": project,
            "anomaly_class": anomaly_class,
            "timestamp": timestamp,
            "event": event,
            "event_name": event_name,
            "property_name": property_name,
            "metric": metric,
            "metric_name": metric_name,
            "metric_type": metric_type,
            "primary_type": primary_type,
        }
        # "property" is a Python builtin but valid as a Pydantic field name
        kwargs["property"] = property_id
        obj = DataVolumeAnomaly(**kwargs)
        data = obj.model_dump()
        restored = DataVolumeAnomaly.model_validate(data)
        assert restored == obj

    @given(
        id=st.integers(),
        actual_count=st.integers(),
        predicted_upper=st.integers(),
        predicted_lower=st.integers(),
        percent_variance=_non_empty_text,
        status=_non_empty_text,
        project=st.integers(),
        anomaly_class=_non_empty_text,
    )
    @settings(max_examples=50)
    def test_alias_round_trip(
        self,
        id: int,
        actual_count: int,
        predicted_upper: int,
        predicted_lower: int,
        percent_variance: str,
        status: str,
        project: int,
        anomaly_class: str,
    ) -> None:
        """DataVolumeAnomaly round-trips through model_dump(by_alias=True).

        Args:
            id: Anomaly ID.
            actual_count: Actual observed count.
            predicted_upper: Upper bound of prediction.
            predicted_lower: Lower bound of prediction.
            percent_variance: Variance percentage.
            status: Anomaly status.
            project: Project ID.
            anomaly_class: Anomaly class.
        """
        obj = DataVolumeAnomaly(
            id=id,
            actual_count=actual_count,
            predicted_upper=predicted_upper,
            predicted_lower=predicted_lower,
            percent_variance=percent_variance,
            status=status,
            project=project,
            anomaly_class=anomaly_class,
        )
        data = obj.model_dump(by_alias=True)
        restored = DataVolumeAnomaly.model_validate(data)
        assert restored == obj

    @given(
        id=st.integers(),
        actual_count=st.integers(),
        predicted_upper=st.integers(),
        predicted_lower=st.integers(),
        percent_variance=_non_empty_text,
        status=_non_empty_text,
        project=st.integers(),
        anomaly_class=_non_empty_text,
    )
    @settings(max_examples=50)
    def test_frozen_immutability(
        self,
        id: int,
        actual_count: int,
        predicted_upper: int,
        predicted_lower: int,
        percent_variance: str,
        status: str,
        project: int,
        anomaly_class: str,
    ) -> None:
        """DataVolumeAnomaly instances are immutable (frozen=True).

        Args:
            id: Anomaly ID.
            actual_count: Actual observed count.
            predicted_upper: Upper bound of prediction.
            predicted_lower: Lower bound of prediction.
            percent_variance: Variance percentage.
            status: Anomaly status.
            project: Project ID.
            anomaly_class: Anomaly class.
        """
        obj = DataVolumeAnomaly(
            id=id,
            actual_count=actual_count,
            predicted_upper=predicted_upper,
            predicted_lower=predicted_lower,
            percent_variance=percent_variance,
            status=status,
            project=project,
            anomaly_class=anomaly_class,
        )
        with pytest.raises(Exception):  # noqa: B017
            obj.status = "mutated"  # type: ignore[misc]

    @given(
        id=st.integers(),
        actual_count=st.integers(),
        predicted_upper=st.integers(),
        predicted_lower=st.integers(),
        percent_variance=_non_empty_text,
        status=_non_empty_text,
        project=st.integers(),
        anomaly_class=_non_empty_text,
        extras=_extra_fields,
    )
    @settings(max_examples=50)
    def test_extra_field_preservation(
        self,
        id: int,
        actual_count: int,
        predicted_upper: int,
        predicted_lower: int,
        percent_variance: str,
        status: str,
        project: int,
        anomaly_class: str,
        extras: dict[str, str],
    ) -> None:
        """DataVolumeAnomaly preserves unknown extra fields (extra='allow').

        Args:
            id: Anomaly ID.
            actual_count: Actual observed count.
            predicted_upper: Upper bound of prediction.
            predicted_lower: Lower bound of prediction.
            percent_variance: Variance percentage.
            status: Anomaly status.
            project: Project ID.
            anomaly_class: Anomaly class.
            extras: Extra keyword arguments.
        """
        obj = DataVolumeAnomaly(
            id=id,
            actual_count=actual_count,
            predicted_upper=predicted_upper,
            predicted_lower=predicted_lower,
            percent_variance=percent_variance,
            status=status,
            project=project,
            anomaly_class=anomaly_class,
            **extras,
        )
        dumped = obj.model_dump()
        for key, value in extras.items():
            assert dumped[key] == value


# =============================================================================
# EventDeletionRequest Property Tests
# =============================================================================


class TestEventDeletionRequestProperties:
    """Property-based tests for EventDeletionRequest Pydantic model."""

    @given(
        id=st.integers(),
        event_name=_non_empty_text,
        from_date=_non_empty_text,
        to_date=_non_empty_text,
        status=_non_empty_text,
        deleted_events_count=st.integers(),
        created=_non_empty_text,
        requesting_user=_string_dicts,
        display_name=_optional_text,
        filters=_optional_string_dicts,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        id: int,
        event_name: str,
        from_date: str,
        to_date: str,
        status: str,
        deleted_events_count: int,
        created: str,
        requesting_user: dict[str, Any],
        display_name: str | None,
        filters: dict[str, Any] | None,
    ) -> None:
        """EventDeletionRequest survives model_dump / model_validate round-trip.

        Args:
            id: Request ID.
            event_name: Event to delete.
            from_date: Start date.
            to_date: End date.
            status: Request status.
            deleted_events_count: Count of deleted events.
            created: Creation timestamp.
            requesting_user: User who requested.
            display_name: Optional display name.
            filters: Optional deletion filters.
        """
        obj = EventDeletionRequest(
            id=id,
            event_name=event_name,
            from_date=from_date,
            to_date=to_date,
            status=status,
            deleted_events_count=deleted_events_count,
            created=created,
            requesting_user=requesting_user,
            display_name=display_name,
            filters=filters,
        )
        data = obj.model_dump()
        restored = EventDeletionRequest.model_validate(data)
        assert restored == obj

    @given(
        id=st.integers(),
        event_name=_non_empty_text,
        from_date=_non_empty_text,
        to_date=_non_empty_text,
        status=_non_empty_text,
        deleted_events_count=st.integers(),
        created=_non_empty_text,
        requesting_user=_string_dicts,
    )
    @settings(max_examples=50)
    def test_alias_round_trip(
        self,
        id: int,
        event_name: str,
        from_date: str,
        to_date: str,
        status: str,
        deleted_events_count: int,
        created: str,
        requesting_user: dict[str, Any],
    ) -> None:
        """EventDeletionRequest round-trips through model_dump(by_alias=True).

        Args:
            id: Request ID.
            event_name: Event to delete.
            from_date: Start date.
            to_date: End date.
            status: Request status.
            deleted_events_count: Count of deleted events.
            created: Creation timestamp.
            requesting_user: User who requested.
        """
        obj = EventDeletionRequest(
            id=id,
            event_name=event_name,
            from_date=from_date,
            to_date=to_date,
            status=status,
            deleted_events_count=deleted_events_count,
            created=created,
            requesting_user=requesting_user,
        )
        data = obj.model_dump(by_alias=True)
        restored = EventDeletionRequest.model_validate(data)
        assert restored == obj

    @given(
        id=st.integers(),
        event_name=_non_empty_text,
        from_date=_non_empty_text,
        to_date=_non_empty_text,
        status=_non_empty_text,
        deleted_events_count=st.integers(),
        created=_non_empty_text,
        requesting_user=_string_dicts,
    )
    @settings(max_examples=50)
    def test_frozen_immutability(
        self,
        id: int,
        event_name: str,
        from_date: str,
        to_date: str,
        status: str,
        deleted_events_count: int,
        created: str,
        requesting_user: dict[str, Any],
    ) -> None:
        """EventDeletionRequest instances are immutable (frozen=True).

        Args:
            id: Request ID.
            event_name: Event to delete.
            from_date: Start date.
            to_date: End date.
            status: Request status.
            deleted_events_count: Count of deleted events.
            created: Creation timestamp.
            requesting_user: User who requested.
        """
        obj = EventDeletionRequest(
            id=id,
            event_name=event_name,
            from_date=from_date,
            to_date=to_date,
            status=status,
            deleted_events_count=deleted_events_count,
            created=created,
            requesting_user=requesting_user,
        )
        with pytest.raises(Exception):  # noqa: B017
            obj.event_name = "mutated"  # type: ignore[misc]

    @given(
        id=st.integers(),
        event_name=_non_empty_text,
        from_date=_non_empty_text,
        to_date=_non_empty_text,
        status=_non_empty_text,
        deleted_events_count=st.integers(),
        created=_non_empty_text,
        requesting_user=_string_dicts,
        extras=_extra_fields,
    )
    @settings(max_examples=50)
    def test_extra_field_preservation(
        self,
        id: int,
        event_name: str,
        from_date: str,
        to_date: str,
        status: str,
        deleted_events_count: int,
        created: str,
        requesting_user: dict[str, Any],
        extras: dict[str, str],
    ) -> None:
        """EventDeletionRequest preserves unknown extra fields (extra='allow').

        Args:
            id: Request ID.
            event_name: Event to delete.
            from_date: Start date.
            to_date: End date.
            status: Request status.
            deleted_events_count: Count of deleted events.
            created: Creation timestamp.
            requesting_user: User who requested.
            extras: Extra keyword arguments.
        """
        obj = EventDeletionRequest(
            id=id,
            event_name=event_name,
            from_date=from_date,
            to_date=to_date,
            status=status,
            deleted_events_count=deleted_events_count,
            created=created,
            requesting_user=requesting_user,
            **extras,
        )
        dumped = obj.model_dump()
        for key, value in extras.items():
            assert dumped[key] == value
