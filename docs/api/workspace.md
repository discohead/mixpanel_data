# Workspace

The `Workspace` class is the unified entry point for all Mixpanel data operations.

!!! tip "Explore on DeepWiki"
    🤖 **[Workspace Class Deep Dive →](https://deepwiki.com/jaredmcfarland/mixpanel_data/3.2.1-workspace-class)**

    Ask questions about Workspace methods, explore usage patterns, or understand how services are orchestrated.

## Overview

Workspace orchestrates internal services and provides direct App API access:

- **DiscoveryService** — Schema exploration (events, properties, funnels, cohorts)
- **LiveQueryService** — Real-time analytics queries (legacy) and Insights engine queries
- **Streaming** — Stream events and profiles directly from Mixpanel
- **Entity CRUD** — Create, read, update, delete dashboards, reports, and cohorts via Mixpanel App API (workspace-scoped)
- **Feature Management** — Create, read, update, delete feature flags and experiments via Mixpanel App API (project-scoped)
- **Operational Tooling** — Manage alerts, annotations, and webhooks via Mixpanel App API (workspace-scoped)
- **Data Governance** — Manage Lexicon definitions, drop filters, custom properties, custom events, lookup tables, schema registry, schema enforcement, data auditing, volume anomalies, and event deletion requests via Mixpanel App API (workspace-scoped)
- **Business Context** — Read and write the markdown documentation that grounds AI assistants (org and project scopes, 50,000-char cap)

## Key Features

### Entity CRUD

Manage dashboards, reports (bookmarks), and cohorts programmatically via the Mixpanel App API (workspace-scoped):

```python
import mixpanel_data as mp

ws = mp.Workspace()

# Dashboards
dashboards = ws.list_dashboards()
new_dash = ws.create_dashboard(mp.CreateDashboardParams(title="Q1 Metrics"))
ws.update_dashboard(new_dash.id, mp.UpdateDashboardParams(title="Q1 Metrics v2"))
ws.favorite_dashboard(new_dash.id)

# Reports (Bookmarks)
reports = ws.list_bookmarks_v2()
report = ws.create_bookmark(mp.CreateBookmarkParams(
    name="Daily Signups",
    bookmark_type="insights"
))

# Cohorts
cohorts = ws.list_cohorts_full()
cohort = ws.create_cohort(mp.CreateCohortParams(name="Power Users"))
ws.update_cohort(cohort.id, mp.UpdateCohortParams(name="Super Users"))
```

Dashboard, report, and cohort operations require a workspace ID, set via `MP_WORKSPACE_ID` environment variable, `--workspace` / `-w` CLI flag, `Workspace(workspace=N)`, or `ws.use(workspace=N)`. List available workspaces with `mp workspace list` or `ws.workspaces()`.

### Feature Flags & Experiments

Manage feature flags and experiments programmatically. Unlike dashboards/reports/cohorts, these are **project-scoped** and do not require a workspace ID.

```python
import mixpanel_data as mp

ws = mp.Workspace()

# Feature Flags
flags = ws.list_feature_flags()
flag = ws.create_feature_flag(mp.CreateFeatureFlagParams(
    name="Dark Mode", key="dark_mode"
))
ws.update_feature_flag(flag.id, mp.UpdateFeatureFlagParams(
    name="Dark Mode", key="dark_mode",
    status=mp.FeatureFlagStatus.ENABLED,
    ruleset=flag.ruleset,
))

# Experiments (full lifecycle)
exp = ws.create_experiment(mp.CreateExperimentParams(name="Checkout Flow Test"))
launched = ws.launch_experiment(exp.id)
concluded = ws.conclude_experiment(exp.id)
decided = ws.decide_experiment(exp.id, mp.ExperimentDecideParams(success=True))
```

Feature flag `update` uses **PUT semantics** (all required fields must be provided). Experiment `update` uses **PATCH semantics** (only changed fields needed). See the [Entity Management guide](../guide/entity-management.md) for complete coverage.

### Data Governance

Manage Lexicon definitions, drop filters, custom properties, custom events, and lookup tables programmatically. All operations are **workspace-scoped**.

```python
import mixpanel_data as mp

ws = mp.Workspace()

# Lexicon — Event and property definitions
defs = ws.get_event_definitions(names=["Signup", "Login"])
ws.update_event_definition("Signup", mp.UpdateEventDefinitionParams(verified=True))
tags = ws.list_lexicon_tags()

# Drop filters
filters = ws.list_drop_filters()
ws.create_drop_filter(mp.CreateDropFilterParams(
    event_name="Debug Event", filters={"property": "env", "value": "test"},
))

# Custom properties
props = ws.list_custom_properties()
prop = ws.get_custom_property("abc123")

# Lookup tables
tables = ws.list_lookup_tables()
table = ws.upload_lookup_table(mp.UploadLookupTableParams(
    name="Countries", file_path="/path/to/countries.csv",
))

# Custom events
events = ws.list_custom_events()
```

See the [Data Governance guide](../guide/data-governance.md) for complete coverage.

### Business Context

Read and write the markdown documentation that grounds AI assistants. Two scopes (`level="organization"` shared across the org, `level="project"` per-project), 50,000-character cap enforced client-side before any HTTP call.

```python
import mixpanel_data as mp

ws = mp.Workspace()

# Read
project_ctx = ws.get_business_context(level="project")
org_ctx = ws.get_business_context(level="organization")     # auto-resolves org_id

# Read both in one round-trip
chain = ws.get_business_context_chain()

# Write (full-replace; pass "" to clear)
ws.set_business_context("# About Acme\n…", level="project")
ws.clear_business_context(level="organization")
```

Project-scope writes require `edit_project_info` permission; org-scope writes require `edit_project_info` at the org level. See the [Business Context guide](../guide/business-context.md) for full coverage of input modes, error handling, and cross-project audit patterns.

!!! note "`workspaces()` vs `list_workspaces()`"
    Both methods are exposed. `workspaces()` (recommended) returns `list[WorkspaceRef]` from the cached `/me` response — fast, typed, and consistent with `events()` / `properties()` / `funnels()` / `cohorts()`. `list_workspaces()` is a lower-level escape hatch that calls `GET /api/app/projects/{pid}/workspaces/public` directly and returns `list[PublicWorkspace]`.

## In-Session Switching

`Workspace.use()` swaps the active account, project, workspace, or target without rebuilding the underlying `httpx.Client` or per-account `/me` cache. It returns `self` for fluent chaining, so cross-project iteration is O(1) per swap.

```python
import mixpanel_data as mp

ws = mp.Workspace()
ws.use(account="team")                              # implicitly clears workspace
ws.use(project="3018488")
ws.use(workspace=3448414)
ws.use(target="ecom")                               # apply all three at once

# Persist the new state
ws.use(project="3018488", persist=True)             # writes [active]

# Read the resolved state
print(ws.account.name, ws.project.id, ws.workspace.id if ws.workspace else None)
print(ws.session)                                   # full Session snapshot
```

See [Auth → Workspace.use()](auth.md#workspaceuse-in-session-switching) for the resolution semantics and parallel-snapshot patterns.

## Class Reference

::: mixpanel_data.Workspace
    options:
      show_root_heading: true
      show_root_toc_entry: true
      members:
        - __init__
        - close
        - account
        - project
        - workspace
        - session
        - use
        - me
        - projects
        - workspaces
        - list_workspaces
        - resolve_workspace_id
        - events
        - properties
        - property_values
        - subproperties
        - funnels
        - cohorts
        - list_bookmarks
        - top_events
        - lexicon_schemas
        - lexicon_schema
        - clear_discovery_cache
        - stream_events
        - stream_profiles
        - query
        - build_params
        - query_funnel
        - build_funnel_params
        - query_retention
        - build_retention_params
        - query_flow
        - build_flow_params
        - query_user
        - build_user_params
        - segmentation
        - funnel
        - retention
        - jql
        - event_counts
        - property_counts
        - activity_feed
        - query_saved_report
        - query_saved_flows
        - frequency
        - segmentation_numeric
        - segmentation_sum
        - segmentation_average
        - property_distribution
        - numeric_summary
        - daily_counts
        - engagement_distribution
        - property_coverage
        - api
        # Dashboard CRUD
        - list_dashboards
        - create_dashboard
        - get_dashboard
        - update_dashboard
        - delete_dashboard
        - bulk_delete_dashboards
        - favorite_dashboard
        - unfavorite_dashboard
        - pin_dashboard
        - unpin_dashboard
        - add_report_to_dashboard
        - remove_report_from_dashboard
        - list_blueprint_templates
        - create_blueprint
        - get_blueprint_config
        - update_blueprint_cohorts
        - finalize_blueprint
        - create_rca_dashboard
        - get_bookmark_dashboard_ids
        - get_dashboard_erf
        - update_report_link
        - update_text_card
        # Report/Bookmark CRUD
        - list_bookmarks_v2
        - create_bookmark
        - get_bookmark
        - update_bookmark
        - delete_bookmark
        - bulk_delete_bookmarks
        - bulk_update_bookmarks
        - bookmark_linked_dashboard_ids
        - get_bookmark_history
        # Cohort CRUD
        - list_cohorts_full
        - get_cohort
        - create_cohort
        - update_cohort
        - delete_cohort
        - bulk_delete_cohorts
        - bulk_update_cohorts
        # Feature Flag CRUD
        - list_feature_flags
        - create_feature_flag
        - get_feature_flag
        - update_feature_flag
        - delete_feature_flag
        - archive_feature_flag
        - restore_feature_flag
        - duplicate_feature_flag
        - set_flag_test_users
        - get_flag_history
        - get_flag_limits
        # Experiment CRUD
        - list_experiments
        - create_experiment
        - get_experiment
        - update_experiment
        - delete_experiment
        - launch_experiment
        - conclude_experiment
        - decide_experiment
        - archive_experiment
        - restore_experiment
        - duplicate_experiment
        - list_erf_experiments
        # Alert CRUD
        - list_alerts
        - create_alert
        - get_alert
        - update_alert
        - delete_alert
        - bulk_delete_alerts
        - get_alert_count
        - get_alert_history
        - test_alert
        - get_alert_screenshot_url
        - validate_alerts_for_bookmark
        # Annotation CRUD
        - list_annotations
        - create_annotation
        - get_annotation
        - update_annotation
        - delete_annotation
        - list_annotation_tags
        - create_annotation_tag
        # Webhook CRUD
        - list_webhooks
        - create_webhook
        - update_webhook
        - delete_webhook
        - test_webhook
        # Lexicon — Event Definitions
        - get_event_definitions
        - update_event_definition
        - delete_event_definition
        - bulk_update_event_definitions
        # Lexicon — Property Definitions
        - get_property_definitions
        - update_property_definition
        - bulk_update_property_definitions
        # Lexicon — Tags
        - list_lexicon_tags
        - create_lexicon_tag
        - update_lexicon_tag
        - delete_lexicon_tag
        # Lexicon — Tracking & History
        - get_tracking_metadata
        - get_event_history
        - get_property_history
        - export_lexicon
        # Drop Filter CRUD
        - list_drop_filters
        - create_drop_filter
        - update_drop_filter
        - delete_drop_filter
        - get_drop_filter_limits
        # Custom Property CRUD
        - list_custom_properties
        - create_custom_property
        - get_custom_property
        - update_custom_property
        - delete_custom_property
        - validate_custom_property
        # Lookup Table CRUD
        - list_lookup_tables
        - upload_lookup_table
        - mark_lookup_table_ready
        - get_lookup_upload_url
        - get_lookup_upload_status
        - update_lookup_table
        - delete_lookup_tables
        - download_lookup_table
        - get_lookup_download_url
        # Custom Event CRUD
        - list_custom_events
        - update_custom_event
        - delete_custom_event
        # Schema Registry CRUD
        - list_schema_registry
        - create_schema
        - create_schemas_bulk
        - update_schema
        - update_schemas_bulk
        - delete_schemas
        # Schema Enforcement
        - get_schema_enforcement
        - init_schema_enforcement
        - update_schema_enforcement
        - replace_schema_enforcement
        - delete_schema_enforcement
        # Data Auditing
        - run_audit
        - run_audit_events_only
        # Data Volume Anomalies
        - list_data_volume_anomalies
        - update_anomaly
        - bulk_update_anomalies
        # Event Deletion Requests
        - list_deletion_requests
        - create_deletion_request
        - cancel_deletion_request
        - preview_deletion_filters
