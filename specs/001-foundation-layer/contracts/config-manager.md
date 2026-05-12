# Contract: ConfigManager

**Type**: Internal Python Interface
**Module**: `mixpanel_data._internal.config`
**Public Access**: Via `mixpanel_data.auth` module

## Interface Definition

```python
class ConfigManager:
    """Manages Mixpanel project credentials and configuration."""

    def __init__(self, config_path: Path | None = None) -> None:
        """
        Initialize ConfigManager.

        Args:
            config_path: Override config file location.
                         Default: ~/.mp/config.toml
        """
        ...

    def resolve_credentials(self, account: str | None = None) -> Credentials:
        """
        Resolve credentials using priority order.

        Resolution order:
        1. Environment variables (MP_USERNAME, MP_SECRET, MP_PROJECT_ID, MP_REGION)
        2. Named account from config file (if account parameter provided)
        3. Default account from config file

        Args:
            account: Optional account name to use instead of default.

        Returns:
            Credentials: Immutable credentials object.

        Raises:
            ConfigError: If no credentials can be resolved.
            AccountNotFoundError: If named account doesn't exist.
        """
        ...

    def list_accounts(self) -> list[AccountInfo]:
        """
        List all configured accounts.

        Returns:
            List of AccountInfo objects (secrets not included).
        """
        ...

    def add_account(
        self,
        name: str,
        username: str,
        secret: str,
        project_id: str,
        region: str,
    ) -> None:
        """
        Add a new account configuration.

        Args:
            name: Display name for the account.
            username: Service account username.
            secret: Service account secret.
            project_id: Mixpanel project ID.
            region: Data residency region (us, eu, in).

        Raises:
            AccountExistsError: If account name already exists.
            ValueError: If region is invalid.
        """
        ...

    def remove_account(self, name: str) -> None:
        """
        Remove an account configuration.

        Args:
            name: Account name to remove.

        Raises:
            AccountNotFoundError: If account doesn't exist.
        """
        ...

    def set_default(self, name: str) -> None:
        """
        Set the default account.

        Args:
            name: Account name to set as default.

        Raises:
            AccountNotFoundError: If account doesn't exist.
        """
        ...

    def get_account(self, name: str) -> AccountInfo:
        """
        Get information about a specific account.

        Args:
            name: Account name.

        Returns:
            AccountInfo object (secret not included).

        Raises:
            AccountNotFoundError: If account doesn't exist.
        """
        ...
```

## Environment Variables

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `MP_USERNAME` | Yes (if using env) | Service account username |
| `MP_SECRET` | Yes (if using env) | Service account secret |
| `MP_PROJECT_ID` | Yes (if using env) | Mixpanel project ID |
| `MP_REGION` | Yes (if using env) | Data residency region |
| `MP_CONFIG_PATH` | No | Override config file path |

## Config File Format

Location: `~/.mp/config.toml`

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
```

## Error Codes

| Code | Exception | Condition |
| ---- | --------- | --------- |
| `CONFIG_ERROR` | ConfigError | Generic configuration error |
| `ACCOUNT_NOT_FOUND` | AccountNotFoundError | Named account doesn't exist |
| `ACCOUNT_EXISTS` | AccountExistsError | Account name already in use |

## Usage Examples

```python
from mixpanel_data._internal.config import ConfigManager

# Default initialization
config = ConfigManager()

# With custom path
config = ConfigManager(config_path=Path("/custom/config.toml"))

# Resolve credentials (uses env vars or config file)
creds = config.resolve_credentials()

# Resolve specific account
creds = config.resolve_credentials(account="staging")

# List all accounts
for account in config.list_accounts():
    print(f"{account.name}: {account.project_id}")

# Add new account
config.add_account(
    name="development",
    username="sa_dev...",
    secret="secret123",
    project_id="99999",
    region="us",
)

# Set as default
config.set_default("development")
```

## Testing Contract

```python
def test_resolve_credentials_env_takes_precedence(config, monkeypatch):
    """Environment variables should override config file."""
    monkeypatch.setenv("MP_USERNAME", "env_user")
    monkeypatch.setenv("MP_SECRET", "env_secret")
    monkeypatch.setenv("MP_PROJECT_ID", "env_project")
    monkeypatch.setenv("MP_REGION", "eu")

    creds = config.resolve_credentials()

    assert creds.username == "env_user"
    assert creds.region == "eu"


def test_add_account_raises_if_exists(config):
    """Adding duplicate account should raise AccountExistsError."""
    config.add_account("test", "user", "secret", "123", "us")

    with pytest.raises(AccountExistsError):
        config.add_account("test", "user2", "secret2", "456", "eu")


def test_credentials_secret_not_in_repr(config):
    """Secret must never appear in string representation."""
    creds = config.resolve_credentials()

    assert creds.secret.get_secret_value() not in repr(creds)
    assert creds.secret.get_secret_value() not in str(creds)
```
