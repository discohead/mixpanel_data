# Quickstart: Foundation Layer

**Feature**: 001-foundation-layer
**Purpose**: Verify foundation layer implementation works correctly

## Prerequisites

- Python 3.10+
- Package installed in development mode

```bash
# From repository root
pip install -e ".[dev]"
```

## Verification Steps

### 1. ConfigManager - Add and Retrieve Credentials

```python
from mixpanel_data._internal.config import ConfigManager
from pathlib import Path
import tempfile

# Use temp directory for testing
with tempfile.TemporaryDirectory() as tmpdir:
    config_path = Path(tmpdir) / "config.toml"
    config = ConfigManager(config_path=config_path)

    # Add an account
    config.add_account(
        name="production",
        username="sa_test_user",
        secret="test_secret_123",
        project_id="12345",
        region="us",
    )

    # List accounts
    accounts = config.list_accounts()
    assert len(accounts) == 1
    assert accounts[0].name == "production"
    print(f"Found {len(accounts)} account(s)")

    # Retrieve credentials
    creds = config.resolve_credentials()
    assert creds.username == "sa_test_user"
    assert creds.project_id == "12345"
    print(f"Resolved credentials for project {creds.project_id}")

    # Verify secret is redacted in output
    creds_str = str(creds)
    assert "test_secret_123" not in creds_str
    print(f"Secret properly redacted: {creds_str}")

print("ConfigManager: PASSED")
```

**Expected Output**:

```
Found 1 account(s)
Resolved credentials for project 12345
Secret properly redacted: Credentials(username='sa_test_user', secret=***, ...)
ConfigManager: PASSED
```

### 2. ConfigManager - Environment Variable Priority

```python
import os
from mixpanel_data._internal.config import ConfigManager

# Set environment variables
os.environ["MP_USERNAME"] = "env_user"
os.environ["MP_SECRET"] = "env_secret"
os.environ["MP_PROJECT_ID"] = "env_project"
os.environ["MP_REGION"] = "eu"

try:
    config = ConfigManager()
    creds = config.resolve_credentials()

    assert creds.username == "env_user"
    assert creds.region == "eu"
    print(f"Env vars override config: user={creds.username}, region={creds.region}")
    print("Environment priority: PASSED")
finally:
    # Clean up
    for key in ["MP_USERNAME", "MP_SECRET", "MP_PROJECT_ID", "MP_REGION"]:
        os.environ.pop(key, None)
```

### 3. Exceptions - Catch All Library Errors

```python
from mixpanel_data import MixpanelDataError
from mixpanel_data.exceptions import (
    ConfigError,
    AccountNotFoundError,
    AuthenticationError,
    TableExistsError,
    RateLimitError,
)

# All specific exceptions inherit from base
exceptions = [
    ConfigError("test"),
    AccountNotFoundError("missing", available_accounts=["a", "b"]),
    AuthenticationError("invalid"),
    TableExistsError("events"),
    RateLimitError("slow down", retry_after=60),
]

for exc in exceptions:
    assert isinstance(exc, MixpanelDataError)
    assert exc.code is not None
    data = exc.to_dict()
    assert "code" in data
    assert "message" in data
    print(f"  {exc.__class__.__name__}: code={exc.code}")

print("Exception hierarchy: PASSED")
```

**Expected Output**:

```
  ConfigError: code=CONFIG_ERROR
  AccountNotFoundError: code=ACCOUNT_NOT_FOUND
  AuthenticationError: code=AUTH_FAILED
  TableExistsError: code=TABLE_EXISTS
  RateLimitError: code=RATE_LIMITED
Exception hierarchy: PASSED
```

### 4. Result Types - FetchResult

```python
from datetime import datetime
from mixpanel_data.types import FetchResult
import json

result = FetchResult(
    table="january_events",
    rows=10000,
    type="events",
    duration_seconds=5.23,
    date_range=("2024-01-01", "2024-01-31"),
    fetched_at=datetime.now(),
)

# Immutable
try:
    result.rows = 20000
    print("ERROR: Should have raised FrozenInstanceError")
except AttributeError:
    print("Immutability: PASSED")

# JSON serializable
data = result.to_dict()
json_str = json.dumps(data)
assert "january_events" in json_str
print(f"Serialization: PASSED ({len(json_str)} bytes)")

# Lazy DataFrame conversion
df = result.df
assert len(df) >= 0  # Empty if no data attached
print("DataFrame conversion: PASSED")

print("FetchResult: PASSED")
```

### 5. Result Types - SegmentationResult

```python
from mixpanel_data.types import SegmentationResult

result = SegmentationResult(
    event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31",
    unit="day",
    segment_property="country",
    total=5000,
)

assert result.event == "Purchase"
assert result.total == 5000
print(f"Segmentation for '{result.event}': {result.total} total")

data = result.to_dict()
assert data["event"] == "Purchase"
print("SegmentationResult: PASSED")
```

## Integration Test: Full Workflow

```python
"""
Run from repository root:
    python -m pytest tests/integration/test_foundation.py -v
"""
from mixpanel_data._internal.config import ConfigManager
from mixpanel_data.exceptions import AccountNotFoundError
from mixpanel_data.types import FetchResult
from pathlib import Path
import tempfile
import pytest

def test_full_foundation_workflow():
    """End-to-end test of foundation layer."""

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"
        config = ConfigManager(config_path=config_path)

        # 1. Initially empty
        assert config.list_accounts() == []

        # 2. Add account
        config.add_account(
            name="test",
            username="user",
            secret="secret",
            project_id="123",
            region="us",
        )

        # 3. Resolve credentials
        creds = config.resolve_credentials()
        assert creds.username == "user"

        # 4. Try to get non-existent account
        with pytest.raises(AccountNotFoundError) as exc_info:
            config.resolve_credentials(account="nonexistent")

        assert exc_info.value.code == "ACCOUNT_NOT_FOUND"
        assert "nonexistent" in str(exc_info.value)

        # 5. Create result type
        from datetime import datetime
        result = FetchResult(
            table="test_table",
            rows=100,
            type="events",
            duration_seconds=1.0,
            date_range=None,
            fetched_at=datetime.now(),
        )
        assert result.to_dict()["rows"] == 100

    print("Full workflow: PASSED")
```

## Checklist

After implementation, verify:

- [ ] `pip install -e ".[dev]"` succeeds
- [ ] ConfigManager stores credentials in TOML format
- [ ] Environment variables override config file
- [ ] Secrets never appear in repr/str output
- [ ] All exceptions are catchable as `MixpanelDataError`
- [ ] Exception `to_dict()` is JSON-serializable
- [ ] Result types are immutable (frozen dataclass)
- [ ] Result types support `to_dict()` serialization
- [ ] `pytest tests/unit/` passes
- [ ] `ruff check src/` passes
- [ ] `mypy --strict src/` passes
