---
description: Generate retention analysis and retention curves from Mixpanel data
allowed-tools: Bash(mp query retention:*), Bash(mp query sql:*), Bash(mp inspect:*)
argument-hint: [born-event] [return-event]
---

# Mixpanel Retention Analysis

Guide the user through building retention analyses and retention curves to understand user behavior over time.

## Pre-flight Check

Verify credentials are configured:

```bash
!$(mp auth test 2>&1 || echo "No credentials configured")
```

If not configured, suggest running `/mp-auth` first.

## Retention Analysis Types

Present three analysis types:

1. **Retention Analysis** - How many users return after initial action (Live API)
2. **Cohort Behavior** - Compare behavior across user cohorts (Local SQL)
3. **Time-to-Event** - How long until users perform key actions (Local SQL)

Ask which type the user wants to perform.

---

## Type 1: Retention Analysis (Live API)

Classic retention: What % of users return to perform an action?

### 1. Define Cohort Entry Event

**Born Event**: Event that defines cohort membership
- Use `$1` if provided, otherwise ask

**Examples**:
- "Sign Up" - New user cohorts
- "First Purchase" - Buyer cohorts
- "Feature Activation" - Feature adoption cohorts

### 2. Define Return Event

**Return Event**: Event indicating user returned
- Use `$2` if provided, otherwise ask

**Examples**:
- "Login" - General activity
- "Purchase" - Repeat purchases
- "Feature Use" - Continued feature use

### 3. Configure Analysis Parameters

**Date Range**:
- From date (YYYY-MM-DD)
- To date (YYYY-MM-DD)
- This defines when cohorts are created (born event window)

**Time Unit**:
- `day` - Daily cohorts (good for recent data)
- `week` - Weekly cohorts (recommended for most analyses)
- `month` - Monthly cohorts (good for long-term trends)

**Retention Intervals**:
- Number of intervals to track (default: 11)
- Example: 11 weeks means track retention for 11 weeks after cohort birth

**Filters** (optional):
- `--born-where`: Filter cohort entry (e.g., only organic signups)
- `--return-where`: Filter return events (e.g., only purchases >$50)

### 4. Execute Retention Query

**Basic retention**:
```bash
mp query retention \
  --born "<born-event>" \
  --return "<return-event>" \
  --from <from-date> \
  --to <to-date> \
  --unit <day|week|month> \
  --format table
```

**With filters**:
```bash
mp query retention \
  --born "Sign Up" \
  --return "Purchase" \
  --from 2024-01-01 \
  --to 2024-01-31 \
  --unit week \
  --interval-count 12 \
  --born-where 'properties["source"] == "organic"' \
  --return-where 'properties["amount"] > 50' \
  --format table
```

### 5. Interpret Retention Results

**Key metrics to highlight**:

**Day 0 Retention**: % who return on the same day/week/month
> 📊 Day 0: X% - This is your immediate activation rate

**Day 1/Week 1 Retention**: First return after initial period
> 📊 Week 1: X% - Critical metric for product stickiness

**Long-term Retention**: Retention at final interval
> 📊 Week 11: X% - Shows long-term value

**Retention Curve Shape**:
- **Steep decline**: Poor onboarding or value prop
- **Gradual decline**: Natural attrition
- **Flattening**: Found product-market fit
- **Uptick**: Reactivation campaigns working

### 6. Visualize Retention Curve

Offer to create visualization:

```python
import pandas as pd
import matplotlib.pyplot as plt

# Assuming retention data from query
intervals = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
retention_rates = [100, 45, 38, 35, 32, 30, 28, 27, 26, 25, 24, 24]

fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(intervals, retention_rates, marker='o', linewidth=2, markersize=8)
ax.set_xlabel('Weeks Since Cohort Birth')
ax.set_ylabel('Retention Rate (%)')
ax.set_title('User Retention Curve')
ax.grid(True, alpha=0.3)
ax.axhline(y=retention_rates[-1], color='r', linestyle='--', alpha=0.5, label=f'Stabilized at {retention_rates[-1]}%')

plt.legend()
plt.tight_layout()
plt.savefig('retention_curve.png')
print("Retention curve saved to retention_curve.png")
```

---

## Type 2: Cohort Behavior Analysis (Local SQL)

Compare how different cohorts behave over time.

### 1. Check Available Tables

```bash
!$(mp inspect tables --format table)
```

If no tables, suggest `/mp-fetch` first. Run `/mp-inspect tables` to explore local data structure.

### 2. Define Cohorts

**Cohort definition options**:

**Time-based cohorts**:
- Weekly cohorts (users who signed up each week)
- Monthly cohorts (users who signed up each month)

**Property-based cohorts**:
- Acquisition channel (organic, paid, referral)
- User segment (free, premium, enterprise)
- Geographic region

Ask the user which cohort dimension to analyze.

### 3. Build Cohort SQL Query

**Weekly Cohort Analysis**:

```sql
WITH user_cohorts AS (
  -- Assign each user to their cohort (week of first event)
  SELECT
    distinct_id,
    DATE_TRUNC('week', MIN(event_time)) as cohort_week
  FROM <table>
  GROUP BY distinct_id
),
cohort_activity AS (
  -- Track activity by cohort and activity week
  SELECT
    c.cohort_week,
    DATE_TRUNC('week', e.event_time) as activity_week,
    COUNT(DISTINCT e.distinct_id) as active_users
  FROM <table> e
  JOIN user_cohorts c ON e.distinct_id = c.distinct_id
  GROUP BY c.cohort_week, activity_week
),
cohort_sizes AS (
  -- Get cohort sizes
  SELECT
    cohort_week,
    COUNT(DISTINCT distinct_id) as cohort_size
  FROM user_cohorts
  GROUP BY cohort_week
)
SELECT
  ca.cohort_week,
  ca.activity_week,
  cs.cohort_size,
  ca.active_users,
  ROUND(100.0 * ca.active_users / cs.cohort_size, 2) as retention_rate,
  FLOOR(DATEDIFF('day', ca.cohort_week, ca.activity_week) / 7) as weeks_since_cohort
FROM cohort_activity ca
JOIN cohort_sizes cs ON ca.cohort_week = cs.cohort_week
ORDER BY ca.cohort_week, ca.activity_week
```

**Property-based Cohort Comparison**:

```sql
WITH user_cohorts AS (
  SELECT
    distinct_id,
    properties->>'$.source' as cohort_source,
    MIN(event_time) as first_seen
  FROM <table>
  WHERE event_name = 'Sign Up'
  GROUP BY distinct_id, properties->>'$.source'
),
cohort_metrics AS (
  SELECT
    c.cohort_source,
    COUNT(DISTINCT e.distinct_id) as total_users,
    AVG(CASE WHEN e.event_name = 'Purchase' THEN 1 ELSE 0 END) as purchase_rate,
    AVG(CAST(e.properties->>'$.amount' AS DOUBLE)) as avg_revenue
  FROM <table> e
  JOIN user_cohorts c ON e.distinct_id = c.distinct_id
  GROUP BY c.cohort_source
)
SELECT * FROM cohort_metrics
ORDER BY total_users DESC
```

### 4. Create Cohort Heatmap

Offer to generate a retention heatmap:

```python
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# Query results transformed to pivot table
# cohort_week on y-axis, weeks_since_cohort on x-axis, retention_rate as values

df = pd.DataFrame({
    'cohort_week': [...],
    'weeks_since_cohort': [...],
    'retention_rate': [...]
})

pivot = df.pivot(index='cohort_week', columns='weeks_since_cohort', values='retention_rate')

fig, ax = plt.subplots(figsize=(15, 8))
sns.heatmap(pivot, annot=True, fmt='.1f', cmap='RdYlGn', ax=ax,
            cbar_kws={'label': 'Retention Rate (%)'})
ax.set_title('Cohort Retention Heatmap')
ax.set_xlabel('Weeks Since Cohort Birth')
ax.set_ylabel('Cohort Week')
plt.tight_layout()
plt.savefig('cohort_heatmap.png')
print("Cohort heatmap saved to cohort_heatmap.png")
```

---

## Type 3: Time-to-Event Analysis

Analyze how long it takes users to reach milestones.

### 1. Define Events

**Starting Event**: Where the clock starts (e.g., "Sign Up")
**Target Event**: What we're measuring time to (e.g., "First Purchase")

### 2. Build Time-to-Event Query

```sql
WITH user_events AS (
  SELECT
    distinct_id,
    MIN(CASE WHEN event_name = '<start-event>' THEN event_time END) as start_time,
    MIN(CASE WHEN event_name = '<target-event>' THEN event_time END) as target_time
  FROM <table>
  GROUP BY distinct_id
),
time_to_event AS (
  SELECT
    distinct_id,
    start_time,
    target_time,
    DATEDIFF('day', start_time, target_time) as days_to_convert,
    DATEDIFF('hour', start_time, target_time) as hours_to_convert
  FROM user_events
  WHERE start_time IS NOT NULL
    AND target_time IS NOT NULL
    AND target_time > start_time
)
SELECT
  -- Bucket by days
  CASE
    WHEN days_to_convert = 0 THEN 'Same day'
    WHEN days_to_convert <= 1 THEN '1 day'
    WHEN days_to_convert <= 7 THEN '2-7 days'
    WHEN days_to_convert <= 30 THEN '1-4 weeks'
    WHEN days_to_convert <= 90 THEN '1-3 months'
    ELSE '3+ months'
  END as time_bucket,
  COUNT(*) as users,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct_of_total
FROM time_to_event
GROUP BY time_bucket
ORDER BY MIN(days_to_convert)
```

### 3. Calculate Key Metrics

Show distribution metrics:
- **Median time-to-event**: 50th percentile
- **90th percentile**: Most users convert by this time
- **Conversion rate**: % of users who reached target event

```sql
SELECT
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY days_to_convert) as median_days,
  PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY days_to_convert) as p90_days,
  COUNT(*) as converted_users
FROM time_to_event
```

---

## Cohort Insights and Recommendations

### Strong Retention Indicators

> ✅ **Healthy retention** detected:
> - Week 1 retention > 40%
> - Curve flattens after week 4
> - Long-term retention > 20%
>
> **This indicates**: Strong product-market fit

### Weak Retention Indicators

> ⚠️ **Retention concerns** detected:
> - Steep drop-off in first week
> - Week 1 retention < 25%
> - Continuous decline without flattening
>
> **Recommendations**:
> - Improve onboarding experience
> - Add early activation hooks
> - Survey churned users
> - Implement retention campaigns

### Cohort Comparison Insights

> 📊 **Cohort performance varies**:
> - [Best cohort]: X% higher retention than average
> - [Worst cohort]: Y% lower retention
>
> **Investigate**:
> - What was different about successful cohorts?
> - Product changes during that period?
> - Marketing campaign differences?
> - External factors (seasonality, competition)?

---

## Next Steps

After cohort analysis, suggest:

1. **Deep dive on specific cohort**:
   ```bash
   /mp-query sql
   # Analyze behavior of specific cohort
   ```

2. **Segment retention by property**:
   ```bash
   mp query retention --born "Sign Up" --return "Login" \
     --from 2024-01-01 --to 2024-01-31 --on source
   ```

3. **Export for stakeholders**:
   ```bash
   mp query retention [...] --format csv > retention_report.csv
   ```

4. **Create dashboard report**:
   ```bash
   /mp-report cohort
   # Generate comprehensive cohort report
   ```

---

## Troubleshooting

**"No retention data"**:
- Verify born event exists: `mp inspect events`
- Check date range includes cohort births
- Ensure return event is tracked

**"All retention is 0%"**:
- Return event might not be occurring
- Check event names are exact matches
- Verify time window is appropriate

**"Cohort sizes too small"**:
- Expand date range for cohort births
- Use weekly/monthly instead of daily cohorts
- Check if filtering is too restrictive
