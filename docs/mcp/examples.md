# Example Workflows

Real-world conversation examples demonstrating the MCP server's capabilities.

## Schema Discovery

Understand what data exists in your Mixpanel project before querying.

### Explore Events and Properties

**You:** What events are tracked in my Mixpanel project?

**Claude:** *Uses `list_events` tool*

Your project tracks 47 events. Here are the most common:

| Event | Description |
|-------|-------------|
| Login | User login |
| Signup | New user registration |
| Purchase | Completed purchase |
| Page View | Page visited |
| Feature Used | Feature interaction |

**You:** What properties are on the Purchase event?

**Claude:** *Uses `list_properties` tool with `event="Purchase"`*

The Purchase event has 12 properties:

| Property | Type | Description |
|----------|------|-------------|
| revenue | number | Purchase amount |
| currency | string | Currency code |
| product_id | string | Product identifier |
| category | string | Product category |
| payment_method | string | Payment type used |
| ... | ... | ... |

**You:** What payment methods do people use?

**Claude:** *Uses `list_property_values` tool*

Top payment methods:
- credit_card (67%)
- paypal (22%)
- apple_pay (8%)
- google_pay (3%)

---

## Live Analytics

Query Mixpanel directly for real-time insights.

### Time Series Analysis

**You:** How many signups happened each day last week?

**Claude:** *Uses `segmentation` tool*

```
Jan 15: 1,234 signups
Jan 16: 1,189 signups
Jan 17: 1,456 signups
Jan 18: 1,102 signups
Jan 19:   892 signups (weekend)
Jan 20:   847 signups (weekend)
Jan 21: 1,298 signups
```

Week-over-week: +3.2% vs previous week

### Funnel Analysis

**You:** What's the conversion rate for my signup funnel?

**Claude:** *Uses `list_funnels` then `funnel` tools*

**Signup Funnel** (last 30 days):

| Step | Users | Conversion |
|------|-------|------------|
| 1. Landing Page | 45,234 | 100% |
| 2. Start Signup | 12,456 | 27.5% |
| 3. Complete Form | 8,234 | 66.1% |
| 4. Verify Email | 6,789 | 82.4% |
| 5. First Login | 5,123 | 75.5% |

**Overall conversion:** 11.3%

The biggest drop-off is between Landing Page and Start Signup (72.5% lost).

### Retention Analysis

**You:** Show day-7 retention for users who signed up last month

**Claude:** *Uses `retention` tool*

**Signup → Return Retention** (January 2025 cohorts):

| Cohort | Day 0 | Day 1 | Day 7 | Day 14 | Day 30 |
|--------|-------|-------|-------|--------|--------|
| Jan 1-7 | 100% | 42% | 28% | 21% | 15% |
| Jan 8-14 | 100% | 45% | 31% | 24% | 18% |
| Jan 15-21 | 100% | 43% | 29% | 22% | — |
| Jan 22-28 | 100% | 44% | — | — | — |

Day-7 retention is averaging 29%, which is healthy for this product category.

---

## Intelligent Analysis (v2)

AI-powered tools for deeper insights.

### Diagnose Metric Drops

**You:** Why did signups drop on January 7th?

**Claude:** *Uses `diagnose_metric_drop` tool*

**Analysis of Signup Drop on January 7th:**

Signups dropped 47% (1,234 → 654) compared to the previous day.

**Root Causes Identified:**

1. **Geographic:** US signups dropped 62% while other regions were stable
   - Timing coincides with a major US holiday

2. **Traffic Source:** Paid acquisition channels showed 78% decline
   - Suggests ad spend was paused or campaigns ended

3. **Device:** Mobile web signups dropped 71%
   - Possible technical issue on mobile landing page

**Recommendation:** Check if paid campaigns were intentionally paused for the holiday. If not, investigate mobile landing page for issues.

### Natural Language Queries

**You:** What features do our best users engage with?

**Claude:** *Uses `ask_mixpanel` tool*

**Power User Feature Engagement** (top 10% by event count):

Power users (>100 events/month) heavily engage with:

| Feature | Usage Rate | vs Average Users |
|---------|------------|------------------|
| Dashboard | 94% | +45% |
| Export | 78% | +62% |
| Collaboration | 71% | +89% |
| Advanced Filters | 67% | +134% |
| API Access | 45% | +312% |

**Key Insight:** Power users are 3x more likely to use the API. Consider promoting API access in onboarding for users who show power-user potential.

### Funnel Optimization Report

**You:** Generate a funnel optimization report for my signup funnel

**Claude:** *Uses `funnel_optimization_report` tool*

**Signup Funnel Optimization Report**

**Executive Summary:** The signup funnel converts 11.3% of landing page visitors. There are two major optimization opportunities worth ~$2.4M annually.

**Drop-off Analysis:**

| Step | Drop-off | Impact | Priority |
|------|----------|--------|----------|
| Landing → Start | 72.5% | High | 1 |
| Form → Verify | 17.6% | Medium | 3 |
| Verify → Login | 24.5% | Medium | 2 |

**Recommendations:**

1. **Landing Page CTA (Priority 1)**
   - Current conversion: 27.5%
   - Benchmark: 35-40%
   - Action: A/B test more prominent signup CTA

2. **Email Verification (Priority 2)**
   - 24.5% never verify email
   - Action: Implement delayed verification, allow limited access before verify

3. **Form Optimization (Priority 3)**
   - Consider progressive profiling
   - Remove non-essential fields

---

## Interactive Workflows (v2)

Guided analysis with user confirmation.

### Guided Analysis

**You:** Help me analyze my data

**Claude:** *Uses `guided_analysis` tool*

I'll help you analyze your Mixpanel data. To get started:

**What's your analysis goal?**

1. Understand user behavior patterns
2. Investigate a metric change
3. Compare user segments
4. Explore product usage
5. Something else (describe)

**You:** I want to understand why conversions dropped last week

**Claude:** Let me investigate the conversion drop.

**Step 1: Confirm scope**
- Metric: Signup-to-Purchase conversion
- Period: Last 7 days vs previous 7 days
- Proceed with this analysis? (Yes/No)

**You:** Yes

**Claude:** *Executes analysis queries*

**Findings:**

Conversion dropped from 4.2% to 3.1% (26% decline).

**Contributing factors:**

1. **Traffic quality changed**
   - Organic: Conversion stable at 5.1%
   - Paid: Dropped from 3.8% to 2.1%

2. **New user segment**
   - Influx of users from a new ad campaign
   - This cohort has 40% lower conversion baseline

**Recommendation:** The conversion drop is due to a new paid acquisition channel bringing lower-intent users. This is expected for new channels. Consider:
- Adjusting targeting for the new channel
- Creating a specific onboarding flow for these users

---

## Local Analysis

Work with data stored in DuckDB.

### Fetch and Query

**You:** Fetch events from January 1-7 and show me the top 10 users by event count

**Claude:** *Uses `fetch_events` tool*

Fetched 156,234 events to table `jan_events`.

*Uses `sql` tool*

**Top 10 Users by Event Count:**

| User | Events | First Seen | Last Seen |
|------|--------|------------|-----------|
| user_8234 | 2,456 | Jan 1 | Jan 7 |
| user_1892 | 1,923 | Jan 1 | Jan 7 |
| user_4521 | 1,845 | Jan 2 | Jan 7 |
| user_7234 | 1,712 | Jan 1 | Jan 6 |
| ... | ... | ... | ... |

These users are significantly more active than average (avg: 23 events/week).

### Complex SQL Analysis

**You:** Find users who purchased but never logged in again

**Claude:** *Uses `sql` tool*

```sql
SELECT
    p.distinct_id,
    p.properties->>'$.email' as email,
    MAX(e.event_time) as last_purchase,
    COUNT(*) as purchase_count
FROM jan_events e
JOIN users p ON e.distinct_id = p.distinct_id
WHERE e.event_name = 'Purchase'
AND NOT EXISTS (
    SELECT 1 FROM jan_events e2
    WHERE e2.distinct_id = e.distinct_id
    AND e2.event_name = 'Login'
    AND e2.event_time > e.event_time
)
GROUP BY 1, 2
ORDER BY last_purchase DESC
```

Found 234 users who purchased but never returned. These are candidates for a win-back campaign.

---

## Product Health Dashboard

**You:** Show me a product health dashboard for the last month

**Claude:** *Uses `product_health_dashboard` tool*

**Product Health Dashboard** (January 2025)

### Acquisition
- New signups: 12,456 (+8% MoM)
- Top channels: Organic (45%), Paid (32%), Referral (23%)

### Activation
- First value event rate: 67%
- Median time to activation: 4.2 hours
- Activation by channel varies: Organic 78%, Paid 52%

### Retention
- Day 1: 45%
- Day 7: 29%
- Day 30: 18%
- Trending up 2% from last month

### Revenue
- Total revenue: $234,567
- ARPU: $18.82
- Transactions: 12,456

### Referral
- Referral rate: 12%
- Viral coefficient: 0.31
- Top referrers driving 45% of referral signups

**Health Score:** 7.2/10 (Healthy)

Primary growth lever: Improve paid channel activation (currently 52% vs 78% for organic).
