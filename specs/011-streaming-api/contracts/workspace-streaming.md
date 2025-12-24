# Contract: Workspace Streaming Methods

**Feature**: 011-streaming-api
**Date**: 2024-12-24

## Overview

This document defines the API contract for streaming methods added to the `Workspace` class.

## Python Library API

### Workspace.stream_events()

```python
def stream_events(
    self,
    *,
    from_date: str,
    to_date: str,
    events: list[str] | None = None,
    where: str | None = None,
    raw: bool = False,
) -> Iterator[dict[str, Any]]:
    """Stream events directly from Mixpanel API without storing.

    Yields events one at a time as they are received from the API.
    No database files or tables are created.

    Args:
        from_date: Start date inclusive (YYYY-MM-DD format).
        to_date: End date inclusive (YYYY-MM-DD format).
        events: Optional list of event names to filter. If None, all events returned.
        where: Optional Mixpanel filter expression (e.g., 'properties["country"]=="US"').
        raw: If True, return events in raw Mixpanel API format.
             If False (default), return normalized format with datetime objects.

    Yields:
        dict[str, Any]: Event dictionaries in normalized or raw format.

    Raises:
        ConfigError: If API credentials are not available (e.g., opened with Workspace.open()).
        AuthenticationError: If credentials are invalid.
        RateLimitError: If rate limit exceeded after max retries.
        QueryError: If filter expression is invalid.

    Example:
        >>> ws = Workspace()
        >>> for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31"):
        ...     process(event)
        >>> ws.close()

        >>> # With raw format
        >>> for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31", raw=True):
        ...     legacy_system.ingest(event)
    """
```

### Workspace.stream_profiles()

```python
def stream_profiles(
    self,
    *,
    where: str | None = None,
    raw: bool = False,
) -> Iterator[dict[str, Any]]:
    """Stream user profiles directly from Mixpanel API without storing.

    Yields profiles one at a time as they are received from the API.
    No database files or tables are created.

    Args:
        where: Optional Mixpanel filter expression for profile properties.
        raw: If True, return profiles in raw Mixpanel API format.
             If False (default), return normalized format.

    Yields:
        dict[str, Any]: Profile dictionaries in normalized or raw format.

    Raises:
        ConfigError: If API credentials are not available.
        AuthenticationError: If credentials are invalid.
        RateLimitError: If rate limit exceeded after max retries.

    Example:
        >>> ws = Workspace()
        >>> for profile in ws.stream_profiles():
        ...     sync_to_crm(profile)
        >>> ws.close()

        >>> # Filter to premium users
        >>> for profile in ws.stream_profiles(where='properties["plan"]=="premium"'):
        ...     send_survey(profile)
    """
```

## CLI Interface

### mp fetch events (with streaming options)

```
mp fetch events [OPTIONS] [NAME]

Arguments:
  [NAME]    Table name for storing events. [default: events]
            Ignored when --stdout is set.

Options:
  --from TEXT           Start date (YYYY-MM-DD). [required]
  --to TEXT             End date (YYYY-MM-DD). [required]
  -e, --events TEXT     Comma-separated event filter.
  -w, --where TEXT      Mixpanel filter expression.
  --replace             Replace existing table.
  --no-progress         Hide progress bar.
  --stdout              Stream to stdout as JSONL instead of storing.
  --raw                 Output raw API format (only with --stdout).
  --format [json|table|csv|jsonl]
                        Output format. [default: json]
  --help                Show this message and exit.

Examples:
  # Stream events to stdout
  mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout

  # Stream with raw format, pipe to jq
  mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout --raw | jq '.event'

  # Stream to file
  mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout > events.jsonl

  # Filter and stream
  mp fetch events --from 2024-01-01 --to 2024-01-31 --events "Purchase,Signup" --stdout
```

### mp fetch profiles (with streaming options)

```
mp fetch profiles [OPTIONS] [NAME]

Arguments:
  [NAME]    Table name for storing profiles. [default: profiles]
            Ignored when --stdout is set.

Options:
  -w, --where TEXT      Mixpanel filter expression.
  --replace             Replace existing table.
  --no-progress         Hide progress bar.
  --stdout              Stream to stdout as JSONL instead of storing.
  --raw                 Output raw API format (only with --stdout).
  --format [json|table|csv|jsonl]
                        Output format. [default: json]
  --help                Show this message and exit.

Examples:
  # Stream all profiles
  mp fetch profiles --stdout

  # Stream premium users only
  mp fetch profiles --where 'properties["plan"]=="premium"' --stdout
```

## Output Formats

### JSONL (stdout mode)

Each line is a complete JSON object:

```jsonl
{"event_name":"PageView","event_time":"2024-01-01T12:00:00+00:00","distinct_id":"user1","insert_id":"abc","properties":{"page":"/home"}}
{"event_name":"Click","event_time":"2024-01-01T12:01:00+00:00","distinct_id":"user1","insert_id":"def","properties":{"button":"signup"}}
```

### Progress Output (stderr)

When `--stdout` is set, progress goes to stderr:

```
Streaming events... 1000 rows
Streaming events... 2000 rows
```

## Error Handling

| Error | Exit Code | Behavior |
|-------|-----------|----------|
| Invalid credentials | 2 | Error message to stderr, no data output |
| Invalid filter expression | 3 | Error message to stderr, no data output |
| Rate limit (after retries) | 5 | Error message to stderr, partial data may have been output |
| Network error | 1 | Error message to stderr, partial data may have been output |

## Backward Compatibility

- Default behavior (without `--stdout`) is unchanged
- `--raw` without `--stdout` is ignored (no effect on stored data format)
- All existing options continue to work as before
