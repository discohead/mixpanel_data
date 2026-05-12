# Data Model: Feature Management (Flags + Experiments)

**Branch**: `025-feature-management` | **Date**: 2026-03-31

## Enums

### FeatureFlagStatus

Represents the lifecycle state of a feature flag.

| Value | Description |
|-------|-------------|
| `enabled` | Flag is active and serving variants |
| `disabled` | Flag is inactive (default state) |
| `archived` | Flag is soft-deleted, excluded from default listings |

### ServingMethod

Controls how flag values are delivered to clients.

| Value | Description |
|-------|-------------|
| `client` | Client-side evaluation (default) |
| `server` | Server-side evaluation only |
| `remote_or_local` | Remote preferred, local fallback |
| `remote_only` | Remote evaluation only |

### FlagContractStatus

Account-level flag contract status.

| Value | Description |
|-------|-------------|
| `active` | Active contract |
| `grace_period` | Contract in grace period |
| `expired` | Contract expired |

### ExperimentStatus

Represents the lifecycle state of an experiment.

| Value | Description |
|-------|-------------|
| `draft` | Experiment created but not started |
| `active` | Experiment running, collecting data |
| `concluded` | Experiment stopped, awaiting decision |
| `success` | Experiment decided as successful |
| `fail` | Experiment decided as failed |

**State transitions**: `draft` → `active` (launch) → `concluded` (conclude) → `success` | `fail` (decide)

## Entity Models (Response Types)

### FeatureFlag

Represents a Mixpanel feature flag with its full configuration.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique identifier (UUID) |
| `project_id` | `int` | Yes | Project this flag belongs to |
| `name` | `str` | Yes | Human-readable name |
| `key` | `str` | Yes | Machine-readable key (unique per project) |
| `description` | `str \| None` | No | Optional description |
| `status` | `FeatureFlagStatus` | Yes | Current lifecycle status |
| `tags` | `list[str]` | No | Tags for organization (default: `[]`) |
| `experiment_id` | `str \| None` | No | Linked experiment ID if flag backs an experiment |
| `context` | `str` | Yes | Flag context identifier |
| `data_group_id` | `str \| None` | No | Data group identifier |
| `serving_method` | `ServingMethod` | Yes | How flag values are delivered |
| `ruleset` | `dict[str, Any]` | Yes | Variants, rollout rules, and test overrides |
| `hash_salt` | `str \| None` | No | Salt for deterministic variant assignment |
| `workspace_id` | `int \| None` | No | Workspace this flag belongs to |
| `content_type` | `str \| None` | No | Content type identifier |
| `created` | `str` | Yes | ISO 8601 creation timestamp |
| `modified` | `str` | Yes | ISO 8601 last-modified timestamp |
| `enabled_at` | `str \| None` | No | Timestamp when flag was last enabled |
| `deleted` | `str \| None` | No | Timestamp when flag was deleted |
| `creator_id` | `int \| None` | No | Creator's user ID |
| `creator_name` | `str \| None` | No | Creator's display name |
| `creator_email` | `str \| None` | No | Creator's email |
| `last_modified_by_id` | `int \| None` | No | Last modifier's user ID |
| `last_modified_by_name` | `str \| None` | No | Last modifier's display name |
| `last_modified_by_email` | `str \| None` | No | Last modifier's email |
| `is_favorited` | `bool \| None` | No | Whether current user has favorited |
| `pinned_date` | `str \| None` | No | Date flag was pinned |
| `can_edit` | `bool` | No | Permission: can current user edit (from Permissions flatten) |

**Notes**: Uses `extra="allow"` for forward compatibility. The `ruleset` field contains nested variant/rollout structures as untyped dicts.

### FlagHistoryResponse

Paginated change history for a feature flag.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `events` | `list[list[Any]]` | Yes | Array of event arrays |
| `count` | `int` | Yes | Total number of events |

### FlagLimitsResponse

Account-level feature flag usage and limits.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `limit` | `int` | Yes | Maximum allowed flags |
| `is_trial` | `bool` | Yes | Whether account is on trial |
| `current_usage` | `int` | Yes | Current number of flags |
| `contract_status` | `FlagContractStatus` | Yes | Contract status |

### ExperimentCreator

Creator metadata for an experiment.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `int \| None` | No | Creator's user ID |
| `first_name` | `str \| None` | No | Creator's first name |
| `last_name` | `str \| None` | No | Creator's last name |

### Experiment

Represents a Mixpanel A/B experiment.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique identifier (UUID) |
| `name` | `str` | Yes | Human-readable name |
| `description` | `str \| None` | No | Optional description |
| `hypothesis` | `str \| None` | No | Experiment hypothesis |
| `status` | `ExperimentStatus \| None` | No | Current lifecycle status |
| `variants` | `dict[str, Any] \| None` | No | Variant configuration |
| `metrics` | `dict[str, Any] \| None` | No | Success metrics |
| `settings` | `dict[str, Any] \| None` | No | Experiment settings |
| `exposures_cache` | `dict[str, Any] \| None` | No | Cached exposure data |
| `results_cache` | `dict[str, Any] \| None` | No | Cached result data |
| `start_date` | `str \| None` | No | ISO 8601 start date |
| `end_date` | `str \| None` | No | ISO 8601 end date |
| `created` | `str \| None` | No | ISO 8601 creation timestamp |
| `updated` | `str \| None` | No | ISO 8601 last-updated timestamp |
| `creator` | `ExperimentCreator \| None` | No | Creator metadata |
| `feature_flag` | `dict[str, Any] \| None` | No | Linked feature flag data |
| `is_favorited` | `bool \| None` | No | Whether current user has favorited |
| `pinned_date` | `str \| None` | No | Date experiment was pinned |
| `tags` | `list[str] \| None` | No | Tags for organization |
| `can_edit` | `bool \| None` | No | Permission: can current user edit |
| `last_modified_by_id` | `int \| None` | No | Last modifier's user ID |
| `last_modified_by_name` | `str \| None` | No | Last modifier's display name |
| `last_modified_by_email` | `str \| None` | No | Last modifier's email |

**Notes**: Uses `extra="allow"` for forward compatibility. Many fields are optional because the API may omit them depending on the request context.

## Parameter Models (Request Types)

### CreateFeatureFlagParams

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Flag name |
| `key` | `str` | Yes | Unique machine-readable key |
| `description` | `str \| None` | No | Optional description |
| `status` | `FeatureFlagStatus \| None` | No | Initial status (defaults to disabled) |
| `tags` | `list[str] \| None` | No | Tags |
| `context` | `str \| None` | No | Flag context |
| `serving_method` | `ServingMethod \| None` | No | Serving method |
| `ruleset` | `dict[str, Any] \| None` | No | Initial ruleset |

### UpdateFeatureFlagParams

**Note**: Uses PUT semantics (full replacement). Required fields must always be provided.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Flag name |
| `key` | `str` | Yes | Unique key |
| `status` | `FeatureFlagStatus` | Yes | Target status |
| `ruleset` | `dict[str, Any]` | Yes | Complete ruleset (replaces existing) |
| `description` | `str \| None` | No | Optional description |
| `tags` | `list[str] \| None` | No | Tags |
| `context` | `str \| None` | No | Flag context |
| `serving_method` | `ServingMethod \| None` | No | Serving method |

### SetTestUsersParams

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `users` | `dict[str, str]` | Yes | Mapping of variant keys to user distinct IDs |

### FlagHistoryParams

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `page` | `str \| None` | No | Pagination cursor |
| `page_size` | `int \| None` | No | Results per page |

### CreateExperimentParams

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Experiment name |
| `description` | `str \| None` | No | Optional description |
| `hypothesis` | `str \| None` | No | Experiment hypothesis |
| `settings` | `dict[str, Any] \| None` | No | Experiment settings |
| `access_type` | `str \| None` | No | Access control type |
| `can_edit` | `bool \| None` | No | Edit permission |

### UpdateExperimentParams

**Note**: Uses PATCH semantics. All fields optional — only provided fields are updated.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str \| None` | No | Updated name |
| `description` | `str \| None` | No | Updated description |
| `hypothesis` | `str \| None` | No | Updated hypothesis |
| `variants` | `dict[str, Any] \| None` | No | Updated variant config |
| `metrics` | `dict[str, Any] \| None` | No | Updated metrics |
| `settings` | `dict[str, Any] \| None` | No | Updated settings |
| `start_date` | `str \| None` | No | Updated start date |
| `end_date` | `str \| None` | No | Updated end date |
| `tags` | `list[str] \| None` | No | Updated tags |
| `exposures_cache` | `dict[str, Any] \| None` | No | Updated exposures cache |
| `results_cache` | `dict[str, Any] \| None` | No | Updated results cache |
| `status` | `ExperimentStatus \| None` | No | Updated status |
| `global_access_type` | `str \| None` | No | Updated access type |

### ExperimentConcludeParams

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `end_date` | `str \| None` | No | Override end date (ISO 8601) |

### ExperimentDecideParams

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `success` | `bool` | Yes | Whether the experiment succeeded |
| `variant` | `str \| None` | No | Winning variant key |
| `message` | `str \| None` | No | Decision summary message |

### DuplicateExperimentParams

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Name for the duplicated experiment |

## Relationships

```
FeatureFlag 1──0..1 Experiment    (flag may back an experiment via experiment_id)
FeatureFlag *──1 Project          (flags belong to a project)
FeatureFlag *──1 Workspace        (flags require workspace scoping)
Experiment  *──1 Project          (experiments belong to a project)
Experiment  0..1──0..1 FeatureFlag (experiment may link to a backing flag)
```
