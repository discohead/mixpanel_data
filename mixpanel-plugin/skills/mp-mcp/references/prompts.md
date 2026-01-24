# MCP Prompts Reference

Prompts provide structured templates that guide users through analytics workflows and best practices.

## Available Prompts

### analytics_workflow

Guide through a complete analytics exploration workflow.

**Parameters**: None

**Workflow Steps**:
1. **Discover Your Schema** - Use `list_events`, `list_funnels`, `list_cohorts`
2. **Explore Key Events** - Use `list_properties`, `top_events`
3. **Run Initial Analysis** - Use `segmentation`, `funnel`, `retention`
4. **Deep Dive with Local Data** - Use `fetch_events`, `sql`, `sample`

**Best For**: New users exploring a Mixpanel project for the first time.

---

### funnel_analysis

Guide through funnel analysis workflow.

**Parameters**:
- `funnel_name`: Name of the funnel to analyze (default: "signup")

**Workflow Steps**:
1. **Find Your Funnel** - Use `list_funnels` to get funnel ID
2. **Analyze Conversion** - Use `funnel` for overall and step-by-step conversion
3. **Segment the Analysis** - Add segment parameters to break down by user properties
4. **Identify Improvements** - Find high drop-off steps and better-converting segments

**Best For**: Understanding conversion paths and identifying bottlenecks.

---

### retention_analysis

Guide through retention analysis workflow.

**Parameters**:
- `event`: The birth event for cohort analysis (default: "signup")

**Workflow Steps**:
1. **Define the Cohort** - Choose born event and return event
2. **Choose Time Frame** - Recent (30 days) for trends, historical for patterns
3. **Run Retention Analysis** - Use `retention` with appropriate parameters
4. **Interpret Results** - D1, D7, D30 retention benchmarks
5. **Compare Segments** - Analyze by source, user type, onboarding

**Best For**: Understanding user stickiness and long-term engagement.

---

### local_analysis_workflow

Guide through local data analysis with SQL.

**Parameters**: None

**Workflow Steps**:
1. **Fetch Your Data** - Use `fetch_events` to download to local storage
2. **Explore the Data** - Use `list_tables`, `table_schema`, `sample`
3. **Query with SQL** - Use `sql` for custom analysis
4. **Advanced Analysis** - Join events with profiles, calculate user-level metrics
5. **Clean Up** - Use `drop_table` when done

**Best For**: Complex analysis requiring custom SQL queries.

---

### gqm_decomposition

Goal-Question-Metric decomposition prompt.

**Parameters**:
- `goal`: The high-level goal to investigate (default: "understand user retention")

**Framework**:
- **Goal**: Define what you want to achieve (conceptual level)
- **Questions**: Identify what you need to know (operational level)
- **Metrics**: Determine what to measure (quantitative level)

**Workflow Steps**:
1. **Clarify the Goal** - Define business outcome, stakeholders, success criteria
2. **Generate Questions** - Current state, trends, segments, correlations, external factors
3. **Define Metrics** - Primary, supporting, and leading indicators
4. **Execute the Investigation** - Use appropriate tools
5. **Synthesize Findings** - Patterns, hypotheses, recommendations

**Best For**: Structured investigation of complex analytics questions.

---

### growth_accounting

AARRR (Pirate Metrics) growth accounting prompt.

**Parameters**:
- `acquisition_event`: The event that marks user acquisition (default: "signup")

**AARRR Stages**:
1. **Acquisition** - How users find you (2-5% landing page conversion B2C, 5-15% B2B)
2. **Activation** - First value experience (20-40% onboarding completion)
3. **Retention** - Users coming back (D1: 25-40% consumer, D7: 15-25%)
4. **Revenue** - Monetization (2-5% free to paid)
5. **Referral** - Users bringing others (5-10% referral rate)

**Suggested Tools**:
- `segmentation` and `property_counts` for acquisition analysis
- `funnel` for activation steps
- `retention` for stickiness
- Quick overview: `product_health_dashboard`

**Best For**: Comprehensive product health analysis with industry benchmarks.

---

### experiment_analysis

A/B test evaluation prompt.

**Parameters**:
- `experiment_name`: Name of the experiment to analyze (default: "homepage_redesign")

**Pre-Analysis Checklist**:
- Control and treatment groups properly defined
- Sufficient sample size
- Test ran for 1-2 business cycles
- No overlapping experiments

**Analysis Steps**:
1. **Segment the Data** - Use `cohort_comparison` for variant separation
2. **Check Sample Sizes** - Minimum 100 conversions per variant
3. **Calculate Results** - Conversion rate, lift, p-value, confidence interval
4. **Interpret Results** - Significant positive = ship, negative = don't ship, not significant = need more data
5. **Consider Segments** - Check effects by user type, platform, geography

**Common Pitfalls**:
- Peeking (checking too early)
- Cherry-picking (only reporting winners)
- Ignoring segments
- Ignoring practical significance

**Best For**: Rigorous A/B test analysis with statistical considerations.

---

### data_quality_audit

Data quality audit prompt.

**Parameters**:
- `event`: Primary event to audit (default: "signup")

**Audit Dimensions**:

1. **Event Coverage Audit**
   - Is the event firing consistently?
   - Are there gaps in the data?
   - Red flags: >50% day-over-day variance, missing days, bot patterns

2. **Property Completeness Audit**
   - What properties are captured?
   - What % have each property?
   - Check: user identification, timestamp, device, attribution

3. **Identity Resolution Audit**
   - Are users properly identified?
   - Is identity stitching working?
   - Red flags: high anonymous %, shared IDs, duplicate profiles

4. **Data Freshness Audit**
   - How recent is the data?
   - Is there processing lag?
   - Red flags: events >24h late, timestamp inconsistencies

5. **Schema Consistency Audit**
   - Are property names consistent?
   - Are data types stable?
   - Best practices: consistent naming, typed values, no PII

**Best For**: Assessing data implementation quality and reliability.

---

## Prompt Usage Patterns

### Discovery -> Analysis Flow

```
1. Request "analytics_workflow" prompt
2. Follow schema discovery steps
3. Choose analysis type based on findings
4. Request specific prompt (funnel_analysis, retention_analysis, etc.)
```

### Investigation Flow

```
1. Request "gqm_decomposition" prompt with your goal
2. Work through Goal -> Questions -> Metrics
3. Use suggested tools to gather data
4. Synthesize findings
```

### Product Review Flow

```
1. Request "growth_accounting" prompt
2. Analyze each AARRR stage
3. Compare to industry benchmarks
4. Identify weakest areas for improvement
```

### Quality Check Flow

```
1. Request "data_quality_audit" prompt
2. Work through each audit dimension
3. Document findings and red flags
4. Create prioritized fix list
```
