# Entity Management

Manage Mixpanel dashboards, reports (bookmarks), cohorts, feature flags, experiments, alerts, annotations, and webhooks programmatically. Full CRUD operations with bulk support. For data governance operations (Lexicon definitions, drop filters, custom properties, custom events, and lookup tables), see the [Data Governance guide](data-governance.md).

!!! note "Prerequisites"
    Entity management requires **authentication** — service account or OAuth credentials.

    **Scoping differs by entity type:**

    - **Dashboards, reports, cohorts, alerts, annotations, webhooks** require a **workspace ID** — set via `MP_WORKSPACE_ID` env var, `--workspace` / `-w` CLI flag, `Workspace(workspace=N)`, or `ws.use(workspace=N)`. List available workspaces with `mp workspace list` or `ws.workspaces()`.
    - **Feature flags and experiments** are **project-scoped** and do NOT require a workspace ID.

## Dashboards

### List Dashboards

=== "Python"

    ```python
    import mixpanel_headless as mp

    ws = mp.Workspace()

    # List all dashboards
    dashboards = ws.list_dashboards()
    for d in dashboards:
        print(f"{d.id}: {d.title}")

    # Filter by specific IDs
    dashboards = ws.list_dashboards(ids=[123, 456])
    ```

=== "CLI"

    ```bash
    # List all dashboards
    mp dashboards list

    # Filter by IDs
    mp dashboards list --ids 123,456

    # Table format for quick scanning
    mp dashboards list --format table
    ```

### Create a Dashboard

=== "Python"

    ```python
    new_dash = ws.create_dashboard(mp.CreateDashboardParams(
        title="Q1 Metrics",
        description="Quarterly performance overview",
    ))
    print(f"Created dashboard {new_dash.id}: {new_dash.title}")
    ```

=== "CLI"

    ```bash
    mp dashboards create --title "Q1 Metrics" --description "Quarterly performance overview"
    ```

### Get, Update, Delete

=== "Python"

    ```python
    # Get a dashboard by ID
    dash = ws.get_dashboard(123)

    # Update
    updated = ws.update_dashboard(123, mp.UpdateDashboardParams(
        title="Q1 Metrics (Updated)",
        description="Revised quarterly overview",
    ))

    # Delete
    ws.delete_dashboard(123)

    # Bulk delete
    ws.bulk_delete_dashboards([123, 456, 789])
    ```

=== "CLI"

    ```bash
    # Get details
    mp dashboards get 123

    # Update
    mp dashboards update 123 --title "Q1 Metrics (Updated)"

    # Delete
    mp dashboards delete 123

    # Bulk delete
    mp dashboards bulk-delete --ids 123,456,789
    ```

### Favorites and Pins

=== "Python"

    ```python
    ws.favorite_dashboard(123)
    ws.unfavorite_dashboard(123)

    ws.pin_dashboard(123)
    ws.unpin_dashboard(123)
    ```

=== "CLI"

    ```bash
    mp dashboards favorite 123
    mp dashboards unfavorite 123

    mp dashboards pin 123
    mp dashboards unpin 123
    ```

### Add a Report to a Dashboard

=== "Python"

    ```python
    updated_dash = ws.add_report_to_dashboard(
        dashboard_id=123,
        bookmark_id=456
    )
    ```

=== "CLI"

    ```bash
    mp dashboards add-report 123 456
    ```

### Remove a Report from a Dashboard

=== "Python"

    ```python
    updated_dash = ws.remove_report_from_dashboard(
        dashboard_id=123,
        bookmark_id=456
    )
    ```

=== "CLI"

    ```bash
    mp dashboards remove-report 123 456
    ```

### Blueprint Dashboards

Create dashboards from pre-built templates:

=== "Python"

    ```python
    # List available templates
    templates = ws.list_blueprint_templates()
    for t in templates:
        print(f"{t.title_key}: {t.number_of_reports} reports")

    # Create from template
    dash = ws.create_blueprint(template_type="product_analytics")

    # Configure and finalize
    config = ws.get_blueprint_config(dash.id)
    ws.finalize_blueprint(mp.BlueprintFinishParams(
        dashboard_id=dash.id,
        cards=config.cards,
    ))
    ```

=== "CLI"

    ```bash
    # List templates
    mp dashboards blueprints

    # Create from template
    mp dashboards blueprint-create --template-type product_analytics
    ```

### Advanced Dashboard Operations

=== "Python"

    ```python
    # Create an RCA (Root Cause Analysis) dashboard
    rca_dash = ws.create_rca_dashboard(mp.CreateRcaDashboardParams(
        rca_source_id=123,
        rca_source_data=mp.RcaSourceData(source_type="metric"),
    ))

    # Get ERF metrics
    erf = ws.get_dashboard_erf(dashboard_id=123)

    # Update dashboard components
    ws.update_report_link(
        dashboard_id=123,
        report_link_id=456,
        params=mp.UpdateReportLinkParams(link_type="embedded"),
    )
    ws.update_text_card(
        dashboard_id=123,
        text_card_id=789,
        params=mp.UpdateTextCardParams(markdown="## Updated Header"),
    )
    ```

=== "CLI"

    ```bash
    # Get ERF metrics
    mp dashboards erf 123

    # Update text card
    mp dashboards update-text-card 123 --text-card-id 789 --markdown "## Updated"
    ```

---

## Reports (Bookmarks)

Reports in Mixpanel are stored as "bookmarks". Each bookmark has a type (insights, funnels, flows, retention, etc.) and a params JSON object defining the query.

### List Reports

=== "Python"

    ```python
    # List all reports
    reports = ws.list_bookmarks_v2()

    # Filter by type
    insights = ws.list_bookmarks_v2(bookmark_type="insights")
    funnels = ws.list_bookmarks_v2(bookmark_type="funnels")

    # Filter by IDs
    specific = ws.list_bookmarks_v2(ids=[123, 456])

    for r in reports:
        print(f"{r.id}: {r.name} ({r.bookmark_type})")
    ```

=== "CLI"

    ```bash
    # List all reports
    mp reports list

    # Filter by type
    mp reports list --type insights
    mp reports list --type funnels

    # Filter by IDs
    mp reports list --ids 123,456
    ```

### Create a Report

=== "Python"

    ```python
    report = ws.create_bookmark(mp.CreateBookmarkParams(
        name="Daily Signups",
        bookmark_type="insights",
        description="Track daily signup volume",
        params={"event": "Signup"},
    ))
    print(f"Created report {report.id}: {report.name}")
    ```

=== "CLI"

    ```bash
    mp reports create \
        --name "Daily Signups" \
        --type insights \
        --description "Track daily signup volume" \
        --params '{"event": "Signup"}'
    ```

### Get, Update, Delete

=== "Python"

    ```python
    # Get
    report = ws.get_bookmark(123)

    # Update
    updated = ws.update_bookmark(123, mp.UpdateBookmarkParams(
        name="Daily Signups v2",
        description="Updated tracking",
    ))

    # Delete
    ws.delete_bookmark(123)

    # Bulk operations
    ws.bulk_delete_bookmarks([123, 456])
    ws.bulk_update_bookmarks([
        mp.BulkUpdateBookmarkEntry(id=123, name="Renamed Report"),
        mp.BulkUpdateBookmarkEntry(id=456, description="Updated desc"),
    ])
    ```

=== "CLI"

    ```bash
    # Get
    mp reports get 123

    # Update
    mp reports update 123 --name "Daily Signups v2"

    # Delete
    mp reports delete 123

    # Bulk delete
    mp reports bulk-delete --ids 123,456
    ```

### Report History and Dashboard Links

=== "Python"

    ```python
    # View change history
    history = ws.get_bookmark_history(bookmark_id=123)
    for entry in history.data:
        print(entry)

    # Paginate through history
    history = ws.get_bookmark_history(bookmark_id=123, page_size=10)
    if history.pagination.has_more:
        next_page = ws.get_bookmark_history(
            bookmark_id=123,
            cursor=history.pagination.cursor,
        )

    # Find which dashboards contain this report
    dashboard_ids = ws.bookmark_linked_dashboard_ids(bookmark_id=123)
    ```

=== "CLI"

    ```bash
    # View history
    mp reports history 123

    # Get linked dashboards
    mp reports linked-dashboards 123
    ```

---

## Cohorts

### List Cohorts

=== "Python"

    ```python
    # List all cohorts
    cohorts = ws.list_cohorts_full()

    # Filter by data group
    cohorts = ws.list_cohorts_full(data_group_id="default")

    # Filter by IDs
    cohorts = ws.list_cohorts_full(ids=[123, 456])

    for c in cohorts:
        print(f"{c.id}: {c.name} ({c.count} users)")
    ```

=== "CLI"

    ```bash
    # List all cohorts
    mp cohorts list

    # Filter by data group
    mp cohorts list --data-group-id default

    # Filter by IDs
    mp cohorts list --ids 123,456
    ```

### Create a Cohort

=== "Python"

    ```python
    cohort = ws.create_cohort(mp.CreateCohortParams(
        name="Power Users",
        description="Users with 10+ sessions in last 30 days",
    ))
    print(f"Created cohort {cohort.id}: {cohort.name}")
    ```

=== "CLI"

    ```bash
    mp cohorts create --name "Power Users" --description "Users with 10+ sessions"
    ```

### Get, Update, Delete

=== "Python"

    ```python
    # Get
    cohort = ws.get_cohort(123)

    # Update
    updated = ws.update_cohort(123, mp.UpdateCohortParams(
        name="Super Users",
        description="Updated criteria",
    ))

    # Delete
    ws.delete_cohort(123)

    # Bulk operations
    ws.bulk_delete_cohorts([123, 456])
    ws.bulk_update_cohorts([
        mp.BulkUpdateCohortEntry(id=123, name="Renamed Cohort"),
        mp.BulkUpdateCohortEntry(id=456, description="Updated"),
    ])
    ```

=== "CLI"

    ```bash
    # Get
    mp cohorts get 123

    # Update
    mp cohorts update 123 --name "Super Users"

    # Delete
    mp cohorts delete 123

    # Bulk delete
    mp cohorts bulk-delete --ids 123,456
    ```

---

## Feature Flags

Feature flags are **project-scoped** — no workspace ID required. They use **UUID string IDs** (not integer IDs like dashboards/reports/cohorts).

!!! warning "PUT Semantics"
    Feature flag `update` uses **full replacement** (PUT semantics). All required fields (`name`, `key`, `status`, `ruleset`) must be provided on every update — even if you're only changing one field.

### List Feature Flags

=== "Python"

    ```python
    import mixpanel_headless as mp

    ws = mp.Workspace()

    # List all flags (excludes archived by default)
    flags = ws.list_feature_flags()
    for f in flags:
        print(f"{f.name} ({f.key}): {f.status.value}")

    # Include archived flags
    flags = ws.list_feature_flags(include_archived=True)
    ```

=== "CLI"

    ```bash
    # List all flags
    mp flags list

    # Include archived
    mp flags list --include-archived

    # Table format
    mp flags list --format table
    ```

### Create a Feature Flag

=== "Python"

    ```python
    flag = ws.create_feature_flag(mp.CreateFeatureFlagParams(
        name="Dark Mode",
        key="dark_mode",
        description="Enable dark mode UI",
        tags=["ui", "frontend"],
    ))
    print(f"Created flag {flag.id}: {flag.key}")
    ```

=== "CLI"

    ```bash
    mp flags create --name "Dark Mode" --key dark_mode \
        --description "Enable dark mode UI" --tags "ui,frontend"
    ```

### Get, Update, Delete

=== "Python"

    ```python
    # Get a flag by UUID
    flag = ws.get_feature_flag("abc-123-uuid")

    # Update (PUT — all required fields must be provided)
    updated = ws.update_feature_flag("abc-123-uuid", mp.UpdateFeatureFlagParams(
        name="Dark Mode",
        key="dark_mode",
        status=mp.FeatureFlagStatus.ENABLED,
        ruleset=flag.ruleset,  # Must provide complete ruleset
    ))

    # Delete
    ws.delete_feature_flag("abc-123-uuid")
    ```

=== "CLI"

    ```bash
    # Get details
    mp flags get abc-123-uuid

    # Update (all required fields)
    mp flags update abc-123-uuid \
        --name "Dark Mode" --key dark_mode \
        --status enabled --ruleset '{"variants": [], "rollout": []}'

    # Delete
    mp flags delete abc-123-uuid
    ```

### Archive, Restore, Duplicate

=== "Python"

    ```python
    # Archive (soft-delete)
    ws.archive_feature_flag("abc-123-uuid")

    # Restore an archived flag
    restored = ws.restore_feature_flag("abc-123-uuid")

    # Duplicate
    copy = ws.duplicate_feature_flag("abc-123-uuid")
    ```

=== "CLI"

    ```bash
    mp flags archive abc-123-uuid
    mp flags restore abc-123-uuid
    mp flags duplicate abc-123-uuid
    ```

### Test Users and History

=== "Python"

    ```python
    # Assign test users to specific variants
    ws.set_flag_test_users("abc-123-uuid", mp.SetTestUsersParams(
        users={"On": "user-1", "Off": "user-2"}
    ))

    # View change history
    history = ws.get_flag_history("abc-123-uuid")
    print(f"{history.count} changes")

    # Check account limits
    limits = ws.get_flag_limits()
    print(f"Using {limits.current_usage}/{limits.limit} flags")
    ```

=== "CLI"

    ```bash
    # Set test users
    mp flags set-test-users abc-123-uuid \
        --users '{"On": "user-1", "Off": "user-2"}'

    # View history
    mp flags history abc-123-uuid

    # Check limits
    mp flags limits
    ```

---

## Experiments

Experiments are **project-scoped** — no workspace ID required. They have a distinct lifecycle with managed state transitions:

```
Draft → Active (launch) → Concluded (conclude) → Success/Fail (decide)
```

!!! info "PATCH Semantics"
    Experiment `update` uses **partial update** (PATCH semantics). Only provide the fields you want to change.

### List Experiments

=== "Python"

    ```python
    import mixpanel_headless as mp

    ws = mp.Workspace()

    experiments = ws.list_experiments()
    for e in experiments:
        print(f"{e.name}: {e.status.value if e.status else 'unknown'}")

    # Include archived
    experiments = ws.list_experiments(include_archived=True)
    ```

=== "CLI"

    ```bash
    mp experiments list
    mp experiments list --include-archived
    ```

### Create an Experiment

=== "Python"

    ```python
    exp = ws.create_experiment(mp.CreateExperimentParams(
        name="Checkout Flow Test",
        description="Test simplified checkout",
        hypothesis="Simpler checkout increases conversions by 10%",
    ))
    print(f"Created experiment {exp.id}: {exp.name}")
    ```

=== "CLI"

    ```bash
    mp experiments create --name "Checkout Flow Test" \
        --description "Test simplified checkout" \
        --hypothesis "Simpler checkout increases conversions by 10%"
    ```

### Get, Update, Delete

=== "Python"

    ```python
    # Get
    exp = ws.get_experiment("xyz-456-uuid")

    # Update (PATCH — only changed fields)
    updated = ws.update_experiment("xyz-456-uuid", mp.UpdateExperimentParams(
        description="Updated hypothesis and metrics",
    ))

    # Delete
    ws.delete_experiment("xyz-456-uuid")
    ```

=== "CLI"

    ```bash
    mp experiments get xyz-456-uuid
    mp experiments update xyz-456-uuid --description "Updated"
    mp experiments delete xyz-456-uuid
    ```

### Experiment Lifecycle

The key differentiator of experiments: a managed lifecycle with state transitions.

=== "Python"

    ```python
    # 1. Create (starts in Draft)
    exp = ws.create_experiment(mp.CreateExperimentParams(
        name="Pricing Page Test"
    ))

    # 2. Launch (Draft → Active)
    launched = ws.launch_experiment(exp.id)

    # 3. Conclude (Active → Concluded)
    concluded = ws.conclude_experiment(exp.id)
    # Or with an explicit end date:
    concluded = ws.conclude_experiment(
        exp.id,
        params=mp.ExperimentConcludeParams(end_date="2026-04-01"),
    )

    # 4. Decide (Concluded → Success or Fail)
    decided = ws.decide_experiment(exp.id, mp.ExperimentDecideParams(
        success=True,
        variant="simplified",
        message="15% conversion lift confirmed",
    ))
    ```

=== "CLI"

    ```bash
    # Launch
    mp experiments launch xyz-456-uuid

    # Conclude
    mp experiments conclude xyz-456-uuid
    mp experiments conclude xyz-456-uuid --end-date 2026-04-01

    # Decide as success
    mp experiments decide xyz-456-uuid --success \
        --variant simplified --message "15% conversion lift confirmed"

    # Decide as failure
    mp experiments decide xyz-456-uuid --no-success \
        --message "No significant difference"
    ```

### Archive, Restore, Duplicate

=== "Python"

    ```python
    ws.archive_experiment("xyz-456-uuid")
    restored = ws.restore_experiment("xyz-456-uuid")
    dup = ws.duplicate_experiment(
        "xyz-456-uuid",
        mp.DuplicateExperimentParams(name="Pricing Page Test v2"),
    )
    ```

=== "CLI"

    ```bash
    mp experiments archive xyz-456-uuid
    mp experiments restore xyz-456-uuid
    mp experiments duplicate xyz-456-uuid --name "Pricing Page Test v2"
    ```

### ERF Experiments

List experiments in ERF (Experiment Results Framework) format:

=== "Python"

    ```python
    erf = ws.list_erf_experiments()
    ```

=== "CLI"

    ```bash
    mp experiments erf
    ```

---

## Alerts

Custom alerts monitor saved reports and notify when conditions are met. Alerts are **workspace-scoped** and linked to bookmarks (saved reports).

### List Alerts

=== "Python"

    ```python
    import mixpanel_headless as mp

    ws = mp.Workspace()

    # List all alerts
    alerts = ws.list_alerts()
    for a in alerts:
        print(f"{a.id}: {a.name} (paused={a.paused})")

    # Filter by linked bookmark
    alerts = ws.list_alerts(bookmark_id=12345)
    ```

=== "CLI"

    ```bash
    # List all alerts
    mp alerts list

    # Filter by bookmark
    mp alerts list --bookmark-id 12345

    # Table format
    mp alerts list --format table
    ```

### Create an Alert

=== "Python"

    ```python
    alert = ws.create_alert(mp.CreateAlertParams(
        bookmark_id=12345,
        name="Daily signups drop",
        condition={
            "keys": [{"header": "Signup", "value": "Signup"}],
            "type": "absolute",
            "op": "<",
            "value": 100,
        },
        frequency=mp.AlertFrequencyPreset.DAILY,
        paused=False,
        subscriptions=[{"type": "email", "value": "team@example.com"}],
    ))
    print(f"Created alert {alert.id}: {alert.name}")
    ```

=== "CLI"

    ```bash
    mp alerts create \
        --bookmark-id 12345 \
        --name "Daily signups drop" \
        --condition '{"keys": [{"header": "Signup", "value": "Signup"}], "type": "absolute", "op": "<", "value": 100}' \
        --frequency 86400 \
        --subscriptions '[{"type": "email", "value": "team@example.com"}]'
    ```

### Get, Update, Delete

=== "Python"

    ```python
    # Get
    alert = ws.get_alert(42)

    # Update (PATCH semantics)
    updated = ws.update_alert(42, mp.UpdateAlertParams(
        name="Updated alert name",
        paused=True,
    ))

    # Delete
    ws.delete_alert(42)

    # Bulk delete
    ws.bulk_delete_alerts([42, 43, 44])
    ```

=== "CLI"

    ```bash
    # Get
    mp alerts get 42

    # Update
    mp alerts update 42 --name "Updated alert name" --paused

    # Delete
    mp alerts delete 42

    # Bulk delete
    mp alerts bulk-delete --ids 42,43,44
    ```

### Monitoring

=== "Python"

    ```python
    # Check alert count and limits
    count = ws.get_alert_count()
    print(f"{count.anomaly_alerts_count}/{count.alert_limit} alerts")

    # View trigger history (paginated)
    history = ws.get_alert_history(42, page_size=10)
    for entry in history.results:
        print(entry)

    # Send a test notification
    result = ws.test_alert(mp.CreateAlertParams(
        bookmark_id=12345,
        name="Test",
        condition={"type": "absolute", "op": "<", "value": 100},
        frequency=86400,
        paused=False,
        subscriptions=[{"type": "email", "value": "me@example.com"}],
    ))

    # Get screenshot URL
    screenshot = ws.get_alert_screenshot_url("gcs-key-here")
    print(screenshot.signed_url)
    ```

=== "CLI"

    ```bash
    # Alert count and limits
    mp alerts count

    # Trigger history
    mp alerts history 42 --page-size 10

    # Test notification
    mp alerts test \
        --bookmark-id 12345 \
        --name "Test" \
        --condition '{"type": "absolute", "op": "<", "value": 100}' \
        --frequency 86400 \
        --subscriptions '[{"type": "email", "value": "me@example.com"}]'

    # Screenshot URL
    mp alerts screenshot --gcs-key "gcs-key-here"
    ```

### Validate Alerts

Check whether alerts are compatible with a bookmark configuration:

=== "Python"

    ```python
    result = ws.validate_alerts_for_bookmark(mp.ValidateAlertsForBookmarkParams(
        alert_ids=[1, 2, 3],
        bookmark_type="insights",
        bookmark_params={"event": "Signup"},
    ))
    if result.invalid_count > 0:
        for v in result.alert_validations:
            if not v.valid:
                print(f"{v.alert_name}: {v.reason}")
    ```

=== "CLI"

    ```bash
    mp alerts validate \
        --alert-ids 1,2,3 \
        --bookmark-type insights \
        --bookmark-params '{"event": "Signup"}'
    ```

---

## Annotations

Timeline annotations mark important events (releases, incidents, campaigns) on your Mixpanel charts.

### List Annotations

=== "Python"

    ```python
    import mixpanel_headless as mp

    ws = mp.Workspace()

    # List all annotations
    annotations = ws.list_annotations()

    # Filter by date range
    annotations = ws.list_annotations(
        from_date="2025-01-01",
        to_date="2025-03-31",
    )

    # Filter by tags
    annotations = ws.list_annotations(tags=[1, 2])

    for ann in annotations:
        print(f"{ann.date}: {ann.description}")
    ```

=== "CLI"

    ```bash
    # List all annotations
    mp annotations list

    # Filter by date range
    mp annotations list --from-date 2025-01-01 --to-date 2025-03-31

    # Filter by tags
    mp annotations list --tags 1,2
    ```

### Create an Annotation

!!! note "Date Format"
    Annotation dates must use `%Y-%m-%d %H:%M:%S` format (e.g., `"2025-03-31 00:00:00"`).

=== "Python"

    ```python
    annotation = ws.create_annotation(mp.CreateAnnotationParams(
        date="2025-03-31 00:00:00",
        description="v2.5 release",
        tags=[1],  # Optional tag IDs
    ))
    print(f"Created annotation {annotation.id}")
    ```

=== "CLI"

    ```bash
    mp annotations create \
        --date "2025-03-31 00:00:00" \
        --description "v2.5 release" \
        --tags 1
    ```

### Get, Update, Delete

!!! note "Immutable Date"
    The annotation date cannot be changed after creation. Only `description` and `tags` are updatable.

=== "Python"

    ```python
    # Get
    ann = ws.get_annotation(123)

    # Update (description and tags only)
    updated = ws.update_annotation(123, mp.UpdateAnnotationParams(
        description="v2.5 release (hotfix applied)",
    ))

    # Delete
    ws.delete_annotation(123)
    ```

=== "CLI"

    ```bash
    # Get
    mp annotations get 123

    # Update
    mp annotations update 123 --description "v2.5 release (hotfix applied)"

    # Delete
    mp annotations delete 123
    ```

### Annotation Tags

Organize annotations with tags:

=== "Python"

    ```python
    # List tags
    tags = ws.list_annotation_tags()
    for t in tags:
        print(f"{t.id}: {t.name}")

    # Create a tag
    tag = ws.create_annotation_tag(mp.CreateAnnotationTagParams(name="releases"))
    ```

=== "CLI"

    ```bash
    # List tags
    mp annotations tags list

    # Create a tag
    mp annotations tags create --name releases
    ```

---

## Webhooks

Project webhooks receive HTTP notifications when events occur in your Mixpanel project.

### List Webhooks

=== "Python"

    ```python
    import mixpanel_headless as mp

    ws = mp.Workspace()

    webhooks = ws.list_webhooks()
    for wh in webhooks:
        print(f"{wh.id}: {wh.name} ({wh.url}) enabled={wh.is_enabled}")
    ```

=== "CLI"

    ```bash
    mp webhooks list
    mp webhooks list --format table
    ```

### Create a Webhook

=== "Python"

    ```python
    result = ws.create_webhook(mp.CreateWebhookParams(
        name="Pipeline webhook",
        url="https://example.com/webhook",
    ))
    print(f"Created webhook {result.id}")

    # With basic auth
    result = ws.create_webhook(mp.CreateWebhookParams(
        name="Authenticated webhook",
        url="https://example.com/webhook",
        auth_type=mp.WebhookAuthType.BASIC,
        username="user",
        password="secret",
    ))
    ```

=== "CLI"

    ```bash
    # Simple webhook
    mp webhooks create --name "Pipeline webhook" --url https://example.com/webhook

    # With basic auth
    mp webhooks create \
        --name "Authenticated webhook" \
        --url https://example.com/webhook \
        --auth-type basic \
        --username user \
        --password secret
    ```

### Update, Delete

=== "Python"

    ```python
    # Update (PATCH semantics)
    result = ws.update_webhook("wh-uuid-123", mp.UpdateWebhookParams(
        name="Updated webhook",
        is_enabled=False,
    ))

    # Delete
    ws.delete_webhook("wh-uuid-123")
    ```

=== "CLI"

    ```bash
    # Update
    mp webhooks update wh-uuid-123 --name "Updated webhook" --disable

    # Delete
    mp webhooks delete wh-uuid-123
    ```

### Test Connectivity

=== "Python"

    ```python
    result = ws.test_webhook(mp.WebhookTestParams(
        url="https://example.com/webhook",
    ))
    if result.success:
        print(f"Webhook reachable (HTTP {result.status_code})")
    else:
        print(f"Webhook failed: {result.message}")
    ```

=== "CLI"

    ```bash
    mp webhooks test --url https://example.com/webhook
    ```

---

## Next Steps

- [API Reference — Workspace](../api/workspace.md) — Complete method signatures and docstrings
- [API Reference — Types](../api/types.md) — Dashboard, Bookmark, Cohort, Feature Flag, Experiment, Alert, Annotation, and Webhook type definitions
- [CLI Reference](../cli/index.md) — Full CLI command documentation
- [Data Governance Guide](data-governance.md) — Manage Lexicon definitions, drop filters, custom properties, custom events, and lookup tables
