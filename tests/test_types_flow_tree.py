"""Unit tests for FlowTreeNode and tree-mode FlowQueryResult.

Tests cover:
    T050: FlowTreeNode — construction, immutability, properties, methods,
          to_anytree() conversion.
    T051: FlowQueryResult tree mode — trees field, tree-mode df, to_dict,
          anytree property.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from anytree import AnyNode, PreOrderIter

import mixpanel_headless
from mixpanel_headless.types import FlowQueryResult, FlowTreeNode

# =============================================================================
# Helpers
# =============================================================================


def _sample_tree() -> FlowTreeNode:
    """Build a 3-level sample tree for testing.

    Structure::

        Login (ANCHOR, total=1000, dropoff=50, converted=950)
        ├── Search (NORMAL, total=600, dropoff=100, converted=500)
        │   ├── Purchase (ANCHOR, total=400, dropoff=0, converted=400)
        │   └── DROPOFF (DROPOFF, total=100, dropoff=100, converted=0)
        ├── Browse (NORMAL, total=300, dropoff=50, converted=250)
        │   └── Purchase (ANCHOR, total=200, dropoff=0, converted=200)
        └── DROPOFF (DROPOFF, total=50, dropoff=50, converted=0)
    """
    purchase_via_search = FlowTreeNode(
        event="Purchase",
        type="ANCHOR",
        step_number=2,
        total_count=400,
        drop_off_count=0,
        converted_count=400,
    )
    dropoff_after_search = FlowTreeNode(
        event="DROPOFF",
        type="DROPOFF",
        step_number=2,
        total_count=100,
        drop_off_count=100,
        converted_count=0,
    )
    search = FlowTreeNode(
        event="Search",
        type="NORMAL",
        step_number=1,
        total_count=600,
        drop_off_count=100,
        converted_count=500,
        children=(purchase_via_search, dropoff_after_search),
    )
    purchase_via_browse = FlowTreeNode(
        event="Purchase",
        type="ANCHOR",
        step_number=2,
        total_count=200,
        drop_off_count=0,
        converted_count=200,
    )
    browse = FlowTreeNode(
        event="Browse",
        type="NORMAL",
        step_number=1,
        total_count=300,
        drop_off_count=50,
        converted_count=250,
        children=(purchase_via_browse,),
    )
    dropoff_from_login = FlowTreeNode(
        event="DROPOFF",
        type="DROPOFF",
        step_number=1,
        total_count=50,
        drop_off_count=50,
        converted_count=0,
    )
    root = FlowTreeNode(
        event="Login",
        type="ANCHOR",
        step_number=0,
        total_count=1000,
        drop_off_count=50,
        converted_count=950,
        children=(search, browse, dropoff_from_login),
    )
    return root


def _leaf_node() -> FlowTreeNode:
    """Build a single leaf node with no children."""
    return FlowTreeNode(
        event="Purchase",
        type="ANCHOR",
        step_number=0,
        total_count=100,
        drop_off_count=0,
        converted_count=100,
    )


# =============================================================================
# T050: FlowTreeNode construction
# =============================================================================


class TestFlowTreeNodeConstruction:
    """Tests for FlowTreeNode construction and defaults."""

    def test_construct_with_required_fields(self) -> None:
        """FlowTreeNode with required fields uses correct defaults."""
        node = FlowTreeNode(
            event="Login",
            type="ANCHOR",
            step_number=0,
            total_count=100,
        )
        assert node.event == "Login"
        assert node.type == "ANCHOR"
        assert node.step_number == 0
        assert node.total_count == 100
        assert node.drop_off_count == 0
        assert node.converted_count == 0
        assert node.anchor_type == "NORMAL"
        assert node.is_computed is False
        assert node.children == ()
        assert node.time_percentiles_from_start == {}
        assert node.time_percentiles_from_prev == {}

    def test_construct_with_all_fields(self) -> None:
        """FlowTreeNode with all fields preserves them."""
        tp_start = {"percentiles": [50, 90], "values": [1.0, 5.0]}
        tp_prev = {"percentiles": [50], "values": [0.5]}
        child = FlowTreeNode(
            event="Search", type="NORMAL", step_number=1, total_count=50
        )
        node = FlowTreeNode(
            event="Login",
            type="ANCHOR",
            step_number=0,
            total_count=100,
            drop_off_count=10,
            converted_count=90,
            anchor_type="RELATIVE_FORWARD",
            is_computed=True,
            children=(child,),
            time_percentiles_from_start=tp_start,
            time_percentiles_from_prev=tp_prev,
        )
        assert node.drop_off_count == 10
        assert node.converted_count == 90
        assert node.anchor_type == "RELATIVE_FORWARD"
        assert node.is_computed is True
        assert len(node.children) == 1
        assert node.children[0].event == "Search"
        assert node.time_percentiles_from_start == tp_start
        assert node.time_percentiles_from_prev == tp_prev

    def test_frozen_immutability(self) -> None:
        """Setting any attribute on a frozen FlowTreeNode raises an error."""
        node = _leaf_node()
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.event = "Other"  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.total_count = 999  # type: ignore[misc]

    def test_empty_children_default(self) -> None:
        """Children defaults to empty tuple, not mutable list."""
        node = _leaf_node()
        assert node.children == ()
        assert isinstance(node.children, tuple)


# =============================================================================
# T050: FlowTreeNode properties
# =============================================================================


class TestFlowTreeNodeProperties:
    """Tests for FlowTreeNode computed properties."""

    def test_depth_leaf(self) -> None:
        """Leaf node has depth 0."""
        assert _leaf_node().depth == 0

    def test_depth_one_level(self) -> None:
        """Root with one child has depth 1."""
        child = _leaf_node()
        root = FlowTreeNode(
            event="Root",
            type="ANCHOR",
            step_number=0,
            total_count=100,
            children=(child,),
        )
        assert root.depth == 1

    def test_depth_sample_tree(self) -> None:
        """Sample tree has depth 2 (Login -> Search -> Purchase)."""
        assert _sample_tree().depth == 2

    def test_node_count_leaf(self) -> None:
        """Leaf node has node_count 1."""
        assert _leaf_node().node_count == 1

    def test_node_count_sample_tree(self) -> None:
        """Sample tree has 7 nodes total."""
        assert _sample_tree().node_count == 7

    def test_leaf_count_leaf(self) -> None:
        """Leaf node has leaf_count 1."""
        assert _leaf_node().leaf_count == 1

    def test_leaf_count_sample_tree(self) -> None:
        """Sample tree has 4 leaves (2 Purchases + 2 DROPOFFs)."""
        assert _sample_tree().leaf_count == 4

    def test_conversion_rate_normal(self) -> None:
        """conversion_rate = converted_count / total_count."""
        tree = _sample_tree()
        assert tree.conversion_rate == pytest.approx(950 / 1000)

    def test_conversion_rate_zero_total(self) -> None:
        """conversion_rate is 0.0 when total_count is 0."""
        node = FlowTreeNode(event="Empty", type="NORMAL", step_number=0, total_count=0)
        assert node.conversion_rate == 0.0

    def test_drop_off_rate_normal(self) -> None:
        """drop_off_rate = drop_off_count / total_count."""
        tree = _sample_tree()
        assert tree.drop_off_rate == pytest.approx(50 / 1000)

    def test_drop_off_rate_zero_total(self) -> None:
        """drop_off_rate is 0.0 when total_count is 0."""
        node = FlowTreeNode(event="Empty", type="NORMAL", step_number=0, total_count=0)
        assert node.drop_off_rate == 0.0


# =============================================================================
# T050: FlowTreeNode methods
# =============================================================================


class TestFlowTreeNodeAllPaths:
    """Tests for FlowTreeNode.all_paths()."""

    def test_leaf_returns_single_path(self) -> None:
        """Leaf node returns one path containing just itself."""
        leaf = _leaf_node()
        paths = leaf.all_paths()
        assert len(paths) == 1
        assert len(paths[0]) == 1
        assert paths[0][0] is leaf

    def test_sample_tree_path_count(self) -> None:
        """Sample tree has 4 root-to-leaf paths."""
        paths = _sample_tree().all_paths()
        assert len(paths) == 4

    def test_paths_start_with_root(self) -> None:
        """Every path starts with the root node."""
        tree = _sample_tree()
        for path in tree.all_paths():
            assert path[0].event == "Login"

    def test_paths_end_with_leaves(self) -> None:
        """Every path ends with a leaf node (no children)."""
        tree = _sample_tree()
        for path in tree.all_paths():
            assert path[-1].children == ()

    def test_paths_contain_node_chain(self) -> None:
        """Paths contain FlowTreeNode objects, not just event names."""
        tree = _sample_tree()
        paths = tree.all_paths()
        # Find Login -> Search -> Purchase path
        purchase_paths = [p for p in paths if p[-1].event == "Purchase"]
        assert len(purchase_paths) == 2
        # Check we can access counts along the path
        search_purchase = [p for p in purchase_paths if p[1].event == "Search"][0]
        assert search_purchase[0].total_count == 1000  # Login
        assert search_purchase[1].total_count == 600  # Search
        assert search_purchase[2].total_count == 400  # Purchase


class TestFlowTreeNodeFind:
    """Tests for FlowTreeNode.find()."""

    def test_find_root_event(self) -> None:
        """find() returns root when searching for root event."""
        tree = _sample_tree()
        results = tree.find("Login")
        assert len(results) == 1
        assert results[0].event == "Login"

    def test_find_multiple_matches(self) -> None:
        """find() returns all nodes matching event name."""
        tree = _sample_tree()
        results = tree.find("Purchase")
        assert len(results) == 2
        assert all(n.event == "Purchase" for n in results)

    def test_find_no_match(self) -> None:
        """find() returns empty list for non-existent event."""
        tree = _sample_tree()
        assert tree.find("NonExistent") == []

    def test_find_preserves_node_data(self) -> None:
        """Found nodes retain their original attributes."""
        tree = _sample_tree()
        purchases = tree.find("Purchase")
        counts = sorted(p.total_count for p in purchases)
        assert counts == [200, 400]


class TestFlowTreeNodeFlatten:
    """Tests for FlowTreeNode.flatten()."""

    def test_leaf_flattens_to_single(self) -> None:
        """Leaf flatten returns list of one."""
        leaf = _leaf_node()
        assert len(leaf.flatten()) == 1
        assert leaf.flatten()[0] is leaf

    def test_flatten_count_matches_node_count(self) -> None:
        """flatten() length equals node_count."""
        tree = _sample_tree()
        assert len(tree.flatten()) == tree.node_count

    def test_flatten_is_preorder(self) -> None:
        """flatten() returns nodes in pre-order (root first)."""
        tree = _sample_tree()
        flat = tree.flatten()
        assert flat[0].event == "Login"
        # Root's first child (Search) comes before root's second child (Browse)
        search_idx = next(i for i, n in enumerate(flat) if n.event == "Search")
        browse_idx = next(i for i, n in enumerate(flat) if n.event == "Browse")
        assert search_idx < browse_idx


class TestFlowTreeNodeToDict:
    """Tests for FlowTreeNode.to_dict()."""

    def test_leaf_to_dict_keys(self) -> None:
        """to_dict() includes all expected keys."""
        d = _leaf_node().to_dict()
        expected_keys = {
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
        assert set(d.keys()) == expected_keys

    def test_leaf_to_dict_values(self) -> None:
        """to_dict() values match node attributes."""
        leaf = _leaf_node()
        d = leaf.to_dict()
        assert d["event"] == "Purchase"
        assert d["total_count"] == 100
        assert d["children"] == []

    def test_recursive_to_dict(self) -> None:
        """to_dict() recursively serializes children."""
        tree = _sample_tree()
        d = tree.to_dict()
        assert len(d["children"]) == 3
        assert d["children"][0]["event"] == "Search"
        assert len(d["children"][0]["children"]) == 2
        assert d["children"][0]["children"][0]["event"] == "Purchase"


class TestFlowTreeNodeRender:
    """Tests for FlowTreeNode.render()."""

    def test_leaf_render(self) -> None:
        """Leaf node renders as single line."""
        rendered = _leaf_node().render()
        assert "Purchase" in rendered
        assert "100" in rendered

    def test_sample_tree_render_contains_all_events(self) -> None:
        """render() output contains all event names."""
        rendered = _sample_tree().render()
        assert "Login" in rendered
        assert "Search" in rendered
        assert "Browse" in rendered
        assert "Purchase" in rendered
        assert "DROPOFF" in rendered

    def test_render_uses_box_drawing(self) -> None:
        """render() uses box-drawing characters for tree structure."""
        rendered = _sample_tree().render()
        # Should contain tree connectors
        assert "├──" in rendered or "└──" in rendered


# =============================================================================
# T050: FlowTreeNode.to_anytree()
# =============================================================================


class TestFlowTreeNodeToAnytree:
    """Tests for FlowTreeNode.to_anytree() conversion."""

    def test_returns_anynode(self) -> None:
        """to_anytree() returns an anytree.AnyNode."""
        at = _leaf_node().to_anytree()
        assert isinstance(at, AnyNode)

    def test_leaf_has_no_parent(self) -> None:
        """Root node's anytree representation has no parent."""
        at = _leaf_node().to_anytree()
        assert at.parent is None

    def test_leaf_has_no_children(self) -> None:
        """Leaf node's anytree representation has no children."""
        at = _leaf_node().to_anytree()
        assert at.children == ()

    def test_attributes_copied(self) -> None:
        """to_anytree() copies all key attributes."""
        at = _sample_tree().to_anytree()
        assert at.event == "Login"
        assert at.type == "ANCHOR"
        assert at.step_number == 0
        assert at.total_count == 1000
        assert at.drop_off_count == 50
        assert at.converted_count == 950

    def test_children_linked(self) -> None:
        """to_anytree() children have correct parent references."""
        at = _sample_tree().to_anytree()
        assert len(at.children) == 3
        for child in at.children:
            assert child.parent is at

    def test_node_count_matches(self) -> None:
        """anytree node count matches FlowTreeNode.node_count."""
        tree = _sample_tree()
        at = tree.to_anytree()
        anytree_count = len(list(PreOrderIter(at)))
        assert anytree_count == tree.node_count

    def test_parent_refs_work_deeply(self) -> None:
        """Deep nodes have correct parent chain via anytree."""
        at = _sample_tree().to_anytree()
        # Find a Purchase node under Search
        search_node = [c for c in at.children if c.event == "Search"][0]
        purchase_node = [c for c in search_node.children if c.event == "Purchase"][0]
        assert purchase_node.parent is search_node
        assert purchase_node.parent.parent is at

    def test_path_from_leaf_to_root(self) -> None:
        """anytree .path gives full ancestor chain (root to node)."""
        at = _sample_tree().to_anytree()
        search_node = [c for c in at.children if c.event == "Search"][0]
        purchase_node = [c for c in search_node.children if c.event == "Purchase"][0]
        path_events = [n.event for n in purchase_node.path]
        assert path_events == ["Login", "Search", "Purchase"]


# =============================================================================
# T051: FlowQueryResult tree mode
# =============================================================================


def _make_tree_result(**overrides: Any) -> FlowQueryResult:
    """Build a default-valid FlowQueryResult in tree mode for testing."""
    from mixpanel_headless.types import FlowQueryResult

    defaults: dict[str, Any] = {
        "computed_at": "2025-01-15T10:00:00",
        "steps": [],
        "flows": [],
        "breakdowns": [],
        "overall_conversion_rate": 0.0,
        "params": {},
        "meta": {},
        "mode": "tree",
        "trees": [_sample_tree()],
    }
    defaults.update(overrides)
    return FlowQueryResult(**defaults)


class TestFlowQueryResultTreeMode:
    """Tests for FlowQueryResult with mode='tree'."""

    def test_accepts_tree_mode(self) -> None:
        """FlowQueryResult can be constructed with mode='tree'."""
        r = _make_tree_result()
        assert r.mode == "tree"

    def test_trees_field_populated(self) -> None:
        """trees field contains FlowTreeNode objects."""
        r = _make_tree_result()
        assert len(r.trees) == 1
        assert isinstance(r.trees[0], FlowTreeNode)
        assert r.trees[0].event == "Login"

    def test_trees_default_empty(self) -> None:
        """trees defaults to empty list when not provided."""
        from mixpanel_headless.types import FlowQueryResult

        r = FlowQueryResult(
            computed_at="2025-01-15T10:00:00",
            mode="tree",
        )
        assert r.trees == []

    def test_df_tree_mode_columns(self) -> None:
        """df in tree mode has the expected columns."""
        r = _make_tree_result()
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
        assert list(r.df.columns) == expected_cols

    def test_df_tree_mode_row_count(self) -> None:
        """df row count equals total node_count across all trees."""
        r = _make_tree_result()
        assert len(r.df) == _sample_tree().node_count

    def test_df_tree_mode_path_column(self) -> None:
        """path column contains ' > ' separated event names."""
        r = _make_tree_result()
        paths = r.df["path"].tolist()
        assert "Login" in paths  # root
        assert "Login > Search" in paths
        assert "Login > Search > Purchase" in paths
        assert "Login > Browse > Purchase" in paths

    def test_df_tree_mode_cached(self) -> None:
        """Second df access returns the same cached object."""
        r = _make_tree_result()
        df1 = r.df
        df2 = r.df
        assert df1 is df2

    def test_df_tree_mode_empty_trees(self) -> None:
        """Empty trees produces empty df with correct columns."""
        r = _make_tree_result(trees=[])
        assert r.df.empty
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
        assert list(r.df.columns) == expected_cols

    def test_to_dict_includes_trees(self) -> None:
        """to_dict() includes trees key with serialized tree dicts."""
        r = _make_tree_result()
        d = r.to_dict()
        assert "trees" in d
        assert len(d["trees"]) == 1
        assert d["trees"][0]["event"] == "Login"
        assert len(d["trees"][0]["children"]) == 3

    def test_anytree_property_returns_list(self) -> None:
        """anytree property returns a list of AnyNode roots."""
        from anytree import AnyNode

        r = _make_tree_result()
        roots = r.anytree
        assert isinstance(roots, list)
        assert len(roots) == 1
        assert isinstance(roots[0], AnyNode)
        assert roots[0].event == "Login"

    def test_anytree_property_cached(self) -> None:
        """Second anytree access returns the same cached object."""
        r = _make_tree_result()
        a1 = r.anytree
        a2 = r.anytree
        assert a1 is a2

    def test_anytree_property_empty_trees(self) -> None:
        """Empty trees produces empty anytree list."""
        r = _make_tree_result(trees=[])
        assert r.anytree == []

    def test_multiple_trees(self) -> None:
        """FlowQueryResult supports multiple trees (one per segment)."""
        tree2 = FlowTreeNode(
            event="Signup",
            type="ANCHOR",
            step_number=0,
            total_count=500,
            drop_off_count=25,
            converted_count=475,
        )
        r = _make_tree_result(trees=[_sample_tree(), tree2])
        assert len(r.trees) == 2
        assert len(r.anytree) == 2
        # df includes nodes from both trees
        assert len(r.df) == _sample_tree().node_count + tree2.node_count
        # tree_index distinguishes them
        assert set(r.df["tree_index"].unique()) == {0, 1}


# =============================================================================
# T052: Public exports
# =============================================================================


class TestFlowTreeNodeExports:
    """Tests for FlowTreeNode public export from mixpanel_headless."""

    def test_importable_from_package(self) -> None:
        """FlowTreeNode can be imported from mixpanel_headless."""
        from mixpanel_headless import FlowTreeNode as Imported

        assert Imported is FlowTreeNode

    def test_in_all(self) -> None:
        """FlowTreeNode is listed in mixpanel_headless.__all__."""
        assert "FlowTreeNode" in mixpanel_headless.__all__
