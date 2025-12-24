# Auth Module

The auth module provides credential management and configuration.

## Overview

```python
from mixpanel_data.auth import ConfigManager, Credentials, AccountInfo

# Manage accounts
config = ConfigManager()
config.add_account("production", username="...", secret="...", project_id="...", region="us")
accounts = config.list_accounts()

# Resolve credentials
creds = config.resolve_credentials(account="production")
```

## ConfigManager

Manages accounts stored in the TOML config file (`~/.mp/config.toml`).

::: mixpanel_data.auth.ConfigManager
    options:
      show_root_heading: true
      show_root_toc_entry: true
      members:
        - __init__
        - config_path
        - resolve_credentials
        - list_accounts
        - add_account
        - remove_account
        - set_default
        - get_account

## Credentials

Immutable container for authentication credentials.

::: mixpanel_data.auth.Credentials
    options:
      show_root_heading: true
      show_root_toc_entry: true

## AccountInfo

Account metadata (without the secret).

::: mixpanel_data.auth.AccountInfo
    options:
      show_root_heading: true
      show_root_toc_entry: true
