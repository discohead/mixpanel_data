# Bug Report: Custom Property Filters Crash in Funnel/Retention Global `where`

**Severity**: P2 — Server returns HTTP 500 for valid bookmark JSON  
**Component**: `bookmark_parser/common/transforms/util.py`  
**Reporter**: mixpanel_data QA (Phase 037 — Custom Properties in Queries)  
**Date**: 2026-04-07

---

## Summary

`transform_insights_filters_to_funnels()` crashes with `KeyError` when a `sections.filter[]` entry uses `customPropertyId` or `customProperty` instead of `value` for property identification. This causes HTTP 500 for any funnel or retention query that includes a custom property in the global `where` filter.

**Impact**: Users cannot filter funnel or retention queries by custom properties (saved or inline) using the global `where` parameter. Per-step filters (`behavior.filters`) and insights queries are unaffected.

---

## Root Cause

**File**: `bookmark_parser/common/transforms/util.py`  
**Function**: `transform_insights_filters_to_funnels()` — line 1452  
**Two crash points**:

### Crash 1 — Line 1459

```python
if f["value"] == "$cohorts":  # KeyError when f has no "value" key
```

Custom property filter entries use `customPropertyId` or `customProperty` instead of `value` to identify the property. This line does a hard dictionary access without checking whether `"value"` exists.

### Crash 2 — Line 1484

```python
"propertyName": f["value"],  # Same KeyError
```

Even if crash 1 were fixed, this line also performs an unchecked `f["value"]` access when building the converted filter dict.

### Irony

Lines 1477–1478 in the same function already handle custom properties correctly using safe `.get()`:

```python
"customProperty": f.get("customProperty"),      # line 1477 — safe
"customPropertyId": f.get("customPropertyId"),   # line 1478 — safe
```

The function was partially updated to pass through custom property data, but the two property name extraction lines were not updated to handle the absence of `"value"`.

---

## Why This Only Affects Funnels/Retention

| Engine | Filter Processing Path | Custom Property Support |
|--------|----------------------|------------------------|
| **Insights** | `sections.filter` → `segment_to_arb_selector()` (arb_selector.py:408) | Works — calls `is_custom_property()` and routes to `_expand_formula_property()` |
| **Funnels** | `sections.filter` → `transform_insights_filters_to_funnels()` → arb_selector | **Crashes** — hard `f["value"]` access before arb_selector ever sees the entry |
| **Retention** | Same transform path as funnels | **Crashes** — same root cause |

The transform function is an intermediate step that converts insights-format filters to the legacy funnels bookmark format. It runs **before** the arb_selector, so the custom property handling in `segment_to_arb_selector()` never gets a chance to execute.

---

## Reproduction

### Minimal Bookmark (Funnel with Custom Property Filter)

```json
{
  "sections": {
    "show": [{
      "type": "metric",
      "behavior": {
        "type": "funnel",
        "resourceType": "events",
        "behaviors": [
          {"type": "event", "name": "Signup", "filters": [], "filtersDeterminer": "all", "funnelOrder": "ordered"},
          {"type": "event", "name": "Purchase", "filters": [], "filtersDeterminer": "all", "funnelOrder": "ordered"}
        ],
        "conversionWindowDuration": 14,
        "conversionWindowUnit": "day",
        "funnelOrder": "ordered",
        "exclusions": [],
        "aggregateBy": [],
        "filter": []
      },
      "measurement": {"math": "conversion_rate_unique", "property": null, "stepIndex": null}
    }],
    "time": [{"dateRangeType": "in the last", "unit": "day", "window": {"unit": "day", "value": 30}}],
    "filter": [{
      "resourceType": "events",
      "filterType": "string",
      "defaultType": "string",
      "filterValue": null,
      "filterOperator": "is set",
      "customPropertyId": 90553,
      "dataset": "$mixpanel"
    }],
    "group": [],
    "formula": []
  },
  "displayOptions": {"chartType": "funnel-steps"}
}
```

**Expected**: Query executes and returns funnel results filtered by custom property  
**Actual**: HTTP 500 `{"error": "An unknown error occurred."}`

### The Same Filter Works in Insights

Replace the show clause with a simple event metric and remove `"formula": []` — the identical `sections.filter` entry succeeds.

### Per-Step Filters Work in Funnels

Moving the custom property filter from `sections.filter[]` to `behavior.behaviors[0].filters[]` succeeds — the per-step filter path goes directly through `segment_to_arb_selector()` without the transform.

---

## Affected Filter Formats

Both custom property filter formats are affected:

### 1. Saved Custom Property Reference (`customPropertyId`)

```json
{
  "customPropertyId": 90553,
  "resourceType": "events",
  "filterType": "string",
  "defaultType": "string",
  "filterValue": null,
  "filterOperator": "is set",
  "dataset": "$mixpanel"
}
```

No `"value"` key → `KeyError` at line 1459.

### 2. Inline Custom Property Definition (`customProperty`)

```json
{
  "customProperty": {
    "displayFormula": "A * B",
    "composedProperties": {
      "A": {"value": "price", "type": "number", "resourceType": "event"},
      "B": {"value": "quantity", "type": "number", "resourceType": "event"}
    },
    "name": "",
    "description": "",
    "propertyType": "number",
    "resourceType": "events"
  },
  "resourceType": "events",
  "filterType": "number",
  "defaultType": "number",
  "filterValue": 1000,
  "filterOperator": "is greater than",
  "dataset": "$mixpanel"
}
```

No `"value"` key → `KeyError` at line 1459.

---

## Suggested Fix

### Option A: Minimal Fix (2 lines)

```python
# Line 1459 — change hard access to safe .get()
# BEFORE:
if f["value"] == "$cohorts":
# AFTER:
if f.get("value") == "$cohorts":

# Line 1484 — change hard access to safe .get()
# BEFORE:
"propertyName": f["value"],
# AFTER:
"propertyName": f.get("value"),
```

This prevents the `KeyError` and allows the custom property data (already passed through at lines 1477–1478) to flow into the converted filter dict. The downstream arb_selector already knows how to process `customProperty`/`customPropertyId` entries.

### Option B: Explicit Custom Property Routing (more robust)

```python
for f in insights_filters:
    # Route custom property filters — they don't have "value"
    if is_custom_property(f):
        resource_key = SUPPORTED_RESOURCE_TYPES[f["resourceType"]]
        converted_filter = {
            resource_key: {
                "customProperty": f.get("customProperty"),
                "customPropertyId": f.get("customPropertyId"),
                "resourceType": resource_key,
                "filterOperator": f["filterOperator"],
                "filterValue": f.get("filterValue"),
                "filterType": f.get("filterType"),
                "propertyDefaultType": f.get("defaultType"),
                "dataset": f.get("dataset"),
            }
        }
        filter_by_event["children"].append(converted_filter)
    elif f.get("value") == "$cohorts":
        # ... existing cohort handling ...
    elif "behavior" not in f:
        # ... existing regular property handling ...
```

This requires importing `is_custom_property` from `webapp.custom_properties.util`.

---

## Test Cases for Verification

After applying the fix, verify these scenarios:

1. **Funnel + `customPropertyId` in global filter** → should return results (not 500)
2. **Funnel + `customProperty` (inline) in global filter** → should return results
3. **Retention + `customPropertyId` in global filter** → should return results
4. **Retention + `customProperty` (inline) in global filter** → should return results
5. **Funnel + cohort filter** → still works (regression check for `$cohorts` path)
6. **Funnel + regular property filter** → still works (regression check)
7. **Insights + custom property filter** → still works (unaffected path)
8. **Funnel + per-step custom property filter** → still works (unaffected path)

---

## Automated Test References

The `mixpanel_data` library has 5 xfailed live tests that serve as ready-made regression tests:

```
tests/live/test_custom_property_queries_live.py::TestCustomPropertyFunnels::test_funnel_where_inline_cp
tests/live/test_custom_property_queries_live.py::TestCustomPropertyRetention::test_retention_where_inline_cp
tests/live/test_custom_property_queries_live.py::TestCustomPropertyRetention::test_retention_where_ref
tests/live/test_custom_property_queries_live.py::TestCrossEngine::test_funnel_inline_cp_groupby_and_where
tests/live/test_custom_property_queries_live.py::TestCrossEngine::test_retention_inline_cp_groupby_and_where
```

Once the server fix is deployed, these tests can be changed from `@pytest.mark.xfail` to regular tests — they should pass.

---

## Environment

- **Server endpoint**: `POST /api/query/insights`
- **Region**: US (`https://mixpanel.com/api/query/insights`)
- **Projects tested**: 3018488 (ecommerce-demo), 8 (p8)
- **Auth method**: Basic Auth (service account)
- **Client**: `mixpanel_data` Python library v0.1.0
