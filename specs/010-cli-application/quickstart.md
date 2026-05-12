# Quickstart: CLI Application Implementation

**Date**: 2025-12-23
**Purpose**: Developer guide for implementing the `mp` CLI

## Prerequisites

Before starting implementation:

1. **Workspace Facade** (Phase 009) must be complete
2. **Dependencies** must be installed:
   ```bash
   # Already in pyproject.toml
   typer>=0.12
   rich>=13.0
   ```
3. **Entry point** configured in pyproject.toml:
   ```toml
   [project.scripts]
   mp = "mixpanel_data.cli.main:app"
   ```

## Implementation Order

### Phase 1: Core Infrastructure (Days 1-2)

1. **Create CLI package structure**
   ```
   src/mixpanel_data/cli/
   ├── __init__.py
   ├── main.py          # Entry point
   ├── formatters.py    # Output formatters
   └── utils.py         # Helpers
   ```

2. **Implement main.py with global options**
   ```python
   import typer
   from typing import Annotated

   app = typer.Typer(help="Mixpanel data CLI")

   @app.callback()
   def main(
       ctx: typer.Context,
       account: Annotated[str | None, typer.Option("--account", "-a")] = None,
       format: Annotated[str, typer.Option("--format", "-f")] = "json",
       quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
       verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
   ):
       ctx.ensure_object(dict)
       ctx.obj["account"] = account
       ctx.obj["format"] = format
       ctx.obj["quiet"] = quiet
       ctx.obj["verbose"] = verbose
   ```

3. **Implement formatters.py**
   - `format_json(data)` → Pretty JSON
   - `format_jsonl(data)` → JSONL
   - `format_table(data, columns)` → Rich Table
   - `format_csv(data)` → CSV
   - `format_plain(data)` → Plain text

4. **Implement utils.py**
   - `handle_errors` decorator
   - `get_workspace(ctx)` helper
   - `get_config(ctx)` helper
   - Exit code constants

### Phase 2: Auth Commands (Day 3)

1. **Create commands/auth.py**
   ```python
   import typer

   auth_app = typer.Typer(help="Manage authentication")

   @auth_app.command("list")
   def list_accounts(ctx: typer.Context):
       ...
   ```

2. **Implement all 6 auth commands**
   - list → ConfigManager.list_accounts()
   - add → ConfigManager.add_account()
   - remove → ConfigManager.remove_account()
   - switch → ConfigManager.set_default()
   - show → ConfigManager.get_account()
   - test → resolve_credentials() + API ping

3. **Add to main.py**
   ```python
   from .commands.auth import auth_app
   app.add_typer(auth_app, name="auth")
   ```

### Phase 3: Fetch Commands (Day 4)

1. **Create commands/fetch.py**
2. **Implement 2 fetch commands**
   - events → Workspace.fetch_events()
   - profiles → Workspace.fetch_profiles()
3. **Add progress bar support**
   ```python
   from rich.progress import Progress

   with Progress(console=err_console) as progress:
       task = progress.add_task("Fetching events...", total=None)
       result = workspace.fetch_events(
           ...,
           progress=not ctx.obj["quiet"]
       )
   ```

### Phase 4: Inspect Commands (Days 5-6)

1. **Create commands/inspect.py**
2. **Implement 10 inspect commands**
   - events → Workspace.events()
   - properties → Workspace.properties()
   - values → Workspace.property_values()
   - funnels → Workspace.funnels()
   - cohorts → Workspace.cohorts()
   - top-events → Workspace.top_events()
   - info → Workspace.info()
   - tables → Workspace.tables()
   - schema → Workspace.schema()
   - drop → Workspace.drop()

### Phase 5: Query Commands (Days 7-10)

1. **Create commands/query.py**
2. **Implement 14 query commands**
   - sql → Workspace.sql() / sql_scalar()
   - segmentation → Workspace.segmentation()
   - funnel → Workspace.funnel()
   - retention → Workspace.retention()
   - jql → Workspace.jql()
   - event-counts → Workspace.event_counts()
   - property-counts → Workspace.property_counts()
   - activity-feed → Workspace.activity_feed()
   - insights → Workspace.insights()
   - frequency → Workspace.frequency()
   - segmentation-numeric → Workspace.segmentation_numeric()
   - segmentation-sum → Workspace.segmentation_sum()
   - segmentation-average → Workspace.segmentation_average()

### Phase 6: Testing & Polish (Days 11-14)

1. **Unit tests for formatters**
2. **Unit tests for utils**
3. **Integration tests with CliRunner**
4. **Help text refinement**
5. **Shell completion**

## Key Implementation Patterns

### Error Handling

```python
from mixpanel_data.exceptions import (
    AuthenticationError,
    AccountNotFoundError,
    RateLimitError,
    MixpanelDataError,
)

def handle_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AuthenticationError as e:
            err_console.print(f"[red]Authentication error:[/red] {e.message}")
            raise typer.Exit(2)
        except AccountNotFoundError as e:
            err_console.print(f"[red]Account not found:[/red] {e.account}")
            if e.available_accounts:
                err_console.print("Available accounts:", ", ".join(e.available_accounts))
            raise typer.Exit(4)
        except RateLimitError as e:
            err_console.print(f"[yellow]Rate limited:[/yellow] Retry after {e.retry_after}s")
            raise typer.Exit(5)
        except MixpanelDataError as e:
            err_console.print(f"[red]Error:[/red] {e.message}")
            raise typer.Exit(1)
    return wrapper
```

### Output Formatting

```python
def output_result(ctx: typer.Context, data: dict | list, columns: list[str] | None = None):
    """Output data in the requested format."""
    fmt = ctx.obj.get("format", "json")

    if fmt == "json":
        console.print_json(data=data)
    elif fmt == "jsonl":
        if isinstance(data, list):
            for item in data:
                console.print(json.dumps(item))
        else:
            console.print(json.dumps(data))
    elif fmt == "table":
        table = format_table(data, columns or list(data[0].keys()) if data else [])
        console.print(table)
    elif fmt == "csv":
        console.print(format_csv(data))
    elif fmt == "plain":
        if isinstance(data, list):
            for item in data:
                console.print(str(item) if not isinstance(item, dict) else item.get("name", item))
        else:
            console.print(str(data))
```

### Lazy Workspace Initialization

```python
def get_workspace(ctx: typer.Context) -> Workspace:
    """Get or create workspace from context."""
    if "workspace" not in ctx.obj or ctx.obj["workspace"] is None:
        account = ctx.obj.get("account")
        ctx.obj["workspace"] = Workspace(account=account)
    return ctx.obj["workspace"]
```

### Confirmation Prompts

```python
@inspect_app.command("drop")
def drop_table(
    ctx: typer.Context,
    table: Annotated[str, typer.Option("--table", "-t")],
    force: Annotated[bool, typer.Option("--force")] = False,
):
    """Drop a table from the local database."""
    if not force:
        confirm = typer.confirm(f"Drop table '{table}'?")
        if not confirm:
            err_console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(2)

    workspace = get_workspace(ctx)
    workspace.drop(table)
    output_result(ctx, {"dropped": table})
```

### Signal Handling

```python
import signal

def setup_signal_handlers():
    def handle_interrupt(signum, frame):
        err_console.print("\n[yellow]Interrupted[/yellow]")
        raise typer.Exit(130)

    signal.signal(signal.SIGINT, handle_interrupt)
```

## Testing Patterns

### Unit Test for Formatter

```python
def test_format_json():
    data = {"name": "test", "count": 123}
    result = format_json(data)
    assert json.loads(result) == data

def test_format_csv():
    data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    result = format_csv(data)
    assert "a,b" in result
    assert "1,2" in result
```

### Integration Test with CliRunner

```python
from typer.testing import CliRunner
from mixpanel_data.cli.main import app

runner = CliRunner()

def test_auth_list(mock_config_manager):
    result = runner.invoke(app, ["auth", "list"])
    assert result.exit_code == 0
    assert "production" in result.stdout

def test_auth_list_json_format(mock_config_manager):
    result = runner.invoke(app, ["auth", "list", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
```

### Mock Workspace for Testing

```python
@pytest.fixture
def mock_workspace(mocker):
    mock = mocker.patch("mixpanel_data.cli.commands.query.get_workspace")
    workspace = mocker.MagicMock()
    workspace.sql.return_value = [{"count": 100}]
    mock.return_value = workspace
    return workspace
```

## Common Pitfalls

1. **Don't forget stderr for progress**
   ```python
   err_console = Console(stderr=True)
   err_console.print("Fetching...")  # Goes to stderr
   ```

2. **Always use .to_dict() for JSON output**
   ```python
   result = workspace.segmentation(...)
   output_result(ctx, result.to_dict())  # Not result directly
   ```

3. **Handle keyboard interrupt at top level**
   ```python
   if __name__ == "__main__":
       setup_signal_handlers()
       app()
   ```

4. **Test all output formats**
   ```python
   @pytest.mark.parametrize("fmt", ["json", "table", "csv", "jsonl", "plain"])
   def test_output_formats(fmt):
       result = runner.invoke(app, ["inspect", "events", "--format", fmt])
       assert result.exit_code == 0
   ```

5. **Validate dates early**
   ```python
   def validate_date(value: str) -> str:
       try:
           datetime.strptime(value, "%Y-%m-%d")
           return value
       except ValueError:
           raise typer.BadParameter(f"Invalid date format: {value}. Use YYYY-MM-DD.")
   ```

## Verification Checklist

After implementation, verify:

- [ ] `mp --help` shows all command groups
- [ ] `mp auth --help` shows all auth commands
- [ ] `MP_SECRET=... mp auth add production -u ... -p ... -r us` works (or interactive prompt)
- [ ] `mp auth test` validates credentials
- [ ] `mp fetch events --from 2024-01-01 --to 2024-01-07` fetches data
- [ ] `mp query sql "SELECT COUNT(*) FROM events"` returns result
- [ ] `mp inspect events` lists events
- [ ] All --format options work (json, table, csv, jsonl, plain)
- [ ] Errors produce correct exit codes
- [ ] Ctrl+C exits cleanly with code 130
- [ ] Progress bars appear on stderr, data on stdout
