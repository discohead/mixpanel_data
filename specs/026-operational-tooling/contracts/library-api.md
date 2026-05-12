# Library API Contract: Alerts, Annotations, and Webhooks

**Branch**: `026-operational-tooling` | **Date**: 2026-03-31

All methods are on the `Workspace` class. Import models from `mixpanel_data.types`.

---

## Alerts

```python
# List all alerts, optionally filtered
def list_alerts(
    self,
    *,
    bookmark_id: int | None = None,
    skip_user_filter: bool | None = None,
) -> list[CustomAlert]: ...

# Create a new alert
def create_alert(self, params: CreateAlertParams) -> CustomAlert: ...

# Get a single alert
def get_alert(self, alert_id: int) -> CustomAlert: ...

# Update an alert (partial)
def update_alert(self, alert_id: int, params: UpdateAlertParams) -> CustomAlert: ...

# Delete an alert
def delete_alert(self, alert_id: int) -> None: ...

# Bulk delete alerts
def bulk_delete_alerts(self, ids: list[int]) -> None: ...

# Get alert count and limits
def get_alert_count(self, *, alert_type: str | None = None) -> AlertCount: ...

# Get paginated alert history
def get_alert_history(
    self,
    alert_id: int,
    *,
    page_size: int | None = None,
    next_cursor: str | None = None,
    previous_cursor: str | None = None,
) -> AlertHistoryResponse: ...

# Test alert config without persisting
def test_alert(self, params: CreateAlertParams) -> dict[str, Any]: ...

# Get signed screenshot URL
def get_alert_screenshot_url(self, gcs_key: str) -> AlertScreenshotResponse: ...

# Validate alerts for a bookmark
def validate_alerts_for_bookmark(
    self, params: ValidateAlertsForBookmarkParams
) -> ValidateAlertsForBookmarkResponse: ...
```

## Annotations

```python
# List annotations with optional filters
def list_annotations(
    self,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    tags: list[int] | None = None,
) -> list[Annotation]: ...

# Create an annotation
def create_annotation(self, params: CreateAnnotationParams) -> Annotation: ...

# Get a single annotation
def get_annotation(self, annotation_id: int) -> Annotation: ...

# Update an annotation (partial)
def update_annotation(
    self, annotation_id: int, params: UpdateAnnotationParams
) -> Annotation: ...

# Delete an annotation
def delete_annotation(self, annotation_id: int) -> None: ...

# List annotation tags
def list_annotation_tags(self) -> list[AnnotationTag]: ...

# Create an annotation tag
def create_annotation_tag(self, params: CreateAnnotationTagParams) -> AnnotationTag: ...
```

## Webhooks

```python
# List all webhooks
def list_webhooks(self) -> list[ProjectWebhook]: ...

# Create a webhook
def create_webhook(self, params: CreateWebhookParams) -> WebhookMutationResult: ...

# Update a webhook (partial)
def update_webhook(
    self, webhook_id: str, params: UpdateWebhookParams
) -> WebhookMutationResult: ...

# Delete a webhook
def delete_webhook(self, webhook_id: str) -> None: ...

# Test webhook connectivity
def test_webhook(self, params: WebhookTestParams) -> WebhookTestResult: ...
```

---

## Usage Examples

### Alerts

```python
import mixpanel_data as mp
from mixpanel_data.types import CreateAlertParams, UpdateAlertParams

ws = mp.Workspace()

# List all alerts
alerts = ws.list_alerts()

# Create an alert linked to a bookmark
alert = ws.create_alert(CreateAlertParams(
    bookmark_id=12345,
    name="Daily signups drop",
    condition={"operator": "less_than", "value": 100},
    frequency=86400,  # daily
    paused=False,
    subscriptions=[{"type": "email", "value": "team@example.com"}],
))

# Get alert history
history = ws.get_alert_history(alert.id, page_size=50)

# Test before creating
test_result = ws.test_alert(CreateAlertParams(
    bookmark_id=12345,
    name="Test alert",
    condition={"operator": "less_than", "value": 100},
    frequency=3600,
    paused=False,
    subscriptions=[],
))
```

### Annotations

```python
from mixpanel_data.types import CreateAnnotationParams, CreateAnnotationTagParams

# Create a tag
tag = ws.create_annotation_tag(CreateAnnotationTagParams(name="releases"))

# Create an annotation with tag
annotation = ws.create_annotation(CreateAnnotationParams(
    date="2026-03-31",
    description="v2.5 release",
    tags=[tag.id],
))

# List annotations for a date range
annotations = ws.list_annotations(from_date="2026-03-01", to_date="2026-03-31")
```

### Webhooks

```python
from mixpanel_data.types import CreateWebhookParams, WebhookTestParams

# Test connectivity first
test = ws.test_webhook(WebhookTestParams(
    url="https://example.com/webhook",
    auth_type="basic",
    username="user",
    password="pass",
))

if test.success:
    # Create the webhook
    result = ws.create_webhook(CreateWebhookParams(
        name="Pipeline webhook",
        url="https://example.com/webhook",
        auth_type="basic",
        username="user",
        password="pass",
    ))
```
