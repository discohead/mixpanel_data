# POC: mixpanel_data Integration with Spark AI Copilot

This runbook documents the integration of the `mixpanel_data` library into the Spark AI Copilot via MCP (Model Context Protocol).

## Overview

The integration exposes 39 tools from the `mixpanel_data` library to the Spark AI Copilot, enabling natural language analytics queries directly in the Mixpanel UI.

### Components

| Component | Location | Port | Purpose |
|-----------|----------|------|---------|
| Spark AI Copilot | `/home/jared/analytics/ai/copilot` | 8082 | TypeScript agent using GPT models |
| mp-mcp-server | `/home/jared/analytics/mixpanel_data/mp-mcp-server` | 8200 | FastMCP Python server exposing mixpanel_data tools |
| mixpanel_data | `/home/jared/analytics/mixpanel_data` | - | Python library for Mixpanel analytics |

### Tool Categories (39 total)

- **Discovery (8)**: `list_events`, `list_properties`, `list_property_values`, `list_funnels`, `list_cohorts`, `list_bookmarks`, `top_events`, `workspace_info`
- **Live queries (8)**: `segmentation`, `funnel`, `retention`, `jql`, `event_counts`, `property_counts`, `activity_feed`, `frequency`
- **Fetch (4)**: `fetch_events`, `fetch_profiles`, `stream_events`, `stream_profiles`
- **Local SQL (11)**: `sql`, `sql_scalar`, `list_tables`, `table_schema`, `sample`, `summarize`, `event_breakdown`, `property_keys`, `column_stats`, `drop_table`, `drop_all_tables`
- **Intelligent (3, AI-powered)**: `diagnose_metric_drop`, `ask_mixpanel`, `funnel_optimization_report`
- **High-level (5)**: `cohort_comparison`, `product_health_dashboard`, `gqm_investigation`, plus others

---

## Files Modified

### mp-mcp-server (Python)

| File | Changes |
|------|---------|
| `mp-mcp-server/src/mp_mcp_server/cli.py` | Added `http` transport option for Streamable HTTP |
| `mp-mcp-server/src/mp_mcp_server/server.py` | Added `_INTERNAL_API_HEADERS` for rate limit bypass |

### mixpanel_data library (Python)

| File | Changes |
|------|---------|
| `src/mixpanel_data/_internal/api_client.py` | Added `default_headers` parameter to `MixpanelAPIClient` |
| `src/mixpanel_data/workspace.py` | Added `api_headers` parameter to `Workspace.__init__` |

### Spark AI Copilot (TypeScript)

| File | Changes |
|------|---------|
| `ai/copilot/agent/mcp-client.ts` | Added `getMixpanelDataMCPTools()` function with `@ai-sdk/mcp` client |
| `ai/copilot/server/app.ts` | Merged tools from both MCP servers |
| `ai/copilot/server/index.ts` | Added undici global dispatcher for 10-minute timeout |
| `ai/copilot/generate-env.sh` | Added `MIXPANEL_DATA_MCP_URL` environment variable |

### Kubernetes (for minikube deployment)

| File | Changes |
|------|---------|
| `kube/lib/ai/copilot-server.libsonnet` | Added `MIXPANEL_DATA_MCP_URL` pointing to `host.minikube.internal:8200` |

---

## Development Workflow

### Prerequisites

1. **Mixpanel credentials** in `~/.bashrc`:
   ```bash
   export MP_USERNAME="your-service-account.org-id.mp-service-account"
   export MP_SECRET="your-secret"
   export MP_PROJECT_ID="your-project-id"
   export MP_REGION="us"  # or eu, in
   ```

2. **Test credentials**:
   ```bash
   source ~/.bashrc
   cd /home/jared/analytics/mixpanel_data
   uv run mp auth test
   ```

### Starting the Servers

#### 1. Start mp-mcp-server (Terminal 1)

```bash
source ~/.bashrc
cd /home/jared/analytics/mixpanel_data/mp-mcp-server
unset VIRTUAL_ENV  # Avoid venv conflicts
uv run python -m mp_mcp_server.cli --transport http --port 8200
```

#### 2. Start Copilot dev server (Terminal 2)

```bash
cd /home/jared/analytics/ai/copilot
npm run dev
```

#### 3. Configure nginx to use local copilot (one-time)

Edit `/etc/nginx/sites-enabled/default` to point copilot to localhost instead of minikube:

```nginx
# Change this:
# proxy_pass http://192.168.49.2:30082;

# To this:
proxy_pass http://127.0.0.1:8082;
```

Then reload nginx:
```bash
sudo nginx -s reload
```

### Verifying the Setup

1. **Check both servers are running**:
   ```bash
   lsof -i :8082  # Copilot
   lsof -i :8200  # mp-mcp-server
   ```

2. **Test MCP server health**:
   ```bash
   curl -s -X POST http://localhost:8200/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
   ```
   (Will return an error about Accept headers, but confirms server is responding)

3. **Open Mixpanel in browser** and use Spark Copilot

---

## Monitoring & Debugging

### Log Locations (when running via Claude Code background tasks)

```bash
# Copilot server logs
tail -f /tmp/claude/-home-jared-analytics/tasks/<copilot-task-id>.output

# mp-mcp-server logs
tail -f /tmp/claude/-home-jared-analytics/tasks/<mcp-task-id>.output
```

### Common Log Patterns

**Successful tool loading**:
```
[MCP mixpanel_data] Got 39 tools: cohort_comparison, product_health_dashboard, ...
```

**SSE fallback (non-fatal)**:
```
[MCP mixpanel_data] Uncaught error: MCPClientError: MCP HTTP Transport Error: GET SSE failed: 400 Bad Request
```
This is expected - the client tries SSE first, fails, then falls back to regular HTTP.

**Authentication error**:
```
Query error: Unable to authenticate request
```
Check that `MP_USERNAME`, `MP_SECRET`, `MP_PROJECT_ID`, `MP_REGION` are set in the mp-mcp-server process.

**Timeout error**:
```
UND_ERR_HEADERS_TIMEOUT
UND_ERR_BODY_TIMEOUT
```
The copilot's undici timeout was too short. Currently set to 10 minutes in `server/index.ts`.

---

## Known Issues & Solutions

### 1. Authentication Failures

**Symptom**: `Unable to authenticate request` in logs

**Cause**: mp-mcp-server doesn't have credentials loaded

**Solution**:
```bash
source ~/.bashrc  # Load credentials
# Then start the server
```

### 2. Timeout on Long-Running Tools

**Symptom**: `UND_ERR_BODY_TIMEOUT` or `ClientDisconnect`

**Cause**: Intelligent tools (like `ask_mixpanel`) can take several minutes

**Solution**: Already fixed by adding to `ai/copilot/server/index.ts`:
```typescript
import {Agent, setGlobalDispatcher} from 'undici';

setGlobalDispatcher(
  new Agent({
    bodyTimeout: 10 * 60 * 1000,    // 10 minutes
    headersTimeout: 10 * 60 * 1000, // 10 minutes
    connectTimeout: 30 * 1000,       // 30 seconds
  }),
);
```

### 3. SSE 400 Bad Request Errors

**Symptom**: `GET SSE failed: 400 Bad Request` in copilot logs

**Cause**: `@ai-sdk/mcp` tries SSE transport first, FastMCP returns 400

**Impact**: Non-fatal, falls back to regular HTTP successfully

**Solution**: Can be ignored - tools still work

### 4. VIRTUAL_ENV Conflict

**Symptom**: `warning: VIRTUAL_ENV=/home/jared/analytics/.venv does not match`

**Cause**: Parent analytics repo has a different venv

**Solution**:
```bash
unset VIRTUAL_ENV
```

### 5. Port Already in Use

**Symptom**: `[Errno 98] address already in use`

**Solution**:
```bash
lsof -ti:8200 | xargs -r kill -9  # Kill process on port 8200
lsof -ti:8082 | xargs -r kill -9  # Kill process on port 8082
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser (Mixpanel UI)                    │
│                              Spark Copilot                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                           nginx                                  │
│                    (localhost or minikube)                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Spark AI Copilot Server                       │
│                         (port 8082)                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  getMixpanelDataMCPTools()                              │    │
│  │  - Uses @ai-sdk/mcp createMCPClient                     │    │
│  │  - 10 minute timeout configured                         │    │
│  │  - Merges tools with existing MCP server                │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────────┘
                                │ MCP over HTTP
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      mp-mcp-server                               │
│                  (FastMCP, port 8200)                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  39 tools from mixpanel_data                            │    │
│  │  - Discovery, Live queries, Fetch, SQL, Intelligent     │    │
│  │  - Internal-Source header for rate limit bypass         │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP (Basic Auth)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Mixpanel API                               │
│                   (mixpanel.com/api/...)                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Reference Commands

```bash
# Test credentials
source ~/.bashrc && cd /home/jared/analytics/mixpanel_data && uv run mp auth test

# Start mp-mcp-server
source ~/.bashrc && cd /home/jared/analytics/mixpanel_data/mp-mcp-server && unset VIRTUAL_ENV && uv run python -m mp_mcp_server.cli --transport http --port 8200

# Start copilot
cd /home/jared/analytics/ai/copilot && npm run dev

# Kill servers
lsof -ti:8200 | xargs -r kill -9
lsof -ti:8082 | xargs -r kill -9

# Check server status
lsof -i :8082 :8200

# Regenerate kube manifests (if libsonnet changed)
cd /home/jared/analytics/kube && ./cmd/gen.py src/mixpanel-dev-1/minikube/ai/copilot-server.jsonnet
```

---

## Next Steps (Future Work)

1. **MCP Sampling**: Enable sampling handler for intelligent tools to use Copilot's GPT access
2. **Production deployment**: Deploy mp-mcp-server to Kubernetes
3. **Caching**: Cache MCP client connections to avoid reconnecting on each request
4. **Error handling**: Better error propagation from MCP tools to Copilot UI
5. **SSE transport**: Fix SSE transport compatibility between @ai-sdk/mcp and FastMCP
