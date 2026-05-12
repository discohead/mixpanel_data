# Implementation Plan: Parallel Export Performance

**Branch**: `017-parallel-export` | **Date**: 2026-01-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/017-parallel-export/spec.md`

## Summary

Add parallel fetching capability to `export_events` operations to improve performance by splitting date ranges into 7-day chunks and processing them concurrently using `ThreadPoolExecutor`. The feature is opt-in (`parallel=True`) to maintain backward compatibility, uses a producer-consumer pattern with a single-writer thread for DuckDB storage, and targets up to 10x speedup for I/O-bound exports.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: concurrent.futures (stdlib), threading (stdlib), queue (stdlib) - no new external dependencies
**Storage**: DuckDB (single-writer constraint requires queue-based serialization)
**Testing**: pytest, Hypothesis (property-based testing), mutmut (mutation testing)
**Target Platform**: Linux/macOS/Windows (cross-platform CLI tool)
**Project Type**: Single Python package (`mixpanel_data`)
**Performance Goals**: Up to 10x faster exports for 30+ day date ranges
**Constraints**: Stay under 20% of Mixpanel's 100 concurrent request limit (~10-15 workers)
**Scale/Scope**: Export operations with date ranges from 1 day to 100+ days

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Library-First** | ✅ PASS | New `parallel=True` parameter added to `Workspace.fetch_events()` library method; CLI wraps library |
| **II. Agent-Native Design** | ✅ PASS | No interactive prompts; progress via callbacks; exit codes unchanged |
| **III. Context Window Efficiency** | ✅ PASS | Faster fetches reduce time-to-analysis; data stored locally |
| **IV. Two Data Paths** | ✅ PASS | Enhances local analysis path (fetch → DuckDB → SQL); live queries unaffected |
| **V. Explicit Over Implicit** | ✅ PASS | Parallel mode is opt-in; default behavior unchanged; partial failures explicit |
| **VI. Unix Philosophy** | ✅ PASS | Composes with existing tools; progress to stderr; data to stdout |
| **VII. Secure by Default** | ✅ PASS | No credentials in logs; reuses existing auth patterns |
| **Technology Stack** | ✅ PASS | Uses stdlib only (concurrent.futures, threading, queue); no new dependencies |
| **Quality Gates** | ✅ PASS | TDD approach; 90%+ coverage; mypy --strict; full docstrings |

**Gate Result**: PASSED - No violations. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/017-parallel-export/
├── plan.md              # This file
├── research.md          # Phase 0 output - threading patterns research
├── data-model.md        # Phase 1 output - new types
├── quickstart.md        # Phase 1 output - usage examples
└── checklists/
    └── requirements.md  # Spec validation checklist
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── types.py                                    # Add BatchProgress, BatchResult, ParallelFetchResult
├── _internal/
│   ├── rate_limiter.py                         # NEW: RateLimiter with semaphore
│   ├── date_utils.py                           # NEW: split_date_range()
│   └── services/
│       ├── fetcher.py                          # Add parallel param, delegate to parallel_fetcher
│       └── parallel_fetcher.py                 # NEW: ParallelFetcherService
├── workspace.py                                # Add parallel params to fetch_events()
└── cli/commands/
    └── fetch.py                                # Add --parallel, --workers flags

tests/
├── unit/
│   ├── test_types_parallel.py                  # NEW: BatchProgress, BatchResult, ParallelFetchResult
│   ├── test_rate_limiter.py                    # NEW: RateLimiter tests
│   ├── test_date_utils.py                      # NEW: split_date_range tests
│   ├── test_date_utils_pbt.py                  # NEW: Property-based date tests
│   ├── test_parallel_fetcher.py                # NEW: ParallelFetcherService unit tests
│   └── test_fetcher_service.py                 # Extend with parallel delegation tests
├── integration/
│   └── test_parallel_fetcher.py                # NEW: End-to-end with mocked API
└── cli/
    └── test_fetch_commands.py                  # Extend with --parallel, --workers tests
```

**Structure Decision**: Single project structure (existing). All new code follows established patterns in `src/mixpanel_data/` with tests in `tests/`.

## Complexity Tracking

> No violations identified. All decisions align with constitution principles.

| Decision | Justification |
|----------|---------------|
| ThreadPoolExecutor over async | Codebase is 100% synchronous; async would require extensive refactoring |
| Fixed 7-day chunks over adaptive | Simple, predictable, debuggable; optimization can come later |
| Single-writer queue pattern | Required by DuckDB's single-writer constraint |
| 10 default workers over 100 | Conservative approach using ~10% of limit for safety margin |
