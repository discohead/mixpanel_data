# Resources & Prompts

MCP resources provide read-only data access, and prompts offer guided workflow templates.

!!! tip "Explore on DeepWiki"
    🤖 **[Resources & Prompts →](https://deepwiki.com/jaredmcfarland/mixpanel_data/3.4.4-resources-and-recipes)**

    Ask about specific resources, explore prompt workflows, or get help with MCP capabilities.

## Resources

Resources expose data through MCP's resource protocol. AI assistants can read these directly without invoking tools.

### Static Resources

Always-available resources that reflect current state.

| URI | Description |
|-----|-------------|
| `workspace://info` | Workspace configuration (project ID, region, account) |
| `workspace://tables` | List of local DuckDB tables |
| `schema://events` | All tracked event names |
| `schema://funnels` | Saved funnel definitions |
| `schema://cohorts` | Saved cohort definitions |
| `schema://bookmarks` | Saved report bookmarks |

**Usage example:**

```
Read the workspace://info resource to see my configuration
```

### Dynamic Resource Templates (v2)

Parameterized resources that accept arguments.

| URI Template | Description |
|--------------|-------------|
| `analysis://retention/{event}/weekly` | 12-week retention curve for an event |
| `analysis://trends/{event}/{days}` | Daily event counts for N days |
| `users://{id}/journey` | Event journey for a specific user |

**Usage examples:**

```
Read analysis://retention/Signup/weekly
Read analysis://trends/Purchase/30
Read users://user@example.com/journey
```

---

## Prompts

Prompts provide structured workflow templates for common analysis patterns. They guide the AI assistant through multi-step analysis processes.

### analytics_workflow

Complete analytics exploration workflow.

**Description:** A comprehensive guide for exploring Mixpanel data, from discovery through analysis.

**Workflow steps:**

1. Discover available events and properties
2. Understand data volume and patterns
3. Run exploratory queries
4. Fetch data for deeper analysis
5. Execute SQL queries locally
6. Synthesize findings

**When to use:** Starting a new analytics exploration with no specific goal in mind.

---

### funnel_analysis

Funnel conversion analysis workflow.

**Description:** Structured approach to analyzing conversion funnels.

**Workflow steps:**

1. List available funnels
2. Select funnel to analyze
3. Query conversion rates over time
4. Identify drop-off points
5. Segment by user properties
6. Recommend optimizations

**When to use:** Investigating conversion rates or funnel performance.

---

### retention_analysis

User retention analysis workflow.

**Description:** Systematic retention and cohort analysis.

**Workflow steps:**

1. Define cohort (born event)
2. Define return criteria
3. Run retention query
4. Analyze by time intervals
5. Segment by acquisition source
6. Compare cohorts

**When to use:** Understanding user retention patterns or comparing cohort performance.

---

### local_analysis_workflow

Local SQL analysis workflow.

**Description:** Guide for working with locally stored data.

**Workflow steps:**

1. List available tables
2. Inspect table schemas
3. Sample data for understanding
4. Build SQL queries iteratively
5. Extract insights
6. Export results if needed

**When to use:** Analyzing data that's already been fetched locally.

---

### gqm_decomposition

Goal-Question-Metric investigation framework.

**Description:** Structured problem investigation using the GQM methodology.

**Workflow steps:**

1. Define the business goal
2. Formulate specific questions
3. Identify metrics for each question
4. Execute queries for each metric
5. Synthesize findings
6. Recommend actions

**When to use:** Investigating a specific business problem or goal.

**Example:** "Why is user activation declining?"

---

### aarrr_analysis

Pirate metrics (AARRR) analysis.

**Description:** Comprehensive product health analysis using the AARRR framework.

**Metrics covered:**

| Metric | Description |
|--------|-------------|
| **Acquisition** | How users find the product |
| **Activation** | First value experience |
| **Retention** | Repeat usage patterns |
| **Revenue** | Monetization metrics |
| **Referral** | Viral growth indicators |

**Workflow steps:**

1. Define events for each stage
2. Query acquisition metrics
3. Measure activation rates
4. Analyze retention curves
5. Track revenue events
6. Identify referral patterns

**When to use:** Getting a holistic view of product health.

---

### experiment_analysis

A/B test and experiment analysis.

**Description:** Framework for analyzing experiment results.

**Workflow steps:**

1. Identify experiment cohorts
2. Define success metrics
3. Query metric values per cohort
4. Calculate statistical significance
5. Analyze segment performance
6. Make recommendations

**When to use:** Analyzing A/B tests or feature experiments.

---

## MCP Capabilities

The server leverages advanced MCP features for enhanced functionality.

| Feature | Usage | Graceful Degradation |
|---------|-------|---------------------|
| **Sampling** | `ctx.sample()` for LLM analysis of query results | Returns raw data with hints |
| **Elicitation** | `ctx.elicit()` for interactive workflows | Proceeds with warning |
| **Tasks** | Progress reporting via `ctx.report_progress()` | Synchronous execution |
| **Middleware** | Request interception for caching, rate limiting, audit | N/A |

### Sampling (ctx.sample)

Used by Tier 3 intelligent tools to synthesize query results. When the AI assistant processes tool results, it can understand and explain complex patterns.

**Example flow:**

1. `diagnose_metric_drop` queries multiple dimensions
2. Results are passed to `ctx.sample()` with analysis prompt
3. LLM synthesizes findings into actionable insights

### Elicitation (ctx.elicit)

Used by interactive tools to request user confirmation or input.

**Example flow:**

1. `safe_large_fetch` estimates data volume
2. If large, `ctx.elicit()` asks for confirmation
3. User confirms or cancels
4. Fetch proceeds based on response

### Progress Reporting (ctx.report_progress)

Long-running operations like `fetch_events` report progress:

```
Fetching events: 15,234 / ~50,000 (30%)
```

---

## Middleware Layer

Cross-cutting concerns handled transparently.

### Caching

Discovery tools cache responses to reduce API calls.

| Scope | TTL | Tools Affected |
|-------|-----|----------------|
| Schema | 5 minutes | list_events, list_properties, list_funnels, etc. |

### Rate Limiting

Respects Mixpanel API limits automatically.

| API | Rate Limit | Concurrent Limit |
|-----|------------|------------------|
| Query API | 60/hour | 5 concurrent |
| Export API | 60/hour, 3/sec | 100 concurrent |

When limits are reached, requests are queued and wait time is reported.

### Audit Logging

All tool invocations are logged with:

- Tool name
- Parameters
- Execution time
- Result summary
- Errors (if any)
