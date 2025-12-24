# Phase 001: Foundation Layer — Implementation Post-Mortem

**Branch:** `001-foundation-layer`
**Status:** Complete
**Date:** 2024-12-20

---

## Executive Summary

Phase 001 established the foundational contracts that all future phases will build upon: the exception hierarchy, credential management system, and result type definitions. This layer contains zero runtime logic for fetching or querying data—it defines *how errors propagate*, *how credentials resolve*, and *what shape results take*.

**Key insight:** This phase is about establishing guarantees. Every service we build later can throw `MixpanelDataError` and callers can catch it. Every method that returns events will return a `FetchResult`. Every credential lookup follows the same resolution priority. These guarantees are now locked in.

---

## What Was Built

### 1. Exception Hierarchy (`exceptions.py`)

**Purpose:** A structured, catchable exception system that enables both fine-grained and catch-all error handling.

```
MixpanelDataError (base)
├── ConfigError
│   ├── AccountNotFoundError
│   └── AccountExistsError
├── AuthenticationError
├── RateLimitError
├── QueryError
├── TableExistsError
└── TableNotFoundError
```

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| Single base class | Enables `except MixpanelDataError` to catch all library errors |
| `code` property | Machine-readable codes like `ACCOUNT_NOT_FOUND` for programmatic handling |
| `details` dict | Structured metadata (e.g., `retry_after` seconds, available accounts) |
| `to_dict()` method | JSON serialization for logging and CLI output |
| Semantic properties | e.g., `RateLimitError.retry_after` returns the actual value, not raw dict access |

**Example usage:**
```python
try:
    workspace.fetch_events(...)
except RateLimitError as e:
    print(f"Retry in {e.retry_after} seconds")
except MixpanelDataError as e:
    log.error(e.to_dict())  # {"code": "...", "message": "...", "details": {...}}
```

**Why this matters:** Without a unified exception system, callers would need to catch multiple exception types or rely on string parsing. The `code` property allows tools (including Claude) to programmatically handle errors without parsing messages.

---

### 2. Credentials and Configuration (`_internal/config.py`, `auth.py`)

**Purpose:** Manage Mixpanel service account credentials with multi-account support and environment variable overrides.

**Components:**

| Class | Role |
|-------|------|
| `Credentials` | Immutable Pydantic model holding username, secret (redacted), project_id, region |
| `AccountInfo` | Public info about an account (no secret) for listing |
| `ConfigManager` | CRUD operations for accounts in `~/.mp/config.toml` |

**Credential Resolution Priority:**
```
1. Environment variables (MP_USERNAME, MP_SECRET, MP_PROJECT_ID, MP_REGION)
2. Named account from config file (if specified)
3. Default account from config file
```

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| `SecretStr` for secrets | Pydantic's `SecretStr` automatically redacts in `repr()`/`str()` |
| Frozen models | Credentials resolved once at Workspace construction, never mutated |
| TOML format | Human-editable, version-control-friendly, Python-native `tomllib` support |
| `auth.py` re-exports | Public API at `mixpanel_data.auth`, implementation in `_internal/` |
| First account = default | Adding first account automatically sets it as default |

**Config file structure:**
```toml
default = "production"

[accounts.production]
username = "sa_prod_user"
secret = "..."
project_id = "12345"
region = "us"

[accounts.staging]
username = "sa_stage_user"
secret = "..."
project_id = "67890"
region = "eu"
```

**Why this matters:** Multi-account support is critical for teams with staging/production environments. Environment variable priority allows CI/CD pipelines to inject credentials without touching config files.

---

### 3. Result Types (`types.py`)

**Purpose:** Define the shape of all data returned from fetch and query operations.

| Type | Use Case |
|------|----------|
| `FetchResult` | Events/profiles fetched and stored locally |
| `SegmentationResult` | Time-series segmentation query |
| `FunnelResult` / `FunnelStep` | Funnel conversion data |
| `RetentionResult` / `CohortInfo` | Cohort retention analysis |
| `JQLResult` | Custom JQL query results |

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| Frozen dataclasses | Immutability prevents accidental mutation |
| Lazy `.df` property | DataFrame only computed on first access, cached thereafter |
| `to_dict()` method | JSON serialization for CLI and logging |
| Internal `_data` fields | Raw data attached but hidden from repr |
| `object.__setattr__` for caching | Workaround for frozen dataclass + lazy caching |

**Example:**
```python
result = workspace.fetch_events("2024-01-01", "2024-01-31")

print(result.rows)           # 10000
print(result.to_dict())      # JSON-serializable dict
df = result.df               # Lazy pandas DataFrame
```

**Why frozen + lazy caching works:**
```python
@property
def df(self) -> pd.DataFrame:
    if self._df_cache is not None:
        return self._df_cache
    result_df = pd.DataFrame(self._data)
    object.__setattr__(self, "_df_cache", result_df)  # Bypass frozen
    return result_df
```

This pattern gives us immutability (the public fields can't change) while still allowing internal memoization.

---

### 4. Package Structure

```
src/mixpanel_data/
├── __init__.py          # Exports exceptions + result types
├── auth.py              # Exports ConfigManager, Credentials, AccountInfo
├── exceptions.py        # Exception hierarchy
├── types.py             # Result types
├── py.typed             # PEP 561 marker
└── _internal/
    ├── __init__.py
    └── config.py        # ConfigManager implementation
```

**Design principle:** Public API is stable, internal implementation can change.

- `from mixpanel_data import MixpanelDataError` — works
- `from mixpanel_data.auth import ConfigManager` — works
- `from mixpanel_data._internal.config import ConfigManager` — works but not guaranteed stable

---

## Test Coverage

| Area | Test Type | What's Verified |
|------|-----------|-----------------|
| Exceptions | Unit | Construction, properties, to_dict(), inheritance |
| Config | Unit | Credential creation, validation, region normalization |
| Config | Integration | Full CRUD workflow, file persistence, env var priority |
| Types | Unit | FetchResult, SegmentationResult, FunnelResult creation |
| Types | Integration | DataFrame conversion, JSON serialization |
| Imports | Integration | Public API surface is correct |

**Key test patterns:**

```python
# Exception hierarchy catch-all
try:
    might_raise_any_library_error()
except MixpanelDataError as e:
    assert e.code is not None
    json.dumps(e.to_dict())  # Must be JSON-serializable

# Frozen dataclass immutability
with pytest.raises(Exception):
    result.rows = 20000  # Should fail

# Secret redaction
assert "actual_secret" not in str(credentials)
```

---

## What's NOT in Phase 001

| Component | Phase | Notes |
|-----------|-------|-------|
| `MixpanelAPIClient` | 002 | HTTP transport, auth, rate limiting |
| `StorageEngine` | 003 | DuckDB, table management |
| `DiscoveryService` | 004 | Event/property discovery |
| `FetcherService` | 005 | Streaming event export |
| `LiveQueryService` | 006 | Segmentation, funnels, retention |
| `Workspace` | 007 | Facade tying everything together |
| CLI | 008 | Typer commands |

Phase 001 established the *contracts* these components will fulfill. For example:
- `FetcherService` will return `FetchResult`
- `MixpanelAPIClient` will raise `RateLimitError` when throttled
- `Workspace` will accept `account` parameter and resolve via `ConfigManager`

---

## Code Quality Notes

**Patterns to maintain:**

1. **Pydantic for validation, dataclasses for data transfer**
   - `Credentials` is Pydantic (needs validation + SecretStr)
   - Result types are dataclasses (simpler, just data containers)

2. **Explicit error codes over string matching**
   ```python
   # Good: programmatic handling
   if error.code == "RATE_LIMITED":
       retry_after = error.retry_after

   # Bad: fragile string parsing
   if "rate limit" in str(error).lower():
       ...
   ```

3. **Semantic properties on exceptions**
   ```python
   # AccountNotFoundError has .account_name and .available_accounts
   # RateLimitError has .retry_after
   # These are typed, documented, and discoverable
   ```

4. **JSON serialization everywhere**
   - All exceptions have `to_dict()`
   - All result types have `to_dict()`
   - CLI can output JSON for agent consumption

---

## Questions for PR Review

1. **Exception granularity:** Is `ConfigError` as a parent of `AccountNotFoundError` useful? Or should all exceptions be direct children of `MixpanelDataError`?

2. **Region validation:** Currently validated in `Credentials` and in `ConfigManager.add_account()`. Redundant or defensive?

3. **Default account behavior:** First account becomes default automatically. Should this be explicit instead?

4. **Result type DataFrame columns:** The column names in `.df` are hardcoded. Should these be constants or configurable?

---

## Next Phase: 002 (API Client)

Phase 002 implements `MixpanelAPIClient` with:
- Regional endpoint selection (US, EU, IN)
- Service account authentication (basic auth)
- Rate limit handling (raise `RateLimitError` with retry info)
- Streaming event export (iterator-based)
- Retry logic for transient failures

The client will use `Credentials` from Phase 001 and raise exceptions from the Phase 001 hierarchy.

---

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| [src/mixpanel_data/exceptions.py](../src/mixpanel_data/exceptions.py) | 299 | Exception hierarchy |
| [src/mixpanel_data/_internal/config.py](../src/mixpanel_data/_internal/config.py) | 399 | ConfigManager, Credentials |
| [src/mixpanel_data/types.py](../src/mixpanel_data/types.py) | 376 | Result types |
| [src/mixpanel_data/auth.py](../src/mixpanel_data/auth.py) | 24 | Public auth re-exports |
| [src/mixpanel_data/__init__.py](../src/mixpanel_data/__init__.py) | 51 | Package exports |
| [tests/conftest.py](../tests/conftest.py) | 46 | Shared test fixtures |
| [tests/unit/test_exceptions.py](../tests/unit/test_exceptions.py) | ~100 | Exception unit tests |
| [tests/unit/test_config.py](../tests/unit/test_config.py) | ~150 | Config unit tests |
| [tests/unit/test_types.py](../tests/unit/test_types.py) | ~150 | Types unit tests |
| [tests/integration/test_foundation.py](../tests/integration/test_foundation.py) | 210 | End-to-end workflow tests |
