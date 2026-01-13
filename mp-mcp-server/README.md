# mp-mcp-server

MCP (Model Context Protocol) server exposing mixpanel_data analytics capabilities to AI assistants like Claude Desktop.

## Features

- **Schema Discovery**: Explore events, properties, funnels, cohorts, and bookmarks
- **Live Analytics**: Run segmentation, funnel, retention, and JQL queries
- **Data Fetching**: Download events and profiles to local DuckDB storage
- **Local Analysis**: Execute SQL queries against fetched data
- **Guided Workflows**: Prompt templates for common analytics tasks

## Installation

```bash
# From the repository root
pip install ./mp-mcp-server
```

## Quick Start

### 1. Configure Credentials

Set environment variables or create `~/.mp/config.toml`:

```bash
export MP_USERNAME="your-service-account-username"
export MP_SECRET="your-service-account-secret"
export MP_PROJECT_ID="123456"
export MP_REGION="us"  # or "eu", "in"
```

### 2. Configure Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mixpanel": {
      "command": "mp-mcp-server",
      "args": []
    }
  }
}
```

### 3. Restart Claude Desktop

The Mixpanel tools are now available!

## Usage

### CLI Options

```bash
mp-mcp-server --help

# Run with default settings (stdio transport)
mp-mcp-server

# Use a specific account
mp-mcp-server --account production

# Run with HTTP transport
mp-mcp-server --transport http --port 8000
```

### Example Conversations

**Schema Discovery:**
- "What events are tracked in my Mixpanel project?"
- "Show me the properties for the signup event"
- "List my saved funnels"

**Live Analytics:**
- "How many logins happened each day last week?"
- "What's the conversion rate for my signup funnel?"
- "Show day-7 retention for users who signed up last month"

**Local Analysis:**
- "Fetch events from January 1-7"
- "Count events by name"
- "Find the top 10 users by event count"

## Available Tools

### Discovery (9 tools)
- `list_events` - List all tracked events
- `list_properties` - Get properties for an event
- `list_property_values` - Get sample values for a property
- `list_funnels` - List saved funnels
- `list_cohorts` - List saved cohorts
- `list_bookmarks` - List saved reports
- `top_events` - Get most active events
- `workspace_info` - Get workspace configuration

### Live Query (9 tools)
- `segmentation` - Time series event analysis
- `funnel` - Conversion funnel analysis
- `retention` - User retention analysis
- `jql` - Execute JQL scripts
- `event_counts` - Count multiple events
- `property_counts` - Property value breakdown
- `activity_feed` - User event history
- `frequency` - Event frequency distribution

### Fetch (4 tools)
- `fetch_events` - Download events to local storage
- `fetch_profiles` - Download profiles to local storage
- `stream_events` - Stream events without storing
- `stream_profiles` - Stream profiles without storing

### Local (12 tools)
- `sql` - Execute SQL queries
- `sql_scalar` - Execute SQL returning single value
- `list_tables` - List local tables
- `table_schema` - Get table columns
- `sample` - Get sample rows
- `summarize` - Get table statistics
- `event_breakdown` - Count events by name
- `property_keys` - Extract property keys
- `column_stats` - Get column statistics
- `drop_table` - Remove a table
- `drop_all_tables` - Remove all tables

## Resources

Static data accessible via MCP resources:

- `workspace://info` - Workspace configuration
- `workspace://tables` - Local table list
- `schema://events` - Event list
- `schema://funnels` - Funnel definitions
- `schema://cohorts` - Cohort definitions
- `schema://bookmarks` - Saved reports

## Prompts

Guided workflow templates:

- `analytics_workflow` - Complete analytics exploration guide
- `funnel_analysis` - Funnel conversion analysis workflow
- `retention_analysis` - User retention analysis workflow
- `local_analysis_workflow` - Local SQL analysis guide

## Development

```bash
# Install with dev dependencies
pip install -e "./mp-mcp-server[dev]"

# Run tests
pytest mp-mcp-server/tests/

# Run with coverage
pytest mp-mcp-server/tests/ --cov=mp_mcp_server
```

## License

MIT
