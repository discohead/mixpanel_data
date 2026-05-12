# Research: Workspace Facade

**Feature**: 009-workspace
**Date**: 2025-12-23

## Overview

This document captures research findings and design decisions for the Workspace facade implementation. Since this is a facade over existing, well-tested services, the research focuses on integration patterns rather than technology selection.

---

## 1. Credential Resolution Pattern

### Decision
Use the existing `ConfigManager.resolve_credentials()` method which already implements the priority order:
1. Environment variables (MP_USERNAME, MP_SECRET, MP_PROJECT_ID, MP_REGION)
2. Named account from config file
3. Default account from config file

### Rationale
- ConfigManager is already fully implemented and tested
- Priority order is established in design documents
- No need to duplicate logic in Workspace

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Re-implement credential logic | Violates DRY; ConfigManager is battle-tested |
| Pass Credentials directly | Less convenient for users; removes named account support |

---

## 2. Service Orchestration Pattern

### Decision
Use dependency injection with lazy service initialization:
- Services are created on first use, not at Workspace construction
- All services share the same MixpanelAPIClient instance
- StorageEngine is created at construction (required for all operations)

### Rationale
- Matches existing service patterns (all accept dependencies in constructor)
- Lazy initialization avoids unnecessary API client creation for opened workspaces
- Shared API client ensures consistent authentication

### Implementation Pattern

```python
class Workspace:
    def __init__(self, ...):
        self._api_client: MixpanelAPIClient | None = None
        self._discovery: DiscoveryService | None = None
        self._fetcher: FetcherService | None = None
        self._live_query: LiveQueryService | None = None
        self._storage: StorageEngine = ...  # Always created

    @property
    def _discovery_service(self) -> DiscoveryService:
        if self._discovery is None:
            self._discovery = DiscoveryService(self._get_api_client())
        return self._discovery
```

---

## 3. Context Manager Pattern

### Decision
Implement `__enter__`/`__exit__` by delegating to StorageEngine's context manager:
- `__enter__` returns self
- `__exit__` calls `close()` which closes storage and API client

### Rationale
- StorageEngine already implements proper cleanup
- API client uses httpx which is context-managed
- Consistent with Python resource management patterns

### For `ephemeral()` Classmethod

```python
@classmethod
@contextmanager
def ephemeral(cls, account=None, project_id=None, region=None, **kwargs):
    """Context manager for temporary workspaces."""
    ws = cls(
        account=account,
        project_id=project_id,
        region=region,
        _storage=StorageEngine.ephemeral(),
        **kwargs
    )
    try:
        yield ws
    finally:
        ws.close()
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Return StorageEngine.ephemeral() directly | Loses Workspace facade benefits |
| Separate EphemeralWorkspace class | Unnecessary complexity; same API |

---

## 4. Opened Workspaces (Query-Only Mode)

### Decision
`Workspace.open()` creates a workspace with:
- StorageEngine pointing to existing file
- No API client (None)
- API-dependent methods raise `ConfigError` with helpful message

### Rationale
- Users need to query existing databases without credentials
- Clear error messages guide users to the right solution
- Maintains single Workspace class for all use cases

### Error Handling Pattern

```python
def _require_api_client(self) -> MixpanelAPIClient:
    """Get API client or raise if unavailable."""
    if self._credentials is None:
        raise ConfigError(
            "API access requires credentials",
            code="NO_CREDENTIALS",
            details={"hint": "Use Workspace() with credentials instead of Workspace.open()"}
        )
    return self._get_api_client()
```

---

## 5. Progress Bar Implementation

### Decision
Wrap Rich progress bar in a callback adapter that matches FetcherService's signature:

```python
def fetch_events(self, ..., progress: bool = True) -> FetchResult:
    callback = None
    if progress:
        pbar = Progress(...)
        task = pbar.add_task("Fetching events...", total=None)
        callback = lambda count: pbar.update(task, advance=count)
        pbar.start()
    try:
        result = self._fetcher_service.fetch_events(..., progress_callback=callback)
    finally:
        if progress:
            pbar.stop()
    return result
```

### Rationale
- Constitution requires Rich for progress bars
- FetcherService already accepts callback
- Indeterminate progress (total=None) since event count unknown upfront

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Pass Rich progress directly to service | Couples service to Rich; reduces testability |
| No progress indicator | Poor UX for large fetches |

---

## 6. Method Delegation Pattern

### Decision
Simple delegation with minimal transformation:

```python
def events(self) -> list[str]:
    """List all event names in the Mixpanel project."""
    return self._discovery_service.list_events()

def sql(self, query: str) -> pd.DataFrame:
    """Execute SQL query and return results as DataFrame."""
    return self._storage.execute_df(query)
```

### Rationale
- Services already have correct signatures
- Workspace adds no new logic, just orchestration
- Type hints flow through from service methods

---

## 7. Public API Exports

### Decision
Add to `__init__.py`:
- `Workspace` class
- `WorkspaceInfo` type (already defined in types.py)
- Schema types: `TableMetadata`, `TableInfo`, `ColumnInfo`, `TableSchema`

### Rationale
- Workspace is the primary entry point
- WorkspaceInfo is returned by `info()`
- Schema types are returned by introspection methods

---

## 8. Testing Strategy

### Decision
Three-tier testing approach:

1. **Unit tests** (mocked services):
   - Test credential resolution
   - Test service wiring
   - Test error handling
   - Mock API client, storage, services

2. **Integration tests** (real DuckDB, mocked API):
   - Test full workflows
   - Use temp databases
   - Mock HTTP with httpx.MockTransport

3. **End-to-end tests** (if applicable):
   - Optional with real Mixpanel credentials
   - Marked as slow/skip by default

### Rationale
- Matches existing test patterns in codebase
- Unit tests fast and isolated
- Integration tests verify real behavior

---

## Summary

All research confirms that the Workspace facade can be implemented by composing existing, well-tested components:

| Component | Status | Integration Approach |
|-----------|--------|----------------------|
| ConfigManager | Exists | Direct delegation |
| MixpanelAPIClient | Exists | Shared instance |
| StorageEngine | Exists | Direct delegation |
| DiscoveryService | Exists | Lazy initialization |
| FetcherService | Exists | Lazy initialization |
| LiveQueryService | Exists | Lazy initialization |
| All result types | Exist | Return as-is |
| All exceptions | Exist | Raise as-is |

No new external dependencies required. No technology decisions needed.
