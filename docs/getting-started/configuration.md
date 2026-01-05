# Configuration

mixpanel_data uses Service Accounts for authentication and supports multiple configuration methods for credentials and settings.

## Environment Variables

Set these environment variables to configure credentials:

| Variable | Description | Required |
|----------|-------------|----------|
| `MP_USERNAME` | Service account username | Yes |
| `MP_SECRET` | Service account secret | Yes |
| `MP_PROJECT_ID` | Mixpanel project ID | Yes |
| `MP_REGION` | Data residency region (`us`, `eu`, `in`) | No (default: `us`) |
| `MP_CONFIG_PATH` | Override config file location | No |
| `MP_ACCOUNT` | Account name to use from config file | No |

Example:

```bash
export MP_USERNAME="sa_abc123..."
export MP_SECRET="your-secret-here"
export MP_PROJECT_ID="12345"
export MP_REGION="us"
```

## Config File

For persistent credential storage, use the config file at `~/.mp/config.toml`:

```toml
default = "production"

[accounts.production]
username = "sa_abc123..."
secret = "..."
project_id = "12345"
region = "us"

[accounts.staging]
username = "sa_xyz789..."
secret = "..."
project_id = "67890"
region = "eu"

[accounts.development]
username = "sa_dev456..."
secret = "..."
project_id = "11111"
region = "us"
```

### Managing Accounts with CLI

Add a new account:

```bash
# Interactive prompt (secure, recommended)
mp auth add production \
    --username sa_abc123... \
    --project 12345 \
    --region us
# You'll be prompted for the secret with hidden input
```

For CI/CD environments, provide the secret via environment variable or stdin:

```bash
# Via environment variable
MP_SECRET=your-secret mp auth add production --username sa_abc123... --project 12345

# Via stdin
echo "$SECRET" | mp auth add production --username sa_abc123... --project 12345 --secret-stdin
```

List configured accounts:

```bash
mp auth list
```

Switch the default account:

```bash
mp auth switch staging
```

Remove an account:

```bash
mp auth remove development
```

Show account details (secrets hidden):

```bash
mp auth show production
```

### Managing Accounts with Python

```python
from mixpanel_data.auth import ConfigManager

config = ConfigManager()

# Add account
config.add_account(
    name="production",
    username="sa_abc123...",
    secret="your-secret",
    project_id="12345",
    region="us"
)

# List accounts
accounts = config.list_accounts()
for account in accounts:
    print(f"{account.name}: project {account.project_id} ({account.region})")

# Set default
config.set_default("production")

# Remove account
config.remove_account("old_account")
```

## Credential Resolution Order

When creating a Workspace, credentials are resolved in this order:

1. **Explicit arguments** — `Workspace(project_id=..., region=...)`
2. **Environment variables** — `MP_USERNAME`, `MP_SECRET`, etc.
3. **Named account** — `Workspace(account="staging")` or `MP_ACCOUNT=staging`
4. **Default account** — The account marked as `default` in config.toml

Example showing resolution:

```python
import mixpanel_data as mp

# Uses explicit arguments
ws = mp.Workspace(
    username="sa_...",
    secret="...",
    project_id="12345"
)

# Uses environment variables (if set)
ws = mp.Workspace()

# Uses named account from config file
ws = mp.Workspace(account="staging")
```

## Data Residency Regions

Mixpanel stores data in regional data centers. Use the correct region for your project:

| Region | Code | API Endpoint |
|--------|------|--------------|
| United States | `us` | `mixpanel.com` |
| European Union | `eu` | `eu.mixpanel.com` |
| India | `in` | `in.mixpanel.com` |

!!! warning "Region Mismatch"
    Using the wrong region will result in authentication errors or empty data.

## Workspace Path

By default, the workspace database is stored at `./mixpanel.db`. Override with:

```python
import mixpanel_data as mp

# Custom path
ws = mp.Workspace(path="./data/analytics.db")

# Ephemeral (temporary, auto-deleted)
with mp.Workspace.ephemeral() as ws:
    # ... work with data
# Database deleted on exit
```

For CLI, use the `--db` option:

```bash
mp fetch events --db ./data/my_project.db --from 2025-01-01 --to 2025-01-31
```

## Next Steps

- [Fetching Data](../guide/fetching.md) — Learn about data ingestion
- [API Reference](../api/index.md) — Complete API documentation
