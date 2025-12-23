# CLI QA Runbook

Systematic QA testing for the `mp` CLI against live Mixpanel data.

## Prerequisites

- Account: `sinkapp-prod` in `~/.mp/config.toml`
- CLI: `uv run mp --version`

## Config

| Var | Value |
|-----|-------|
| ACCOUNT | sinkapp-prod |
| EVENT | Added Entity |
| PROPERTY | $screen_height |
| DISTINCT_ID | $device:60FB1D2E-2BE7-45AD-8887-53C397DE6234 |
| BOOKMARK | 44592511 |

---

## 1. Help
```bash
uv run mp --version
uv run mp --help
uv run mp auth --help
uv run mp fetch --help
uv run mp query --help
uv run mp inspect --help
```

## 2. Auth
```bash
uv run mp auth list
uv run mp --format table auth list
uv run mp auth show sinkapp-prod
uv run mp auth test sinkapp-prod
```

## 3. Inspect
```bash
uv run mp -a sinkapp-prod inspect events
uv run mp -a sinkapp-prod inspect properties --event "Added Entity"
uv run mp -a sinkapp-prod inspect values --property '$screen_height' --event "Added Entity" --limit 10
uv run mp -a sinkapp-prod inspect funnels
uv run mp -a sinkapp-prod inspect cohorts
uv run mp -a sinkapp-prod inspect top-events --limit 5
uv run mp -a sinkapp-prod inspect info
uv run mp -a sinkapp-prod inspect tables
```

## 4. Fetch
```bash
uv run mp -a sinkapp-prod fetch events qa_events --from 2024-11-01 --to 2024-11-01 --events "Added Entity" --no-progress
uv run mp -a sinkapp-prod inspect tables
uv run mp -a sinkapp-prod fetch events qa_events --from 2024-11-01 --to 2024-11-01 --replace --no-progress
uv run mp -a sinkapp-prod fetch profiles qa_profiles --no-progress
uv run mp -a sinkapp-prod inspect schema --table qa_events
uv run mp -a sinkapp-prod inspect drop --table qa_profiles --force
```

## 5. SQL
```bash
uv run mp -a sinkapp-prod query sql "SELECT COUNT(*) FROM qa_events"
uv run mp -a sinkapp-prod query sql --scalar "SELECT COUNT(*) FROM qa_events"
```

## 6. Live Queries
```bash
uv run mp -a sinkapp-prod query segmentation --event "Added Entity" --from 2024-11-01 --to 2024-11-30 --unit day
uv run mp -a sinkapp-prod query event-counts --events "Added Entity" --from 2024-11-01 --to 2024-11-07
uv run mp -a sinkapp-prod query property-counts --event "Added Entity" --property '$screen_height' --from 2024-11-01 --to 2024-11-07 --limit 5
uv run mp -a sinkapp-prod query retention --born "Added Entity" --return "Added Entity" --from 2024-11-01 --to 2024-11-30 --intervals 5
uv run mp -a sinkapp-prod query activity-feed --users '$device:60FB1D2E-2BE7-45AD-8887-53C397DE6234'
uv run mp -a sinkapp-prod query insights 44592511
uv run mp -a sinkapp-prod query frequency --from 2024-11-01 --to 2024-11-30 --event "Added Entity"
uv run mp -a sinkapp-prod query segmentation-numeric --event "Added Entity" --on 'properties["$screen_height"]' --from 2024-11-01 --to 2024-11-07
uv run mp -a sinkapp-prod query segmentation-sum --event "Added Entity" --on 'properties["$screen_height"]' --from 2024-11-01 --to 2024-11-07
uv run mp -a sinkapp-prod query segmentation-average --event "Added Entity" --on 'properties["$screen_height"]' --from 2024-11-01 --to 2024-11-07
```

## 7. Output Formats
```bash
uv run mp -a sinkapp-prod --format json inspect events | head -10
uv run mp -a sinkapp-prod --format table auth list
uv run mp -a sinkapp-prod --format csv auth list
uv run mp -a sinkapp-prod --format plain inspect events | head -5
uv run mp -a sinkapp-prod --format jsonl inspect events | head -5
```

## 8. Errors
```bash
uv run mp -a nonexistent_account inspect events; echo "Exit: $?"
uv run mp -a sinkapp-prod fetch events test; echo "Exit: $?"
uv run mp -a sinkapp-prod query sql "SELECT * FROM no_table"; echo "Exit: $?"
```

## 9. Cleanup
```bash
uv run mp -a sinkapp-prod inspect drop --table qa_events --force
uv run mp -a sinkapp-prod inspect tables
```

## Total: 46 test cases
