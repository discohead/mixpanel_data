# mixpanel_data — Project Brief

> A foundational Python library for working with Mixpanel data, designed for AI coding agents.

**Date:** December 2024  
**Author:** Jared Stenquist  
**Status:** Design phase

---

## The Problem

AI coding agents (Claude Code, Cursor, Codex, etc.) are becoming powerful tools for data analysis. When these agents interact with Mixpanel data via the existing MCP server, every API response consumes context window tokens. A single query might return 30KB of JSON—tokens that could otherwise be used for reasoning, insight generation, and iterative exploration.

The context window is the agent's working memory. Filling it with raw data leaves less room for thinking.

## The Insight

What if agents could fetch data once, store it locally, and then query it repeatedly without consuming additional context? The heavy data lives outside the context window; only the precise answers flow back in.

This is how humans work with data—we load it into a database or DataFrame, explore it, query it from multiple angles, and iterate. The agent should work the same way.

## The Vision

`mixpanel_data` is a **foundational layer** for working with Mixpanel data. It provides:

1. **A local data store** — Fetch events and user data from Mixpanel, store them in an embedded analytical database (DuckDB), query them with SQL
2. **Live query access** — Run Mixpanel reports (segmentation, funnels, retention) directly when fresh data is needed
3. **Data discovery** — Introspect what events, properties, and values exist before writing queries
4. **A Python library** — Import and use programmatically for complex analysis
5. **A CLI** — Compose into unix pipelines, invoke from agents without writing Python

The library is the foundation; the CLI is a thin layer on top.

---

## Design Principles

### 1. Library-First

The CLI is just one interface to the library. Every capability should be accessible programmatically:

```python
import mixpanel_data as mp

mp.fetch_events(from_date="2024-01-01")
df = mp.query_df("SELECT * FROM events")
```

The CLI wraps library functions with argument parsing and output formatting—nothing more.

### 2. Agent-Native

Every command must be non-interactive. Agents cannot type into REPLs or respond to prompts. Commands take inputs, produce outputs, and exit.

Output should be structured (JSON, CSV) and composable into unix pipelines:

```bash
mp query "SELECT ..." --format json | jq '...' | other-tool
```

### 3. Context Window Efficiency

The primary goal is preserving agent context for reasoning. This means:

- Fetch data once, store locally, query many times
- Return precise answers, not raw dumps
- Provide introspection commands so agents can understand data shape before querying
- Support output formats that minimize tokens while preserving information

### 4. Two Data Paths

Not every question needs local storage. Quick answers should be quick:

- **Live queries**: Call Mixpanel API, get answer, done (like the MCP server)
- **Local analysis**: Fetch → store → query → iterate (unique to this tool)

The tool should make it easy to choose the right path for each task.

### 5. Unix Philosophy

Do one thing well. Compose with other tools. Output clean data. Exit with meaningful codes.

The tool doesn't need to do everything—it needs to integrate well with the ecosystem of tools agents already use (jq, pandas, SQL, etc.).

### 6. Escape Hatches

When the abstractions don't fit, users should be able to drop down:

- Raw API access when structured commands don't cover an endpoint
- Direct database access for humans (interactive shell)
- Python library for analysis too complex for CLI commands
- Notebook generation for interactive human exploration

---

## Goals

1. **Enable agents to do real Mixpanel analysis** — Funnels, retention, user behavior, without consuming context on raw data

2. **Preserve context window for reasoning** — Data lives in local DB; only answers enter context

3. **Support both quick answers and deep exploration** — Live queries for simple questions; local DB for complex analysis

4. **Be a foundation others can build on** — Clean library API that plugins, notebooks, and other tools can leverage

5. **Teach agents via a Skill** — A `SKILL.md` that makes agents expert users without the tool itself being complex

## Non-Goals (for initial version)

1. **Plugin system** — Architecture should support it, but not implement it yet

2. **Visualization** — Output is data; visualization is for other tools (notebooks, marimo, etc.)

3. **Write operations** — This is read-only; no sending events or modifying Mixpanel data

4. **Real-time streaming** — Batch fetch, not live event streams

5. **Replacing Mixpanel UI** — This is for programmatic access, not a dashboard replacement

---

## Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | DuckDB/Pandas ecosystem, data science tooling |
| CLI Framework | Typer | Type hints, minimal boilerplate, auto-generated help |
| Output Formatting | Rich | Tables, progress bars, colors |
| Validation | Pydantic | API response validation, settings management |
| Database | DuckDB | Embedded, analytical, excellent JSON support, no server process |
| HTTP Client | httpx | Async support, modern API |

**Why DuckDB over SQLite or NoSQL:**
- Columnar storage optimized for analytical queries (GROUP BY, aggregations)
- Native JSON support with SQL syntax for querying nested properties
- Can query DataFrames directly, seamless pandas integration
- Single file, no server, easy to manage

**Why Python:**
- First-class DuckDB bindings
- Pandas/Polars integration for complex analysis
- Agents can write Python scripts that import the library directly
- Rich ecosystem for data science and ML

---

## Core Concepts

### Projects

A Mixpanel project is identified by a token. Users may have access to multiple projects (production, staging, etc.). The tool should support:

- Storing credentials for multiple projects
- Switching between projects
- Overriding via environment variables (for CI/automation)

### Local Database

Events and user data fetched from Mixpanel are stored in DuckDB. Key considerations:

- **Where do databases live?** Per-project? Per-workspace? Configurable?
- **How long do they persist?** Forever? TTL? Manual cleanup?
- **Can agents request ephemeral databases?** Fetch, analyze, discard?
- **What's the schema?** Flatten properties? Store as JSON? Both?

### Data Fetching

The Mixpanel Export API returns raw events. Considerations:

- **Incremental fetching** — Append new data or replace?
- **Filtering** — By event name, date range, properties?
- **Rate limiting** — How to handle API limits gracefully?
- **Progress reporting** — How to communicate progress for large fetches?

### Querying

Two types of queries:

1. **Local SQL** — Query the DuckDB database directly
2. **Live Mixpanel queries** — Call Mixpanel's Query API (segmentation, funnels, etc.)

For local queries:
- How do users query JSON properties?
- What output formats are needed?
- Should results be cacheable?

For live queries:
- How closely should we mirror Mixpanel's API?
- Should results optionally be saved to the local DB?

### Data Discovery

Agents need to understand data shape before querying:

- What events exist?
- What properties does an event have?
- What values appear for a property?
- What's in the local database? Schema? Row counts?

### Notebooks

The library should work in any notebook environment. Additionally:

- **Jupyter** — Generate starter notebooks with mp pre-configured
- **marimo** — Generate reactive Python apps for interactive exploration

marimo is particularly interesting because:
- Stored as pure Python (Git-friendly, agent-editable)
- Reactive cells (change input, outputs update automatically)
- Deployable as web apps
- Native SQL support

This could become the "Lens runtime"—interactive data exploration without building custom UI infrastructure.

---

## Open Questions for Design Phase

### API Design

- What's the right balance of convenience methods vs. flexibility?
- How do we name things consistently?
- What's the recommended import pattern? `import mixpanel_data as mp`?
- How do library functions report progress for long operations?
- How do library functions handle errors?

### Data Model

- How do we represent events in DuckDB? Flat columns? JSON blob? Hybrid?
- How do we handle Mixpanel's dynamic properties?
- What metadata do we store about fetches? (date ranges, filters, timestamps)
- How do we track what data is "stale" vs. "fresh"?

### Database Lifecycle

- Default behavior: persistent or ephemeral?
- How do workspaces/namespaces work?
- How does cleanup work? Automatic? Manual? TTL?
- How do we handle concurrent access from multiple agent runs?

### CLI Design

- Command hierarchy: how deep? `mp events fetch` vs `mp fetch-events`?
- Global flags vs. per-command options?
- How verbose is default output? Silent? Progress? Chatty?
- Exit codes: what conventions?

### Skill Design

- What patterns should agents learn?
- When should agents use live queries vs. local DB?
- How do we teach agents about data discovery?
- What common mistakes should the skill prevent?

---

## Relationship to Other Projects

### Mixpanel MCP Server

The existing MCP server calls Mixpanel APIs and returns results directly into the context window. `mixpanel_data` complements this by offering the local database approach. 

We can learn from the MCP server's tool design:
- `run_segmentation_query`, `run_funnels_query`, etc.
- `get_events`, `get_event_properties`, `get_event_property_values`

### Lens

The conceptual "Lens" project envisions AI-generated interactive data visualizations. marimo integration positions `mixpanel_data` as a lightweight path to this vision:

- Agent generates marimo app → Interactive exploration
- No custom infrastructure needed
- Pure Python artifact that's simultaneously script, notebook, and app

### CLI Builder Skill

The `cli-builder` skill provides patterns for building Python CLIs with Typer/Rich. `mixpanel_data` should follow these patterns for consistency.

---

## Success Criteria

### For Agents

An agent should be able to:

1. Discover what data exists in a Mixpanel project
2. Fetch relevant events into a local database
3. Understand the shape of the fetched data
4. Query the data with SQL, getting precise answers
5. Do all of this while preserving context for reasoning

### For Humans

A human should be able to:

1. Use the CLI for quick answers
2. Use the library in scripts and notebooks
3. Generate marimo apps for interactive exploration
4. Trust that the tool handles authentication, rate limits, and data storage correctly

### For the Ecosystem

The tool should:

1. Be installable via pip
2. Work in any Python environment (scripts, notebooks, REPL)
3. Integrate well with pandas, DuckDB, and the Python data ecosystem
4. Be extensible for future plugins and integrations

---

## Next Steps

1. **Design the library API** — Core functions, naming, patterns
2. **Design the data model** — DuckDB schema, metadata, lifecycle
3. **Design the CLI** — Commands, hierarchy, output formats
4. **Build MVP** — Fetch events, store locally, query with SQL
5. **Write the Skill** — Teach agents to use it effectively
6. **Iterate** — Add live queries, data discovery, notebooks

---

*This document captures the spirit and goals of mixpanel_data. Detailed design decisions will be made collaboratively during the development phase.*
