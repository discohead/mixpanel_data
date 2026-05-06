"""Unit tests for ``src/mixpanel_data/_internal/bookmark_schema.py`` models.

Each model in ``bookmark_schema.py`` mirrors a canonical Pydantic class
in Mixpanel's upstream ``analytics`` repository under
``lib/common/mxpnl/report/bookmarks/`` (and its sibling
``mixpanel_mcp/mcp_server/types/reports/internal/`` package for flows).
These tests verify, for each model:

- valid input passes without errors
- required fields rejected when missing
- extra fields rejected (``extra="forbid"`` mirrors server)
- legacy ``Ignore[T]`` fields tolerated (don't reject; don't surface)
- discriminated unions select the right variant
- enum-like Literal fields reject invalid values

Each test class names the canonical source file + line in its docstring
for drift-tracking.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

# =============================================================================
# Sorting models — mirrors
# ``analytics/lib/common/mxpnl/report/bookmarks/insights/sorting.py``
# in the upstream ``analytics`` repository.
# =============================================================================


class TestSortByColumnsConfig:
    """Tests mirroring sorting.py ``SortByColumnsConfig``.

    Discriminator ``sortBy=Literal["column"]``, requires ``colSortAttrs``,
    tolerates legacy ``sortOrder`` and ``viewNLimit`` via ``Ignore[T]``.
    """

    def test_valid_minimal_passes(self) -> None:
        """Minimal valid config: sortBy=column + empty colSortAttrs."""
        from mixpanel_data._internal.bookmark_schema import SortByColumnsConfig

        m = SortByColumnsConfig.model_validate({"sortBy": "column", "colSortAttrs": []})
        assert m.sortBy == "column"
        assert m.colSortAttrs == []

    def test_with_value_field_passes(self) -> None:
        """``valueField`` is optional and accepted when provided."""
        from mixpanel_data._internal.bookmark_schema import SortByColumnsConfig

        m = SortByColumnsConfig.model_validate(
            {"sortBy": "column", "colSortAttrs": [], "valueField": "averageValue"}
        )
        assert m.valueField == "averageValue"

    def test_missing_col_sort_attrs_rejected(self) -> None:
        """``colSortAttrs`` is required."""
        from mixpanel_data._internal.bookmark_schema import SortByColumnsConfig

        with pytest.raises(PydanticValidationError) as exc:
            SortByColumnsConfig.model_validate({"sortBy": "column"})
        errs = exc.value.errors()
        assert any(e["type"] == "missing" and "colSortAttrs" in e["loc"] for e in errs)

    def test_wrong_sort_by_rejected(self) -> None:
        """``sortBy`` must be the literal ``"column"`` for this variant."""
        from mixpanel_data._internal.bookmark_schema import SortByColumnsConfig

        with pytest.raises(PydanticValidationError):
            SortByColumnsConfig.model_validate({"sortBy": "value", "colSortAttrs": []})

    def test_legacy_sort_order_tolerated(self) -> None:
        """``sortOrder`` is ``Ignore[T]`` on this variant — tolerated, hidden."""
        from mixpanel_data._internal.bookmark_schema import SortByColumnsConfig

        m = SortByColumnsConfig.model_validate(
            {"sortBy": "column", "colSortAttrs": [], "sortOrder": "asc"}
        )
        # Field was accepted but excluded from output
        assert "sortOrder" not in m.model_dump()

    def test_legacy_view_n_limit_tolerated(self) -> None:
        """``viewNLimit`` is ``Ignore[T]`` on this variant — tolerated, hidden."""
        from mixpanel_data._internal.bookmark_schema import SortByColumnsConfig

        m = SortByColumnsConfig.model_validate(
            {"sortBy": "column", "colSortAttrs": [], "viewNLimit": 50}
        )
        assert "viewNLimit" not in m.model_dump()

    def test_unknown_field_rejected(self) -> None:
        """Truly unknown fields rejected (mirrors server ``extra='forbid'``)."""
        from mixpanel_data._internal.bookmark_schema import SortByColumnsConfig

        with pytest.raises(PydanticValidationError) as exc:
            SortByColumnsConfig.model_validate(
                {
                    "sortBy": "column",
                    "colSortAttrs": [],
                    "segmentation": "value",
                }
            )
        assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())


class TestSortByValueConfig:
    """Tests mirroring sorting.py ``SortByValueConfig``.

    Discriminator ``sortBy=Literal["value", "liftComparisonValue"]``;
    ``colSortAttrs`` required, ``sortOrder`` optional. Deprecated
    ``"liftComparisonValue"`` retained for input compatibility.
    """

    def test_valid_minimal_passes(self) -> None:
        """Minimal valid config: sortBy=value + empty colSortAttrs."""
        from mixpanel_data._internal.bookmark_schema import SortByValueConfig

        m = SortByValueConfig.model_validate({"sortBy": "value", "colSortAttrs": []})
        assert m.sortBy == "value"

    def test_missing_col_sort_attrs_rejected(self) -> None:
        """``colSortAttrs`` is required."""
        from mixpanel_data._internal.bookmark_schema import SortByValueConfig

        with pytest.raises(PydanticValidationError):
            SortByValueConfig.model_validate({"sortBy": "value"})

    def test_sort_order_optional(self) -> None:
        """``sortOrder`` is optional on this variant (canonical:
        ``Optional[SortOrder] = None``)."""
        from mixpanel_data._internal.bookmark_schema import SortByValueConfig

        m = SortByValueConfig.model_validate({"sortBy": "value", "colSortAttrs": []})
        assert m.sortOrder is None

    def test_sort_order_when_provided_validated(self) -> None:
        """``sortOrder`` must be ``"asc"``/``"desc"`` when provided."""
        from mixpanel_data._internal.bookmark_schema import SortByValueConfig

        with pytest.raises(PydanticValidationError):
            SortByValueConfig.model_validate(
                {"sortBy": "value", "sortOrder": "ascending", "colSortAttrs": []}
            )

    def test_deprecated_lift_comparison_value_accepted(self) -> None:
        """``"liftComparisonValue"`` is deprecated but still accepted as
        ``sortBy`` per canonical model."""
        from mixpanel_data._internal.bookmark_schema import SortByValueConfig

        m = SortByValueConfig.model_validate(
            {"sortBy": "liftComparisonValue", "colSortAttrs": []}
        )
        assert m.sortBy == "liftComparisonValue"

    def test_extra_segmentation_field_rejected(self) -> None:
        """Extra ``segmentation`` key on ``SortByValueConfig`` is rejected.

        Mirrors server ``extra='forbid'`` policy; sending it produces
        ``extra_forbidden`` at parse time rather than a server-side
        rejection at chart-render time.
        """
        from mixpanel_data._internal.bookmark_schema import SortByValueConfig

        with pytest.raises(PydanticValidationError) as exc:
            SortByValueConfig.model_validate(
                {
                    "sortBy": "value",
                    "sortOrder": "asc",
                    "colSortAttrs": [],
                    "segmentation": "value",
                }
            )
        assert any(
            e["type"] == "extra_forbidden" and "segmentation" in e["loc"]
            for e in exc.value.errors()
        )


class TestFlatSortConfigs:
    """Tests for ``FlatLabelSortConfig`` and ``FlatValueSortConfig``
    mirroring sorting.py.

    These appear inside ``colSortAttrs`` lists on both column and value
    sort configs. Discriminator on ``sortBy``: ``"label"`` vs
    ``"value"``/``"liftComparisonValue"``.
    """

    def test_flat_label_valid(self) -> None:
        """Label variant: requires sortOrder, valueField/viewNLimit optional."""
        from mixpanel_data._internal.bookmark_schema import FlatLabelSortConfig

        m = FlatLabelSortConfig.model_validate({"sortBy": "label", "sortOrder": "asc"})
        assert m.sortBy == "label"
        assert m.sortOrder == "asc"

    def test_flat_value_valid(self) -> None:
        """Value variant: requires sortOrder, valueField optional."""
        from mixpanel_data._internal.bookmark_schema import FlatValueSortConfig

        m = FlatValueSortConfig.model_validate(
            {
                "sortBy": "value",
                "sortOrder": "desc",
                "valueField": "averageValue",
            }
        )
        assert m.valueField == "averageValue"

    def test_flat_label_missing_sort_order_rejected(self) -> None:
        """``sortOrder`` is required on ``FlatLabelSortConfig``."""
        from mixpanel_data._internal.bookmark_schema import FlatLabelSortConfig

        with pytest.raises(PydanticValidationError):
            FlatLabelSortConfig.model_validate({"sortBy": "label"})


class TestInsightsBookmarkSortConfig:
    """Tests mirroring sorting.py ``InsightsBookmarkSortConfig``.

    The wrapper at ``params['sorting']`` — keys are chart-type strings
    (kebab-case wire form, snake_case Python field). Each key holds an
    optional ``SortConfig`` (discriminated union).
    """

    def test_empty_passes(self) -> None:
        """Empty sorting block is valid (no per-chart-type overrides)."""
        from mixpanel_data._internal.bookmark_schema import (
            InsightsBookmarkSortConfig,
        )

        m = InsightsBookmarkSortConfig.model_validate({})
        assert m.bar is None

    def test_bar_with_columns_config_passes(self) -> None:
        """Canonical valid bar config: sortBy=column + colSortAttrs."""
        from mixpanel_data._internal.bookmark_schema import (
            InsightsBookmarkSortConfig,
        )

        m = InsightsBookmarkSortConfig.model_validate(
            {"bar": {"sortBy": "column", "colSortAttrs": []}}
        )
        assert m.bar is not None
        assert m.bar.sortBy == "column"

    def test_funnel_steps_kebab_alias_accepted(self) -> None:
        """``funnel-steps`` (kebab-case wire) maps to ``funnel_steps`` field."""
        from mixpanel_data._internal.bookmark_schema import (
            InsightsBookmarkSortConfig,
        )

        m = InsightsBookmarkSortConfig.model_validate(
            {"funnel-steps": {"sortBy": "column", "colSortAttrs": []}}
        )
        assert m.funnel_steps is not None

    def test_retention_curve_kebab_alias_accepted(self) -> None:
        """``retention-curve`` kebab alias works."""
        from mixpanel_data._internal.bookmark_schema import (
            InsightsBookmarkSortConfig,
        )

        m = InsightsBookmarkSortConfig.model_validate(
            {"retention-curve": {"sortBy": "column", "colSortAttrs": []}}
        )
        assert m.retention_curve is not None

    def test_unknown_chart_type_rejected(self) -> None:
        """Unknown top-level keys (e.g. typo ``"barz"``) rejected."""
        from mixpanel_data._internal.bookmark_schema import (
            InsightsBookmarkSortConfig,
        )

        with pytest.raises(PydanticValidationError):
            InsightsBookmarkSortConfig.model_validate(
                {"barz": {"sortBy": "column", "colSortAttrs": []}}
            )

    def test_invalid_sorting_combinations_collected(self) -> None:
        """All per-chart-type errors are collected without short-circuiting.

        Two malformed configs (``bar``, ``funnel-steps``) — each missing
        ``colSortAttrs`` and carrying extra ``segmentation`` — produce
        four errors total via Pydantic's batch error collection.
        """
        from mixpanel_data._internal.bookmark_schema import (
            InsightsBookmarkSortConfig,
        )

        bad: dict[str, Any] = {
            "bar": {
                "sortBy": "value",
                "sortOrder": "asc",
                "segmentation": "value",
            },
            "funnel-steps": {
                "sortBy": "value",
                "sortOrder": "asc",
                "segmentation": "value",
            },
        }
        with pytest.raises(PydanticValidationError) as exc:
            InsightsBookmarkSortConfig.model_validate(bad)
        errs = exc.value.errors()
        # Missing colSortAttrs on both bar and funnel-steps
        missing = [e for e in errs if e["type"] == "missing"]
        assert len(missing) >= 2
        # Extra segmentation field on both
        extras = [
            e
            for e in errs
            if e["type"] == "extra_forbidden" and "segmentation" in e["loc"]
        ]
        assert len(extras) >= 2


class TestPydanticAdapter:
    """Direct tests for the Pydantic-error → ``ValidationError`` adapter.

    The adapter (``validate_with_pydantic``, ``_translate_pydantic_error``,
    ``_loc_to_jsonpath``) is the load-bearing translation layer between
    Pydantic and the package's stable ``B*``/``S*`` codes. Bugs here
    propagate to every caller and break agent-grep workflows.
    """

    def test_loc_to_jsonpath_top_level(self) -> None:
        """Single-segment loc renders as the segment name."""
        from mixpanel_data._internal.bookmark_schema import _loc_to_jsonpath

        assert _loc_to_jsonpath(("sortBy",), "") == "sortBy"

    def test_loc_to_jsonpath_nested_with_index(self) -> None:
        """List-index ints attach to the previous segment as ``[i]``."""
        from mixpanel_data._internal.bookmark_schema import _loc_to_jsonpath

        assert (
            _loc_to_jsonpath(("show", 0, "behavior", "type"), "sections")
            == "sections.show[0].behavior.type"
        )

    def test_loc_to_jsonpath_with_prefix(self) -> None:
        """``prefix`` is prepended verbatim (no trailing dot needed)."""
        from mixpanel_data._internal.bookmark_schema import _loc_to_jsonpath

        assert _loc_to_jsonpath(("bar", "sortBy"), "sorting") == "sorting.bar.sortBy"

    def test_loc_to_jsonpath_leading_index(self) -> None:
        """A leading int (no preceding segment) renders as ``[i]``."""
        from mixpanel_data._internal.bookmark_schema import _loc_to_jsonpath

        assert _loc_to_jsonpath((0, "name"), "") == "[0].name"

    def test_loc_to_jsonpath_strips_discriminator_tags(self) -> None:
        """Pydantic ``Tag`` names are filtered out of the JSONPath.

        ``Discriminator(...)+Tag(...)`` causes Pydantic to insert the Tag
        name into ``loc`` for discriminated-union failures. Those names
        are internal model class names and shouldn't leak to callers.
        """
        from mixpanel_data._internal.bookmark_schema import _loc_to_jsonpath

        loc = ("line", "FlatLabelSortConfig", "sortOrder")
        assert _loc_to_jsonpath(loc, "sorting") == "sorting.line.sortOrder"

    def test_unmapped_error_falls_through_to_validation_error(self) -> None:
        """Default mapper returns ``"VALIDATION_ERROR"`` for unknown types."""
        from mixpanel_data._internal.bookmark_schema import _default_code_mapper

        assert _default_code_mapper("totally_made_up_type", ()) == "VALIDATION_ERROR"

    def test_default_code_mapper_uses_default_map(self) -> None:
        """Known Pydantic error types map via ``_DEFAULT_CODE_MAP``."""
        from mixpanel_data._internal.bookmark_schema import _default_code_mapper

        assert _default_code_mapper("missing", ()) == "B0_MISSING_FIELD"
        assert _default_code_mapper("extra_forbidden", ()) == "S3_UNKNOWN_FIELD"
        assert _default_code_mapper("literal_error", ()) == "B0_INVALID_LITERAL"

    def test_sorting_code_mapper_path_disambiguation(self) -> None:
        """Sorting mapper distinguishes ``missing`` codes by terminal field."""
        from mixpanel_data._internal.bookmark_schema import _sorting_code_mapper

        assert (
            _sorting_code_mapper("missing", ("bar", "colSortAttrs"))
            == "S2_MISSING_COL_SORT_ATTRS"
        )
        assert (
            _sorting_code_mapper("missing", ("bar", "colSortAttrs", 0, "sortBy"))
            == "S8_MISSING_SORT_BY"
        )
        assert (
            _sorting_code_mapper("missing", ("line", "sortOrder"))
            == "S9_MISSING_SORT_ORDER"
        )

    def test_validate_with_pydantic_uses_code_mapper_when_provided(self) -> None:
        """Custom ``code_mapper`` overrides the default mapping."""
        from mixpanel_data._internal.bookmark_schema import (
            SortByValueConfig,
            validate_with_pydantic,
        )

        def my_mapper(err_type: str, loc: tuple[Any, ...]) -> str:
            return "CUSTOM_CODE"

        errs = validate_with_pydantic(
            SortByValueConfig, {"sortBy": "value"}, code_mapper=my_mapper
        )
        assert len(errs) >= 1
        assert all(e.code == "CUSTOM_CODE" for e in errs)

    def test_validate_with_pydantic_path_prefix_prepended(self) -> None:
        """``path_prefix`` is prepended to every translated error path."""
        from mixpanel_data._internal.bookmark_schema import (
            SortByValueConfig,
            validate_with_pydantic,
        )

        errs = validate_with_pydantic(
            SortByValueConfig,
            {"sortBy": "value"},
            path_prefix="custom.prefix",
        )
        assert len(errs) >= 1
        assert all(e.path.startswith("custom.prefix.") for e in errs)

    def test_validate_with_pydantic_no_errors_returns_empty(self) -> None:
        """Valid input produces an empty error list."""
        from mixpanel_data._internal.bookmark_schema import (
            FlatLabelSortConfig,
            validate_with_pydantic,
        )

        errs = validate_with_pydantic(
            FlatLabelSortConfig, {"sortBy": "label", "sortOrder": "asc"}
        )
        assert errs == []


class TestEnumParity:
    """Frozenset/Literal parity tests (Issue 16).

    Each ``Literal[...]`` alias in ``bookmark_schema`` has a sibling
    ``frozenset[str]`` constant in ``bookmark_enums``. The two must
    match exactly; otherwise the runtime check (frozenset) and the
    type-time check (Literal) silently disagree and one path becomes
    stricter than the other. Drift here is invisible without a test.
    """

    @pytest.mark.parametrize(
        ("literal_name", "frozen_name"),
        [
            ("MathTypeLiteral", "VALID_MATH_TYPES"),
            ("ChartTypeLiteral", "VALID_CHART_TYPES"),
            ("MetricTypeLiteral", "VALID_METRIC_TYPES"),
            ("TimeUnitLiteral", "VALID_TIME_UNITS"),
            ("InsightsResourceTypeLiteral", "VALID_RESOURCE_TYPES"),
            ("FiltersDeterminerLiteral", "VALID_FILTERS_DETERMINER"),
        ],
    )
    def test_literal_matches_frozenset(
        self, literal_name: str, frozen_name: str
    ) -> None:
        """``Literal`` args match the corresponding frozenset members."""
        from typing import get_args

        from mixpanel_data._internal import bookmark_enums, bookmark_schema

        literal_alias = getattr(bookmark_schema, literal_name)
        frozen_set = getattr(bookmark_enums, frozen_name)
        assert frozenset(get_args(literal_alias)) == frozen_set, (
            f"{literal_name} (in bookmark_schema) and {frozen_name} "
            f"(in bookmark_enums) diverged. Update both together to keep "
            f"the runtime frozenset check and the type-time Literal in sync."
        )


class TestBookmarkTypeLiteral:
    """Tests for ``CreateBookmarkParams.bookmark_type`` Literal tightening (Issue 14)."""

    def test_create_bookmark_params_rejects_unknown_type(self) -> None:
        """Typo in ``bookmark_type`` is rejected at construction time."""
        from mixpanel_data.types import CreateBookmarkParams

        with pytest.raises(PydanticValidationError) as exc:
            CreateBookmarkParams(
                name="Test",
                bookmark_type="insightz",  # typo
                params={},
            )
        assert any(
            e["type"] == "literal_error"
            and "bookmark_type" in str(e["loc"])
            or "type" in str(e["loc"])
            for e in exc.value.errors()
        )

    def test_create_bookmark_params_accepts_canonical_types(self) -> None:
        """All five canonical bookmark types are accepted."""
        from mixpanel_data.types import CreateBookmarkParams

        for bt in ("insights", "funnels", "retention", "flows", "user"):
            CreateBookmarkParams(name="X", bookmark_type=bt, params={})


class TestMathAndChartTypeTightening:
    """Tests for ``BehaviorMeasurement.math`` and ``DisplayOptions.chartType``
    Literal tightening (Issue 9).
    """

    def test_behavior_measurement_rejects_invalid_math(self) -> None:
        """``math='totl'`` (typo for ``'total'``) is rejected at parse time."""
        from mixpanel_data._internal.bookmark_schema import BehaviorMeasurement

        with pytest.raises(PydanticValidationError):
            BehaviorMeasurement.model_validate({"math": "totl"})

    def test_behavior_measurement_accepts_valid_math(self) -> None:
        """A canonical math operator validates."""
        from mixpanel_data._internal.bookmark_schema import BehaviorMeasurement

        m = BehaviorMeasurement.model_validate({"math": "total"})
        assert m.math == "total"

    def test_display_options_rejects_invalid_chart_type(self) -> None:
        """``chartType='lien'`` (typo for ``'line'``) is rejected at parse time."""
        from mixpanel_data._internal.bookmark_schema import DisplayOptions

        with pytest.raises(PydanticValidationError):
            DisplayOptions.model_validate({"chartType": "lien"})

    def test_display_options_accepts_valid_chart_type(self) -> None:
        """A canonical chart type validates."""
        from mixpanel_data._internal.bookmark_schema import DisplayOptions

        m = DisplayOptions.model_validate({"chartType": "bar"})
        assert m.chartType == "bar"


class TestFlowsBookmarkParams:
    """Tests pinning the current ``FlowsBookmarkParams`` behavior (Issue 10)."""

    def test_flows_bookmark_params_currently_allows_extras(self) -> None:
        """Pin the ``extra='allow'`` decision so it can't silently change.

        FlowsBookmarkParams uses ``extra='allow'`` (not ``'forbid'``)
        because the canonical MCP source itself doesn't forbid extras
        and the wire format carries many UI-only fields. Tightening
        requires corpus-driven enumeration (see TODO in source).

        This test fails if someone changes the model_config without
        also updating the corpus enumeration — forcing a deliberate
        choice rather than a silent regression.
        """
        from mixpanel_data._internal.bookmark_schema import FlowsBookmarkParams

        m = FlowsBookmarkParams.model_validate(
            {
                "steps": [{"event": "Login"}],
                "date_range": {"from_date": "2025-01-01"},
                "totally_unknown_ui_field": 12345,
            }
        )
        # extra="allow" stores unknowns on the model; "forbid" would raise.
        assert hasattr(m, "totally_unknown_ui_field") or hasattr(m, "model_extra")

    def test_flows_step_bool_op_rejects_invalid(self) -> None:
        """``FlowsBookmarkStep.bool_op`` is now a Literal — typos rejected."""
        from mixpanel_data._internal.bookmark_schema import FlowsBookmarkStep

        with pytest.raises(PydanticValidationError):
            FlowsBookmarkStep.model_validate({"event": "X", "bool_op": "annd"})
