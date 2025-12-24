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

::: mixpanel_data.InsightsResult
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
