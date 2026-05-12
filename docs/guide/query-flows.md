# Flow Queries

Build typed flow path analysis against Mixpanel's Insights engine — define anchor events, control forward/reverse step depth, apply per-step filters, and analyze user paths inline without creating saved reports first.

!!! tip "Recommended"
    `Workspace.query_flow()` is the typed way to run flow analysis programmatically. It supports capabilities not available through the legacy `query_saved_flows()` method, including per-step filters, direction controls, multiple visualization modes, NetworkX graph output, and typed result analysis.

## When to Use `query_flow()`

`query_flow()` builds flow bookmark params and posts them to the Insights engine. The legacy `query_saved_flows()` method queries a pre-existing saved Flows report by bookmark ID. Use `query_flow()` when you need any of the capabilities in the right column:

| Capability | Legacy `query_saved_flows()` | `query_flow()` |
|---|---|---|
| Basic flow analysis | `query_saved_flows(bookmark_id=123)` | `query_flow("Purchase")` |
| Ad-hoc anchor events | Not available — requires saved report | `query_flow("Purchase")` or `query_flow(["Signup", "Purchase"])` |
| Per-step filters | Not available | `FlowStep("Purchase", filters=[...])` |
| Direction control | Not available | `forward=3, reverse=1` |
| Per-step direction | Not available | `FlowStep("Purchase", forward=5)` |
| Visualization modes | Not available | `mode="sankey"`, `"paths"`, or `"tree"` |
| NetworkX graph | Not available | `result.graph` — full DiGraph |
| Top transitions | Not available | `result.top_transitions(10)` |
| Drop-off summary | Not available | `result.drop_off_summary()` |
| Tree traversal | Not available | `result.trees` — recursive `FlowTreeNode` |
| Save query as a report | N/A | `result.params` → `create_bookmark()` |

Use the legacy `query_saved_flows()` when:

- You need to query an existing saved Flows report by bookmark ID → `query_saved_flows(bookmark_id=123)`

## Getting Started

The simplest possible flow query — what happens after a Purchase event, last 30 days:

```python
import mixpanel_headless as mp

ws = mp.Workspace()

result = ws.query_flow("Purchase")
print(result.nodes_df.head())
#   step           event       type  count anchor_type
# 0    0        Purchase     ANCHOR   5000      NORMAL
# 1    1    View Receipt    FORWARD   3200      NORMAL
# 2    1       Add to Cart FORWARD   1800      NORMAL

print(result.edges_df.head())
#   source_step source_event  target_step  target_event  count target_type
# 0           0     Purchase            1  View Receipt   3200     FORWARD
# 1           0     Purchase            1   Add to Cart   1800     FORWARD
```

Add direction controls and time range:

```python
# 3 steps forward and 1 step back from Purchase
result = ws.query_flow("Purchase", forward=3, reverse=1, last=90)

# Top user paths
print(result.top_transitions(5))
# [("Purchase", "View Receipt", 3200), ("View Receipt", "Checkout", 2100), ...]

# Specific date range
result = ws.query_flow(
    "Purchase",
    from_date="2025-01-01",
    to_date="2025-03-31",
)
```

## Steps

### Plain Strings

The simplest way to define anchor events — pass event names as strings:

```python
# Single anchor event
result = ws.query_flow("Purchase")

# Multiple anchor events
result = ws.query_flow(["Signup", "Purchase"])
```

Each string becomes an anchor step in the flow — Mixpanel traces user paths forward and backward from these events.

### The `FlowStep` Class

For per-step configuration with filters and direction overrides, use `FlowStep` objects:

```python
from mixpanel_headless import FlowStep, Filter

result = ws.query_flow(
    FlowStep(
        "Purchase",
        forward=5,
        reverse=2,
        filters=[Filter.greater_than("amount", 50)],
    ),
)
```

`FlowStep` fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `event` | `str` | (required) | Mixpanel event name to anchor on |
| `forward` | `int \| None` | `None` | Forward steps for this step (0-5, overrides global) |
| `reverse` | `int \| None` | `None` | Reverse steps for this step (0-5, overrides global) |
| `label` | `str \| None` | `None` | Display label (defaults to event name) |
| `filters` | `list[Filter] \| None` | `None` | Per-step filter conditions |
| `filters_combinator` | `"all" \| "any"` | `"all"` | How per-step filters combine (AND/OR) |

Plain strings and `FlowStep` objects can be mixed freely:

```python
result = ws.query_flow([
    "Signup",  # plain string — no overrides needed
    FlowStep("Purchase", filters=[Filter.equals("country", "US")]),
])
```

### Per-Step Filters

Apply filters to individual steps using `FlowStep.filters`. These restrict which events count for that specific anchor:

```python
from mixpanel_headless import FlowStep, Filter

result = ws.query_flow(
    FlowStep(
        "Purchase",
        filters=[
            Filter.equals("country", "US"),
            Filter.greater_than("amount", 25),
        ],
    ),
)
```

By default, multiple per-step filters combine with AND logic. Use `filters_combinator="any"` for OR logic:

```python
result = ws.query_flow(
    FlowStep(
        "Purchase",
        filters=[
            Filter.equals("country", "US"),
            Filter.equals("country", "CA"),
        ],
        filters_combinator="any",  # match US OR CA
    ),
)
```

See [Insights Queries — Filters](query.md#filters) for the full list of `Filter` factory methods.

### Filtering with `where=`

Restrict flow analysis to a subset of users using the `where=` parameter. Flows support both cohort filters and property filters:

```python
from mixpanel_headless import Filter, CohortCriteria, CohortDefinition

# Cohort filter — what do power users do after purchasing?
result = ws.query_flow(
    "Purchase",
    forward=3,
    where=Filter.in_cohort(123, "Power Users"),
)

# Property filter — iOS users only
result = ws.query_flow(
    "Purchase",
    where=Filter.equals("platform", "iOS"),
    last=30,
)

# Inline cohort — what paths do frequent buyers take?
frequent_buyers = CohortDefinition(
    CohortCriteria.did_event("Purchase", at_least=5, within_days=30)
)
result = ws.query_flow(
    "Purchase",
    where=Filter.in_cohort(frequent_buyers, name="Frequent Buyers"),
)
```

!!! note
    Cohort breakdowns (`CohortBreakdown`) and custom properties (`CustomPropertyRef`, `InlineCustomProperty`) are not supported in flows.

See [Insights Queries — Cohort Filters](query.md#cohort-filters) for the full cohort filter reference and [Insights Queries — Filters](query.md#filters) for all `Filter` factory methods.

## Direction

Control how many steps forward and backward from the anchor Mixpanel traces:

| Parameter | Range | Default | Description |
|---|---|---|---|
| `forward` | 0–5 | 3 | Steps traced after the anchor event |
| `reverse` | 0–5 | 0 | Steps traced before the anchor event |

```python
# Forward-only (default) — what happens after Purchase?
result = ws.query_flow("Purchase", forward=3)

# Reverse-only — what led to Purchase?
result = ws.query_flow("Purchase", forward=0, reverse=3)

# Both directions — context around Purchase
result = ws.query_flow("Purchase", forward=3, reverse=2)
```

At least one direction must be nonzero — a flow with `forward=0, reverse=0` raises a validation error.

### Per-Step Direction Overrides

Each `FlowStep` can override the global direction settings:

```python
from mixpanel_headless import FlowStep

result = ws.query_flow(
    [
        FlowStep("Signup", forward=5),       # trace 5 steps forward from Signup
        FlowStep("Purchase", reverse=3),     # trace 3 steps back from Purchase
    ],
    forward=2,  # global default (used when step doesn't override)
    reverse=0,  # global default
)
```

When a step provides `forward` or `reverse`, that value is used for that step. When `None`, the global value applies.

## Visualization Modes

The `mode` parameter controls how flow data is structured and returned:

| Mode | `flows_merge_type` | Use case |
|---|---|---|
| `"sankey"` (default) | `"graph"` | Aggregated node/edge graph — best for Sankey diagrams |
| `"paths"` | `"list"` | Top user paths as ranked sequences |
| `"tree"` | `"tree"` | Recursive tree from anchor — detailed node-level analysis |

```python
# Sankey mode (default) — aggregated graph
result = ws.query_flow("Purchase", mode="sankey")
print(result.nodes_df)   # node-level data
print(result.edges_df)   # edge-level transitions
print(result.graph)       # NetworkX DiGraph

# Paths mode — top user paths
result = ws.query_flow("Purchase", mode="paths")
print(result.df)          # ranked path sequences

# Tree mode — recursive tree structure
result = ws.query_flow("Purchase", mode="tree")
for tree in result.trees:
    print(f"{tree.event}: {tree.total_count} users")
    for child in tree.children:
        print(f"  → {child.event}: {child.total_count}")
```

## Conversion Window

Control the maximum time between the first and last step in the flow:

```python
# 7-day conversion window (default)
result = ws.query_flow("Purchase", conversion_window=7)

# 30-day window
result = ws.query_flow("Purchase", conversion_window=30, conversion_window_unit="day")

# Weekly window
result = ws.query_flow("Purchase", conversion_window=2, conversion_window_unit="week")

# Session-based window
result = ws.query_flow("Purchase", conversion_window=1, conversion_window_unit="session")
```

| Unit | Description |
|---|---|
| `"day"` (default) | Window measured in days |
| `"week"` | Window measured in weeks |
| `"month"` | Window measured in months |
| `"session"` | Window measured in sessions |

## Count Type

The `count_type` parameter controls how users are counted:

| Count type | What it measures |
|---|---|
| `"unique"` (default) | Unique users who traversed each path |
| `"total"` | Total event occurrences (one user can count multiple times) |
| `"session"` | Unique sessions containing the path |

```python
# Unique users (default)
result = ws.query_flow("Purchase", count_type="unique")

# Total events
result = ws.query_flow("Purchase", count_type="total")

# Session-based
result = ws.query_flow("Purchase", count_type="session")
```

## Additional Options

### Data Group

Scope flow analysis to a specific data group:

```python
# Scope to a data group
result = ws.query_flow("Purchase", data_group_id=42, last=30)
```

### Cardinality

Control how many unique next/previous events are shown per step. Higher values show more granular paths; lower values collapse rare paths:

```python
# Show top 5 events per step (default is 3)
result = ws.query_flow("Purchase", cardinality=5)

# Maximum granularity
result = ws.query_flow("Purchase", cardinality=50)
```

Range: 1–50.

### Collapse Repeated Events

Merge consecutive occurrences of the same event into a single step:

```python
# Collapse repeated events (e.g., multiple "Page View" in a row)
result = ws.query_flow("Purchase", collapse_repeated=True)
```

### Hidden Events

Exclude specific events from the flow analysis:

```python
# Hide noisy events from the flow
result = ws.query_flow(
    "Purchase",
    hidden_events=["Session Start", "Page View", "Heartbeat"],
)
```

## Time Ranges

### Relative (Default)

By default, `query_flow()` returns the last 30 days. Customize with `last`:

```python
# Last 7 days
result = ws.query_flow("Purchase", last=7)

# Last 90 days
result = ws.query_flow("Purchase", last=90)
```

### Absolute

Specify explicit start and end dates:

```python
# Q1 2025
result = ws.query_flow(
    "Purchase",
    from_date="2025-01-01",
    to_date="2025-03-31",
)
```

Dates must be in `YYYY-MM-DD` format. When `from_date` is provided without `to_date`, the end date defaults to today.

## Working with Results

### `FlowQueryResult`

`query_flow()` returns a `FlowQueryResult` with mode-aware properties:

```python
result = ws.query_flow("Purchase", forward=3, reverse=1, last=90)

# Node data — one row per node in the flow
result.nodes_df
#   step           event       type  count anchor_type  is_custom_event  conversion_rate_change
# 0    0        Purchase     ANCHOR   5000      NORMAL            False                     NaN

# Edge data — transitions between nodes
result.edges_df
#   source_step source_event  target_step  target_event  count target_type

# NetworkX graph — for programmatic path analysis
g = result.graph
print(f"Nodes: {g.number_of_nodes()}, Edges: {g.number_of_edges()}")

# Top transitions by volume
result.top_transitions(5)
# [("Purchase", "View Receipt", 3200), ("View Receipt", "Checkout", 2100), ...]

# Per-step drop-off summary
result.drop_off_summary()
# {"steps": [{"step": 0, "total": 5000, "dropoff": 0, "rate": 0.0}, ...]}

# Overall conversion rate
result.overall_conversion_rate  # 0.42

# Visualization mode
result.mode  # "sankey"

# API metadata
result.computed_at  # "2025-03-31T12:00:00.000000+00:00"
result.meta         # {"sampling_factor": 1.0, ...}

# Generated bookmark params (for debugging or persistence)
result.params       # dict — the full bookmark JSON sent to API
```

### Node DataFrame (`nodes_df`)

One row per node in the flow graph:

| Column | Description |
|---|---|
| `step` | Step index (0 = anchor, positive = forward, negative = reverse) |
| `event` | Event name |
| `type` | Node type: `ANCHOR`, `FORWARD`, `REVERSE`, `DROPOFF`, `PRUNED` |
| `count` | Number of users at this node |
| `anchor_type` | `NORMAL`, `RELATIVE_FORWARD`, or `RELATIVE_REVERSE` |
| `is_custom_event` | Whether this is a computed/custom event |
| `conversion_rate_change` | Change in conversion rate from previous step |

### Edge DataFrame (`edges_df`)

One row per transition between nodes:

| Column | Description |
|---|---|
| `source_step` | Source node step index |
| `source_event` | Source event name |
| `target_step` | Target node step index |
| `target_event` | Target event name |
| `count` | Number of users who made this transition |
| `target_type` | Target node type |

### NetworkX Graph (`graph`)

A `networkx.DiGraph` for programmatic path analysis:

```python
import networkx as nx

g = result.graph

# Shortest paths from anchor
anchor_nodes = [n for n, d in g.nodes(data=True) if d.get("type") == "ANCHOR"]

# All paths from anchor to a specific event
for path in nx.all_simple_paths(g, source=anchor_nodes[0], target="Checkout@2"):
    print(" → ".join(path))

# Highest-traffic edges
for u, v, data in sorted(g.edges(data=True), key=lambda x: x[2]["count"], reverse=True)[:5]:
    print(f"{u} → {v}: {data['count']} users")
```

Nodes are keyed as `"{event}@{step}"` with attributes `count`, `type`, and `step`. Edges have a `count` attribute.

#### What the graph unlocks

The DiGraph turns flow data into a structure that algorithms can reason about — answering questions no dashboard can:

```python
import networkx as nx

g = result.graph

# "What's the shortest path from Signup to Purchase?"
path = nx.shortest_path(g, "Signup@0", "Purchase@3")
# → ["Signup@0", "Browse@1", "Add to Cart@2", "Purchase@3"]

# "Which event is the biggest bottleneck — the one most paths must pass through?"
betweenness = nx.betweenness_centrality(g, weight="count")
bottleneck = max(betweenness, key=betweenness.get)

# "Are users looping back?"
cycles = list(nx.simple_cycles(g))

# "What fraction of Add to Cart users actually Purchase?"
cart_out = sum(d["count"] for _, _, d in g.out_edges("Add to Cart@2", data=True))
to_purchase = g.edges["Add to Cart@2", "Purchase@3"]["count"]
micro_conversion = to_purchase / cart_out

# "Which events are dead ends — reachable but leading nowhere?"
dead_ends = [n for n in g.nodes() if g.out_degree(n) == 0 and g.in_degree(n) > 0]
```

Every graph theory algorithm in NetworkX — shortest paths, centrality, community detection, cycle detection, max-flow — works out of the box on flow data. This is particularly powerful for AI agents: they can programmatically explore path structure, identify optimization opportunities, and quantify the impact of removing or adding steps, without any visualization required.

### Tree Mode Results

When `mode="tree"`, results include `FlowTreeNode` objects:

```python
result = ws.query_flow("Purchase", mode="tree")

for tree in result.trees:
    print(f"{tree.event}: {tree.total_count} users")
    print(f"  Conversion: {tree.conversion_rate:.1%}")
    print(f"  Drop-off: {tree.drop_off_count}")
    print(f"  Depth: {tree.depth}")

    # Traverse children
    for child in tree.children:
        print(f"  → {child.event}: {child.total_count}")

    # All paths from root to leaves
    for path in tree.all_paths():
        print(" → ".join(node.event for node in path))
```

`FlowTreeNode` fields:

| Field | Type | Description |
|---|---|---|
| `event` | `str` | Event name |
| `type` | `str` | `ANCHOR`, `NORMAL`, `DROPOFF`, `PRUNED`, `FORWARD`, `REVERSE` |
| `step_number` | `int` | Zero-based step index |
| `total_count` | `int` | Total users at this node |
| `drop_off_count` | `int` | Users who dropped off |
| `converted_count` | `int` | Users who continued |
| `children` | `tuple[FlowTreeNode, ...]` | Child nodes |
| `conversion_rate` | `float` | Property: `converted_count / total_count` |
| `depth` | `int` | Property: maximum depth of subtree |
| `node_count` | `int` | Property: total nodes in subtree |

`FlowTreeNode` methods:

| Method | Returns | Description |
|---|---|---|
| `all_paths()` | `list[list[FlowTreeNode]]` | All root-to-leaf paths through the subtree |
| `flatten()` | `list[FlowTreeNode]` | Preorder traversal of all nodes |
| `find(event)` | `list[FlowTreeNode]` | All nodes matching an event name |
| `render()` | `str` | Box-drawing ASCII visualization |
| `to_dict()` | `dict` | JSON-serializable recursive dictionary |
| `to_anytree()` | `AnyNode` | Convert to [`anytree`](https://anytree.readthedocs.io/) node for rendering and export |

#### What the tree unlocks

Tree mode gives each node its own `total_count`, `converted_count`, and `drop_off_count` — the full decision tree at every branching point. This lets you answer questions about *where exactly* users diverge:

```python
result = ws.query_flow("Signup", mode="tree", forward=4)

for tree in result.trees:
    # "At each step, what percentage of users take each branch?"
    for node in tree.flatten():
        if node.children:
            print(f"\nAfter {node.event} ({node.total_count} users):")
            for child in sorted(
                node.children, key=lambda c: c.total_count, reverse=True
            ):
                pct = child.total_count / node.total_count * 100
                print(f"  → {child.event}: {pct:.0f}% ({child.total_count})")

    # "What's the highest-converting complete path?"
    best_path = max(tree.all_paths(), key=lambda p: p[-1].converted_count)
    print(" → ".join(f"{n.event}({n.conversion_rate:.0%})" for n in best_path))

    # "Where is the single biggest drop-off?"
    worst = max(tree.flatten(), key=lambda n: n.drop_off_count)
    print(f"Biggest drop-off: {worst.event} — {worst.drop_off_count} users lost")

    # Render the full decision tree as ASCII
    print(tree.render())
    # Purchase (5000)
    # ├── View Receipt (3200)
    # │   ├── Rate App (1100)
    # │   └── Browse More (2100)
    # └── Contact Support (800)
    #     └── ⊘ Drop-off (800)
```

The tree is uniquely suited to *branching analysis* — understanding not just the top path, but what fraction of users chose each alternative at every fork.

#### anytree Integration

`FlowTreeNode` is frozen and children-only — you can traverse downward, but you can't ask a node "how did I get here?" Converting to [`anytree`](https://anytree.readthedocs.io/) adds **parent references**, **root-to-node paths**, **tree-wide search**, and **Graphviz export**, unlocking questions that require upward or lateral navigation.

Use `to_anytree()` on any single `FlowTreeNode`, or `result.anytree` for the full list of converted roots:

```python
from anytree import RenderTree, findall

result = ws.query_flow("Purchase", mode="tree", forward=3)
root = result.anytree[0]  # converted AnyNode root

# Render the full tree with counts
for pre, _, node in RenderTree(root):
    print(f"{pre}{node.event} ({node.total_count})")
# Purchase (5000)
# ├── View Receipt (3200)
# │   ├── Rate App (1100)
# │   └── Browse More (2100)
# └── Contact Support (800)
```

##### Tracing backward from any node

The killer feature: given a node deep in the tree, trace the exact path that led there — something `FlowTreeNode` alone can't do.

```python
from anytree import findall

# Find all drop-off points and trace how users got there
dropoffs = findall(root, filter_=lambda n: n.type == "DROPOFF")
for node in dropoffs:
    # .path gives the full root-to-node chain
    journey = " → ".join(n.event for n in node.path)
    print(f"{journey} ({node.drop_off_count} users lost)")

# Parent references — "what came immediately before this event?"
support = findall(root, filter_=lambda n: n.event == "Contact Support")[0]
print(f"{support.event} ← {support.parent.event}")
# Contact Support ← Purchase
```

##### Node introspection

Every converted node exposes properties that make tree analysis concise:

```python
from anytree import findall

checkout = findall(root, filter_=lambda n: n.event == "Checkout")[0]

checkout.depth       # 2 — distance from anchor
checkout.ancestors   # (Purchase, View Receipt) — full chain above
checkout.siblings    # other events at the same branching point
checkout.is_leaf     # True if no further steps follow
root.leaves          # all terminal nodes — drop-offs and end-of-funnel
root.height          # deepest path length in the tree
```

##### Graphviz export

Export the flow tree as a visual diagram — especially useful for sharing with stakeholders or embedding in reports:

```python
from anytree.exporter import UniqueDotExporter

# Basic export — renders to PNG via Graphviz
UniqueDotExporter(root).to_picture("flow.png")

# Custom formatting — size nodes by user count, highlight drop-offs
UniqueDotExporter(
    root,
    nodenamefunc=lambda n: f"{n.event}\n({n.total_count:,})",
    nodeattrfunc=lambda n: (
        'shape=box, style=filled, fillcolor="#ff6b6b"'
        if n.type == "DROPOFF"
        else 'shape=box, style=filled, fillcolor="#4ecdc4"'
    ),
).to_picture("flow_colored.png")
```

!!! note
    Graphviz must be installed on your system (`brew install graphviz` / `apt install graphviz`) for `to_picture()` to work. Alternatively, use `to_dotfile("flow.dot")` to generate the DOT source for rendering elsewhere.

### Persisting as a Saved Report

The generated bookmark params can be saved as a Mixpanel report:

```python
from mixpanel_headless import CreateBookmarkParams

result = ws.query_flow("Purchase", forward=3, reverse=1)

ws.create_bookmark(CreateBookmarkParams(
    name="Purchase Flow Analysis",
    bookmark_type="flows",
    params=result.params,
))
```

### Debugging

Inspect `result.params` to see the exact bookmark JSON sent to the API:

```python
import json

result = ws.query_flow("Purchase")
print(json.dumps(result.params, indent=2))
```

## Validation

`query_flow()` validates all parameter combinations **before** making an API call and raises `BookmarkValidationError` with descriptive messages:

| Rule | Error code | Error message |
|---|---|---|
| No steps provided | `FL1_EMPTY_STEPS` | At least one step is required |
| Empty step event name | `FL2_EMPTY_STEP_EVENT` | Step event name must be a non-empty string |
| Control chars in event name | `FL2_CONTROL_CHAR_STEP_EVENT` | Step event name contains control characters |
| Forward out of range | `FL3_FORWARD_RANGE` | forward must be between 0 and 5 |
| Reverse out of range | `FL4_REVERSE_RANGE` | reverse must be between 0 and 5 |
| Both directions zero | `FL5_NO_DIRECTION` | At least one of forward or reverse must be nonzero |
| Cardinality out of range | `FL6_CARDINALITY_RANGE` | cardinality must be between 1 and 50 |
| Invalid count type | `FL7_INVALID_COUNT_TYPE` | Must be one of: unique, total, session |
| Invalid window unit | `FL8_INVALID_WINDOW_UNIT` | Must be one of: day, week, month, session |
| Invalid date range | `FL9_INVALID_DATE_RANGE` | Invalid date range configuration |
| Invalid mode | `FL10_INVALID_MODE` | Must be one of: sankey, paths, tree |

Errors are collected — all validation issues are reported at once, not just the first:

```python
from mixpanel_headless import BookmarkValidationError

try:
    ws.query_flow("", forward=10, reverse=-1)
except BookmarkValidationError as e:
    for error in e.errors:
        print(f"[{error.code}] {error.path}: {error.message}")
    # [FL2_EMPTY_STEP_EVENT] steps[0].event: Step event name must be a non-empty string
    # [FL3_FORWARD_RANGE] forward: forward must be between 0 and 5
    # [FL4_REVERSE_RANGE] reverse: reverse must be between 0 and 5
```

## Complete Examples

### E-Commerce Checkout Flow

```python
import mixpanel_headless as mp
from mixpanel_headless import FlowStep, Filter

ws = mp.Workspace()

# What happens after users add items to cart?
result = ws.query_flow(
    FlowStep(
        "Add to Cart",
        forward=4,
        filters=[Filter.greater_than("item_price", 10)],
    ),
    conversion_window=7,
    last=90,
    hidden_events=["Session Start", "Page View"],
)

# Top conversion paths
for src, tgt, count in result.top_transitions(10):
    print(f"  {src} → {tgt}: {count:,} users")

# Drop-off analysis
summary = result.drop_off_summary()
for step in summary["steps"]:
    print(f"  Step {step['step']}: {step['dropoff']:,} dropped ({step['rate']:.1%})")
```

### User Onboarding Paths

```python
# What do new users do after signing up?
result = ws.query_flow(
    "Signup",
    forward=5,
    cardinality=10,
    last=30,
    collapse_repeated=True,
)

# Visualize as NetworkX graph
g = result.graph
print(f"Discovered {g.number_of_nodes()} unique steps")
print(f"Discovered {g.number_of_edges()} unique transitions")

# Find most common path from signup
import networkx as nx
for node in g.successors("Signup@0"):
    weight = g.edges["Signup@0", node]["count"]
    print(f"  Signup → {node}: {weight:,} users")
```

### Reverse Flow Analysis

```python
# What led users to churn?
result = ws.query_flow(
    "Cancel Subscription",
    forward=0,
    reverse=5,
    count_type="unique",
    last=90,
)

# Analyze the reverse path
print(result.nodes_df[result.nodes_df["type"] == "REVERSE"])
```

### Tree Mode Exploration

```python
# Detailed tree analysis of purchase paths
result = ws.query_flow("Purchase", mode="tree", forward=3)

for tree in result.trees:
    print(f"\nAnchor: {tree.event} ({tree.total_count:,} users)")
    print(f"  Tree depth: {tree.depth}")
    print(f"  Total nodes: {tree.node_count}")

    # Print all complete paths
    for path in tree.all_paths():
        path_str = " → ".join(f"{n.event}({n.total_count})" for n in path)
        print(f"  {path_str}")
```

## Generating Params Without Querying

Use `build_flow_params()` to generate bookmark params without making an API call — useful for debugging, inspecting the generated JSON, or saving queries as reports:

```python
# Same arguments as query_flow(), returns dict instead of FlowQueryResult
params = ws.build_flow_params(
    "Purchase",
    forward=3,
    reverse=1,
    conversion_window=7,
    last=90,
)

import json
print(json.dumps(params, indent=2))  # inspect the generated bookmark JSON

# Save as a report directly from params
from mixpanel_headless import CreateBookmarkParams

ws.create_bookmark(CreateBookmarkParams(
    name="Purchase Flow (3 forward, 1 reverse)",
    bookmark_type="flows",
    params=params,
))
```

## Flow Segments

Break flow results down by a property, cohort, or frequency using the `segments` parameter:

```python
# Break down paths by platform
result = ws.query_flow("Purchase", segments="platform", last=30)

# Segment by a GroupBy with bucketing
from mixpanel_headless import GroupBy
result = ws.query_flow(
    "Purchase",
    segments=GroupBy("revenue", property_type="number", bucket_size=50),
    last=30,
)

# Segment by cohort membership
from mixpanel_headless import CohortBreakdown
result = ws.query_flow(
    "Purchase",
    segments=CohortBreakdown(cohort_id=123, name="Power Users"),
    last=30,
)
```

`segments` accepts a string (property name), `GroupBy`, `CohortBreakdown`, `FrequencyBreakdown`, or a list of these.

## Flow Exclusions

Hide specific events from flow paths using the `exclusions` parameter:

```python
# Exclude noisy events from the flow
result = ws.query_flow(
    "Purchase",
    exclusions=["Page View", "Session Start"],
    forward=3,
    last=30,
)
```

Excluded events are removed from the flow graph — they won't appear as nodes or edges, making it easier to see meaningful user paths.

## Session Events

Anchor a flow step to a session boundary using `FlowStep.session_event`:

```python
from mixpanel_headless import FlowStep

# What happens after a session starts?
result = ws.query_flow(
    FlowStep(event="Session Start", session_event="start"),
    forward=5,
    last=30,
)

# What leads up to a session ending?
result = ws.query_flow(
    FlowStep(event="Session End", session_event="end"),
    reverse=3,
    last=30,
)
```

Values: `"start"` (session start anchor) or `"end"` (session end anchor).

## Next Steps

- [Insights Queries](query.md) — Typed analytics with DAU, formulas, filters, and breakdowns
- [Funnel Queries](query-funnels.md) — Typed funnel conversion analysis with steps, exclusions, and conversion windows
- [Retention Queries](query-retention.md) — Typed retention analysis with event pairs and custom buckets
- [Live Analytics — Flows](live-analytics.md#flows) — Legacy saved Flows report method
- [API Reference — Workspace](../api/workspace.md) — Full method signatures
- [API Reference — Types](../api/types.md) — FlowStep, FlowTreeNode, FlowQueryResult details
