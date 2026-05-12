# Result Types

!!! tip "Explore on DeepWiki"
    🤖 **[Result Types Reference →](https://deepwiki.com/mixpanel/mixpanel-headless/7.5-result-type-reference)**

    Ask questions about result structures, DataFrame conversion, or type usage patterns.

All result types are immutable frozen dataclasses with:

- Lazy DataFrame conversion via the `.df` property
- JSON serialization via the `.to_dict()` method
- Full type hints for IDE/mypy support

## App API Types

Types for the Mixpanel App API infrastructure.

::: mixpanel_headless.PublicWorkspace
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CursorPagination
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.PaginatedResponse
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Insights Query Types

Types for `Workspace.query()` — typed Insights engine queries with composable metrics, filters, and breakdowns.

::: mixpanel_headless.Metric
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.Formula
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.Filter
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.GroupBy
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.ListItemGroupMode
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.QueryResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Cohort Query Types

Types for cohort-scoped queries — filter by cohort, break down by cohort membership, or track cohort size as a metric across all query engines.

::: mixpanel_headless.CohortBreakdown
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CohortMetric
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Custom Property Query Types

Types for using saved or inline custom properties as property references in query breakdowns, filters, and metric measurement. See [Custom Properties in Queries](../guide/query.md#custom-properties-in-queries) for usage guide.

::: mixpanel_headless.CustomPropertyRef
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.InlineCustomProperty
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.PropertyInput
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Advanced Query Types

Types for advanced query features — period-over-period comparison, frequency analysis, and frequency filtering across query engines.

::: mixpanel_headless.TimeComparison
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.FrequencyBreakdown
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.FrequencyFilter
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Cohort Definition Types

Types for building inline cohort definitions programmatically — used with `Filter.in_cohort()`, `CohortBreakdown`, and `CohortMetric`.

::: mixpanel_headless.CohortDefinition
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CohortCriteria
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Funnel Query Types

Types for `Workspace.query_funnel()` — typed funnel conversion analysis with step definitions, exclusions, and conversion windows.

::: mixpanel_headless.FunnelStep
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.Exclusion
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.HoldingConstant
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.FunnelQueryResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Retention Query Types

Types for `Workspace.query_retention()` — typed retention analysis with event pairs, custom buckets, alignment modes, and segmentation.

::: mixpanel_headless.RetentionEvent
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.RetentionAlignment
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.RetentionMode
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.RetentionMathType
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.RetentionQueryResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Flow Query Types

Types for `Workspace.query_flow()` — typed flow path analysis with step definitions, direction controls, and visualization modes.

::: mixpanel_headless.FlowStep
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.FlowTreeNode
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.FlowQueryResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Legacy Query Results

::: mixpanel_headless.SegmentationResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.FunnelResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.FunnelResultStep
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.RetentionResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CohortInfo
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.JQLResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Discovery Types

::: mixpanel_headless.FunnelInfo
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.SavedCohort
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.TopEvent
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Subproperty Discovery Types

Types for `Workspace.subproperties()` — schema discovery for list-of-object event properties. See [Subproperties](../guide/discovery.md#subproperties) for usage.

::: mixpanel_headless.SubPropertyInfo
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Lexicon Types

::: mixpanel_headless.LexiconSchema
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.LexiconDefinition
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.LexiconProperty
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.LexiconMetadata
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Event Analytics Results

::: mixpanel_headless.EventCountsResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.PropertyCountsResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Advanced Query Results

::: mixpanel_headless.UserEvent
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.ActivityFeedResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.FrequencyResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.NumericBucketResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.NumericSumResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.NumericAverageResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Bookmark Types

::: mixpanel_headless.BookmarkInfo
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.SavedReportResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.FlowsResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## JQL Discovery Types

::: mixpanel_headless.PropertyDistributionResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.PropertyValueCount
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.NumericPropertySummaryResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.DailyCountsResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.DailyCount
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.EngagementDistributionResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.EngagementBucket
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.PropertyCoverageResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.PropertyCoverage
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Dashboard CRUD Types

::: mixpanel_headless.Dashboard
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CreateDashboardParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateDashboardParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BlueprintTemplate
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BlueprintConfig
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BlueprintCard
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BlueprintFinishParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CreateRcaDashboardParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.RcaSourceData
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateReportLinkParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateTextCardParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Report CRUD Types

::: mixpanel_headless.Bookmark
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BookmarkMetadata
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CreateBookmarkParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateBookmarkParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BulkUpdateBookmarkEntry
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BookmarkHistoryResponse
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BookmarkHistoryPagination
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Cohort CRUD Types

::: mixpanel_headless.Cohort
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CohortCreator
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CreateCohortParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateCohortParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BulkUpdateCohortEntry
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Feature Flag Enums

::: mixpanel_headless.FeatureFlagStatus
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.ServingMethod
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.FlagContractStatus
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Feature Flag Types

::: mixpanel_headless.FeatureFlag
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CreateFeatureFlagParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateFeatureFlagParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.SetTestUsersParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.FlagHistoryParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.FlagHistoryResponse
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.FlagLimitsResponse
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Experiment Enums

::: mixpanel_headless.ExperimentStatus
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Experiment Types

::: mixpanel_headless.ExperimentCreator
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.Experiment
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CreateExperimentParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateExperimentParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.ExperimentConcludeParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.ExperimentDecideParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.DuplicateExperimentParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Annotation Types

::: mixpanel_headless.Annotation
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AnnotationUser
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AnnotationTag
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CreateAnnotationParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateAnnotationParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CreateAnnotationTagParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Webhook Enums

::: mixpanel_headless.WebhookAuthType
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Webhook Types

::: mixpanel_headless.ProjectWebhook
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CreateWebhookParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateWebhookParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.WebhookTestParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.WebhookTestResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.WebhookMutationResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Alert Enums

::: mixpanel_headless.AlertFrequencyPreset
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Alert Types

::: mixpanel_headless.CustomAlert
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AlertBookmark
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AlertCreator
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AlertWorkspace
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AlertProject
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CreateAlertParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateAlertParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AlertCount
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AlertHistoryPagination
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AlertHistoryResponse
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AlertScreenshotResponse
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AlertValidation
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.ValidateAlertsForBookmarkParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.ValidateAlertsForBookmarkResponse
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Data Governance Enums

::: mixpanel_headless.PropertyResourceType
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CustomPropertyResourceType
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Event Definition Types

::: mixpanel_headless.EventDefinition
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateEventDefinitionParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BulkEventUpdate
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BulkUpdateEventsParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Property Definition Types

::: mixpanel_headless.PropertyDefinition
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdatePropertyDefinitionParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BulkPropertyUpdate
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BulkUpdatePropertiesParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Lexicon Tag Types

::: mixpanel_headless.LexiconTag
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CreateTagParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateTagParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Drop Filter Types

::: mixpanel_headless.DropFilter
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CreateDropFilterParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateDropFilterParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.DropFilterLimitsResponse
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Custom Property Types

::: mixpanel_headless.ComposedPropertyValue
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CustomProperty
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CreateCustomPropertyParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateCustomPropertyParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Lookup Table Types

::: mixpanel_headless.LookupTable
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UploadLookupTableParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.MarkLookupTableReadyParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.LookupTableUploadUrl
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateLookupTableParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Schema Registry Types

Types for managing JSON Schema Draft 7 definitions in the schema registry.

::: mixpanel_headless.SchemaEntry
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BulkCreateSchemasParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BulkCreateSchemasResponse
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BulkPatchResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.DeleteSchemasResponse
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Schema Enforcement Types

Types for configuring schema enforcement policies.

::: mixpanel_headless.SchemaEnforcementConfig
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.InitSchemaEnforcementParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateSchemaEnforcementParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.ReplaceSchemaEnforcementParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Data Audit Types

Types for schema audit operations and violation reporting.

::: mixpanel_headless.AuditViolation
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AuditResponse
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Data Volume Anomaly Types

Types for monitoring and managing data volume anomalies.

::: mixpanel_headless.DataVolumeAnomaly
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.UpdateAnomalyParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BulkAnomalyEntry
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BulkUpdateAnomalyParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Event Deletion Request Types

Types for managing event deletion requests.

::: mixpanel_headless.EventDeletionRequest
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.CreateDeletionRequestParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.PreviewDeletionFiltersParams
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Business Context Types

Types for the markdown documentation that grounds AI assistants — see the [Business Context guide](../guide/business-context.md). Both org and project scopes return the same `BusinessContext` model; `BusinessContextChain` bundles both for the convenience `get_business_context_chain()` round-trip.

The 50,000-character cap is exposed as the constant `mixpanel_headless.BUSINESS_CONTEXT_MAX_CHARS` and enforced both client-side (before any HTTP call) and server-side.

::: mixpanel_headless.BusinessContext
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.BusinessContextChain
    options:
      show_root_heading: true
      show_root_toc_entry: true
