# Data Model: Operational Tooling — Alerts, Annotations, and Webhooks

**Branch**: `026-operational-tooling` | **Date**: 2026-03-31

## Entity Inventory

All models use `ConfigDict(frozen=True, extra="allow")` for response types and plain `BaseModel` for request params, consistent with existing patterns (Dashboard, Bookmark, Cohort, etc.).

---

## Domain 6: Alerts

### CustomAlert (response)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | yes | Alert ID |
| name | str | yes | Alert name |
| bookmark | AlertBookmark \| None | no | Linked saved report |
| condition | dict[str, Any] | yes | Trigger condition (opaque JSON) |
| frequency | int | yes | Check frequency in seconds |
| paused | bool | yes | Whether alert is paused |
| subscriptions | list[dict[str, Any]] | yes | Notification targets |
| notification_windows | dict[str, Any] \| None | no | Notification window config |
| creator | AlertCreator \| None | no | Creator user info |
| workspace | AlertWorkspace \| None | no | Workspace metadata |
| project | AlertProject \| None | no | Project metadata |
| created | str | yes | Creation timestamp |
| modified | str | yes | Last modified timestamp |
| last_checked | str \| None | no | Last check timestamp |
| last_fired | str \| None | no | Last trigger timestamp |
| valid | bool | yes | Whether alert is valid |
| results | dict[str, Any] \| None | no | Latest evaluation results |

### AlertBookmark (response, nested)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | yes | Bookmark ID |
| name | str \| None | no | Bookmark name |
| type | str \| None | no | Bookmark type |

### AlertCreator (response, nested)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | yes | User ID |
| first_name | str \| None | no | First name |
| last_name | str \| None | no | Last name |
| email | str \| None | no | Email |

### AlertWorkspace (response, nested)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | yes | Workspace ID |
| name | str \| None | no | Workspace name |

### AlertProject (response, nested)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | yes | Project ID |
| name | str \| None | no | Project name |

### CreateAlertParams (request)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| bookmark_id | int | yes | ID of linked bookmark |
| name | str | yes | Alert name |
| condition | dict[str, Any] | yes | Trigger condition JSON |
| frequency | int | yes | Check frequency in seconds |
| paused | bool | yes | Start paused or active |
| subscriptions | list[dict[str, Any]] | yes | Notification targets |
| notification_windows | dict[str, Any] \| None | no | Notification window config |

### UpdateAlertParams (request)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | str \| None | no | New name |
| bookmark_id | int \| None | no | New bookmark ID |
| condition | dict[str, Any] \| None | no | New condition |
| frequency | int \| None | no | New frequency |
| paused | bool \| None | no | New pause state |
| subscriptions | list[dict[str, Any]] \| None | no | New subscriptions |
| notification_windows | dict[str, Any] \| None | no | New notification windows |

### AlertCount (response)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| anomaly_alerts_count | int | yes | Current alert count |
| alert_limit | int | yes | Account limit |
| is_below_limit | bool | yes | Whether below limit |

### AlertHistoryResponse (response)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| results | list[dict[str, Any]] | yes | History entries |
| pagination | AlertHistoryPagination | yes | Pagination metadata |

### AlertHistoryPagination (response, nested)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| next_cursor | str \| None | no | Next page cursor |
| previous_cursor | str \| None | no | Previous page cursor |
| page_size | int | yes | Page size |

### AlertScreenshotResponse (response)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signed_url | str | yes | Signed GCS URL for screenshot |

### ValidateAlertsForBookmarkParams (request)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| alert_ids | list[int] | yes | Alert IDs to validate |
| bookmark_type | str | yes | Bookmark type to validate against |
| bookmark_params | dict[str, Any] | yes | Bookmark params JSON |

### ValidateAlertsForBookmarkResponse (response)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| alert_validations | list[AlertValidation] | yes | Per-alert validation results |
| invalid_count | int | yes | Count of invalid alerts |

### AlertValidation (response, nested)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| alert_id | int | yes | Alert ID |
| alert_name | str | yes | Alert name |
| valid | bool | yes | Whether valid |
| reason | str \| None | no | Reason if invalid |

### AlertFrequencyPreset (enum)

| Value | Seconds | Description |
|-------|---------|-------------|
| HOURLY | 3600 | Check every hour |
| DAILY | 86400 | Check every day |
| WEEKLY | 604800 | Check every week |

---

## Domain 7: Annotations

### Annotation (response)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | yes | Annotation ID |
| project_id | int | yes | Project ID |
| date | str | yes | Annotation date (ISO format) |
| description | str | yes | Annotation text |
| user | AnnotationUser \| None | no | Creator user info |
| tags | list[AnnotationTag] | yes | Associated tags |

### AnnotationUser (response, nested)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | yes | User ID |
| first_name | str | yes | First name |
| last_name | str | yes | Last name |

### AnnotationTag (response)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | yes | Tag ID |
| name | str | yes | Tag name |
| project_id | int \| None | no | Project ID |
| has_annotations | bool \| None | no | Whether tag has annotations |

### CreateAnnotationParams (request)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| date | str | yes | Date string (ISO format) |
| description | str | yes | Annotation text |
| tags | list[int] \| None | no | Tag IDs to associate |
| user_id | int \| None | no | Creator user ID |

### UpdateAnnotationParams (request)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| description | str \| None | no | New description |
| tags | list[int] \| None | no | New tag IDs |

### CreateAnnotationTagParams (request)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | str | yes | Tag name |

---

## Domain 8: Webhooks

### WebhookAuthType (enum)

| Value | Description |
|-------|-------------|
| BASIC | HTTP Basic authentication |
| UNKNOWN | Unknown/unsupported auth type |

### ProjectWebhook (response)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str | yes | Webhook ID (UUID string) |
| name | str | yes | Webhook name |
| url | str | yes | Webhook URL |
| is_enabled | bool | yes | Whether enabled |
| auth_type | str \| None | no | Authentication type |
| created | str \| None | no | Creation timestamp |
| modified | str \| None | no | Last modified timestamp |
| creator_id | int \| None | no | Creator user ID |
| creator_name | str \| None | no | Creator name |

### CreateWebhookParams (request)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | str | yes | Webhook name |
| url | str | yes | Webhook URL |
| auth_type | str \| None | no | Auth type ("basic" or None) |
| username | str \| None | no | Basic auth username |
| password | str \| None | no | Basic auth password |

### UpdateWebhookParams (request)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | str \| None | no | New name |
| url | str \| None | no | New URL |
| auth_type | str \| None | no | New auth type |
| username | str \| None | no | New username |
| password | str \| None | no | New password |
| is_enabled | bool \| None | no | New enabled state |

### WebhookTestParams (request)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| url | str | yes | URL to test |
| name | str \| None | no | Webhook name |
| auth_type | str \| None | no | Auth type |
| username | str \| None | no | Username for auth |
| password | str \| None | no | Password for auth |

### WebhookTestResult (response)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| success | bool | yes | Whether test succeeded |
| status_code | int | yes | HTTP status code |
| message | str | yes | Descriptive message |

### WebhookMutationResult (response)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str | yes | Webhook ID |
| name | str | yes | Webhook name |

---

## Entity Relationships

```
CustomAlert ──▶ AlertBookmark (linked saved report)
CustomAlert ──▶ AlertCreator (who created it)
CustomAlert ──▶ AlertWorkspace (workspace context)
CustomAlert ──▶ AlertProject (project context)

Annotation ──▶ AnnotationUser (creator)
Annotation ──▶ AnnotationTag[] (categorization)

ProjectWebhook (standalone, no relationships)
```

## Model Count Summary

| Domain | Response Models | Request Models | Enum | Total |
|--------|----------------|----------------|------|-------|
| Alerts | 11 (CustomAlert, AlertBookmark, AlertCreator, AlertWorkspace, AlertProject, AlertCount, AlertHistoryResponse, AlertHistoryPagination, AlertScreenshotResponse, ValidateAlertsForBookmarkResponse, AlertValidation) | 3 (Create, Update, ValidateForBookmark) | 1 (FrequencyPreset) | 15 |
| Annotations | 3 (Annotation, AnnotationUser, AnnotationTag) | 3 (CreateAnnotation, UpdateAnnotation, CreateAnnotationTag) | 0 | 6 |
| Webhooks | 3 (ProjectWebhook, WebhookTestResult, WebhookMutationResult) | 3 (Create, Update, TestParams) | 1 (AuthType) | 7 |
| **Total** | **15** | **9** | **2** | **26** |
