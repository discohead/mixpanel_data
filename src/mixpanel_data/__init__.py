"""
mixpanel_data - Python library for working with Mixpanel analytics data.

Designed for AI coding agents. Fetch data once into a local DuckDB database,
then query it repeatedly with SQL.
"""

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
    EventCountsResult,
    FetchResult,
    FrequencyResult,
    FunnelInfo,
    FunnelResult,
    FunnelStep,
    InsightsResult,
    JQLResult,
    NumericAverageResult,
    NumericBucketResult,
    NumericSumResult,
    PropertyCountsResult,
    RetentionResult,
    SavedCohort,
    SegmentationResult,
    TopEvent,
    UserEvent,
)

__version__ = "0.1.0"

__all__ = [
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
]
