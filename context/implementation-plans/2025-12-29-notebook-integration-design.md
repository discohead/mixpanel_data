# Notebook Integration Design

**Date:** 2025-12-29
**Status:** Draft
**Author:** Claude + User

## Overview

Add notebook support to `mixpanel_data` for visualizing Mixpanel analytics data in Jupyter notebooks. The integration provides auto-display of result types as interactive charts/tables, explicit plotting functions for customization, and parameter widgets for interactive exploration.

## Goals

- Enable both AI agents and human analysts to visualize Mixpanel data
- Provide zero-config auto-display that "just works"
- Allow customization for users who need more control
- Keep the core library lightweight (notebook features are optional)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Target audience | Both agents and humans | Need convenience AND programmatic control |
| MVP visualizations | Time-series charts + rich tables | Covers 80% of analytics use cases |
| Parametric control | Query widgets + interactive charts | Date pickers, dropdowns, zoom/pan/hover |
| Platform priority | Jupyter first, Marimo later | Larger ecosystem, learn before tackling Marimo |
| Packaging | Optional extra `[notebook]` | Keeps core lightweight |
| Charting library | Plotly | Interactive out of the box |
| API style | Auto-display + explicit `.plot()` | Best of both worlds |

## Package Structure

```
src/mixpanel_data/
├── notebook/                    # New subpackage
│   ├── __init__.py             # Exports: enable(), plot(), table(), widgets
│   ├── _display.py             # Auto-display registration logic
│   ├── _charts.py              # Plotly chart builders
│   ├── _tables.py              # Rich table formatters
│   └── _widgets.py             # ipywidgets for parameters
└── types.py                    # Existing - NO changes to core types
```

### Dependencies (notebook extra only)

```toml
[project.optional-dependencies]
notebook = [
    "plotly>=5.0",
    "ipywidgets>=8.0",
]
```

## API Design

### 1. Enable Auto-Display

```python
from mixpanel_data.notebook import enable
enable()  # Registers _repr_html_() hooks for all result types
```

When enabled, result types automatically render as charts/tables in notebook cells:

```python
ws = Workspace()
ws.segmentation("Signup", from_date="2024-01-01", to_date="2024-01-31")
# ^ Automatically displays as interactive line chart
```

### 2. Auto-Display Mapping

| Result Type | Display Format |
|-------------|----------------|
| `SegmentationResult` | Line chart (date vs count, one line per segment) |
| `FunnelResult` | Horizontal bar chart (step conversion rates) |
| `RetentionResult` | Heatmap (cohort x period retention %) |
| `EventCountsResult` | Multi-line chart (one line per event) |
| `PropertyCountsResult` | Multi-line chart (one line per property value) |
| `SummaryResult` | Rich HTML table with column stats |
| `EventBreakdownResult` | Rich HTML table with event stats |
| `ColumnStatsResult` | Stats card + bar chart of top values |
| `FetchResult` | Simple stats card (rows fetched, duration) |

### 3. Explicit Plot Function

For customization beyond auto-display:

```python
from mixpanel_data.notebook import plot

# Get a Plotly figure you can customize
fig = plot(segmentation_result)
fig.update_layout(title="My Custom Title", height=400)
fig.show()
```

Function signature:

```python
def plot(
    result: SegmentationResult | FunnelResult | RetentionResult | ...,
    *,
    title: str | None = None,
    height: int = 400,
    width: int | None = None,  # None = responsive
    theme: Literal["plotly", "plotly_dark", "minimal"] = "minimal",
) -> go.Figure:
    """Create an interactive chart from any result type."""
```

Type-specific functions for more control:

```python
from mixpanel_data.notebook import line_chart, bar_chart, heatmap

fig = line_chart(
    segmentation_result,
    title="Daily Signups",
    color_map={"US": "blue", "EU": "green"},
    show_legend=True,
)
```

### 4. DataFrame Passthrough

For custom queries not covered by result types:

```python
df = ws.sql("SELECT date, count(*) as cnt FROM events GROUP BY date")
fig = plot(df, x="date", y="cnt", kind="line")
```

### 5. Rich Tables

```python
from mixpanel_data.notebook import table

# Rich display of any DataFrame or result
table(ws.sql("SELECT * FROM events LIMIT 100"))
table(summary_result)  # Shows column stats with conditional formatting
```

Function signature:

```python
def table(
    data: pd.DataFrame | SummaryResult | EventBreakdownResult | ...,
    *,
    max_rows: int = 50,
    max_col_width: int = 40,
    highlight: Literal["none", "heatmap", "bars"] = "none",
) -> DisplayHandle:
    """Render data as an interactive HTML table."""
```

Table features:
- Click column headers to sort
- Long text values truncated with hover-to-expand
- Numeric formatting (thousands separators, percentages)
- Optional conditional coloring (heatmap mode)
- Pagination for large results

### 6. Parameter Widgets

Interactive exploration with ipywidgets:

```python
from mixpanel_data.notebook import widgets

# Creates date range picker + event dropdown + "Run" button
query_widget = widgets.segmentation(
    ws,
    events=["Signup", "Purchase", "Login"],  # Dropdown options
    default_range=("2024-01-01", "2024-01-31"),
)
query_widget  # Display in notebook - auto-updates chart on Run
```

Widget behavior:
1. Renders date pickers + dropdowns using ipywidgets
2. User adjusts parameters and clicks "Run" (or auto-run on change)
3. Widget calls `ws.segmentation(...)` with selected parameters
4. Result auto-displays as chart below the widget
5. Result accessible via `query_widget.result` for further analysis

Available widget factories:

| Function | Parameters | Output |
|----------|------------|--------|
| `widgets.segmentation()` | event, dates, segment_by | Line chart |
| `widgets.event_counts()` | events[], dates, unit | Multi-line chart |
| `widgets.retention()` | born_event, return_event, dates | Heatmap |

## Error Handling

### Environment Detection

```python
def enable() -> None:
    """Enable rich notebook display for all result types.

    Safe to call in any environment - no-op if not in a notebook.
    """
    if not _is_notebook_environment():
        import warnings
        warnings.warn(
            "enable() called outside notebook environment - display hooks not registered",
            stacklevel=2,
        )
        return
    _register_display_hooks()

def _is_notebook_environment() -> bool:
    """Detect if running in Jupyter/IPython notebook."""
    try:
        from IPython import get_ipython
        shell = get_ipython()
        if shell is None:
            return False
        return shell.__class__.__name__ in (
            "ZMQInteractiveShell",
            "TerminalInteractiveShell",
        )
    except ImportError:
        return False
```

### Import Safety

```python
try:
    from mixpanel_data.notebook import enable
except ImportError:
    print("Install with: pip install mixpanel_data[notebook]")
```

### Widget Fallbacks

If ipywidgets can't render (e.g., JupyterLab without extension), widgets degrade to simple function calls with printed output rather than crashing.

## Implementation Details

### Display Hook Registration

The `enable()` function monkey-patches `_repr_html_()` methods onto frozen dataclasses:

```python
# mixpanel_data/notebook/_display.py

from mixpanel_data.types import SegmentationResult, FunnelResult, ...

def _register_display_hooks() -> None:
    """Register _repr_html_() on all result types."""
    SegmentationResult._repr_html_ = _segmentation_repr
    FunnelResult._repr_html_ = _funnel_repr
    RetentionResult._repr_html_ = _retention_repr
    # ... etc for each result type

def _segmentation_repr(self: SegmentationResult) -> str:
    """Render segmentation as interactive time-series chart."""
    fig = build_segmentation_chart(self)
    return fig.to_html(include_plotlyjs="cdn", full_html=False)
```

### Chart Builders

Each result type has a dedicated chart builder in `_charts.py`:

```python
def build_segmentation_chart(result: SegmentationResult) -> go.Figure:
    """Build line chart from segmentation result."""
    fig = go.Figure()
    for segment, date_counts in result.series.items():
        dates = list(date_counts.keys())
        counts = list(date_counts.values())
        fig.add_trace(go.Scatter(x=dates, y=counts, name=segment, mode="lines"))

    fig.update_layout(
        title=f"{result.event} by {result.segment_property or 'total'}",
        xaxis_title="Date",
        yaxis_title="Count",
        template="plotly_white",
    )
    return fig
```

## Testing Strategy

| Test Type | Approach |
|-----------|----------|
| Unit tests | Mock IPython display system, verify HTML output |
| Integration tests | Use `nbconvert` to execute notebooks headlessly |
| Visual regression | Capture chart HTML for comparison (optional) |

## MVP Scope

### In Scope

- Package structure with `mixpanel_data[notebook]` extra
- `enable()` function to register display hooks
- Auto-display charts: Segmentation, EventCounts, Retention, Funnel
- Auto-display tables: SummaryResult, EventBreakdownResult, ColumnStatsResult
- `plot()` function returning Plotly figures
- `table()` function with sorting and truncation
- Basic widgets: `widgets.segmentation()`, `widgets.event_counts()`
- Jupyter Notebook and JupyterLab support

### Deferred (Post-MVP)

| Feature | Reason |
|---------|--------|
| Marimo support | Different reactive model - needs separate implementation |
| Funnel/Sankey diagrams | Complex visualization - start with simpler charts |
| Dashboard builder | Full layout system is over-engineering for now |
| Sparklines in tables | Nice-to-have, not essential |
| `widgets.sql()` | Custom SQL widget can come after core widgets work |
| `widgets.retention()` | Can be added after core widgets pattern established |

## Future Considerations

### Marimo Support

Marimo's reactive model means:
- No need for `enable()` - Marimo auto-discovers display methods
- Widgets work differently (Marimo has its own reactive primitives)
- May need a separate `mixpanel_data.marimo` module

### Theme Support

Could add theme configuration:
```python
from mixpanel_data.notebook import set_theme
set_theme("dark")  # Affects all subsequent charts
```

### Export Capabilities

Could add chart export:
```python
fig = plot(result)
fig.write_image("chart.png")  # Requires kaleido
fig.write_html("chart.html")
```
