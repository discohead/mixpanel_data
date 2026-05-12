# Research: Streaming API

**Feature**: 011-streaming-api
**Date**: 2024-12-24

## Overview

This research documents the findings and decisions for implementing streaming API capability in `mixpanel_data`.

## Research Tasks

### 1. Existing Iterator Infrastructure

**Question**: Can we reuse existing API client iterators for streaming?

**Finding**: Yes. The `MixpanelAPIClient` class already has:
- `export_events()` → Returns `Iterator[dict[str, Any]]` (line 446-582 in api_client.py)
- `export_profiles()` → Returns `Iterator[dict[str, Any]]` (line 584-640 in api_client.py)

Both methods already stream data line-by-line from Mixpanel's JSONL export endpoints without buffering the entire response in memory.

**Decision**: Reuse these existing iterators. No modifications needed to the API client.

**Alternatives Considered**:
- Create new streaming-specific API methods: Rejected (would duplicate logic)
- Modify FetcherService to optionally skip storage: Rejected (muddies service responsibility)

---

### 2. Transformation Function Reusability

**Question**: Can we reuse existing transformation functions outside FetcherService?

**Finding**: Yes. The transformation functions are module-level functions in `fetcher.py`:
- `_transform_event(event: dict[str, Any]) -> dict[str, Any]` (line 24-57)
- `_transform_profile(profile: dict[str, Any]) -> dict[str, Any]` (line 60-81)

These are pure functions with no side effects or dependencies on FetcherService state.

**Decision**: Import and reuse these functions directly in Workspace streaming methods.

**Alternatives Considered**:
- Move functions to a shared module: Not needed (import from fetcher.py works fine)
- Duplicate transformation logic: Rejected (DRY violation)

---

### 3. CLI Output to Stdout

**Question**: How should CLI handle JSONL output while keeping progress on stderr?

**Finding**: The existing CLI uses:
- `rich.console.Console()` for stdout (via `console` in utils.py)
- `rich.console.Console(stderr=True)` for errors (via `err_console` in utils.py)

For streaming, we need raw JSON output (not Rich-formatted) to stdout.

**Decision**: Use `print()` or `sys.stdout.write()` for JSONL data output. Use `err_console` for progress/status. This aligns with Constitution Principle II (Agent-Native Design) and VI (Unix Philosophy).

**Alternatives Considered**:
- Use Rich console for JSONL: Rejected (adds formatting, breaks piping)
- Disable Rich entirely in streaming mode: Not needed (just bypass for data output)

---

### 4. Datetime Serialization in JSONL

**Question**: How should datetime objects be serialized in JSONL output?

**Finding**: Normalized events contain `event_time` as a Python `datetime` object. JSON doesn't support datetime natively.

**Decision**: Use ISO 8601 format via `json.dumps(event, default=str)` which handles datetime automatically. This produces `"2024-01-01T12:00:00+00:00"` format.

**Alternatives Considered**:
- Unix timestamps: Rejected (less human-readable, harder to debug)
- Custom JSON encoder: Overkill for this use case
- Raw mode only: Rejected (normalized format is more useful for most users)

---

### 5. Optional Table Name Argument

**Question**: How should Typer handle optional positional arguments when `--stdout` is set?

**Finding**: Typer supports `Optional[str]` with default `None` for arguments. The table name can be made optional by changing:
```python
name: Annotated[str, typer.Argument(...)] = "events"
```
to:
```python
name: Annotated[str | None, typer.Argument(...)] = None
```

When `--stdout` is set and `name` is `None`, streaming proceeds without storage. When `--stdout` is not set and `name` is `None`, default to `"events"` or `"profiles"`.

**Decision**: Make table name `Optional[str]` with logic:
- If `--stdout`: ignore table name entirely
- If not `--stdout` and name is None: use default ("events" or "profiles")
- If not `--stdout` and name provided: use provided name

**Alternatives Considered**:
- Separate `mp stream` command: Rejected (more commands to learn, less discoverable)
- Require table name always: Rejected (confusing when streaming)

---

## Summary of Decisions

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Iterator source | Reuse `MixpanelAPIClient` iterators | Already streaming, no buffering |
| Transformation | Import from `fetcher.py` | DRY, pure functions |
| JSONL output | `print()` to stdout | Clean for piping, no Rich formatting |
| Datetime format | ISO 8601 via `default=str` | Human-readable, standard format |
| Table name | Optional with `--stdout` | Natural UX, no forced argument |

## No Outstanding Clarifications

All technical questions resolved. Ready for Phase 1 design.
