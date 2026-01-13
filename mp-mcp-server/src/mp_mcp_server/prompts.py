"""MCP prompts for guided analytics workflows.

Prompts provide structured templates that guide users through
analytics workflows and best practices.

Example:
    User requests "analytics workflow" prompt and gets guided steps
    for exploring their Mixpanel data.
"""

from mp_mcp_server.server import mcp


@mcp.prompt()
def analytics_workflow() -> str:
    """Guide through a complete analytics exploration workflow.

    Provides step-by-step guidance for:
    1. Discovering available events and properties
    2. Running initial queries to understand data
    3. Building insights from the analysis

    Returns:
        Prompt text guiding the analytics workflow.
    """
    return """# Mixpanel Analytics Workflow

Let me help you explore your Mixpanel data. Here's a structured approach:

## Step 1: Discover Your Schema
First, let's understand what data you have:
- Use `list_events` to see all tracked events
- Use `list_funnels` to see saved funnels
- Use `list_cohorts` to see user segments

## Step 2: Explore Key Events
For your most important events:
- Use `list_properties` to see what data is captured
- Use `top_events` to identify your most active events

## Step 3: Run Initial Analysis
Based on what you want to learn:
- **Trends**: Use `segmentation` for time series analysis
- **Conversions**: Use `funnel` to analyze conversion paths
- **Retention**: Use `retention` to understand user stickiness

## Step 4: Deep Dive with Local Data
For complex analysis:
- Use `fetch_events` to download data locally
- Use `sql` to run custom queries
- Use `sample` to explore data format

What would you like to explore first?"""


@mcp.prompt()
def funnel_analysis(funnel_name: str = "signup") -> str:
    """Guide through funnel analysis workflow.

    Args:
        funnel_name: Name of the funnel to analyze.

    Returns:
        Prompt text guiding funnel analysis.
    """
    return f"""# Funnel Analysis Workflow: {funnel_name}

Let me help you analyze your {funnel_name} funnel:

## Step 1: Find Your Funnel
Use `list_funnels` to find the funnel ID for "{funnel_name}"

## Step 2: Analyze Conversion
Use `funnel` with the funnel_id to see:
- Overall conversion rate
- Step-by-step drop-off
- Time-based trends

## Step 3: Segment the Analysis
To understand WHO converts:
- Add segment parameters to break down by user properties
- Compare conversion across different user groups

## Step 4: Identify Improvements
- Which step has the highest drop-off?
- Are there user segments that convert better?
- What time periods show best conversion?

Ready to start? I'll find your funnel and run the analysis."""


@mcp.prompt()
def retention_analysis(event: str = "signup") -> str:
    """Guide through retention analysis workflow.

    Args:
        event: The birth event for cohort analysis.

    Returns:
        Prompt text guiding retention analysis.
    """
    return f"""# Retention Analysis Workflow

Let me help you understand retention for users who did "{event}":

## Step 1: Define the Cohort
- **Born Event**: {event} (when users enter the cohort)
- **Return Event**: What action shows they're still active?

## Step 2: Choose Time Frame
- Recent cohorts (last 30 days) for current trends
- Historical cohorts for long-term patterns

## Step 3: Run Retention Analysis
Use `retention` with:
- born_event: "{event}"
- return_event: (the engagement event)
- from_date/to_date: your analysis period

## Step 4: Interpret Results
- Day 1 retention: immediate engagement
- Day 7 retention: weekly habit formation
- Day 30 retention: monthly stickiness

## Step 5: Compare Segments
- Which user sources have better retention?
- Do power users retain longer?
- Impact of onboarding changes?

Ready to analyze retention? Tell me your return event."""


@mcp.prompt()
def local_analysis_workflow() -> str:
    """Guide through local data analysis with SQL.

    Returns:
        Prompt text guiding local SQL analysis.
    """
    return """# Local Data Analysis Workflow

Let me help you analyze data locally with SQL:

## Step 1: Fetch Your Data
Use `fetch_events` to download events to local storage:
```
fetch_events(from_date="2024-01-01", to_date="2024-01-31")
```

## Step 2: Explore the Data
- Use `list_tables` to see available tables
- Use `table_schema` to see column definitions
- Use `sample` to preview actual data

## Step 3: Query with SQL
Use `sql` for custom analysis:
```sql
SELECT event_name, COUNT(*) as count
FROM events
GROUP BY event_name
ORDER BY count DESC
```

## Step 4: Advanced Analysis
- Join events with profiles
- Calculate user-level metrics
- Build custom funnels

## Step 5: Clean Up
Use `drop_table` when done to free space

What data would you like to analyze?"""
