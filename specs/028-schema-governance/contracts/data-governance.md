# Contract: Data Governance API

**Feature**: 028-schema-governance | **Domain**: 15

## Python Library API (Workspace Methods)

### Schema Enforcement

```python
def get_schema_enforcement(
    self,
    *,
    fields: str | None = None,
) -> SchemaEnforcementConfig:
    """Get current schema enforcement configuration.

    Args:
        fields: Comma-separated field names to return (e.g., "ruleEvent,state").
            If None, returns all fields.

    Returns:
        Schema enforcement configuration.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: No enforcement configured (404).
    """

def init_schema_enforcement(
    self,
    params: InitSchemaEnforcementParams,
) -> dict[str, Any]:
    """Initialize schema enforcement.

    Args:
        params: Init parameters with rule_event
            ("Warn and Accept", "Warn and Hide", "Warn and Drop").

    Returns:
        Raw API response as dict.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Enforcement already initialized or invalid rule_event.
    """

def update_schema_enforcement(
    self,
    params: UpdateSchemaEnforcementParams,
) -> dict[str, Any]:
    """Partially update enforcement configuration.

    Args:
        params: Partial update parameters. Only specified fields are updated.

    Returns:
        Raw API response as dict.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: No enforcement configured or validation error.
    """

def replace_schema_enforcement(
    self,
    params: ReplaceSchemaEnforcementParams,
) -> dict[str, Any]:
    """Fully replace enforcement configuration.

    Args:
        params: Complete replacement parameters (all required fields).

    Returns:
        Raw API response as dict.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Validation error.
    """

def delete_schema_enforcement(self) -> dict[str, Any]:
    """Delete enforcement configuration, disabling enforcement.

    Returns:
        Raw API response as dict.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: No enforcement configured.
    """
```

### Data Auditing

```python
def run_audit(self) -> AuditResponse:
    """Run a full data audit (events + properties).

    Returns:
        Audit response with violations and computed_at timestamp.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: No schemas defined.
    """

def run_audit_events_only(self) -> AuditResponse:
    """Run an events-only data audit (faster).

    Returns:
        Audit response with event violations only.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: No schemas defined.
    """
```

### Data Volume Anomalies

```python
def list_data_volume_anomalies(
    self,
    *,
    query_params: dict[str, str] | None = None,
) -> list[DataVolumeAnomaly]:
    """List detected data volume anomalies.

    Args:
        query_params: Optional filters. Supported keys:
            - status: "open" or "dismissed"
            - limit: Max results
            - event_id: Filter by event ID
            - prop_id: Filter by property ID
            - include_property_anomalies: "true"/"false"
            - include_metric_anomalies: "true"/"false"

    Returns:
        List of anomaly objects.

    Raises:
        AuthenticationError: Invalid credentials.
    """

def update_anomaly(
    self,
    params: UpdateAnomalyParams,
) -> dict[str, Any]:
    """Update the status of a single anomaly.

    Args:
        params: Update parameters with id, status, and anomaly_class.

    Returns:
        Raw API response as dict.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Anomaly not found or invalid parameters.
    """

def bulk_update_anomalies(
    self,
    params: BulkUpdateAnomalyParams,
) -> dict[str, Any]:
    """Bulk update anomaly statuses.

    Args:
        params: Bulk update with anomalies list and target status.

    Returns:
        Raw API response as dict.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Invalid parameters.
    """
```

### Event Deletion Requests

```python
def list_deletion_requests(self) -> list[EventDeletionRequest]:
    """List all event deletion requests.

    Returns:
        List of deletion requests with status.

    Raises:
        AuthenticationError: Invalid credentials.
    """

def create_deletion_request(
    self,
    params: CreateDeletionRequestParams,
) -> list[EventDeletionRequest]:
    """Create a new event deletion request.

    Args:
        params: Deletion parameters with event_name, from_date, to_date,
            and optional filters.

    Returns:
        Updated full list of deletion requests.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Validation error (date range, monthly limits, no matching events).
    """

def cancel_deletion_request(self, id: int) -> list[EventDeletionRequest]:
    """Cancel a pending deletion request.

    Args:
        id: Deletion request ID to cancel.

    Returns:
        Updated full list of deletion requests.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Request not found or not in cancellable state.
    """

def preview_deletion_filters(
    self,
    params: PreviewDeletionFiltersParams,
) -> list[dict[str, Any]]:
    """Preview what events a deletion filter would match.

    This is a read-only operation that does not modify any data.

    Args:
        params: Preview parameters with event_name, date range, and optional filters.

    Returns:
        List of expanded/normalized filters that would be applied.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Invalid filter parameters.
    """
```

## CLI Commands

### Enforcement

```
mp lexicon enforcement get [--fields FIELDS] [--format FORMAT] [--jq FILTER]
mp lexicon enforcement init --rule-event RULE [--format FORMAT]
mp lexicon enforcement update --body JSON [--format FORMAT]
mp lexicon enforcement replace --body JSON [--format FORMAT]
mp lexicon enforcement delete [--format FORMAT]
```

### Audit

```
mp lexicon audit [--events-only] [--format FORMAT] [--jq FILTER]
```

### Anomalies

```
mp lexicon anomalies list [--status STATUS] [--limit N] [--format FORMAT] [--jq FILTER]
mp lexicon anomalies update --id ID --status STATUS --anomaly-class CLASS [--format FORMAT]
mp lexicon anomalies bulk-update --body JSON [--format FORMAT]
```

### Deletion Requests

```
mp lexicon deletion-requests list [--format FORMAT] [--jq FILTER]
mp lexicon deletion-requests create --event-name NAME --from-date DATE --to-date DATE [--filters JSON] [--format FORMAT]
mp lexicon deletion-requests cancel ID [--format FORMAT]
mp lexicon deletion-requests preview --event-name NAME --from-date DATE --to-date DATE [--filters JSON] [--format FORMAT]
```

## API Endpoints

| Operation | HTTP | Path |
|-----------|------|------|
| Get enforcement | GET | `data-definitions/schema/` |
| Init enforcement | POST | `data-definitions/schema/` |
| Update enforcement | PATCH | `data-definitions/schema/` |
| Replace enforcement | PUT | `data-definitions/schema/` |
| Delete enforcement | DELETE | `data-definitions/schema/` |
| Full audit | GET | `data-definitions/audit/` |
| Events-only audit | GET | `data-definitions/audit-events-only/` |
| List anomalies | GET | `data-definitions/data-volume-anomalies/` |
| Update anomaly | PATCH | `data-definitions/data-volume-anomalies/` |
| Bulk update anomalies | PATCH | `data-definitions/data-volume-anomalies/bulk/` |
| List deletions | GET | `data-definitions/events/deletion-requests/` |
| Create deletion | POST | `data-definitions/events/deletion-requests/` |
| Cancel deletion | DELETE | `data-definitions/events/deletion-requests/` |
| Preview filters | POST | `data-definitions/events/deletion-requests/preview-filters/` |

All paths use `maybe_scoped_path()`.
