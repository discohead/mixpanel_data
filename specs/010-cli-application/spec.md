# Feature Specification: CLI Application

**Feature Branch**: `010-cli-application`
**Created**: 2025-12-23
**Status**: Draft
**Input**: Phase 010 CLI Application - Implement the mp command-line interface that wraps the Workspace facade with 31 commands across 4 groups: auth (list, add, remove, switch, show, test), fetch (events, profiles), query (sql, segmentation, funnel, retention, jql, event-counts, property-counts, activity-feed, insights, frequency, segmentation-numeric, segmentation-sum, segmentation-average), and inspect (events, properties, values, funnels, cohorts, top-events, info, tables, schema, drop). Supports multiple output formats (json, table, csv, jsonl, plain), global options (--account, --format, --quiet, --verbose), and structured exit codes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure Account Credentials (Priority: P1)

A developer setting up the CLI for the first time needs to securely store their Mixpanel service account credentials so they can authenticate with the Mixpanel API without exposing secrets in their command history or environment.

**Why this priority**: Without credentials, no other CLI functionality works. This is the foundational requirement that gates all other features.

**Independent Test**: Can be fully tested by adding an account, listing accounts to verify it exists, and removing it. Delivers value by enabling all subsequent CLI operations.

**Acceptance Scenarios**:

1. **Given** no accounts configured, **When** user runs `mp auth add` with valid credentials, **Then** the account is stored securely and becomes the default account
2. **Given** one or more accounts configured, **When** user runs `mp auth list`, **Then** all accounts are displayed with their project IDs and regions, with the default account clearly marked
3. **Given** multiple accounts configured, **When** user runs `mp auth switch <account>`, **Then** that account becomes the new default for subsequent commands
4. **Given** an account exists, **When** user runs `mp auth test`, **Then** credentials are validated against the Mixpanel API and success/failure is reported
5. **Given** an account exists, **When** user runs `mp auth remove <account>`, **Then** the account is removed after confirmation (or immediately with `--force`)

---

### User Story 2 - Fetch and Store Events Locally (Priority: P1)

A data analyst needs to fetch Mixpanel events for a date range and store them in a local database so they can perform repeated SQL queries without consuming API rate limits or their AI agent's context window with raw API responses.

**Why this priority**: Event fetching is the core value proposition—enabling local SQL analysis. This is the primary use case the library was designed for.

**Independent Test**: Can be fully tested by fetching events for a short date range and then running a SQL query against them. Delivers value by enabling local data analysis.

**Acceptance Scenarios**:

1. **Given** valid credentials, **When** user runs `mp fetch events --from 2024-01-01 --to 2024-01-07`, **Then** events are downloaded and stored in a table called "events" with progress feedback
2. **Given** valid credentials, **When** user runs `mp fetch events --name custom_table --from 2024-01-01 --to 2024-01-07`, **Then** events are stored in the specified table name
3. **Given** valid credentials, **When** user runs `mp fetch events --from 2024-01-01 --to 2024-01-07 --events "Signup,Purchase"`, **Then** only the specified event types are fetched
4. **Given** a table already exists with that name, **When** user runs `mp fetch events` without `--replace`, **Then** an error is shown explaining the table exists
5. **Given** credentials are invalid or expired, **When** user runs `mp fetch events`, **Then** a clear authentication error is displayed with exit code 2

---

### User Story 3 - Query Local Data with SQL (Priority: P1)

An AI coding agent needs to execute SQL queries against locally stored Mixpanel data to answer analytics questions without making additional API calls, preserving context window for reasoning.

**Why this priority**: SQL querying is the payoff for local storage—this is how users extract value from fetched data.

**Independent Test**: Can be fully tested by running a SQL query against any existing table. Delivers value by enabling flexible data analysis.

**Acceptance Scenarios**:

1. **Given** events stored locally, **When** user runs `mp query sql "SELECT COUNT(*) FROM events"`, **Then** the query result is displayed in the requested format
2. **Given** events stored locally, **When** user runs `mp query sql "SELECT event, COUNT(*) FROM events GROUP BY event" --format table`, **Then** results are displayed as a formatted table
3. **Given** invalid SQL syntax, **When** user runs `mp query sql`, **Then** a clear error message is displayed with exit code 3
4. **Given** events stored locally, **When** user runs `mp query sql --scalar "SELECT COUNT(*) FROM events"`, **Then** only the single value is output (no column headers or formatting)
5. **Given** a non-existent table referenced, **When** user runs `mp query sql`, **Then** a table-not-found error is displayed with exit code 4

---

### User Story 4 - Run Live Analytics Queries (Priority: P2)

A data analyst needs to run segmentation, funnel, and retention queries directly against the Mixpanel API to get real-time analytics without fetching all the underlying event data.

**Why this priority**: Live queries complement local analysis by providing real-time aggregations that would be expensive to compute locally.

**Independent Test**: Can be fully tested by running a segmentation query for a specific event. Delivers value by providing real-time analytics insights.

**Acceptance Scenarios**:

1. **Given** valid credentials, **When** user runs `mp query segmentation --event "Signup" --from 2024-01-01 --to 2024-01-31`, **Then** time-series data is returned showing signup counts by day
2. **Given** a saved funnel exists, **When** user runs `mp query funnel --id <funnel_id> --from 2024-01-01 --to 2024-01-31`, **Then** conversion data is displayed for each funnel step
3. **Given** valid credentials, **When** user runs `mp query retention --born "Signup" --return "Purchase" --from 2024-01-01 --to 2024-01-31`, **Then** cohort retention data is displayed
4. **Given** valid credentials, **When** user runs `mp query jql --script "function main() { ... }"`, **Then** the JQL script is executed and results returned
5. **Given** rate limits are exceeded, **When** user runs any live query, **Then** a rate limit error is displayed with exit code 5

---

### User Story 5 - Discover Schema and Metadata (Priority: P2)

A developer new to a Mixpanel project needs to discover what events, properties, funnels, and cohorts are available so they can construct meaningful queries.

**Why this priority**: Discovery enables informed query construction—users need to know what data exists before they can query it effectively.

**Independent Test**: Can be fully tested by listing events and properties for a project. Delivers value by revealing the data model.

**Acceptance Scenarios**:

1. **Given** valid credentials, **When** user runs `mp inspect events`, **Then** all event names in the project are listed alphabetically
2. **Given** valid credentials, **When** user runs `mp inspect properties --event "Signup"`, **Then** all properties for that event are listed
3. **Given** valid credentials, **When** user runs `mp inspect values --property "country"`, **Then** sample values for that property are shown
4. **Given** valid credentials, **When** user runs `mp inspect funnels`, **Then** all saved funnels are listed with their IDs and names
5. **Given** valid credentials, **When** user runs `mp inspect cohorts`, **Then** all saved cohorts are listed with their IDs, names, and sizes

---

### User Story 6 - Inspect Local Database State (Priority: P2)

A developer needs to understand what data is stored locally—which tables exist, their schemas, row counts, and when they were fetched—so they can manage their local data workspace.

**Why this priority**: Local introspection enables data management and helps users understand what's available for SQL queries.

**Independent Test**: Can be fully tested by running `mp inspect info` on a workspace with tables. Delivers value by providing workspace visibility.

**Acceptance Scenarios**:

1. **Given** a workspace with tables, **When** user runs `mp inspect info`, **Then** workspace summary is displayed including path, project ID, tables, and total size
2. **Given** a workspace with tables, **When** user runs `mp inspect tables`, **Then** all tables are listed with their row counts and fetch timestamps
3. **Given** a table exists, **When** user runs `mp inspect schema --table events`, **Then** column names, types, and constraints are displayed
4. **Given** a table exists, **When** user runs `mp inspect drop --table events`, **Then** the table is removed after confirmation (or immediately with `--force`)
5. **Given** an empty workspace, **When** user runs `mp inspect tables`, **Then** a message indicates no tables exist

---

### User Story 7 - Fetch User Profiles (Priority: P3)

A developer needs to fetch user profile data to analyze user attributes and segment their user base locally.

**Why this priority**: Profile fetching extends the local analysis capability to user data, complementing event analysis.

**Independent Test**: Can be fully tested by fetching profiles and running a SQL query against them. Delivers value by enabling user-level analysis.

**Acceptance Scenarios**:

1. **Given** valid credentials, **When** user runs `mp fetch profiles`, **Then** user profiles are downloaded and stored in a table called "profiles" with progress feedback
2. **Given** valid credentials, **When** user runs `mp fetch profiles --name vip_users --where "$properties.plan == 'premium'"`, **Then** only matching profiles are fetched
3. **Given** profiles are stored, **When** user runs `mp query sql "SELECT COUNT(*) FROM profiles"`, **Then** the profile count is returned

---

### User Story 8 - Control Output Format (Priority: P3)

A developer integrating the CLI into scripts or pipelines needs to control the output format to match their toolchain's requirements (JSON for parsing, table for human reading, CSV for spreadsheets).

**Why this priority**: Output flexibility enables diverse integration scenarios but is not required for basic functionality.

**Independent Test**: Can be fully tested by running the same command with different `--format` options. Delivers value by enabling tool integration.

**Acceptance Scenarios**:

1. **Given** any command producing output, **When** user specifies `--format json`, **Then** output is valid JSON that can be parsed programmatically
2. **Given** any command producing output, **When** user specifies `--format table`, **Then** output is a human-readable formatted table
3. **Given** any command producing output, **When** user specifies `--format csv`, **Then** output is valid CSV with headers
4. **Given** any command producing output, **When** user specifies `--format jsonl`, **Then** output is newline-delimited JSON (one object per line)
5. **Given** streaming output like event fetching, **When** user specifies `--format plain`, **Then** minimal output suitable for log parsing is produced

---

### User Story 9 - Use Different Accounts Per-Command (Priority: P3)

A developer working with multiple Mixpanel projects needs to specify which account to use for a particular command without changing the default account.

**Why this priority**: Multi-account support is important for users with multiple projects but most users work with a single project.

**Independent Test**: Can be fully tested by running a command with `--account <name>` for a non-default account. Delivers value by enabling multi-project workflows.

**Acceptance Scenarios**:

1. **Given** multiple accounts configured, **When** user runs `mp --account staging inspect events`, **Then** the command uses the "staging" account credentials
2. **Given** a non-existent account name, **When** user runs `mp --account unknown inspect events`, **Then** an error is displayed listing available accounts

---

### Edge Cases

- What happens when the user interrupts a long-running fetch with Ctrl+C? The CLI should exit gracefully with code 130 and partial data should not corrupt the database.
- How does the CLI handle network timeouts during API calls? Clear timeout errors should be displayed with suggestions to retry.
- What happens when the workspace database file is locked by another process? A clear error should explain the lock and suggest solutions.
- What happens when disk space runs out during a fetch? The operation should fail gracefully with a clear error message.
- How does the CLI handle very large result sets that exceed terminal buffer? Output should stream incrementally rather than buffering everything in memory.

## Requirements *(mandatory)*

### Functional Requirements

#### Authentication Group (6 commands)

- **FR-001**: CLI MUST provide `mp auth list` to display all configured accounts with project IDs, regions, and default marker
- **FR-002**: CLI MUST provide `mp auth add` to interactively or non-interactively add new account credentials
- **FR-003**: CLI MUST provide `mp auth remove <name>` to remove an account with confirmation (bypassable via `--force`)
- **FR-004**: CLI MUST provide `mp auth switch <name>` to change the default account
- **FR-005**: CLI MUST provide `mp auth show <name>` to display account details (with secret redacted)
- **FR-006**: CLI MUST provide `mp auth test` to validate credentials against the Mixpanel API

#### Fetch Group (2 commands)

- **FR-007**: CLI MUST provide `mp fetch events` with required `--from` and `--to` date options, optional `--name`, `--events`, `--where`, and `--replace` options
- **FR-008**: CLI MUST provide `mp fetch profiles` with optional `--name`, `--where`, and `--replace` options
- **FR-009**: CLI MUST display progress feedback during fetch operations (suppressible via `--quiet`)
- **FR-010**: CLI MUST fail with appropriate error if target table exists and `--replace` not specified

#### Query Group (14 commands)

- **FR-011**: CLI MUST provide `mp query sql <query>` to execute SQL against local database with optional `--scalar` for single-value output
- **FR-012**: CLI MUST provide `mp query segmentation` for time-series event analysis with `--event`, `--from`, `--to`, optional `--on`, `--unit`, `--where`
- **FR-013**: CLI MUST provide `mp query funnel` for conversion analysis with `--id`, `--from`, `--to`, optional `--unit`, `--on`
- **FR-014**: CLI MUST provide `mp query retention` for cohort retention with `--born`, `--return`, `--from`, `--to`, optional additional parameters
- **FR-015**: CLI MUST provide `mp query jql` for custom JQL script execution with `--script` or `--file`
- **FR-016**: CLI MUST provide `mp query event-counts` for multi-event time series
- **FR-017**: CLI MUST provide `mp query property-counts` for property breakdown time series
- **FR-018**: CLI MUST provide `mp query activity-feed` to query user event history by distinct IDs
- **FR-019**: CLI MUST provide `mp query insights` to query saved Insights reports by bookmark ID
- **FR-020**: CLI MUST provide `mp query frequency` for event frequency distribution analysis
- **FR-021**: CLI MUST provide `mp query segmentation-numeric` for numeric property bucketing
- **FR-022**: CLI MUST provide `mp query segmentation-sum` for numeric property sum aggregation
- **FR-023**: CLI MUST provide `mp query segmentation-average` for numeric property average aggregation

#### Inspect Group (10 commands)

- **FR-024**: CLI MUST provide `mp inspect events` to list all event names in the project
- **FR-025**: CLI MUST provide `mp inspect properties --event <name>` to list properties for an event
- **FR-026**: CLI MUST provide `mp inspect values --property <name>` to show sample property values
- **FR-027**: CLI MUST provide `mp inspect funnels` to list saved funnels with IDs and names
- **FR-028**: CLI MUST provide `mp inspect cohorts` to list saved cohorts with IDs, names, and sizes
- **FR-029**: CLI MUST provide `mp inspect top-events` to show today's most active events
- **FR-030**: CLI MUST provide `mp inspect info` to display workspace summary (path, project, tables, size)
- **FR-031**: CLI MUST provide `mp inspect tables` to list local tables with row counts and fetch times
- **FR-032**: CLI MUST provide `mp inspect schema --table <name>` to display table column definitions
- **FR-033**: CLI MUST provide `mp inspect drop --table <name>` to remove a table with confirmation

#### Global Options

- **FR-034**: CLI MUST support `--account <name>` global option to override the default account for any command
- **FR-035**: CLI MUST support `--quiet` global option to suppress progress output (data still goes to stdout)
- **FR-036**: CLI MUST support `--verbose` global option to show debug information

#### Per-Command Options

- **FR-037**: CLI MUST support `--format <format>` per-command option with values: json (default), table, csv, jsonl, plain

#### Exit Codes

- **FR-038**: CLI MUST exit with code 0 on success
- **FR-039**: CLI MUST exit with code 1 on general errors
- **FR-040**: CLI MUST exit with code 2 on authentication errors
- **FR-041**: CLI MUST exit with code 3 on invalid arguments
- **FR-042**: CLI MUST exit with code 4 when a requested resource is not found
- **FR-043**: CLI MUST exit with code 5 on rate limit errors
- **FR-044**: CLI MUST exit with code 130 on user interruption (Ctrl+C)

#### Output Behavior

- **FR-045**: CLI MUST write data output to stdout and progress/status messages to stderr
- **FR-046**: CLI MUST produce valid, parseable output for the selected format (no mixed content)
- **FR-047**: CLI MUST redact secrets in all output (auth show, error messages, verbose logs)

### Key Entities

- **Account**: A named credential configuration containing service account username, secret, project ID, and region
- **Workspace**: A local database containing fetched Mixpanel data, associated with a directory path and project
- **Table**: A collection of fetched events or profiles stored locally, with metadata about when and how it was fetched
- **Event**: A tracked user action from Mixpanel with timestamp, properties, and user identifier
- **Profile**: A user record from Mixpanel with properties describing the user

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 31 commands are functional and documented in built-in help (`mp --help`, `mp <group> --help`, `mp <group> <command> --help`)
- **SC-002**: Users can complete the full workflow (configure account, fetch data, run SQL query) in under 5 minutes on first use
- **SC-003**: JSON output from any command is valid JSON parseable by standard tools (jq, Python json module)
- **SC-004**: Exit codes are consistent across all commands, enabling reliable scripting (e.g., `mp auth test && mp fetch events ...`)
- **SC-005**: Progress feedback during fetch operations updates at least every 2 seconds, providing meaningful status
- **SC-006**: Error messages clearly identify the problem, suggest remediation, and include relevant context (account name, table name, etc.)
- **SC-007**: The CLI handles interruption (Ctrl+C) gracefully without corrupting local data
- **SC-008**: All commands complete within acceptable time bounds: auth operations < 2 seconds, inspect operations < 5 seconds, queries display first results within 3 seconds
- **SC-009**: The CLI works correctly when invoked from scripts, pipelines, and AI coding agents (no interactive prompts unless `--interactive` specified)

## Assumptions

- The existing Workspace facade correctly implements all underlying functionality; the CLI is a thin wrapper
- Users have network access to Mixpanel API endpoints for their configured region
- The local filesystem supports the database storage requirements
- Service account credentials are obtained separately from the Mixpanel dashboard
- Users understand basic command-line interface conventions (options, arguments, piping)
- JSON is the appropriate default output format for programmatic consumers (especially AI agents)

## Dependencies

- Workspace facade (Phase 009) - provides all core functionality
- ConfigManager (Phase 001) - provides credential storage and retrieval
- All result types with `.to_dict()` method - enables JSON serialization

## Out of Scope

- GUI or web-based interface
- Credential creation/provisioning in Mixpanel (users must create service accounts manually)
- Real-time streaming of events (beyond what Mixpanel API provides)
- Data transformation or ETL beyond what the Workspace provides
- Scheduled/automated fetching (users can use cron or similar tools)
- Multi-workspace management from a single command
