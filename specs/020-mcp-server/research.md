# Research: MCP Server for mixpanel_data

**Date**: 2026-01-12
**Purpose**: Resolve technical unknowns and document design decisions

## Research Topics

### 1. MCP Server Framework Selection

**Decision**: FastMCP 2.0+

**Rationale**:
- High-level decorator-based API (`@mcp.tool`, `@mcp.resource`, `@mcp.prompt`)
- Built-in lifespan management for session state
- Context injection for accessing server state in tools
- In-memory Client for testing without network
- Supports both stdio and HTTP transports
- Official Python SDK integration

**Alternatives Considered**:
- **Raw mcp-python-sdk**: Lower-level, requires more boilerplate for tool registration
- **Custom implementation**: Not justified given FastMCP maturity

**Key FastMCP Patterns**:
```python
# Lifespan for session management
@asynccontextmanager
async def lifespan(mcp: FastMCP):
    workspace = Workspace()
    mcp.state["workspace"] = workspace
    yield
    workspace.close()

# Tool definition with context injection
@mcp.tool
def list_events(ctx: Context) -> list[str]:
    ws = ctx.request_context.lifespan_state["workspace"]
    return ws.events()

# Resource definition
@mcp.resource("schema://events")
def events_resource(ctx: Context) -> str:
    return json.dumps(ws.events())
```

### 2. Package Structure

**Decision**: Separate `mp-mcp-server` package at repository root

**Rationale**:
- Clean separation of concerns (MCP ≠ library)
- Independent versioning and release cycle
- Can be installed without modifying mixpanel_data
- Follows pattern of other MCP servers

**Alternatives Considered**:
- **Subpackage of mixpanel_data**: Would couple MCP to library releases
- **Monorepo workspace**: Overkill for single additional package

**Structure**:
```
mixpanel_data/           # Repository root
├── src/mixpanel_data/   # Existing library
├── mp-mcp-server/       # New MCP server package
│   ├── pyproject.toml
│   └── src/mp_mcp_server/
```

### 3. Session State Management

**Decision**: Server-level Workspace singleton via lifespan pattern

**Rationale**:
- Workspace is expensive to create (DuckDB connection, API client)
- Session state (fetched tables) must persist across tool calls
- MCP sessions are long-lived (conversation duration)
- Lifespan pattern is idiomatic FastMCP

**Alternatives Considered**:
- **Per-tool Workspace**: Would lose session state between calls
- **Global singleton**: Works but lifespan is cleaner
- **Context object storage**: Lifespan is the FastMCP-recommended approach

### 4. Tool Naming Convention

**Decision**: Action-oriented names without service prefix

**Rationale**:
- MCP server is Mixpanel-specific; prefix redundant
- Shorter names reduce token usage
- Consistent with mixpanel_data library method names

**Alternatives Considered**:
- **mixpanel_list_events**: Adds 9 tokens per tool name across 35 tools = 315 extra tokens
- **mp_list_events**: Still adds overhead without clarity

**Naming Pattern**:
| Tool Name | Library Method |
|-----------|---------------|
| `list_events` | `ws.events()` |
| `segmentation` | `ws.segmentation()` |
| `fetch_events` | `ws.fetch_events()` |
| `sql` | `ws.sql_rows()` |

### 5. Error Handling Strategy

**Decision**: Decorator-based exception conversion to ToolError

**Rationale**:
- Centralized error handling logic
- Consistent error format for all tools
- Preserves original exception context
- Includes actionable guidance (e.g., retry timing for rate limits)

**Pattern**:
```python
from fastmcp.exceptions import ToolError

def handle_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RateLimitError as e:
            raise ToolError(
                f"Rate limited. Retry after {e.retry_after}s.",
                details={"retry_after": e.retry_after}
            ) from e
        except MixpanelDataError as e:
            raise ToolError(e.message, details=e.to_dict()) from e
    return wrapper
```

### 6. Resource vs Tool Design

**Decision**: Resources for cacheable schema data; Tools for parameterized queries

**Rationale**:
- Resources are read-only, support caching
- Tools are for operations with parameters
- Schema data (events, funnels, cohorts) changes infrequently
- Query results (segmentation, SQL) depend on parameters

**Resource URIs**:
| URI Pattern | Data Type |
|-------------|-----------|
| `schema://events` | Event name list |
| `schema://funnels` | Saved funnel metadata |
| `schema://properties/{event}` | Properties for specific event |
| `workspace://tables` | Local table list |

### 7. Transport Selection

**Decision**: Support both stdio (default) and HTTP

**Rationale**:
- stdio: Required for Claude Desktop, local development
- HTTP: Required for remote deployment, multi-client scenarios
- Both are well-supported by FastMCP

**CLI Interface**:
```bash
# Default: stdio for Claude Desktop
mp-mcp-server

# HTTP for remote access
mp-mcp-server --transport http --port 8000
```

### 8. Authentication Strategy

**Decision**: Credentials resolved at server startup via environment/config

**Rationale**:
- MCP protocol should not transport credentials
- Reuses existing mixpanel_data credential resolution
- Named accounts supported via `--account` flag
- Secure: credentials never in protocol messages

**Resolution Order**:
1. Environment variables (`MP_USERNAME`, `MP_SECRET`, `MP_PROJECT_ID`)
2. Named account from `~/.mp/config.toml` (via `--account`)
3. Default account from config file

### 9. Testing Strategy

**Decision**: In-memory FastMCP Client for integration tests

**Rationale**:
- No network required
- Fast test execution
- Full protocol compliance testing
- Tests actual tool registration and execution

**Pattern**:
```python
from fastmcp import Client

@pytest.fixture
async def client():
    async with Client(mcp) as client:
        yield client

async def test_list_events(client):
    result = await client.call_tool("list_events", {})
    assert isinstance(result.data, list)
```

## Summary of Decisions

| Topic | Decision | Key Reason |
|-------|----------|------------|
| Framework | FastMCP 2.0+ | Decorator API, lifespan, testing |
| Package | Separate mp-mcp-server | Clean separation |
| Session | Lifespan singleton | State persistence |
| Tool naming | No prefix | Token efficiency |
| Errors | Decorator conversion | Centralized, actionable |
| Resources | Schema data | Cacheable, infrequent changes |
| Transport | stdio + HTTP | Claude Desktop + remote |
| Auth | Server startup | Secure, reuses library |
| Testing | In-memory Client | Fast, protocol-compliant |

## Open Questions

None - all technical decisions resolved.
