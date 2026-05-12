"""Unit tests for flow query types.

Tests cover:
    T012: FlowStep — construction, defaults, immutability, field preservation.
    T013: FlowQueryResult — construction, defaults, to_dict(), immutability.
    T031: FlowQueryResult.nodes_df — node extraction from sankey steps.
    T032: FlowQueryResult.edges_df — edge extraction from sankey steps.
    T033: FlowQueryResult.df — mode-aware DataFrame dispatch.
    T037: FlowQueryResult.graph — networkx DiGraph construction.
    T047: FlowQueryResult.top_transitions — highest-traffic transitions.
    T048: FlowQueryResult.drop_off_summary — per-step drop-off analysis.
"""

from __future__ import annotations

import warnings
from typing import Any

import networkx as nx
import pandas as pd
import pytest

from mixpanel_headless.types import Filter, FlowQueryResult, FlowStep, _safe_int

# =============================================================================
# T012: FlowStep
# =============================================================================


class TestFlowStepConstruction:
    """Tests for FlowStep construction and defaults."""

    def test_construct_with_event_only(self) -> None:
        """FlowStep with just an event name uses correct defaults."""
        s = FlowStep("Purchase")
        assert s.event == "Purchase"
        assert s.forward is None
        assert s.reverse is None
        assert s.label is None
        assert s.filters is None
        assert s.filters_combinator == "all"

    def test_construct_with_all_fields(self) -> None:
        """FlowStep with all fields preserves them."""
        f = Filter.equals("country", "US")
        s = FlowStep(
            "Purchase",
            forward=5,
            reverse=3,
            label="Buy",
            filters=[f],
            filters_combinator="any",
        )
        assert s.event == "Purchase"
        assert s.forward == 5
        assert s.reverse == 3
        assert s.label == "Buy"
        assert s.filters is not None
        assert len(s.filters) == 1
        assert s.filters_combinator == "any"

    def test_default_forward_is_none(self) -> None:
        """Default forward is None."""
        s = FlowStep("Login")
        assert s.forward is None

    def test_default_reverse_is_none(self) -> None:
        """Default reverse is None."""
        s = FlowStep("Login")
        assert s.reverse is None

    def test_default_label_is_none(self) -> None:
        """Default label is None."""
        s = FlowStep("Login")
        assert s.label is None

    def test_default_filters_is_none(self) -> None:
        """Default filters is None, not an empty list."""
        s = FlowStep("Login")
        assert s.filters is None

    def test_default_filters_combinator_is_all(self) -> None:
        """Default filters_combinator is 'all'."""
        s = FlowStep("Login")
        assert s.filters_combinator == "all"

    def test_event_field_preserved(self) -> None:
        """Event name is preserved exactly as given, including unicode."""
        s = FlowStep("My Custom Event \u2728")
        assert s.event == "My Custom Event \u2728"

    def test_filters_list_preserved(self) -> None:
        """Filters list contents are preserved."""
        f1 = Filter.equals("country", "US")
        f2 = Filter.equals("platform", "iOS")
        s = FlowStep("Signup", filters=[f1, f2])
        assert s.filters is not None
        assert len(s.filters) == 2

    def test_string_normalization_not_applied(self) -> None:
        """Event with whitespace is NOT stripped (preserved as-is)."""
        s = FlowStep("  Purchase  ")
        assert s.event == "  Purchase  "


class TestFlowStepImmutability:
    """Tests for FlowStep frozen dataclass immutability."""

    def test_cannot_set_event(self) -> None:
        """Setting event on a frozen instance must raise."""
        s = FlowStep("Purchase")
        with pytest.raises(AttributeError):
            s.event = "Login"  # type: ignore[misc]

    def test_cannot_set_forward(self) -> None:
        """Setting forward on a frozen instance must raise."""
        s = FlowStep("Purchase")
        with pytest.raises(AttributeError):
            s.forward = 5  # type: ignore[misc]

    def test_cannot_set_filters(self) -> None:
        """Setting filters on a frozen instance must raise."""
        s = FlowStep("Purchase")
        with pytest.raises(AttributeError):
            s.filters = []  # type: ignore[misc]


# =============================================================================
# T013: FlowQueryResult
# =============================================================================


def _make_result(**overrides: Any) -> FlowQueryResult:
    """Build a default-valid FlowQueryResult for testing.

    Args:
        **overrides: Field overrides to apply on top of defaults.

    Returns:
        FlowQueryResult instance with sensible defaults.
    """
    defaults: dict[str, Any] = {
        "computed_at": "2025-01-15T10:00:00",
        "steps": [],
        "flows": [],
        "breakdowns": [],
        "overall_conversion_rate": 0.0,
        "params": {},
        "meta": {},
        "mode": "sankey",
    }
    defaults.update(overrides)
    return FlowQueryResult(**defaults)


class TestFlowQueryResultConstruction:
    """Tests for FlowQueryResult construction and defaults."""

    def test_construct_with_defaults(self) -> None:
        """_make_result() produces a valid instance with correct defaults."""
        r = _make_result()
        assert r.computed_at == "2025-01-15T10:00:00"
        assert r.steps == []
        assert r.flows == []
        assert r.breakdowns == []
        assert r.overall_conversion_rate == 0.0
        assert r.params == {}
        assert r.meta == {}
        assert r.mode == "sankey"

    def test_construct_with_overrides(self) -> None:
        """Overriding each field works correctly."""
        r = _make_result(
            computed_at="2025-02-01T12:00:00",
            steps=[{"event": "Login"}],
            flows=[{"path": ["Login", "Purchase"]}],
            breakdowns=[{"name": "country"}],
            overall_conversion_rate=0.75,
            params={"sections": {}},
            meta={"sampling_factor": 1.0},
            mode="paths",
        )
        assert r.computed_at == "2025-02-01T12:00:00"
        assert len(r.steps) == 1
        assert len(r.flows) == 1
        assert len(r.breakdowns) == 1
        assert r.overall_conversion_rate == 0.75
        assert "sections" in r.params
        assert r.meta["sampling_factor"] == 1.0
        assert r.mode == "paths"

    def test_default_mode_is_sankey(self) -> None:
        """Default mode is 'sankey'."""
        r = _make_result()
        assert r.mode == "sankey"

    def test_steps_default_empty_list(self) -> None:
        """Steps defaults to an empty list."""
        r = FlowQueryResult(computed_at="")
        assert r.steps == []

    def test_flows_default_empty_list(self) -> None:
        """Flows defaults to an empty list."""
        r = FlowQueryResult(computed_at="")
        assert r.flows == []


class TestFlowQueryResultImmutability:
    """Tests for FlowQueryResult frozen dataclass immutability."""

    def test_cannot_set_computed_at(self) -> None:
        """Setting computed_at on a frozen instance must raise."""
        r = _make_result()
        with pytest.raises(AttributeError):
            r.computed_at = "new"  # type: ignore[misc]

    def test_cannot_set_steps(self) -> None:
        """Setting steps on a frozen instance must raise."""
        r = _make_result()
        with pytest.raises(AttributeError):
            r.steps = []  # type: ignore[misc]


class TestFlowQueryResultToDict:
    """Tests for FlowQueryResult.to_dict() serialization."""

    def test_to_dict_contains_all_fields(self) -> None:
        """to_dict() includes all public fields."""
        r = _make_result()
        d = r.to_dict()
        assert "computed_at" in d
        assert "steps" in d
        assert "flows" in d
        assert "breakdowns" in d
        assert "overall_conversion_rate" in d
        assert "params" in d
        assert "meta" in d
        assert "mode" in d

    def test_to_dict_values_match_fields(self) -> None:
        """to_dict() values match the instance fields."""
        r = _make_result()
        d = r.to_dict()
        assert d["computed_at"] == r.computed_at
        assert d["steps"] == r.steps
        assert d["flows"] == r.flows
        assert d["breakdowns"] == r.breakdowns
        assert d["overall_conversion_rate"] == r.overall_conversion_rate
        assert d["params"] == r.params
        assert d["meta"] == r.meta
        assert d["mode"] == r.mode

    def test_to_dict_with_populated_data(self) -> None:
        """to_dict() correctly serializes populated steps and flows."""
        r = _make_result(
            steps=[
                {"event": "Login", "count": 100},
                {"event": "Purchase", "count": 50},
            ],
            flows=[
                {"path": ["Login", "Purchase"], "count": 30},
            ],
            overall_conversion_rate=0.5,
        )
        d = r.to_dict()
        assert len(d["steps"]) == 2
        assert d["steps"][0]["event"] == "Login"
        assert len(d["flows"]) == 1
        assert d["flows"][0]["count"] == 30
        assert d["overall_conversion_rate"] == 0.5


# =============================================================================
# Shared helpers for T031–T037
# =============================================================================


def _sample_sankey_steps() -> list[dict[str, Any]]:
    """Build sample sankey steps data for testing.

    Returns two steps: Login (anchor) with edges to Search and DROPOFF,
    then Search with an edge to Purchase.

    Returns:
        List of step dicts matching the Mixpanel sankey API response format.
    """
    return [
        {
            "nodes": [
                {
                    "event": "Login",
                    "type": "ANCHOR",
                    "anchorType": "NORMAL",
                    "totalCount": "100",
                    "isComputed": False,
                    "isCustomEvent": False,
                    "conversionRateChange": 0.0,
                    "edges": [
                        {
                            "event": "Search",
                            "type": "NORMAL",
                            "step": 1,
                            "totalCount": "80",
                        },
                        {
                            "event": "DROPOFF",
                            "type": "DROPOFF",
                            "step": 1,
                            "totalCount": "20",
                        },
                    ],
                }
            ]
        },
        {
            "nodes": [
                {
                    "event": "Search",
                    "type": "NORMAL",
                    "anchorType": "NORMAL",
                    "totalCount": "80",
                    "isComputed": False,
                    "isCustomEvent": False,
                    "conversionRateChange": -0.2,
                    "edges": [
                        {
                            "event": "Purchase",
                            "type": "NORMAL",
                            "step": 2,
                            "totalCount": "50",
                        },
                    ],
                }
            ]
        },
    ]


def _sample_top_paths_flows() -> list[dict[str, Any]]:
    """Build sample top-paths flows data for testing.

    Returns two flow paths: Login->Search and Login->Browse.

    Returns:
        List of flow dicts matching the Mixpanel top-paths API response format.
    """
    return [
        {
            "flowSteps": [
                {"event": "Login", "type": "ANCHOR", "totalCount": "100"},
                {"event": "Search", "type": "NORMAL", "totalCount": "80"},
            ],
            "segments": [],
        },
        {
            "flowSteps": [
                {"event": "Login", "type": "ANCHOR", "totalCount": "100"},
                {"event": "Browse", "type": "NORMAL", "totalCount": "20"},
            ],
            "segments": [],
        },
    ]


# =============================================================================
# T031: FlowQueryResult.nodes_df
# =============================================================================


class TestFlowQueryResultNodesDf:
    """Tests for FlowQueryResult.nodes_df property."""

    def test_nodes_df_columns(self) -> None:
        """nodes_df has the expected column names."""
        r = _make_result(steps=_sample_sankey_steps())
        expected_cols = [
            "step",
            "event",
            "type",
            "count",
            "anchor_type",
            "is_custom_event",
            "conversion_rate_change",
        ]
        assert list(r.nodes_df.columns) == expected_cols

    def test_nodes_df_row_count(self) -> None:
        """nodes_df has one row per node (2 nodes in sample data)."""
        r = _make_result(steps=_sample_sankey_steps())
        assert len(r.nodes_df) == 2

    def test_nodes_df_empty_steps(self) -> None:
        """Empty steps produces an empty DataFrame with correct columns."""
        r = _make_result(steps=[])
        df = r.nodes_df
        assert len(df) == 0
        expected_cols = [
            "step",
            "event",
            "type",
            "count",
            "anchor_type",
            "is_custom_event",
            "conversion_rate_change",
        ]
        assert list(df.columns) == expected_cols

    def test_nodes_df_total_count_parsed_as_int(self) -> None:
        """totalCount string '100' is parsed to int 100."""
        r = _make_result(steps=_sample_sankey_steps())
        counts = r.nodes_df["count"].tolist()
        assert counts == [100, 80]
        # Verify dtype is integer
        assert pd.api.types.is_integer_dtype(r.nodes_df["count"])

    def test_nodes_df_cached(self) -> None:
        """Second access returns the same cached object (id equality)."""
        r = _make_result(steps=_sample_sankey_steps())
        df1 = r.nodes_df
        df2 = r.nodes_df
        assert df1 is df2


# =============================================================================
# T032: FlowQueryResult.edges_df
# =============================================================================


class TestFlowQueryResultEdgesDf:
    """Tests for FlowQueryResult.edges_df property."""

    def test_edges_df_columns(self) -> None:
        """edges_df has the expected column names."""
        r = _make_result(steps=_sample_sankey_steps())
        expected_cols = [
            "source_step",
            "source_event",
            "target_step",
            "target_event",
            "count",
            "target_type",
        ]
        assert list(r.edges_df.columns) == expected_cols

    def test_edges_df_row_count(self) -> None:
        """edges_df has one row per edge (3 edges in sample data)."""
        r = _make_result(steps=_sample_sankey_steps())
        # Login->Search, Login->DROPOFF, Search->Purchase = 3 edges
        assert len(r.edges_df) == 3

    def test_edges_df_empty_steps(self) -> None:
        """Empty steps produces an empty DataFrame with correct columns."""
        r = _make_result(steps=[])
        df = r.edges_df
        assert len(df) == 0
        expected_cols = [
            "source_step",
            "source_event",
            "target_step",
            "target_event",
            "count",
            "target_type",
        ]
        assert list(df.columns) == expected_cols

    def test_edges_df_count_parsed_as_int(self) -> None:
        """Edge totalCount strings are parsed to int dtype."""
        r = _make_result(steps=_sample_sankey_steps())
        assert pd.api.types.is_integer_dtype(r.edges_df["count"])

    def test_edges_df_cached(self) -> None:
        """Second access returns the same cached object (id equality)."""
        r = _make_result(steps=_sample_sankey_steps())
        df1 = r.edges_df
        df2 = r.edges_df
        assert df1 is df2


# =============================================================================
# T033: FlowQueryResult.df (mode-aware)
# =============================================================================


class TestFlowQueryResultDfModeAware:
    """Tests for FlowQueryResult.df mode-aware dispatch."""

    def test_df_sankey_returns_nodes_df(self) -> None:
        """In sankey mode, df returns the same DataFrame as nodes_df."""
        r = _make_result(mode="sankey", steps=_sample_sankey_steps())
        df = r.df
        nodes = r.nodes_df
        assert df is nodes

    def test_df_paths_returns_paths_dataframe(self) -> None:
        """In paths mode with flows data, df returns a tabular paths DataFrame."""
        r = _make_result(mode="paths", flows=_sample_top_paths_flows())
        df = r.df
        assert len(df) > 0
        # Should have path_index, step, event, type, count columns
        assert "path_index" in df.columns
        assert "step" in df.columns
        assert "event" in df.columns
        assert "count" in df.columns

    def test_df_paths_empty_flows(self) -> None:
        """In paths mode with no flows, df returns an empty DataFrame."""
        r = _make_result(mode="paths", flows=[])
        df = r.df
        assert len(df) == 0


# =============================================================================
# T037: FlowQueryResult.graph
# =============================================================================


class TestFlowQueryResultGraph:
    """Tests for FlowQueryResult.graph networkx DiGraph property."""

    def test_graph_is_digraph(self) -> None:
        """graph property returns a networkx DiGraph."""
        r = _make_result(steps=_sample_sankey_steps())
        assert isinstance(r.graph, nx.DiGraph)

    def test_graph_node_keys(self) -> None:
        """Nodes are keyed as 'event@step' (e.g. 'Login@0', 'Search@1')."""
        r = _make_result(steps=_sample_sankey_steps())
        G = r.graph
        # Explicit nodes from the steps data
        assert "Login@0" in G.nodes
        assert "Search@1" in G.nodes
        # Edge targets also create nodes
        assert "DROPOFF@1" in G.nodes
        assert "Purchase@2" in G.nodes

    def test_graph_node_attributes(self) -> None:
        """Explicit node attributes include step, event, type, count, anchor_type."""
        r = _make_result(steps=_sample_sankey_steps())
        G = r.graph
        attrs = G.nodes["Login@0"]
        assert attrs["step"] == 0
        assert attrs["event"] == "Login"
        assert attrs["type"] == "ANCHOR"
        assert attrs["count"] == 100
        assert attrs["anchor_type"] == "NORMAL"

    def test_graph_edge_attributes(self) -> None:
        """Edge attributes include count and type."""
        r = _make_result(steps=_sample_sankey_steps())
        G = r.graph
        edge_data = G.edges["Login@0", "Search@1"]
        assert edge_data["count"] == 80
        assert edge_data["type"] == "NORMAL"

    def test_graph_empty_steps(self) -> None:
        """Empty steps produces an empty graph."""
        r = _make_result(steps=[])
        G = r.graph
        assert len(G.nodes) == 0
        assert len(G.edges) == 0

    def test_graph_cached(self) -> None:
        """Second access returns the same cached object (id equality)."""
        r = _make_result(steps=_sample_sankey_steps())
        g1 = r.graph
        g2 = r.graph
        assert g1 is g2

    def test_same_event_multiple_steps(self) -> None:
        """Same event at different steps produces distinct nodes."""
        steps: list[dict[str, Any]] = [
            {
                "nodes": [
                    {
                        "event": "Login",
                        "type": "ANCHOR",
                        "anchorType": "NORMAL",
                        "totalCount": "50",
                        "isComputed": False,
                        "isCustomEvent": False,
                        "conversionRateChange": 0.0,
                        "edges": [
                            {
                                "event": "Login",
                                "type": "NORMAL",
                                "step": 1,
                                "totalCount": "30",
                            },
                        ],
                    }
                ]
            },
            {
                "nodes": [
                    {
                        "event": "Login",
                        "type": "NORMAL",
                        "anchorType": "NORMAL",
                        "totalCount": "30",
                        "isComputed": False,
                        "isCustomEvent": False,
                        "conversionRateChange": -0.4,
                        "edges": [],
                    }
                ]
            },
        ]
        r = _make_result(steps=steps)
        G = r.graph
        assert "Login@0" in G.nodes
        assert "Login@1" in G.nodes
        assert G.nodes["Login@0"]["count"] == 50
        assert G.nodes["Login@1"]["count"] == 30


# =============================================================================
# T047: FlowQueryResult.top_transitions
# =============================================================================


class TestFlowQueryResultTopTransitions:
    """Tests for FlowQueryResult.top_transitions() convenience method."""

    def test_returns_list_of_tuples(self) -> None:
        """top_transitions() returns list of (source, target, count) tuples."""
        result = _make_result(steps=_sample_sankey_steps())
        transitions = result.top_transitions()
        assert isinstance(transitions, list)
        assert all(isinstance(t, tuple) and len(t) == 3 for t in transitions)

    def test_sorted_by_count_descending(self) -> None:
        """Transitions should be sorted by count, highest first."""
        result = _make_result(steps=_sample_sankey_steps())
        transitions = result.top_transitions()
        counts = [t[2] for t in transitions]
        assert counts == sorted(counts, reverse=True)

    def test_respects_n_limit(self) -> None:
        """top_transitions(n=1) returns at most 1 transition."""
        result = _make_result(steps=_sample_sankey_steps())
        transitions = result.top_transitions(n=1)
        assert len(transitions) <= 1

    def test_empty_edges_returns_empty_list(self) -> None:
        """No edges produces empty list."""
        result = _make_result(steps=[])
        transitions = result.top_transitions()
        assert transitions == []

    def test_default_n_is_10(self) -> None:
        """Default limit is 10."""
        result = _make_result(steps=_sample_sankey_steps())
        # Sample data has 3 edges, all should be returned
        transitions = result.top_transitions()
        assert len(transitions) == 3


# =============================================================================
# T048: FlowQueryResult.drop_off_summary
# =============================================================================


class TestFlowQueryResultDropOffSummary:
    """Tests for FlowQueryResult.drop_off_summary() convenience method."""

    def test_returns_dict(self) -> None:
        """drop_off_summary() returns a dict."""
        result = _make_result(steps=_sample_sankey_steps())
        summary = result.drop_off_summary()
        assert isinstance(summary, dict)

    def test_per_step_structure(self) -> None:
        """Each step entry has total, dropoff, and rate keys."""
        result = _make_result(steps=_sample_sankey_steps())
        summary = result.drop_off_summary()
        for _key, value in summary.items():
            assert "total" in value
            assert "dropoff" in value
            assert "rate" in value

    def test_dropoff_count_from_edges_of_non_dropoff_nodes(self) -> None:
        """Dropoff count comes from DROPOFF edges of non-DROPOFF nodes only.

        DROPOFF nodes represent prior-step dropoffs carried forward,
        so only DROPOFF edges from ANCHOR/NORMAL/PRUNED nodes are
        counted to avoid double-counting.
        """
        result = _make_result(steps=_sample_sankey_steps())
        summary = result.drop_off_summary()
        # Step 0: Login ANCHOR has DROPOFF edge count=20
        step_0 = summary["step_0"]
        assert step_0["total"] == 100
        assert step_0["dropoff"] == 20
        assert step_0["rate"] == 20 / 100

    def test_empty_steps_returns_empty_dict(self) -> None:
        """No steps produces empty dict."""
        result = _make_result(steps=[])
        summary = result.drop_off_summary()
        assert summary == {}


# =============================================================================
# T044–T045: Rename verification (US6)
# =============================================================================


class TestRenameVerification:
    """Tests verifying query_flows -> query_saved_flows rename (US6)."""

    def test_query_flows_attribute_does_not_exist(self) -> None:
        """Workspace must not have a query_flows attribute after rename."""
        from mixpanel_headless import Workspace

        assert not hasattr(Workspace, "query_flows")

    def test_query_saved_flows_exists(self) -> None:
        """Workspace must have query_saved_flows method after rename."""
        from mixpanel_headless import Workspace

        assert hasattr(Workspace, "query_saved_flows")
        assert callable(Workspace.query_saved_flows)


# =============================================================================
# _safe_int — resilient integer parsing
# =============================================================================


class TestSafeInt:
    """Tests for _safe_int() resilient integer parsing."""

    def test_valid_string(self) -> None:
        """String '100' is parsed to int 100."""
        assert _safe_int("100") == 100

    def test_int_passthrough(self) -> None:
        """Integer values pass through unchanged."""
        assert _safe_int(42) == 42

    def test_zero_int(self) -> None:
        """Integer zero passes through."""
        assert _safe_int(0) == 0

    def test_none_returns_default(self) -> None:
        """None returns the default value without warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            assert _safe_int(None) == 0
            assert len(w) == 0

    def test_empty_string_warns(self) -> None:
        """Empty string returns default and emits a warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _safe_int("")
            assert result == 0
            assert len(w) == 1
            assert "Non-numeric string" in str(w[0].message)

    def test_non_numeric_string_warns(self) -> None:
        """Non-numeric string 'N/A' returns default and warns."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _safe_int("N/A")
            assert result == 0
            assert len(w) == 1
            assert "Non-numeric string" in str(w[0].message)

    def test_float_string_warns(self) -> None:
        """Float string '100.5' returns default and warns."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _safe_int("100.5")
            assert result == 0
            assert len(w) == 1
            assert "Non-numeric string" in str(w[0].message)

    def test_bool_warns(self) -> None:
        """Boolean True is rejected (not treated as int 1)."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _safe_int(True)
            assert result == 0
            assert len(w) == 1
            assert "Unexpected type" in str(w[0].message)

    def test_custom_default(self) -> None:
        """Custom default value is used on failure."""
        assert _safe_int(None, default=-1) == -1

    def test_negative_string(self) -> None:
        """Negative string '-5' is parsed correctly."""
        assert _safe_int("-5") == -5


# =============================================================================
# T037: FlowStep with session_event (US8 — Advanced Flow Features)
# =============================================================================


class TestFlowStepSessionEvent:
    """Tests for FlowStep.session_event field (FS1)."""

    def test_session_start_succeeds(self) -> None:
        """FlowStep with session_event='start' and event='$session_start' succeeds."""
        step = FlowStep(event="$session_start", session_event="start")
        assert step.session_event == "start"
        assert step.event == "$session_start"

    def test_session_end_succeeds(self) -> None:
        """FlowStep with session_event='end' and event='$session_end' succeeds."""
        step = FlowStep(event="$session_end", session_event="end")
        assert step.session_event == "end"
        assert step.event == "$session_end"

    def test_default_session_event_is_none(self) -> None:
        """FlowStep without session_event has session_event=None."""
        step = FlowStep("Login")
        assert step.session_event is None

    def test_regular_event_with_session_event_raises(self) -> None:
        """FlowStep with a regular event name and session_event raises ValueError."""
        with pytest.raises(ValueError, match="session_event"):
            FlowStep(event="Login", session_event="start")

    def test_session_start_wrong_event_raises(self) -> None:
        """FlowStep with session_event='start' but event='$session_end' raises."""
        with pytest.raises(ValueError, match="session_event"):
            FlowStep(event="$session_end", session_event="start")

    def test_session_end_wrong_event_raises(self) -> None:
        """FlowStep with session_event='end' but event='$session_start' raises."""
        with pytest.raises(ValueError, match="session_event"):
            FlowStep(event="$session_start", session_event="end")

    def test_session_event_immutable(self) -> None:
        """session_event cannot be set on a frozen instance."""
        step = FlowStep(event="$session_start", session_event="start")
        with pytest.raises(AttributeError):
            step.session_event = "end"  # type: ignore[misc]
