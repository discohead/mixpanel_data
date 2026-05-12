"""Public API contract for query_user() and build_user_params().

This file documents the public interface that users interact with.
It is NOT executable code — it is a contract specification.
"""

from __future__ import annotations

from typing import Any, Literal

import pandas as pd
from mixpanel_data.types import (
    CohortDefinition,
    Filter,
    ResultWithDataFrame,
)

# ──────────────────────────────────────────────────────────────────────
# Result Type
# ──────────────────────────────────────────────────────────────────────


class UserQueryResult(ResultWithDataFrame):
    """Result from a user profile query.

    Frozen dataclass extending ResultWithDataFrame. Supports two modes:
    - mode="profiles": Individual profile records with lazy DataFrame
    - mode="aggregate": Aggregate statistics (count/sum/mean/min/max)

    Fields:
        computed_at: ISO timestamp when the query was computed.
        total: Number of profiles returned (equals len(profiles)).
        profiles: Normalized profile dicts (empty for mode="aggregate").
        params: Engage API parameters used (for debugging/reproduction).
        meta: Response metadata (session_id, pages_fetched, etc.).
        mode: Which output mode produced this result.
        aggregate_data: Raw aggregate result (for mode="aggregate" only).
    """

    computed_at: str
    total: int
    profiles: list[dict[str, Any]]
    params: dict[str, Any]
    meta: dict[str, Any]
    mode: Literal["profiles", "aggregate"]
    aggregate_data: dict[str, Any] | int | float | None

    @property
    def df(self) -> pd.DataFrame:
        """Mode-aware DataFrame.

        mode="profiles":
            One row per user. Columns: distinct_id, last_seen, <properties>.
            $ prefix stripped from built-in properties ($email → email).
        mode="aggregate":
            One row per metric (or per segment).
            Columns: metric, value (or segment, value when segmented).
        """
        ...

    @property
    def distinct_ids(self) -> list[str]:
        """List of distinct IDs in the result (mode="profiles" only).

        Returns empty list for mode="aggregate".
        """
        ...

    @property
    def value(self) -> int | float | None:
        """Scalar aggregate value (mode="aggregate" only).

        Returns the single aggregate result when no segmentation is used.
        Returns None for mode="profiles" or segmented aggregates.
        """
        ...


# ──────────────────────────────────────────────────────────────────────
# Workspace Methods
# ──────────────────────────────────────────────────────────────────────


class WorkspaceQueryUserContract:
    """Contract for query_user() and build_user_params() on Workspace."""

    def query_user(
        self,
        *,
        # ── Filtering (shared vocabulary) ──────────────────────
        where: Filter | list[Filter] | str | None = None,
        cohort: int | CohortDefinition | None = None,
        # ── Property Selection ─────────────────────────────────
        properties: list[str] | None = None,
        # ── Ordering ───────────────────────────────────────────
        sort_by: str | None = None,
        sort_order: Literal["ascending", "descending"] = "descending",
        # ── Result Size ────────────────────────────────────────
        limit: int | None = 1,
        # ── Full-Text Search ───────────────────────────────────
        search: str | None = None,
        # ── Specific Users ─────────────────────────────────────
        distinct_id: str | None = None,
        distinct_ids: list[str] | None = None,
        # ── Group Profiles ─────────────────────────────────────
        group_id: str | None = None,
        # ── Point-in-Time ──────────────────────────────────────
        as_of: str | int | None = None,
        # ── Output Mode ────────────────────────────────────────
        mode: Literal["profiles", "aggregate"] = "profiles",
        # ── Aggregation (mode="aggregate" only) ────────────────
        aggregate: Literal["count", "sum", "mean", "min", "max"] = "count",
        aggregate_property: str | None = None,
        segment_by: list[int] | None = None,
        # ── Performance ────────────────────────────────────────
        parallel: bool = False,
        workers: int = 5,
        # ── Advanced ───────────────────────────────────────────
        include_all_users: bool = False,
    ) -> UserQueryResult:
        """Query user profiles or compute aggregate statistics.

        The 5th query engine in the unified query system. Uses the same
        Filter vocabulary as query(), query_funnel(), query_retention(),
        and query_flow().

        Args:
            where: Filter profiles by property values. Accepts Filter
                objects (unified vocabulary), list of Filters (AND-combined),
                or raw selector string (escape hatch).
            cohort: Filter by cohort membership. Int for saved cohort ID,
                CohortDefinition for inline behavioral criteria.
            properties: Output properties to include in result. None for all.
                Only applies to mode="profiles".
            sort_by: Property name to sort results by.
                Only applies to mode="profiles".
            sort_order: Sort direction. Default "descending".
            limit: Maximum profiles to return. Default 1 (safe: returns 1
                sample profile). None fetches all matching profiles.
                Only applies to mode="profiles".
            search: Full-text search across profile fields.
                Only applies to mode="profiles".
            distinct_id: Fetch a single user by distinct ID.
                Only applies to mode="profiles".
            distinct_ids: Fetch multiple users by distinct IDs.
                Only applies to mode="profiles".
            group_id: Query group profiles instead of users.
            as_of: Point-in-time query. String "YYYY-MM-DD" or Unix int.
            mode: Output mode. "profiles" for individual records,
                "aggregate" for population statistics.
            aggregate: Aggregation function for mode="aggregate".
                Default "count".
            aggregate_property: Property to aggregate on. Required for
                sum/mean/min/max, prohibited for count.
            segment_by: Cohort IDs for segmented aggregation.
                Only applies to mode="aggregate".
            parallel: Enable concurrent page fetching for large results.
                Only applies to mode="profiles".
            workers: Max concurrent workers. Capped at 5.
            include_all_users: Include non-members in cohort queries.
                Requires cohort parameter.

        Returns:
            UserQueryResult with mode-aware .df, .total, .value properties.

        Raises:
            BookmarkValidationError: If arguments violate validation rules.
            ConfigError: If credentials are not configured.
            RateLimitError: If API rate limit exceeded after retries.
        """
        ...

    def build_user_params(
        self,
        *,
        # Same parameters as query_user(), excluding: limit, parallel, workers
        where: Filter | list[Filter] | str | None = None,
        cohort: int | CohortDefinition | None = None,
        properties: list[str] | None = None,
        sort_by: str | None = None,
        sort_order: Literal["ascending", "descending"] = "descending",
        search: str | None = None,
        distinct_id: str | None = None,
        distinct_ids: list[str] | None = None,
        group_id: str | None = None,
        as_of: str | int | None = None,
        mode: Literal["profiles", "aggregate"] = "profiles",
        aggregate: Literal["count", "sum", "mean", "min", "max"] = "count",
        aggregate_property: str | None = None,
        segment_by: list[int] | None = None,
        include_all_users: bool = False,
    ) -> dict[str, Any]:
        """Build validated engage API params without executing.

        Same validation as query_user() but returns the params dict
        instead of executing the query. Useful for debugging, inspecting
        generated parameters, or testing.

        Returns:
            Engage API params dict ready for the /engage endpoint.

        Raises:
            BookmarkValidationError: If arguments violate validation rules.
        """
        ...


# ──────────────────────────────────────────────────────────────────────
# API Client Extension
# ──────────────────────────────────────────────────────────────────────


class APIClientEngageStatsContract:
    """Contract for the new engage_stats() method on MixpanelAPIClient."""

    def engage_stats(
        self,
        *,
        where: str | None = None,
        action: str = "count()",
        filter_by_cohort: str | None = None,
        segment_by_cohorts: dict[str, bool] | None = None,
        group_id: str | None = None,
        as_of_timestamp: int | None = None,
        include_all_users: bool = False,
    ) -> dict[str, Any]:
        """Query aggregate statistics from the Engage stats endpoint.

        POSTs to /api/2.0/engage with filter_type=stats.

        Args:
            where: Selector string for filtering profiles.
            action: Aggregation expression (e.g., "count()", "mean(ltv)").
            filter_by_cohort: JSON-encoded cohort filter dict.
            segment_by_cohorts: Cohort IDs for segmentation.
            group_id: Group analytics identifier.
            as_of_timestamp: Unix timestamp for point-in-time.
            include_all_users: Include non-members in cohort results.

        Returns:
            Raw stats response dict with 'results', 'status',
            'computed_at' fields.

        Raises:
            RateLimitError: If API rate limit exceeded.
            MixpanelAPIError: If the API returns an error.
        """
        ...
