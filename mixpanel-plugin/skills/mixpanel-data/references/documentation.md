# Documentation Reference

Complete guide to accessing mixpanel_data documentation programmatically.

## Base URL

```
https://jaredmcfarland.github.io/mixpanel_data/
```

## LLM-Optimized Endpoints

### llms.txt (Index)

```
https://jaredmcfarland.github.io/mixpanel_data/llms.txt
```

A structured index file (~3KB) containing:
- Project name and description
- Section headers (Getting Started, User Guide, API Reference, CLI Reference, Architecture)
- Links to each documentation page with descriptions
- URLs point to markdown files for direct LLM consumption

**When to fetch:** To discover what documentation exists or find the right page for a topic.

### llms-full.txt (Complete Documentation)

```
https://jaredmcfarland.github.io/mixpanel_data/llms-full.txt
```

Complete documentation (~400KB, ~15,000 lines) containing:
- All user guide content
- Full API reference with method signatures and docstrings
- CLI command documentation with all options
- Architecture documentation

**When to fetch:** When you need comprehensive information about multiple topics or want to search across all documentation.

## Individual Markdown Pages

Each HTML page has a corresponding `.md` file at the same path:

```
HTML: https://jaredmcfarland.github.io/mixpanel_data/guide/fetching/
MD:   https://jaredmcfarland.github.io/mixpanel_data/guide/fetching/index.md
```

### Complete Page List

#### Getting Started
| Page | URL | Content |
|------|-----|---------|
| Home | `/index.md` | Project overview, key concepts |
| Installation | `/getting-started/installation/index.md` | pip/uv installation, optional dependencies |
| Quick Start | `/getting-started/quickstart/index.md` | First queries in 5 minutes |
| Configuration | `/getting-started/configuration/index.md` | Credentials, environment variables, config files |

#### User Guide
| Page | URL | Content |
|------|-----|---------|
| Fetching Data | `/guide/fetching/index.md` | fetch_events, fetch_profiles, options |
| Streaming Data | `/guide/streaming/index.md` | stream_events, stream_profiles, pipelines |
| Local SQL Queries | `/guide/sql-queries/index.md` | DuckDB SQL, JSON operators, patterns |
| Live Analytics | `/guide/live-analytics/index.md` | Segmentation, funnels, retention, JQL |
| Data Discovery | `/guide/discovery/index.md` | Schema exploration, events, properties |

#### API Reference
| Page | URL | Content |
|------|-----|---------|
| Overview | `/api/index.md` | Import patterns, public API |
| Workspace | `/api/workspace/index.md` | Full Workspace class reference |
| Auth | `/api/auth/index.md` | Authentication, ConfigManager |
| Exceptions | `/api/exceptions/index.md` | Exception hierarchy, error handling |
| Result Types | `/api/types/index.md` | FetchResult, SegmentationResult, etc. |

#### CLI Reference
| Page | URL | Content |
|------|-----|---------|
| Overview | `/cli/index.md` | CLI structure, global options |
| Commands | `/cli/commands/index.md` | Complete command reference |

#### Architecture
| Page | URL | Content |
|------|-----|---------|
| Design | `/architecture/design/index.md` | Layered architecture, services |
| Data Model | `/architecture/data-model/index.md` | Event/profile schema |
| Storage Engine | `/architecture/storage/index.md` | DuckDB storage details |

## Fetch Strategy

### Quick Questions
Use the skill's quick reference for:
- Common code patterns
- Basic API method signatures
- CLI command examples
- Error solutions

### Detailed Implementation
Fetch individual `.md` pages for:
- Full method signatures with all parameters
- Edge case handling
- Complete option descriptions
- Detailed examples

### Comprehensive Search
Fetch `llms-full.txt` when:
- Searching for specific functionality across the library
- Need complete context for complex implementation
- Debugging obscure issues
- Understanding the full API surface

## Example: Fetching Documentation

Using WebFetch tool:

```
# Get the index to find relevant pages
WebFetch(url="https://jaredmcfarland.github.io/mixpanel_data/llms.txt",
         prompt="Find pages related to funnel analysis")

# Get specific page for details
WebFetch(url="https://jaredmcfarland.github.io/mixpanel_data/guide/live-analytics/index.md",
         prompt="Extract the funnel() method signature and all parameters")

# Get complete docs for comprehensive search
WebFetch(url="https://jaredmcfarland.github.io/mixpanel_data/llms-full.txt",
         prompt="Find all methods that accept a where parameter")
```

## Documentation Content Types

### User Guide Pages
- Conceptual explanations
- Step-by-step tutorials
- Code examples with context
- Best practices

### API Reference Pages
- Complete method signatures extracted from source
- Docstrings with Args, Returns, Raises sections
- Type annotations
- Source code links

### CLI Reference
- Auto-generated from Typer CLI app
- All commands with options
- Output format examples
