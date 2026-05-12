# Feature Specification: JQ Filter Support for CLI Output

**Feature Branch**: `016-jq-filter-support`
**Created**: 2026-01-04
**Status**: Draft
**Input**: User description: "Add --jq option to CLI commands for client-side JSON filtering using jq syntax, enabling power users to filter and transform JSON output without piping to external tools"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Filter JSON Output with jq Expression (Priority: P1)

As a power user, I want to filter and transform JSON output from CLI commands using jq syntax so that I can extract exactly the data I need without piping to external tools.

**Why this priority**: This is the core functionality that delivers the primary value proposition—native jq filtering without external dependencies.

**Independent Test**: Can be fully tested by running any command with `--format json --jq '<expression>'` and verifying the output matches the expected filtered result.

**Acceptance Scenarios**:

1. **Given** a command returns JSON data, **When** I add `--jq '.field'` to extract a single field, **Then** only that field's value is returned
2. **Given** a command returns a JSON array, **When** I add `--jq '.[] | select(.count > 50)'` to filter items, **Then** only items matching the condition are returned
3. **Given** a command returns JSON data, **When** I add `--jq 'length'` to count items, **Then** the count is returned as a number

---

### User Story 2 - Receive Clear Error for Invalid jq Syntax (Priority: P2)

As a user who makes typos or is learning jq, I want to receive clear error messages when my jq filter has invalid syntax so that I can quickly identify and fix the problem.

**Why this priority**: Good error handling is essential for usability but depends on the core filtering functionality existing first.

**Independent Test**: Can be tested by providing malformed jq expressions and verifying error messages are clear and actionable.

**Acceptance Scenarios**:

1. **Given** a valid command with JSON output, **When** I provide an incomplete jq expression like `.name |`, **Then** I receive a clear syntax error message
2. **Given** a valid command with JSON output, **When** I provide an invalid jq expression, **Then** the error message includes the word "jq" and describes the problem
3. **Given** an invalid jq expression, **When** the command exits, **Then** it uses a non-zero exit code indicating invalid arguments

---

### User Story 3 - Receive Error for Incompatible Format (Priority: P2)

As a user, I want to be informed when I attempt to use `--jq` with a non-JSON format so that I understand why my command failed and how to fix it.

**Why this priority**: Prevents user confusion when combining incompatible options; important for usability but secondary to core functionality.

**Independent Test**: Can be tested by combining `--jq` with `--format table` (or other non-JSON formats) and verifying the appropriate error.

**Acceptance Scenarios**:

1. **Given** a command with `--format table`, **When** I add `--jq '.[]'`, **Then** I receive an error stating jq requires JSON format
2. **Given** a command with `--format csv`, **When** I add `--jq '.[]'`, **Then** I receive an error stating jq requires JSON format
3. **Given** a command with `--format plain`, **When** I add `--jq '.[]'`, **Then** I receive an error stating jq requires JSON format

---

### User Story 4 - Handle jq Runtime Errors Gracefully (Priority: P3)

As a user, I want to receive helpful error messages when my jq filter fails at runtime (e.g., accessing a non-existent field or wrong data type) so that I can debug my query.

**Why this priority**: Runtime errors are less common than syntax errors but still important for a complete user experience.

**Independent Test**: Can be tested by running valid jq syntax against incompatible data structures.

**Acceptance Scenarios**:

1. **Given** a command returns a JSON object, **When** I apply a filter expecting an array like `.[0]`, **Then** I receive a runtime error message
2. **Given** a jq filter causes a runtime error, **When** the command exits, **Then** it uses a non-zero exit code indicating invalid arguments

---

### User Story 5 - Empty Results Handled Gracefully (Priority: P3)

As a user, I want to see empty results clearly represented when my jq filter matches no items so that I understand the filter worked but found nothing.

**Why this priority**: Edge case handling that improves usability but is not core functionality.

**Independent Test**: Can be tested by running filters that select non-existent items.

**Acceptance Scenarios**:

1. **Given** a command returns JSON data, **When** I apply a select filter that matches no items, **Then** an empty array `[]` is returned
2. **Given** a jq filter returns empty results, **When** the command completes, **Then** it exits with success (zero exit code)

---

### Edge Cases

- What happens when the JSON output is deeply nested and the jq filter navigates multiple levels?
- How does the system handle jq filters that produce multiple separate results (not wrapped in an array)?
- What happens when the jq filter returns a scalar value vs. an object vs. an array?
- How are special characters in jq expressions handled (quotes, backslashes)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: CLI MUST provide a `--jq` option on all commands that support `--format json` or `--format jsonl`
- **FR-002**: CLI MUST apply the jq filter expression to JSON output after formatting
- **FR-003**: CLI MUST pretty-print jq results as properly indented JSON
- **FR-004**: CLI MUST display a clear error message when jq filter syntax is invalid
- **FR-005**: CLI MUST display a clear error message when jq filter encounters a runtime error
- **FR-006**: CLI MUST reject `--jq` option when used with non-JSON formats (table, csv, plain) with a clear error message
- **FR-007**: CLI MUST exit with a specific error code for jq-related errors (syntax or runtime)
- **FR-008**: CLI MUST return an empty array `[]` when a jq filter produces no results
- **FR-009**: CLI MUST handle jq filters that produce single results (scalar, object, or array)
- **FR-010**: CLI MUST handle jq filters that produce multiple results by wrapping them in an array

### Key Entities

- **JQ Filter Expression**: A string containing valid jq syntax that transforms or filters JSON data
- **Filtered Result**: The JSON output after applying the jq filter, which may be a scalar, object, array, or empty array

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can filter JSON output without installing external tools (zero external dependencies for end users)
- **SC-002**: The `--jq` option works consistently across all major platforms (Windows, macOS, Linux)
- **SC-003**: Error messages for invalid jq syntax clearly indicate the problem and suggest how to fix it
- **SC-004**: All commands supporting `--format json` also support `--jq` (100% coverage)
- **SC-005**: Users can complete common filtering tasks (select, extract field, count) in a single command

## Assumptions

- Users are familiar with basic jq syntax or will refer to jq documentation
- The jq library used provides consistent behavior across platforms
- Performance overhead of jq filtering is negligible for typical output sizes
- Standard jq syntax is sufficient; custom jq functions and modules are not required
