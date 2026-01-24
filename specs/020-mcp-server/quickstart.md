# Quickstart: MCP Server for mixpanel_data

Get up and running with the Mixpanel MCP server in 5 minutes.

## Prerequisites

- Python 3.10+
- Mixpanel service account credentials
- Claude Desktop (or another MCP-compatible client)

## Installation

```bash
# Clone the repository (if not already done)
git clone https://github.com/your-org/mixpanel_data.git
cd mixpanel_data

# Install the MCP server package
pip install ./mp_mcp
```

## Configuration

### Step 1: Set up Mixpanel credentials

Choose one of these methods:

**Option A: Environment variables**

```bash
export MP_USERNAME="your-service-account-username"
export MP_SECRET="your-service-account-secret"
export MP_PROJECT_ID="123456"
export MP_REGION="us"  # or "eu", "in"
```

**Option B: Configuration file**

```bash
mkdir -p ~/.mp
cat > ~/.mp/config.toml << 'EOF'
[default]
username = "your-service-account-username"
secret = "your-service-account-secret"
project_id = 123456
region = "us"
EOF
```

### Step 2: Configure Claude Desktop

Add the MCP server to your Claude Desktop configuration:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

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

For named accounts:

```json
{
  "mcpServers": {
    "mixpanel-prod": {
      "command": "mp_mcp",
      "args": ["--account", "production"]
    }
  }
}
```

### Step 3: Restart Claude Desktop

Restart Claude Desktop to load the new MCP server configuration.

## Verify Installation

Ask Claude: **"What events are tracked in my Mixpanel project?"**

You should see a list of event names from your Mixpanel project.

## Example Conversations

### Schema Discovery

```
You: What events do I have in Mixpanel?
Claude: [Lists all events alphabetically]

You: What properties does the "signup" event have?
Claude: [Lists properties with their types]

You: Show me my saved funnels
Claude: [Lists funnels with names and step counts]
```

### Live Analytics

```
You: How many logins happened each day last week?
Claude: [Runs segmentation query, shows daily counts]

You: What's the conversion rate for my checkout funnel?
Claude: [Queries funnel, shows step-by-step conversion]

You: What's day-7 retention for users who signed up last month?
Claude: [Runs retention analysis, shows cohort curves]
```

### Local Data Analysis

```
You: Fetch events from January 1-7
Claude: [Downloads events to local DuckDB]

You: Show me a sample of the data
Claude: [Displays random rows]

You: Count events by name
Claude: [Runs SQL, shows event distribution]

You: Find the top 10 users by event count
Claude: [Writes and executes SQL query]
```

## Troubleshooting

### "Authentication failed"

- Verify your credentials are correct
- Check that the service account has access to the project
- Ensure `MP_PROJECT_ID` matches your project

### "Rate limit exceeded"

- Wait for the retry period (indicated in error message)
- Consider using smaller date ranges for queries
- Use `parallel=true` for large data fetches

### "Table already exists"

- The server won't overwrite existing tables
- Use `drop_table` to remove the old table first
- Or use a different table name

### Server not appearing in Claude Desktop

- Verify the config file path is correct
- Check that `mp_mcp` is in your PATH
- Look at Claude Desktop logs for errors

## Next Steps

- Explore the [full tool reference](contracts/) for all available capabilities
- Try the guided workflows: ask Claude to "run the analytics workflow"
- Fetch data locally for complex SQL analysis
- Set up multiple accounts for different Mixpanel projects
