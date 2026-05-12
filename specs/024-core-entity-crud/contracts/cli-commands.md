# CLI Command Contract: Core Entity CRUD

**Feature**: 024-core-entity-crud

All commands follow the pattern: `mp <group> <subcommand> [args] [--options]`
All commands support: `--format {json,jsonl,table,csv,plain}` (default: json)
All commands require valid credentials (env vars, config file, or OAuth tokens).

## `mp dashboards` (17 subcommands)

### Basic CRUD

```
mp dashboards list [--ids ID1,ID2,...] [--format FORMAT]
mp dashboards create --title TITLE [--description DESC] [--private] [--restricted] [--duplicate ID]
mp dashboards get ID [--format FORMAT]
mp dashboards update ID [--title TITLE] [--description DESC] [--private/--no-private] [--restricted/--no-restricted]
mp dashboards delete ID
mp dashboards bulk-delete --ids ID1,ID2,...
```

### Organization

```
mp dashboards favorite ID
mp dashboards unfavorite ID
mp dashboards pin ID
mp dashboards unpin ID
mp dashboards remove-report DASHBOARD_ID BOOKMARK_ID
```

### Blueprints

```
mp dashboards blueprints [--include-reports] [--format FORMAT]
mp dashboards blueprint-create TEMPLATE_TYPE [--format FORMAT]
```

### Advanced

```
mp dashboards rca --source-id ID --source-data JSON [--format FORMAT]
mp dashboards erf DASHBOARD_ID [--format FORMAT]
mp dashboards update-report-link DASHBOARD_ID REPORT_LINK_ID --type LINK_TYPE
mp dashboards update-text-card DASHBOARD_ID TEXT_CARD_ID [--markdown TEXT]
```

## `mp reports` (10 subcommands)

```
mp reports list [--type TYPE] [--ids ID1,ID2,...] [--format FORMAT]
mp reports create --name NAME --type TYPE --params JSON [--description DESC] [--dashboard-id ID]
mp reports get ID [--format FORMAT]
mp reports update ID [--name NAME] [--params JSON] [--description DESC]
mp reports delete ID
mp reports bulk-delete --ids ID1,ID2,...
mp reports bulk-update --entries JSON
mp reports linked-dashboards ID [--format FORMAT]
mp reports dashboard-ids BOOKMARK_ID [--format FORMAT]
mp reports history ID [--cursor CURSOR] [--page-size N] [--format FORMAT]
```

## `mp cohorts` (7 subcommands)

```
mp cohorts list [--data-group-id ID] [--ids ID1,ID2,...] [--format FORMAT]
mp cohorts create --name NAME [--description DESC] [--data-group-id ID] [--definition JSON]
mp cohorts get ID [--format FORMAT]
mp cohorts update ID [--name NAME] [--description DESC] [--definition JSON]
mp cohorts delete ID
mp cohorts bulk-delete --ids ID1,ID2,...
mp cohorts bulk-update --entries JSON
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Authentication error |
| 3 | Invalid arguments |
| 4 | Not found |
| 5 | Rate limit exceeded |

## Total: 34 CLI Subcommands
