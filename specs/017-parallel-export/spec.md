# Feature Specification: Parallel Export Performance

**Feature Branch**: `017-parallel-export`
**Created**: 2026-01-04
**Status**: Draft
**Input**: User description: "Add parallel fetching to export_events for improved performance by splitting date ranges into chunks and processing concurrently, enabling up to 10x faster exports while respecting Mixpanel rate limits"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Faster Large Date Range Exports (Priority: P1)

As a data analyst exporting months of event data, I want exports to complete faster so that I can iterate on my analysis without waiting hours for data.

Currently, exporting 90 days of event data can take hours because the system makes a single sequential request. With parallel export, the same operation should complete in a fraction of the time by fetching multiple date chunks simultaneously.

**Why this priority**: This is the core value proposition. Without faster exports, the feature provides no benefit. This directly impacts user productivity and is the primary reason for the feature.

**Independent Test**: Can be fully tested by exporting a 30+ day date range with parallel mode and measuring time vs sequential mode. Delivers immediate measurable value.

**Acceptance Scenarios**:

1. **Given** I have a 90-day date range to export, **When** I enable parallel export mode, **Then** the export completes significantly faster than sequential mode (target: up to 10x improvement for I/O-bound scenarios)
2. **Given** I am exporting data, **When** parallel mode is enabled, **Then** all data is retrieved completely and accurately (no missing or duplicate events)
3. **Given** I have an existing export workflow, **When** I don't explicitly enable parallel mode, **Then** the export behaves exactly as before (backward compatible)

---

### User Story 2 - Progress Visibility During Parallel Export (Priority: P2)

As a user running a long export, I want to see progress updates for each batch so that I know the export is working and can estimate completion time.

**Why this priority**: Progress visibility improves user experience during long operations but is not essential for the core functionality. Users can still export without it.

**Independent Test**: Can be tested by running a parallel export and verifying batch completion callbacks are received with accurate progress information.

**Acceptance Scenarios**:

1. **Given** I am running a parallel export, **When** a batch completes, **Then** I receive a progress update indicating which date range completed
2. **Given** I am running a parallel export via CLI, **When** batches complete, **Then** I see progress output showing batch completion status

---

### User Story 3 - Handling Partial Failures Gracefully (Priority: P2)

As a user exporting data, I want the system to continue even if some date ranges fail, so that I get as much data as possible and can retry only the failed portions.

**Why this priority**: Resilience to partial failures is important for large exports but secondary to core speed improvement. Equal priority with progress visibility as both enhance the user experience.

**Independent Test**: Can be tested by simulating network failures for specific date ranges and verifying successful batches are preserved.

**Acceptance Scenarios**:

1. **Given** I am running a parallel export, **When** one batch fails but others succeed, **Then** the successful data is preserved and I receive a report of which date ranges failed
2. **Given** some batches failed during export, **When** the export completes, **Then** I can see exactly which date ranges need to be retried
3. **Given** all batches fail, **When** the export completes, **Then** I receive a clear error indicating no data was retrieved

---

### User Story 4 - Configurable Concurrency Level (Priority: P3)

As an advanced user, I want to control the number of concurrent requests so that I can balance speed against rate limit concerns for my specific account.

**Why this priority**: Most users will be satisfied with sensible defaults. This is an advanced configuration option for power users.

**Independent Test**: Can be tested by running exports with different worker counts and verifying the concurrency is respected.

**Acceptance Scenarios**:

1. **Given** I want to use a specific concurrency level, **When** I set the worker count option, **Then** the export respects that limit
2. **Given** I don't specify a worker count, **When** I run a parallel export, **Then** a sensible default is used (10 workers)

---

### Edge Cases

- What happens when the date range is very small (1-7 days)? The system should handle this gracefully, potentially using sequential mode if parallelism provides no benefit.
- What happens if the user cancels mid-export? Partial data should be available if already written.
- What happens if Mixpanel rate limits are exceeded? The system should handle rate limit errors gracefully and report them as batch failures.
- What happens with overlapping or invalid date ranges? Validation should occur before export begins.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support an optional parallel export mode for events that is disabled by default (backward compatible)
- **FR-002**: System MUST split large date ranges into smaller chunks for parallel processing
- **FR-003**: System MUST respect Mixpanel's rate limits (staying safely under the 100 concurrent request limit)
- **FR-004**: System MUST provide batch completion callbacks for progress tracking
- **FR-005**: System MUST continue processing remaining batches when individual batches fail
- **FR-006**: System MUST report which date ranges failed so users can retry them
- **FR-007**: System MUST ensure all data is written correctly without gaps or duplicates
- **FR-008**: System MUST allow users to configure the number of concurrent workers
- **FR-009**: System MUST provide sensible default concurrency (10 workers)
- **FR-010**: CLI MUST support `--parallel` flag to enable parallel mode
- **FR-011**: CLI MUST support `--workers` option to configure concurrency
- **FR-012**: CLI MUST display batch progress during parallel exports

### Key Entities

- **BatchProgress**: Represents progress information for a single batch (date range, event count, status)
- **BatchResult**: Represents the outcome of fetching a single date range chunk (success/failure, event count, error info if failed)
- **ParallelFetchResult**: Aggregates results from all batches (total events, failed date ranges, success status)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users exporting 30+ days of data see at least 5x improvement in export time when using parallel mode
- **SC-002**: 100% of events are retrieved correctly with no data loss or duplication when using parallel mode
- **SC-003**: Existing workflows using sequential mode continue to work identically (zero breaking changes)
- **SC-004**: Users can identify and retry failed date ranges without re-exporting successful data
- **SC-005**: Batch progress updates are delivered within 1 second of batch completion
- **SC-006**: System stays under 20% of Mixpanel's rate limit capacity (using ~15-20 of 100 concurrent limit)

## Assumptions

- Users have valid Mixpanel credentials with export permissions
- Network latency is the primary bottleneck for export operations (I/O-bound workload)
- 7-day chunks provide a reasonable balance between parallelism and request overhead
- Default of 10 concurrent workers provides good speedup while staying safely under rate limits
- DuckDB storage can handle concurrent writes from multiple worker threads via a single-writer queue pattern
- This feature applies to events only; profile exports will be addressed separately

## Scope Boundaries

### In Scope
- Parallel fetching for event exports only
- Optional parallel mode (opt-in)
- Configurable concurrency
- Progress callbacks and CLI output
- Partial failure handling and retry information

### Out of Scope
- Parallel fetching for profile exports (future work)
- Automatic retry of failed batches (users can manually retry failed ranges)
- Adaptive chunk sizing based on data density
- Async/await refactoring of the codebase
