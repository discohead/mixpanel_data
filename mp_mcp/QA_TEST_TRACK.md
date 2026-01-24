# MCP Server QA Test Track

Manual QA testing guide for mp_mcp with Claude Desktop.

## Prerequisites

- Claude Desktop installed
- Mixpanel credentials configured (`~/.mp/config.toml` or environment variables)
- Access to a Mixpanel project with events

## Setup

### 1. Install the MCP Server

**Option A: Using uv (recommended)**

```bash
cd mp_mcp
uv pip install -e .
```

**Option B: Using pip**

```bash
# Install mixpanel_data first (required dependency)
pip install -e .
# Then install the MCP server
pip install -e ./mp_mcp
```

### 2. Verify CLI Works

```bash
mp_mcp --help
```

**Expected output:**

```
usage: mp_mcp [-h] [--account ACCOUNT] [--transport {stdio,sse}] [--port PORT]

MCP server for Mixpanel analytics

options:
  -h, --help            show this help message and exit
  --account ACCOUNT     Named account from ~/.mp/config.toml
  --transport {stdio,sse}
                        Transport type (default: stdio). 'sse' uses HTTP Server-Sent Events.
  --port PORT           HTTP port (only used with --transport sse)
```

### 3. Configure Claude Desktop

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

**With specific account:**

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

### 4. Restart Claude Desktop

Quit and relaunch Claude Desktop to load the MCP server.

---

## Test Cases

### Phase 1: Connection Verification

| #   | Test           | Prompt                               | Expected Result                                       | Pass |
| --- | -------------- | ------------------------------------ | ----------------------------------------------------- | ---- |
| 1.1 | Server loads   | Open Claude Desktop                  | No error dialogs, Mixpanel tools visible in tool list | [ ]  |
| 1.2 | Tool discovery | "What Mixpanel tools are available?" | Lists discovery, query, fetch, and local tools        | [ ]  |

---

### Phase 2: Schema Discovery (US1)

| #   | Test            | Prompt                                                      | Expected Result                                      | Pass |
| --- | --------------- | ----------------------------------------------------------- | ---------------------------------------------------- | ---- |
| 2.1 | List events     | "What events are tracked in my Mixpanel project?"           | Returns list of event names from your project        | [ ]  |
| 2.2 | List properties | "Show me the properties for the login event"                | Returns property names and types for specified event | [ ]  |
| 2.3 | Property values | "What are sample values for the browser property on login?" | Returns example values like "Chrome", "Safari"       | [ ]  |
| 2.4 | List funnels    | "What funnels do I have saved?"                             | Returns list of saved funnel names and IDs           | [ ]  |
| 2.5 | List cohorts    | "Show my saved cohorts"                                     | Returns cohort names and IDs                         | [ ]  |
| 2.6 | Top events      | "What are my most popular events?"                          | Returns events ranked by volume                      | [ ]  |
| 2.7 | Workspace info  | "What's the current workspace state?"                       | Returns project ID, region, tables                   | [ ]  |

---

### Phase 3: Live Analytics (US2)

| #   | Test                     | Prompt                                                                                                                                        | Expected Result                      | Pass |
| --- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ | ---- |
| 3.1 | Segmentation             | "How many logins happened each day last week?"                                                                                                | Returns daily counts as time series  | [ ]  |
| 3.2 | Segmentation by property | "Break down signups by browser for the last 7 days"                                                                                           | Returns counts segmented by browser  | [ ]  |
| 3.3 | Funnel query             | "What's the conversion rate for my signup funnel?"                                                                                            | Returns step-by-step conversion data | [ ]  |
| 3.4 | Retention                | "Show day-7 retention for users who signed up last month"                                                                                     | Returns cohort retention data        | [ ]  |
| 3.5 | JQL                      | "Run this JQL: function main() { return Events({from_date:'2025-01-01', to_date:'2025-01-07'}).groupBy(['name'], mixpanel.reducer.count()) }" | Returns JQL query results            | [ ]  |

---

### Phase 4: Data Fetching (US3)

| #   | Test               | Prompt                                                         | Expected Result                                 | Pass |
| --- | ------------------ | -------------------------------------------------------------- | ----------------------------------------------- | ---- |
| 4.1 | Fetch events       | "Fetch events from January 1-7 into a table called jan_events" | Creates table, reports row count                | [ ]  |
| 4.2 | Fetch with filter  | "Fetch only login events from last week"                       | Creates filtered table                          | [ ]  |
| 4.3 | Fetch profiles     | "Download user profiles to a table called users"               | Creates profiles table                          | [ ]  |
| 4.4 | Table exists error | "Fetch events into jan_events again"                           | Reports table already exists, suggests new name | [ ]  |

---

### Phase 5: Local SQL Analysis (US4)

**Prerequisite:** Complete test 4.1 first to have local data.

| #   | Test            | Prompt                                               | Expected Result                            | Pass |
| --- | --------------- | ---------------------------------------------------- | ------------------------------------------ | ---- |
| 5.1 | List tables     | "What tables do I have locally?"                     | Lists jan_events (or whatever you created) | [ ]  |
| 5.2 | Table schema    | "What columns are in the jan_events table?"          | Returns column names and types             | [ ]  |
| 5.3 | Sample data     | "Show me 5 sample rows from jan_events"              | Returns 5 random rows                      | [ ]  |
| 5.4 | SQL query       | "Count events by name in jan_events"                 | Returns event counts                       | [ ]  |
| 5.5 | SQL scalar      | "How many total events are in jan_events?"           | Returns single count value                 | [ ]  |
| 5.6 | Complex SQL     | "Find the top 10 users by event count in jan_events" | Returns user IDs with counts               | [ ]  |
| 5.7 | Event breakdown | "Break down jan_events by event name"                | Returns name → count mapping               | [ ]  |
| 5.8 | Drop table      | "Delete the jan_events table"                        | Confirms deletion                          | [ ]  |

---

### Phase 6: Session Persistence (US5)

| #   | Test                | Prompt                                                              | Expected Result                                      | Pass |
| --- | ------------------- | ------------------------------------------------------------------- | ---------------------------------------------------- | ---- |
| 6.1 | Multi-query session | "Fetch events from Jan 1-3, then count them, then show top 5 users" | All three operations work in sequence, data persists | [ ]  |
| 6.2 | Resource access     | Ask Claude to use workspace://info resource                         | Returns current workspace state                      | [ ]  |

---

### Phase 7: Guided Workflows (US6)

| #   | Test               | Prompt                                | Expected Result                     | Pass |
| --- | ------------------ | ------------------------------------- | ----------------------------------- | ---- |
| 7.1 | Analytics workflow | Request the analytics_workflow prompt | Returns multi-step analytics guide  | [ ]  |
| 7.2 | Funnel analysis    | Request the funnel_analysis prompt    | Returns funnel analysis workflow    | [ ]  |
| 7.3 | Retention analysis | Request the retention_analysis prompt | Returns retention analysis workflow | [ ]  |

---

### Phase 8: Error Handling

| #   | Test               | Prompt                                       | Expected Result                     | Pass |
| --- | ------------------ | -------------------------------------------- | ----------------------------------- | ---- |
| 8.1 | Invalid event      | "Show properties for nonexistent_event_xyz"  | Graceful error message              | [ ]  |
| 8.2 | SQL error          | "Run SQL: SELECT \* FROM nonexistent_table"  | Reports table not found             | [ ]  |
| 8.3 | Invalid date range | "Fetch events from 2099-01-01 to 2099-01-07" | Handles gracefully (empty or error) | [ ]  |

---

## End-to-End Workflow Test

Complete this full workflow to verify the entire system works together:

```
1. "What events are tracked in my project?"
   → Note one event name (e.g., "login")

2. "Show me properties for the [event] event"
   → Note a property name (e.g., "browser")

3. "How many [event] events happened each day last week, broken down by [property]?"
   → Verify you get segmented time series data

4. "Fetch [event] events from last week into a table called test_data"
   → Verify table is created

5. "What's the schema of the test_data table?"
   → Verify columns are listed

6. "Find the top 5 distinct_ids by event count in test_data"
   → Verify SQL works on local data

7. "Drop the test_data table"
   → Verify cleanup works
```

**End-to-end test result:** [ ] Pass / [ ] Fail

---

## Troubleshooting

### Server not loading

- Check Claude Desktop logs: `~/Library/Logs/Claude/`
- Verify `mp_mcp` is in PATH
- Test manually: `mp_mcp` (should hang waiting for stdio)

### Authentication errors

- Verify `~/.mp/config.toml` has valid credentials
- Check environment variables: `MP_USERNAME`, `MP_SECRET`, `MP_PROJECT_ID`

### Tools not appearing

- Restart Claude Desktop completely (Cmd+Q, then relaunch)
- Check config JSON syntax

### Rate limit errors

- Wait and retry
- Check Mixpanel API quotas

---

## Sign-off

| Tester | Date | Version | Result |
| ------ | ---- | ------- | ------ |
|        |      | 0.1.0   |        |

**Notes:**
