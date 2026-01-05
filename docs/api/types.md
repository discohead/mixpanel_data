# Result Types

All result types are immutable frozen dataclasses with:

- Lazy DataFrame conversion via the `.df` property
- JSON serialization via the `.to_dict()` method
- Full type hints for IDE/mypy support

## Fetch Results

::: mixpanel_data.FetchResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Parallel Fetch Types

Types for parallel event fetching with progress tracking and failure handling.

::: mixpanel_data.ParallelFetchResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.BatchProgress
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.BatchResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Parallel Profile Fetch Types

Types for parallel profile fetching with page-based progress tracking.

::: mixpanel_data.ParallelProfileResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.ProfileProgress
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.ProfilePageResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Query Results

::: mixpanel_data.SegmentationResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.FunnelResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.FunnelStep
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.RetentionResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.CohortInfo
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.JQLResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Discovery Types

::: mixpanel_data.FunnelInfo
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.SavedCohort
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.TopEvent
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Lexicon Types

::: mixpanel_data.LexiconSchema
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.LexiconDefinition
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.LexiconProperty
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.LexiconMetadata
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Event Analytics Results

::: mixpanel_data.EventCountsResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.PropertyCountsResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Advanced Query Results

::: mixpanel_data.UserEvent
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.ActivityFeedResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.FrequencyResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.NumericBucketResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.NumericSumResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.NumericAverageResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Bookmark Types

::: mixpanel_data.BookmarkInfo
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.SavedReportResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.FlowsResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## JQL Discovery Types

::: mixpanel_data.PropertyDistributionResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.PropertyValueCount
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.NumericPropertySummaryResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.DailyCountsResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.DailyCount
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.EngagementDistributionResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.EngagementBucket
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.PropertyCoverageResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.PropertyCoverage
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Introspection Types

::: mixpanel_data.ColumnSummary
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.SummaryResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.EventStats
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.EventBreakdownResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.ColumnStatsResult
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Storage Types

::: mixpanel_data.TableMetadata
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.TableInfo
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.ColumnInfo
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.TableSchema
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.WorkspaceInfo
    options:
      show_root_heading: true
      show_root_toc_entry: true
