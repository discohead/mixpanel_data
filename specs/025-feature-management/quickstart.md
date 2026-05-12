# Quickstart: Feature Management (Flags + Experiments)

**Branch**: `025-feature-management` | **Date**: 2026-03-31

## Library Usage

### Feature Flags

```python
from mixpanel_data import Workspace
from mixpanel_data.types import (
    CreateFeatureFlagParams,
    UpdateFeatureFlagParams,
    SetTestUsersParams,
    FeatureFlagStatus,
)

ws = Workspace()

# List all flags
flags = ws.list_feature_flags()
flags_with_archived = ws.list_feature_flags(include_archived=True)

# Create a flag
flag = ws.create_feature_flag(CreateFeatureFlagParams(
    name="Dark Mode",
    key="dark_mode",
    description="Enable dark mode for users",
))

# Get a flag by ID
flag = ws.get_feature_flag("abc-123-uuid")

# Update a flag (PUT — full replacement, all required fields must be provided)
updated = ws.update_feature_flag("abc-123-uuid", UpdateFeatureFlagParams(
    name="Dark Mode",
    key="dark_mode",
    status=FeatureFlagStatus.ENABLED,
    ruleset={"variants": [{"key": "on", "value": True, "is_control": False, "split": 100}]},
))

# Delete a flag
ws.delete_feature_flag("abc-123-uuid")

# Lifecycle operations
ws.archive_feature_flag("abc-123-uuid")
restored = ws.restore_feature_flag("abc-123-uuid")
duplicate = ws.duplicate_feature_flag("abc-123-uuid")

# Test users
ws.set_flag_test_users("abc-123-uuid", SetTestUsersParams(
    users={"on": "user-distinct-id-1", "off": "user-distinct-id-2"},
))

# History and limits
history = ws.get_flag_history("abc-123-uuid", page_size=50)
limits = ws.get_flag_limits()
```

### Experiments

```python
from mixpanel_data.types import (
    CreateExperimentParams,
    UpdateExperimentParams,
    ExperimentDecideParams,
    ExperimentConcludeParams,
)

# Create an experiment
experiment = ws.create_experiment(CreateExperimentParams(
    name="Checkout Flow Test",
    hypothesis="Simplified checkout increases conversion by 10%",
))

# Full lifecycle
launched = ws.launch_experiment(experiment.id)
concluded = ws.conclude_experiment(experiment.id)
decided = ws.decide_experiment(experiment.id, ExperimentDecideParams(
    success=True,
    variant="simplified",
    message="15% conversion lift confirmed",
))

# List, get, update, delete
experiments = ws.list_experiments()
exp = ws.get_experiment("xyz-456-uuid")
updated = ws.update_experiment("xyz-456-uuid", UpdateExperimentParams(
    description="Updated description",
))
ws.delete_experiment("xyz-456-uuid")

# Archive, restore, duplicate
ws.archive_experiment("xyz-456-uuid")
restored = ws.restore_experiment("xyz-456-uuid")
duplicate = ws.duplicate_experiment("xyz-456-uuid")
```

## CLI Usage

### Feature Flags

```bash
# List flags
mp flags list
mp flags list --include-archived --format table

# CRUD
mp flags create --name "Dark Mode" --key "dark_mode" --description "Enable dark mode"
mp flags get abc-123-uuid
mp flags update abc-123-uuid --name "Dark Mode" --key "dark_mode" --status enabled --ruleset '{"variants": []}'
mp flags delete abc-123-uuid

# Lifecycle
mp flags archive abc-123-uuid
mp flags restore abc-123-uuid
mp flags duplicate abc-123-uuid

# Test users and history
mp flags set-test-users abc-123-uuid --users '{"on": "user-1"}'
mp flags history abc-123-uuid --page-size 50
mp flags limits
```

### Experiments

```bash
# List experiments
mp experiments list
mp experiments list --include-archived --format table

# CRUD
mp experiments create --name "Checkout Flow Test" --hypothesis "Simplified checkout improves conversion"
mp experiments get xyz-456-uuid
mp experiments update xyz-456-uuid --description "Updated"
mp experiments delete xyz-456-uuid

# Lifecycle
mp experiments launch xyz-456-uuid
mp experiments conclude xyz-456-uuid --end-date 2026-04-01
mp experiments decide xyz-456-uuid --success --variant simplified --message "15% lift"

# Archive, restore, duplicate
mp experiments archive xyz-456-uuid
mp experiments restore xyz-456-uuid
mp experiments duplicate xyz-456-uuid --name "Checkout Flow Test v2"

# ERF experiments
mp experiments erf --format json
```

## Error Handling

```python
from mixpanel_data.exceptions import (
    ConfigError,           # Missing credentials
    AuthenticationError,   # Invalid credentials (401)
    QueryError,            # Bad request (400), not found (404)
    ServerError,           # Server errors (5xx)
)

try:
    flag = ws.get_feature_flag("nonexistent-id")
except QueryError as e:
    print(f"Flag not found: {e}")
```
