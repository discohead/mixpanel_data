# Library API Contract: Data Governance CRUD

**Feature**: 027-data-governance-crud | **Date**: 2026-04-01

## Workspace Methods

### Data Definitions (Lexicon)

```python
# Event definitions
def get_event_definitions(self, *, names: list[str]) -> list[EventDefinition]: ...
def update_event_definition(self, event_name: str, params: UpdateEventDefinitionParams) -> EventDefinition: ...
def delete_event_definition(self, event_name: str) -> None: ...
def bulk_update_event_definitions(self, params: BulkUpdateEventsParams) -> list[EventDefinition]: ...

# Property definitions
def get_property_definitions(self, *, names: list[str], resource_type: str | None = None) -> list[PropertyDefinition]: ...
def update_property_definition(self, property_name: str, params: UpdatePropertyDefinitionParams) -> PropertyDefinition: ...
def bulk_update_property_definitions(self, params: BulkUpdatePropertiesParams) -> list[PropertyDefinition]: ...

# Tags
def list_lexicon_tags(self) -> list[LexiconTag]: ...
def create_lexicon_tag(self, params: CreateTagParams) -> LexiconTag: ...
def update_lexicon_tag(self, tag_id: int, params: UpdateTagParams) -> LexiconTag: ...
def delete_lexicon_tag(self, tag_name: str) -> None: ...

# Tracking & history
def get_tracking_metadata(self, event_name: str) -> dict[str, Any]: ...
def get_event_history(self, event_name: str) -> list[dict[str, Any]]: ...
def get_property_history(self, property_name: str, entity_type: str) -> list[dict[str, Any]]: ...

# Export
def export_lexicon(self, *, export_types: list[str] | None = None) -> dict[str, Any]: ...
```

### Drop Filters

```python
def list_drop_filters(self) -> list[DropFilter]: ...
def create_drop_filter(self, params: CreateDropFilterParams) -> list[DropFilter]: ...
def update_drop_filter(self, params: UpdateDropFilterParams) -> list[DropFilter]: ...
def delete_drop_filter(self, drop_filter_id: int) -> list[DropFilter]: ...
def get_drop_filter_limits(self) -> DropFilterLimitsResponse: ...
```

Note: Drop filter mutations return the full list after mutation (API behavior).

### Custom Properties

```python
def list_custom_properties(self) -> list[CustomProperty]: ...
def create_custom_property(self, params: CreateCustomPropertyParams) -> CustomProperty: ...
def get_custom_property(self, property_id: str) -> CustomProperty: ...
def update_custom_property(self, property_id: str, params: UpdateCustomPropertyParams) -> CustomProperty: ...
def delete_custom_property(self, property_id: str) -> None: ...
def validate_custom_property(self, params: CreateCustomPropertyParams) -> dict[str, Any]: ...
```

### Custom Events

```python
def list_custom_events(self) -> list[EventDefinition]: ...
def update_custom_event(self, event_name: str, params: UpdateEventDefinitionParams) -> EventDefinition: ...
def delete_custom_event(self, event_name: str) -> None: ...
```

### Lookup Tables

```python
def list_lookup_tables(self, *, data_group_id: int | None = None) -> list[LookupTable]: ...
def upload_lookup_table(self, params: UploadLookupTableParams) -> LookupTable: ...
def mark_lookup_table_ready(self, params: MarkLookupTableReadyParams) -> LookupTable: ...
def get_lookup_upload_url(self, content_type: str = "text/csv") -> LookupTableUploadUrl: ...
def get_lookup_upload_status(self, upload_id: str) -> dict[str, Any]: ...
def update_lookup_table(self, data_group_id: int, params: UpdateLookupTableParams) -> LookupTable: ...
def delete_lookup_tables(self, data_group_ids: list[int]) -> None: ...
def download_lookup_table(self, data_group_id: int, *, file_name: str | None = None, limit: int | None = None) -> bytes: ...
def get_lookup_download_url(self, data_group_id: int) -> str: ...
```

## CLI Commands

### mp lexicon

```
mp lexicon events get --names NAME1,NAME2 [--format FORMAT] [--jq EXPR]
mp lexicon events update --name NAME [--hidden] [--dropped] [--verified] [--description DESC] [--tags TAG1,TAG2] [--format FORMAT]
mp lexicon events delete --name NAME
mp lexicon events bulk-update --data JSON [--format FORMAT]
mp lexicon properties get --names NAME1,NAME2 [--resource-type TYPE] [--format FORMAT]
mp lexicon properties update --name NAME [--hidden] [--dropped] [--sensitive] [--description DESC] [--format FORMAT]
mp lexicon properties bulk-update --data JSON [--format FORMAT]
mp lexicon tags list [--format FORMAT]
mp lexicon tags create --name NAME [--format FORMAT]
mp lexicon tags update --id ID --name NAME [--format FORMAT]
mp lexicon tags delete --name NAME
mp lexicon tracking-metadata --event-name NAME [--format FORMAT]
mp lexicon event-history --event-name NAME [--format FORMAT]
mp lexicon property-history --property-name NAME --entity-type TYPE [--format FORMAT]
mp lexicon export [--types events,properties] [--format FORMAT]
```

### mp custom-properties

```
mp custom-properties list [--format FORMAT]
mp custom-properties get --id ID [--format FORMAT]
mp custom-properties create --name NAME --resource-type TYPE [--display-formula FORMULA] [--composed-properties JSON] [--behavior JSON] [--format FORMAT]
mp custom-properties update --id ID [--name NAME] [--description DESC] [--display-formula FORMULA] [--format FORMAT]
mp custom-properties delete --id ID
mp custom-properties validate --name NAME --resource-type TYPE [--display-formula FORMULA] [--composed-properties JSON] [--behavior JSON] [--format FORMAT]
```

### mp custom-events

```
mp custom-events list [--format FORMAT]
mp custom-events update --name NAME [--hidden] [--dropped] [--description DESC] [--format FORMAT]
mp custom-events delete --name NAME
```

### mp drop-filters

```
mp drop-filters list [--format FORMAT]
mp drop-filters create --event-name NAME --filters JSON [--format FORMAT]
mp drop-filters update --id ID [--event-name NAME] [--filters JSON] [--active/--no-active] [--format FORMAT]
mp drop-filters delete --id ID [--format FORMAT]
mp drop-filters limits [--format FORMAT]
```

### mp lookup-tables

```
mp lookup-tables list [--data-group-id ID] [--format FORMAT]
mp lookup-tables upload --name NAME --file PATH [--data-group-id ID] [--format FORMAT]
mp lookup-tables update --data-group-id ID --name NAME [--format FORMAT]
mp lookup-tables delete --data-group-ids ID1,ID2 
mp lookup-tables upload-url [--content-type TYPE] [--format FORMAT]
mp lookup-tables download --data-group-id ID [--file-name NAME] [--limit N] [--output PATH]
mp lookup-tables download-url --data-group-id ID [--format FORMAT]
```

## Error Handling

All methods raise the standard exception hierarchy:
- `ConfigError` — Missing credentials or configuration
- `AuthenticationError` — Invalid credentials (401)
- `QueryError` — API error (400, 404)
- `ServerError` — Server-side errors (5xx)
- `RateLimitError` — Rate limited (429)
