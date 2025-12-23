# mixpanel_data API Specification

> Version: 0.3.0 (Draft)
> Status: Design Phase
> Last Updated: December 2024

## Overview

`mixpanel_data` is a Python library for working with Mixpanel data, designed for AI coding agents and data analysis workflows. The library enables users to fetch data from Mixpanel into a local analytical database (DuckDB), query it with SQL, and run live Mixpanel reports—all through a single, consistent API.

## Design Principles

The API is built around these core principles:

**Workspace-centric**: A single abstraction (`Workspace`) encapsulates a Mixpanel project connection and local database. All operations are methods on this object.

**Explicit over implicit**: No global state. Table creation fails if a table already exists. Destruction requires explicit `drop()` calls.

**DataFrame-native**: Query methods return pandas DataFrames by default. The library integrates seamlessly with notebooks and the pandas ecosystem.

**Agent-friendly**: Every operation is non-interactive, returns structured data, and has predictable behavior. Agents can reason about what each method does without parsing flags or modes.

**Unix philosophy**: Each method does one thing well. Fetching creates tables. Dropping removes tables. No behavioral flags that change fundamental semantics.

**Secure by default**: Credentials are never passed as arguments or stored in code. They live in a config file or environment variables, following the pattern established by AWS CLI, GitHub CLI, and similar tools.

---

## Installation

```bash
pip install mixpanel_data
```

---

## Quick Start

```python
from mixpanel_data import Workspace

# Create a workspace (uses credentials from ~/.mp/config.toml)
ws = Workspace()

# Fetch events into local database
ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")

# Query with SQL (returns pandas DataFrame)
df = ws.sql("SELECT event_name, COUNT(*) as count FROM events GROUP BY 1")
```

Before using the library, configure authentication via the CLI:

```bash
mp auth add production --username sa_xxx --secret xxx --project 12345 --region us
mp auth switch production
```

---

## Authentication

### Overview

`mixpanel_data` uses Mixpanel Service Accounts for authentication. Service accounts provide secure, programmatic access to Mixpanel APIs without requiring user OAuth flows.

A service account can be granted access to multiple projects within an organization. Each configured account in `mixpanel_data` ties a service account to a specific project, allowing you to maintain named profiles for different environments (production, staging, etc.).

### Config File

Credentials are stored in `~/.mp/config.toml`:

```toml
# ~/.mp/config.toml

default = "production"

[accounts.production]
username = "sa_abc123..."
secret = "..."
project_id = "12345"
region = "us"

[accounts.staging]
username = "sa_xyz789..."
secret = "..."
project_id = "67890"
region = "eu"

# Same service account, different project
[accounts.production-analytics]
username = "sa_abc123..."
secret = "..."
project_id = "11111"
region = "us"
```

The config file is created with restrictive permissions (600) to protect credentials. The library will warn if permissions are too open.

### CLI Authentication Commands

```bash
# List configured accounts
mp auth list

# Add a new account (interactive)
mp auth add <name>

# Add a new account (non-interactive)
mp auth add <name> --username <u> --secret <s> --project <id> --region <r>

# Remove an account
mp auth remove <name>

# Set the default account
mp auth switch <name>

# Show account config (secret is redacted)
mp auth show <name>

# Test credentials (makes API call to verify)
mp auth test <name>
```

### Environment Variables

For CI/CD, Docker, and other environments where config files are impractical, credentials can be provided via environment variables:

```bash
export MP_USERNAME="sa_abc123..."
export MP_SECRET="..."
export MP_PROJECT_ID="12345"
export MP_REGION="us"
```

Environment variables take precedence over the config file.

### Credential Resolution Order

When creating a `Workspace`, credentials are resolved in this order:

1. Environment variables (`MP_USERNAME`, `MP_SECRET`, `MP_PROJECT_ID`, `MP_REGION`)
2. Named account from config file (if `account` parameter specified)
3. Default account from config file

### Creating a Service Account

Service accounts are created in the Mixpanel UI:

1. Navigate to Organization Settings → Service Accounts
2. Click "Create Service Account"
3. Assign a name and select the appropriate role for each project
4. Copy the username and secret (the secret is only shown once)

For `mixpanel_data`, the service account needs read access to the projects you want to query. The "Analyst" role is typically sufficient.

---

## Auth Module

The `auth` module provides programmatic access to credential management.

```python
from mixpanel_data import auth

# List all configured accounts
accounts = auth.list_accounts()
for account in accounts:
    print(f"{account.name}: project {account.project_id}")
    if account.is_default:
        print("  (default)")

# Add a new account
auth.add_account(
    name="production",
    username="sa_abc123...",
    secret="...",
    project_id="12345",
    region="us"
)

# Remove an account
auth.remove_account("staging")

# Set the default account
auth.set_default("production")

# Get account details (secret is redacted)
account = auth.get_account("production")

# Test credentials
result = auth.test_account("production")
if result.success:
    print(f"Authenticated as {result.user}")
else:
    print(f"Failed: {result.error}")
```

### Auth Module Reference

```python
def list_accounts() -> list[AccountInfo]:
    """
    List all configured accounts.

    Returns:
        List of AccountInfo objects

    Example:
        for account in auth.list_accounts():
            print(f"{account.name}: {account.project_id}")
    """

def add_account(
    name: str,
    username: str,
    secret: str,
    project_id: str,
    region: str = "us"
) -> None:
    """
    Add a new account to the config file.

    Args:
        name: Profile name for this account
        username: Service account username
        secret: Service account secret
        project_id: Mixpanel project ID
        region: Data residency region ("us", "eu", or "in")

    Raises:
        AccountExistsError: If an account with this name already exists
    """

def remove_account(name: str) -> None:
    """
    Remove an account from the config file.

    Args:
        name: Profile name to remove

    Raises:
        AccountNotFoundError: If account does not exist
    """

def set_default(name: str) -> None:
    """
    Set the default account.

    Args:
        name: Profile name to set as default

    Raises:
        AccountNotFoundError: If account does not exist
    """

def get_account(name: str) -> AccountInfo:
    """
    Get account details.

    The secret is redacted in the returned object.

    Args:
        name: Profile name

    Returns:
        AccountInfo with account details

    Raises:
        AccountNotFoundError: If account does not exist
    """

def test_account(name: str | None = None) -> TestResult:
    """
    Test account credentials by making an API call.

    Args:
        name: Profile name, or None for default account

    Returns:
        TestResult with success status and details
    """
```

### Auth Types

```python
@dataclass
class AccountInfo:
    name: str               # Profile name
    username: str           # Service account username (not redacted)
    project_id: str         # Mixpanel project ID
    region: str             # Data residency region
    is_default: bool        # Whether this is the default account
    # Note: secret is never included in this object

@dataclass
class TestResult:
    success: bool           # Whether authentication succeeded
    user: str | None        # Authenticated user info (if success)
    error: str | None       # Error message (if failure)
```

---

## Core API

### Workspace

The `Workspace` class is the primary entry point to the library. It represents the combination of a Mixpanel project and a local DuckDB database.

#### Construction

```python
class Workspace:
    def __init__(
        self,
        account: str | None = None,
        project_id: str | None = None,
        region: str | None = None,
        path: str | Path | None = None
    ) -> None:
        """
        Create a workspace using stored credentials.

        Credentials are resolved in order:
        1. Environment variables (MP_USERNAME, MP_SECRET, etc.)
        2. Named account from config file
        3. Default account from config file

        Args:
            account: Named account from config file. If None, uses default.
            project_id: Override project ID from config
            region: Override region from config
            path: Path to DuckDB database file. If None, uses
                  ~/.mixpanel_data/{project_id}.db

        Raises:
            AuthenticationError: If no valid credentials found
            ConfigError: If named account doesn't exist

        Example:
            # Uses default account
            ws = Workspace()

            # Uses named account
            ws = Workspace(account="staging")

            # Override project ID
            ws = Workspace(account="production", project_id="99999")
        """
```

#### Class Methods

```python
@classmethod
def ephemeral(
    cls,
    account: str | None = None,
    project_id: str | None = None,
    region: str | None = None
) -> ContextManager[Workspace]:
    """
    Create a temporary workspace that is deleted on exit.

    Use this for fetch-analyze-discard workflows where you don't
    need to persist the data between sessions.

    Args:
        account: Named account from config file. If None, uses default.
        project_id: Override project ID from config
        region: Override region from config

    Example:
        with Workspace.ephemeral() as ws:
            ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
            total = ws.sql_scalar("SELECT COUNT(*) FROM events")
        # Database is deleted here
    """

@classmethod
def open(cls, path: str | Path) -> Workspace:
    """
    Open an existing workspace database without credentials.

    Use this to query a previously-created database without needing
    API credentials. Fetching new data will raise an error.

    Args:
        path: Path to existing DuckDB database file

    Raises:
        FileNotFoundError: If database file does not exist

    Example:
        ws = Workspace.open("./analysis.db")
        df = ws.sql("SELECT * FROM events")
    """
```

---

### Discovery Methods

These methods query the Mixpanel API to discover what data exists in the project. They do not modify the local database.

```python
def events(self) -> list[str]:
    """
    List all event names in the Mixpanel project.

    Returns:
        List of event names, sorted alphabetically

    Example:
        ws.events()
        # → ["Login", "Purchase", "Signup", ...]
    """

def properties(self, event: str) -> list[str]:
    """
    List all properties for a specific event.

    Args:
        event: Event name

    Returns:
        List of property names, sorted alphabetically

    Example:
        ws.properties("Purchase")
        # → ["amount", "country", "currency", "product_id", ...]
    """

def property_values(
    self,
    event: str,
    property: str,
    limit: int = 100
) -> list[str]:
    """
    List sample values for a property on an event.

    Args:
        event: Event name
        property: Property name
        limit: Maximum number of values to return

    Returns:
        List of property values (as strings)

    Example:
        ws.property_values("Purchase", "country")
        # → ["US", "CA", "UK", "DE", ...]
    """

def funnels(self) -> list[FunnelInfo]:
    """
    List all saved funnels in the Mixpanel project.

    Results are cached for the session. Use ws.clear_discovery_cache()
    to refresh.

    Returns:
        List of FunnelInfo objects with funnel_id and name

    Example:
        for funnel in ws.funnels():
            print(f"{funnel.funnel_id}: {funnel.name}")
        # → 123: Signup to Purchase
        # → 456: Onboarding Flow
    """

def cohorts(self) -> list[SavedCohort]:
    """
    List all saved cohorts in the Mixpanel project.

    Results are cached for the session. Use ws.clear_discovery_cache()
    to refresh.

    Returns:
        List of SavedCohort objects with cohort metadata

    Example:
        for cohort in ws.cohorts():
            print(f"{cohort.id}: {cohort.name} ({cohort.count} users)")
        # → 789: Power Users (1234 users)
        # → 101: Churned Users (567 users)
    """

def top_events(
    self,
    type: Literal["general", "average", "unique"] = "general",
    limit: int | None = None
) -> list[TopEvent]:
    """
    Get the top events in the Mixpanel project by volume.

    Unlike other discovery methods, this is NOT cached because it
    returns real-time usage data that may change frequently.

    Args:
        type: Count type for ranking:
            - "general": Total event count (default)
            - "average": Average events per user
            - "unique": Unique users who triggered
        limit: Maximum number of events to return (None = all)

    Returns:
        List of TopEvent objects sorted by count descending

    Example:
        for event in ws.top_events(limit=5):
            print(f"{event.event}: {event.count} ({event.percent_change:+.1f}%)")
        # → Page View: 50000 (+12.3%)
        # → Button Click: 25000 (-5.2%)
    """
```

---

### Fetching Methods

These methods fetch data from the Mixpanel API and store it in the local DuckDB database. Each fetch creates a new table.

```python
def fetch_events(
    self,
    name: str = "events",
    *,
    from_date: str,
    to_date: str,
    events: list[str] | None = None,
    where: str | None = None,
    progress: bool = True
) -> FetchResult:
    """
    Fetch events from Mixpanel and store in a local table.

    Args:
        name: Table name to create. Defaults to "events".
        from_date: Start date (inclusive), format "YYYY-MM-DD"
        to_date: End date (inclusive), format "YYYY-MM-DD"
        events: Optional list of event names to filter
        where: Optional Mixpanel filter expression
        progress: Whether to display progress bar

    Returns:
        FetchResult with metadata about the fetch

    Raises:
        TableExistsError: If a table with this name already exists.
            Use ws.drop(name) first to replace.
        AuthenticationError: If API credentials are invalid
        RateLimitError: If Mixpanel rate limit is exceeded

    Example:
        # Basic fetch (creates "events" table)
        ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")

        # Named fetch with filters
        ws.fetch_events(
            "big_purchases",
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=["Purchase"],
            where='properties["amount"] > 1000'
        )
    """

def fetch_profiles(
    self,
    name: str = "profiles",
    *,
    where: str | None = None,
    progress: bool = True
) -> FetchResult:
    """
    Fetch user profiles from Mixpanel and store in a local table.

    Args:
        name: Table name to create. Defaults to "profiles".
        where: Optional Mixpanel filter expression
        progress: Whether to display progress bar

    Returns:
        FetchResult with metadata about the fetch

    Raises:
        TableExistsError: If a table with this name already exists.
            Use ws.drop(name) first to replace.
        AuthenticationError: If API credentials are invalid

    Example:
        # All profiles (creates "profiles" table)
        ws.fetch_profiles()

        # Filtered profiles with custom name
        ws.fetch_profiles(
            "premium_users",
            where='user["plan"] == "premium"'
        )
    """
```

---

### Local Query Methods

These methods query the local DuckDB database. They do not make any API calls.

```python
def sql(self, query: str) -> pd.DataFrame:
    """
    Execute SQL query and return results as a DataFrame.

    Args:
        query: SQL query string

    Returns:
        pandas DataFrame with query results

    Example:
        df = ws.sql('''
            SELECT
                properties->>'$.country' as country,
                COUNT(*) as purchases,
                SUM(CAST(properties->>'$.amount' AS DECIMAL)) as revenue
            FROM events
            WHERE event_name = 'Purchase'
            GROUP BY 1
            ORDER BY revenue DESC
        ''')
    """

def sql_scalar(self, query: str) -> Any:
    """
    Execute SQL query and return a single scalar value.

    Use this for COUNT, SUM, AVG, or other aggregate queries
    that return a single value.

    Args:
        query: SQL query that returns a single value

    Returns:
        The scalar value (int, float, str, etc.)

    Raises:
        ValueError: If query returns more than one row or column

    Example:
        count = ws.sql_scalar("SELECT COUNT(*) FROM events")
        # → 15234
    """

def sql_rows(self, query: str) -> list[tuple]:
    """
    Execute SQL query and return results as a list of tuples.

    Use this when you don't need pandas overhead, or for
    queries that return simple lists.

    Args:
        query: SQL query string

    Returns:
        List of tuples, one per row

    Example:
        rows = ws.sql_rows("SELECT DISTINCT event_name FROM events")
        # → [("Purchase",), ("Signup",), ("Login",)]
    """
```

---

### Live Query Methods

These methods query the Mixpanel API directly and return results without storing them locally. Use these for quick answers when you don't need to iterate on the data.

```python
def segmentation(
    self,
    event: str,
    *,
    from_date: str,
    to_date: str,
    on: str | None = None,
    unit: str = "day",
    where: str | None = None
) -> SegmentationResult:
    """
    Run a segmentation query against Mixpanel.

    Args:
        event: Event name to analyze
        from_date: Start date (inclusive), format "YYYY-MM-DD"
        to_date: End date (inclusive), format "YYYY-MM-DD"
        on: Property to segment by (e.g., "properties.country")
        unit: Time unit ("minute", "hour", "day", "week", "month")
        where: Optional filter expression

    Returns:
        SegmentationResult containing the data and metadata

    Example:
        result = ws.segmentation(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            on="properties.country",
            unit="day"
        )
        print(result.total)  # Total events
        df = result.df       # DataFrame with time series by segment
    """

def funnel(
    self,
    funnel_id: int,
    *,
    from_date: str,
    to_date: str,
    unit: str = "day",
    on: str | None = None
) -> FunnelResult:
    """
    Run a funnel analysis using a saved funnel definition.

    Args:
        funnel_id: ID of saved funnel in Mixpanel
        from_date: Start date (inclusive), format "YYYY-MM-DD"
        to_date: End date (inclusive), format "YYYY-MM-DD"
        unit: Time unit ("day", "week", "month")
        on: Property to segment by

    Returns:
        FunnelResult containing conversion data and metadata

    Example:
        result = ws.funnel(
            funnel_id=123,
            from_date="2024-01-01",
            to_date="2024-01-31"
        )
        print(result.conversion_rate)  # Overall conversion
        print(result.steps)            # Step-by-step breakdown
        df = result.df                 # Full data as DataFrame
    """

def retention(
    self,
    *,
    born_event: str,
    return_event: str,
    from_date: str,
    to_date: str,
    born_where: str | None = None,
    return_where: str | None = None,
    interval: int = 1,
    interval_count: int = 10,
    unit: str = "day"
) -> RetentionResult:
    """
    Run a retention analysis.

    Args:
        born_event: Event that defines the cohort (e.g., "Signup")
        return_event: Event that defines retention (e.g., "Login")
        from_date: Start date for cohort birth
        to_date: End date for cohort birth
        born_where: Filter for birth event
        return_where: Filter for return event
        interval: Size of each retention bucket
        interval_count: Number of retention buckets
        unit: Time unit ("day", "week", "month")

    Returns:
        RetentionResult containing cohort retention data

    Example:
        result = ws.retention(
            born_event="Signup",
            return_event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            interval_count=12,
            unit="week"
        )
        print(result.cohorts)  # Cohort sizes
        df = result.df         # Full retention matrix
    """

def jql(self, script: str, params: dict | None = None) -> JQLResult:
    """
    Execute a JQL (JavaScript Query Language) query.

    Use this for complex custom queries that aren't covered by
    the other live query methods.

    Args:
        script: JQL script as a string
        params: Optional parameters to pass to the script

    Returns:
        JQLResult containing the query output

    Example:
        result = ws.jql('''
            function main() {
                return Events({
                    from_date: params.from_date,
                    to_date: params.to_date
                })
                .groupBy(["properties.country"], mixpanel.reducer.count())
            }
        ''', params={"from_date": "2024-01-01", "to_date": "2024-01-31"})
        df = result.df
    """

def event_counts(
    self,
    events: list[str],
    *,
    from_date: str,
    to_date: str,
    unit: Literal["minute", "hour", "day", "week", "month"] = "day",
    type: Literal["general", "average", "unique"] = "general",
    where: str | None = None
) -> EventCountsResult:
    """
    Get time-series counts for multiple events in a single query.

    This is more efficient than calling segmentation() multiple times
    when you need to compare trends across several events.

    Args:
        events: List of event names to query
        from_date: Start date (inclusive), format "YYYY-MM-DD"
        to_date: End date (inclusive), format "YYYY-MM-DD"
        unit: Time unit for bucketing ("minute", "hour", "day", "week", "month")
        type: Count type:
            - "general": Total event count (default)
            - "average": Average events per user
            - "unique": Unique users who triggered
        where: Optional filter expression

    Returns:
        EventCountsResult containing time-series data for all events

    Example:
        result = ws.event_counts(
            events=["Login", "Purchase", "Logout"],
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day"
        )
        # Access data per event
        for event, series in result.series.items():
            print(f"{event}: {sum(series.values())} total")

        # Or use DataFrame for analysis
        df = result.df  # Columns: date, Login, Purchase, Logout
    """

def property_counts(
    self,
    event: str,
    property_name: str,
    *,
    from_date: str,
    to_date: str,
    unit: Literal["minute", "hour", "day", "week", "month"] = "day",
    type: Literal["general", "average", "unique"] = "general",
    where: str | None = None,
    limit: int = 10
) -> PropertyCountsResult:
    """
    Get time-series counts for an event, broken down by property values.

    Similar to segmentation with 'on' parameter, but returns data
    in a format optimized for multi-value analysis.

    Args:
        event: Event name to analyze
        property_name: Property to segment by (e.g., "country", "plan")
        from_date: Start date (inclusive), format "YYYY-MM-DD"
        to_date: End date (inclusive), format "YYYY-MM-DD"
        unit: Time unit for bucketing ("minute", "hour", "day", "week", "month")
        type: Count type:
            - "general": Total event count (default)
            - "average": Average events per user
            - "unique": Unique users who triggered
        where: Optional filter expression
        limit: Maximum number of property values to return

    Returns:
        PropertyCountsResult containing time-series data per property value

    Example:
        result = ws.property_counts(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-31"
        )
        # Access data per property value
        for value, series in result.series.items():
            print(f"{value}: {sum(series.values())} purchases")

        # Or use DataFrame
        df = result.df  # Columns: date, US, CA, UK, ...
    """
```

---

### Introspection Methods

These methods inspect the local database state.

```python
def info(self) -> WorkspaceInfo:
    """
    Get summary information about the workspace.

    Returns:
        WorkspaceInfo with database metadata

    Example:
        info = ws.info()
        print(info.path)          # Database file path
        print(info.project_id)    # Mixpanel project ID
        print(info.tables)        # List of tables
        print(info.size_mb)       # Database size in MB
    """

def tables(self) -> list[TableInfo]:
    """
    List all tables in the local database.

    Returns:
        List of TableInfo objects with metadata about each table

    Example:
        for table in ws.tables():
            print(f"{table.name}: {table.rows} rows")
            print(f"  Type: {table.type}")
            print(f"  Fetched: {table.fetched_at}")
            if table.date_range:
                print(f"  Range: {table.date_range}")
    """

def schema(self, table: str) -> TableSchema:
    """
    Get schema information for a specific table.

    Args:
        table: Table name

    Returns:
        TableSchema with column information and sample values

    Raises:
        TableNotFoundError: If table does not exist

    Example:
        schema = ws.schema("events")
        for col in schema.columns:
            print(f"{col.name}: {col.dtype}")
    """
```

---

### Table Management Methods

These methods manage tables in the local database.

```python
def drop(self, *names: str) -> None:
    """
    Drop one or more tables from the local database.

    Args:
        *names: Table names to drop

    Raises:
        TableNotFoundError: If any table does not exist

    Example:
        ws.drop("january")
        ws.drop("january", "february", "march")
    """

def drop_all(self, type: str | None = None) -> None:
    """
    Drop all tables from the local database.

    Args:
        type: Optional filter - "events" or "profiles".
              If None, drops all tables.

    Example:
        ws.drop_all()                 # Drop everything
        ws.drop_all(type="events")    # Drop only event tables
        ws.drop_all(type="profiles")  # Drop only profile tables
    """
```

---

### Escape Hatches

These properties provide direct access to underlying components for advanced use cases.

```python
@property
def connection(self) -> duckdb.DuckDBPyConnection:
    """
    Direct access to the DuckDB connection.

    Use this for complex queries, creating custom tables, or
    operations not covered by the standard API.

    Example:
        conn = ws.connection
        conn.execute("CREATE TABLE my_analysis AS SELECT ...")
    """

@property
def api(self) -> MixpanelAPI:
    """
    Direct access to the Mixpanel API client.

    Use this for API endpoints not covered by the standard methods.

    Example:
        response = ws.api.get("/api/2.0/events/names")
        response = ws.api.post("/api/2.0/jql", data={"script": "..."})
    """
```

---

## Result Types

### FetchResult

Returned by `fetch_events()` and `fetch_profiles()`.

```python
@dataclass
class FetchResult:
    table: str              # Name of created table
    rows: int               # Number of rows fetched
    type: str               # "events" or "profiles"
    duration_seconds: float # Time taken to fetch
    date_range: tuple[str, str] | None  # For events: (from_date, to_date)
    fetched_at: datetime    # Timestamp of fetch
```

### SegmentationResult

Returned by `segmentation()`.

```python
@dataclass
class SegmentationResult:
    event: str                    # Event that was queried
    from_date: str                # Query start date
    to_date: str                  # Query end date
    unit: str                     # Time unit
    segment_property: str | None  # Property segmented by
    total: int                    # Total event count
    df: pd.DataFrame              # Full results as DataFrame
```

### FunnelResult

Returned by `funnel()`.

```python
@dataclass
class FunnelResult:
    funnel_id: int                    # Funnel ID
    funnel_name: str                  # Funnel name
    from_date: str                    # Query start date
    to_date: str                      # Query end date
    conversion_rate: float            # Overall conversion (0-1)
    steps: list[FunnelStep]           # Step-by-step data
    df: pd.DataFrame                  # Full results as DataFrame

@dataclass
class FunnelStep:
    name: str           # Step name
    count: int          # Users reaching this step
    conversion: float   # Conversion from previous step (0-1)
    overall: float      # Conversion from first step (0-1)
```

### RetentionResult

Returned by `retention()`.

```python
@dataclass
class RetentionResult:
    born_event: str               # Cohort-defining event
    return_event: str             # Retention event
    from_date: str                # Query start date
    to_date: str                  # Query end date
    unit: str                     # Time unit
    cohorts: list[CohortInfo]     # Per-cohort summary
    df: pd.DataFrame              # Full retention matrix as DataFrame

@dataclass
class CohortInfo:
    date: str           # Cohort date
    size: int           # Cohort size
    retained: list[int] # Retained users per interval
```

### JQLResult

Returned by `jql()`.

```python
@dataclass
class JQLResult:
    df: pd.DataFrame    # Query results as DataFrame
    raw: list[Any]      # Raw API response
```

### FunnelInfo

Returned by `funnels()`.

```python
@dataclass(frozen=True)
class FunnelInfo:
    funnel_id: int      # Unique funnel identifier
    name: str           # Funnel display name
```

### SavedCohort

Returned by `cohorts()`.

```python
@dataclass(frozen=True)
class SavedCohort:
    id: int             # Unique cohort identifier
    name: str           # Cohort display name
    count: int          # Number of users in cohort
    description: str    # Cohort description
    created: str        # Creation timestamp (ISO format)
    is_visible: bool    # Whether cohort is visible in UI
```

### TopEvent

Returned by `top_events()`.

```python
@dataclass(frozen=True)
class TopEvent:
    event: str          # Event name
    count: int          # Event count (based on type parameter)
    percent_change: float  # Change from previous period
```

### EventCountsResult

Returned by `event_counts()`.

```python
@dataclass(frozen=True)
class EventCountsResult:
    events: list[str]                     # Events that were queried
    from_date: str                        # Query start date
    to_date: str                          # Query end date
    unit: str                             # Time unit used
    type: str                             # Count type used
    series: dict[str, dict[str, int]]     # {event: {date: count}}
    df: pd.DataFrame                      # Lazy-converted DataFrame
```

### PropertyCountsResult

Returned by `property_counts()`.

```python
@dataclass(frozen=True)
class PropertyCountsResult:
    event: str                            # Event that was queried
    property_name: str                    # Property segmented by
    from_date: str                        # Query start date
    to_date: str                          # Query end date
    unit: str                             # Time unit used
    type: str                             # Count type used
    series: dict[str, dict[str, int]]     # {property_value: {date: count}}
    df: pd.DataFrame                      # Lazy-converted DataFrame
```

### WorkspaceInfo

Returned by `info()`.

```python
@dataclass
class WorkspaceInfo:
    path: Path | None           # Database file path (None for ephemeral)
    project_id: str             # Mixpanel project ID
    region: str                 # Data residency region
    account: str | None         # Account name used (None if env vars)
    tables: list[str]           # Table names
    size_mb: float              # Database size in MB
    created_at: datetime        # Workspace creation time
```

### TableInfo

Returned by `tables()`.

```python
@dataclass
class TableInfo:
    name: str                           # Table name
    type: str                           # "events" or "profiles"
    rows: int                           # Row count
    date_range: tuple[str, str] | None  # For events: (from_date, to_date)
    fetched_at: datetime                # When the fetch occurred
    filter_events: list[str] | None     # Event filter used (if any)
    filter_where: str | None            # Where filter used (if any)
```

### TableSchema

Returned by `schema()`.

```python
@dataclass
class TableSchema:
    name: str                     # Table name
    columns: list[ColumnInfo]     # Column definitions
    row_count: int                # Number of rows
    sample_properties: dict       # Sample of JSON properties (for events/profiles)

@dataclass
class ColumnInfo:
    name: str       # Column name
    dtype: str      # DuckDB data type
    nullable: bool  # Whether column allows nulls
```

---

## Exceptions

```python
class MixpanelDataError(Exception):
    """Base exception for all mixpanel_data errors."""

class TableExistsError(MixpanelDataError):
    """Raised when attempting to create a table that already exists."""

class TableNotFoundError(MixpanelDataError):
    """Raised when referencing a table that does not exist."""

class AuthenticationError(MixpanelDataError):
    """Raised when API credentials are invalid or missing."""

class ConfigError(MixpanelDataError):
    """Raised when there's a problem with the config file."""

class AccountNotFoundError(ConfigError):
    """Raised when a named account doesn't exist in config."""

class AccountExistsError(ConfigError):
    """Raised when attempting to add an account that already exists."""

class RateLimitError(MixpanelDataError):
    """Raised when Mixpanel rate limit is exceeded."""

class QueryError(MixpanelDataError):
    """Raised when a SQL or API query fails."""
```

---

## Database Schema

### Events Table

When fetching events, the following schema is created:

| Column | Type | Description |
|--------|------|-------------|
| `event_name` | VARCHAR | Name of the event |
| `event_time` | TIMESTAMP | When the event occurred |
| `distinct_id` | VARCHAR | User identifier |
| `insert_id` | VARCHAR | Unique event identifier |
| `properties` | JSON | All event properties as JSON |

### Profiles Table

When fetching profiles, the following schema is created:

| Column | Type | Description |
|--------|------|-------------|
| `distinct_id` | VARCHAR | User identifier |
| `properties` | JSON | All profile properties as JSON |
| `last_seen` | TIMESTAMP | Last activity timestamp |

### Metadata Table

A `_metadata` table tracks fetch history:

| Column | Type | Description |
|--------|------|-------------|
| `table_name` | VARCHAR | Name of the fetched table |
| `type` | VARCHAR | "events" or "profiles" |
| `fetched_at` | TIMESTAMP | When the fetch occurred |
| `from_date` | DATE | Start of date range (events only) |
| `to_date` | DATE | End of date range (events only) |
| `filter_events` | JSON | Event name filters used |
| `filter_where` | VARCHAR | Where clause filter used |
| `row_count` | INTEGER | Number of rows fetched |

---

## DuckDB JSON Query Syntax

Events and profiles store properties as JSON. Use DuckDB's JSON operators to query them:

```sql
-- Extract string property
properties->>'$.country'

-- Extract numeric property (must cast)
CAST(properties->>'$.amount' AS DECIMAL)

-- Extract nested property
properties->>'$.user.plan'

-- Filter on JSON property
WHERE properties->>'$.country' = 'US'

-- Check if property exists
WHERE properties->>'$.coupon' IS NOT NULL
```

---

## Environment Variables

The library respects these environment variables:

| Variable | Description |
|----------|-------------|
| `MP_USERNAME` | Service account username |
| `MP_SECRET` | Service account secret |
| `MP_PROJECT_ID` | Project ID |
| `MP_REGION` | Data residency region (us, eu, in) |
| `MP_CONFIG_PATH` | Override config file location |
| `MP_DATA_DIR` | Override default database directory |

Environment variables take precedence over the config file.

---

## Usage Examples

### Basic Analysis Workflow

```python
from mixpanel_data import Workspace

# Create workspace (uses default account from config)
ws = Workspace()

# Discover what events exist
print(ws.events())

# Fetch last month of data
ws.fetch_events(from_date="2024-11-01", to_date="2024-11-30")

# Analyze
df = ws.sql("""
    SELECT 
        DATE_TRUNC('day', event_time) as day,
        event_name,
        COUNT(*) as count
    FROM events
    GROUP BY 1, 2
    ORDER BY 1, 3 DESC
""")
```

### Multi-Account Workflow

```python
# Work with production data
prod = Workspace(account="production")
prod.fetch_events(from_date="2024-01-01", to_date="2024-01-31")

# Work with staging data
staging = Workspace(account="staging")
staging.fetch_events(from_date="2024-01-01", to_date="2024-01-31")

# Compare
prod_count = prod.sql_scalar("SELECT COUNT(*) FROM events")
staging_count = staging.sql_scalar("SELECT COUNT(*) FROM events")
print(f"Production: {prod_count}, Staging: {staging_count}")
```

### Comparative Analysis

```python
ws = Workspace()

# Fetch two time periods
ws.fetch_events("november", from_date="2024-11-01", to_date="2024-11-30")
ws.fetch_events("december", from_date="2024-12-01", to_date="2024-12-31")

# Compare
ws.sql("""
    SELECT 
        'November' as month, 
        COUNT(*) as events,
        COUNT(DISTINCT distinct_id) as users
    FROM november
    UNION ALL
    SELECT 
        'December',
        COUNT(*),
        COUNT(DISTINCT distinct_id)
    FROM december
""")
```

### Ephemeral Analysis

```python
with Workspace.ephemeral() as ws:
    ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
    
    total_revenue = ws.sql_scalar("""
        SELECT SUM(CAST(properties->>'$.amount' AS DECIMAL))
        FROM events
        WHERE event_name = 'Purchase'
    """)
    
    print(f"January revenue: ${total_revenue:,.2f}")
# Database automatically deleted
```

### Notebook Workflow

```python
# Cell 1: Setup
from mixpanel_data import Workspace
ws = Workspace()

# Cell 2: Fetch
ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
ws.info()

# Cell 3: Query (DataFrame displays nicely in notebooks)
ws.sql("""
    SELECT 
        properties->>'$.country' as country,
        COUNT(*) as purchases,
        AVG(CAST(properties->>'$.amount' AS DECIMAL)) as avg_amount
    FROM events
    WHERE event_name = 'Purchase'
    GROUP BY 1
    ORDER BY 2 DESC
    LIMIT 10
""")

# Cell 4: Further pandas manipulation
df = ws.sql("SELECT * FROM events WHERE event_name = 'Purchase'")
df['amount'] = df['properties'].apply(lambda x: x.get('amount', 0))
df.groupby('country')['amount'].mean().plot(kind='bar')
```

### Live Query for Quick Answer

```python
ws = Workspace()

# No need to fetch if you just want a quick segmentation
result = ws.segmentation(
    event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31",
    on="properties.country"
)

print(f"Total purchases: {result.total}")
result.df.head(10)
```

### Re-fetching Data

```python
ws = Workspace()

# Initial fetch
ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")

# Later, want to re-fetch with different parameters
# This will error:
# ws.fetch_events(from_date="2024-01-01", to_date="2024-01-15")
# → TableExistsError: Table 'events' already exists. Use ws.drop('events') first.

# Correct approach: explicit drop, then fetch
ws.drop("events")
ws.fetch_events(from_date="2024-01-01", to_date="2024-01-15")
```

---

## Version History

| Version | Date | Notes |
|---------|------|-------|
| 0.1.0 | December 2024 | Initial API specification |
| 0.2.0 | December 2024 | Service account authentication model |
| 0.3.0 | December 2024 | Discovery enhancements: funnels, cohorts, top events; event/property counts |

---

*This specification defines the public API surface for mixpanel_data. Implementation details may vary, but the external interface should match this document.*
