# Data Model: MCP Server v2 - Intelligent Analytics Platform

**Feature Branch**: `021-mcp-server-v2` | **Date**: 2026-01-13

## Overview

This document defines the data structures used by the MCP Server v2 intelligent tools, middleware, and enhanced resources. These types are defined in Python using Pydantic models and dataclasses for MCP protocol compatibility.

---

## Core Result Types

### AnalysisResult

Structured output from intelligent tools (Tier 3) that use sampling for synthesis.

```python
from dataclasses import dataclass, field
from typing import Any, Literal

@dataclass
class AnalysisResult:
    """Result from an intelligent tool with AI synthesis."""

    status: Literal["success", "partial", "sampling_unavailable"]
    """Execution status: success (full synthesis), partial (some queries failed),
    or sampling_unavailable (client doesn't support sampling)."""

    findings: dict[str, Any] | None = None
    """AI-synthesized findings when sampling is available."""

    recommendations: list[str] = field(default_factory=list)
    """Actionable recommendations derived from analysis."""

    confidence: Literal["low", "medium", "high"] | None = None
    """Confidence level in the analysis."""

    raw_data: dict[str, Any] = field(default_factory=dict)
    """Underlying query results for transparency."""

    analysis_hints: list[str] = field(default_factory=list)
    """Manual analysis hints when sampling unavailable."""
```

### ExecutionPlan

Query plan generated from natural language by `ask_mixpanel`.

```python
@dataclass
class QuerySpec:
    """Specification for a single query to execute."""

    method: Literal[
        "segmentation", "retention", "funnel",
        "property_counts", "event_counts", "activity_feed", "jql"
    ]
    """The Workspace method to call."""

    params: dict[str, Any]
    """Parameters to pass to the method."""


@dataclass
class ExecutionPlan:
    """Plan for answering a natural language question."""

    intent: str
    """Brief description of user's analytical intent."""

    query_type: str
    """Primary analysis type (retention, conversion, trend, etc.)."""

    queries: list[QuerySpec]
    """List of queries to execute."""

    date_range: dict[str, str]
    """Date range for all queries: {from_date, to_date}."""

    comparison_needed: bool = False
    """Whether comparison between periods/segments is required."""

    reasoning: str = ""
    """Explanation of why these queries answer the question."""
```

### DiagnosisResult

Specific result type for `diagnose_metric_drop`.

```python
@dataclass
class SegmentContribution:
    """A segment's contribution to a metric change."""

    dimension: str
    """Property dimension (e.g., 'platform', 'country')."""

    segment: str
    """Specific segment value (e.g., 'iOS', 'US')."""

    contribution_pct: float
    """Percentage of total drop attributable to this segment."""

    baseline_value: float
    """Value during baseline period."""

    current_value: float
    """Value during drop period."""

    description: str
    """Human-readable description of the impact."""


@dataclass
class DiagnosisResult:
    """Result from diagnose_metric_drop tool."""

    drop_confirmed: bool
    """Whether a significant drop was detected."""

    drop_percentage: float
    """Percentage change from baseline to drop period."""

    primary_driver: SegmentContribution | None
    """Main segment contributing to the drop."""

    secondary_factors: list[SegmentContribution] = field(default_factory=list)
    """Other contributing segments."""

    recommendations: list[str] = field(default_factory=list)
    """Actionable next steps."""

    confidence: Literal["low", "medium", "high"] = "medium"
    """Confidence in the diagnosis."""

    caveats: list[str] = field(default_factory=list)
    """Data quality concerns or limitations."""

    raw_data: dict[str, Any] = field(default_factory=dict)
    """Underlying query results."""
```

### FunnelOptimizationResult

Specific result type for `funnel_optimization_report`.

```python
@dataclass
class OptimizationRecommendation:
    """A single optimization recommendation."""

    action: str
    """What to do."""

    priority: Literal["high", "medium", "low"]
    """Priority level."""

    expected_impact: str
    """Expected improvement if implemented."""


@dataclass
class FunnelOptimizationResult:
    """Result from funnel_optimization_report tool."""

    executive_summary: str
    """2-3 sentence summary of key findings."""

    overall_conversion_rate: float
    """End-to-end conversion rate."""

    bottleneck: dict[str, Any]
    """Details of worst-performing step: {step_number, step_name, drop_percentage}."""

    top_performing_segments: list[dict[str, Any]]
    """Segments with highest conversion."""

    underperforming_segments: list[dict[str, Any]]
    """Segments with lowest conversion."""

    recommendations: list[OptimizationRecommendation]
    """Prioritized optimization actions."""

    raw_data: dict[str, Any] = field(default_factory=dict)
    """Underlying funnel and segment data."""
```

---

## Dashboard Types

### ProductHealthDashboard

Result type for `product_health_dashboard`.

```python
@dataclass
class AARRRMetrics:
    """Metrics for one AARRR category."""

    category: Literal["acquisition", "activation", "retention", "revenue", "referral"]
    """AARRR category."""

    primary_metric: float
    """Main metric value for this category."""

    trend: dict[str, float]
    """Time series data: {date: value}."""

    by_segment: dict[str, dict[str, Any]] | None = None
    """Breakdown by segment if available."""


@dataclass
class ProductHealthDashboard:
    """Complete AARRR product health dashboard."""

    period: dict[str, str]
    """Analysis period: {from_date, to_date}."""

    acquisition: AARRRMetrics | None = None
    """Acquisition metrics (signups, traffic)."""

    activation: AARRRMetrics | None = None
    """Activation metrics (onboarding, first value)."""

    retention: AARRRMetrics | None = None
    """Retention metrics (D1/D7/D30 return rates)."""

    revenue: AARRRMetrics | None = None
    """Revenue metrics (transactions, ARPU)."""

    referral: AARRRMetrics | None = None
    """Referral metrics (invites, viral coefficient)."""

    health_score: dict[str, int] | None = None
    """Score 1-10 for each category."""
```

---

## Investigation Types

### GQMInvestigation

Result type for `gqm_investigation`.

```python
@dataclass
class QuestionFinding:
    """Finding for a single GQM question."""

    question: str
    """The operational question."""

    query_type: str
    """Type of query used."""

    status: Literal["success", "failed"]
    """Whether query succeeded."""

    result: dict[str, Any] | None = None
    """Query result if successful."""

    error: str | None = None
    """Error message if failed."""


@dataclass
class GQMInvestigation:
    """Result from gqm_investigation tool."""

    interpreted_goal: str
    """Clarified version of user's goal."""

    aarrr_category: Literal["acquisition", "activation", "retention", "revenue", "referral"]
    """Classification for scoping."""

    period: dict[str, str]
    """Analysis period: {from_date, to_date}."""

    schema_context: dict[str, Any]
    """Available events and funnels used."""

    questions: list[dict[str, str]]
    """List of sub-questions generated."""

    findings: list[QuestionFinding]
    """Results for each question."""

    synthesis: dict[str, Any]
    """Overall synthesis of findings."""

    next_steps: list[str]
    """Suggested follow-up investigations."""
```

### CohortComparison

Result type for `cohort_comparison`.

```python
@dataclass
class CohortMetrics:
    """Metrics for a single cohort."""

    name: str
    """Cohort display name."""

    filter: str
    """Filter expression defining the cohort."""

    user_count: int | None = None
    """Number of users in cohort."""

    metrics: dict[str, Any] = field(default_factory=dict)
    """Computed metrics for this cohort."""


@dataclass
class CohortComparison:
    """Result from cohort_comparison tool."""

    cohort_a: CohortMetrics
    """First cohort."""

    cohort_b: CohortMetrics
    """Second cohort."""

    period: dict[str, str]
    """Analysis period."""

    comparisons: dict[str, dict[str, Any]]
    """Comparison results by dimension (retention, event_frequency, top_events)."""

    statistical_significance: dict[str, bool] | None = None
    """Whether differences are statistically significant."""
```

---

## Elicitation Types

### FetchConfirmation

User response type for `safe_large_fetch`.

```python
@dataclass
class FetchConfirmation:
    """User confirmation for large fetch operation."""

    proceed: bool
    """Whether to proceed with the fetch."""

    reduce_scope: bool = False
    """Whether to reduce the scope."""

    new_limit: int | None = None
    """New event limit if reducing scope."""
```

### AnalysisChoice

User choice type for `guided_analysis`.

```python
@dataclass
class AnalysisChoice:
    """User's choice for analysis direction."""

    focus_area: Literal["conversion", "retention", "engagement", "revenue"]
    """Primary focus area."""

    time_period: Literal["last_7_days", "last_30_days", "last_90_days", "custom"]
    """Analysis time period."""

    custom_start: str | None = None
    """Custom start date if time_period is 'custom'."""

    custom_end: str | None = None
    """Custom end date if time_period is 'custom'."""


@dataclass
class SegmentChoice:
    """User's choice for segment investigation."""

    segment_index: int
    """Index of selected segment from presented list."""

    investigate_further: bool = True
    """Whether to drill deeper into this segment."""
```

---

## Middleware Types

### RateLimitState

Internal state for rate limiting middleware.

```python
@dataclass
class RateLimitState:
    """State tracking for rate limiting."""

    request_times: list[float] = field(default_factory=list)
    """Timestamps of recent requests."""

    active_count: int = 0
    """Number of currently active requests."""


@dataclass
class MixpanelRateLimits:
    """Mixpanel API rate limit configuration."""

    # Query API limits
    query_hourly_limit: int = 60
    query_concurrent_limit: int = 5

    # Export API limits
    export_hourly_limit: int = 60
    export_per_second_limit: int = 3
    export_concurrent_limit: int = 100
```

### CacheEntry

Internal cache entry structure.

```python
@dataclass
class CacheEntry:
    """Cached response entry."""

    key: str
    """Cache key (hash of tool name + arguments)."""

    value: Any
    """Cached result."""

    created_at: float
    """Timestamp when cached."""

    ttl: int
    """Time-to-live in seconds."""

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        import time
        return time.time() - self.created_at > self.ttl
```

---

## Entity Relationships

```
┌─────────────────┐
│   AnalysisResult│ ◄── Base for all intelligent tool results
└────────┬────────┘
         │ specializes
         ▼
┌─────────────────┐  ┌───────────────────────┐  ┌──────────────────┐
│ DiagnosisResult │  │FunnelOptimizationResult│  │ GQMInvestigation │
└─────────────────┘  └───────────────────────┘  └──────────────────┘
         │                      │                        │
         │ contains             │ contains               │ contains
         ▼                      ▼                        ▼
┌───────────────────┐  ┌─────────────────────────┐  ┌───────────────┐
│SegmentContribution│  │OptimizationRecommendation│  │QuestionFinding│
└───────────────────┘  └─────────────────────────┘  └───────────────┘

┌──────────────────────┐
│ ProductHealthDashboard│
└──────────┬───────────┘
           │ contains 5x
           ▼
   ┌─────────────┐
   │ AARRRMetrics │
   └─────────────┘

┌────────────────┐
│ ExecutionPlan  │
└───────┬────────┘
        │ contains N
        ▼
  ┌───────────┐
  │ QuerySpec │
  └───────────┘
```

---

## Validation Rules

| Entity | Field | Rule |
|--------|-------|------|
| DiagnosisResult | drop_percentage | Must be numeric; negative indicates increase |
| SegmentContribution | contribution_pct | Must be 0-100; sum should approximate 100 |
| ExecutionPlan | queries | Must have at least 1 query |
| QuerySpec | method | Must be valid Workspace method name |
| ProductHealthDashboard | period | from_date must be before to_date |
| FetchConfirmation | new_limit | If reduce_scope, must be positive integer |
| AnalysisChoice | custom_start/end | Required if time_period is 'custom' |
| CacheEntry | ttl | Must be positive integer |

---

## State Transitions

### Intelligent Tool Execution

```
INITIATED → GATHERING_DATA → SYNTHESIZING → COMPLETE
                ↓                 ↓
           PARTIAL_FAILURE   SAMPLING_UNAVAILABLE
                ↓                 ↓
            COMPLETE         COMPLETE (raw data only)
```

### Task-Enabled Tool Execution

```
QUEUED → IN_PROGRESS → COMPLETE
              ↓
         CANCELLED (preserves partial results)
```

### Elicitation Flow

```
WAITING_FOR_USER → ACCEPTED (with data)
                 → DECLINED (no data)
                 → CANCELLED (operation aborted)
```
