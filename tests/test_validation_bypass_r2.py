"""Round 2 validation bypass tests: flow, retention, and NaN/Inf fixes.

After fixing Bug 4 (flow CP scanning), Bug 5 (retention event CP scanning),
and Bug 6 (NaN/Inf filter values), all round 2 bypass vectors are now caught.

- **R2-V1**: FlowStep.filters CP → now raises BookmarkValidationError
- **R2-V2**: RetentionEvent.filters CP → now raises BookmarkValidationError
- **R2-V3**: NaN filter values → now raises BookmarkValidationError
- **R2-V4**: Inf filter values → now raises BookmarkValidationError
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.exceptions import BookmarkValidationError, ValidationError
from mixpanel_headless.types import (
    CustomPropertyRef,
    Filter,
    FlowStep,
    InlineCustomProperty,
    Metric,
    PropertyInput,
    RetentionEvent,
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
# FIXED: R2-V1 — FlowStep.filters custom property scanning
# =========================================================================


class TestR2V1FlowStepFiltersCPFixed:
    """Bug 4 fix: _scan_custom_properties now scans FlowStep.filters."""

    def test_invalid_cp_id_raises(self, ws: Workspace) -> None:
        """CustomPropertyRef(0) in FlowStep.filters raises."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_flow_params(
                FlowStep(
                    "Purchase",
                    filters=[Filter.is_set(property=CustomPropertyRef(0))],
                ),
                last=7,
            )

    def test_negative_cp_id_raises(self, ws: Workspace) -> None:
        """CustomPropertyRef(-1) in FlowStep.filters raises."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_flow_params(
                FlowStep(
                    "Purchase",
                    filters=[Filter.is_set(property=CustomPropertyRef(-1))],
                ),
                last=7,
            )

    def test_empty_formula_cp_raises(self, ws: Workspace) -> None:
        """InlineCustomProperty(formula='') in FlowStep.filters raises."""
        bad_cp = InlineCustomProperty(
            formula="",
            inputs={"A": PropertyInput("$browser")},
        )
        with pytest.raises(BookmarkValidationError, match="non-empty"):
            ws.build_flow_params(
                FlowStep(
                    "Purchase",
                    filters=[Filter.is_set(property=bad_cp)],
                ),
                last=7,
            )

    def test_valid_cp_in_flow_step_passes(self, ws: Workspace) -> None:
        """Valid CustomPropertyRef(42) in FlowStep.filters passes."""
        params = ws.build_flow_params(
            FlowStep(
                "Purchase",
                filters=[Filter.is_set(property=CustomPropertyRef(42))],
            ),
            last=7,
        )
        assert "steps" in params


# =========================================================================
# FIXED: R2-V2 — RetentionEvent.filters custom property scanning
# =========================================================================


class TestR2V2RetentionEventFiltersCPFixed:
    """Bug 5 fix: _scan_custom_properties now scans RetentionEvent.filters."""

    def test_born_event_cp_raises(self, ws: Workspace) -> None:
        """CustomPropertyRef(0) in born_event filters raises."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_retention_params(
                RetentionEvent(
                    "Signup",
                    filters=[Filter.is_set(property=CustomPropertyRef(0))],
                ),
                "Login",
                last=7,
            )

    def test_return_event_cp_raises(self, ws: Workspace) -> None:
        """CustomPropertyRef(0) in return_event filters raises."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_retention_params(
                "Signup",
                RetentionEvent(
                    "Login",
                    filters=[Filter.is_set(property=CustomPropertyRef(0))],
                ),
                last=7,
            )

    def test_empty_formula_cp_raises(self, ws: Workspace) -> None:
        """InlineCustomProperty(formula='') in RetentionEvent.filters raises."""
        bad_cp = InlineCustomProperty(
            formula="",
            inputs={"A": PropertyInput("$browser")},
        )
        with pytest.raises(BookmarkValidationError, match="non-empty"):
            ws.build_retention_params(
                RetentionEvent(
                    "Signup",
                    filters=[Filter.is_set(property=bad_cp)],
                ),
                "Login",
                last=7,
            )

    def test_valid_cp_in_retention_passes(self, ws: Workspace) -> None:
        """Valid CustomPropertyRef(42) in RetentionEvent.filters passes."""
        params = ws.build_retention_params(
            RetentionEvent(
                "Signup",
                filters=[Filter.is_set(property=CustomPropertyRef(42))],
            ),
            "Login",
            last=7,
        )
        assert "sections" in params


# =========================================================================
# FIXED: R2-V3 — NaN filter values
# =========================================================================


class TestR2V3NaNFilterFixed:
    """Bug 6 fix: NaN filter values now caught by B20b at L2."""

    def test_nan_in_where_filter_raises(self, ws: Workspace) -> None:
        """NaN in where filter raises BookmarkValidationError."""
        with pytest.raises(BookmarkValidationError, match="finite number"):
            ws.build_params(
                "AnyEvent",
                where=Filter.greater_than("age", float("nan")),
                last=7,
            )

    def test_nan_in_per_metric_filter_raises(self, ws: Workspace) -> None:
        """NaN in Metric.filters raises BookmarkValidationError."""
        with pytest.raises(BookmarkValidationError, match="finite number"):
            ws.build_params(
                Metric(
                    "AnyEvent",
                    filters=[Filter.greater_than("age", float("nan"))],
                ),
                last=7,
            )

    def test_finite_value_passes(self, ws: Workspace) -> None:
        """Normal finite values still pass."""
        params = ws.build_params(
            "AnyEvent",
            where=Filter.greater_than("age", 18),
            last=7,
        )
        assert "sections" in params


# =========================================================================
# FIXED: R2-V4 — Inf filter values
# =========================================================================


class TestR2V4InfFilterFixed:
    """Bug 6 fix: Inf filter values now caught by B20b at L2."""

    def test_inf_in_where_filter_raises(self, ws: Workspace) -> None:
        """Inf in where filter raises BookmarkValidationError."""
        with pytest.raises(BookmarkValidationError, match="finite number"):
            ws.build_params(
                "AnyEvent",
                where=Filter.greater_than("age", float("inf")),
                last=7,
            )

    def test_negative_inf_raises(self, ws: Workspace) -> None:
        """Negative infinity also raises."""
        with pytest.raises(BookmarkValidationError, match="finite number"):
            ws.build_params(
                "AnyEvent",
                where=Filter.greater_than("age", float("-inf")),
                last=7,
            )

    def test_large_finite_value_passes(self, ws: Workspace) -> None:
        """Large but finite values still pass."""
        params = ws.build_params(
            "AnyEvent",
            where=Filter.greater_than("age", 1e15),
            last=7,
        )
        assert "sections" in params


# =========================================================================
# FIXED: Combined — multiple R2 fixes working together
# =========================================================================


class TestR2CombinedFixes:
    """Multiple round 2 fixes working in combination."""

    def test_flow_cp_caught_before_nan(self, ws: Workspace) -> None:
        """FlowStep with invalid CP is caught at L1 (before NaN at L2)."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_flow_params(
                FlowStep(
                    "Purchase",
                    filters=[
                        Filter.is_set(property=CustomPropertyRef(0)),
                        Filter.greater_than("amount", float("nan")),
                    ],
                ),
                last=7,
            )

    def test_retention_cp_caught(self, ws: Workspace) -> None:
        """RetentionEvent with invalid CP is caught."""
        with pytest.raises(BookmarkValidationError, match="positive integer"):
            ws.build_retention_params(
                RetentionEvent(
                    "Signup",
                    filters=[Filter.is_set(property=CustomPropertyRef(-1))],
                ),
                "Login",
                where=Filter.greater_than("age", float("inf")),
                last=7,
            )
