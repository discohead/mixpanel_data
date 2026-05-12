# CLI Command Contract: Alerts, Annotations, and Webhooks

**Branch**: `026-operational-tooling` | **Date**: 2026-03-31

All commands support `--format {json|jsonl|table|csv|plain}` and `--jq <EXPR>` options.

---

## Alerts (`mp alerts`)

```bash
# List alerts
mp alerts list [--bookmark-id ID] [--skip-user-filter]

# Create alert
mp alerts create \
  --bookmark-id ID \
  --name NAME \
  --condition JSON \
  --frequency SECONDS \
  [--paused | --no-paused] \
  [--subscriptions JSON] \
  [--notification-windows JSON]

# Get alert
mp alerts get ALERT_ID

# Update alert
mp alerts update ALERT_ID \
  [--name NAME] \
  [--bookmark-id ID] \
  [--condition JSON] \
  [--frequency SECONDS] \
  [--paused | --no-paused] \
  [--subscriptions JSON] \
  [--notification-windows JSON]

# Delete alert
mp alerts delete ALERT_ID

# Bulk delete
mp alerts bulk-delete --ids ID1,ID2,ID3

# Alert count and limits
mp alerts count [--type TYPE]

# Alert trigger history
mp alerts history ALERT_ID [--page-size N] [--cursor CURSOR]

# Test alert config
mp alerts test \
  --bookmark-id ID \
  --name NAME \
  --condition JSON \
  --frequency SECONDS \
  [--subscriptions JSON]

# Screenshot URL
mp alerts screenshot --gcs-key KEY

# Validate alerts for bookmark
mp alerts validate \
  --alert-ids ID1,ID2 \
  --bookmark-type TYPE \
  --bookmark-params JSON
```

## Annotations (`mp annotations`)

```bash
# List annotations
mp annotations list [--from DATE] [--to DATE] [--tags ID1,ID2]

# Create annotation
mp annotations create \
  --date DATE \
  --description TEXT \
  [--tags ID1,ID2] \
  [--user-id ID]

# Get annotation
mp annotations get ANNOTATION_ID

# Update annotation
mp annotations update ANNOTATION_ID \
  [--description TEXT] \
  [--tags ID1,ID2]

# Delete annotation
mp annotations delete ANNOTATION_ID

# List tags
mp annotations tags list

# Create tag
mp annotations tags create --name NAME
```

## Webhooks (`mp webhooks`)

```bash
# List webhooks
mp webhooks list

# Create webhook
mp webhooks create \
  --name NAME \
  --url URL \
  [--auth-type TYPE] \
  [--username USER] \
  [--password PASS]

# Update webhook
mp webhooks update WEBHOOK_ID \
  [--name NAME] \
  [--url URL] \
  [--auth-type TYPE] \
  [--username USER] \
  [--password PASS] \
  [--enabled | --no-enabled]

# Delete webhook
mp webhooks delete WEBHOOK_ID

# Test connectivity
mp webhooks test \
  --url URL \
  [--name NAME] \
  [--auth-type TYPE] \
  [--username USER] \
  [--password PASS]
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Authentication error |
| 3 | Invalid arguments |
| 4 | Not found |
| 5 | Rate limited |
