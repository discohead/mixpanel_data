"""
mixpanel_data - Python library for working with Mixpanel analytics data.

Designed for AI coding agents. Fetch data once into a local DuckDB database,
then query it repeatedly with SQL.
"""

from mixpanel_data.exceptions import (
    AccountExistsError,
    AccountNotFoundError,
    AuthenticationError,
    ConfigError,
    MixpanelDataError,
    QueryError,
    RateLimitError,
    TableExistsError,
    TableNotFoundError,
)
from mixpanel_data.types import (
    CohortInfo,
    FetchResult,
    FunnelResult,
    FunnelStep,
    JQLResult,
    RetentionResult,
    SegmentationResult,
)

__version__ = "0.1.0"

__all__ = [
    # Exceptions
    "MixpanelDataError",
    "ConfigError",
    "AccountNotFoundError",
    "AccountExistsError",
    "AuthenticationError",
    "RateLimitError",
    "QueryError",
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
]
