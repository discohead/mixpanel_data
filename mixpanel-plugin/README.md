# Mixpanel Data Plugin for Claude Code

Comprehensive Mixpanel analytics integration for Claude Code with interactive commands and automated guidance.

## Features

### 🎯 Slash Commands (User-Invoked)

**`/mp-auth [account-name] [list|switch|test]`**
- Interactive wizard for authentication and account management
- Setup: Configure credentials with secure secret handling
- List: View all configured accounts
- Switch: Change default account
- Test: Validate credentials and API access
- **Use when**: Managing Mixpanel credentials or switching between projects

**`/mp-inspect [operation] [table-name]`**
- Explore Mixpanel schema and local data structure
- 12 curated operations across 3 categories:
  - Discover Schema: events, properties, funnels, cohorts
  - Explore Local Data: tables, schema, sample, breakdown
  - Analyze Patterns: keys, column, distribution, daily
- Progressive workflow chaining with next-step suggestions
- **Use when**: Discovering available data before queries or understanding schema

**`/mp-fetch [from-date] [to-date] [table-name]`**
- Guided data fetching with validation
- Parallel fetching for large date ranges (up to 10x faster)
- Handles table conflicts (append/replace)
- Optional filters: events, WHERE clauses, limits
- **Use when**: Fetching Mixpanel events into local DuckDB for analysis

**`/mp-query [sql|jql|segmentation|funnel|retention]`**
- Interactive query builder for all query types
- SQL: Query local DuckDB tables
- JQL: JavaScript Query Language for complex transformations
- Live queries: Segmentation, funnels, retention
- **Use when**: Analyzing fetched data or running live queries

**`/mp-funnel [funnel-id]`**
- Interactive funnel analysis wizard
- Supports saved Mixpanel funnels or custom event sequences
- Segmentation and drop-off analysis
- Visualization generation (Python/matplotlib)
- **Use when**: Analyzing conversion funnels and identifying drop-off points

**`/mp-retention [born-event] [return-event]`**
- Comprehensive retention and cohort behavior analysis
- Retention curves with multiple time units
- Cohort behavior comparison
- Time-to-event analysis
- **Use when**: Understanding user retention and cohort behavior

**`/mp-report [funnel|retention|dashboard|custom]`**
- Generate comprehensive analysis reports
- Automated visualizations and insights
- Export to Markdown, PDF, or HTML
- Executive summaries with recommendations
- **Use when**: Creating shareable reports for stakeholders

### 📚 Agent Skill (Auto-Discovered)

**mixpanel-data Skill**
- Automatically activates when you mention Mixpanel, analytics, or data queries
- Provides comprehensive guidance on:
  - Library API (Python)
  - CLI commands (mp)
  - Query expressions (filter syntax, JQL)
  - Integration patterns (pandas, jq, Unix pipelines)
  - Documentation access (llms.txt)
- **Progressive disclosure**: Core concepts in SKILL.md, detailed references loaded as needed

### 🤖 Subagents (Auto-Invoked)

Specialized AI analysts that Claude invokes automatically for deep analysis workflows:

**mixpanel-analyst** - General-purpose data analyst
- Triggered: When user asks about Mixpanel data analysis, event analytics, user behavior
- Expertise: SQL queries, JQL scripts, data interpretation, insights generation
- Tools: Read, Write, Bash, Grep, Glob
- **Use when**: "Analyze my purchase events", "What's driving user engagement?"

**funnel-optimizer** - Conversion funnel specialist
- Triggered: Questions about conversion rates, funnel analysis, drop-off points, user journeys
- Expertise: Funnel segmentation, time-to-convert, drop-off analysis, CRO recommendations
- Tools: Read, Write, Bash
- **Use when**: "Why are users dropping off?", "Optimize my signup funnel"

**retention-specialist** - Cohort and retention expert
- Triggered: Questions about retention rates, churn, cohort behavior, user stickiness
- Expertise: Retention curves, cohort comparison, LTV indicators, sticky features
- Tools: Read, Write, Bash
- **Use when**: "What's our Day 7 retention?", "Which cohorts have best retention?"

**jql-expert** - JQL query builder
- Triggered: Complex transformations, user-level analysis, advanced JQL needs
- Expertise: JQL syntax, reducers, joins, custom aggregations, performance optimization
- Tools: Read, Write, Bash
- **Use when**: "Build a JQL query for...", "How do I calculate average events per user?"

**How it works:**
1. You ask a question or request analysis
2. Claude determines which specialist is best suited
3. The subagent runs autonomously in its own context
4. Results are returned to the main conversation
5. You can explicitly invoke: "Use the funnel-optimizer to analyze my checkout flow"

## Installation

### For End Users

Install directly from GitHub:

```bash
/plugin marketplace add jaredmcfarland/mixpanel_data
/plugin install mixpanel-data
```

Then restart Claude Code.

### For Development/Testing

Use the local marketplace from the repository root:

```bash
/plugin marketplace add /path/to/mixpanel_data
/plugin install mixpanel-data
```

Restart Claude Code to load the plugin.

**For detailed distribution strategies, release workflows, and troubleshooting, see [DISTRIBUTION.md](DISTRIBUTION.md)**

## Quick Start

### 1. Configure Credentials

```bash
claude
> /mp-auth production
```

Follow the interactive wizard to enter:
- Mixpanel service account username
- Service account secret
- Project ID
- Region (us, eu, in)

### 2. Explore Schema (Optional)

```bash
> /mp-inspect
```

Discover available events, properties, and saved funnels before fetching data.

### 3. Fetch Data

```bash
> /mp-fetch 2024-01-01 2024-01-31 events
```

This fetches January 2024 events into a table named "events".

### 4. Query Data

```bash
> /mp-query sql
```

Choose from suggested queries or build custom SQL/JQL.

### 5. Auto-Guidance

Just ask questions naturally:
```
"How do I analyze purchase events from Mixpanel?"
"What's the revenue by country?"
"Show me user retention curves"
```

The skill activates automatically to guide you.

## Component Breakdown

### Commands (7 files, 2,521 lines)

#### Phase 1: Essential Commands (1,176 lines)
| Command | Lines | Purpose |
|---------|-------|---------|
| `/mp-auth` | 242 | Authentication and account management |
| `/mp-fetch` | 162 | Data fetching with validation |
| `/mp-query` | 334 | Interactive query builder (SQL/JQL/live queries) |
| `/mp-inspect` | 438 | Schema and data exploration |

#### Phase 2: Analysis Commands (1,345 lines)
| Command | Lines | Purpose |
|---------|-------|---------|
| `/mp-funnel` | 339 | Conversion funnel analysis with visualizations |
| `/mp-retention` | 428 | Retention and cohort behavior analysis |
| `/mp-report` | 578 | Comprehensive report generator |

### Skill (1 directory)

- **SKILL.md** (246 lines): Core concepts, quick reference
- **references/** (5 files, 2,179 lines):
  - `library-api.md` - Complete Python API reference
  - `cli-commands.md` - Full CLI documentation
  - `query-expressions.md` - Filter expressions & JQL
  - `patterns.md` - Integration patterns (pandas, jq)
  - `documentation.md` - External docs access

### Subagents (4 files)

| Agent | Lines | Specialization |
|-------|-------|----------------|
| `mixpanel-analyst.md` | 362 | General-purpose data analysis (SQL, JQL, insights) |
| `funnel-optimizer.md` | 382 | Conversion funnel analysis and optimization |
| `retention-specialist.md` | 448 | Cohort retention and engagement analysis |
| `jql-expert.md` | 521 | Advanced JQL query building and optimization |

**Total: 1,713 lines** of specialized analysis expertise

## Usage Patterns

### Pattern 1: Quick Setup → Fetch → Analyze

```bash
/mp-auth production
/mp-fetch 2024-01-01 2024-01-31 jan
/mp-query sql
```

### Pattern 2: Guided Discovery

```
User: "I want to analyze Mixpanel purchase events"
Claude: [Activates skill automatically]
        "First, let's configure credentials with /mp-auth..."
```

### Pattern 3: Advanced Analysis

```bash
# Fetch specific events with filters
/mp-fetch 2024-01-01 2024-01-31 purchases --events "Purchase" --where 'properties["amount"] > 100'

# Build complex JQL query
/mp-query jql

# Or ask for help
User: "Help me build a funnel analysis for signup → purchase"
```

## Design Philosophy

### Commands = Actions (Explicit Control)

Slash commands give users **explicit control** over operations:
- `/mp-auth` → "Configure credentials NOW"
- `/mp-inspect` → "Explore schema NOW"
- `/mp-fetch` → "Fetch data NOW"
- `/mp-query` → "Query data NOW"

### Skill = Knowledge (Auto-Discovery)

The skill provides **automatic guidance** when needed:
- Mentions "Mixpanel" → Skill activates
- Asks about "analytics" → Skill provides context
- References "JQL" → Skill loads query expression docs

### Progressive Disclosure

All components minimize context usage:
- **Commands**: Load only when invoked
- **Skill**: Core in SKILL.md, detailed references loaded as needed
- **Subagents**: Run in separate context, return only results
- **Result**: Maximum context for conversation, minimal bloat

## Development

### Structure

```
mixpanel-plugin/
├── .claude-plugin/
│   └── plugin.json               # Plugin metadata
├── commands/                      # Slash commands (user-invoked)
│   ├── mp-auth.md
│   ├── mp-fetch.md
│   ├── mp-funnel.md
│   ├── mp-inspect.md
│   ├── mp-query.md
│   ├── mp-report.md
│   └── mp-retention.md
├── agents/                        # Subagents (auto-invoked)
│   ├── mixpanel-analyst.md       # General data analyst
│   ├── funnel-optimizer.md       # Conversion specialist
│   ├── retention-specialist.md   # Retention expert
│   └── jql-expert.md             # JQL query builder
└── skills/                        # Agent Skills (auto-discovered)
    └── mixpanel-data/
        ├── SKILL.md
        └── references/
            ├── cli-commands.md
            ├── documentation.md
            ├── library-api.md
            ├── patterns.md
            └── query-expressions.md
```

### Testing

```bash
# Verify plugin loads
claude --debug

# Test commands
/help  # Should show /mp-auth, /mp-inspect, /mp-fetch, /mp-query, /mp-funnel, /mp-retention, /mp-report

# Test skill activation
"What skills are available?"  # Should show mixpanel-data

# Test functionality
/mp-auth test
```

## Requirements

- Claude Code 1.0+
- `mixpanel_data` Python library installed (`pip install mixpanel_data`)
- Mixpanel service account credentials

## Roadmap

### ✅ Phase 1: Essential Commands (Complete)
- `/mp-auth` - Authentication and account management
- `/mp-inspect` - Schema and data exploration
- `/mp-fetch` - Data fetching
- `/mp-query` - Query builder

### ✅ Phase 2: Analysis Commands (Complete)
- `/mp-funnel` - Funnel analysis
- `/mp-retention` - Retention analysis
- `/mp-report` - Report generation

### ✅ Phase 3: Subagents (Complete)
- **mixpanel-analyst** - General-purpose data analyst (SQL, JQL, insights)
- **funnel-optimizer** - Conversion funnel specialist
- **retention-specialist** - Cohort and retention analysis expert
- **jql-expert** - Advanced JQL query builder

### 🚀 Phase 4: Future Components
Consider adding:
1. **MCP Server** - Expose Mixpanel data as structured tools for other agents
2. **Hooks** - Pre-commit validation for queries/scripts, session-start credential checks

## License

See project repository for license information.

## Links

- [mixpanel_data Documentation](https://jaredmcfarland.github.io/mixpanel_data/)
- [GitHub Repository](https://github.com/jaredmcfarland/mixpanel_data)
- [Claude Code Plugins](https://docs.claude.com/en/docs/claude-code/plugins)
