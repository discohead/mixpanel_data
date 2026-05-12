# Feature Specification: Lexicon Schemas API (Read Operations)

**Feature Branch**: `012-lexicon-schemas`
**Created**: 2025-12-24
**Status**: Draft
**Input**: Add read-only Lexicon Schemas API support to DiscoveryService for retrieving data dictionary definitions including event and profile property schemas

---

## Overview

This feature extends the Discovery Service to support Mixpanel's Lexicon Schemas API for retrieving data dictionary definitions. The Lexicon API enables AI agents, analysts, and developers to programmatically explore documented schema definitions for events and profile properties.

**Important Distinction**: The Lexicon Schemas API returns only events and properties that have explicit schema definitions (created via API, CSV import, or UI metadata additions). It does NOT return all events visible in the Mixpanel Lexicon UI, which also shows events transmitted in the last 30 days without formal schemas.

---

## User Scenarios & Testing

### User Story 1 - List All Project Schemas (Priority: P1)

As an AI coding agent or data analyst, I want to list all schemas in a project so that I can understand the complete documented data structure before writing queries or analysis code.

**Why this priority**: This is the foundational capability that enables all schema discovery workflows. Without the ability to list schemas, users cannot explore what data definitions exist in their project.

**Independent Test**: Can be fully tested by calling the list operation and verifying a complete list of schema objects is returned. Delivers immediate value by exposing the full data dictionary.

**Acceptance Scenarios**:

1. **Given** valid credentials and a project with defined schemas, **When** I request all schemas, **Then** I receive a list of schema objects containing entity type, name, and schema definition for each.
2. **Given** valid credentials and a project with no defined schemas, **When** I request all schemas, **Then** I receive an empty list (not an error).
3. **Given** valid credentials, **When** I request all schemas multiple times in the same session, **Then** subsequent requests return cached results without additional network calls.
4. **Given** each schema in the list, **Then** it contains the entity type (event or profile), the entity name, and the full schema definition including description and properties.

---

### User Story 2 - Filter Schemas by Entity Type (Priority: P1)

As an AI coding agent or data analyst, I want to list schemas filtered by entity type (events or profile properties) so that I can focus on the specific category of data relevant to my current task.

**Why this priority**: Most analysis tasks focus on either events (behavioral data) or profile properties (user attributes). Filtering reduces cognitive load and provides targeted results.

**Independent Test**: Can be fully tested by calling the filtered list operation with each entity type and verifying only matching schemas are returned. Delivers focused results for type-specific analysis.

**Acceptance Scenarios**:

1. **Given** valid credentials and entity type "event", **When** I request schemas, **Then** I receive only event schemas.
2. **Given** valid credentials and entity type "profile", **When** I request schemas, **Then** I receive only profile property schemas.
3. **Given** an entity type with no defined schemas, **When** I request schemas, **Then** I receive an empty list (not an error).
4. **Given** different entity type filter values, **When** I request schemas, **Then** results are cached separately per entity type.

---

### User Story 3 - Get Single Schema by Name (Priority: P2)

As an AI coding agent or data analyst, I want to retrieve a specific schema by entity type and name so that I can inspect its detailed structure when I already know which event or property I need.

**Why this priority**: Once users know what they're looking for, direct lookup is more efficient than listing and filtering. This supports targeted queries in automated workflows.

**Independent Test**: Can be fully tested by requesting a known schema by type and name and verifying the complete schema definition is returned. Delivers precise lookup for known entities.

**Acceptance Scenarios**:

1. **Given** valid credentials and an existing schema, **When** I request it by entity type and name, **Then** I receive a single schema object with full definition.
2. **Given** a non-existent schema name, **When** I request it, **Then** I receive an empty result (not an error).
3. **Given** valid credentials, **When** I request the same schema multiple times in a session, **Then** subsequent requests return cached results.
4. **Given** schema names with special characters or spaces, **When** I request them, **Then** the system handles encoding correctly and returns the schema if it exists.

---

### User Story 4 - Access Schemas via CLI (Priority: P2)

As a developer or analyst working in the terminal, I want to inspect Lexicon schemas using the CLI so that I can quickly explore data definitions without writing code.

**Why this priority**: CLI access enables rapid exploration and scripting. It complements the programmatic API for interactive use cases.

**Independent Test**: Can be fully tested by running `mp inspect lexicon` commands and verifying output displays schema information in the requested format. Delivers terminal-based schema exploration.

**Acceptance Scenarios**:

1. **Given** valid CLI configuration, **When** I run `mp inspect lexicon`, **Then** I see a list of all schemas in a readable format.
2. **Given** the entity-type filter option, **When** I run `mp inspect lexicon --entity-type event` or `--entity-type profile`, **Then** I see only schemas of that type.
3. **Given** the name option with an entity type, **When** I run `mp inspect lexicon --entity-type event --name Purchase`, **Then** I see the detailed schema for that specific entity.
4. **Given** output format options (JSON, table, CSV), **When** I specify `--format`, **Then** output is rendered in that format.

---

### Edge Cases

- **Empty project**: A project with no schema definitions returns an empty list, not an error.
- **Invalid entity type**: Requesting an entity type other than "event" or "profile" produces a clear validation error.
- **Schema name not found**: Looking up a non-existent schema returns empty/null, not an error.
- **Special characters in names**: Schema names containing spaces, unicode, or URL-sensitive characters are handled correctly.
- **Rate limit exceeded**: When the API rate limit (5 requests/minute) is hit, the system provides appropriate feedback and handles retries gracefully.
- **Invalid credentials**: Authentication failures produce clear error messages distinguishable from other errors.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST provide a method to list all schemas in a project, returning entity type, name, and schema definition for each.
- **FR-002**: System MUST provide a method to list schemas filtered by entity type ("event" or "profile").
- **FR-003**: System MUST provide a method to retrieve a single schema by entity type and name.
- **FR-004**: System MUST cache schema query results within a session to minimize API calls given the strict rate limit.
- **FR-005**: System MUST provide a method to clear cached schema data when fresh data is needed.
- **FR-006**: System MUST return empty results (not errors) when no schemas match the query criteria.
- **FR-007**: System MUST handle schema lookup failures gracefully, returning null/empty for non-existent schemas.
- **FR-008**: System MUST expose schema operations through the CLI with filtering and output format options.
- **FR-009**: System MUST include schema types in the public API exports for programmatic access.
- **FR-010**: All schema result types MUST support serialization to dictionary format for interoperability.

### Key Entities

- **LexiconSchema**: A documented definition for an event or profile property from the Mixpanel Lexicon. Contains the entity type (event or profile), the entity name, and the full schema definition.

- **LexiconDefinition**: The structural definition of an event or profile property. Contains a description, a collection of property definitions, and optional metadata.

- **LexiconProperty**: The definition of a single property within a Lexicon schema. Contains the data type (string, number, boolean, array, object, etc.), optional description, and optional metadata.

- **LexiconMetadata**: Platform-specific metadata attached to Lexicon schemas and properties. Includes display name, categorization tags, visibility flags (hidden, dropped), and ownership information (contacts, team contacts).

- **EntityType**: A classification of schema entities, limited to "event" (behavioral tracking events) or "profile" (user profile properties).

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: Users can retrieve all project schemas in a single operation that completes within normal API response times.
- **SC-002**: Users can filter schemas by entity type, receiving only relevant results.
- **SC-003**: Users can look up a specific schema by type and name, receiving the complete definition or empty result.
- **SC-004**: Repeated schema queries within a session use cached data, making only one API call per unique query.
- **SC-005**: CLI users can list and inspect schemas with the same capabilities as the programmatic API.
- **SC-006**: All new schema types are accessible through the public API for programmatic use.
- **SC-007**: Schema operations handle the API rate limit (5 requests/minute) without causing errors in normal usage patterns.
- **SC-008**: All schema result types can be serialized to dictionary format for JSON export and interoperability.

---

## Assumptions

- **A-001**: Schema definitions are relatively stable within a user session, making caching appropriate without automatic invalidation.
- **A-002**: The Mixpanel Lexicon API follows consistent patterns across all supported regions (US, EU, India).
- **A-003**: Non-existent schema lookups return a distinguishable response (likely HTTP 404) that can be mapped to an empty result.
- **A-004**: Entity type values are case-sensitive and must be lowercase ("event", "profile").
- **A-005**: Schema names may contain special characters that require URL encoding, which is handled by the underlying HTTP client.
- **A-006**: Users who need fresh schema data can manually clear the cache using existing cache management methods.

---

## Out of Scope

- **Schema creation, modification, or deletion**: This feature covers read-only operations only.
- **Schema validation**: The feature stores and returns schema structures but does not validate incoming event data against them.
- **Automatic cache invalidation**: Schemas are cached for the session; users must manually clear cache if needed.
- **Annotations API**: Separate API with different use case (marking points in time on reports).
- **Data compliance APIs**: GDPR and data privacy operations are unrelated to schema discovery.

---

## Dependencies

- Existing Discovery Service with caching infrastructure
- Existing Workspace facade pattern for public API exposure
- Existing CLI command structure with output format support
- HTTP client with authentication and regional endpoint support

---

## Related Changes (Scope Expansion)

**Breaking Change**: Rename `Workspace.schema(table)` to `Workspace.table_schema(table)`

To avoid naming confusion between local DuckDB table schema inspection and remote Mixpanel Lexicon schema retrieval, the existing `ws.schema()` method will be renamed to `ws.table_schema()`. This provides clear disambiguation:

- `ws.table_schema("events")` → Local DuckDB table schema (existing, renamed)
- `ws.lexicon_schema("event", "Purchase")` → Remote Mixpanel Lexicon schema (new)

This is a breaking change, but acceptable as the library has not yet been released publicly.
