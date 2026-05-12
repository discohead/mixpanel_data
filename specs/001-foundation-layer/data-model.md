# Data Model: Foundation Layer

**Feature**: 001-foundation-layer
**Date**: 2025-12-19

## Overview

The Foundation layer defines three categories of data structures:

1. **Configuration Entities** - Credential storage and management
2. **Exception Types** - Error representation and handling
3. **Result Types** - Operation outcome representation

---

## 1. Configuration Entities

### Credentials

Represents authentication information for a single Mixpanel project. Immutable after creation.

| Field | Type | Constraints | Description |
| ----- | ---- | ----------- | ----------- |
| `username` | string | Required, non-empty | Service account username |
| `secret` | SecretStr | Required, redacted in output | Service account secret |
| `project_id` | string | Required, non-empty | Mixpanel project identifier |
| `region` | string | Required, enum: `us`, `eu`, `in` | Data residency region |

**Validation Rules**:

- All fields required and non-empty
- `region` must be lowercase and one of: `us`, `eu`, `in`
- Immutable: no setters or mutations allowed

**Behaviors**:

- `__repr__`: Shows `secret=***` (never raw value)
- `__str__`: Same as repr
- `__eq__`: Compares all fields except uses secret value internally

---

### AccountInfo

Represents a named project configuration for listing and management.

| Field | Type | Constraints | Description |
| ----- | ---- | ----------- | ----------- |
| `name` | string | Required, unique | Account display name (e.g., "production") |
| `username` | string | Required | Service account username |
| `project_id` | string | Required | Mixpanel project identifier |
| `region` | string | Required | Data residency region |
| `is_default` | boolean | Required | Whether this is the default account |

**Note**: `AccountInfo` does NOT contain the secret. Used for listing without exposing credentials.

---

### ConfigFile (Internal)

Represents the persisted configuration file structure.

| Field | Type | Constraints | Description |
| ----- | ---- | ----------- | ----------- |
| `default` | string | Optional | Name of default account |
| `accounts` | map[string, AccountConfig] | Required | Named account configurations |

### AccountConfig (Internal)

| Field | Type | Constraints | Description |
| ----- | ---- | ----------- | ----------- |
| `username` | string | Required | Service account username |
| `secret` | string | Required | Service account secret (encrypted at rest) |
| `project_id` | string | Required | Mixpanel project identifier |
| `region` | string | Required | Data residency region |

---

## 2. Exception Types

### Base Exception

| Type | Parent | Purpose |
| ---- | ------ | ------- |
| `MixpanelDataError` | `Exception` | Base for all library exceptions |

**Fields**:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `message` | string | Human-readable error message |
| `code` | string | Machine-readable error code |
| `details` | dict | Additional structured data |

**Methods**:

- `to_dict()` → dict: Serializable representation
- `__str__()` → string: Human-readable message

---

### Configuration Exceptions

| Type | Parent | Purpose | Code |
| ---- | ------ | ------- | ---- |
| `ConfigError` | `MixpanelDataError` | Base for config errors | `CONFIG_ERROR` |
| `AccountNotFoundError` | `ConfigError` | Named account doesn't exist | `ACCOUNT_NOT_FOUND` |
| `AccountExistsError` | `ConfigError` | Account name already taken | `ACCOUNT_EXISTS` |

**AccountNotFoundError Fields**:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `account_name` | string | The requested account name |
| `available_accounts` | list[string] | Names of available accounts |

---

### Operation Exceptions

| Type | Parent | Purpose | Code |
| ---- | ------ | ------- | ---- |
| `AuthenticationError` | `MixpanelDataError` | Invalid/missing credentials | `AUTH_FAILED` |
| `RateLimitError` | `MixpanelDataError` | API rate limit exceeded | `RATE_LIMITED` |
| `QueryError` | `MixpanelDataError` | Query execution failed | `QUERY_FAILED` |

**RateLimitError Fields**:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `retry_after` | int | None | Seconds until retry allowed |

---

### Storage Exceptions

| Type | Parent | Purpose | Code |
| ---- | ------ | ------- | ---- |
| `TableExistsError` | `MixpanelDataError` | Table already exists | `TABLE_EXISTS` |
| `TableNotFoundError` | `MixpanelDataError` | Table doesn't exist | `TABLE_NOT_FOUND` |

**TableExistsError Fields**:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `table_name` | string | Name of existing table |
| `suggestion` | string | How to resolve (e.g., "use drop() first") |

---

## 3. Result Types

### FetchResult

Represents the outcome of a data fetch operation.

| Field | Type | Constraints | Description |
| ----- | ---- | ----------- | ----------- |
| `table` | string | Required | Name of created table |
| `rows` | int | Required, >= 0 | Number of rows fetched |
| `type` | string | Required, enum: `events`, `profiles` | Data type |
| `duration_seconds` | float | Required, >= 0 | Operation duration |
| `date_range` | tuple[string, string] | None | Optional | Start/end dates (events only) |
| `fetched_at` | datetime | Required | When fetch completed |

**Behaviors**:

- `df` property: Lazy conversion to pandas DataFrame
- `to_dict()`: JSON-serializable dictionary
- Immutable: frozen dataclass

---

### SegmentationResult

Represents the outcome of a segmentation query.

| Field | Type | Constraints | Description |
| ----- | ---- | ----------- | ----------- |
| `event` | string | Required | Queried event name |
| `from_date` | string | Required | Query start date |
| `to_date` | string | Required | Query end date |
| `unit` | string | Required | Time unit (day, week, month) |
| `segment_property` | string | None | Optional | Property used for segmentation |
| `total` | int | Required, >= 0 | Total count |
| `series` | dict | Required | Time series data |

**Behaviors**:

- `df` property: Lazy conversion to pandas DataFrame
- `to_dict()`: JSON-serializable dictionary

---

### FunnelResult

Represents the outcome of a funnel query.

| Field | Type | Constraints | Description |
| ----- | ---- | ----------- | ----------- |
| `funnel_id` | int | Required | Funnel identifier |
| `funnel_name` | string | Required | Funnel display name |
| `from_date` | string | Required | Query start date |
| `to_date` | string | Required | Query end date |
| `conversion_rate` | float | Required, 0-1 | Overall conversion |
| `steps` | list[FunnelStep] | Required | Step-by-step data |

### FunnelStep

| Field | Type | Constraints | Description |
| ----- | ---- | ----------- | ----------- |
| `event` | string | Required | Step event name |
| `count` | int | Required, >= 0 | Users at this step |
| `conversion_rate` | float | Required, 0-1 | Conversion from previous |

---

### RetentionResult

Represents the outcome of a retention query.

| Field | Type | Constraints | Description |
| ----- | ---- | ----------- | ----------- |
| `born_event` | string | Required | Initial event |
| `return_event` | string | Required | Return event |
| `from_date` | string | Required | Query start date |
| `to_date` | string | Required | Query end date |
| `unit` | string | Required | Time unit |
| `cohorts` | list[CohortInfo] | Required | Cohort retention data |

### CohortInfo

| Field | Type | Constraints | Description |
| ----- | ---- | ----------- | ----------- |
| `date` | string | Required | Cohort date |
| `size` | int | Required, >= 0 | Cohort size |
| `retention` | list[float] | Required | Retention percentages by period |

---

## Entity Relationships

```text
┌─────────────────┐
│  ConfigManager  │
│    (service)    │
└────────┬────────┘
         │ manages
         ▼
┌─────────────────┐      ┌─────────────────┐
│   AccountInfo   │◄────▶│   Credentials   │
│  (listing only) │      │ (with secret)   │
└─────────────────┘      └─────────────────┘
         │                        │
         └──────────┬─────────────┘
                    │ stored in
                    ▼
           ┌─────────────────┐
           │   ConfigFile    │
           │ (~/.mp/config)  │
           └─────────────────┘
```

---

## State Transitions

### Account Lifecycle

```text
[Not Exists] ──add()──▶ [Active] ──set_default()──▶ [Default]
     ▲                      │                           │
     │                      │                           │
     └───────remove()───────┴─────────remove()──────────┘
```

### Credential Resolution

```text
resolve_credentials(account_name)
         │
         ▼
    ┌──────────────────────┐
    │ Check env variables  │
    │ MP_USERNAME, etc.    │
    └──────────┬───────────┘
               │ if all set
               ▼
         [Return Credentials]
               │ if not set
               ▼
    ┌──────────────────────┐
    │ Check named account  │
    │ in config file       │
    └──────────┬───────────┘
               │ if found
               ▼
         [Return Credentials]
               │ if not found
               ▼
    ┌──────────────────────┐
    │ Check default account│
    └──────────┬───────────┘
               │ if found
               ▼
         [Return Credentials]
               │ if not found
               ▼
         [Raise ConfigError]
```
