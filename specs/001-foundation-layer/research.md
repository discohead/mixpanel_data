# Research: Foundation Layer

**Feature**: 001-foundation-layer
**Date**: 2025-12-19

## Research Questions

1. TOML parsing library selection
2. Pydantic v2 patterns for immutable credentials
3. Exception hierarchy design
4. Result types: dataclasses vs Pydantic
5. Secret redaction patterns

---

## 1. TOML Parsing Library

### Decision

Use `tomllib` (Python 3.11+) or `tomli` (Python 3.10) for reading, `tomli-w` for writing.

### Rationale

- Python 3.11+ includes `tomllib` in the standard library (read-only)
- Python 3.10 users use the `tomli` package (conditional dependency)
- `tomli-w` is a lightweight write-only companion (minimal footprint)
- Project supports Python 3.10+ with automatic fallback to `tomli` when needed

### Alternatives Considered

| Option | Pros | Cons |
| ------ | ---- | ---- |
| `toml` | Read/write | Unmaintained, PEP 680 superseded it |
| `tomli` + `tomli-w` | Well-maintained | Extra dependency when stdlib has reader |
| `rtoml` | Fast (Rust) | Heavy dependency for simple config |

---

## 2. Pydantic v2 Patterns for Immutable Credentials

### Decision

Use `frozen=True` Pydantic models with `model_validator` for credential validation.

### Rationale

- `frozen=True` makes instances immutable after creation (per constitution Principle V)
- Pydantic v2's `model_validator` enables cross-field validation (e.g., region must be valid)
- `SecretStr` type automatically redacts in repr/logs (per FR-007)
- Pydantic integrates with config file loading via `model_validate`

### Pattern

```python
from pydantic import BaseModel, SecretStr, field_validator

class Credentials(BaseModel, frozen=True):
    username: str
    secret: SecretStr  # Auto-redacted in repr
    project_id: str
    region: str

    @field_validator("region")
    @classmethod
    def validate_region(cls, v: str) -> str:
        valid = {"us", "eu", "in"}
        if v.lower() not in valid:
            raise ValueError(f"Region must be one of {valid}")
        return v.lower()
```

### Alternatives Considered

| Option | Pros | Cons |
| ------ | ---- | ---- |
| `@dataclass(frozen=True)` | Stdlib, simple | No SecretStr, manual validation |
| `NamedTuple` | Immutable | No validation, no SecretStr |
| `attrs` | Powerful | Extra dependency when Pydantic already required |

---

## 3. Exception Hierarchy Design

### Decision

Single base class `MixpanelDataError` with category-specific subclasses.

### Rationale

- Python convention: library-specific base exception
- Users can catch `MixpanelDataError` for all library errors
- Subclasses enable specific handling (e.g., retry on `RateLimitError`)
- Per FR-008, FR-009: base type + specific types required

### Hierarchy

```
MixpanelDataError (base)
├── ConfigError
│   ├── AccountNotFoundError
│   └── AccountExistsError
├── AuthenticationError
├── TableExistsError
├── TableNotFoundError
├── RateLimitError
└── QueryError
```

### Key Design Points

- All exceptions store structured data (not just message strings)
- `__str__` provides human-readable message
- `to_dict()` method for JSON serialization (per FR-011)
- No secrets in exception messages (validated in tests)

---

## 4. Result Types: Dataclasses vs Pydantic

### Decision

Use `frozen=True` dataclasses for result types, with Pydantic only for validation.

### Rationale

- Result types are output, not input - validation less critical
- Dataclasses are lighter weight and faster to instantiate
- `@property` methods support lazy DataFrame conversion
- Constitution doesn't mandate Pydantic for all models, only API responses

### Pattern

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Any
import pandas as pd

@dataclass(frozen=True)
class FetchResult:
    table: str
    rows: int
    type: str  # "events" or "profiles"
    duration_seconds: float
    date_range: tuple[str, str] | None
    fetched_at: datetime
    _data: list[dict[str, Any]] = field(repr=False, default_factory=list)

    @property
    def df(self) -> pd.DataFrame:
        """Lazy conversion to DataFrame."""
        return pd.DataFrame(self._data)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "table": self.table,
            "rows": self.rows,
            "type": self.type,
            "duration_seconds": self.duration_seconds,
            "date_range": self.date_range,
            "fetched_at": self.fetched_at.isoformat(),
        }
```

### Alternatives Considered

| Option | Pros | Cons |
| ------ | ---- | ---- |
| Pydantic models | Consistent, validation | Heavier, slower for output types |
| Plain dicts | Simple | No type safety, no properties |
| TypedDict | Typed | No methods, no immutability |

---

## 5. Secret Redaction Patterns

### Decision

Multi-layer defense: Pydantic `SecretStr` + custom `__repr__` + logging filter.

### Rationale

- FR-007 requires zero credential leakage
- Multiple layers provide defense in depth
- `SecretStr` handles most cases automatically
- Custom `__repr__` on Credentials catches edge cases
- Logging filter as final safety net

### Implementation Layers

1. **Pydantic SecretStr**: Auto-redacts in `repr()` and `str()`
2. **Custom `__repr__`**: Credentials shows `secret=***` even if accessed
3. **Exception messages**: Validated to never contain raw secrets
4. **Test suite**: Grep for credential patterns in all output

### Pattern

```python
class Credentials(BaseModel, frozen=True):
    username: str
    secret: SecretStr

    def __repr__(self) -> str:
        return f"Credentials(username={self.username!r}, secret=***, ...)"
```

---

## Summary

| Topic | Decision | Key Benefit |
| ----- | -------- | ----------- |
| TOML | stdlib `tomllib` + `tomli-w` | No extra read dependency |
| Credentials | Pydantic frozen + SecretStr | Immutable, auto-redacted |
| Exceptions | Single base + specific subclasses | Catch-all + specific handling |
| Result Types | Frozen dataclasses | Lightweight, lazy DataFrame |
| Secrets | Multi-layer (SecretStr + repr + tests) | Defense in depth |

All NEEDS CLARIFICATION items resolved. Ready for Phase 1: Design & Contracts.
