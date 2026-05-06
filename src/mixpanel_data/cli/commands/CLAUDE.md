# CLI Commands

Typer command groups for the `mp` CLI. Each file defines one subcommand
group. The auth surface (042 redesign) is organized around the
**Account → Project → Workspace** hierarchy — see
[`../CLAUDE.md`](../CLAUDE.md) for the canonical group list and global
flags.

## Files

| File | Command Group | Purpose |
|------|---------------|---------|
| `account.py` | `mp account` | Account CRUD + lifecycle (`list`, `add`, `update`, `remove`, `use`, `show`, `test`, `login`, `logout`, `token`, `export-bridge`, `remove-bridge`) |
| `project.py` | `mp project` | Project axis (`list` from `/me`, `use ID`, `show`) |
| `workspace.py` | `mp workspace` | Workspace axis (`list`, `use ID`, `show`) |
| `target.py` | `mp target` | Saved (account, project, workspace?) cursors (`list`, `add`, `use`, `show`, `remove`) |
| `session.py` | `mp session` | Resolved active-session viewer (`mp session [--bridge]`) |
| `query.py` | `mp query` | Live Mixpanel API queries (segmentation, funnel, retention, JQL, …) |
| `inspect.py` | `mp inspect` | Schema discovery (events, properties, funnels, cohorts, bookmarks) |
| `dashboards.py` | `mp dashboards` | Dashboard CRUD (list, create, get, update, delete, favorite, pin, blueprints, RCA) |
| `reports.py` | `mp reports` | Report/bookmark CRUD (list, create, get, update, delete, bulk operations, history) |
| `cohorts.py` | `mp cohorts` | Cohort CRUD (list, create, get, update, delete, bulk operations) |
| `flags.py` | `mp flags` | Feature flag CRUD |
| `experiments.py` | `mp experiments` | Experiment CRUD |
| `alerts.py` | `mp alerts` | Alert CRUD |
| `annotations.py` | `mp annotations` | Annotation CRUD |
| `webhooks.py` | `mp webhooks` | Webhook CRUD |
| `lexicon.py` | `mp lexicon` | Lexicon (event/property definitions, tags, history, export) |
| `drop_filters.py` | `mp drop-filters` | Drop-filter CRUD (data governance) |
| `custom_properties.py` | `mp custom-properties` | Custom-property CRUD (data governance) |
| `custom_events.py` | `mp custom-events` | Custom-event CRUD (data governance) |
| `lookup_tables.py` | `mp lookup-tables` | Lookup-table CRUD + upload/download (data governance) |
| `schemas.py` | `mp schemas` | Project / workspace JSON schemas |
| `business_context.py` | `mp business-context` | Read/write markdown business context at org or project scope (`get`, `set`, `clear`, `chain`) |

**Removed (no shim):** `mp auth`, `mp projects`, `mp workspaces`, `mp context`,
`mp config`. See `RELEASE_NOTES_0.4.0.md` for the legacy → v3 verb map.

## Command Pattern

All commands follow this pattern:

```python
@app.command()
@handle_errors  # Converts exceptions to exit codes
def command_name(
    ctx: typer.Context,
    # Annotated options...
    format: FormatOption = "json",
) -> None:
    """Docstring becomes --help text."""
    workspace = get_workspace(ctx)  # Lazy workspace from context
    result = workspace.some_method(...)
    output_result(ctx, result.to_dict(), format=format)
```

## Key Helpers

From `cli/utils.py`:
- `@handle_errors`: Decorator converting exceptions to exit codes
- `get_workspace(ctx)`: Get/create workspace from context (respects `--account` / `--project` / `--workspace` / `--target`)
- `get_config(ctx)`: Get/create ConfigManager from context
- `output_result(ctx, data)`: Format and output data per `--format` option

## Output Formats

All data commands support `--format`:
- `json` (default for entity CRUD): Pretty-printed JSON
- `jsonl`: One JSON object per line
- `table` (default for list commands): Rich ASCII table
- `csv`: Comma-separated with headers
- `plain`: Minimal text output

## Exit Codes

From `ExitCode` enum:
- 0: Success
- 1: General error
- 2: Authentication error
- 3: Invalid arguments
- 4: Not found
- 5: Rate limited
- 130: Interrupted (Ctrl+C)

## Adding New Commands

1. Add command to the appropriate group file (or create a new group file
   and register it in `cli/main.py::_register_commands`)
2. Use `@handle_errors` decorator
3. Accept `format: FormatOption` for data output
4. Call `output_result()` (or the equivalent format ladder used by the
   identity groups) with serializable dict / list
5. Follow existing docstring conventions for `--help`
