---
name: mp-mcp
description: Use the Mixpanel MCP server for analytics. Triggers on mentions of Mixpanel MCP tools, MCP resources, analytics queries via MCP, segmentation, funnels, retention, cohort_comparison, product_health_dashboard, ask_mixpanel, diagnose_metric_drop, guided_analysis, fetch_events, or SQL queries on local DuckDB data.
---

# Mixpanel MCP Server

The Mixpanel MCP server exposes analytics capabilities through 40+ tools, 8 resources, and 8 prompts.

## Reference Files

When you need detailed information, read these reference files:

| File | When to Read |
|------|--------------|
| [tools.md](references/tools.md) | Complete tool signatures, parameters, return types for all 40+ tools |
| [resources.md](references/resources.md) | Resource URIs (workspace://, schema://, analysis://, users://, recipes://) |
| [prompts.md](references/prompts.md) | Guided workflow prompts (analytics_workflow, funnel_analysis, retention_analysis, etc.) |
| [patterns.md](references/patterns.md) | Usage patterns, JSON property access, error handling, best practices |

## Tool Categories

| Category | Purpose | Key Tools |
|----------|---------|-----------|
| **Discovery** | Explore schema | `list_events`, `list_properties`, `list_funnels`, `list_cohorts`, `top_events` |
| **Live Query** | Real-time API | `segmentation`, `funnel`, `retention`, `jql`, `event_counts`, `property_counts` |
| **Fetch** | Download data | `fetch_events`, `fetch_profiles`, `stream_events`, `stream_profiles` |
| **Local** | SQL analysis | `sql`, `sql_scalar`, `list_tables`, `sample`, `summarize`, `event_breakdown` |
| **Composed** | Multi-primitive | `cohort_comparison`, `product_health_dashboard`, `gqm_investigation` |
| **Intelligent** | AI-powered | `ask_mixpanel`, `diagnose_metric_drop`, `funnel_optimization_report` |
| **Interactive** | Guided workflows | `guided_analysis`, `safe_large_fetch` |

## Quick Patterns

### Explore -> Query -> Analyze

```
1. list_events() -> top_events()     # Find what to analyze
2. list_properties(event)            # Understand the data
3. segmentation() or funnel()        # Quick insights
4. fetch_events() + sql()            # Deep local analysis
```

### Diagnostic Investigation

```
1. diagnose_metric_drop(event, date)  # Automatic root cause analysis
2. cohort_comparison(a_filter, b_filter)  # Isolate segment differences
3. ask_mixpanel("Why did X happen?")  # Natural language queries
```

### Product Health

```
1. product_health_dashboard()         # AARRR snapshot
2. guided_analysis(focus_area)        # Interactive drill-down
3. funnel_optimization_report(id)     # Bottleneck analysis
```

## Resources (Read-Only)

| URI | Content |
|-----|---------|
| `workspace://info` | Project connection status, tables |
| `schema://events` | All tracked event names |
| `schema://funnels` | Saved funnel definitions |
| `schema://cohorts` | Saved cohort definitions |
| `analysis://retention/{event}/weekly` | 12-week retention curve |
| `analysis://trends/{event}/{days}` | Daily event counts |
| `users://{id}/journey` | User's 90-day activity |
| `recipes://weekly-review` | Weekly analytics checklist |

## JSON Property Access (Critical)

Events and profiles store properties as JSON. Access with DuckDB JSON syntax:

```sql
-- DuckDB SQL (local queries)
SELECT properties->>'$.country' as country FROM events
WHERE properties->>'$.plan' = 'premium'
```

## Filter Expressions

Use SQL-like syntax for filtering in API calls:

```python
# WHERE parameter
where='properties["amount"] > 100 and properties["plan"] in ["premium", "enterprise"]'

# ON parameter (segmentation)
on='properties["country"]'
```

## Error Handling

All tools return structured errors with actionable suggestions:

| Error | Cause | Solution |
|-------|-------|----------|
| `TableExistsError` | Table already exists | Use `append=True` or drop table first |
| `AuthenticationError` | Invalid credentials | Check `workspace_info()` |
| `RateLimitError` | API rate limited | Wait and retry |

## Middleware

The server includes automatic:
- **Rate limiting**: Respects Mixpanel API limits (60 req/hour for query, 3 req/sec for export)
- **Response caching**: Discovery operations cached for 5 minutes
- **Audit logging**: All requests logged with timing
