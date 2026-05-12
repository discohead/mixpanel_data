# Workspace API Contract: Feature Management

**Branch**: `025-feature-management` | **Date**: 2026-03-31

## Feature Flag Methods

All methods follow the established pattern: `client = self._require_api_client()`, call API method, validate response with Pydantic model.

### list_feature_flags

```python
def list_feature_flags(
    self,
    *,
    include_archived: bool = False,
) -> list[FeatureFlag]:
```

**Behavior**: Lists all feature flags for the project. Uses `require_scoped_path` (workspace-scoped).
**Returns**: List of `FeatureFlag` objects.
**Errors**: `ConfigError` (no credentials), `AuthenticationError` (401), `QueryError` (400/404), `ServerError` (5xx).

### create_feature_flag

```python
def create_feature_flag(
    self,
    params: CreateFeatureFlagParams,
) -> FeatureFlag:
```

**Behavior**: Creates a new feature flag. Requires `name` and `key`.
**Returns**: The newly created `FeatureFlag`.

### get_feature_flag

```python
def get_feature_flag(
    self,
    flag_id: str,
) -> FeatureFlag:
```

**Behavior**: Retrieves a single flag by UUID.
**Returns**: `FeatureFlag` with full details.

### update_feature_flag

```python
def update_feature_flag(
    self,
    flag_id: str,
    params: UpdateFeatureFlagParams,
) -> FeatureFlag:
```

**Behavior**: Replaces the full flag configuration (PUT semantics). All required fields in `UpdateFeatureFlagParams` must be provided.
**Returns**: The updated `FeatureFlag`.

### delete_feature_flag

```python
def delete_feature_flag(
    self,
    flag_id: str,
) -> None:
```

**Behavior**: Permanently deletes a feature flag.

### archive_feature_flag

```python
def archive_feature_flag(
    self,
    flag_id: str,
) -> None:
```

**Behavior**: Soft-deletes a flag (sets status to archived).

### restore_feature_flag

```python
def restore_feature_flag(
    self,
    flag_id: str,
) -> FeatureFlag:
```

**Behavior**: Restores an archived flag.
**Returns**: The restored `FeatureFlag`.

### duplicate_feature_flag

```python
def duplicate_feature_flag(
    self,
    flag_id: str,
) -> FeatureFlag:
```

**Behavior**: Creates a copy of an existing flag.
**Returns**: The newly created duplicate `FeatureFlag`.

### set_flag_test_users

```python
def set_flag_test_users(
    self,
    flag_id: str,
    params: SetTestUsersParams,
) -> None:
```

**Behavior**: Sets test user variant overrides for a flag.

### get_flag_history

```python
def get_flag_history(
    self,
    flag_id: str,
    *,
    page: str | None = None,
    page_size: int | None = None,
) -> FlagHistoryResponse:
```

**Behavior**: Retrieves paginated change history for a flag.
**Returns**: `FlagHistoryResponse` with events and count.

### get_flag_limits

```python
def get_flag_limits(self) -> FlagLimitsResponse:
```

**Behavior**: Retrieves account-level flag limits and usage.
**Returns**: `FlagLimitsResponse` with limit, current_usage, is_trial, contract_status.

## Experiment Methods

### list_experiments

```python
def list_experiments(
    self,
    *,
    include_archived: bool = False,
) -> list[Experiment]:
```

**Behavior**: Lists all experiments. Uses `maybe_scoped_path` (optionally workspace-scoped).
**Returns**: List of `Experiment` objects.

### create_experiment

```python
def create_experiment(
    self,
    params: CreateExperimentParams,
) -> Experiment:
```

**Behavior**: Creates a new experiment in Draft status.
**Returns**: The newly created `Experiment`.

### get_experiment

```python
def get_experiment(
    self,
    experiment_id: str,
) -> Experiment:
```

**Behavior**: Retrieves a single experiment by UUID.
**Returns**: `Experiment` with full details.

### update_experiment

```python
def update_experiment(
    self,
    experiment_id: str,
    params: UpdateExperimentParams,
) -> Experiment:
```

**Behavior**: Partially updates an experiment (PATCH semantics).
**Returns**: The updated `Experiment`.

### delete_experiment

```python
def delete_experiment(
    self,
    experiment_id: str,
) -> None:
```

**Behavior**: Permanently deletes an experiment.

### launch_experiment

```python
def launch_experiment(
    self,
    experiment_id: str,
) -> Experiment:
```

**Behavior**: Transitions experiment from Draft to Active.
**Returns**: The launched `Experiment` with updated status.

### conclude_experiment

```python
def conclude_experiment(
    self,
    experiment_id: str,
    *,
    params: ExperimentConcludeParams | None = None,
) -> Experiment:
```

**Behavior**: Transitions experiment from Active to Concluded. Always sends a JSON body (empty `{}` if no params).
**Returns**: The concluded `Experiment`.

### decide_experiment

```python
def decide_experiment(
    self,
    experiment_id: str,
    params: ExperimentDecideParams,
) -> Experiment:
```

**Behavior**: Records the experiment decision (success/fail, winning variant).
**Returns**: The decided `Experiment` with terminal status.

### archive_experiment

```python
def archive_experiment(
    self,
    experiment_id: str,
) -> None:
```

**Behavior**: Archives an experiment.

### restore_experiment

```python
def restore_experiment(
    self,
    experiment_id: str,
) -> Experiment:
```

**Behavior**: Restores an archived experiment.
**Returns**: The restored `Experiment`.

### duplicate_experiment

```python
def duplicate_experiment(
    self,
    experiment_id: str,
    *,
    params: DuplicateExperimentParams | None = None,
) -> Experiment:
```

**Behavior**: Duplicates an experiment, optionally with a new name.
**Returns**: The newly created duplicate `Experiment`.

### list_erf_experiments

```python
def list_erf_experiments(self) -> list[dict[str, Any]]:
```

**Behavior**: Lists experiments in ERF (Experiment Results Framework) format.
**Returns**: List of experiment dicts (untyped, varies by API version).
