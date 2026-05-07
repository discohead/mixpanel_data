# CLI Package

The `mp` command-line interface for `mixpanel_headless`—a complete programmable interface to Mixpanel analytics. Built with Typer.

## Command Groups

The auth surface is organized around the **Account → Project → Workspace** hierarchy
(042 redesign): five identity command groups, each with `use` as the universal
state-change verb.

| Group | Purpose |
|-------|---------|
| `account` | Account CRUD + lifecycle (`list`, `add`, `remove`, `use`, `show`, `test`, `login`, `logout`, `token`, `export-bridge`, `remove-bridge`) |
| `project` | Project axis (`list` from `/me`, `use ID`, `show`) |
| `workspace` | Workspace axis (`list` from `/me`, `use ID`, `show`) |
| `target` | Saved (account, project, workspace?) cursors (`list`, `add`, `use`, `show`, `remove`) |
| `session` | Resolved active session viewer (`mp session [--bridge]`) |
| `query` | Live Mixpanel API queries (segmentation, funnels, retention, JQL) |
| `inspect` | Schema discovery (events, properties, funnels, cohorts, bookmarks) |
| `dashboards` | Dashboard CRUD (list, create, get, update, delete, favorite, pin, blueprints) |
| `reports` | Report/bookmark CRUD (list, create, get, update, delete, bulk ops, history) |
| `cohorts` | Cohort CRUD (list, create, get, update, delete, bulk ops) |
| `flags` / `experiments` / `alerts` / `annotations` / `webhooks` / `lexicon` / `drop-filters` / `custom-properties` / `custom-events` / `lookup-tables` / `schemas` | Entity CRUD + data governance for the matching App API surface |
| `business-context` | Read/write markdown business context at org or project scope (`get`, `set`, `clear`, `chain`) |

**Removed (no shim):** `mp auth`, `mp projects`, `mp workspaces`, `mp context`,
`mp config`. See `docs/migration/0.4.0.md` for the legacy → v3 verb map.

## Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point, global options, command registration |
| `formatters.py` | Output formatters (JSON, JSONL, table, CSV, plain) |
| `utils.py` | Error handling, workspace helpers, output routing |
| `options.py` | Shared option type aliases (`FormatOption`) |
| `validators.py` | Literal type validators for CLI parameters |
| `commands/` | Command group implementations |

## Global Options

Defined in `main.py` — flow into the resolver as the *param* layer
(env > param > target > bridge > config):

| Flag | Short | Purpose |
|---|---|---|
| `--account NAME` | `-a` | Named account override |
| `--project ID` | `-p` | Project ID override |
| `--workspace ID` | `-w` | Workspace ID override |
| `--target NAME` | `-t` | Apply a saved target (mutually exclusive with -a/-p/-w) |
| `--quiet` | `-q` | Suppress progress output |
| `--verbose` | `-v` | Enable debug output |
| `--version` |  | Show version and exit |

These overrides are **per-command** — they do NOT mutate `~/.mp/config.toml
[active]`. To persist, use `mp account use NAME` / `mp project use ID` /
`mp workspace use N` / `mp target use NAME`.

## Architecture

```
mp command → main.py callback → command handler
                   ↓
              ctx.obj = {account, quiet, verbose, workspace, config}
                   ↓
              get_workspace(ctx) / get_config(ctx)
                   ↓
              Workspace or ConfigManager
```

## Output Flow

1. Command calls `output_result(ctx, data, format=format)`
2. `output_result()` routes to appropriate formatter
3. Formatter converts data to string or Rich Table
4. Output printed to stdout via `console`

Errors go to stderr via `err_console`.

## Error Handling

`@handle_errors` decorator maps exceptions to exit codes:

| Exception | Exit Code |
|-----------|-----------|
| `AuthenticationError` | 2 |
| `AccountNotFoundError` | 4 |
| `RateLimitError` | 5 |
| `QueryError` | 3 |
| `ConfigError` | 1 |
| `MixpanelDataError` | 1 |

## Adding New Commands

1. Create or extend file in `commands/`
2. Use Typer decorators and Annotated types
3. Apply `@handle_errors` decorator
4. Use helpers: `get_workspace()`, `get_config()`, `output_result()`
5. Register command group in `main.py:_register_commands()`
