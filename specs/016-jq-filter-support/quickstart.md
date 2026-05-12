# Quickstart: JQ Filter Support

**Feature**: 016-jq-filter-support
**Date**: 2026-01-04

## Basic Usage

The `--jq` option applies a jq filter to JSON output. It works with any command that supports `--format json` or `--format jsonl`.

```bash
# Basic field extraction
mp inspect events --format json --jq '.[0]'

# Get first 5 events
mp inspect events --format json --jq '.[:5]'

# Count events
mp inspect events --format json --jq 'length'
```

## Filtering Results

Use `select()` to filter results based on conditions:

```bash
# Filter events starting with "User"
mp inspect events --format json --jq '.[] | select(startswith("User"))'

# Filter segmentation results by count
mp query segmentation --event Signup --from 2024-01-01 --to 2024-01-31 \
  --format json --jq '.series.total | to_entries | map(select(.value > 100))'

# Filter SQL results
mp query sql "SELECT * FROM events" --format json \
  --jq '.[] | select(.properties.country == "US")'
```

## Transforming Data

Reshape output using jq transformations:

```bash
# Extract specific fields from funnel
mp query funnel --funnel-id 12345 --format json \
  --jq '.steps | map({step: .step_label, rate: .conversion_rate})'

# Flatten nested structures
mp inspect properties --event Signup --format json \
  --jq '.[] | {name, type: .property_type}'

# Create summary object
mp query segmentation --event Purchase --from 2024-01-01 --to 2024-01-31 \
  --format json --jq '{total: .series.total | add, days: .series.total | length}'
```

## Common Patterns

### Get First/Last N Items

```bash
mp inspect events --format json --jq '.[:10]'    # First 10
mp inspect events --format json --jq '.[-5:]'    # Last 5
mp inspect events --format json --jq '.[10:20]'  # Items 10-19
```

### Count and Aggregate

```bash
mp inspect events --format json --jq 'length'                    # Count items
mp query sql "SELECT * FROM events" --format json --jq 'group_by(.event) | map({event: .[0].event, count: length})'
```

### Check for Existence

```bash
# Check if any events match
mp inspect events --format json --jq 'map(select(contains("signup"))) | length > 0'

# Find events containing substring
mp inspect events --format json --jq '.[] | select(contains("User"))'
```

## Error Handling

### Invalid jq Syntax

```bash
$ mp inspect events --format json --jq '.name |'
jq filter error: compile error: syntax error, unexpected end of file
```

### Runtime Errors

```bash
$ mp inspect events --format json --jq '.[0].nonexistent.field'
jq filter error: Cannot index string with string "nonexistent"
```

### Incompatible Format

```bash
$ mp inspect events --format table --jq '.[0]'
Error: --jq requires --format json or jsonl
```

## jq Reference

For full jq syntax, see the [jq manual](https://jqlang.org/manual/).

Common operators:
- `.field` - access field
- `.[]` - iterate array
- `| ` - pipe to next filter
- `select(condition)` - filter items
- `map(expr)` - transform each item
- `length` - array/string length
- `keys` - object keys
- `to_entries` - `{k:v}` → `[{key:k, value:v}]`
- `group_by(.field)` - group by field value
- `sort_by(.field)` - sort by field value
- `unique` - deduplicate
- `first`, `last` - first/last item
