# Contract: Schema Registry API

**Feature**: 028-schema-governance | **Domain**: 14

## Python Library API (Workspace Methods)

### list_schema_registry

```python
def list_schema_registry(
    self,
    *,
    entity_type: str | None = None,
) -> list[SchemaEntry]:
    """List schema registry entries.

    Args:
        entity_type: Filter by entity type ("event", "custom_event", "profile").
            If None, returns all schemas.

    Returns:
        List of schema entries.

    Raises:
        AuthenticationError: Invalid credentials.
        RateLimitError: Rate limit exceeded.
    """
```

### create_schema

```python
def create_schema(
    self,
    entity_type: str,
    entity_name: str,
    schema_json: dict[str, Any],
) -> dict[str, Any]:
    """Create a single schema definition.

    Args:
        entity_type: Entity type ("event", "custom_event", "profile").
        entity_name: Entity name (event name or "$user" for profile).
        schema_json: JSON Schema Draft 7 definition.

    Returns:
        Created schema as dict.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Validation error (invalid schema, permissions).
        RateLimitError: Rate limit exceeded.
    """
```

### create_schemas_bulk

```python
def create_schemas_bulk(
    self,
    params: BulkCreateSchemasParams,
) -> BulkCreateSchemasResponse:
    """Bulk create schemas.

    Args:
        params: Bulk creation parameters with entries list and optional truncate flag.

    Returns:
        Response with added and deleted counts.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Validation error.
        RateLimitError: Rate limit exceeded (5/min org, 4000/min entities).
    """
```

### update_schema

```python
def update_schema(
    self,
    entity_type: str,
    entity_name: str,
    schema_json: dict[str, Any],
) -> dict[str, Any]:
    """Update a single schema definition (merge semantics).

    Args:
        entity_type: Entity type.
        entity_name: Entity name.
        schema_json: Partial JSON Schema to merge with existing.

    Returns:
        Updated schema as dict.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Entity not found or validation error.
        RateLimitError: Rate limit exceeded.
    """
```

### update_schemas_bulk

```python
def update_schemas_bulk(
    self,
    params: BulkCreateSchemasParams,
) -> list[BulkPatchResult]:
    """Bulk update schemas (merge semantics per entry).

    Args:
        params: Bulk update parameters with entries list.

    Returns:
        List of per-entry results with status ("ok" or "error").

    Raises:
        AuthenticationError: Invalid credentials.
        RateLimitError: Rate limit exceeded.
    """
```

### delete_schemas

```python
def delete_schemas(
    self,
    *,
    entity_type: str | None = None,
    entity_name: str | None = None,
) -> DeleteSchemasResponse:
    """Delete schemas by entity type and/or name.

    If both provided, deletes a single schema.
    If only entity_type, deletes all schemas of that type.
    If neither, deletes all schemas (use with caution).
    entity_name requires entity_type.

    Args:
        entity_type: Filter by entity type.
        entity_name: Filter by entity name (requires entity_type).

    Returns:
        Response with delete_count.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Invalid parameters (entity_name without entity_type).
        RateLimitError: Rate limit exceeded.
    """
```

## CLI Commands

```
mp schemas list [--entity-type TYPE] [--format FORMAT] [--jq FILTER]
mp schemas create --entity-type TYPE --entity-name NAME --schema-json JSON [--format FORMAT]
mp schemas create-bulk --entries JSON [--truncate] [--entity-type TYPE] [--format FORMAT]
mp schemas update --entity-type TYPE --entity-name NAME --schema-json JSON [--format FORMAT]
mp schemas update-bulk --entries JSON [--format FORMAT]
mp schemas delete [--entity-type TYPE] [--entity-name NAME] [--format FORMAT]
```

## API Endpoints

| Operation | HTTP | Path | Body |
|-----------|------|------|------|
| List | GET | `schemas/` or `schemas/{entity_type}/` | — |
| Create | POST | `schemas/{entity_type}/{entity_name}/` | schema_json |
| Create Bulk | POST | `schemas/` | BulkCreateSchemasParams |
| Update | PATCH | `schemas/{entity_type}/{entity_name}/` | schema_json |
| Update Bulk | PATCH | `schemas/` | BulkCreateSchemasParams |
| Delete | DELETE | `schemas/`, `schemas/{et}/`, or `schemas/{et}/{en}/` | — |

All paths use `maybe_scoped_path()`. Path segments are percent-encoded.
