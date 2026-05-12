# Feature Specification: Local Introspection API

**Feature Branch**: `014-introspection-api`
**Created**: 2024-12-25
**Status**: Draft
**Input**: User description: "Add local introspection API methods to Workspace class for exploring DuckDB data: sample(), summarize(), event_breakdown(), property_keys(), and column_stats()"

## Problem Statement

After fetching Mixpanel data into a local database, users (human analysts and AI agents) need to quickly understand what's in the data before writing queries. Currently this requires writing custom queries to:

- See sample data rows
- Get statistical summaries of columns
- Understand event distribution
- Discover JSON property structure
- Analyze individual columns in depth

This friction slows exploration and is especially problematic for AI agents that need to understand unfamiliar data before generating analysis queries.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sample Data Inspection (Priority: P1)

An analyst or AI agent wants to see actual data rows before writing queries, to understand the structure, property formats, and value types present in the data.

**Why this priority**: This is the most fundamental exploration action. Without seeing real data, users cannot understand what they're working with. It's also the simplest to implement and provides immediate value.

**Independent Test**: Can be fully tested by sampling any table and verifying representative rows are returned. Delivers immediate data visibility.

**Acceptance Scenarios**:

1. **Given** a table with data, **When** I request a sample, **Then** I receive a random selection of rows from throughout the table (not just the first N rows)
2. **Given** a table with data, **When** I request a sample with a specific count, **Then** I receive exactly that many rows
3. **Given** a table with fewer rows than requested, **When** I request a sample, **Then** I receive all available rows
4. **Given** a non-existent table, **When** I request a sample, **Then** I receive a clear error indicating the table doesn't exist

---

### User Story 2 - Statistical Summary (Priority: P1)

An analyst exploring an unfamiliar table wants instant statistical context before writing queries—understanding data types, value ranges, null rates, and cardinality for every column.

**Why this priority**: Statistical summaries provide comprehensive table-level understanding in a single operation. This is essential context for any subsequent analysis.

**Independent Test**: Can be fully tested by summarizing any table and verifying per-column statistics are returned. Delivers complete table overview.

**Acceptance Scenarios**:

1. **Given** a table with data, **When** I request a summary, **Then** I receive statistics for every column including data type, min/max values, null percentage, and approximate distinct count
2. **Given** a table with numeric columns, **When** I request a summary, **Then** numeric columns include mean, standard deviation, and quartile values
3. **Given** a table with non-numeric columns, **When** I request a summary, **Then** non-numeric columns have null for numeric-only statistics
4. **Given** a non-existent table, **When** I request a summary, **Then** I receive a clear error indicating the table doesn't exist

---

### User Story 3 - Event Distribution Analysis (Priority: P2)

An analyst who fetched a month of events wants to understand what's in the data—which event types exist, how many of each, how many users triggered each, and the time range covered.

**Why this priority**: Event breakdown is specific to analytics workflows but provides critical context for any event-based analysis. It builds on the foundation of P1 features.

**Independent Test**: Can be fully tested by analyzing any event table and verifying per-event statistics are returned. Delivers event-level insights.

**Acceptance Scenarios**:

1. **Given** an event table with data, **When** I request an event breakdown, **Then** I receive statistics for each unique event type including count, unique users, first/last occurrence, and percentage of total
2. **Given** an event table, **When** I request an event breakdown, **Then** events are ordered by count descending (most frequent first)
3. **Given** an event table, **When** I request an event breakdown, **Then** I receive overall totals including total events, total unique users, and date range
4. **Given** a table missing required columns (event name, event time, user ID), **When** I request an event breakdown, **Then** I receive a clear error listing the missing columns
5. **Given** a non-existent table, **When** I request an event breakdown, **Then** I receive a clear error indicating the table doesn't exist

---

### User Story 4 - Property Key Discovery (Priority: P2)

An agent sees a JSON properties column and needs to know what keys exist before querying them. They want to discover all available property keys, optionally filtered to a specific event type.

**Why this priority**: JSON property discovery is essential for querying nested data but requires the user to already understand the table structure (from P1 features).

**Independent Test**: Can be fully tested by discovering keys in any table with JSON properties. Delivers queryable field visibility.

**Acceptance Scenarios**:

1. **Given** a table with JSON properties, **When** I request property keys, **Then** I receive an alphabetically sorted list of all distinct keys across all rows
2. **Given** a table with JSON properties, **When** I request property keys for a specific event type, **Then** I receive only keys present in events of that type
3. **Given** a table with empty JSON objects, **When** I request property keys, **Then** I receive an empty list
4. **Given** a table without a properties column, **When** I request property keys, **Then** I receive a clear error indicating the column is missing
5. **Given** a non-existent table, **When** I request property keys, **Then** I receive a clear error indicating the table doesn't exist

---

### User Story 5 - Deep Column Analysis (Priority: P3)

An analyst sees a column in the summary with high cardinality and wants to dig deeper—understanding the top values, their frequencies, null distribution, and (for numeric columns) detailed statistics.

**Why this priority**: Deep column analysis is a drill-down feature that users reach after using P1/P2 features to identify columns of interest.

**Independent Test**: Can be fully tested by analyzing any column and verifying detailed statistics are returned. Delivers column-level insights.

**Acceptance Scenarios**:

1. **Given** a table with data, **When** I request column statistics, **Then** I receive count, null count, null percentage, approximate distinct count, and unique percentage
2. **Given** a table with data, **When** I request column statistics, **Then** I receive top values ordered by frequency descending
3. **Given** a table with data, **When** I request column statistics with a custom top count, **Then** I receive that many top values
4. **Given** a numeric column, **When** I request column statistics, **Then** I receive min, max, mean, and standard deviation
5. **Given** a non-numeric column, **When** I request column statistics, **Then** numeric statistics are null
6. **Given** a JSON path expression (to analyze nested properties), **When** I request column statistics, **Then** the expression is evaluated and statistics are returned for the extracted values
7. **Given** a non-existent table, **When** I request column statistics, **Then** I receive a clear error indicating the table doesn't exist

---

### User Story 6 - Command-Line Access (Priority: P3)

A user working in the terminal wants to run introspection commands via the CLI with flexible output formats (table, JSON, etc.) for integration with other tools.

**Why this priority**: CLI access extends the programmatic API to terminal users but is not required for core functionality.

**Independent Test**: Can be fully tested by running CLI commands and verifying formatted output. Delivers terminal-based data exploration.

**Acceptance Scenarios**:

1. **Given** a table with data, **When** I run sample/summarize/breakdown/keys/column commands, **Then** I receive formatted output appropriate to the chosen format
2. **Given** any introspection command, **When** I specify JSON format, **Then** I receive machine-readable JSON output
3. **Given** any introspection command with an invalid table, **When** I run the command, **Then** I receive a user-friendly error message

---

### Edge Cases

- What happens when a table is empty (zero rows)?
- How does sampling behave when requested count exceeds table size?
- What happens when JSON properties contain nested objects?
- How are null values handled in statistical calculations?
- What happens when all values in a column are null?
- How does event breakdown handle null event names or timestamps?

## Requirements *(mandatory)*

### Functional Requirements

#### Core Sampling

- **FR-001**: System MUST provide random sampling that returns rows from throughout the table, not just the first N rows
- **FR-002**: System MUST allow users to specify the number of sample rows (default: 10)
- **FR-003**: System MUST return fewer rows than requested when the table has insufficient data

#### Statistical Summary

- **FR-004**: System MUST compute per-column statistics including data type, min, max, approximate distinct count, count, and null percentage
- **FR-005**: System MUST compute numeric-only statistics (mean, standard deviation, quartiles) for numeric columns
- **FR-006**: System MUST return null for numeric-only statistics on non-numeric columns
- **FR-007**: System MUST report total row count for the table

#### Event Distribution

- **FR-008**: System MUST compute per-event statistics including count, unique users, first seen, last seen, and percentage of total
- **FR-009**: System MUST order events by count descending
- **FR-010**: System MUST compute overall totals including total events, total unique users, and date range
- **FR-011**: System MUST validate that required columns (event name, event time, user ID) exist before querying
- **FR-012**: System MUST provide a clear error message listing any missing required columns

#### Property Discovery

- **FR-013**: System MUST extract all distinct keys from JSON property columns
- **FR-014**: System MUST return keys in alphabetical order
- **FR-015**: System MUST support filtering keys to a specific event type
- **FR-016**: System MUST return an empty list when no keys exist

#### Column Analysis

- **FR-017**: System MUST compute column statistics including count, null count, null percentage, distinct count, and unique percentage
- **FR-018**: System MUST compute top values with their frequencies, ordered by frequency descending
- **FR-019**: System MUST allow users to specify the number of top values (default: 10)
- **FR-020**: System MUST compute numeric statistics (min, max, mean, std) for numeric columns
- **FR-021**: System MUST support JSON path expressions for analyzing nested properties

#### Result Types

- **FR-022**: All introspection results MUST be serializable to JSON via a standard method
- **FR-023**: All introspection results with multiple records MUST be convertible to tabular format
- **FR-024**: Result types MUST be immutable after creation

#### Error Handling

- **FR-025**: System MUST raise a specific error when a table doesn't exist
- **FR-026**: System MUST raise a specific error when required columns are missing
- **FR-027**: Error messages MUST be actionable (tell the user what's wrong and what they can do)

#### CLI Integration

- **FR-028**: All introspection methods MUST be accessible via command-line interface
- **FR-029**: CLI commands MUST support multiple output formats (table, JSON at minimum)
- **FR-030**: CLI commands MUST display user-friendly error messages

### Key Entities

- **ColumnSummary**: Statistics for a single column including name, type, min, max, distinct count, null percentage, and (for numeric) mean, std, quartiles
- **SummaryResult**: Collection of column summaries for a table with total row count
- **EventStats**: Statistics for a single event type including name, count, unique users, first/last seen, percentage of total
- **EventBreakdownResult**: Collection of event statistics with overall totals and date range
- **ColumnStatsResult**: Deep analysis of a single column including null analysis, cardinality, top values, and numeric statistics

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can sample any table and receive random rows in under 1 second for tables up to 1 million rows
- **SC-002**: Users can summarize any table and receive complete column statistics in under 5 seconds for tables up to 1 million rows
- **SC-003**: Users can analyze event distribution and receive per-event statistics in under 5 seconds for tables up to 1 million rows
- **SC-004**: Users can discover all JSON property keys in under 5 seconds for tables up to 1 million rows
- **SC-005**: Users can analyze any column and receive detailed statistics in under 2 seconds for tables up to 1 million rows
- **SC-006**: All result types successfully serialize to JSON without errors
- **SC-007**: All result types successfully convert to tabular format without errors
- **SC-008**: All CLI commands work with table and JSON output formats
- **SC-009**: All methods raise appropriate errors for missing tables with clear error messages
- **SC-010**: Event breakdown provides clear error messages listing specific missing columns when required columns are absent

## Assumptions

- Tables are stored in a local analytical database (not remote/network)
- Event tables follow a consistent schema with columns for event name, event time, and user identifier
- JSON properties are stored in a dedicated column named "properties"
- Performance targets assume typical analytical workloads (not streaming/real-time)
- Users have read access to all tables they attempt to introspect
