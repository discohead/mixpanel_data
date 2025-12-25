"""
mixpanel_data - Python library for working with Mixpanel analytics data.

Designed for AI coding agents. Fetch data once into a local DuckDB database,
then query it repeatedly with SQL.
"""

from mixpanel_data._literal_types import CountType, HourDayUnit, TimeUnit
from mixpanel_data.exceptions import (
    AccountExistsError,
    AccountNotFoundError,
    APIError,
    AuthenticationError,
    ConfigError,
    JQLSyntaxError,
    MixpanelDataError,
    QueryError,
    RateLimitError,
    ServerError,
    TableExistsError,
    TableNotFoundError,
)
from mixpanel_data.types import (
    ActivityFeedResult,
    CohortInfo,
    ColumnInfo,
    ColumnStatsResult,
    ColumnSummary,
    EntityType,
    EventBreakdownResult,
    EventCountsResult,
    EventStats,
    FetchResult,
    FrequencyResult,
    FunnelInfo,
    FunnelResult,
    FunnelStep,
    InsightsResult,
    JQLResult,
    LexiconDefinition,
    LexiconMetadata,
    LexiconProperty,
    LexiconSchema,
    NumericAverageResult,
    NumericBucketResult,
    NumericSumResult,
    PropertyCountsResult,
    RetentionResult,
    SavedCohort,
    SegmentationResult,
    SummaryResult,
    TableInfo,
    TableMetadata,
    TableSchema,
    TopEvent,
    UserEvent,
    WorkspaceInfo,
)
from mixpanel_data.workspace import Workspace

__version__ = "0.1.0"

__all__ = [
    # Core
    "Workspace",
    # Type aliases
    "CountType",
    "HourDayUnit",
    "TimeUnit",
    # Exceptions
    "MixpanelDataError",
    "APIError",
    "ConfigError",
    "AccountNotFoundError",
    "AccountExistsError",
    "AuthenticationError",
    "RateLimitError",
    "QueryError",
    "JQLSyntaxError",
    "ServerError",
    "TableExistsError",
    "TableNotFoundError",
    # Result types
    "FetchResult",
    "SegmentationResult",
    "FunnelResult",
    "FunnelStep",
    "RetentionResult",
    "CohortInfo",
    "JQLResult",
    # Discovery types
    "FunnelInfo",
    "SavedCohort",
    "TopEvent",
    "EventCountsResult",
    "PropertyCountsResult",
    # Phase 008: Query Service Enhancement types
    "UserEvent",
    "ActivityFeedResult",
    "InsightsResult",
    "FrequencyResult",
    "NumericBucketResult",
    "NumericSumResult",
    "NumericAverageResult",
    # Storage types
    "TableMetadata",
    "TableInfo",
    "ColumnInfo",
    "TableSchema",
    # Workspace types
    "WorkspaceInfo",
    # Lexicon schema types
    "EntityType",
    "LexiconMetadata",
    "LexiconProperty",
    "LexiconDefinition",
    "LexiconSchema",
    # Introspection types
    "ColumnSummary",
    "SummaryResult",
    "EventStats",
    "EventBreakdownResult",
    "ColumnStatsResult",
]
