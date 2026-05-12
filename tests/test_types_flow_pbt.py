"""Property-based tests for flow query types using Hypothesis.

These tests verify invariants of FlowStep, FlowQueryResult,
and build_flow_params that should hold for all possible inputs,
catching edge cases that example-based tests miss.

Usage:
    # Run with default profile (100 examples)
    pytest tests/test_types_flow_pbt.py

    # Run with dev profile (10 examples, verbose)
    HYPOTHESIS_PROFILE=dev pytest tests/test_types_flow_pbt.py

    # Run with CI profile (200 examples, deterministic)
    HYPOTHESIS_PROFILE=ci pytest tests/test_types_flow_pbt.py
"""

from __future__ import annotations

import dataclasses
from typing import Any
from unittest.mock import MagicMock

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.types import FlowQueryResult, FlowStep
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

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for event names (non-empty visible characters only)
event_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())


@st.composite
def flow_steps(draw: st.DrawFn) -> FlowStep:
    """Generate random valid FlowStep objects.

    Draws an event name, optional forward/reverse step counts,
    and an optional display label to construct a valid ``FlowStep``.
    Uses visible characters only (letters, numbers, punctuation, symbols)
    since ``FlowStep.__post_init__`` rejects control characters.

    Args:
        draw: Hypothesis draw function for composing strategies.

    Returns:
        A randomly generated FlowStep instance.
    """
    event = draw(event_names)
    forward = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=5)))
    reverse = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=5)))
    label = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    return FlowStep(event=event, forward=forward, reverse=reverse, label=label)


@st.composite
def valid_flow_steps(draw: st.DrawFn) -> FlowStep:
    """Generate FlowStep objects with API-safe event names.

    Uses the ``event_names`` strategy which restricts to visible
    characters (letters, numbers, punctuation, symbols), avoiding
    control characters that would fail bookmark validation.

    Args:
        draw: Hypothesis draw function for composing strategies.

    Returns:
        A FlowStep instance safe for ``build_flow_params`` calls.
    """
    event = draw(event_names)
    forward = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=5)))
    reverse = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=5)))
    label = draw(st.one_of(st.none(), event_names))
    return FlowStep(event=event, forward=forward, reverse=reverse, label=label)


@st.composite
def step_node_dicts(draw: st.DrawFn) -> list[dict[str, Any]]:
    """Generate random sankey step-node structures matching API shape.

    Each step contains a ``nodes`` list. Each node has an event name,
    type, totalCount (string), anchorType, and optional edges to
    downstream nodes.

    Args:
        draw: Hypothesis draw function for composing strategies.

    Returns:
        A list of step dicts with nested node and edge structures.
    """
    n_steps = draw(st.integers(min_value=0, max_value=4))
    steps: list[dict[str, Any]] = []
    for step_idx in range(n_steps):
        n_nodes = draw(st.integers(min_value=0, max_value=3))
        nodes: list[dict[str, Any]] = []
        for _ in range(n_nodes):
            event = draw(event_names)
            count = draw(st.integers(min_value=0, max_value=10000))
            node_type = draw(st.sampled_from(["ANCHOR", "NORMAL", "DROPOFF"]))
            n_edges = draw(st.integers(min_value=0, max_value=2))
            edges: list[dict[str, Any]] = []
            for _ in range(n_edges):
                edge_event = draw(event_names)
                edge_count = draw(st.integers(min_value=0, max_value=count))
                edge_type = draw(st.sampled_from(["NORMAL", "DROPOFF"]))
                edges.append(
                    {
                        "event": edge_event,
                        "step": step_idx + 1,
                        "totalCount": str(edge_count),
                        "type": edge_type,
                    }
                )
            nodes.append(
                {
                    "event": event,
                    "type": node_type,
                    "totalCount": str(count),
                    "anchorType": "NORMAL",
                    "isCustomEvent": False,
                    "conversionRateChange": 0.0,
                    "edges": edges,
                }
            )
        steps.append({"nodes": nodes})
    return steps


# =============================================================================
# Helpers
# =============================================================================


def _make_workspace() -> Workspace:
    """Create a Workspace instance with mocked dependencies.

    Uses dependency injection so no real credentials or network access
    are needed.  Built as a plain function (not a pytest fixture) so it
    can be called inside ``@given``-decorated tests without triggering
    Hypothesis's ``function_scoped_fixture`` health check.

    Returns:
        A Workspace with mocked ConfigManager and MixpanelAPIClient.
    """
    creds = make_session(
        username="test_user",
        secret="test_secret",
        project_id="12345",
        region="us",
    )
    manager = MagicMock()
    manager.config_version.return_value = 1
    manager.resolve_credentials.return_value = creds
    client = MagicMock(spec=MixpanelAPIClient)
    client.close = MagicMock()
    return Workspace(
        session=_TEST_SESSION,
        _api_client=client,
    )


# =============================================================================
# FlowStep Property Tests
# =============================================================================


class TestFlowStepPBT:
    """Property-based tests for FlowStep frozen dataclass.

    Verifies immutability, field preservation, and range invariants
    that should hold for all possible FlowStep instances.
    """

    @given(step=flow_steps())
    @settings(max_examples=100)
    def test_immutability(self, step: FlowStep) -> None:
        """Setting any attribute on a frozen FlowStep raises an error.

        Generates random FlowStep instances and verifies that
        assigning to any field raises ``FrozenInstanceError``.
        """
        with pytest.raises(dataclasses.FrozenInstanceError):
            step.event = "other"  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            step.forward = 1  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            step.reverse = 1  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            step.label = "other"  # type: ignore[misc]

    @given(step=flow_steps())
    @settings(max_examples=100)
    def test_event_preserved(self, step: FlowStep) -> None:
        """The event field is preserved exactly as given across random strings.

        Verifies that no normalization, stripping, or transformation
        occurs on the event name during construction.
        """
        rebuilt = FlowStep(
            event=step.event,
            forward=step.forward,
            reverse=step.reverse,
            label=step.label,
        )
        assert rebuilt.event == step.event

    @given(step=flow_steps())
    @settings(max_examples=100)
    def test_forward_in_range(self, step: FlowStep) -> None:
        """Forward is None or in range 0-5.

        The strategy constrains forward to ``None`` or ``0..5``,
        so this invariant must always hold for generated values.
        """
        assert step.forward is None or 0 <= step.forward <= 5

    @given(step=flow_steps())
    @settings(max_examples=100)
    def test_reverse_in_range(self, step: FlowStep) -> None:
        """Reverse is None or in range 0-5.

        The strategy constrains reverse to ``None`` or ``0..5``,
        so this invariant must always hold for generated values.
        """
        assert step.reverse is None or 0 <= step.reverse <= 5


# =============================================================================
# FlowQueryResult Property Tests
# =============================================================================


class TestFlowQueryResultPBT:
    """Property-based tests for FlowQueryResult.

    Verifies DataFrame shape, column presence, and serialization
    invariants across randomly generated flow step data.
    """

    @given(steps=step_node_dicts())
    @settings(max_examples=100)
    def test_nodes_df_shape_invariant(self, steps: list[dict[str, Any]]) -> None:
        """nodes_df columns always match the expected set, even with random steps.

        Regardless of input shape (empty steps, zero nodes, many nodes),
        the column set must be exactly these seven in order.
        """
        result = FlowQueryResult(
            computed_at="2025-01-01T00:00:00",
            steps=steps,
        )
        expected_columns = [
            "step",
            "event",
            "type",
            "count",
            "anchor_type",
            "is_custom_event",
            "conversion_rate_change",
        ]
        assert list(result.nodes_df.columns) == expected_columns

    @given(steps=step_node_dicts())
    @settings(max_examples=100)
    def test_edges_df_shape_invariant(self, steps: list[dict[str, Any]]) -> None:
        """edges_df columns always match the expected set.

        Regardless of input shape (empty steps, no edges, many edges),
        the column set must be exactly these six in order.
        """
        result = FlowQueryResult(
            computed_at="2025-01-01T00:00:00",
            steps=steps,
        )
        expected_columns = [
            "source_step",
            "source_event",
            "target_step",
            "target_event",
            "count",
            "target_type",
        ]
        assert list(result.edges_df.columns) == expected_columns

    @given(steps=step_node_dicts())
    @settings(max_examples=100)
    def test_to_dict_keys(self, steps: list[dict[str, Any]]) -> None:
        """to_dict() always has all required keys.

        The serialized dict must always contain the full set of
        FlowQueryResult fields regardless of the input data.
        """
        result = FlowQueryResult(
            computed_at="2025-01-01T00:00:00",
            steps=steps,
        )
        d = result.to_dict()
        required_keys = {
            "computed_at",
            "steps",
            "flows",
            "breakdowns",
            "overall_conversion_rate",
            "params",
            "meta",
            "mode",
            "trees",
        }
        assert required_keys == set(d.keys())

    @given(steps=step_node_dicts())
    @settings(max_examples=100)
    def test_immutability(self, steps: list[dict[str, Any]]) -> None:
        """Setting any attribute on a frozen FlowQueryResult raises an error.

        Verifies that assigning to the core fields of a frozen
        FlowQueryResult raises ``FrozenInstanceError``.
        """
        result = FlowQueryResult(
            computed_at="2025-01-01T00:00:00",
            steps=steps,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.computed_at = "other"  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.steps = []  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.mode = "paths"  # type: ignore[misc]


# =============================================================================
# build_flow_params Property Tests
# =============================================================================


class TestBuildFlowParamsPBT:
    """Property-based tests for Workspace.build_flow_params output structure.

    Verifies that for any valid event name inputs, the output always
    has the expected top-level structure, version, and step count.

    Uses ``_make_workspace()`` instead of pytest fixtures to avoid
    Hypothesis's ``function_scoped_fixture`` health check.
    """

    @given(event=event_names)
    @settings(max_examples=100)
    def test_params_always_has_required_keys(self, event: str) -> None:
        """build_flow_params output always has steps, date_range, chartType, version, count_type.

        These top-level keys are required for the bookmark JSON to be
        valid. They must always be present regardless of event names.
        """
        ws = _make_workspace()
        result = ws.build_flow_params(event)
        required_keys = {"steps", "date_range", "chartType", "version", "count_type"}
        assert required_keys.issubset(set(result.keys()))

    @given(event=event_names)
    @settings(max_examples=100)
    def test_version_always_2(self, event: str) -> None:
        """version is always 2.

        Flow bookmark params always use version 2 of the bookmark
        format, regardless of the input event name.
        """
        ws = _make_workspace()
        result = ws.build_flow_params(event)
        assert result["version"] == 2

    @given(
        steps=st.lists(valid_flow_steps(), min_size=1, max_size=5),
    )
    @settings(max_examples=100)
    def test_steps_match_input_count(self, steps: list[FlowStep]) -> None:
        """Number of steps in output matches input.

        The output ``steps`` array must have the same length as the
        input list of FlowStep objects passed to ``build_flow_params``.
        Steps that explicitly zero both directions (overriding the
        top-level default ``forward=1``) are correctly rejected by
        FL5 validation, so skip those inputs.
        """
        # build_flow_params defaults: forward=1, reverse=0.
        # Skip when all steps would have zero effective direction.
        effective = [
            (s.forward if s.forward is not None else 1)
            + (s.reverse if s.reverse is not None else 0)
            for s in steps
        ]
        assume(max(effective) > 0)
        ws = _make_workspace()
        result = ws.build_flow_params(steps)
        assert len(result["steps"]) == len(steps)
