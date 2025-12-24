# Mixpanel Data Model Reference

## Table of Contents
1. [Core Concepts](#core-concepts)
2. [Events](#events)
3. [User Profiles](#user-profiles)
4. [Group Profiles](#group-profiles)
5. [Lookup Tables](#lookup-tables)
6. [Data Types](#data-types)
7. [Property System](#property-system)
8. [Profile Operations](#profile-operations)
9. [Pydantic Mapping Guidelines](#pydantic-mapping-guidelines)
10. [DuckDB Mapping Guidelines](#duckdb-mapping-guidelines)

## Core Concepts

### Data Model Architecture
Mixpanel implements a **fact and dimension table** architecture:

| Entity | Type | Purpose | Join Key |
|--------|------|---------|----------|
| **Events** | Fact Table | Time-series behavioral data | - |
| **User Profiles** | Dimension Table | User demographic attributes | `distinct_id` |
| **Group Profiles** | Dimension Table | Organization/account attributes | Custom group key |
| **Lookup Tables** | Dimension Table | Arbitrary entity enrichment | Custom join key |

### Key Principles
- **Events are immutable**: Once tracked, events cannot be modified
- **Profiles are mutable**: Represent current state, updated via operations
- **Properties are flexible**: Arbitrary JSON with type constraints
- **Joins happen at query time**: Not at ingestion time

## Events

### Definition
Events represent **timestamped user actions** within your product.

### Required Components
| Component | Type | Description |
|-----------|------|-------------|
| `event` | String | Name of the action (e.g., "Song Played") |
| `distinct_id` | String | User identifier |
| `time` | Timestamp | When the event occurred (ms since epoch or ISO format) |

### Recommended Components
| Component | Type | Purpose |
|-----------|------|---------|
| `$insert_id` | String (UUID) | Deduplication identifier |
| `token` | String | Project identifier (API requirement) |

### Structure Example
```json
{
  "event": "Song Played",
  "properties": {
    "distinct_id": "user_123",
    "time": 1601412131000,
    "$insert_id": "5d958f87-542d-4c10-9422-0ed75893dc81",
    "song_id": "song_456",
    "duration": 180,
    "shuffle_mode": true
  }
}
```

### Constraints
- **Event name limit**: 5,000 distinct event names (soft limit)
- **Properties per event**: Maximum 255
- **Property name/value length**: 255 characters
- **Batch size**: 2,000 events per API call

## User Profiles

### Definition
User Profiles are **key-value stores** containing persistent attributes about users.

### Key Field
- `distinct_id`: Unique user identifier (must match events)

### Common Properties
| Property | Purpose |
|----------|---------|
| `$name`, `$first_name`, `$last_name` | Name fields |
| `$email` | Email address |
| `$phone` | Phone number (include + for international) |
| `$created` | Account creation time |
| `$last_seen` | Last profile update (auto-maintained) |

### Constraints
- **Properties per profile**: Maximum 2,000
- **Property name length**: 255 characters
- **List property size**: 256KB

## Group Profiles

### Definition
Group Profiles enable **analysis at organizational level** (companies, teams, accounts).

### Structure
- **Group Type**: Category (e.g., "company", "team")
- **Group Key**: Identifier within type (e.g., "company_123")
- **Properties**: Attributes of the group

### B2B Analytics Features
- Company health metrics (DAU, WAU, MAU by company)
- User engagement per company
- Account-level retention

## Lookup Tables

### Definition
Lookup Tables provide **enrichment data** for events without indexing.

### Characteristics
- Custom join keys
- Not indexed for unique counting
- Can be referenced from events and profiles
- Dynamic schema based on data

### Use Cases
- Product catalogs
- Content metadata
- Geographic data

## Data Types

### Supported Types

| Type | Description | Limits |
|------|-------------|--------|
| **String** | Text values | 255 bytes (UTF-8) |
| **Numeric** | Integer or decimal | No specific limit |
| **Boolean** | true/false | JSON boolean |
| **Date** | Timestamps | ISO format in UTC |
| **List** | Array of scalars | 8KB (events), 256KB (profiles) |
| **Object** | Nested JSON (limited) | Max 255 keys, depth 3 |
| **List of Objects** | Array of objects (limited) | Same as List |

### Type Coercion Rules
- Unrecognized values → String
- Unix timestamps → Numeric (cast to Date for time operations)
- Null/"false"/0/empty → Boolean false
- Non-zero/non-empty → Boolean true

## Property System

### Property Categories

#### Event Properties
- Describe specific event instance
- Immutable once tracked
- Provide action context

#### Profile Properties
- Describe user/group overall
- Mutable - current state
- Demographic/firmographic

#### Super Properties
- Automatically included with every event
- Client-side only (stored in cookies)
- Persist between sessions

### Reserved Properties

#### Critical Event Properties
| Property | Purpose | Required |
|----------|---------|----------|
| `$distinct_id` | User identifier | Yes |
| `$time` | Event timestamp | Yes |
| `$insert_id` | Deduplication | Recommended |
| `$device_id` | Device tracking | Optional |
| `$user_id` | Cross-device ID | Optional |

#### Critical Profile Properties
| Property | Purpose |
|----------|---------|
| `$distinct_id` | Profile identifier |
| `$email` | Contact email |
| `$phone` | Contact phone |
| `$created` | Profile creation |
| `$last_seen` | Last update |

### Default Properties (Auto-collected)

#### From IP Address
- `$city`, `$region`, `mp_country_code`
- `$timezone` (profiles only)

#### From SDKs
- `$os`, `$os_version`
- `$browser`, `$browser_version` (web)
- `$device`, `$model`, `$manufacturer`
- `$screen_width`, `$screen_height`
- `$lib_version`, `mp_lib`

## Profile Operations

### Available Operations

| Operation | Purpose | Value Type | Behavior |
|-----------|---------|------------|----------|
| `$set` | Set properties | Any | Overwrites existing |
| `$set_once` | Set if not exists | Any | No-op if exists |
| `$add` | Increment numeric | Numeric | Adds to current value |
| `$union` | Merge into list | List | No duplicates |
| `$append` | Add to list | Any | Allows duplicates |
| `$remove` | Remove from list | Any | Removes all instances |
| `$unset` | Delete properties | Property names | Removes properties |
| `$delete` | Delete profile | Boolean | Removes entire profile |

### Operation Semantics
```json
{
  "$distinct_id": "user_123",
  "$token": "project_token",
  "$set": {
    "plan": "premium",
    "credits": 100
  },
  "$add": {
    "lifetime_value": 29.99
  }
}
```

## Pydantic Mapping Guidelines

### Core Principles
1. **Type Safety**: Enforce Mixpanel's type constraints
2. **Validation**: Catch errors before API calls
3. **Flexibility**: Support arbitrary properties via JSON

### Suggested Type Hierarchy
```python
# Base types
PropertyValue = Union[str, int, float, bool, datetime, List, Dict]

# Constrained types
ConstrainedString = constr(max_length=255)  # UTF-8 byte validation
EventName = constr(regex=r'^[a-zA-Z][a-zA-Z0-9_\s]*$')
DistinctId = constr(min_length=1)

# Property collections
EventProperties = Dict[str, PropertyValue]
ProfileProperties = Dict[str, PropertyValue]
```

### Model Structure Suggestions

#### Events
- Separate required fields from properties dict
- Validate `$insert_id` format (UUID)
- Normalize time to datetime internally
- Enforce byte limits on strings

#### Profiles
- Model operations as separate fields
- Validate operation-specific constraints
- Support both current state and operation models

#### Validation Points
- String byte length (not character length)
- List size limits (8KB/256KB)
- Property count limits (255/2000)
- Reserved property types

## DuckDB Mapping Guidelines

### Schema Design Principles

1. **Hybrid Storage**: Structured columns for hot properties + JSON for flexibility
2. **Temporal Versioning**: Current + history pattern for profiles
3. **Selective Indexing**: Only index what you query frequently
4. **Progressive Enhancement**: Start simple, optimize based on usage

### Suggested Table Structure

#### Events Table
```sql
-- Core structure
- event_name VARCHAR        -- Always structured
- event_time TIMESTAMP      -- Always structured
- distinct_id VARCHAR       -- Always structured
- insert_id VARCHAR PK      -- For deduplication
- properties JSON           -- Everything else

-- Promoted properties (based on usage)
- project_id VARCHAR        -- If multi-project
- platform VARCHAR          -- If commonly filtered
- [other hot properties]    -- Promote from JSON when needed
```

#### Profile Tables
```sql
-- Current state
- distinct_id VARCHAR PK
- email, name, etc.         -- Common properties as columns
- properties JSON           -- Remaining properties
- updated_at TIMESTAMP

-- History (if needed)
- distinct_id VARCHAR
- valid_from TIMESTAMP
- valid_to TIMESTAMP
- properties JSON           -- Snapshot
```

### JSON Query Patterns

#### Property Access
- Direct: `properties->>'$.field'`
- Nested: `properties->>'$.object.field'`
- Arrays: `JSON_EXTRACT_ARRAY(properties, '$.items')`

#### Type Casting
- String: Direct extraction
- Numeric: `CAST(properties->>'$.value' AS DECIMAL)`
- Boolean: `properties->>'$.flag' = 'true'`
- Date: `CAST(properties->>'$.timestamp' AS TIMESTAMP)`

### Optimization Strategies

1. **Property Registry**: Track types and usage
2. **Selective Promotion**: Move hot properties to columns
3. **Materialized Views**: Only for proven slow queries
4. **Partitioning**: By time for events, not profiles

### Data Pipeline Considerations

#### Ingestion
- Batch operations with deduplication on `insert_id`
- Type validation against property registry
- Profile operations as event stream

#### Maintenance
- Regular VACUUM ANALYZE
- Property statistics updates
- Archival of old events

---

*This reference provides a complete specification of Mixpanel's data model with suggested mappings to Pydantic and DuckDB. Focus on understanding the data model first, then adapt the mapping suggestions to your specific use case.*