# Feature Specification: Parallel Profile Fetching

**Feature Branch**: `019-parallel-profile-fetch`
**Created**: 2026-01-05
**Status**: Draft
**Input**: User description: "Add parallel fetching capability to profile exports using page-index parallelism for up to 5x speedup"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Faster Profile Export for Large Datasets (Priority: P1)

As a data analyst working with large Mixpanel projects, I want to export user profiles significantly faster so that I can reduce wait times when analyzing user segments with tens of thousands of profiles.

**Why this priority**: This is the core value proposition. Without faster fetching, the feature provides no benefit. Large profile exports (10,000+ profiles) currently take several minutes due to sequential page fetching.

**Independent Test**: Can be fully tested by exporting a large profile set with parallel mode enabled and comparing completion time against sequential mode. Delivers immediate time savings.

**Acceptance Scenarios**:

1. **Given** a Mixpanel project with 25,000 profiles, **When** I fetch profiles with parallel mode enabled, **Then** the export completes in approximately 1/5th the time compared to sequential mode
2. **Given** a Mixpanel project with 5,000 profiles (5 pages), **When** I fetch profiles with parallel mode enabled, **Then** all 5 pages are fetched concurrently and stored correctly
3. **Given** parallel mode is enabled, **When** fetching completes, **Then** the stored data is identical to what sequential mode would produce (same profiles, same properties)

---

### User Story 2 - Progress Visibility During Parallel Fetch (Priority: P2)

As a user running a long-running profile export, I want to see real-time progress so that I know how much longer the export will take and can verify it's making progress.

**Why this priority**: Progress visibility is important for user experience but not essential for core functionality. Users can still benefit from faster exports without progress feedback.

**Independent Test**: Can be tested by running a multi-page parallel fetch and observing progress updates. Delivers confidence that the export is working.

**Acceptance Scenarios**:

1. **Given** a parallel profile fetch is running, **When** each page completes, **Then** I receive a progress update showing completed pages vs total pages
2. **Given** I'm using the CLI with parallel mode, **When** the fetch runs, **Then** I see a progress bar showing page completion progress
3. **Given** I'm using the Python API with parallel mode, **When** I provide a callback function, **Then** my callback is invoked for each completed page with progress details

---

### User Story 3 - Graceful Handling of Partial Failures (Priority: P3)

As a user exporting profiles, I want the system to handle page failures gracefully so that I don't lose all my data if one page fails due to a transient network error.

**Why this priority**: Failure handling improves reliability but most exports succeed completely. This is defensive functionality for edge cases.

**Independent Test**: Can be tested by simulating page failures during export and verifying partial data is preserved and failure information is reported.

**Acceptance Scenarios**:

1. **Given** a parallel fetch where 2 of 10 pages fail, **When** the fetch completes, **Then** the 8 successful pages are stored and I receive a report listing which pages failed
2. **Given** some pages failed during fetch, **When** I check the result, **Then** I can identify the specific page numbers that failed for potential retry
3. **Given** a page fails due to rate limiting, **When** the system retries, **Then** automatic exponential backoff is applied before retry

---

### User Story 4 - CLI Support for Parallel Mode (Priority: P2)

As a CLI user, I want command-line flags to enable parallel fetching so that I can use the faster export method from scripts and terminal sessions.

**Why this priority**: CLI is a primary interface for many users. This enables adoption through the command line alongside the Python API.

**Independent Test**: Can be tested by running the CLI with parallel flags and verifying the export completes faster with correct output.

**Acceptance Scenarios**:

1. **Given** I'm using the CLI, **When** I run `mp fetch profiles --parallel`, **Then** parallel mode is enabled for the profile export
2. **Given** I want to control concurrency, **When** I specify `--workers 3`, **Then** at most 3 pages are fetched concurrently
3. **Given** parallel mode completes with failures, **When** the CLI exits, **Then** I see a warning message and appropriate exit code indicating partial failure

---

### Edge Cases

- What happens when the profile set fits in a single page? System should work correctly without parallelism benefit (only 1 page to fetch)
- What happens when all pages fail? System reports complete failure with no partial data stored
- What happens when the hourly rate limit is approached? System warns users proactively before starting fetch
- How does the system handle concurrent write constraints? All writes are serialized to maintain data integrity
- What happens if the session expires mid-fetch? System fails gracefully with clear error message

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support a parallel mode option for profile fetching that enables concurrent page retrieval
- **FR-002**: System MUST fetch the first page sequentially to obtain total count and pagination metadata before parallel fetching
- **FR-003**: System MUST fetch remaining pages concurrently using a configurable number of workers
- **FR-004**: System MUST respect the Mixpanel Engage API's maximum concurrent query limit of 5 workers
- **FR-005**: System MUST serialize all database writes to maintain data integrity despite concurrent fetches
- **FR-006**: System MUST provide progress callbacks/updates during parallel fetch operations
- **FR-007**: System MUST track and report page-level success/failure status
- **FR-008**: System MUST preserve successfully fetched data even when some pages fail
- **FR-009**: System MUST report failed page indices to enable targeted retry
- **FR-010**: System MUST warn users when the number of pages exceeds 80% of the hourly rate limit (48+ pages of 60 queries/hour)
- **FR-011**: CLI MUST provide `--parallel` flag to enable parallel mode for profile fetching
- **FR-012**: CLI MUST provide `--workers` option to configure maximum concurrent fetch threads
- **FR-013**: System MUST cap workers to 5 (API limit) even if user requests more, with appropriate warning
- **FR-014**: Parallel mode MUST produce identical data output as sequential mode for the same query

### Key Entities

- **ProfileBatchProgress**: Represents the progress of a single page fetch, including page index, total pages, row count, success status, and any error message
- **ParallelProfileFetchResult**: Aggregated result of a parallel fetch operation, including total rows fetched, successful/failed page counts, failed page indices, duration, and completion timestamp

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Profile exports of 5+ pages complete in approximately 1/5th the time when parallel mode is enabled compared to sequential mode
- **SC-002**: System handles exports of up to 60,000 profiles (60 pages) within a single hour without hitting rate limits
- **SC-003**: 100% of successfully fetched pages are persisted correctly, even when other pages fail
- **SC-004**: Progress updates are delivered within 1 second of each page completing
- **SC-005**: Users are warned when their export will consume more than 80% of the hourly rate limit quota
- **SC-006**: Parallel mode maintains data integrity - output matches sequential mode exactly for identical queries

## Assumptions

- Users have valid Mixpanel credentials with access to the Engage API
- The Mixpanel Engage API rate limits remain at 5 concurrent queries and 60 queries per hour
- Users understand that very large profile sets (>60,000 profiles) may encounter rate limiting
- The existing rate limiter and retry logic will be reused for handling transient failures
- DuckDB's single-writer constraint requires write serialization (producer-consumer pattern)
