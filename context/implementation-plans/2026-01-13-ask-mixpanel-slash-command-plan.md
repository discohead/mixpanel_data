# `/ask-mixpanel` Slash Command: Natural Language Analytics for Claude Code

## Executive Summary

This document defines the implementation of `/ask-mixpanel`, a Claude Code slash command that enables natural language analytics queries against Mixpanel data. Unlike the MCP `ask_mixpanel` tool (which uses `ctx.sample()` for LLM synthesis), this implementation leverages Claude Code's **native capabilities**: the `mp` CLI, `mixpanel_data` Python library, and subagent orchestration.

### Vision

> **Ask analytics questions in plain English. Get answers powered by full programmatic analysis.**

```
/ask-mixpanel why did retention drop this week?
```

The command spawns an intelligent orchestrator agent that:
1. Explores the Mixpanel schema via `mp` CLI
2. Classifies the question type (retention, funnel, trend, segment)
3. Executes queries via CLI or writes custom Python analysis scripts
4. Spawns specialist subagents for parallel deep dives
5. Synthesizes findings into actionable insights

### Why Not MCP Sampling?

| MCP `ctx.sample()` | Claude Code Subagents |
|-------------------|----------------------|
| Single-shot LLM call with fixed context | Multi-turn reasoning with iteration |
| No tool access within sample | Full access to Bash, Python, all tools |
| Predefined output format | Custom analysis scripts, DuckDB SQL |
| Can't iterate or explore | Run → analyze → adjust → re-run |
| Limited to MCP tool catalog | Full `mixpanel_data` API surface |

Claude Code subagents writing and executing Python scripts **is** the sampling equivalent—but with full programmatic power.

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  USER: /ask-mixpanel why did retention drop this week?                  │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  SLASH COMMAND: commands/ask-mixpanel.md                                │
│                                                                         │
│  1. Parse question and extract hints (dates, metrics, events)          │
│  2. Load mixpanel-data SKILL for API/CLI reference                     │
│  3. Spawn ask-mixpanel-orchestrator SUBAGENT                           │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  SUBAGENT: agents/ask-mixpanel-orchestrator.md                          │
│                                                                         │
│  DISCOVERY PHASE:                                                       │
│  • mp inspect events                                                    │
│  • mp query top-events --limit 10                                       │
│                                                                         │
│  CLASSIFICATION:                                                        │
│  • Retention? Funnel? Trend? Segment comparison?                       │
│                                                                         │
│  EXECUTION:                                                             │
│  ├─ Simple query → mp query segmentation/retention/funnel              │
│  └─ Complex analysis → Write + execute Python script                   │
│                                                                         │
│  PARALLEL DEEP DIVES:                                                   │
│  • Spawn specialist agents via Task tool                               │
│                                                                         │
│  SYNTHESIS:                                                             │
│  • Combine findings into actionable insights                           │
└────────┬────────────────────────┬────────────────────────┬──────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ retention-      │    │ mixpanel-       │    │ funnel-         │
│ specialist      │    │ explorer        │    │ optimizer       │
│                 │    │                 │    │                 │
│ Deep retention  │    │ Broad discovery │    │ Funnel-specific │
│ analysis        │    │ and exploration │    │ analysis        │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         └──────────────────────┴──────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  NATIVE INTERFACES                                                      │
│                                                                         │
│  CLI (Bash):                      Python (Script Execution):            │
│  • mp inspect events              • from mixpanel_data import Workspace │
│  • mp query segmentation          • ws.retention(...)                   │
│  • mp query retention             • ws.cohort_comparison(...)           │
│  • mp fetch events                • ws.sql("SELECT ...")                │
│  • mp query sql                   • Custom analysis logic               │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Hierarchy

```
mixpanel-plugin/
├── .claude-plugin/
│   └── plugin.json                    # Plugin manifest (update)
├── commands/
│   └── ask-mixpanel.md               # NEW: Slash command entry point
├── agents/
│   ├── ask-mixpanel-orchestrator.md  # NEW: Orchestration agent
│   ├── mixpanel-explorer.md          # EXISTS: Quick discovery
│   ├── mixpanel-analyst.md           # EXISTS: General analysis
│   ├── retention-specialist.md       # EXISTS: Retention deep dives
│   ├── funnel-optimizer.md           # EXISTS: Funnel analysis
│   └── jql-expert.md                 # EXISTS: Complex JQL
└── skills/
    └── mixpanel-data/
        ├── SKILL.md                  # UPDATE: Add CLI/Python patterns
        └── references/
            ├── cli-reference.md      # NEW: mp CLI command reference
            ├── python-api.md         # NEW: mixpanel_data API patterns
            └── analysis-patterns.md  # NEW: Common analysis workflows
```

---

## Component Specifications

### 1. Slash Command: `ask-mixpanel.md`

**Location**: `mixpanel-plugin/commands/ask-mixpanel.md`

```yaml
---
description: Ask natural language analytics questions about Mixpanel data
arguments:
  - name: question
    description: Your analytics question in natural language
    required: true
allowed_tools:
  - Task
  - Bash
  - Read
  - Write
---
```

**Command Body**:

```markdown
# /ask-mixpanel

You are answering a natural language analytics question about Mixpanel data.

## Question
${ARGUMENTS.question}

## Instructions

1. **Load Context**: Read the mixpanel-data skill for CLI and Python API reference
2. **Spawn Orchestrator**: Use the Task tool to spawn the `ask-mixpanel-orchestrator` agent

The orchestrator will:
- Explore the Mixpanel schema
- Classify your question
- Execute appropriate queries
- Provide synthesized insights

## Spawn Command

Use this exact Task invocation:

```
Task(
  subagent_type="mixpanel-data:ask-mixpanel-orchestrator",
  prompt="Answer this analytics question: ${ARGUMENTS.question}"
)
```
```

### 2. Orchestrator Agent: `ask-mixpanel-orchestrator.md`

**Location**: `mixpanel-plugin/agents/ask-mixpanel-orchestrator.md`

```markdown
# Ask Mixpanel Orchestrator

You are an intelligent analytics orchestrator. Given a natural language
question about Mixpanel data, you investigate, analyze, and synthesize
insights using the `mp` CLI and `mixpanel_data` Python library.

## Workflow

### Phase 1: Discovery

Always start by understanding the available data:

```bash
# List available events
mp inspect events

# See most active events
mp query top-events --limit 10 --type unique
```

### Phase 2: Question Classification

Classify the question to determine analysis approach:

| Pattern | Question Type | Primary Tool |
|---------|--------------|--------------|
| "drop", "decline", "decreased" | Retention/Metric Drop | `mp query retention` + diagnose |
| "conversion", "funnel", "checkout" | Funnel Analysis | `mp query funnel` |
| "trend", "over time", "changed" | Trend Analysis | `mp query segmentation` |
| "compare", "vs", "versus" | Segment Comparison | Python cohort_comparison |
| "which users", "who" | User Segmentation | `mp query segmentation --segment` |
| "why", "root cause" | Diagnostic | Multi-tool investigation |

### Phase 3: Execution Strategy

**For simple queries** - Use CLI directly:

```bash
# Retention analysis
mp query retention --born signup --from 2026-01-01 --to 2026-01-13

# Segmentation with breakdown
mp query segmentation -e login --from 2026-01-01 --segment '$browser'

# Funnel conversion
mp query funnel --id 12345 --from 2026-01-01
```

**For complex analysis** - Write and execute Python:

```python
from mixpanel_data import Workspace
from datetime import datetime, timedelta

ws = Workspace()

# Example: Compare retention across segments
baseline_period = ("2025-12-01", "2025-12-31")
current_period = ("2026-01-01", "2026-01-13")

# Fetch retention for both periods
baseline = ws.retention(
    born_event="signup",
    from_date=baseline_period[0],
    to_date=baseline_period[1],
)
current = ws.retention(
    born_event="signup",
    from_date=current_period[0],
    to_date=current_period[1],
)

# Compare by segment
comparison = ws.cohort_comparison(
    cohort_a_filter='properties["platform"] == "ios"',
    cohort_b_filter='properties["platform"] == "android"',
    from_date=current_period[0],
    to_date=current_period[1],
)

print(f"Baseline D7: {baseline.summary['d7_retention']}")
print(f"Current D7: {current.summary['d7_retention']}")
print(f"iOS vs Android: {comparison}")
```

### Phase 4: Parallel Deep Dives

For complex questions, spawn specialist agents in parallel:

```python
# Use a single message with multiple Task calls for parallelism
Task(
  subagent_type="mixpanel-data:retention-specialist",
  prompt="Analyze retention drop for signup event from 2026-01-06 to 2026-01-13"
)

Task(
  subagent_type="mixpanel-data:mixpanel-explorer",
  prompt="Check for anomalies in signup events around 2026-01-08"
)
```

### Phase 5: Synthesis

Combine findings into actionable insights:

1. **Direct answer** to the question
2. **Key metrics** that support the answer
3. **Root cause** if diagnostic question
4. **Recommendations** for next steps
5. **Follow-up questions** to explore

## Decision Matrix: CLI vs Python

| Scenario | Use CLI | Use Python |
|----------|---------|------------|
| Single query, standard params | ✅ | - |
| View raw API response | ✅ `--format json` | - |
| Compare multiple periods | - | ✅ |
| Custom date logic | - | ✅ |
| Cohort comparison | - | ✅ |
| Complex filtering | - | ✅ |
| Parallel data fetching | - | ✅ `parallel=True` |
| SQL on fetched data | Either | Either |
| Multi-step workflow | - | ✅ |

## Agent Spawning Guide

| Question Type | Primary Agent | When to Add Secondary |
|--------------|---------------|----------------------|
| Retention drop | retention-specialist | Add explorer if cause unclear |
| Funnel optimization | funnel-optimizer | Add analyst for custom SQL |
| General exploration | mixpanel-explorer | - |
| Complex JQL needed | jql-expert | - |
| Broad investigation | mixpanel-analyst | Add specialists as needed |

## Output Format

Structure your response as:

### Answer
[Direct answer to the question in 1-2 sentences]

### Key Findings
- [Metric 1]: [Value and interpretation]
- [Metric 2]: [Value and interpretation]

### Analysis Details
[Deeper explanation with context]

### Recommendations
1. [Actionable recommendation]
2. [Actionable recommendation]

### Suggested Follow-ups
- [Follow-up question 1]
- [Follow-up question 2]
```

### 3. Skill Update: `mixpanel-data/SKILL.md`

**Location**: `mixpanel-plugin/skills/mixpanel-data/SKILL.md`

Add these sections to the existing skill:

```markdown
## CLI Quick Reference

### Discovery Commands

```bash
# List all events
mp inspect events

# Properties for specific event
mp inspect properties login

# Saved funnels and cohorts
mp inspect funnels
mp inspect cohorts

# Most active events by unique users
mp query top-events --limit 10 --type unique
```

### Query Commands

```bash
# Segmentation (time series)
mp query segmentation -e login --from 2026-01-01 --to 2026-01-13
mp query segmentation -e login --segment '$browser' --unit week

# Retention
mp query retention --born signup --from 2026-01-01
mp query retention --born signup --return purchase --unit week

# Funnel (requires saved funnel ID)
mp query funnel --id 12345 --from 2026-01-01

# Property distribution
mp query property-counts -e login -p '$browser' --limit 10

# Compare multiple events
mp query event-counts -e login -e signup -e purchase --type unique
```

### Fetch + Local SQL

```bash
# Fetch events to local DuckDB
mp fetch events --from 2026-01-01 --to 2026-01-07 --table jan_events

# Query local data
mp query sql "SELECT name, COUNT(*) FROM jan_events GROUP BY name"

# Fetch with filters
mp fetch events --from 2026-01-01 --events login,signup --table signups
```

### Output Formats

```bash
# JSON output (for parsing)
mp query segmentation -e login --format json

# Table output (human readable)
mp query segmentation -e login --format table

# CSV output (for export)
mp query segmentation -e login --format csv
```

## Python API Patterns

### Basic Workspace Usage

```python
from mixpanel_data import Workspace

# Initialize (uses environment credentials)
ws = Workspace()

# Discovery
events = ws.events()
properties = ws.properties("login")

# Live queries
segmentation = ws.segmentation(
    event="login",
    from_date="2026-01-01",
    to_date="2026-01-13",
    on='properties["browser"]',
)

retention = ws.retention(
    born_event="signup",
    from_date="2026-01-01",
    to_date="2026-01-13",
    unit="day",
)
```

### Cohort Comparison

```python
# Compare two user segments
comparison = ws.cohort_comparison(
    cohort_a_filter='properties["platform"] == "ios"',
    cohort_b_filter='properties["platform"] == "android"',
    cohort_a_name="iOS Users",
    cohort_b_name="Android Users",
    from_date="2026-01-01",
    to_date="2026-01-13",
)
```

### Fetch + SQL Analysis

```python
# Fetch events to local storage
result = ws.fetch_events(
    from_date="2026-01-01",
    to_date="2026-01-07",
    table="jan_events",
    events=["login", "signup"],
    parallel=True,
    workers=4,
)

# Query with SQL
df = ws.sql("""
    SELECT
        properties->>'$.browser' as browser,
        COUNT(*) as event_count,
        COUNT(DISTINCT distinct_id) as unique_users
    FROM jan_events
    WHERE name = 'login'
    GROUP BY browser
    ORDER BY event_count DESC
""")
```

### GQM Investigation

```python
# Goal-Question-Metric investigation
investigation = ws.gqm_investigation(
    goal="understand why retention is declining",
    from_date="2026-01-01",
    to_date="2026-01-13",
)
```

## Analysis Pattern Templates

### Retention Drop Investigation

```python
from mixpanel_data import Workspace

ws = Workspace()

# 1. Get current vs baseline retention
current = ws.retention(born_event="signup", from_date="2026-01-06", to_date="2026-01-13")
baseline = ws.retention(born_event="signup", from_date="2025-12-23", to_date="2025-12-30")

# 2. Segment by common dimensions
for dimension in ["$browser", "$os", "mp_country_code"]:
    current_seg = ws.segmentation(
        event="signup",
        from_date="2026-01-06",
        to_date="2026-01-13",
        on=f'properties["{dimension}"]',
    )
    # Compare segments to find anomalies

# 3. Diagnose specific drop
diagnosis = ws.diagnose_metric_drop(
    event="signup",
    date="2026-01-10",
    dimensions=["$browser", "$os"],
)
```

### Funnel Optimization

```python
from mixpanel_data import Workspace

ws = Workspace()

# 1. Get funnel performance
funnel = ws.funnel(funnel_id=12345, from_date="2026-01-01", to_date="2026-01-13")

# 2. Segment by key dimensions
for segment in ["$device_type", "utm_source"]:
    segmented = ws.funnel(
        funnel_id=12345,
        from_date="2026-01-01",
        to_date="2026-01-13",
        on=f'properties["{segment}"]',
    )
    # Identify best/worst performing segments

# 3. Get optimization report
report = ws.funnel_optimization_report(
    funnel_id=12345,
    from_date="2026-01-01",
    to_date="2026-01-13",
    segment_properties=["$device_type", "utm_source"],
)
```
```

### 4. Reference Files

Create these reference files for the skill:

**`skills/mixpanel-data/references/cli-reference.md`**:
Complete `mp` CLI command reference with all flags and examples.

**`skills/mixpanel-data/references/python-api.md`**:
Full `mixpanel_data.Workspace` API documentation with type hints.

**`skills/mixpanel-data/references/analysis-patterns.md`**:
Common analysis workflows and templates.

---

## Implementation Phases

### Phase 1: Core Infrastructure (Day 1)

| Task | File | Description |
|------|------|-------------|
| 1.1 | `commands/ask-mixpanel.md` | Create slash command |
| 1.2 | `agents/ask-mixpanel-orchestrator.md` | Create orchestrator agent |
| 1.3 | `.claude-plugin/plugin.json` | Register new command |
| 1.4 | Test basic flow | Verify command → agent spawning |

**Acceptance Criteria**:
- `/ask-mixpanel how many signups today?` spawns orchestrator
- Orchestrator runs `mp inspect events` successfully
- Basic question answered via CLI

### Phase 2: Skill Enhancement (Day 1-2)

| Task | File | Description |
|------|------|-------------|
| 2.1 | `skills/mixpanel-data/SKILL.md` | Add CLI/Python quick reference |
| 2.2 | `references/cli-reference.md` | Complete CLI documentation |
| 2.3 | `references/python-api.md` | Python API patterns |
| 2.4 | `references/analysis-patterns.md` | Analysis workflow templates |

**Acceptance Criteria**:
- Orchestrator can reference skill for CLI syntax
- Python script templates are copy-pastable
- All common patterns documented

### Phase 3: Question Classification (Day 2)

| Task | File | Description |
|------|------|-------------|
| 3.1 | `agents/ask-mixpanel-orchestrator.md` | Add classification logic |
| 3.2 | Test classification | Verify correct tool selection |

**Test Cases**:

| Question | Expected Classification | Expected Tool |
|----------|------------------------|---------------|
| "How many logins yesterday?" | Trend | CLI segmentation |
| "Why did retention drop?" | Diagnostic/Retention | Python + specialists |
| "Compare iOS vs Android" | Segment Comparison | Python cohort_comparison |
| "What's our signup funnel conversion?" | Funnel | CLI funnel |
| "Which browser has lowest retention?" | Retention + Segment | Python |

**Acceptance Criteria**:
- 90%+ classification accuracy on test cases
- Correct tool selection for each type

### Phase 4: Python Script Execution (Day 2-3)

| Task | File | Description |
|------|------|-------------|
| 4.1 | Orchestrator update | Add Python script generation |
| 4.2 | Script templates | Create reusable analysis templates |
| 4.3 | Error handling | Handle script execution failures |

**Acceptance Criteria**:
- Orchestrator can write and execute Python scripts
- Scripts use `mixpanel_data` correctly
- Errors are caught and reported gracefully

### Phase 5: Parallel Agent Spawning (Day 3)

| Task | File | Description |
|------|------|-------------|
| 5.1 | Orchestrator update | Add parallel Task spawning |
| 5.2 | Specialist coordination | Define when to spawn which agent |
| 5.3 | Result synthesis | Combine multi-agent findings |

**Acceptance Criteria**:
- Complex questions spawn multiple specialists
- Specialists run in parallel (single message, multiple Task calls)
- Results are synthesized coherently

### Phase 6: Testing & Refinement (Day 4)

| Task | Description |
|------|-------------|
| 6.1 | End-to-end testing with real Mixpanel data |
| 6.2 | Edge case handling (no data, API errors, etc.) |
| 6.3 | Output format refinement |
| 6.4 | Documentation updates |

**Test Scenarios**:
1. Simple question with immediate CLI answer
2. Complex diagnostic requiring Python analysis
3. Multi-agent parallel investigation
4. Error handling (invalid event, API timeout)
5. Follow-up question in same session

---

## Example Flows

### Flow 1: Simple Query (CLI Path)

```
User: /ask-mixpanel how many signups this week?

Orchestrator:
1. Runs: mp inspect events
   → Finds: signup event exists

2. Classifies: Trend query, simple count

3. Runs: mp query segmentation -e signup --from 2026-01-06 --to 2026-01-13

4. Returns:
   ### Answer
   There were 1,247 signups this week (Jan 6-13, 2026).

   ### Key Findings
   - Total signups: 1,247
   - Daily average: 178
   - Peak day: Tuesday (Jan 7) with 245 signups

   ### Suggested Follow-ups
   - How does this compare to last week?
   - What's the signup-to-purchase conversion rate?
```

### Flow 2: Diagnostic Query (Python Path)

```
User: /ask-mixpanel why did retention drop this week?

Orchestrator:
1. Runs: mp inspect events
   → Finds: signup, login, purchase events

2. Classifies: Diagnostic + Retention

3. Runs: mp query retention --born signup --from 2026-01-06
   → D7 retention: 12% (was 18% last week)

4. Writes Python script for segment analysis:
   ```python
   from mixpanel_data import Workspace
   ws = Workspace()

   for dim in ["$browser", "$os", "mp_country_code"]:
       current = ws.segmentation(event="signup", on=f'properties["{dim}"]', ...)
       # Analyze each segment
   ```

5. Executes script, finds: Chrome dropped 25%, others stable

6. Spawns retention-specialist:
   "Deep dive on Chrome user retention drop Jan 6-13"

7. Synthesizes:
   ### Answer
   Retention dropped from 18% to 12% due to Chrome 120 compatibility issues.

   ### Key Findings
   - Overall D7 retention: 12% (down from 18%)
   - Chrome users: 8% retention (down from 20%)
   - Safari/Firefox: 18% retention (stable)
   - Chrome 120 rollout: Jan 8, 2026

   ### Root Cause
   Chrome 120 introduced breaking changes affecting our login flow.
   Users on Chrome 120+ fail to complete authentication 25% more often.

   ### Recommendations
   1. Investigate Chrome 120 console errors in login flow
   2. Check for deprecated API usage in auth code
   3. Consider browser-specific fallback handling

   ### Suggested Follow-ups
   - Which specific login step fails for Chrome users?
   - What's the error rate in Chrome vs other browsers?
```

### Flow 3: Parallel Agent Investigation

```
User: /ask-mixpanel what's causing low conversion and is it affecting retention?

Orchestrator:
1. Classifies: Multi-faceted diagnostic (funnel + retention)

2. Spawns in parallel (single message):
   Task(subagent_type="funnel-optimizer", prompt="Analyze main conversion funnel")
   Task(subagent_type="retention-specialist", prompt="Check if retention correlates with conversion issues")

3. funnel-optimizer returns:
   - Checkout step has 35% drop-off
   - Mobile users 2x higher drop-off than desktop

4. retention-specialist returns:
   - Users who complete checkout have 3x better retention
   - Mobile users who drop off rarely return

5. Orchestrator synthesizes:
   ### Answer
   Low conversion at checkout (35% drop-off) is directly causing retention issues,
   especially for mobile users.

   ### Key Findings
   - Checkout drop-off: 35% overall, 52% on mobile
   - Retention correlation: Checkout completers retain 3x better
   - Mobile users who abandon: 5% return rate

   ### Root Cause
   Mobile checkout UX issues causing abandonment, which cascades into
   poor retention as frustrated users don't return.

   ### Recommendations
   1. Audit mobile checkout flow for UX friction
   2. Implement checkout abandonment recovery emails
   3. Add payment method variety for mobile

   ### Suggested Follow-ups
   - What specific checkout step has highest mobile drop-off?
   - Do recovered abandoned carts have better retention?
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Question answerable rate | 90%+ | % of questions that produce useful output |
| Classification accuracy | 90%+ | Correct tool/agent selection |
| Response time (simple) | <10s | CLI-only queries |
| Response time (complex) | <60s | Multi-agent investigations |
| User satisfaction | 4.5/5 | Qualitative feedback |

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| API rate limiting | Use local DuckDB for heavy analysis |
| Credential issues | Clear error messages, point to `mp auth` |
| No matching events | Suggest similar events, run discovery |
| Script execution fails | Catch errors, fallback to CLI |
| Agent spawning overhead | Use parallel spawning, cache skill context |

---

## Future Enhancements

### Phase 2: Conversational Context

- Remember previous questions in session
- "Compare that to last month" follow-ups
- Build on previous analysis results

### Phase 3: Visualization

- Generate charts via Python matplotlib
- Export to common formats (PNG, SVG)
- Inline display in terminal

### Phase 4: Scheduled Analysis

- `/ask-mixpanel schedule daily: what's our DAU?`
- Hook-based alerts for metric changes
- Automated reporting

### Phase 5: Learning

- Track which patterns work well
- Suggest improvements to CLAUDE.md
- Refine classification over time

---

## Appendix: File Checklist

**New Files**:
- [ ] `commands/ask-mixpanel.md`
- [ ] `agents/ask-mixpanel-orchestrator.md`
- [ ] `skills/mixpanel-data/references/cli-reference.md`
- [ ] `skills/mixpanel-data/references/python-api.md`
- [ ] `skills/mixpanel-data/references/analysis-patterns.md`

**Updated Files**:
- [ ] `.claude-plugin/plugin.json` (add command registration)
- [ ] `skills/mixpanel-data/SKILL.md` (add CLI/Python sections)
- [ ] Existing specialist agents (ensure parallel compatibility)

---

## References

- [mixpanel_data Design Doc](../mixpanel_data-design.md)
- [mp CLI Specification](../mp-cli-project-spec.md)
- [MCP Server v2 Plan](./2026-01-13-mcp-server-v2-enhancements-plan.md) (contrast with MCP approach)
- [Claude Code Plugin Development](https://docs.anthropic.com/en/docs/claude-code/plugins)
