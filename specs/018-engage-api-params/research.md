# Research: Engage API Full Parameter Support

**Feature**: 018-engage-api-params
**Date**: 2026-01-04

## Research Questions

This document resolves technical unknowns identified during planning.

---

## 1. Mixpanel Engage API Parameter Specification

### Question
What are the exact parameter names, types, and constraints for the 6 new parameters?

### Findings

From the Mixpanel HTTP API specification and existing implementation patterns:

| Parameter | API Name | Type | Serialization | Constraint |
|-----------|----------|------|---------------|------------|
| `distinct_id` | `distinct_id` | string | Direct value | Mutually exclusive with `distinct_ids` |
| `distinct_ids` | `distinct_ids` | list[str] | JSON array string | Max 2000 IDs; mutually exclusive with `distinct_id` |
| `data_group_id` | `data_group_id` | string | Direct value | Must be valid group type |
| `behaviors` | `behaviors` | string | Direct value (selector expression) | Mutually exclusive with `filter_by_cohort` |
| `as_of_timestamp` | `as_of_timestamp` | int | Unix epoch integer | Required for pagination with behaviors |
| `include_all_users` | `include_all_users` | bool | Boolean string | Only valid with `filter_by_cohort` |

### Decision
Use exact API parameter names at the API client layer. Map to user-friendly names at higher layers:
- API: `data_group_id` → Service/Workspace/CLI: `group_id`
- All others: same name across all layers

### Rationale
Reduces cognitive load for users while maintaining API fidelity at the transport layer.

---

## 2. Parameter Validation Strategy

### Question
Where should parameter validation (mutual exclusivity, dependencies) be implemented?

### Findings

Existing pattern in the codebase:
- API client layer performs validation before making HTTP requests
- Service layer validates business logic (e.g., table existence)
- Workspace layer validates user-facing concerns (e.g., batch_size range)
- CLI layer validates input types via Typer

### Decision
Implement mutual exclusivity validation at the **API client layer** with clear error messages:
1. `distinct_id` XOR `distinct_ids` → `ValueError("Cannot specify both distinct_id and distinct_ids")`
2. `behaviors` XOR `cohort_id` → `ValueError("Cannot specify both behaviors and cohort_id")`
3. `include_all_users` requires `cohort_id` → `ValueError("include_all_users requires cohort_id")`

### Rationale
Early validation at the API client layer:
- Prevents invalid requests from being sent
- Provides immediate feedback to users
- Matches existing pattern for parameter validation (see `output_properties` JSON serialization)

---

## 3. JSON Serialization Pattern

### Question
How should `distinct_ids` list be serialized for the API?

### Findings

Existing pattern for `output_properties`:
```python
if output_properties:
    params["output_properties"] = json.dumps(output_properties)
```

The Mixpanel API expects JSON-encoded arrays for list parameters.

### Decision
Use `json.dumps()` for `distinct_ids`:
```python
if distinct_ids:
    params["distinct_ids"] = json.dumps(distinct_ids)
```

### Rationale
Consistent with existing list serialization pattern in the codebase.

---

## 4. Pagination with Behaviors

### Question
How does `as_of_timestamp` interact with pagination when using `behaviors`?

### Findings

From API specification:
- `as_of_timestamp` provides a point-in-time snapshot for consistent pagination
- Required when paginating >1000 profiles with behavior filtering
- Prevents profile changes from affecting page consistency

### Decision
When `behaviors` is specified and results span multiple pages:
1. If `as_of_timestamp` not provided, use current timestamp automatically
2. Include the timestamp in all subsequent page requests
3. Document this behavior in method docstrings

### Rationale
Automatic timestamp generation ensures consistent pagination without requiring users to manage it manually, following the principle of sensible defaults.

---

## 5. Group Profile vs User Profile Distinction

### Question
How should metadata track whether fetched profiles are user or group profiles?

### Findings

Current `TableMetadata` structure:
```python
@dataclass
class TableMetadata:
    type: Literal["events", "profiles"]
    fetched_at: datetime
    from_date: datetime | None
    to_date: datetime | None
    ...
```

### Decision
Extend the `type` field or add a new field:
- Option A: New `profile_type: Literal["user", "group"] | None` field
- Option B: Extend type to `"profiles" | "group_profiles"`

**Selected**: Option A - Add `filter_group_id: str | None` to TableMetadata (matches existing `filter_cohort_id` pattern).

### Rationale
Minimal change that follows the existing filter tracking pattern (`filter_where`, `filter_cohort_id`, etc.)

---

## 6. CLI Flag Naming Conventions

### Question
What naming pattern should CLI flags follow?

### Findings

Existing CLI flags in `mp fetch profiles`:
- `--where` (short filter expression)
- `--cohort-id` (kebab-case)
- `--output-properties` (kebab-case, plural)

### Decision
New flags follow kebab-case convention:
| Parameter | CLI Flag |
|-----------|----------|
| `distinct_id` | `--distinct-id` |
| `distinct_ids` | `--distinct-ids` (multiple values) |
| `group_id` | `--group-id` |
| `behaviors` | `--behaviors` |
| `as_of_timestamp` | `--as-of-timestamp` |
| `include_all_users` | `--include-all-users / --no-include-all-users` |

### Rationale
Consistent with existing CLI conventions and Typer best practices.

---

## Summary

All research questions resolved. Key decisions:

1. **Parameter naming**: API names at transport layer, user-friendly names at higher layers
2. **Validation**: Mutual exclusivity checks at API client layer with clear error messages
3. **Serialization**: `json.dumps()` for `distinct_ids` list
4. **Pagination**: Auto-generate `as_of_timestamp` when using `behaviors`
5. **Metadata**: Add `filter_group_id` field following existing pattern
6. **CLI**: Kebab-case flags matching existing conventions
