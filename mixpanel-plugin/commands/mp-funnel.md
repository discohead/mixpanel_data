---
description: Interactive wizard to build and analyze conversion funnels from Mixpanel data
allowed-tools: Bash(mp query funnel:*), Bash(mp inspect:*)
argument-hint: [funnel-id]
---

# Mixpanel Funnel Analysis

Guide the user through building and analyzing conversion funnels using saved Mixpanel funnels or custom event sequences.

## Pre-flight Check

Verify credentials are configured:

```bash
!$(mp auth test 2>&1 || echo "No credentials configured")
```

If credentials aren't configured, suggest running `/mp-auth` first.

## Funnel Analysis Options

Present two approaches:

1. **Saved Funnel** - Use existing funnel from Mixpanel UI (faster)
2. **Custom Funnel** - Build funnel from local event data (more flexible)

Ask which approach the user prefers.

---

## Option 1: Saved Funnel Analysis (Live API)

### 1. List Available Funnels

```bash
!$(mp inspect funnels --format table)
```

Show the user:
- Funnel ID
- Funnel name
- Number of steps

**Tip**: Use `/mp-inspect` to discover available events and cohorts for analysis context.

### 2. Select Funnel

If `$1` is provided, use that as funnel ID. Otherwise, ask user to choose from the list.

### 3. Configure Analysis Parameters

**Date Range** (required):
- From date (YYYY-MM-DD)
- To date (YYYY-MM-DD)
- Validate range is reasonable (suggest ≤ 90 days for performance)

**Time Unit** (optional):
- `day` (default)
- `week`
- `month`

**Segmentation** (optional):
- Property to segment by (e.g., `country`, `plan`, `source`)
- Shows conversion rates broken down by this property

### 4. Execute Funnel Query

**Basic funnel**:
```bash
mp query funnel <funnel-id> \
  --from <from-date> \
  --to <to-date> \
  --format table
```

**With segmentation**:
```bash
mp query funnel <funnel-id> \
  --from <from-date> \
  --to <to-date> \
  --unit <day|week|month> \
  --on <property> \
  --format table
```

### 5. Interpret Results

Show the user:
- **Overall conversion rate**: Final step / First step
- **Step-by-step drop-off**: Where users are leaving
- **Conversion rates by segment** (if segmented)

**Key insights to highlight**:
- Which step has the biggest drop-off?
- What's the overall conversion rate?
- How do segments compare?

---

## Option 2: Custom Funnel from Local Data

### 1. Check Available Tables

```bash
!$(mp inspect tables --format table)
```

If no tables exist, suggest running `/mp-fetch` first.

### 2. Define Funnel Steps

Ask the user for the event sequence (3-5 events recommended):
- Step 1: Event name (e.g., "View Product")
- Step 2: Event name (e.g., "Add to Cart")
- Step 3: Event name (e.g., "Checkout")
- Step 4: Event name (e.g., "Purchase")

### 3. Configure Analysis Parameters

**Table**: Which table to analyze
**Time window**: Maximum time between steps (e.g., 24 hours, 7 days)
**Date range**: Filter events by date

### 4. Build SQL Funnel Query

Use a window function approach to detect sequences:

```sql
WITH user_events AS (
  SELECT
    distinct_id,
    event_name,
    event_time,
    ROW_NUMBER() OVER (PARTITION BY distinct_id ORDER BY event_time) as event_seq
  FROM <table>
  WHERE event_name IN ('Step1', 'Step2', 'Step3', 'Step4')
    AND event_time >= '<from-date>'
    AND event_time <= '<to-date>'
),
funnel_progression AS (
  SELECT
    distinct_id,
    MAX(CASE WHEN event_name = 'Step1' THEN 1 ELSE 0 END) as completed_step1,
    MAX(CASE WHEN event_name = 'Step2' THEN 1 ELSE 0 END) as completed_step2,
    MAX(CASE WHEN event_name = 'Step3' THEN 1 ELSE 0 END) as completed_step3,
    MAX(CASE WHEN event_name = 'Step4' THEN 1 ELSE 0 END) as completed_step4
  FROM user_events
  GROUP BY distinct_id
)
SELECT
  SUM(completed_step1) as step1_users,
  SUM(completed_step2) as step2_users,
  SUM(completed_step3) as step3_users,
  SUM(completed_step4) as step4_users,
  ROUND(100.0 * SUM(completed_step2) / NULLIF(SUM(completed_step1), 0), 2) as step1_to_step2_rate,
  ROUND(100.0 * SUM(completed_step3) / NULLIF(SUM(completed_step2), 0), 2) as step2_to_step3_rate,
  ROUND(100.0 * SUM(completed_step4) / NULLIF(SUM(completed_step3), 0), 2) as step3_to_step4_rate,
  ROUND(100.0 * SUM(completed_step4) / NULLIF(SUM(completed_step1), 0), 2) as overall_conversion
FROM funnel_progression
```

Execute via:
```bash
mp query sql "<query>" --format table
```

### 5. Visualize Results

Offer to create a Python visualization:

```python
import pandas as pd
import matplotlib.pyplot as plt

# Data from query results
steps = ['Step1', 'Step2', 'Step3', 'Step4']
users = [<step1_users>, <step2_users>, <step3_users>, <step4_users>]

# Create funnel chart
fig, ax = plt.subplots(figsize=(10, 6))
ax.barh(steps, users, color=['#4CAF50', '#8BC34A', '#CDDC39', '#FFEB3B'])
ax.set_xlabel('Number of Users')
ax.set_title('Conversion Funnel')

# Add conversion rates
for i, (step, count) in enumerate(zip(steps, users)):
    ax.text(count, i, f' {count:,} users', va='center')

plt.tight_layout()
plt.savefig('funnel.png')
print("Funnel visualization saved to funnel.png")
```

---

## Advanced Analysis: Segmented Funnels

For local data, offer segmented funnel analysis:

**Segment by property** (e.g., country, plan, source):

```sql
WITH user_events AS (
  SELECT
    distinct_id,
    event_name,
    event_time,
    properties->>'$.country' as country
  FROM <table>
  WHERE event_name IN ('Step1', 'Step2', 'Step3', 'Step4')
),
funnel_by_segment AS (
  SELECT
    country,
    MAX(CASE WHEN event_name = 'Step1' THEN 1 ELSE 0 END) as completed_step1,
    MAX(CASE WHEN event_name = 'Step2' THEN 1 ELSE 0 END) as completed_step2,
    MAX(CASE WHEN event_name = 'Step3' THEN 1 ELSE 0 END) as completed_step3,
    MAX(CASE WHEN event_name = 'Step4' THEN 1 ELSE 0 END) as completed_step4
  FROM user_events
  GROUP BY distinct_id, country
)
SELECT
  country,
  SUM(completed_step1) as step1_users,
  ROUND(100.0 * SUM(completed_step4) / NULLIF(SUM(completed_step1), 0), 2) as conversion_rate
FROM funnel_by_segment
GROUP BY country
ORDER BY step1_users DESC
```

---

## Common Funnel Patterns

**E-commerce Funnel**:
1. Product View → Add to Cart → Checkout → Purchase

**SaaS Signup Funnel**:
1. Landing Page → Sign Up → Onboarding → First Action

**Content Engagement Funnel**:
1. Page View → Scroll Depth → Click CTA → Convert

**Mobile App Funnel**:
1. App Open → Feature Discovery → Feature Use → Retention

---

## Insights and Recommendations

After showing results, provide actionable insights:

### High Drop-off Detection

If any step shows >50% drop-off:
> ⚠️ **High drop-off detected** at Step X → Step Y (Z% drop)
>
> **Recommendations**:
> - Investigate UX issues at Step X
> - Add tracking for abandonment reasons
> - A/B test simplified flow
> - Check for technical errors

### Segment Performance Comparison

If segmented:
> 📊 **Segment insights**:
> - Best performing: [Segment A] (X% conversion)
> - Worst performing: [Segment B] (Y% conversion)
> - Delta: Z percentage points
>
> **Recommendations**:
> - Study what makes [Segment A] successful
> - Optimize experience for [Segment B]
> - Consider separate funnels per segment

### Time-Based Trends

If using time units:
> 📈 **Trend analysis**:
> - Conversion improving/declining over time
> - Seasonal patterns detected
>
> **Recommendations**:
> - Investigate what changed during improvements
> - Prepare for seasonal variations

---

## Next Steps

After analysis, suggest:

1. **Deep dive on specific step**:
   ```bash
   /mp-query sql
   # Analyze users who dropped at specific step
   ```

2. **Retention analysis**:
   ```bash
   /mp-retention
   # Analyze retention for users who completed funnel
   ```

3. **Export for presentation**:
   ```bash
   mp query funnel <id> --from <date> --to <date> --format csv > funnel_results.csv
   ```

4. **Create custom report**:
   ```bash
   /mp-report funnel
   # Generate comprehensive funnel report
   ```

---

## Troubleshooting

**"Funnel not found"**:
- Check funnel ID with `mp inspect funnels`
- Verify access permissions in Mixpanel

**"No events found"**:
- Verify event names exactly match (case-sensitive)
- Check date range includes relevant data
- Run `mp inspect events` to see available events

**"Low sample size"**:
- Expand date range
- Check if events are being tracked correctly
- Verify filtering isn't too restrictive

**"Segmentation returns null"**:
- Property might not exist on all events
- Check property name with `mp inspect properties <event>`
- Use `defined(properties["prop"])` in filters
