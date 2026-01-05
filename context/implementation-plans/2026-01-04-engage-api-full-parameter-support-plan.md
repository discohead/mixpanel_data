# TDD Implementation Plan: Full Engage Query API Parameter Support

## Summary

Add support for missing Mixpanel Engage Query API parameters: `distinct_id`, `distinct_ids`, `data_group_id`, `behaviors`, `as_of_timestamp`, and `include_all_users`.

## Current State

**Supported:** `where`, `filter_by_cohort` (via `cohort_id`), `output_properties`, `session_id`, `page`

**Missing:** `distinct_id`, `distinct_ids`, `data_group_id`, `behaviors`, `as_of_timestamp`, `include_all_users`

**Out of Scope:** `workspace_id` (not needed for this project)

## Critical Files

- [api_client.py](src/mixpanel_data/_internal/api_client.py) - `export_profiles()` method (lines 755-821)
- [fetcher.py](src/mixpanel_data/_internal/services/fetcher.py) - `fetch_profiles()` method (lines 281-379)
- [workspace.py](src/mixpanel_data/workspace.py) - `fetch_profiles()`, `stream_profiles()` methods
- [fetch.py](src/mixpanel_data/cli/commands/fetch.py) - `mp fetch profiles` command (lines 303-463)
- [types.py](src/mixpanel_data/types.py) - Result and metadata types
- [test_api_client.py](tests/unit/test_api_client.py) - API client tests (lines 692-840)
- [test_fetcher_service.py](tests/unit/test_fetcher_service.py) - Fetcher tests (lines 452-682)

## Implementation Phases

### Phase 1: Single/Multiple Profile Lookup (`distinct_id`, `distinct_ids`)

**Purpose:** Fetch specific profiles by ID rather than querying all profiles.

#### 1.1 Write Failing Tests (API Client)
```python
# tests/unit/test_api_client.py - TestProfileExport class
def test_export_profiles_with_distinct_id():
    """Fetch single profile by distinct_id."""

def test_export_profiles_with_distinct_ids():
    """Fetch multiple profiles by distinct_ids list."""

def test_distinct_id_and_distinct_ids_mutually_exclusive():
    """Cannot specify both distinct_id and distinct_ids."""

def test_distinct_ids_json_serialization():
    """distinct_ids is serialized as JSON array."""
```

#### 1.2 Implement API Client
- Add `distinct_id: str | None` parameter to `export_profiles()`
- Add `distinct_ids: list[str] | None` parameter to `export_profiles()`
- Validate mutual exclusivity
- Add to request data with proper JSON serialization for `distinct_ids`

#### 1.3 Propagate Through Layers
- FetcherService: Add parameters to `fetch_profiles()`
- Workspace: Add parameters to `fetch_profiles()` and `stream_profiles()`
- CLI: Add `--distinct-id` and `--distinct-ids` options

---

### Phase 2: Group Profiles Support (`data_group_id`)

**Purpose:** Query group profiles (companies, accounts) instead of user profiles.

#### 2.1 Write Failing Tests
```python
def test_export_profiles_with_data_group_id():
    """Query group profiles using data_group_id."""

def test_data_group_id_passed_to_api():
    """data_group_id is included in API request."""
```

#### 2.2 Implement API Client
- Add `data_group_id: str | None` parameter to `export_profiles()`
- Include in request data when provided

#### 2.3 Propagate Through Layers
- FetcherService, Workspace, CLI: Add `group_id` parameter
- Update metadata to track group vs user profile fetches

---

### Phase 3: Behavior-Based Filtering (`behaviors`, `as_of_timestamp`)

**Purpose:** Filter profiles by event behavior (e.g., "users who did X in last 7 days").

**Note:** This follows the same pattern as existing `where` and `on` selectors throughout the codebase.

#### 3.1 Write Failing Tests
```python
def test_export_profiles_with_behaviors():
    """Filter profiles by event behavior selector."""

def test_behaviors_requires_as_of_timestamp_for_pagination():
    """as_of_timestamp required when paginating >1k with behaviors."""

def test_behaviors_passed_to_api():
    """behaviors parameter included in API request."""

def test_as_of_timestamp_passed_to_api():
    """as_of_timestamp parameter included in API request."""

def test_behaviors_and_filter_by_cohort_mutually_exclusive():
    """Cannot use both behaviors and cohort filtering."""
```

#### 3.2 Implement API Client
- Add `behaviors: str | None` parameter (event selector expression, like `where`)
- Add `as_of_timestamp: int | None` parameter
- Validate mutual exclusivity with `cohort_id`
- Handle pagination with `as_of_timestamp` when using behaviors

#### 3.3 Propagate Through Layers
- FetcherService, Workspace: Add `behaviors` and `as_of_timestamp` parameters
- CLI: Add `--behaviors` and `--as-of-timestamp` options

---

### Phase 4: Cohort Filtering Enhancement (`include_all_users`)

**Purpose:** Control whether to include distinct_ids without profiles when filtering by cohort.

#### 4.1 Write Failing Tests
```python
def test_include_all_users_default_true():
    """include_all_users defaults to true (API default)."""

def test_include_all_users_false_excludes_profileless():
    """include_all_users=false excludes distinct_ids without profiles."""

def test_include_all_users_only_with_cohort():
    """include_all_users only valid with filter_by_cohort."""
```

#### 4.2 Implement API Client
- Add `include_all_users: bool | None` parameter to `export_profiles()`
- Only include in request when `cohort_id` is also provided
- Validate dependency relationship

#### 4.3 Propagate Through Layers
- Add to FetcherService, Workspace, CLI
- CLI: Add `--include-all-users / --no-include-all-users` flag

---

### Phase 5: Integration Tests & Documentation

#### 5.1 Integration Tests
```python
# tests/integration/test_fetch_service.py
def test_fetch_profiles_by_distinct_ids():
    """End-to-end test: fetch specific profiles by ID list."""

def test_fetch_group_profiles():
    """End-to-end test: fetch group profiles with data_group_id."""
```

#### 5.2 CLI Integration Tests
```python
# tests/integration/cli/test_fetch_commands.py
def test_profiles_with_distinct_id():
    """CLI: mp fetch profiles --distinct-id user123"""

def test_profiles_with_data_group_id():
    """CLI: mp fetch profiles --group-id companies"""
```

#### 5.3 Property-Based Tests
```python
# tests/unit/test_api_client_pbt.py
def test_distinct_ids_serialization_invariants():
    """Any list of strings serializes to valid JSON array."""
```

---

## Validation Requirements

Each phase must pass:
1. `just check` - All linting, type checking, and tests pass
2. Coverage maintained at 90%+
3. All new code has complete docstrings
4. Mutation testing score maintained at 80%+

## Parameter Summary Table

| Parameter | API Layer | Service Layer | Workspace | CLI |
|-----------|-----------|---------------|-----------|-----|
| `distinct_id` | `distinct_id` | `distinct_id` | `distinct_id` | `--distinct-id` |
| `distinct_ids` | `distinct_ids` | `distinct_ids` | `distinct_ids` | `--distinct-ids` |
| `data_group_id` | `data_group_id` | `group_id` | `group_id` | `--group-id` |
| `behaviors` | `behaviors` | `behaviors` | `behaviors` | `--behaviors` |
| `as_of_timestamp` | `as_of_timestamp` | `as_of_timestamp` | `as_of_timestamp` | `--as-of-timestamp` |
| `include_all_users` | `include_all_users` | `include_all_users` | `include_all_users` | `--include-all-users` |

## Estimated Complexity

- **Phase 1 (distinct_id/ids):** Medium - straightforward parameter addition with mutual exclusivity validation
- **Phase 2 (data_group_id):** Low - simple parameter, add to existing method
- **Phase 3 (behaviors):** Medium - follows existing selector patterns (`where`, `on`), mutual exclusivity with cohort
- **Phase 4 (include_all_users):** Low - boolean with dependency validation (requires cohort_id)
- **Phase 5 (Integration):** Medium - comprehensive testing across all layers
