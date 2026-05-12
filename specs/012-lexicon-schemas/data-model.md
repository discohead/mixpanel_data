# Data Model: Lexicon Schemas API

**Feature**: 012-lexicon-schemas
**Date**: 2025-12-24

---

## Type Alias

### EntityType

```python
EntityType = Literal["event", "profile"]
```

Constrains schema entity types to the two valid values supported by the Mixpanel Lexicon API.

---

## Entities

### LexiconMetadata

Platform-specific metadata attached to Lexicon schemas and properties.

```python
@dataclass(frozen=True)
class LexiconMetadata:
    """Mixpanel-specific metadata for Lexicon schemas and properties."""

    source: str | None
    """Origin of the schema definition (e.g., 'api', 'csv', 'ui')."""

    display_name: str | None
    """Human-readable display name in Mixpanel UI."""

    tags: list[str]
    """Categorization tags for organization."""

    hidden: bool
    """Whether hidden from Mixpanel UI."""

    dropped: bool
    """Whether data is dropped/ignored."""

    contacts: list[str]
    """Owner email addresses."""

    team_contacts: list[str]
    """Team ownership labels."""
```

**Field Mapping from API:**

| API Field | Model Field | Notes |
|-----------|-------------|-------|
| `$source` | `source` | Strip `$` prefix |
| `displayName` | `display_name` | snake_case conversion |
| `tags` | `tags` | Direct copy, default `[]` |
| `hidden` | `hidden` | Direct copy, default `False` |
| `dropped` | `dropped` | Direct copy, default `False` |
| `contacts` | `contacts` | Direct copy, default `[]` |
| `teamContacts` | `team_contacts` | snake_case conversion |

**Validation Rules:**
- All fields have sensible defaults for missing data
- `tags`, `contacts`, `team_contacts` default to empty lists
- `hidden`, `dropped` default to `False`
- `source`, `display_name` default to `None`

---

### LexiconProperty

Definition of a single property within a Lexicon schema.

```python
@dataclass(frozen=True)
class LexiconProperty:
    """Schema definition for a single property in a Lexicon schema."""

    type: str
    """JSON Schema type (string, number, boolean, array, object, integer, null)."""

    description: str | None
    """Human-readable description of the property."""

    metadata: LexiconMetadata | None
    """Optional Mixpanel-specific metadata."""
```

**Valid Type Values:**
- `"string"`
- `"number"`
- `"boolean"`
- `"array"`
- `"object"`
- `"integer"`
- `"null"`

**Validation Rules:**
- `type` is required (no default)
- `description` defaults to `None`
- `metadata` defaults to `None`

---

### LexiconDefinition

The structural definition of an event or profile property in the Lexicon.

```python
@dataclass(frozen=True)
class LexiconDefinition:
    """Full schema definition for an event or profile property in Lexicon."""

    description: str | None
    """Human-readable description of the entity."""

    properties: dict[str, LexiconProperty]
    """Property definitions keyed by property name."""

    metadata: LexiconMetadata | None
    """Optional Mixpanel-specific metadata for the entity."""
```

**Field Mapping from API:**

| API Field | Model Field | Notes |
|-----------|-------------|-------|
| `description` | `description` | Direct copy, default `None` |
| `properties` | `properties` | Parse each into LexiconProperty |
| `metadata.com.mixpanel` | `metadata` | Extract nested object |

**Validation Rules:**
- `properties` defaults to empty dict `{}`
- Each property value is parsed as `LexiconProperty`
- `metadata` extracted from `metadata.com.mixpanel` path

---

### LexiconSchema

A documented definition for an event or profile property from the Mixpanel Lexicon.

```python
@dataclass(frozen=True)
class LexiconSchema:
    """Complete schema definition from Mixpanel Lexicon."""

    entity_type: EntityType
    """Type of entity: 'event' or 'profile'."""

    name: str
    """Name of the event or profile property."""

    schema_json: LexiconDefinition
    """Full schema definition."""
```

**Field Mapping from API:**

| API Field | Model Field | Notes |
|-----------|-------------|-------|
| `entityType` | `entity_type` | snake_case conversion |
| `name` | `name` | Direct copy |
| `schemaJson` | `schema_json` | Parse as LexiconDefinition |

**Validation Rules:**
- All fields are required
- `entity_type` must be `"event"` or `"profile"`

---

## Serialization

All entities implement `to_dict()` for JSON serialization:

### LexiconMetadata.to_dict()

```python
def to_dict(self) -> dict[str, Any]:
    return {
        "source": self.source,
        "display_name": self.display_name,
        "tags": self.tags,
        "hidden": self.hidden,
        "dropped": self.dropped,
        "contacts": self.contacts,
        "team_contacts": self.team_contacts,
    }
```

### LexiconProperty.to_dict()

```python
def to_dict(self) -> dict[str, Any]:
    result: dict[str, Any] = {"type": self.type}
    if self.description is not None:
        result["description"] = self.description
    if self.metadata is not None:
        result["metadata"] = self.metadata.to_dict()
    return result
```

### LexiconDefinition.to_dict()

```python
def to_dict(self) -> dict[str, Any]:
    result: dict[str, Any] = {
        "properties": {k: v.to_dict() for k, v in self.properties.items()},
    }
    if self.description is not None:
        result["description"] = self.description
    if self.metadata is not None:
        result["metadata"] = self.metadata.to_dict()
    return result
```

### LexiconSchema.to_dict()

```python
def to_dict(self) -> dict[str, Any]:
    return {
        "entity_type": self.entity_type,
        "name": self.name,
        "schema_json": self.schema_json.to_dict(),
    }
```

---

## Factory Functions

### _parse_lexicon_metadata()

```python
def _parse_lexicon_metadata(data: dict[str, Any] | None) -> LexiconMetadata | None:
    """Parse Lexicon metadata from API response."""
    if data is None:
        return None
    mp_data = data.get("com.mixpanel", {})
    if not mp_data:
        return None
    return LexiconMetadata(
        source=mp_data.get("$source"),
        display_name=mp_data.get("displayName"),
        tags=mp_data.get("tags", []),
        hidden=mp_data.get("hidden", False),
        dropped=mp_data.get("dropped", False),
        contacts=mp_data.get("contacts", []),
        team_contacts=mp_data.get("teamContacts", []),
    )
```

### _parse_lexicon_property()

```python
def _parse_lexicon_property(data: dict[str, Any]) -> LexiconProperty:
    """Parse a single Lexicon property from API response."""
    return LexiconProperty(
        type=data.get("type", "string"),
        description=data.get("description"),
        metadata=_parse_lexicon_metadata(data.get("metadata")),
    )
```

### _parse_lexicon_definition()

```python
def _parse_lexicon_definition(data: dict[str, Any]) -> LexiconDefinition:
    """Parse Lexicon definition from API response."""
    properties_raw = data.get("properties", {})
    properties = {
        k: _parse_lexicon_property(v) for k, v in properties_raw.items()
    }
    return LexiconDefinition(
        description=data.get("description"),
        properties=properties,
        metadata=_parse_lexicon_metadata(data.get("metadata")),
    )
```

### _parse_lexicon_schema()

```python
def _parse_lexicon_schema(data: dict[str, Any]) -> LexiconSchema:
    """Parse a complete Lexicon schema from API response."""
    return LexiconSchema(
        entity_type=data["entityType"],
        name=data["name"],
        schema_json=_parse_lexicon_definition(data["schemaJson"]),
    )
```

---

## Relationship Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       LexiconSchema                         │
├─────────────────────────────────────────────────────────────┤
│ entity_type: "event" | "profile"                            │
│ name: str                                                   │
│ schema_json: LexiconDefinition ─────────────────────────┐   │
└─────────────────────────────────────────────────────────│───┘
                                                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    LexiconDefinition                        │
├─────────────────────────────────────────────────────────────┤
│ description: str | None                                     │
│ properties: dict[str, LexiconProperty] ─────────────────┐   │
│ metadata: LexiconMetadata | None ───────────┐           │   │
└─────────────────────────────────────────────│───────────│───┘
                                              │           ▼
                                              │   ┌───────────────────┐
                                              │   │  LexiconProperty  │
                                              │   ├───────────────────┤
                                              │   │ type: str         │
                                              │   │ description: ...  │
                                              │   │ metadata: ... ────┤
                                              │   └───────────────────┘
                                              ▼                       │
┌─────────────────────────────────────────────────────────────┐       │
│                    LexiconMetadata                          │◀──────┘
├─────────────────────────────────────────────────────────────┤
│ source: str | None                                          │
│ display_name: str | None                                    │
│ tags: list[str]                                             │
│ hidden: bool                                                │
│ dropped: bool                                               │
│ contacts: list[str]                                         │
│ team_contacts: list[str]                                    │
└─────────────────────────────────────────────────────────────┘
```
