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


@mcp.prompt()
def gqm_decomposition(goal: str = "understand user retention") -> str:
    """Goal-Question-Metric decomposition prompt.

    Guides users through structured investigation using the GQM methodology.
    Helps decompose high-level goals into operational questions and metrics.

    Args:
        goal: The high-level goal to investigate.

    Returns:
        Prompt text guiding GQM decomposition.

    Example:
        User provides goal "understand why retention is declining"
        and receives structured investigation guidance.
    """
    return f"""# Goal-Question-Metric (GQM) Investigation Framework

## Your Goal
"{goal}"

## Framework Overview
GQM is a systematic approach to measurement:
- **Goal**: Define what you want to achieve (conceptual level)
- **Questions**: Identify what you need to know (operational level)
- **Metrics**: Determine what to measure (quantitative level)

## Step 1: Clarify the Goal
Let's refine your goal:
- What business outcome are you trying to improve?
- Who are the stakeholders?
- What does success look like?

## Step 2: Generate Questions
Based on your goal, answer these questions:
1. What is the current state of the metric?
2. How has it changed over time?
3. What segments or cohorts are most affected?
4. What actions or events correlate with the outcome?
5. What external factors might influence this?

## Step 3: Define Metrics
For each question, identify measurable metrics:
- **Primary Metric**: The main measure of goal achievement
- **Supporting Metrics**: Context and segmentation
- **Leading Indicators**: Early signals of change

## Step 4: Execute the Investigation
Use these tools in order:
1. `list_events` - Identify relevant events
2. `segmentation` - Analyze trends
3. `retention` - Measure return rates
4. `property_counts` - Segment analysis

## Step 5: Synthesize Findings
After gathering data:
- What patterns emerged?
- What hypotheses are supported/rejected?
- What actions do you recommend?

Ready to investigate "{goal}"? Let's start with Step 1."""


@mcp.prompt()
def growth_accounting(acquisition_event: str = "signup") -> str:
    """AARRR (Pirate Metrics) growth accounting prompt.

    Guides users through analyzing all five stages of the pirate metrics
    framework with industry benchmarks.

    Args:
        acquisition_event: The event that marks user acquisition.

    Returns:
        Prompt text guiding AARRR analysis with benchmarks.

    Example:
        User requests growth accounting and receives structured
        analysis of each AARRR stage.
    """
    return f"""# Growth Accounting: AARRR Framework Analysis

## Overview
The AARRR framework (Pirate Metrics) measures the customer lifecycle:
- **A**cquisition: How users find you
- **A**ctivation: First value experience
- **R**etention: Users coming back
- **R**evenue: Monetization
- **R**eferral: Users bringing others

## Your Acquisition Event: "{acquisition_event}"

## Stage 1: Acquisition Analysis
Questions to answer:
- How many users signed up?
- Which channels drive the most signups?
- What's the cost per acquisition by channel?

**Benchmarks**:
- 2-5% landing page conversion (B2C)
- 5-15% landing page conversion (B2B)

Tools: `segmentation(event="{acquisition_event}")`, `property_counts(event="{acquisition_event}", property_name="utm_source")`

## Stage 2: Activation Analysis
Questions to answer:
- What % complete onboarding?
- How long to first value moment?
- Where do users drop off?

**Benchmarks**:
- 20-40% onboarding completion
- Under 2 minutes to "aha moment"

Tools: `funnel()` for activation steps

## Stage 3: Retention Analysis
Questions to answer:
- What's D1/D7/D30 retention?
- Which features drive retention?
- When do users typically churn?

**Benchmarks**:
- D1: 25-40% (consumer), 40-60% (B2B)
- D7: 15-25% (consumer), 25-40% (B2B)
- D30: 10-15% (consumer), 20-30% (B2B)

Tools: `retention(born_event="{acquisition_event}")`

## Stage 4: Revenue Analysis
Questions to answer:
- What's the conversion rate to paid?
- What's the ARPU (average revenue per user)?
- What drives upgrades?

**Benchmarks**:
- 2-5% free to paid conversion
- 10-20% trial to paid conversion

Tools: `segmentation(event="purchase")`, property analysis on plan type

## Stage 5: Referral Analysis
Questions to answer:
- What % of users refer others?
- What's the viral coefficient (K-factor)?
- Are referred users more valuable?

**Benchmarks**:
- 5-10% referral rate
- K-factor > 0.5 indicates good virality

Tools: `segmentation(event="referral_sent")`, compare referred user retention

## Quick Dashboard
Use `product_health_dashboard(acquisition_event="{acquisition_event}")` for a quick overview of all metrics.

Which stage would you like to analyze first?"""


@mcp.prompt()
def experiment_analysis(experiment_name: str = "homepage_redesign") -> str:
    """A/B test evaluation prompt.

    Guides users through analyzing experiment results with
    statistical rigor.

    Args:
        experiment_name: Name of the experiment to analyze.

    Returns:
        Prompt text guiding A/B test analysis.

    Example:
        User provides experiment name and receives structured
        analysis guidance.
    """
    return f"""# A/B Test Analysis: {experiment_name}

## Pre-Analysis Checklist

### 1. Experiment Setup Validation
Before analyzing results, verify:
- [ ] Control and treatment groups are properly defined
- [ ] Sample size is sufficient for statistical power
- [ ] Test ran for at least 1-2 business cycles
- [ ] No overlapping experiments on same users

### 2. Define Success Metrics
**Primary Metric**: The main metric you're trying to improve
- Should be directly tied to business value
- Should be measurable during the test

**Guardrail Metrics**: Metrics that shouldn't regress
- User experience metrics
- Revenue/engagement baselines

**Secondary Metrics**: Supporting metrics for context
- Segment-specific impacts
- Upstream/downstream effects

## Analysis Steps

### Step 1: Segment the Data
Use cohort or property filters to separate variants:
```
cohort_comparison(
    cohort_a_filter='properties["experiment_variant"] == "control"',
    cohort_b_filter='properties["experiment_variant"] == "treatment"'
)
```

### Step 2: Check Sample Sizes
Ensure you have sufficient data:
- Minimum 100 conversions per variant (rule of thumb)
- For small effect sizes, need larger samples

### Step 3: Calculate Results
For each metric, calculate:
- **Conversion rate** per variant
- **Lift** (% change from control)
- **Statistical significance** (p-value < 0.05)
- **Confidence interval** for the lift

### Step 4: Interpret Results

| Result | Interpretation |
|--------|---------------|
| Significant + positive | Ship it! |
| Significant + negative | Don't ship |
| Not significant | Need more data or effect is small |

### Step 5: Consider Segments
Check if the effect varies by:
- User type (new vs returning)
- Platform (web vs mobile)
- Geography
- User segment

### Common Pitfalls
- **Peeking**: Don't check results too early
- **Cherry-picking**: Report all metrics, not just winners
- **Ignoring segments**: Effect may vary by user type
- **Ignoring practical significance**: Statistical significance ≠ business impact

## Launch Decision Framework
1. Is the primary metric significantly improved?
2. Are guardrail metrics stable?
3. Is the implementation sustainable?
4. Are there any segment concerns?

Ready to analyze "{experiment_name}"? Let's start by defining your metrics."""


@mcp.prompt()
def data_quality_audit(event: str = "signup") -> str:
    """Data quality audit prompt.

    Guides users through assessing implementation quality and
    data reliability.

    Args:
        event: Primary event to audit.

    Returns:
        Prompt text guiding data quality assessment.

    Example:
        User requests audit of "signup" event and receives
        comprehensive quality checklist.
    """
    return f"""# Data Quality Audit: {event}

## Audit Overview
This audit assesses the quality and reliability of your "{event}" event
and related data.

## 1. Event Coverage Audit

### Questions to Answer:
- Is the event firing consistently?
- Are there gaps in the data?
- Does volume match expected traffic?

### Steps:
1. Use `segmentation(event="{event}")` to check daily volume
2. Look for:
   - Sudden drops (possible tracking issues)
   - Zero days (outages?)
   - Unexpected spikes (duplicates? bots?)

### Red Flags:
- [ ] Day-over-day variance > 50%
- [ ] Missing days
- [ ] Obvious bot patterns (identical timestamps)

## 2. Property Completeness Audit

### Questions to Answer:
- What properties are captured?
- What % of events have each property?
- Are there unexpected null values?

### Steps:
1. Use `list_properties(event="{event}")` to see all properties
2. Use `property_counts(event="{event}", property_name="...")` for each key property
3. Check for:
   - "(not set)" or null values
   - Unexpected values
   - Inconsistent formatting

### Standard Properties to Check:
- [ ] User identification (distinct_id, user_id)
- [ ] Timestamp accuracy
- [ ] Device/platform properties
- [ ] Source/campaign attribution

## 3. Identity Resolution Audit

### Questions to Answer:
- Are users properly identified?
- Is identity stitching working?
- Are there duplicate user profiles?

### Steps:
1. Check `activity_feed(distinct_id="test_user")` for a known user
2. Verify events appear under correct identity
3. Check for:
   - Anonymous → identified transitions
   - Cross-device identification
   - Profile property consistency

### Red Flags:
- [ ] High % of anonymous users
- [ ] Events with generic/shared IDs
- [ ] Duplicate user profiles

## 4. Data Freshness Audit

### Questions to Answer:
- How recent is the data?
- Is there processing lag?
- Are real-time events working?

### Steps:
1. Compare expected vs actual event timestamps
2. Check for batching delays
3. Verify real-time updates work

### Red Flags:
- [ ] Events arriving > 24h late
- [ ] Timestamp inconsistencies
- [ ] Missing recent data

## 5. Schema Consistency Audit

### Questions to Answer:
- Are property names consistent?
- Are data types stable?
- Are there deprecated properties?

### Steps:
1. Use `property_keys(table="events", event="{event}")` to list all properties
2. Look for:
   - Duplicate properties (camelCase vs snake_case)
   - Type inconsistencies (string vs number)
   - Old/deprecated properties

### Best Practices:
- [ ] Consistent naming convention
- [ ] Typed values (not all strings)
- [ ] No PII in properties

## Audit Summary Template

```markdown
## Data Quality Report: {event}

**Date**: [today]
**Analyst**: [name]

### Coverage Score: [1-5]
- Volume consistency: [OK/ISSUE]
- Data gaps: [NONE/SOME/MANY]

### Completeness Score: [1-5]
- Required properties: [%]
- Optional properties: [%]

### Identity Score: [1-5]
- Identification rate: [%]
- Resolution accuracy: [HIGH/MEDIUM/LOW]

### Recommendations:
1. [Priority 1 fix]
2. [Priority 2 fix]
3. [Priority 3 fix]
```

Ready to audit "{event}"? Let's start with the coverage analysis."""
