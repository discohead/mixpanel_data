"""Validation bypass tests: verify the validation engine catches invalid inputs.

Originally written as QA bypass probes (Vectors 1-7). After fixing Bug 1
(``_scan_custom_properties()`` blind spot) and Bug 3b (formula show clause
guard), Vectors 1/2/5/6 and V7b are now caught by validation.

Vectors 3 and 4 remain as **design-documentation tests** — they demonstrate
intentional design choices (construction-time validation for cohorts,
forward-compatible warning severity for enum rules).

Test layout:
- **Fixed bugs**: Expect ``BookmarkValidationError`` (bypasses closed)
- **Design choices**: Assert current behavior is intentional (no fix needed)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless._internal.validation import validate_bookmark
from mixpanel_headless.exceptions import BookmarkValidationError, ValidationError
from mixpanel_headless.types import (
    CohortBreakdown,
    CohortCriteria,
    CohortDefinition,
    CustomPropertyRef,
    Filter,
    FunnelStep,
    InlineCustomProperty,
    Metric,
    PropertyInput,
)
from tests.conftest import make_session

# ---- 042 redesign: canonical fake Session for Workspace(session=…) ----
_TEST_SESSION = Session(
    account=ServiceAccount(
        name="test_account",
        region="us",
        username="test_user",
        secret=SecretStr("test_secret"),
        default_project="12345",
    ),
    project=Project(id="12345"),
)

# ---------------------------------------------------------------------------
# Fixtures (local — matches existing codebase convention)
# ---------------------------------------------------------------------------


@pytest.fixture()
def ws() -> Workspace:
    """Create a Workspace with mocked dependencies (no network)."""
    creds = make_session(username="u", secret="s", project_id="1", region="us")
    mgr = MagicMock()
    mgr.config_version.return_value = 1
    mgr.resolve_credentials.return_value = creds
    return Workspace(session=_TEST_SESSION, _api_client=MagicMock())


def _has_error(errors: list[ValidationError]) -> bool:
    """Return True if any error has severity='error'."""
    return any(e.severity == "error" for e in errors)


# =========================================================================
# FIXED: Vector 1 — CustomPropertyRef(0) in Metric.filters
# =========================================================================


class TestVector1MetricFilterCPFixed:
    """Bug 1 fix: _scan_custom_properties() now scans Metric.filters.

    CustomPropertyRef(0) in Metric.filters is caught by CP1 validation.
    """

    def test_invalid_cp_id_raises(self, ws: Workspace) -> None:
        """CustomPropertyRef(0) in Metric.filters raises BookmarkValidationError."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                Metric(
                    "AnyEvent",
                    filters=[Filter.is_set(property=CustomPropertyRef(0))],
                ),
                last=7,
            )

    def test_negative_cp_id_raises(self, ws: Workspace) -> None:
        """CustomPropertyRef(-1) in Metric.filters raises BookmarkValidationError."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                Metric(
                    "AnyEvent",
                    filters=[Filter.is_set(property=CustomPropertyRef(-1))],
                ),
                last=7,
            )

    def test_valid_cp_id_passes(self, ws: Workspace) -> None:
        """CustomPropertyRef(42) in Metric.filters passes validation."""
        params = ws.build_params(
            Metric(
                "AnyEvent",
                filters=[Filter.is_set(property=CustomPropertyRef(42))],
            ),
            last=7,
        )
        assert "sections" in params

    def test_l2_also_catches_invalid_cp_id(self, ws: Workspace) -> None:
        """Defense-in-depth: L2 B18b validates customPropertyId > 0."""
        params = ws.build_params(
            Metric(
                "AnyEvent",
                filters=[Filter.is_set(property=CustomPropertyRef(42))],
            ),
            last=7,
        )
        # Mutate to inject invalid ID after build (simulating L2-only check)
        params["sections"]["show"][0]["behavior"]["filters"][0]["customPropertyId"] = 0
        errors = validate_bookmark(params)
        assert _has_error(errors)
        assert any("B18B" in e.code for e in errors)


# =========================================================================
# FIXED: Vector 2 — CustomPropertyRef(0) in FunnelStep.filters
# =========================================================================


class TestVector2FunnelStepFilterCPFixed:
    """Bug 1 fix: _scan_custom_properties() now scans FunnelStep.filters.

    CustomPropertyRef(0) in FunnelStep.filters is caught by CP1 validation.
    """

    def test_invalid_cp_id_raises(self, ws: Workspace) -> None:
        """CustomPropertyRef(0) in FunnelStep.filters raises BookmarkValidationError."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_funnel_params(
                [
                    FunnelStep(
                        "Step1",
                        filters=[Filter.is_set(property=CustomPropertyRef(0))],
                    ),
                    "Step2",
                ],
                last=30,
            )

    def test_valid_cp_id_passes(self, ws: Workspace) -> None:
        """CustomPropertyRef(42) in FunnelStep.filters passes validation."""
        params = ws.build_funnel_params(
            [
                FunnelStep(
                    "Step1",
                    filters=[Filter.is_set(property=CustomPropertyRef(42))],
                ),
                "Step2",
            ],
            last=30,
        )
        assert "sections" in params


# =========================================================================
# DESIGN CHOICE: Vector 3 — Inline CohortDefinition in CohortBreakdown
# =========================================================================


class TestVector3InlineCohortDesignChoice:
    """Design choice: CohortDefinition validates at construction time.

    CohortCriteria.did_event("") raises ValueError (CD4).
    Valid-but-semantically-nonsensical cohorts (fake event names) produce
    valid JSON — the server returns empty results, not errors.
    This is intentional: the validation engine trusts type constructors.
    """

    def test_inline_cohort_breakdown_passes_validation(self, ws: Workspace) -> None:
        """Inline CohortDefinition in breakdown passes both validation layers."""
        criteria = CohortCriteria.did_event("FakeEvent", at_least=1, within_days=30)
        defn = CohortDefinition(criteria)
        params = ws.build_params(
            "AnyEvent",
            group_by=CohortBreakdown(defn, "Test Cohort"),
            last=7,
        )
        assert "sections" in params

    def test_construction_time_validation_catches_empty_event(self) -> None:
        """CohortCriteria.did_event('') raises ValueError at construction."""
        with pytest.raises(ValueError, match="non-empty"):
            CohortCriteria.did_event("", at_least=1, within_days=30)

    def test_raw_cohort_structure_present(self, ws: Workspace) -> None:
        """raw_cohort is present in group section with valid structure."""
        criteria = CohortCriteria.did_event("FakeEvent", at_least=1, within_days=30)
        defn = CohortDefinition(criteria)
        params = ws.build_params(
            "AnyEvent",
            group_by=CohortBreakdown(defn, "Test Cohort"),
            last=7,
        )
        group = params["sections"]["group"]
        cohorts = group[0]["cohorts"]
        assert any("raw_cohort" in c for c in cohorts)
        errors = validate_bookmark(params)
        assert not _has_error(errors)


# =========================================================================
# DESIGN CHOICE: Vector 4 — Warning-only enum severity
# =========================================================================


class TestVector4WarningOnlyEnumDesignChoice:
    """Design choice: B7/B16/B17 are warnings for forward compatibility.

    Invalid enum values in bookmark JSON produce warnings, not errors.
    Builder functions always produce valid enums — these warnings only fire
    on post-build dict mutation, which is outside the library's responsibility.
    """

    def test_invalid_resource_type_is_warning_only(self, ws: Workspace) -> None:
        """Invalid resourceType in group section → warning, not error."""
        params = ws.build_params("AnyEvent", group_by="country", last=7)
        params["sections"]["group"][0]["resourceType"] = "BOGUS_TYPE"

        errors = validate_bookmark(params)
        resource_errors = [e for e in errors if "B16" in e.code]
        assert len(resource_errors) > 0, "Expected B16 warning"
        assert all(e.severity == "warning" for e in resource_errors)
        assert not _has_error(errors)

    def test_invalid_property_type_is_warning_only(self, ws: Workspace) -> None:
        """Invalid propertyType in group section → warning, not error."""
        params = ws.build_params("AnyEvent", group_by="country", last=7)
        params["sections"]["group"][0]["propertyType"] = "FAKE_TYPE"

        errors = validate_bookmark(params)
        prop_errors = [e for e in errors if "B17" in e.code]
        assert len(prop_errors) > 0, "Expected B17 warning"
        assert all(e.severity == "warning" for e in prop_errors)
        assert not _has_error(errors)

    def test_invalid_behavior_type_is_warning_only(self, ws: Workspace) -> None:
        """Invalid behavior.type → warning via B7, not error."""
        params = ws.build_params("AnyEvent", last=7)
        params["sections"]["show"][0]["behavior"]["type"] = "NONEXISTENT"

        errors = validate_bookmark(params)
        b7_errors = [e for e in errors if "B7" in e.code]
        assert len(b7_errors) > 0, "Expected B7 warning"
        assert all(e.severity == "warning" for e in b7_errors)


# =========================================================================
# FIXED: Vector 5 — Negative CustomPropertyRef ID via Metric.filters
# =========================================================================


class TestVector5NegativeCPRefFixed:
    """Bug 1 fix: Negative CustomPropertyRef IDs in Metric.filters now caught."""

    def test_negative_id_raises(self, ws: Workspace) -> None:
        """CustomPropertyRef(-1) in Metric.filters raises BookmarkValidationError."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                Metric(
                    "AnyEvent",
                    filters=[Filter.is_set(property=CustomPropertyRef(-1))],
                ),
                last=7,
            )

    def test_large_negative_id_raises(self, ws: Workspace) -> None:
        """CustomPropertyRef(-999999) in Metric.filters raises."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                Metric(
                    "AnyEvent",
                    filters=[Filter.is_set(property=CustomPropertyRef(-999999))],
                ),
                last=7,
            )


# =========================================================================
# FIXED: Vector 6 — Empty formula InlineCustomProperty in Metric.filters
# =========================================================================


class TestVector6EmptyFormulaFixed:
    """Bug 1 fix: Empty formula InlineCustomProperty in Metric.filters now caught."""

    def test_empty_formula_raises(self, ws: Workspace) -> None:
        """Empty formula in per-metric filter raises BookmarkValidationError."""
        bad_cp = InlineCustomProperty(
            formula="",
            inputs={"A": PropertyInput("$browser")},
        )
        with pytest.raises(BookmarkValidationError, match="non-empty"):
            ws.build_params(
                Metric(
                    "AnyEvent",
                    filters=[Filter.is_set(property=bad_cp)],
                ),
                last=7,
            )

    def test_valid_inline_cp_in_metric_filter_passes(self, ws: Workspace) -> None:
        """Valid InlineCustomProperty in Metric.filters passes."""
        good_cp = InlineCustomProperty(
            formula="A",
            inputs={"A": PropertyInput("$browser")},
        )
        params = ws.build_params(
            Metric(
                "AnyEvent",
                filters=[Filter.is_set(property=good_cp)],
            ),
            last=7,
        )
        assert "sections" in params


# =========================================================================
# FIXED: Vector 7 — Formula show clause injection
# =========================================================================


class TestVector7FormulaShowClauseFixed:
    """Bug 3b fix: Formula key no longer acts as a validation kill-switch.

    Hybrid show clauses (both 'formula' and 'behavior' keys) now get
    full behavior validation instead of being silently skipped.
    """

    def test_hybrid_formula_behavior_clause_still_validates(
        self, ws: Workspace
    ) -> None:
        """A hybrid clause (formula + behavior) still validates the behavior."""
        params = ws.build_params("AnyEvent", last=7)
        # Inject formula key into a valid show clause — creates hybrid
        params["sections"]["show"][0]["formula"] = ""

        errors = validate_bookmark(params)
        # Valid behavior + formula key → behavior still validated, no errors
        assert not _has_error(errors)

    def test_corrupted_behavior_detected_despite_formula_key(
        self, ws: Workspace
    ) -> None:
        """Corrupted behavior IS detected even when 'formula' key present."""
        params = ws.build_params("AnyEvent", last=7)
        # Corrupt the behavior block
        params["sections"]["show"][0]["behavior"]["type"] = "INVALID"
        # Attempt to hide it with formula key — no longer works
        params["sections"]["show"][0]["formula"] = ""

        errors = validate_bookmark(params)
        # B7 (invalid type) IS now reported as a warning
        b7_errors = [e for e in errors if "B7" in e.code]
        assert len(b7_errors) > 0, "B7 should fire even when formula key is present"
        assert all(e.severity == "warning" for e in b7_errors), (
            "B7 is intentionally severity='warning' (forward compatibility)"
        )


# =========================================================================
# FIXED: Combined — Multiple fixes working together
# =========================================================================


class TestCombinedFixes:
    """Multiple fix vectors working in combination."""

    def test_cp_bypass_in_metric_filter_now_caught(self, ws: Workspace) -> None:
        """Invalid CP ID in Metric.filters is caught regardless of other params."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_params(
                Metric(
                    "AnyEvent",
                    filters=[Filter.is_set(property=CustomPropertyRef(0))],
                ),
                group_by="country",
                last=7,
            )

    def test_empty_formula_cp_in_funnel_step_now_caught(self, ws: Workspace) -> None:
        """Empty-formula InlineCustomProperty in FunnelStep.filters is caught."""
        bad_cp = InlineCustomProperty(
            formula="",
            inputs={"A": PropertyInput("$browser")},
        )
        with pytest.raises(BookmarkValidationError, match="non-empty"):
            ws.build_funnel_params(
                [
                    FunnelStep(
                        "Step1",
                        filters=[Filter.is_set(property=bad_cp)],
                    ),
                    "Step2",
                ],
                last=30,
            )
