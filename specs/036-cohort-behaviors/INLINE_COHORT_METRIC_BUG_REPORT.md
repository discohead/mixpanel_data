# Bug Report: Inline CohortMetric 500 Error

**Status**: Root-caused and fix identified  
**Severity**: Medium — affects inline `CohortDefinition` in `CohortMetric` show clause only  
**Affects**: `CohortMetric(inline_def, name="...")` in `ws.query()`  
**Does NOT affect**: Saved cohort IDs (`CohortMetric(123, "PU")`), inline definitions in filters/breakdowns

## Summary

When a `CohortMetric` uses an inline `CohortDefinition` instead of a saved cohort ID, the Mixpanel insights query API returns a 500 "An unknown error occurred". The root cause is that our `raw_cohort` dict is missing fields that the server-side cohort processing pipeline expects.

## Root Cause

### Server-side flow for cohort-over-time queries

1. **`CohortsSizeParams.raw_cohort()`** (`insights/cohorts.py:164-183`) extracts the `raw_cohort` from `cohort_info` and adds `project_id`
2. **`get_cohort_size_timeseries()`** (`cohorts/over_time.py:201`) passes it to `_make_params()`
3. **`_make_params()`** (`cohorts/over_time.py:86-87`) wraps it: `cohort = {"raw_cohort": cohort}`
4. This goes through `get_behaviors_filter_and_group_by_selector_from_cohorts()` → tree traversal → `cohort_from_type_negated_item()` → `cohort_from_raw()`
5. **`cohort_from_raw()`** (`legacy/cohort.py:377-430`) processes the raw_cohort dict

### The mismatch

When a **saved cohort ID** is used, `get_raw_cohort_by_id()` (`backend/app_helpers/projects.py:1442`) loads the cohort from the `engage_cohort` database table and merges the `definition` JSON into the result dict, producing:

```python
{
    "id": 123,
    "project_id": 8,
    "data_group_id": None,
    "name": "Power Users",
    "count": 5000,
    "selector": {...},
    "behaviors": {...},
}
```

When an **inline `CohortDefinition`** is used, our code produces:

```python
{
    "selector": {...},
    "behaviors": {...},
}
```

The `CohortsSizeParams.raw_cohort()` method adds `project_id`, but `name` is still missing. Downstream processing in `_create_cohort()` and the Selector chain methods expect `name` to be present for label generation and result formatting.

### Evidence

Sending `raw_cohort` with `name` and `project_id` added returns **HTTP 200** successfully:

```python
raw_cohort = {
    "selector": {...},
    "behaviors": {...},
    "name": "Inline Test",
    "project_id": 8,
}
```

Without `name`, it returns **HTTP 500**.

## Fix (in mixpanel_data)

In `workspace.py` `_build_query_params()`, when building the CohortMetric show clause for inline definitions, include `name` and `project_id` inside the `raw_cohort` dict:

```python
# Current (broken):
cohort_behavior["raw_cohort"] = sanitized_raw

# Fixed:
raw = sanitized_raw
raw["name"] = item.name or ""
cohort_behavior["raw_cohort"] = raw
```

The `project_id` is already added by `CohortsSizeParams.raw_cohort()` server-side, so only `name` needs to be added client-side.

## Server-side recommendation

The `CohortsSizeParams.raw_cohort()` method at `insights/cohorts.py:168-170` should defensively add `name` from `self.cohort_info` if not present in the raw_cohort:

```python
if "raw_cohort" in self.cohort_info:
    raw_cohort = copy.copy(self.cohort_info["raw_cohort"])
    raw_cohort["project_id"] = self.project_id
    # Defensive: ensure name is present for downstream label generation
    if "name" not in raw_cohort:
        raw_cohort["name"] = self.cohort_info.get("name", self.name or "")
```

Additionally, the cohort-over-time path (`cohorts/over_time.py`, `cohorts/util_impl.py`) has **zero test coverage** for inline `raw_cohort` definitions. Adding test cases would prevent regressions.

## Files Referenced

| File | Lines | Purpose |
|------|-------|---------|
| `insights/cohorts.py` | 164-183 | `CohortsSizeParams.raw_cohort()` — extracts raw_cohort |
| `cohorts/over_time.py` | 64-167 | `_make_params()` — wraps cohort, builds query |
| `cohorts/util_impl.py` | 65-102 | `_filter_by_cohort_tree_leaf_callback()` — routes to factory |
| `cohorts/legacy/cohort.py` | 377-430 | `cohort_from_raw()` — creates Cohort from raw dict |
| `cohorts/legacy/cohort.py` | 273-366 | `_create_cohort()` — expands selector, generates ARB |
| `backend/app_helpers/projects.py` | 1442-1472 | `get_raw_cohort_by_id()` — DB fetch (has all fields) |
| `bookmark_parser/insights/validate.py` | 306-357 | `cohorts_validator` — voluptuous schemas |

## Verification

### Two bugs found and fixed (client-side):
1. **`groups` key in inline cohort entries** — Schema 2 rejects it → fixed by omitting for inline
2. **`event_selector.selector: null`** — `postorder_traverse` crashes → fixed by stripping null selectors

### One bug remaining (needs name in raw_cohort):
- **`CohortMetric` inline definition missing `name`** — server expects it for label generation → fix by adding `name` to raw_cohort dict
