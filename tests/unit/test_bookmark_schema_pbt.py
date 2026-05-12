"""Property-based tests for ``src/mixpanel_headless/_internal/bookmark_schema.py``.

Properties verified:

- **Round-trip soundness**: any valid model dumps and re-validates to the same shape.
- **Idempotence**: validating an already-valid input twice produces the same errors (none).
- **Mutation invariants**: the validator catches every kind of malformation it claims to (missing required field, extra field, wrong literal, wrong type, bad discriminator).
- **Legacy field tolerance**: ``Ignore[T]`` fields named in the canonical
  source are accepted at parse time without surfacing in output.

Hypothesis profile defaults to 100 examples (``just test``); CI uses 200
(``just test-ci``); fast iteration uses 10 (``just test-pbt-dev``).
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError as PydanticValidationError

from mixpanel_headless._internal.bookmark_schema import (
    Behavior,
    BehaviorMeasurement,
    BehaviorShowClause,
    FlowsBookmarkParams,
    FlowsBookmarkStep,
    FormulaShowClause,
    InsightsBookmarkParams,
    InsightsBookmarkSortConfig,
    SortByColumnsConfig,
    SortByValueConfig,
    get_root_model_for_bookmark_type,
    validate_with_pydantic,
)

# =============================================================================
# Strategies
# =============================================================================


def _valid_minimal_insights() -> dict[str, Any]:
    """Return a minimal valid ``InsightsBookmarkParams`` dict."""
    return {
        "displayOptions": {"chartType": "bar"},
        "sections": {
            "show": [
                {
                    "type": "metric",
                    "behavior": {"type": "event", "name": "Login"},
                }
            ],
            "time": [],
        },
    }


def _valid_minimal_flows() -> dict[str, Any]:
    """Return a minimal valid ``FlowsBookmarkParams`` dict."""
    return {
        "steps": [{"event": "Login"}],
        "date_range": {"from_date": "2025-01-01", "to_date": "2025-01-31"},
    }


# Names that are NEVER on any of our schema models — used as inputs for the
# extra-field rejection invariant. Excludes anything in any model's field
# set or any documented ``Ignore[T]`` legacy field.
_KNOWN_FIELDS = frozenset(
    # Combine all known field names from the schema models
    set(InsightsBookmarkParams.model_fields.keys())
    | set(Behavior.model_fields.keys())
    | set(BehaviorShowClause.model_fields.keys())
    | set(FormulaShowClause.model_fields.keys())
    | set(BehaviorMeasurement.model_fields.keys())
    | set(SortByColumnsConfig.model_fields.keys())
    | set(SortByValueConfig.model_fields.keys())
    | set(InsightsBookmarkSortConfig.model_fields.keys())
    | set(FlowsBookmarkParams.model_fields.keys())
    | set(FlowsBookmarkStep.model_fields.keys())
    # Pydantic field aliases that may surface
    | {"funnel-steps", "retention-curve", "insights-metric", "_idx", "from", "to"}
    | {"conv-first-step", "conv-prev-step"}
)

# Strategy: short ASCII identifier strings unlikely to collide with real fields.
_safe_extra_field_names = st.text(
    alphabet=st.characters(min_codepoint=ord("a"), max_codepoint=ord("z")),
    min_size=8,
    max_size=20,
).filter(lambda s: s not in _KNOWN_FIELDS and not s.startswith("_"))


# Documented Ignore[T] fields on InsightsBookmarkParams — must be tolerated.
# The value type matches the canonical Ignore[T] declaration: most are
# Ignore[JsonValue] (any JSON-compatible value); a handful have specific
# types (icon=str, id=int, isNewQBEnabled=bool).
_INSIGHTS_LEGACY_FIELDS: list[tuple[str, Any]] = [
    ("alignment", "any-json-value"),
    ("anchor_position", 1),
    ("anchorPosition", 1),
    ("cardinality", 5),
    ("cardinality_threshold", 10),
    ("chart_type", "bar"),
    ("chartType", "bar"),
    ("count_type", "unique"),
    ("date_range", {"from_date": "2025-01-01"}),
    ("error", "some-error"),
    ("exclusions", []),
    ("fields", ["a", "b"]),
    ("filter_by_cohort", 42),
    ("filter_by_event", "Login"),
    ("global_access_type", "public"),
    ("graph_sort_priority", 1),
    ("group_by", []),
    ("hidden_events", []),
    ("icon", "icon-name"),  # Ignore[str]
    ("id", 12345),  # Ignore[int]
    ("isNewQBEnabled", True),  # Ignore[bool]
    ("modified", "2025-01-01"),
    ("segments", []),
    ("smartHub", {}),
    ("steps", []),
    ("title", "old title"),  # Ignore[str]
    ("trend_unit", "day"),
    ("trendType", "linear"),
    ("ttcVizType", "line"),
    ("use_query_sampling", True),
    ("user", "test"),
    ("user_id", 42),
]


# =============================================================================
# Round-trip soundness
# =============================================================================


class TestRoundtripSoundness:
    """A valid input → ``model_validate`` → ``model_dump`` → re-validate
    should produce the same set of errors (none)."""

    @given(name=st.text(min_size=1, max_size=50))
    @settings(max_examples=50)
    def test_insights_minimal_roundtrip_no_errors(self, name: str) -> None:
        """Random ``name`` field values still round-trip cleanly."""
        params = _valid_minimal_insights()
        params["name"] = name
        # First validate
        errs1 = validate_with_pydantic(InsightsBookmarkParams, params)
        assert errs1 == []
        # Round-trip via model_dump
        m = InsightsBookmarkParams.model_validate(params)
        dumped = m.model_dump(by_alias=True, exclude_none=True)
        errs2 = validate_with_pydantic(InsightsBookmarkParams, dumped)
        assert errs2 == []

    @given(
        sort_by=st.sampled_from(["column"]),
    )
    @settings(max_examples=20)
    def test_sort_by_columns_roundtrip(self, sort_by: str) -> None:
        """Valid SortByColumnsConfig dicts round-trip without errors."""
        raw = {"sortBy": sort_by, "colSortAttrs": []}
        errs = validate_with_pydantic(SortByColumnsConfig, raw)
        assert errs == []
        m = SortByColumnsConfig.model_validate(raw)
        dumped = m.model_dump(by_alias=True, exclude_none=True)
        assert dumped["sortBy"] == sort_by

    @given(forward=st.integers(min_value=0, max_value=10))
    @settings(max_examples=20)
    def test_flows_step_roundtrip(self, forward: int) -> None:
        """``FlowsBookmarkStep`` round-trips with arbitrary ``forward`` count."""
        raw: dict[str, Any] = {"event": "Login", "forward": forward}
        m = FlowsBookmarkStep.model_validate(raw)
        dumped = m.model_dump(by_alias=True, exclude_none=True)
        assert dumped["forward"] == forward


# =============================================================================
# Idempotence
# =============================================================================


class TestValidatorIdempotence:
    """``validate_with_pydantic`` on the same input twice yields the same
    result. (Pydantic models are stateless, so this should always hold —
    these tests guard against accidental mutation in our adapter.)"""

    @given(extra_count=st.integers(min_value=0, max_value=5))
    @settings(max_examples=20)
    def test_validator_no_state_leak(self, extra_count: int) -> None:
        """Adding/removing extras across calls doesn't pollute later calls."""
        valid = _valid_minimal_insights()
        # First, validate a valid bookmark.
        assert validate_with_pydantic(InsightsBookmarkParams, valid) == []
        # Then, validate one with extras (should produce errors).
        bad = dict(valid)
        for i in range(extra_count + 1):
            bad[f"definitely_unknown_{i}"] = i
        bad_errs = validate_with_pydantic(InsightsBookmarkParams, bad)
        assert len(bad_errs) >= 1
        # Then re-validate the original valid input — should still pass.
        assert validate_with_pydantic(InsightsBookmarkParams, valid) == []


# =============================================================================
# Mutation invariants
# =============================================================================


class TestExtraFieldRejection:
    """Adding any unknown top-level field to a strict model produces an
    ``S3_UNKNOWN_FIELD`` error (mirrors server ``extra='forbid'``)."""

    @given(field_name=_safe_extra_field_names)
    @settings(max_examples=50)
    def test_unknown_field_on_sections_rejected(self, field_name: str) -> None:
        """Unknown fields on ``Sections`` are rejected."""
        params = _valid_minimal_insights()
        params["sections"][field_name] = "anything"
        errs = validate_with_pydantic(InsightsBookmarkParams, params)
        assert any(e.code == "S3_UNKNOWN_FIELD" and field_name in e.path for e in errs)

    @given(field_name=_safe_extra_field_names)
    @settings(max_examples=50)
    def test_unknown_field_on_behavior_rejected(self, field_name: str) -> None:
        """Unknown fields on ``Behavior`` are rejected."""
        params = _valid_minimal_insights()
        params["sections"]["show"][0]["behavior"][field_name] = 1
        errs = validate_with_pydantic(InsightsBookmarkParams, params)
        assert any(e.code == "S3_UNKNOWN_FIELD" and field_name in e.path for e in errs)

    @given(field_name=_safe_extra_field_names)
    @settings(max_examples=50)
    def test_unknown_field_on_sort_config_rejected(self, field_name: str) -> None:
        """Unknown fields on ``SortByValueConfig`` are rejected."""
        bad = {"sortBy": "value", "colSortAttrs": [], field_name: "x"}
        errs = validate_with_pydantic(SortByValueConfig, bad)
        assert any(e.code == "S3_UNKNOWN_FIELD" and field_name in e.path for e in errs)


class TestRequiredFieldRejection:
    """Removing a required field from a model produces a ``B0_MISSING_FIELD``
    error."""

    @given(
        field_name=st.sampled_from(["displayOptions", "sections"]),
    )
    @settings(max_examples=10)
    def test_missing_required_top_level_field_rejected(self, field_name: str) -> None:
        """Removing a required top-level field is caught."""
        params = _valid_minimal_insights()
        del params[field_name]
        errs = validate_with_pydantic(InsightsBookmarkParams, params)
        assert any(e.code == "B0_MISSING_FIELD" and field_name in e.path for e in errs)

    @given(
        field_name=st.sampled_from(["show", "time"]),
    )
    @settings(max_examples=10)
    def test_missing_required_sections_field_rejected(self, field_name: str) -> None:
        """Removing a required ``sections.*`` field is caught."""
        params = _valid_minimal_insights()
        del params["sections"][field_name]
        errs = validate_with_pydantic(InsightsBookmarkParams, params)
        assert any(e.code == "B0_MISSING_FIELD" and field_name in e.path for e in errs)


class TestDiscriminatorRejection:
    """Bad values on discriminator fields produce the right error code."""

    @given(
        bad_type=st.text(min_size=2, max_size=15).filter(
            lambda s: (
                s
                not in {
                    "event",
                    "simple",
                    "cohort",
                    "funnel",
                    "retention",
                    "formula",
                    "custom-event",
                    "people",
                    "saved-metric",
                    "verified",
                    "retention-frequency",
                    "addiction",
                    "metric",
                }
            )
        ),
    )
    @settings(max_examples=30)
    def test_bad_behavior_type_rejected(self, bad_type: str) -> None:
        """Invalid ``behavior.type`` produces ``B0_INVALID_LITERAL``."""
        params = _valid_minimal_insights()
        params["sections"]["show"][0]["behavior"]["type"] = bad_type
        errs = validate_with_pydantic(InsightsBookmarkParams, params)
        # Could be literal_error (the type field is a Literal union)
        # or behavior-type discriminator failure.
        assert any(
            e.code in ("B0_INVALID_LITERAL", "B7_INVALID_BEHAVIOR_TYPE") for e in errs
        )

    @given(
        bad_sort_by=st.text(min_size=2, max_size=15).filter(
            lambda s: s not in {"column", "value", "label", "liftComparisonValue"}
        ),
    )
    @settings(max_examples=30)
    def test_bad_sort_by_rejected(self, bad_sort_by: str) -> None:
        """Invalid ``sortBy`` on a sort config is rejected."""
        bad = {"sortBy": bad_sort_by, "colSortAttrs": []}
        with pytest.raises(PydanticValidationError):
            SortByColumnsConfig.model_validate(bad)


# =============================================================================
# Legacy field tolerance
# =============================================================================


class TestLegacyFieldTolerance:
    """All 27 documented ``Ignore[T]`` fields on
    ``InsightsBookmarkParams`` must pass validation without errors."""

    @given(field=st.sampled_from(_INSIGHTS_LEGACY_FIELDS))
    @settings(max_examples=len(_INSIGHTS_LEGACY_FIELDS))
    def test_legacy_field_tolerated(self, field: tuple[str, Any]) -> None:
        """Each documented legacy field with a typed-correct value is
        silently tolerated."""
        field_name, field_value = field
        params = _valid_minimal_insights()
        params[field_name] = field_value
        errs = validate_with_pydantic(InsightsBookmarkParams, params)
        assert errs == [], (
            f"Legacy field '{field_name}' should be tolerated, got {len(errs)} errors"
        )

    @given(
        # Pick several legacy fields and add them all at once.
        fields=st.lists(
            st.sampled_from(_INSIGHTS_LEGACY_FIELDS),
            min_size=2,
            max_size=5,
            unique_by=lambda t: t[0],
        ),
    )
    @settings(max_examples=20)
    def test_multiple_legacy_fields_tolerated(
        self, fields: list[tuple[str, Any]]
    ) -> None:
        """Multiple legacy fields together still pass."""
        params = _valid_minimal_insights()
        for field_name, field_value in fields:
            params[field_name] = field_value
        errs = validate_with_pydantic(InsightsBookmarkParams, params)
        assert errs == []


# =============================================================================
# Dispatch consistency
# =============================================================================


class TestDispatchConsistency:
    """``get_root_model_for_bookmark_type`` returns the right root model
    for every documented bookmark_type."""

    @given(bt=st.sampled_from(["insights", "funnels", "retention", "flows", "user"]))
    @settings(max_examples=5)
    def test_dispatch_returns_consistent_class(self, bt: str) -> None:
        """Funnels and Retention share ``InsightsBookmarkParams``.
        Flows uses ``FlowsBookmarkParams``. User has no canonical schema.
        """
        m = get_root_model_for_bookmark_type(bt)
        if bt in ("insights", "funnels", "retention"):
            assert m is InsightsBookmarkParams
        elif bt == "flows":
            assert m is FlowsBookmarkParams
        elif bt == "user":
            assert m is None
