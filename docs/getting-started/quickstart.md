# Quick Start

This guide walks you through your first queries with mixpanel_data in about 5 minutes.

## Prerequisites

You'll need:

- mixpanel_data installed (`pip install mixpanel_data`)
- A Mixpanel service account with username, secret, and project ID
- Your project's data residency region (us, eu, or in)

## Step 1: Set Up Credentials

### Option A: Environment Variables

```bash
export MP_USERNAME="sa_abc123..."
export MP_SECRET="your-secret-here"
export MP_PROJECT_ID="12345"
export MP_REGION="us"
```

### Option B: Using the CLI

```bash
# Interactive prompt (secure, recommended)
mp auth add production \
    --username sa_abc123... \
    --project 12345 \
    --region us
# You'll be prompted for the secret with hidden input
```

This stores credentials in `~/.mp/config.toml` and sets `production` as the default account.

For CI/CD environments, provide the secret via environment variable or stdin:

```bash
# Via environment variable
MP_SECRET=your-secret mp auth add production --username sa_abc123... --project 12345

# Via stdin
echo "$SECRET" | mp auth add production --username sa_abc123... --project 12345 --secret-stdin
```

## Step 2: Test Your Connection

Verify credentials are working:

=== "CLI"

    ```bash
    mp auth test
    ```

=== "Python"

    ```python
    import mixpanel_data as mp

    ws = mp.Workspace()
    ws.test_credentials()  # Raises AuthenticationError if invalid
    ```

## Step 3: Explore Your Data

Discover what events exist in your project:

=== "CLI"

    ```bash
    mp inspect events
    ```

=== "Python"

    ```python
    import mixpanel_data as mp

    ws = mp.Workspace()
    events = ws.events()
    print(events)  # ['Login', 'Purchase', 'Signup', ...]
    ```

## Step 4: Fetch Events to Local Storage

Fetch a month of events into a local DuckDB database:

=== "CLI"

    ```bash
    mp fetch events jan_events --from 2024-01-01 --to 2024-01-31
    ```

=== "Python"

    ```python
    import mixpanel_data as mp

    ws = mp.Workspace()
    result = ws.fetch_events(
        name="jan_events",
        from_date="2024-01-01",
        to_date="2024-01-31"
    )
    print(f"Fetched {result.row_count} events in {result.duration_seconds:.1f}s")
    ```

## Step 5: Query with SQL

Analyze the data with SQL:

=== "CLI"

    ```bash
    mp query sql "SELECT event_name, COUNT(*) as count FROM jan_events GROUP BY 1 ORDER BY 2 DESC" --format table
    ```

=== "Python"

    ```python
    import mixpanel_data as mp

    ws = mp.Workspace()

    # Get results as DataFrame
    df = ws.sql("""
        SELECT
            event_name,
            COUNT(*) as count
        FROM jan_events
        GROUP BY 1
        ORDER BY 2 DESC
    """)
    print(df)
    ```

## Step 6: Run Live Queries

For real-time analytics, query Mixpanel directly:

=== "CLI"

    ```bash
    mp query segmentation --event Purchase --from 2024-01-01 --to 2024-01-31 --format table
    ```

=== "Python"

    ```python
    import mixpanel_data as mp

    ws = mp.Workspace()

    result = ws.segmentation(
        event="Purchase",
        from_date="2024-01-01",
        to_date="2024-01-31"
    )

    # Access as DataFrame
    print(result.df)
    ```

## Alternative: Stream Data Without Storage

For ETL pipelines or one-time processing, stream data directly without storing:

=== "CLI"

    ```bash
    # Stream events as JSONL
    mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout

    # Pipe to other tools
    mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout | jq '.event_name'
    ```

=== "Python"

    ```python
    import mixpanel_data as mp

    ws = mp.Workspace()
    for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31"):
        send_to_warehouse(event)
    ws.close()
    ```

## Using Ephemeral Workspaces

For one-off analysis without persisting data:

```python
import mixpanel_data as mp

with mp.Workspace.ephemeral() as ws:
    ws.fetch_events("events", from_date="2024-01-01", to_date="2024-01-07")
    total = ws.sql_scalar("SELECT COUNT(*) FROM events")
    print(f"Total events: {total}")
# Database automatically deleted when context exits
```

## Next Steps

- [Configuration](configuration.md) — Multiple accounts and advanced settings
- [Fetching Data](../guide/fetching.md) — Filtering and progress callbacks
- [Streaming Data](../guide/streaming.md) — Process data without local storage
- [SQL Queries](../guide/sql-queries.md) — DuckDB JSON syntax and patterns
- [Live Analytics](../guide/live-analytics.md) — Segmentation, funnels, retention
