"""Property-based tests for FlowTreeNode using Hypothesis.

These tests verify invariants of FlowTreeNode that should hold for
all possible tree structures, catching edge cases that example-based
tests miss.

Usage:
    # Run with default profile (100 examples)
    pytest tests/test_types_flow_tree_pbt.py

    # Run with dev profile (10 examples, verbose)
    HYPOTHESIS_PROFILE=dev pytest tests/test_types_flow_tree_pbt.py

    # Run with CI profile (200 examples, deterministic)
    HYPOTHESIS_PROFILE=ci pytest tests/test_types_flow_tree_pbt.py
"""

from __future__ import annotations

from typing import cast

from anytree import PreOrderIter
from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_headless._literal_types import FlowNodeType
from mixpanel_headless.types import FlowQueryResult, FlowTreeNode

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for event names (non-empty visible characters only)
event_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip())

# Strategy for node type strings
node_types = st.sampled_from(
    ["ANCHOR", "NORMAL", "DROPOFF", "PRUNED", "FORWARD", "REVERSE"]
)


@st.composite
def flow_tree_nodes(draw: st.DrawFn, max_depth: int = 3) -> FlowTreeNode:
    """Generate random valid FlowTreeNode trees.

    Recursively builds tree structures with random event names,
    counts, and children up to the specified depth.

    Args:
        draw: Hypothesis draw function for composing strategies.
        max_depth: Maximum tree depth. Children are only generated
            when depth > 0.

    Returns:
        A randomly generated FlowTreeNode tree.
    """
    event = draw(event_names)
    node_type = cast(FlowNodeType, draw(node_types))
    step_number = draw(st.integers(min_value=0, max_value=10))
    total = draw(st.integers(min_value=0, max_value=10000))
    dropoff = draw(st.integers(min_value=0, max_value=total))
    converted = draw(st.integers(min_value=0, max_value=total))

    n_children = draw(st.integers(min_value=0, max_value=3)) if max_depth > 0 else 0
    children = tuple(
        draw(flow_tree_nodes(max_depth=max_depth - 1)) for _ in range(n_children)
    )

    return FlowTreeNode(
        event=event,
        type=node_type,
        step_number=step_number,
        total_count=total,
        drop_off_count=dropoff,
        converted_count=converted,
        children=children,
    )


# =============================================================================
# Structural Invariants
# =============================================================================


class TestFlowTreeNodeStructuralInvariants:
    """Property-based tests for structural invariants of FlowTreeNode."""

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_node_count_at_least_one(self, tree: FlowTreeNode) -> None:
        """node_count is always >= 1 (at least the root)."""
        assert tree.node_count >= 1

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_leaf_count_at_least_one(self, tree: FlowTreeNode) -> None:
        """leaf_count is always >= 1."""
        assert tree.leaf_count >= 1

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_leaf_count_lte_node_count(self, tree: FlowTreeNode) -> None:
        """leaf_count is always <= node_count."""
        assert tree.leaf_count <= tree.node_count

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_depth_non_negative(self, tree: FlowTreeNode) -> None:
        """depth is always >= 0."""
        assert tree.depth >= 0

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_flatten_length_equals_node_count(self, tree: FlowTreeNode) -> None:
        """flatten() returns exactly node_count elements."""
        assert len(tree.flatten()) == tree.node_count


# =============================================================================
# Path Invariants
# =============================================================================


class TestFlowTreeNodePathInvariants:
    """Property-based tests for path-related invariants."""

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_path_count_equals_leaf_count(self, tree: FlowTreeNode) -> None:
        """Number of paths equals leaf_count."""
        assert len(tree.all_paths()) == tree.leaf_count

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_all_paths_start_with_root(self, tree: FlowTreeNode) -> None:
        """Every path starts with the root node."""
        for path in tree.all_paths():
            assert path[0] is tree

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_all_paths_end_with_leaf(self, tree: FlowTreeNode) -> None:
        """Every path ends with a leaf node (no children)."""
        for path in tree.all_paths():
            assert path[-1].children == ()

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_find_root_always_returns_result(self, tree: FlowTreeNode) -> None:
        """find(root.event) always returns at least 1 result."""
        results = tree.find(tree.event)
        assert len(results) >= 1


# =============================================================================
# Serialization Invariants
# =============================================================================


class TestFlowTreeNodeSerializationInvariants:
    """Property-based tests for serialization invariants."""

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_to_dict_has_required_keys(self, tree: FlowTreeNode) -> None:
        """to_dict() always has the required keys."""
        d = tree.to_dict()
        required_keys = {
            "event",
            "type",
            "step_number",
            "total_count",
            "drop_off_count",
            "converted_count",
            "anchor_type",
            "is_computed",
            "children",
            "time_percentiles_from_start",
            "time_percentiles_from_prev",
        }
        assert set(d.keys()) == required_keys

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_to_dict_children_count_matches(self, tree: FlowTreeNode) -> None:
        """to_dict() children count matches actual children."""
        d = tree.to_dict()
        assert len(d["children"]) == len(tree.children)


# =============================================================================
# Rate Invariants
# =============================================================================


class TestFlowTreeNodeRateInvariants:
    """Property-based tests for rate computation invariants."""

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_conversion_rate_bounded(self, tree: FlowTreeNode) -> None:
        """conversion_rate is in [0.0, 1.0] when total_count > 0."""
        if tree.total_count > 0:
            assert 0.0 <= tree.conversion_rate <= 1.0

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_conversion_rate_zero_when_no_total(self, tree: FlowTreeNode) -> None:
        """conversion_rate is 0.0 when total_count is 0."""
        if tree.total_count == 0:
            assert tree.conversion_rate == 0.0

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_drop_off_rate_bounded(self, tree: FlowTreeNode) -> None:
        """drop_off_rate is in [0.0, 1.0] when total_count > 0."""
        if tree.total_count > 0:
            assert 0.0 <= tree.drop_off_rate <= 1.0

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_drop_off_rate_zero_when_no_total(self, tree: FlowTreeNode) -> None:
        """drop_off_rate is 0.0 when total_count is 0."""
        if tree.total_count == 0:
            assert tree.drop_off_rate == 0.0


# =============================================================================
# Anytree Conversion Invariants
# =============================================================================


class TestFlowTreeNodeAnytreeInvariants:
    """Property-based tests for to_anytree() conversion invariants."""

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_anytree_node_count_matches(self, tree: FlowTreeNode) -> None:
        """to_anytree() produces a tree with the same node count."""
        at = tree.to_anytree()
        anytree_count = len(list(PreOrderIter(at)))
        assert anytree_count == tree.node_count

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_anytree_root_has_no_parent(self, tree: FlowTreeNode) -> None:
        """to_anytree() root node has no parent."""
        at = tree.to_anytree()
        assert at.parent is None

    @given(tree=flow_tree_nodes())
    @settings(max_examples=100)
    def test_anytree_root_event_matches(self, tree: FlowTreeNode) -> None:
        """to_anytree() root event matches FlowTreeNode event."""
        at = tree.to_anytree()
        assert at.event == tree.event


# =============================================================================
# FlowQueryResult Tree Mode Invariants
# =============================================================================


@st.composite
def tree_mode_results(draw: st.DrawFn) -> FlowQueryResult:
    """Generate random FlowQueryResult with mode='tree' and random trees.

    Args:
        draw: Hypothesis draw function for composing strategies.

    Returns:
        A randomly generated FlowQueryResult in tree mode.
    """
    n_trees = draw(st.integers(min_value=0, max_value=3))
    trees = [draw(flow_tree_nodes(max_depth=2)) for _ in range(n_trees)]
    return FlowQueryResult(
        computed_at="2025-01-01T00:00:00",
        mode="tree",
        trees=trees,
    )


class TestFlowQueryResultTreeInvariants:
    """Property-based tests for FlowQueryResult tree mode."""

    @given(result=tree_mode_results())
    @settings(max_examples=100)
    def test_df_columns_always_match(self, result: FlowQueryResult) -> None:
        """df columns always match the expected set in tree mode."""
        expected_cols = [
            "tree_index",
            "depth",
            "path",
            "event",
            "type",
            "step_number",
            "total_count",
            "drop_off_count",
            "converted_count",
        ]
        assert list(result.df.columns) == expected_cols

    @given(result=tree_mode_results())
    @settings(max_examples=100)
    def test_df_row_count_equals_total_nodes(self, result: FlowQueryResult) -> None:
        """df row count equals sum of node_count across all trees."""
        expected = sum(t.node_count for t in result.trees)
        assert len(result.df) == expected

    @given(result=tree_mode_results())
    @settings(max_examples=100)
    def test_to_dict_trees_length_matches(self, result: FlowQueryResult) -> None:
        """to_dict()['trees'] length matches len(result.trees)."""
        d = result.to_dict()
        assert len(d["trees"]) == len(result.trees)

    @given(result=tree_mode_results())
    @settings(max_examples=100)
    def test_anytree_length_matches(self, result: FlowQueryResult) -> None:
        """anytree property length matches len(result.trees)."""
        assert len(result.anytree) == len(result.trees)
