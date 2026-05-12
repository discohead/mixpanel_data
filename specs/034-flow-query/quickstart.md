# Quickstart: Typed Flow Query API

**Date**: 2026-04-06  
**Feature**: 034-flow-query

---

## Basic Usage

```python
import mixpanel_data as mp

ws = mp.Workspace()

# What happens after Purchase? (3 steps forward)
result = ws.query_flow("Purchase", forward=3)

# What happens before AND after Purchase?
result = ws.query_flow("Purchase", forward=3, reverse=2)

# Inspect the generated bookmark params (no API call)
params = ws.build_flow_params("Purchase", forward=3)
print(params)
```

## Configuring the Query

```python
# With conversion window and counting
result = ws.query_flow(
    "Add to Cart",
    forward=5,
    conversion_window=14,
    conversion_window_unit="day",
    count_type="unique",
)

# Hide noisy events
result = ws.query_flow(
    "Checkout",
    forward=3,
    hidden_events=["Page View", "Session Start"],
)

# Collapse repeated consecutive events
result = ws.query_flow("Login", forward=3, collapse_repeated=True)

# Custom date range
result = ws.query_flow(
    "Signup",
    forward=3,
    from_date="2025-01-01",
    to_date="2025-03-31",
)
```

## Per-Step Filters

```python
from mixpanel_data import FlowStep, Filter

# Filter to high-value purchases
result = ws.query_flow(
    FlowStep("Purchase", forward=3, filters=[Filter.greater_than("amount", 50)])
)

# Multiple anchors with independent directions
result = ws.query_flow([
    FlowStep("Signup", forward=3, reverse=0),
    FlowStep("Purchase", forward=0, reverse=3),
])
```

## Working with Results

### DataFrames

```python
result = ws.query_flow("Login", forward=3)

# Node-level data
print(result.nodes_df)
#   step  event      type    count  anchor_type  ...
# 0    0  Login    ANCHOR      100       NORMAL  ...
# 1    1  Search   NORMAL       80       NORMAL  ...
# 2    1  Browse   NORMAL       20       NORMAL  ...

# Edge-level data (transitions between events)
print(result.edges_df)
#   source_step source_event  target_step target_event  count  ...
# 0           0        Login            1       Search     80  ...
# 1           0        Login            1       Browse     20  ...

# Top transitions by volume
result.edges_df.sort_values("count", ascending=False).head(10)

# Drop-off nodes
result.nodes_df[result.nodes_df["type"] == "DROPOFF"]
```

### NetworkX Graph

```python
G = result.graph  # lazy-cached DiGraph

# All paths from Login to Purchase
import networkx as nx
list(nx.all_simple_paths(G, "Login@0", "Purchase@3"))

# Events reachable within 2 steps
nx.ego_graph(G, "Login@0", radius=2)

# Drop-off ratio per node
for node, data in G.nodes(data=True):
    if data["type"] != "DROPOFF":
        outflow = sum(d["count"] for _, _, d in G.out_edges(node, data=True))
        ratio = outflow / data["count"] if data["count"] else 0
        print(f"{node}: {ratio:.0%} retained")
```

### Convenience Methods

```python
# Top 5 highest-traffic transitions
result.top_transitions(n=5)
# [("Login@0", "Search@1", 80), ("Search@1", "ViewItem@2", 50), ...]

# Per-step drop-off summary
result.drop_off_summary()
# {"step_0": {"total": 100, "dropoff": 0, "rate": 0.0},
#  "step_1": {"total": 100, "dropoff": 20, "rate": 0.2}, ...}
```

## Top Paths Mode

```python
# List of top paths instead of sankey graph
result = ws.query_flow("Purchase", forward=3, mode="paths")
print(result.df)  # tabular path data
```

## Debugging and Persistence

```python
# Inspect generated params
result = ws.query_flow("Signup", forward=3)
print(result.params)

# Save as a Mixpanel report
from mixpanel_data.types import CreateBookmarkParams
ws.create_bookmark(CreateBookmarkParams(
    name="Signup Flow Analysis",
    bookmark_type="flows",
    params=result.params,
))
```

## Saved Reports (Renamed Method)

```python
# Query a pre-saved flows report (formerly query_flows)
saved = ws.query_saved_flows(bookmark_id=12345678)
print(saved.steps)
```
