# Implementation Plan: Parallel Profile Fetching

**Branch**: `019-parallel-profile-fetch` | **Date**: 2026-01-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/019-parallel-profile-fetch/spec.md`

## Summary

Add parallel profile fetching capability using page-index parallelism (up to 5x speedup for large profile exports). Unlike events (date-based chunking), profiles use pagination where page 0 returns `total`, `page_size`, and `session_id` for subsequent parallel page fetches. Implements producer-consumer pattern with single writer thread to handle DuckDB's single-writer constraint.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: concurrent.futures (stdlib), threading (stdlib), queue (stdlib) - no new dependencies
**Storage**: DuckDB (existing StorageEngine)
**Testing**: pytest, pytest-cov
**Target Platform**: Linux/macOS/Windows (cross-platform)
**Project Type**: single (existing Python library + CLI)
**Performance Goals**: ~5x speedup for profile exports with 5+ pages
**Constraints**: Max 5 concurrent workers (Engage API limit), 60 queries/hour (hourly rate limit)
**Scale/Scope**: Supports profile sets up to 60,000 profiles before rate limiting

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | PASS | Python API gets `parallel=True` parameter first; CLI wraps it |
| II. Agent-Native Design | PASS | No interactive prompts; structured `ParallelProfileFetchResult` output |
| III. Context Window Efficiency | PASS | Data fetched once, stored locally in DuckDB for repeated queries |
| IV. Two Data Paths | PASS | Enhances fetch-to-local path; live queries unaffected |
| V. Explicit Over Implicit | PASS | `parallel=True` is explicit opt-in; preserves existing behavior |
| VI. Unix Philosophy | PASS | JSON output, exit codes, progress to stderr |
| VII. Secure by Default | PASS | Uses existing credential handling; no new secrets exposure |

**Technology Stack Compliance**:
- Python 3.11+ with type hints: COMPLIANT
- Typer for CLI: COMPLIANT (extends existing `mp fetch profiles` command)
- Rich for output: COMPLIANT (progress bar)
- DuckDB for storage: COMPLIANT
- No new dependencies required

## Project Structure

### Documentation (this feature)

```text
specs/019-parallel-profile-fetch/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (internal API contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── types.py                              # Add ProfileBatchProgress, ParallelProfileFetchResult
├── __init__.py                           # Export new types
├── workspace.py                          # Add parallel, max_workers params to fetch_profiles
├── _internal/
│   ├── api_client.py                     # Add query_engage_page method
│   └── services/
│       ├── fetcher.py                    # Add parallel delegation
│       └── parallel_profile_fetcher.py   # NEW: ParallelProfileFetcherService
└── cli/
    └── commands/
        └── fetch.py                      # Add --parallel, --workers flags

tests/
├── unit/
│   ├── test_types.py                     # Test ProfileBatchProgress, ParallelProfileFetchResult
│   ├── test_api_client.py                # Test query_engage_page
│   ├── test_parallel_profile_fetcher.py  # NEW: Unit tests for parallel fetcher
│   ├── test_fetcher_service.py           # Test parallel delegation
│   └── test_workspace.py                 # Test parallel fetch via workspace
└── integration/
    ├── test_parallel_profile_fetcher.py  # NEW: Integration tests with real DuckDB
    └── cli/
        └── test_fetch_commands.py        # Test CLI --parallel flag
```

**Structure Decision**: Extends existing single-project structure. New file `parallel_profile_fetcher.py` follows the pattern of existing `parallel_fetcher.py` for events.

## Complexity Tracking

> No violations - implementation follows existing patterns from Phase 017 parallel event export.

## Reusable Components

The following components from Phase 017 (parallel event export) can be reused:

| Component | Location | Reuse Strategy |
|-----------|----------|----------------|
| `RateLimiter` | `_internal/rate_limiter.py` | Use directly (unchanged) |
| Producer-consumer pattern | `parallel_fetcher.py` | Copy pattern, adapt for pages |
| `_transform_profile()` | `fetcher.py` | Use directly (already exists) |
| Progress callback pattern | `parallel_fetcher.py` | Adapt: page_index instead of date |

## Key Implementation Decisions

1. **Default workers = 5**: Engage API allows max 5 concurrent queries (vs 10 for Export API)
2. **Session ID handling**: Page 0 must be fetched first to obtain session_id for subsequent pages
3. **Page-based chunking**: Unlike events (date ranges), profiles use page indices
4. **Rate limit warnings**: Warn when pages > 60 (exceeds hourly quota)
5. **Return type union**: `fetch_profiles()` returns `FetchResult | ParallelProfileFetchResult`
