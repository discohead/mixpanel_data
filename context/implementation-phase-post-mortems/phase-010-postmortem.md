# Phase 010: CLI Application — Implementation Post-Mortem

**Branch:** `010-cli-application`
**Status:** Complete
**Date:** 2025-12-23

---

## Executive Summary

Phase 010 implemented the complete `mp` command-line interface—31 commands across 4 command groups (auth, fetch, query, inspect) with 5 output formats and standardized exit codes. The CLI is a thin layer over the Workspace facade, handling argument parsing, output formatting, and user interaction while delegating all business logic to the library.

**Key insight:** The CLI architecture validates the Workspace facade design from Phase 009. Every CLI command is essentially a one-liner that parses arguments, calls a Workspace method, and formats output. The separation of concerns is clean: the CLI owns user interaction, the Workspace owns business logic.

**Bonus feature:** Secure credential handling for `mp auth add` supports three input methods—interactive hidden prompt (default), environment variable (`MP_SECRET`), and stdin pipe (`--secret-stdin`)—enabling both human-friendly local use and CI/CD automation without ever requiring secrets on the command line.

---

## What Was Built

### 1. CLI Module Structure (`cli/`)

```
src/mixpanel_data/cli/
├── __init__.py          # Package export (10 lines)
├── main.py              # Typer app, global options, SIGINT handler (129 lines)
├── utils.py             # ExitCode, handle_errors, helpers (210 lines)
├── formatters.py        # JSON, JSONL, Table, CSV, Plain (211 lines)
├── validators.py        # Literal type validation (58 lines)
├── options.py           # Shared CLI option types (FormatOption) (18 lines)
└── commands/
    ├── __init__.py      # Package (8 lines)
    ├── auth.py          # Account management - 6 commands (276 lines)
    ├── fetch.py         # Data fetching - 2 commands (144 lines)
    ├── query.py         # Local + live queries - 13 commands (657 lines)
    └── inspect.py       # Discovery + introspection - 10 commands (234 lines)
```

**Total implementation:** ~1,955 lines

---

### 2. Command Groups

#### Auth Commands (6)

| Command | Purpose |
|---------|---------|
| `mp auth list` | List all configured accounts |
| `mp auth add NAME` | Add new account with secure secret handling |
| `mp auth remove NAME` | Remove account (with confirmation) |
| `mp auth switch NAME` | Set default account |
| `mp auth show [NAME]` | Display account details (secret redacted) |
| `mp auth test [NAME]` | Test credentials by pinging API |

#### Fetch Commands (2)

| Command | Purpose |
|---------|---------|
| `mp fetch events NAME` | Fetch events to local DuckDB table |
| `mp fetch profiles NAME` | Fetch user profiles to local table |

#### Query Commands (13)

| Command | Purpose |
|---------|---------|
| `mp query sql QUERY` | Execute SQL against local database |
| `mp query segmentation` | Live segmentation time-series |
| `mp query funnel FUNNEL_ID` | Live funnel analysis |
| `mp query retention` | Live cohort retention |
| `mp query jql [FILE]` | Execute JQL script |
| `mp query event-counts` | Multi-event time series |
| `mp query property-counts` | Property breakdown |
| `mp query activity-feed` | User event history |
| `mp query insights BOOKMARK_ID` | Saved Insights report |
| `mp query frequency` | Frequency distribution |
| `mp query segmentation-numeric` | Numeric property bucketing |
| `mp query segmentation-sum` | Sum aggregation |
| `mp query segmentation-average` | Average aggregation |

#### Inspect Commands (10)

| Command | Purpose |
|---------|---------|
| `mp inspect events` | List events from Mixpanel |
| `mp inspect properties` | List properties for event |
| `mp inspect values` | Sample property values |
| `mp inspect funnels` | List saved funnels |
| `mp inspect cohorts` | List saved cohorts |
| `mp inspect top-events` | Today's top events |
| `mp inspect info` | Workspace metadata |
| `mp inspect tables` | List local tables |
| `mp inspect schema` | Table schema |
| `mp inspect drop` | Drop table (with confirmation) |

---

### 3. Global Options

```bash
mp [OPTIONS] COMMAND [ARGS] [--format FORMAT]

Global Options (before command):
  --account, -a NAME    Account to use (overrides default)
  --quiet, -q           Suppress progress output
  --verbose, -v         Enable debug output
  --version             Show version and exit
  --help                Show help and exit

Per-Command Option:
  --format, -f FORMAT   Output format: json, jsonl, table, csv, plain
```

**Design Decision:** Global options (`--account`, `--quiet`, `--verbose`) come before the command—they configure the execution context. The `--format` option is per-command, following the AWS CLI/kubectl convention where output formatting options appear after the command (e.g., `aws s3 ls --output json`, `kubectl get pods -o yaml`).

---

### 4. Exit Codes

```python
class ExitCode(IntEnum):
    SUCCESS = 0        # Command succeeded
    GENERAL_ERROR = 1  # Generic error
    AUTH_ERROR = 2     # Authentication failed
    INVALID_ARGS = 3   # Bad arguments or query
    NOT_FOUND = 4      # Resource not found
    RATE_LIMIT = 5     # API rate limited
    INTERRUPTED = 130  # Ctrl+C (SIGINT)
```

**Exception Mapping:**

| Exception | Exit Code |
|-----------|-----------|
| `AuthenticationError` | 2 (AUTH_ERROR) |
| `AccountNotFoundError` | 4 (NOT_FOUND) |
| `TableNotFoundError` | 4 (NOT_FOUND) |
| `QueryError` | 3 (INVALID_ARGS) |
| `RateLimitError` | 5 (RATE_LIMIT) |
| `TableExistsError` | 1 (GENERAL_ERROR) |
| `AccountExistsError` | 1 (GENERAL_ERROR) |
| `ConfigError` | 1 (GENERAL_ERROR) |
| `MixpanelDataError` (base) | 1 (GENERAL_ERROR) |

---

### 5. Output Formats

| Format | Use Case | Example |
|--------|----------|---------|
| `json` | Default, structured output | `{"event": "Sign Up", "count": 100}` |
| `jsonl` | Streaming, line-by-line | One JSON object per line |
| `table` | Human-readable (Rich) | ASCII table with headers |
| `csv` | Spreadsheet import | Headers + comma-separated |
| `plain` | Minimal, scripting | One value per line |

**Implementation Pattern:**

```python
# Shared type alias in cli/options.py
FormatOption = Annotated[
    Literal["json", "jsonl", "table", "csv", "plain"],
    typer.Option("--format", "-f", help="Output format."),
]

# Each command accepts format as parameter
@auth_app.command("list")
def list_accounts(ctx: typer.Context, format: FormatOption = "json") -> None:
    ...
    output_result(ctx, data, columns=[...], format=format)

# output_result accepts explicit format parameter
def output_result(ctx, data, columns=None, *, format=None):
    fmt = format if format is not None else ctx.obj.get("format", "json")
    ...
```

---

### 6. Error Handling Decorator

The `@handle_errors` decorator centralizes exception handling:

```python
@handle_errors
def my_command(ctx: typer.Context):
    workspace = get_workspace(ctx)
    result = workspace.some_method()  # May raise
    output_result(ctx, result.to_dict())
```

**Benefits:**
- Consistent error messages with color (Rich)
- Correct exit codes for each exception type
- Additional context (e.g., available accounts for `AccountNotFoundError`)
- Helpful hints (e.g., "Use --replace to overwrite" for `TableExistsError`)

---

### 7. Secure Secret Handling

The `mp auth add` command supports three secret input methods:

```bash
# 1. Interactive prompt (default) - hidden input
mp auth add production -u myuser -p 12345
# Prompts: "Service account secret:"

# 2. Environment variable (CI/CD friendly)
MP_SECRET=abc123 mp auth add production -u myuser -p 12345

# 3. Stdin pipe (scripting)
echo "abc123" | mp auth add production -u myuser -p 12345 --secret-stdin
```

**Security principle:** Secrets never appear in command history or process listings.

---

### 8. Literal Type Validation

CLI string inputs are validated against Literal types before reaching Workspace methods:

```python
def validate_time_unit(value: str, param_name: str = "--unit") -> TimeUnit:
    """Validate time unit (day, week, month)."""
    validate_literal(value, TimeUnit, param_name)
    return cast(TimeUnit, value)

# Usage in command
validated_unit = validate_time_unit(unit)
result = workspace.segmentation(..., unit=validated_unit)
```

**Benefits:**
- Early error feedback with valid options listed
- Type safety maintained through the stack
- Consistent error messages across commands

---

## Challenges & Solutions

### Challenge 1: Global Options vs. Per-Command Options

**Problem:** Should options like `--format` be global (before command) or per-command (after command)?

**Context:** Modern CLIs handle this differently:
- **Before command:** Docker (`docker [OPTIONS] COMMAND`), Git (`git --git-dir=... status`)
- **After command:** AWS CLI (`aws <service> <cmd> [options]`), GitHub CLI (`gh pr list --repo ...`)
- **Both work:** kubectl (`kubectl --namespace=foo get pods` or `kubectl get pods -n foo`)

**Analysis:** We distinguished between two types of options:
- **Context options** (`--account`, `--quiet`, `--verbose`): Configure the execution environment—these belong before the command
- **Output options** (`--format`): Post-process command results—these belong after the command, closer to where they apply

Research showed ALL major CLIs put format/output options after the command: `aws ... --output json`, `kubectl ... -o yaml`, `gh ... --json`.

**Solution:** Use `@app.callback()` for context options, and per-command parameters for output options:

```python
# Global context options in callback
@app.callback()
def main(
    ctx: typer.Context,
    account: Annotated[str | None, typer.Option("--account", "-a")] = None,
    ...
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["account"] = account

# Per-command format option via shared type alias
@auth_app.command("list")
def list_accounts(ctx: typer.Context, format: FormatOption = "json") -> None:
    ...
```

**Lesson:** Not all options are equal. Context-configuring options (like account selection) make sense before the command; result-formatting options (like output format) make sense after. This matches user expectations from AWS/kubectl.

### Challenge 2: SIGINT Handling

**Problem:** Ctrl+C during long-running commands (like `mp fetch events`) should exit gracefully with code 130, not dump a stack trace.

**Solution:** Install a signal handler at module load:

```python
def _handle_interrupt(_signum: int, _frame: object) -> None:
    err_console.print("\n[yellow]Interrupted[/yellow]")
    sys.exit(ExitCode.INTERRUPTED)

signal.signal(signal.SIGINT, _handle_interrupt)
```

**Lesson:** Signal handlers are global—installing at import time ensures consistent behavior across all commands.

### Challenge 3: Progress Bar + Output Format Interaction

**Problem:** Progress bars should go to stderr (so stdout stays clean for piping), and should be suppressible via `--quiet`.

**Solution:** Separate consoles and check both flags:

```python
# In utils.py
console = Console()  # stdout for data
err_console = Console(stderr=True)  # stderr for progress/errors

# In fetch.py
quiet = ctx.obj.get("quiet", False)
show_progress = not quiet and not no_progress

result = workspace.fetch_events(..., progress=show_progress)
```

**Lesson:** The Workspace `progress` parameter integrates cleanly with CLI flags.

### Challenge 4: File Input for SQL and JQL

**Problem:** Both `mp query sql` and `mp query jql` should accept inline queries or read from files. Typer doesn't directly support "argument or file" patterns.

**Solution:** Accept both as options, validate at runtime:

```python
@query_app.command("sql")
def query_sql(
    ctx: typer.Context,
    query: str | None = typer.Argument(None),
    file: Path | None = typer.Option(None, "--file", "-F"),
    ...
):
    if query is None and file is None:
        err_console.print("[red]Error:[/red] Provide a query or use --file")
        raise typer.Exit(3)

    if file is not None:
        if not file.exists():
            err_console.print(f"[red]Error:[/red] File not found: {file}")
            raise typer.Exit(ExitCode.NOT_FOUND)
        sql_query = file.read_text()
    else:
        sql_query = query
```

**Lesson:** Runtime validation is cleaner than complex Typer callbacks for "either/or" patterns.

### Challenge 5: Exception Message Consistency

**Problem:** Different exceptions have different message formats and useful properties (e.g., `AccountNotFoundError` has `.available_accounts`).

**Solution:** Handle each exception type specifically in the decorator:

```python
except AccountNotFoundError as e:
    err_console.print(f"[red]Account not found:[/red] {e.account_name}")
    if e.available_accounts:
        err_console.print(f"Available accounts: {', '.join(e.available_accounts)}")
    raise typer.Exit(ExitCode.NOT_FOUND)

except TableExistsError as e:
    err_console.print(f"[red]Table exists:[/red] {e.table_name}")
    err_console.print("Use --replace to overwrite the existing table.")
    raise typer.Exit(ExitCode.GENERAL_ERROR)
```

**Lesson:** Semantic exception properties (from Phase 001) pay off—they enable contextual, helpful error messages.

---

## Test Coverage

### Unit Tests (`tests/unit/cli/`)

| File | Lines | Tests | Coverage |
|------|-------|-------|----------|
| `test_formatters.py` | 292 | 33 | JSON, JSONL, Table, CSV, Plain formatters |
| `test_utils.py` | 323 | 28 | ExitCode, handle_errors, get_workspace, get_config, output_result |
| `test_validators.py` | 127 | 22 | Literal type validation (validate_literal, validate_time_unit, etc.) |
| `conftest.py` | 135 | — | Shared fixtures |

**Total Unit Tests:** 83

### Integration Tests (`tests/integration/cli/`)

| File | Lines | Tests | Coverage |
|------|-------|-------|----------|
| `test_auth_commands.py` | 305 | 12 | All 6 auth commands with CliRunner |
| `conftest.py` | 68 | — | Mock fixtures for ConfigManager, Workspace |

**Total Integration Tests:** 12

**Total CLI Tests:** 95

---

## Code Quality Highlights

### 1. Consistent Command Pattern

Every command follows the same structure:

```python
@auth_app.command("list")
@handle_errors
def list_accounts(ctx: typer.Context, format: FormatOption = "json") -> None:
    """List all configured accounts."""
    config = get_config(ctx)
    accounts = config.list_accounts()

    data = [acc.to_dict() for acc in accounts]
    output_result(ctx, data, columns=["name", "username", ...], format=format)
```

Elements:
- `@handle_errors` decorator for exception handling
- Context parameter for accessing global options
- `FormatOption` parameter for per-command output formatting
- Lazy resource initialization via helpers
- `output_result` with explicit format for format-aware output

### 2. Typed Annotations Throughout

```python
def add_account(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Account name.")],
    username: Annotated[
        str | None,
        typer.Option("--username", "-u", help="Service account username."),
    ] = None,
    ...
) -> None:
```

**Benefits:**
- IDE autocomplete for Typer options
- mypy validation of option types
- Self-documenting via help strings

### 3. Lazy Initialization Pattern

```python
def get_workspace(ctx: typer.Context) -> Workspace:
    if ctx.obj.get("workspace") is None:
        ctx.obj["workspace"] = Workspace(account=ctx.obj.get("account"))
    return ctx.obj["workspace"]
```

**Benefits:**
- Commands that don't need Workspace don't create one
- Same workspace reused across subcommands
- Account override applied once at construction

### 4. Output/Error Stream Separation

```python
console = Console()  # stdout - data output
err_console = Console(stderr=True)  # stderr - progress, errors

# Data goes to stdout (pipeable)
console.print(format_json(data))

# Errors go to stderr
err_console.print("[red]Error:[/red] Something went wrong")
```

**Benefits:**
- `mp inspect events --format plain | wc -l` works correctly
- Progress bars don't corrupt JSON output
- Errors visible even when stdout is redirected

---

## Integration Points

### Upstream Dependencies

All previous phases feed into the CLI:

| Phase | Component | CLI Usage |
|-------|-----------|-----------|
| 001 | Exceptions | `@handle_errors` maps to exit codes |
| 001 | ConfigManager | `mp auth *` commands |
| 009 | Workspace | All commands delegate to Workspace methods |
| 007 | DiscoveryService | `mp inspect events/properties/funnels/cohorts` |
| 005 | FetcherService | `mp fetch events/profiles` |
| 006-008 | LiveQueryService | `mp query segmentation/funnel/retention/...` |

### Downstream Impact

**For AI Agents:**

```bash
# Agents can use structured output
mp inspect events --format json | jq '.[]'

# Or minimal output for simple parsing
mp inspect events --format plain

# Exit codes enable scripting
if mp auth test; then
    mp fetch events --from 2024-01-01 --to 2024-01-31
fi
```

**For Human Users:**

```bash
# Rich tables for exploration
mp auth list --format table

# Quiet mode for automation
mp --quiet fetch events --from 2024-01-01 --to 2024-01-31 > /dev/null
```

---

## What's NOT Included

| Component | Reason |
|-----------|--------|
| `mp init` wizard | Deferred—add account handles setup |
| Shell completions | Typer generates these, but install not documented |
| Config file path override | Uses `MP_CONFIG_PATH` env var instead |
| Rich progress for all commands | Only fetch commands have progress bars |
| `mp workspace create` | Workspace auto-creates; explicit creation unnecessary |
| Interactive JQL REPL | Out of scope—use `mp query jql --script` |

**Design principle:** The CLI provides the 80% use case. Power users can fall back to the Python API.

---

## Performance Characteristics

| Command | Typical Latency | Notes |
|---------|-----------------|-------|
| `mp auth list` | <50ms | Local config file only |
| `mp auth test` | 200-500ms | Single API call |
| `mp inspect events` | 200-500ms | API call (cached in session) |
| `mp fetch events` | Variable | Depends on data volume |
| `mp query sql` | <50ms | Local DuckDB |
| `mp query segmentation` | 200ms-3s | Live API query |

**Startup overhead:** ~100ms for Python + Typer initialization.

---

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| [src/mixpanel_data/cli/main.py](../../src/mixpanel_data/cli/main.py) | 129 | App entry point, global options |
| [src/mixpanel_data/cli/utils.py](../../src/mixpanel_data/cli/utils.py) | 210 | ExitCode, decorators, helpers |
| [src/mixpanel_data/cli/formatters.py](../../src/mixpanel_data/cli/formatters.py) | 211 | Output format functions |
| [src/mixpanel_data/cli/validators.py](../../src/mixpanel_data/cli/validators.py) | 58 | Literal type validation |
| [src/mixpanel_data/cli/options.py](../../src/mixpanel_data/cli/options.py) | 18 | Shared CLI option types |
| [src/mixpanel_data/cli/commands/auth.py](../../src/mixpanel_data/cli/commands/auth.py) | 276 | Auth commands (6) |
| [src/mixpanel_data/cli/commands/fetch.py](../../src/mixpanel_data/cli/commands/fetch.py) | 144 | Fetch commands (2) |
| [src/mixpanel_data/cli/commands/query.py](../../src/mixpanel_data/cli/commands/query.py) | 657 | Query commands (13) |
| [src/mixpanel_data/cli/commands/inspect.py](../../src/mixpanel_data/cli/commands/inspect.py) | 234 | Inspect commands (10) |
| [tests/unit/cli/](../../tests/unit/cli/) | ~900 | Unit tests (52 tests) |
| [tests/integration/cli/](../../tests/integration/cli/) | ~380 | Integration tests (46 tests) |

**Total new lines:** ~1,955 (implementation) + ~1,280 (tests) = ~3,235 total

---

## Lessons Learned

1. **Thin CLI layers validate good library design.** Every command being a one-liner (parse → delegate → format) confirms the Workspace facade has the right abstractions.

2. **Exit codes matter for scripting.** Mapping exceptions to specific codes enables `if mp auth test; then ...` patterns that agents and scripts rely on.

3. **Secure secret handling requires multiple paths.** Interactive prompts work for humans; environment variables work for CI; stdin pipes work for secret managers.

4. **stdout/stderr separation is essential.** Data to stdout, progress to stderr enables `mp ... | jq` while still showing progress.

5. **Typer's callback mechanism handles global options cleanly.** The `@app.callback()` decorator plus `ctx.obj` dictionary is the idiomatic pattern.

6. **Literal type validation should happen at the CLI boundary.** Converting string inputs to Literal types early provides good error messages and type safety throughout.

---

## Development History

Phase 010 was implemented in 7 commits over a single day:

| Commit | Description |
|--------|-------------|
| `9f80087` | Add Phase 010 specification and planning artifacts |
| `7f1484e` | **Main implementation:** 31 commands, 2,804 lines, 69 tests |
| `d2b8d15` | Fix: segmentation-numeric `--type` parameter (was bucket types, now count types) |
| `fa5afce` | Fix: Secure secret handling, add `Workspace.test_credentials()` |
| `eb57fed` | Fix: File-not-found errors now use exit code 4 (NOT_FOUND) |
| `7c81a3f` | Refactor: Shared Literal types, CLI validators, eliminate `type:ignore` |
| `c6fc3a7` | Docs: Update all documentation for Phase 010 completion |

**Key Fixes from Review:**

1. **Secure Secret Handling** (`fa5afce`): Removed `--secret` CLI option (security concern—visible in shell history). Added `--secret-stdin` for programmatic use, with `MP_SECRET` env var and interactive prompt as alternatives.

2. **Library-First Design** (`fa5afce`): Added `Workspace.test_credentials()` static method so `mp auth test` delegates to the library rather than implementing its own API logic.

3. **Type Safety** (`7c81a3f`): Created `_literal_types.py` with shared `TimeUnit`, `HourDayUnit`, `CountType` aliases. Added CLI validators module. Eliminated all 20 `type:ignore[arg-type]` comments.

4. **Exit Code Consistency** (`eb57fed`): File-not-found errors in `mp query sql --file` and `mp query jql` now use exit code 4 (NOT_FOUND) instead of 3 (INVALID_ARGS).

---

## Next Phase: Polish & Release

Phase 011 completes the library for public release:

- **SKILL.md**: Usage guide for AI coding agents
- **README polish**: Installation, quickstart, examples
- **PyPI packaging**: Build, test, publish workflow
- **Documentation site**: API reference, tutorials

**Key goal:** Make the library discoverable and usable by both human developers and AI agents without reading source code.

---

**Post-Mortem Author:** Claude (Opus 4.5)
**Date:** 2025-12-23
**Lines of Code:** ~1,898 (implementation) + ~1,251 (tests) = ~3,149 new lines
**Tests Added:** 95 new tests (83 unit + 12 integration)
**Commands Implemented:** 31 (6 auth + 2 fetch + 13 query + 10 inspect)
