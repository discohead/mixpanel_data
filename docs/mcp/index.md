# MCP Server

Expose mixpanel_data analytics capabilities to AI assistants through the Model Context Protocol (MCP).

!!! tip "Explore on DeepWiki"
    🤖 **[MCP Server Guide →](https://deepwiki.com/jaredmcfarland/mixpanel_data/3.4-mcp-server-integration)**

    Ask questions about tools, explore configuration options, or get help with AI assistant integration.

## Overview

The `mp_mcp` package provides an MCP server that connects AI assistants like Claude Desktop to your Mixpanel analytics. Built on **FastMCP 3.x**, it transforms natural language requests into structured analytics queries.

**Key capabilities:**

- **Account Management** — List, switch, and test Mixpanel account credentials
- **Schema Discovery** — Explore events, properties, funnels, cohorts, Lexicon schemas, and bookmarks
- **Live Analytics** — Run segmentation, funnel, retention, JQL, and numeric aggregation queries
- **Saved Reports** — Execute saved Insights, Retention, Funnel, and Flows reports
- **Data Fetching** — Download events and profiles to local DuckDB storage
- **Local Analysis** — Execute SQL queries against fetched data
- **Intelligent Tools** — AI-powered metric diagnosis and natural language queries
- **Interactive Workflows** — Guided analysis with user confirmation for large operations

## What's New in v2

The MCP Server v2 transforms from a thin API wrapper into an **intelligent analytics platform**:

| Feature                   | Description                                                      |
| ------------------------- | ---------------------------------------------------------------- |
| **Intelligent Tools**     | AI-powered analysis using `ctx.sample()` for synthesis           |
| **Composed Tools**        | Multi-query orchestration (AARRR dashboards, GQM investigations) |
| **Interactive Workflows** | User confirmation via `ctx.elicit()` for large operations        |
| **Progress Reporting**    | Real-time updates for long-running fetches                       |
| **Middleware Layer**      | Caching, rate limiting, and audit logging                        |
| **Graceful Degradation**  | All tools work when sampling/elicitation unavailable             |

## Quick Start

### 1. Install the Server

```bash
pip install mp_mcp
```

Or from the repository:

```bash
pip install ./mp_mcp
```

### 2. Configure Credentials

Set environment variables:

```bash
export MP_USERNAME="your-service-account-username"
export MP_SECRET="your-service-account-secret"
export MP_PROJECT_ID="123456"
export MP_REGION="us"  # or "eu", "in"
```

Or create `~/.mp/config.toml`:

```toml
[default]
username = "your-service-account-username"
secret = "your-service-account-secret"
project_id = 123456
region = "us"
```

### 3. Add to Claude Desktop

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

### 4. Restart Claude Desktop

The Mixpanel tools are now available! Try asking:

- "What events are tracked in my Mixpanel project?"
- "How many logins happened each day last week?"
- "Why did signups drop on January 7th?"

## Tool Tiers

The server organizes tools into tiers based on complexity:

| Tier            | Description                                | MCP Feature    |
| --------------- | ------------------------------------------ | -------------- |
| **Tier 1**      | Primitive tools (direct API calls)         | Standard tools |
| **Tier 2**      | Composed tools (multi-query orchestration) | Standard tools |
| **Tier 3**      | Intelligent tools (AI synthesis)           | `ctx.sample()` |
| **Interactive** | Elicitation workflows                      | `ctx.elicit()` |

See [Tools](tools.md) for the complete reference.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Client                           │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                   Middleware Layer                      │
│  ┌─────────┐  ┌──────────────┐  ┌─────────────────┐     │
│  │ Logging │→ │ Rate Limiting│→ │     Caching     │     │
│  └─────────┘  └──────────────┘  └─────────────────┘     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                     Tool Tiers                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Tier 3: Intelligent (sampling-powered)           │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Tier 2: Composed (multi-query orchestration)     │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Tier 1: Primitive (direct API calls)             │  │
│  └───────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              mixpanel_data.Workspace                    │
│  ┌─────────────┐  ┌────────────────┐  ┌─────────────┐   │
│  │  Discovery  │  │  Live Queries  │  │   Storage   │   │
│  └─────────────┘  └────────────────┘  └─────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                   Mixpanel API                          │
└─────────────────────────────────────────────────────────┘
```

## Next Steps

- [Installation](installation.md) — Detailed setup instructions
- [Tools](tools.md) — Complete tool reference
- [Resources & Prompts](resources.md) — MCP resources and workflow prompts
- [Examples](examples.md) — Example conversations and workflows
