# Exceptions

All library exceptions inherit from `MixpanelDataError`, enabling callers to catch all library errors with a single except clause.

## Exception Hierarchy

```
MixpanelDataError
├── ConfigError
│   ├── AccountNotFoundError
│   └── AccountExistsError
├── APIError
│   ├── AuthenticationError
│   ├── RateLimitError
│   ├── QueryError
│   ├── ServerError
│   └── JQLSyntaxError
├── TableExistsError
├── TableNotFoundError
├── DatabaseLockedError
└── DatabaseNotFoundError
```

## Catching Errors

```python
import mixpanel_data as mp

try:
    ws = mp.Workspace()
    result = ws.segmentation(event="Purchase", from_date="2025-01-01", to_date="2025-01-31")
except mp.AuthenticationError as e:
    print(f"Auth failed: {e.message}")
except mp.RateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
except mp.MixpanelDataError as e:
    print(f"Error [{e.code}]: {e.message}")
```

## Base Exception

::: mixpanel_data.MixpanelDataError
    options:
      show_root_heading: true
      show_root_toc_entry: true

## API Exceptions

::: mixpanel_data.APIError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.AuthenticationError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.RateLimitError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.QueryError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.ServerError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.JQLSyntaxError
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Configuration Exceptions

::: mixpanel_data.ConfigError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.AccountNotFoundError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.AccountExistsError
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Storage Exceptions

Storage exceptions are raised during fetch and table operations:

| Exception | Raised When |
|-----------|-------------|
| `TableExistsError` | Fetching to an existing table without `append=True` or `--replace` |
| `TableNotFoundError` | Using `append=True` on a non-existent table |
| `DatabaseLockedError` | Another process has the database locked |
| `DatabaseNotFoundError` | Database file not found in read-only mode |

::: mixpanel_data.TableExistsError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.TableNotFoundError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.DatabaseLockedError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.DatabaseNotFoundError
    options:
      show_root_heading: true
      show_root_toc_entry: true
