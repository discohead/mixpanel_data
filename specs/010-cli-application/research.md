# Research: CLI Application

**Date**: 2025-12-23
**Status**: Complete
**Purpose**: Document technology decisions and best practices for CLI implementation

## Technology Decisions

### CLI Framework: Typer

**Decision**: Use Typer as the CLI framework
**Rationale**:
- Mandated by constitution (Technology Stack section)
- Native type hint support aligns with Python 3.10+ requirement
- Built on Click but provides cleaner, more modern API
- Automatic help generation from function signatures and docstrings
- Built-in shell completion support

**Alternatives Considered**:
- Click: Lower-level, more verbose; Typer is built on Click
- argparse: Standard library but lacks modern features; prohibited by constitution
- Fire: Auto-generates CLI from functions but less control over interface

### Output Formatting: Rich

**Decision**: Use Rich for terminal output formatting
**Rationale**:
- Mandated by constitution for tables and progress bars
- Provides Table, Progress, Console for structured output
- Handles terminal width detection and wrapping
- Supports markdown rendering for help text
- Color/styling can be disabled via NO_COLOR

**Key Rich Components**:
- `rich.console.Console` - Central output handler with stderr/stdout routing
- `rich.table.Table` - Formatted table output
- `rich.progress.Progress` - Progress bars for fetch operations
- `rich.json.JSON` - Pretty-printed JSON output

### Command Structure: Subcommand Groups

**Decision**: Organize 31 commands into 4 subcommand groups
**Rationale**:
- Groups provide logical organization (auth, fetch, query, inspect)
- Follows established CLI conventions (git, docker, kubectl)
- Each group can be imported as a separate Typer app
- Enables per-group help: `mp auth --help`

**Group Structure**:
| Group | Commands | Primary Class |
|-------|----------|---------------|
| auth | 6 | ConfigManager |
| fetch | 2 | Workspace |
| query | 14 | Workspace |
| inspect | 10 | Workspace + DiscoveryService |

## Best Practices

### Typer Patterns

#### Global Options via Callback

```python
@app.callback()
def main(
    ctx: typer.Context,
    account: Annotated[str | None, typer.Option("--account", "-a")] = None,
    format: Annotated[str, typer.Option("--format", "-f")] = "json",
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
):
    """Mixpanel data CLI."""
    ctx.ensure_object(dict)
    ctx.obj["account"] = account
    ctx.obj["format"] = format
    ctx.obj["quiet"] = quiet
    ctx.obj["verbose"] = verbose
```

#### Exit Codes via Exceptions

```python
class CLIError(Exception):
    """Base CLI error with exit code."""
    exit_code: int = 1

class AuthError(CLIError):
    exit_code = 2

class InvalidArgsError(CLIError):
    exit_code = 3
```

#### Stdout vs Stderr Separation

```python
console = Console()
err_console = Console(stderr=True)

# Data output
console.print_json(data=result.to_dict())

# Progress/status
err_console.print("[dim]Fetching events...[/dim]")
```

### Output Format Implementation

#### JSON Formatter
```python
def format_json(data: dict | list) -> str:
    return json.dumps(data, indent=2, default=str)
```

#### Table Formatter
```python
def format_table(data: list[dict], columns: list[str]) -> Table:
    table = Table()
    for col in columns:
        table.add_column(col.upper())
    for row in data:
        table.add_row(*[str(row.get(col, "")) for col in columns])
    return table
```

#### CSV Formatter
```python
def format_csv(data: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys() if data else [])
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue()
```

### Error Handling Pattern

```python
def handle_errors(func):
    """Decorator to convert library exceptions to CLI exit codes."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AuthenticationError as e:
            err_console.print(f"[red]Authentication error:[/red] {e.message}")
            raise typer.Exit(2)
        except AccountNotFoundError as e:
            err_console.print(f"[red]Account not found:[/red] {e.message}")
            raise typer.Exit(4)
        except RateLimitError as e:
            err_console.print(f"[yellow]Rate limited:[/yellow] {e.message}")
            raise typer.Exit(5)
        except MixpanelDataError as e:
            err_console.print(f"[red]Error:[/red] {e.message}")
            raise typer.Exit(1)
    return wrapper
```

### Interrupt Handling

```python
import signal

def handle_interrupt(signum, frame):
    err_console.print("\n[yellow]Interrupted[/yellow]")
    raise typer.Exit(130)

signal.signal(signal.SIGINT, handle_interrupt)
```

## Integration Points

### Workspace Facade Mapping

| CLI Command | Workspace Method |
|-------------|------------------|
| `mp fetch events` | `workspace.fetch_events()` |
| `mp fetch profiles` | `workspace.fetch_profiles()` |
| `mp query sql` | `workspace.sql()` / `workspace.sql_scalar()` |
| `mp query segmentation` | `workspace.segmentation()` |
| `mp query funnel` | `workspace.funnel()` |
| `mp query retention` | `workspace.retention()` |
| `mp query jql` | `workspace.jql()` |
| `mp inspect events` | `workspace.events()` |
| `mp inspect properties` | `workspace.properties()` |
| `mp inspect values` | `workspace.property_values()` |
| `mp inspect funnels` | `workspace.funnels()` |
| `mp inspect cohorts` | `workspace.cohorts()` |
| `mp inspect top-events` | `workspace.top_events()` |
| `mp inspect info` | `workspace.info()` |
| `mp inspect tables` | `workspace.tables()` |
| `mp inspect schema` | `workspace.schema()` |
| `mp inspect drop` | `workspace.drop()` |

### ConfigManager Mapping

| CLI Command | ConfigManager Method |
|-------------|----------------------|
| `mp auth list` | `config.list_accounts()` |
| `mp auth add` | `config.add_account()` |
| `mp auth remove` | `config.remove_account()` |
| `mp auth switch` | `config.set_default()` |
| `mp auth show` | `config.get_account()` |
| `mp auth test` | `config.resolve_credentials()` + API ping |

### Result Type Serialization

All result types (FetchResult, SegmentationResult, etc.) implement `.to_dict()` for JSON serialization. The CLI formatters consume these dictionaries.

## Testing Strategy

### Unit Tests
- Formatters: Test each format produces valid output
- Utils: Test error handling, exit code mapping
- Commands: Test argument parsing with mocked Workspace

### Integration Tests
- Use Typer's CliRunner for end-to-end command testing
- Mock Workspace/ConfigManager to avoid API calls
- Verify exit codes, output format, error messages

```python
from typer.testing import CliRunner

runner = CliRunner()

def test_auth_list():
    result = runner.invoke(app, ["auth", "list"])
    assert result.exit_code == 0
    assert "production" in result.stdout
```

## Open Decisions (None)

All technology decisions are predetermined by the constitution. No open decisions remain.
