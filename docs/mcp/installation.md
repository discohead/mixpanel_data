# Installation & Configuration

Set up the MCP server for use with Claude Desktop or other MCP clients.

!!! tip "Explore on DeepWiki"
    🤖 **[Installation Guide →](https://deepwiki.com/jaredmcfarland/mixpanel_data/3.4.1-mcp-server-setup)**

    Get help with configuration, troubleshoot setup issues, or explore advanced options.

## Prerequisites

- Python 3.10 or later
- A Mixpanel service account with API access
- An MCP client (e.g., Claude Desktop)

## Installation

### From PyPI

```bash
pip install mp_mcp
```

### From Repository

```bash
# Clone the repository
git clone https://github.com/jaredmcfarland/mixpanel_data.git
cd mixpanel_data

# Install the MCP server
pip install ./mp_mcp
```

### With uv

```bash
uv pip install mp_mcp
```

### Verify Installation

```bash
mp_mcp --version
```

## Credential Configuration

The MCP server uses the same credential system as the `mixpanel_data` library. Configure credentials using environment variables or a config file.

### Option 1: Environment Variables

```bash
export MP_USERNAME="your-service-account-username"
export MP_SECRET="your-service-account-secret"
export MP_PROJECT_ID="123456"
export MP_REGION="us"  # us, eu, or in
```

| Variable        | Description                              |
| --------------- | ---------------------------------------- |
| `MP_USERNAME`   | Service account username                 |
| `MP_SECRET`     | Service account secret                   |
| `MP_PROJECT_ID` | Mixpanel project ID                      |
| `MP_REGION`     | Data residency region (`us`, `eu`, `in`) |

### Option 2: Config File

Create `~/.mp/config.toml`:

```toml
[default]
username = "your-service-account-username"
secret = "your-service-account-secret"
project_id = 123456
region = "us"

[production]
username = "prod-service-account"
secret = "prod-secret"
project_id = 789012
region = "eu"
```

Use a specific account with the `--account` flag:

```bash
mp_mcp --account production
```

## Claude Desktop Configuration

### macOS

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mixpanel": {
      "command": "mp_mcp",
      "args": []
    }
  }
}
```

### With Specific Account

```json
{
  "mcpServers": {
    "mixpanel": {
      "command": "mp_mcp",
      "args": ["--account", "production"]
    }
  }
}
```

### With Environment Variables

```json
{
  "mcpServers": {
    "mixpanel": {
      "command": "mp_mcp",
      "env": {
        "MP_USERNAME": "your-username",
        "MP_SECRET": "your-secret",
        "MP_PROJECT_ID": "123456",
        "MP_REGION": "us"
      }
    }
  }
}
```

### Windows

Edit `%APPDATA%\Claude\claude_desktop_config.json` with the same structure.

## CLI Options

```bash
mp_mcp --help
```

| Option        | Description                      | Default   |
| ------------- | -------------------------------- | --------- |
| `--account`   | Account name from config file    | `default` |
| `--transport` | Transport type (`stdio`, `sse`) | `stdio`   |
| `--port`      | Port for SSE transport          | `8000`    |
| `--help`      | Show help and exit               | —         |

### Transport Options

**stdio (default)** — Standard input/output, used by Claude Desktop:

```bash
mp_mcp
```

**SSE** — HTTP Server-Sent Events for custom integrations:

```bash
mp_mcp --transport sse --port 8000
```

## Multi-Account Setup

Configure multiple Mixpanel accounts and switch between them:

```toml
# ~/.mp/config.toml

[default]
username = "dev-account"
secret = "dev-secret"
project_id = 111111
region = "us"

[staging]
username = "staging-account"
secret = "staging-secret"
project_id = 222222
region = "us"

[production]
username = "prod-account"
secret = "prod-secret"
project_id = 333333
region = "eu"
```

Run separate MCP server instances for each environment, or use the `--account` flag.

## Verification

### Test Credentials

Use the CLI to verify your credentials work:

```bash
# Using environment variables
mp auth test

# Using a specific account
mp auth test --account production
```

### Test MCP Server

Run the server directly to check for errors:

```bash
mp_mcp
```

The server should start without errors and wait for input. Press Ctrl+C to exit.

### Check Claude Desktop Logs

If the server isn't appearing in Claude Desktop:

1. Check the Claude Desktop logs for errors
2. Verify the path to `mp_mcp` is in your PATH
3. Ensure the config file is valid JSON
4. Restart Claude Desktop after configuration changes

## Troubleshooting

### "Command not found" Error

The `mp_mcp` command isn't in your PATH. Use the full path:

```json
{
  "mcpServers": {
    "mixpanel": {
      "command": "/path/to/venv/bin/mp_mcp"
    }
  }
}
```

Find the path with:

```bash
which mp_mcp
```

### Authentication Errors

Check that your credentials are valid:

```bash
MP_USERNAME="your-username" MP_SECRET="your-secret" \
MP_PROJECT_ID="123456" MP_REGION="us" \
mp auth test
```

### Rate Limiting

The server includes built-in rate limiting that respects Mixpanel's API limits. If you encounter rate limit errors:

- Query API: 60 requests/hour, 5 concurrent
- Export API: 60 requests/hour, 3/second

The server automatically queues requests when limits are reached.
