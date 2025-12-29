# Storage Engine

How mixpanel_data uses DuckDB for local data storage.

## Overview

The `StorageEngine` class wraps DuckDB to provide persistent local storage for fetched Mixpanel data. Understanding DuckDB's concurrency model helps avoid conflicts when running multiple `mp` commands.

## Storage Modes

Three storage modes are available:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Persistent** | Database file on disk (default) | Production use, data preservation |
| **Ephemeral** | Temp file deleted on close | Testing, one-off analysis |
| **In-Memory** | No file, RAM only | Quick scripts, no persistence needed |

### Mode Selection

```python
# Persistent (default) - stored at ~/.mp/data/{project_id}.db
ws = Workspace()

# Custom path
ws = Workspace(path="/path/to/my.db")

# Ephemeral - temp file, deleted on close
ws = Workspace(ephemeral=True)

# In-memory - no file at all
ws = Workspace(in_memory=True)
```

## DuckDB Concurrency Model

DuckDB uses a **single-writer, multiple-reader** concurrency model:

- **One write connection** can be active at a time per database file
- **Multiple read connections** can coexist with each other
- Read and write connections **cannot coexist** on the same file

This differs from client-server databases (PostgreSQL, MySQL) where a server process mediates all access.

### What This Means in Practice

| Scenario | Result |
|----------|--------|
| One `mp fetch` command | Works normally |
| Two `mp fetch` commands to same database | Second command gets `DatabaseLockedError` |
| `mp fetch` + `mp query` to same database | Query command gets `DatabaseLockedError` |
| Two `mp query` commands to same database | Both work (when no write lock is held) |
| Two `mp inspect` commands (API-only) | Both work (no database access) |

## Lock Conflicts

When a second process tries to open a database that's already locked for writing, DuckDB raises an error. mixpanel_data catches this and raises a `DatabaseLockedError`:

```
Database locked: /home/user/.mp/data/12345.db
Another mp command may be running. Try again shortly.
```

## Database Not Found

When opening a database in read-only mode, the file must already exist. If you run a read command (like `mp query` or `mp inspect tables`) before fetching any data, you'll get a `DatabaseNotFoundError`:

```
No data yet: /home/user/.mp/data/12345.db
Run 'mp fetch events' or 'mp fetch profiles' to create the database.
```

This is different from write mode, which creates the database file automatically.

### Common Causes

1. **Long-running fetch** — Large date ranges take time; other commands must wait
2. **Background processes** — A previous command didn't exit cleanly
3. **Multiple terminals** — Different shells running concurrent `mp` commands

### Resolution

1. **Wait** — Let the first operation complete
2. **Check for stuck processes** — `ps aux | grep mp` to find orphaned commands
3. **Use separate databases** — Specify different `--path` for concurrent work

## Lazy Storage Initialization

To avoid unnecessary lock conflicts, `Workspace` initializes storage **lazily**:

```python
# These DON'T open the database:
ws = Workspace()
ws.events()           # API call, no storage
ws.segmentation(...)  # API call, no storage
ws.funnels(...)       # API call, no storage

# These DO open the database (on first access):
ws.fetch_events(...)  # Writes to storage
ws.sql(...)           # Reads from storage
ws.tables()           # Reads metadata
```

This means API-only commands like `mp inspect events` never conflict with fetch operations, even when targeting the same project.

## Avoiding Conflicts

### Use Ephemeral Mode for Testing

```bash
# Won't conflict with your main database
mp fetch events --from 2025-01-01 --to 2025-01-07 --ephemeral
```

### Use Separate Paths for Parallel Work

```bash
# Terminal 1
mp fetch events --from 2025-01-01 --to 2025-06-30 --path ./h1.db

# Terminal 2 (parallel)
mp fetch events --from 2025-07-01 --to 2025-12-31 --path ./h2.db
```

### Combine into Single Commands

```bash
# Instead of two fetches, use date range in one command
mp fetch events --from 2025-01-01 --to 2025-12-31
```

### Stream Instead of Store

If you don't need to query the data repeatedly:

```bash
# No database, no locks
mp fetch events --from 2025-01-01 --stdout | process_events.py
```

## Connection Lifecycle

The `StorageEngine` manages its DuckDB connection:

```python
# Workspace as context manager ensures cleanup
with Workspace() as ws:
    ws.fetch_events(from_date="2025-01-01", to_date="2025-01-31")
    df = ws.sql("SELECT * FROM events LIMIT 10")
# Connection closed, lock released

# Or explicit close
ws = Workspace()
try:
    ws.fetch_events(...)
finally:
    ws.close()
```

CLI commands handle this automatically.

## Technical Details

### Lock File

DuckDB creates a `.wal` (write-ahead log) file alongside the database during write operations. The lock is held for the duration of the connection.

### Process Isolation

Within a single Python process, multiple `Workspace` instances can share the same database file (DuckDB handles internal locking). Lock conflicts occur between **separate processes**.

### Read-Only Mode

Both `StorageEngine` and `Workspace` support a `read_only` parameter:

```python
# Default: write access (matches DuckDB's native behavior)
ws = Workspace()  # read_only=False

# Explicit read-only for concurrent access
ws = Workspace(path="data.db", read_only=True)
```

Read-only connections:

- Allow multiple reader processes to access the database concurrently (when no write lock is held)
- Cannot execute INSERT, UPDATE, DELETE, or DDL statements
- Still blocked by an active write lock (DuckDB write locks are exclusive)

The CLI uses this automatically:

- **Read commands** (`mp query`, `mp inspect tables`, etc.) use `read_only=True`
- **Write commands** (`mp fetch`, `mp inspect drop`) use `read_only=False`

**Note:** If a `mp fetch` is running, other commands will still be blocked until it completes. The benefit of read-only mode is enabling multiple concurrent read operations (e.g., two `mp query` commands).

## See Also

- [Design](design.md) — Overall architecture
- [Data Model](data-model.md) — Table schemas and query patterns
- [DuckDB Documentation](https://duckdb.org/docs/) — Full DuckDB reference
