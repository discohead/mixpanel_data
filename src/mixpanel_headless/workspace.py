"""Workspace facade for Mixpanel data operations.

The Workspace class is the unified entry point for all Mixpanel data operations,
orchestrating DiscoveryService, LiveQueryService, and the App API client.

Example:
    Basic usage with credentials from config:

    ```python
    ws = Workspace()
    events = ws.events()  # discover schema
    result = ws.segmentation(event="login", from_date="2024-01-01", to_date="2024-01-31")
    ws.close()
    ```

    Stream events for external processing:

    ```python
    ws = Workspace()
    for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31"):
        process(event)
    ws.close()
    ```
"""

from __future__ import annotations

import calendar
import json
import logging
import math
import time
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as _date
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from mixpanel_headless._internal.me import MeService

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import Account as _AccountUnion
from mixpanel_headless._internal.auth.bridge import load_bridge as _load_bridge
from mixpanel_headless._internal.auth.resolver import (
    env_workspace_id as _env_workspace_id,
)
from mixpanel_headless._internal.auth.resolver import (
    format_no_project_error as _format_no_project_error,
)
from mixpanel_headless._internal.auth.resolver import (
    resolve_project_axis as _resolve_project_axis,
)
from mixpanel_headless._internal.auth.resolver import (
    resolve_session as _resolve_session,
)
from mixpanel_headless._internal.auth.session import (
    Project as _Project,
)
from mixpanel_headless._internal.auth.session import (
    Session as _Session,
)
from mixpanel_headless._internal.auth.session import (
    WorkspaceRef as _WorkspaceRef,
)
from mixpanel_headless._internal.bookmark_builders import (
    _build_composed_properties,
    build_date_range,
    build_filter_entry,
    build_filter_section,
    build_flow_cohort_filter,
    build_flow_property_filter,
    build_group_section,
    build_time_comparison,
    build_time_section,
    patch_custom_property_filters_for_transform,
)
from mixpanel_headless._internal.bookmark_schema import (
    PARTIAL_UPDATE_SUB_MODELS,
    get_root_model_for_bookmark_type,
    validate_with_pydantic,
)
from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless._internal.query.user_builders import (
    extract_cohort_filter,
    filters_to_selector,
)
from mixpanel_headless._internal.query.user_validators import (
    validate_user_args,
    validate_user_params,
)
from mixpanel_headless._internal.segfilter import build_segfilter_entry
from mixpanel_headless._internal.services.discovery import DiscoveryService
from mixpanel_headless._internal.services.live_query import LiveQueryService
from mixpanel_headless._internal.transforms import transform_event, transform_profile
from mixpanel_headless._internal.validation import (
    _scan_custom_properties,
    contains_control_chars,
    validate_bookmark,
    validate_flow_args,
    validate_flow_bookmark,
    validate_funnel_args,
    validate_query_args,
    validate_retention_args,
    validate_sorting_block,
)
from mixpanel_headless._literal_types import (
    ConversionWindowUnit,
    FlowChartType,
    FlowConversionWindowUnit,
    FlowCountType,
    FunnelMode,
    FunnelOrder,
    FunnelReentryMode,
    InsightsMode,
    QueryTimeUnit,
    RetentionUnboundedMode,
    TimeUnit,
)
from mixpanel_headless.exceptions import (
    AuthenticationError,
    BookmarkValidationError,
    BusinessContextValidationError,
    ConfigError,
    MixpanelHeadlessError,
    QueryError,
    RateLimitError,
    ServerError,
    ValidationError,
    WorkspaceScopeError,
)
from mixpanel_headless.types import (
    BUSINESS_CONTEXT_MAX_CHARS,
    ActivityFeedResult,
    AlertCount,
    AlertHistoryResponse,
    AlertScreenshotResponse,
    Annotation,
    AnnotationTag,
    AuditResponse,
    AuditViolation,
    BlueprintConfig,
    BlueprintFinishParams,
    BlueprintTemplate,
    Bookmark,
    BookmarkHistoryResponse,
    BookmarkInfo,
    BookmarkType,
    BulkCreateSchemasParams,
    BulkCreateSchemasResponse,
    BulkPatchResult,
    BulkUpdateAnomalyParams,
    BulkUpdateBookmarkEntry,
    BulkUpdateCohortEntry,
    BulkUpdateEventsParams,
    BulkUpdatePropertiesParams,
    BusinessContext,
    BusinessContextChain,
    Cohort,
    CohortBreakdown,
    CohortDefinition,
    CohortMetric,
    CreateAlertParams,
    CreateAnnotationParams,
    CreateAnnotationTagParams,
    CreateBookmarkParams,
    CreateCohortParams,
    CreateCustomEventParams,
    CreateCustomPropertyParams,
    CreateDashboardParams,
    CreateDeletionRequestParams,
    CreateDropFilterParams,
    CreateExperimentParams,
    CreateFeatureFlagParams,
    CreateRcaDashboardParams,
    CreateTagParams,
    CreateWebhookParams,
    CustomAlert,
    CustomEvent,
    CustomProperty,
    CustomPropertyRef,
    DailyCountsResult,
    Dashboard,
    DataVolumeAnomaly,
    DeleteSchemasResponse,
    DropFilter,
    DropFilterLimitsResponse,
    DuplicateExperimentParams,
    EngagementDistributionResult,
    EntityType,
    EventCountsResult,
    EventDefinition,
    EventDeletionRequest,
    Exclusion,
    Experiment,
    ExperimentConcludeParams,
    ExperimentDecideParams,
    FeatureFlag,
    Filter,
    FlagHistoryResponse,
    FlagLimitsResponse,
    FlowQueryResult,
    FlowsResult,
    FlowStep,
    Formula,
    FrequencyBreakdown,
    FrequencyFilter,
    FrequencyResult,
    FunnelInfo,
    FunnelMathType,
    FunnelQueryResult,
    FunnelResult,
    FunnelStep,
    GroupBy,
    HoldingConstant,
    InitSchemaEnforcementParams,
    InlineCustomProperty,
    JQLResult,
    LexiconSchema,
    LexiconTag,
    LookupTable,
    LookupTableUploadUrl,
    MarkLookupTableReadyParams,
    MathType,
    Metric,
    NumericAverageResult,
    NumericBucketResult,
    NumericPropertySummaryResult,
    NumericSumResult,
    PerUserAggregation,
    PreviewDeletionFiltersParams,
    ProjectWebhook,
    PropertyCountsResult,
    PropertyCoverageResult,
    PropertyDefinition,
    PropertyDistributionResult,
    PublicWorkspace,
    QueryResult,
    ReplaceSchemaEnforcementParams,
    RetentionAlignment,
    RetentionEvent,
    RetentionMathType,
    RetentionMode,
    RetentionQueryResult,
    RetentionResult,
    SavedCohort,
    SavedReportResult,
    SchemaEnforcementConfig,
    SchemaEntry,
    SegmentationResult,
    SetTestUsersParams,
    SubPropertyInfo,
    TimeComparison,
    TopEvent,
    UpdateAlertParams,
    UpdateAnnotationParams,
    UpdateAnomalyParams,
    UpdateBookmarkParams,
    UpdateCohortParams,
    UpdateCustomPropertyParams,
    UpdateDashboardParams,
    UpdateDropFilterParams,
    UpdateEventDefinitionParams,
    UpdateExperimentParams,
    UpdateFeatureFlagParams,
    UpdateLookupTableParams,
    UpdatePropertyDefinitionParams,
    UpdateReportLinkParams,
    UpdateSchemaEnforcementParams,
    UpdateTagParams,
    UpdateTextCardParams,
    UpdateWebhookParams,
    UploadLookupTableParams,
    UserQueryResult,
    ValidateAlertsForBookmarkParams,
    ValidateAlertsForBookmarkResponse,
    WebhookMutationResult,
    WebhookTestParams,
    WebhookTestResult,
    _sanitize_raw_cohort,
)

logger = logging.getLogger(__name__)

# Limit validation bounds (Mixpanel API restriction)
_MIN_LIMIT = 1
_MAX_LIMIT = 100_000


def _validate_limit(limit: int | None) -> None:
    """Validate limit is within the allowed range.

    Mixpanel API restricts the limit parameter to a maximum of 100000 events.
    This validation catches invalid values early to avoid wasting an API call.

    Args:
        limit: Maximum number of events to return, or None for no limit.

    Raises:
        ValueError: If limit is outside the valid range (1 to 100000).
    """
    if limit is None:
        return
    if limit < _MIN_LIMIT:
        raise ValueError(f"limit must be at least {_MIN_LIMIT}, got {limit}")
    if limit > _MAX_LIMIT:
        raise ValueError(f"limit must be at most {_MAX_LIMIT}, got {limit}")


def _check_step_direction(
    value: int | None,
    name: str,
    step_path: str,
) -> list[ValidationError]:
    """Validate a per-step forward/reverse value for type and range.

    Args:
        value: The forward or reverse value (None means inherit default).
        name: Field name (``"forward"`` or ``"reverse"``).
        step_path: Parent path for error reporting (e.g. ``"steps[0]"``).

    Returns:
        List of validation errors (empty if valid).
    """
    if value is None:
        return []
    if isinstance(value, bool) or not isinstance(value, int):
        return [
            ValidationError(
                path=f"{step_path}.{name}",
                message=(
                    f"Per-step {name} must be an integer (got {type(value).__name__})"
                ),
                code=f"FL_TYPE_{name.upper()}",
            )
        ]
    if value < 0 or value > 5:
        code = "FL3_FORWARD_RANGE" if name == "forward" else "FL4_REVERSE_RANGE"
        return [
            ValidationError(
                path=f"{step_path}.{name}",
                message=f"Per-step {name} must be between 0 and 5 (got {value})",
                code=code,
            )
        ]
    return []


class Workspace:
    """Unified entry point for Mixpanel data operations.

    The Workspace class is a facade that orchestrates:
    - DiscoveryService for schema exploration
    - LiveQueryService for real-time analytics
    - App API client for CRUD and data governance operations

    Examples:
        Basic usage with credentials from config:

        ```python
        ws = Workspace()
        events = ws.events()  # discover schema
        result = ws.segmentation(event="login", from_date="2024-01-01", to_date="2024-01-31")
        ws.close()
        ```

        Stream events for external processing:

        ```python
        ws = Workspace()
        for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31"):
            process(event)
        ws.close()
        ```
    """

    # =========================================================================
    # LIFECYCLE & CONSTRUCTION
    # =========================================================================

    def __init__(
        self,
        *,
        account: str | None = None,
        project: str | None = None,
        workspace: int | None = None,
        target: str | None = None,
        session: _Session | None = None,
        _api_client: MixpanelAPIClient | None = None,
    ) -> None:
        """Create a new Workspace bound to a resolved :class:`Session`.

        Resolution priority follows FR-017: env vars > kwargs > target >
        bridge > ``[active]`` > ``Account.default_project``. Pass
        ``session=`` to bypass the resolver and use a pre-built
        :class:`Session` directly.

        Args:
            account: Named account from ``~/.mp/config.toml``.
            project: Project ID override (digit string).
            workspace: Workspace ID override (positive int).
            target: Apply all three axes from ``[targets.NAME]``. Mutually
                exclusive with ``account``/``project``/``workspace``.
            session: Pre-built :class:`Session` (full resolver bypass).
            _api_client: Injected :class:`MixpanelAPIClient` for testing.

        Raises:
            ValueError: ``target=`` combined with any axis kwarg.
            ConfigError: Account or project axis cannot be resolved.
            OAuthError: Auth header construction fails.
        """
        if target is not None and (
            account is not None or project is not None or workspace is not None
        ):
            raise ValueError(
                "`target=` is mutually exclusive with "
                "`account=`/`project=`/`workspace=`."
            )

        self._discovery: DiscoveryService | None = None
        self._live_query: LiveQueryService | None = None
        self._me_service: MeService | None = None

        if session is not None:
            sess = session
        else:
            from mixpanel_headless._internal.auth.bridge import load_bridge

            br = load_bridge()
            # If the bridge has oauth_browser tokens embedded, materialize them
            # to the per-account on-disk path so the OnDiskTokenResolver can
            # serve them downstream. This is the Cowork credential-courier
            # contract: the bridge is the source of truth at startup.
            if (
                br is not None
                and br.tokens is not None
                and br.account.type == "oauth_browser"
            ):
                from mixpanel_headless._internal.auth.storage import (
                    ensure_account_dir,
                )
                from mixpanel_headless._internal.auth.token import token_payload_bytes
                from mixpanel_headless._internal.io_utils import atomic_write_bytes

                tokens_path = ensure_account_dir(br.account.name) / "tokens.json"
                # Always overwrite — the bridge is the authoritative
                # source of truth at startup, so a refreshed payload from
                # the host must replace any stale on-disk cache here.
                # ``OAuthTokens.expires_at`` is always set (required, tz-aware
                # per Fix 25) — no fall-through to None which would trip the
                # OnDiskTokenResolver expiry check. Empty scopes from the
                # bridge get a ``"read"`` default so the cached file matches
                # what `mp account login` would have written.
                tokens_to_persist = br.tokens
                if not tokens_to_persist.scope:
                    tokens_to_persist = tokens_to_persist.model_copy(
                        update={"scope": "read"}
                    )
                # atomic_write_bytes creates the file with 0o600 via O_EXCL
                # before any data is written, eliminating the umask-derived
                # permission window left open by write_text + chmod.
                atomic_write_bytes(tokens_path, token_payload_bytes(tokens_to_persist))
            sess = _resolve_session(
                account=account,
                project=project,
                workspace=workspace,
                target=target,
                config=ConfigManager(),
                bridge=br,
            )
        self._session = sess
        self._account_name: str = sess.account.name
        self._initial_workspace_id = sess.workspace.id if sess.workspace else None
        if _api_client is not None:
            self._api_client: MixpanelAPIClient | None = _api_client
        else:
            self._api_client = MixpanelAPIClient(session=sess)

    # ---- v3 read-only properties --------------------------------------

    @property
    def account(self) -> _AccountUnion:
        """Return the resolved :class:`Account` for the current session."""
        return self._session.account

    @property
    def project(self) -> _Project:
        """Return the resolved :class:`Project` for the current session."""
        return self._session.project

    @property
    def workspace(self) -> _WorkspaceRef | None:
        """Return the resolved :class:`WorkspaceRef` (or ``None`` for lazy)."""
        return self._session.workspace

    @property
    def session(self) -> _Session:
        """Return the bound :class:`Session`."""
        return self._session

    # ---- v3 in-session switching --------------------------------------

    def use(
        self,
        *,
        account: str | None = None,
        project: str | None = None,
        workspace: int | None = None,
        target: str | None = None,
        persist: bool = False,
    ) -> Workspace:
        """Swap one or more session axes in place; return ``self`` for chaining.

        ``target=`` is mutually exclusive with ``account=``/``project=``/
        ``workspace=``. The HTTP transport is preserved across all switches
        (per Research R5).

        When ``account=`` is supplied, the project axis re-resolves through
        the FR-017 chain ending at the new account's ``default_project``
        (env ``MP_PROJECT_ID`` > explicit ``project=`` > new account's
        ``default_project``). If no source provides a project, the call
        raises :class:`ConfigError` per FR-033 — the prior session's
        project is NEVER carried forward across an account swap because
        cross-account project access is not guaranteed. The workspace
        axis is cleared on account swap (workspaces are project-scoped;
        the prior workspace doesn't apply to the new project) — explicit
        ``workspace=`` or ``MP_WORKSPACE_ID`` env override is honored.

        Args:
            account: Replacement account name.
            project: Replacement project ID.
            workspace: Replacement workspace ID.
            target: Apply this target's three axes atomically.
            persist: When ``True``, also write the new state to ``[active]``.

        Returns:
            ``self`` for fluent chaining.

        Raises:
            ValueError: Mutually exclusive args, or referenced name missing.
            OAuthError: New auth header construction fails (atomic on success).
            ConfigError: ``account=`` swap cannot resolve a project axis.
        """
        if target is not None and (
            account is not None or project is not None or workspace is not None
        ):
            raise ValueError(
                "`target=` is mutually exclusive with `account=`/`project=`/`workspace=`."
            )

        cm = ConfigManager()
        client = self._require_api_client()
        new_account_obj: _AccountUnion | None = None
        new_project_obj: _Project | None = None
        new_workspace_obj: _WorkspaceRef | None = None
        if target is not None:
            # Route through the same resolver as Workspace() construction so
            # env > param > target > bridge > config ordering applies (FR-017).
            # Without this, mid-process env-var overrides would be honored at
            # construction but silently ignored on `ws.use(target=...)`.
            sess = _resolve_session(
                target=target,
                config=cm,
                bridge=_load_bridge(),
            )
            new_account_obj = sess.account
            new_project_obj = sess.project
            new_workspace_obj = sess.workspace
        elif account is not None:
            # Explicit account swap: the user told us which account to use,
            # so the env-vars-override-param rule (FR-017) on the account
            # axis doesn't apply here — load the requested account directly.
            # Project re-resolves through the FR-017 chain ending at the
            # NEW account's default_project (env > explicit > new account's
            # default); raises ConfigError if nothing resolves (per FR-033,
            # cross-account project access is not guaranteed).
            # Workspace is cleared (workspaces are project-scoped; the
            # prior workspace is meaningless under the new account/project)
            # — explicit `workspace=` overrides the clear, and env override
            # via MP_WORKSPACE_ID still applies for parity with FR-017.
            new_account_obj = cm.get_account(account)
            br = _load_bridge()
            project_id = _resolve_project_axis(
                explicit=project,
                target_project=None,
                bridge=br,
                account=new_account_obj,
            )
            if project_id is None:
                raise ConfigError(_format_no_project_error(new_account_obj))
            new_project_obj = _Project(id=project_id)
            # Account-swap intentionally clears workspace per FR-033 (workspaces
            # are project-scoped; the prior workspace doesn't apply to the new
            # project). Only an explicit ``workspace=`` kwarg or a validated
            # ``MP_WORKSPACE_ID`` env var can populate it. We bypass
            # ``resolve_workspace_axis`` because that consults ``[active].workspace``
            # — which is exactly the fallback we need to skip here.
            if workspace is not None:
                new_workspace_obj = _WorkspaceRef(id=workspace)
            else:
                env_ws = _env_workspace_id()
                new_workspace_obj = (
                    _WorkspaceRef(id=env_ws) if env_ws is not None else None
                )
        else:
            new_project_obj = _Project(id=project) if project is not None else None
            new_workspace_obj = (
                _WorkspaceRef(id=workspace) if workspace is not None else None
            )
        client.use(
            account=new_account_obj,
            project=new_project_obj,
            workspace=new_workspace_obj,
        )
        self._session = client.session

        # Clear lazy services so subsequent reads of `project` / `account` /
        # `workspaces()` / `_me_svc` observe the new session rather than the
        # prior one.
        self._account_name = self._session.account.name
        self._initial_workspace_id = (
            self._session.workspace.id if self._session.workspace else None
        )
        self._discovery = None
        self._live_query = None
        self._me_service = None

        if persist:
            self._persist_active()
        return self

    def _persist_active(self) -> None:
        """Persist the current session's axes to disk in one transaction.

        ``[active].account`` and ``[active].workspace`` are written to the
        ``[active]`` block. The session's project is written to the
        account's ``default_project`` (project lives on the account in v3,
        not in ``[active]``). This keeps ``ws.use(..., persist=True)``
        consistent with construction-time resolution: a fresh
        ``Workspace()`` will reproduce the same session.

        All three writes happen inside one :meth:`ConfigManager.apply_session`
        call so an interrupted process never leaves the on-disk state
        reflecting a partial swap (e.g., new account but stale project).
        When the in-session workspace was cleared, ``clear_workspace=True``
        explicitly drops ``[active].workspace`` rather than leaving the
        prior pin behind.
        """
        ConfigManager().apply_session(
            account=self._session.account.name,
            project=self._session.project.id,
            workspace=(
                self._session.workspace.id
                if self._session.workspace is not None
                else None
            ),
            clear_workspace=self._session.workspace is None,
        )

    def __enter__(self) -> Workspace:
        """Enter context manager.

        Returns:
            Self for use in 'with' statement.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager, closing all resources.

        Closes the HTTP client. Exceptions are NOT suppressed - they
        propagate normally after cleanup.
        """
        self.close()

    def close(self) -> None:
        """Close all resources (HTTP client).

        This method is idempotent and safe to call multiple times.
        """
        # Close API client if we created one
        if self._api_client is not None:
            self._api_client.close()
            self._api_client = None

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _get_api_client(self) -> MixpanelAPIClient:
        """Get or create the API client (lazy initialization).

        Returns:
            MixpanelAPIClient instance.
        """
        if self._api_client is None:
            self._api_client = MixpanelAPIClient(session=self._session)
            if self._initial_workspace_id is not None:
                self._api_client.set_workspace_id(self._initial_workspace_id)
        return self._api_client

    def _require_api_client(self) -> MixpanelAPIClient:
        """Get API client (always available — created in ``__init__``).

        Returns:
            MixpanelAPIClient instance.
        """
        return self._get_api_client()

    # =========================================================================
    # WORKSPACE MANAGEMENT
    # =========================================================================

    def list_workspaces(self) -> list[PublicWorkspace]:
        """List all public workspaces for the current project.

        Delegates to the API client's ``list_workspaces()`` method, which
        calls ``GET /api/app/projects/{pid}/workspaces/public``.

        Returns:
            List of ``PublicWorkspace`` models for the project.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            workspaces = ws.list_workspaces()
            for w in workspaces:
                print(f"{w.name} (id={w.id}, default={w.is_default})")
            ```
        """
        client = self._require_api_client()
        return client.list_workspaces()

    def resolve_workspace_id(self) -> int:
        """Resolve the workspace ID for scoped requests.

        Resolution order:
        1. Workspace ID already pinned on the resolved session (for example
           via ``Workspace(workspace=N)``, ``Workspace.use(workspace=N)``,
           ``MP_WORKSPACE_ID``, saved targets, bridge pins, or persisted
           ``[active].workspace`` state)
        2. Cached auto-discovered workspace ID
        3. Auto-discover by listing workspaces and finding the default

        Returns:
            The resolved workspace ID.

        Raises:
            ConfigError: If credentials are not available.
            WorkspaceScopeError: If no workspaces are found for the project.

        Example:
            ```python
            ws = Workspace()
            ws_id = ws.resolve_workspace_id()
            print(f"Using workspace {ws_id}")
            ```
        """
        client = self._require_api_client()
        return client.resolve_workspace_id()

    # =========================================================================
    # /ME & PROJECT DISCOVERY
    # =========================================================================

    @property
    def _me_svc(self) -> MeService:
        """Get or create MeService (lazy initialization).

        Returns:
            MeService instance for /me API operations.
        """
        if self._me_service is None:
            from mixpanel_headless._internal.me import MeCache
            from mixpanel_headless._internal.me import MeService as _MeService

            cache = MeCache(account_name=self._account_name)
            self._me_service = _MeService(
                self._require_api_client(),
                cache,
                self._session.account.region,
                account_type=self._session.account.type,
            )
        return self._me_service

    def me(self, *, force_refresh: bool = False) -> Any:
        """Get /me response for current credentials (cached 24h).

        Returns the authenticated user's profile including all accessible
        organizations, projects, and workspaces.

        Args:
            force_refresh: If True, bypass cache and call the API.

        Returns:
            MeResponse with user profile, projects, and workspaces.

        Raises:
            ConfigError: If credentials lack /me access (401 or 403).
            QueryError: If the API returns a non-403 error.

        Example:
            ```python
            ws = Workspace()
            me = ws.me()
            print(me.user_email)
            for pid, proj in me.projects.items():
                print(f"  {pid}: {proj.name}")
            ```
        """
        return self._me_svc.fetch(force_refresh=force_refresh)

    def projects(self, *, refresh: bool = False) -> list[_Project]:
        """List all accessible projects via the /me API (FR-035).

        Returns projects from the cached /me response, sorted by name. Each
        entry is a v3 :class:`Project` (id + name + organization_id +
        timezone), built from the underlying ``MeProjectInfo`` payload —
        callers iterate ``for project in ws.projects(): ws.use(project=project.id)``
        per the documented cross-project iteration pattern.

        Replaces the deprecated ``discover_projects()`` (which returned
        ``list[tuple[str, MeProjectInfo]]``) — for the raw ``/me`` shape
        with extra fields (``has_workspaces``, ``domain``, ``type``, ...),
        call ``self._me_svc.list_projects()`` directly from internal code.

        Args:
            refresh: When True, bypass the on-disk and in-memory ``/me``
                caches and refetch from the API. Default False uses the
                24h cache.

        Returns:
            List of :class:`Project` records sorted by name.

        Raises:
            ConfigError: If credentials lack /me access.

        Example:
            ```python
            ws = Workspace()
            for project in ws.projects():
                ws.use(project=project.id)
                print(project.id, project.name, len(ws.events()))
            ```
        """
        if refresh:
            self._me_svc.fetch(force_refresh=True)
        return [
            _Project(
                id=pid,
                name=info.name,
                organization_id=info.organization_id,
                timezone=info.timezone,
            )
            for pid, info in self._me_svc.list_projects()
        ]

    def workspaces(
        self,
        *,
        project_id: str | None = None,
        refresh: bool = False,
    ) -> list[_WorkspaceRef]:
        """List workspaces for a project via the /me API (FR-036).

        Returns workspaces from the cached /me response, sorted by name.
        Defaults to the current project if ``project_id`` is not provided.

        Replaces the deprecated ``discover_workspaces()`` (which returned
        ``list[MeWorkspaceInfo]``) — for the raw ``/me`` shape with extra
        fields (``is_global``, ``is_restricted``, ``description``, ...),
        call ``self._me_svc.list_workspaces(project_id=)`` directly from
        internal code.

        Args:
            project_id: Project ID to list workspaces for. Defaults to
                the current project.
            refresh: When True, bypass the on-disk and in-memory ``/me``
                caches and refetch from the API. Default False uses the
                24h cache. Mirrors :meth:`projects(refresh=)` (FR-047).

        Returns:
            List of :class:`WorkspaceRef` records sorted by name.

        Raises:
            ConfigError: If credentials lack /me access.

        Example:
            ```python
            ws = Workspace()
            for workspace in ws.workspaces():
                print(workspace.id, workspace.name, workspace.is_default)
            ```
        """
        if refresh:
            self._me_svc.fetch(force_refresh=True)
        pid = project_id
        if pid is None:
            pid = self._session.project.id
        return [
            _WorkspaceRef(id=info.id, name=info.name, is_default=info.is_default)
            for info in self._me_svc.list_workspaces(project_id=pid)
        ]

    @property
    def _discovery_service(self) -> DiscoveryService:
        """Get or create discovery service (lazy initialization)."""
        if self._discovery is None:
            self._discovery = DiscoveryService(self._require_api_client())
        return self._discovery

    @property
    def _live_query_service(self) -> LiveQueryService:
        """Get or create live query service (lazy initialization)."""
        if self._live_query is None:
            self._live_query = LiveQueryService(self._require_api_client())
        return self._live_query

    # =========================================================================
    # DISCOVERY METHODS
    # =========================================================================

    def events(
        self,
        *,
        limit: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[str]:
        """List event names in the Mixpanel project.

        Defaults to the widest window the underlying
        ``/events/names`` endpoint will accept: ``limit=5000`` (the
        server-side ceiling), ``from_date=2000-01-01`` (the API's
        earliest accepted year — pre-2000 values come back as
        ``"invalid date, bad year"``), and ``to_date`` set to today.
        The endpoint is gated by the per-project
        ``max_data_history_days`` feature; if the wide ``from_date``
        is rejected (HTTP 403, "Date range exceeds N days into the
        past"), the call automatically retries with ``today - N days``.

        Note that this method reflects events seen during the queried
        window — it is not the schema registry. Events that were
        registered in Lexicon but never fired in the window are
        absent. For the full registered schema, use the Lexicon
        endpoints (e.g. :meth:`get_event_definitions`).

        Results are cached per ``(limit, from_date, to_date)`` triple
        for the lifetime of the Workspace.

        Args:
            limit: Maximum events to return. Defaults to the
                server-side ceiling (5000).
            from_date: ``YYYY-MM-DD`` lower bound. Defaults to
                ``2000-01-01`` and falls back to the project's
                ``max_data_history_days`` ceiling on rejection.
            to_date: ``YYYY-MM-DD`` upper bound. Defaults to today.

        Returns:
            Alphabetically sorted list of event names.

        Raises:
            ConfigError: If API credentials not available.
            AuthenticationError: If credentials are invalid.
        """
        return self._discovery_service.list_events(
            limit=limit,
            from_date=from_date,
            to_date=to_date,
        )

    def properties(self, event: str) -> list[str]:
        """List all property names for an event.

        Results are cached per event for the lifetime of the Workspace.

        Args:
            event: Event name to get properties for.

        Returns:
            Alphabetically sorted list of property names.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._discovery_service.list_properties(event)

    def property_values(
        self,
        property_name: str,
        *,
        event: str | None = None,
        limit: int = 100,
    ) -> list[str]:
        """Get sample values for a property.

        Results are cached per (property, event, limit) for the lifetime of the Workspace.

        Args:
            property_name: Property to get values for.
            event: Optional event to filter by.
            limit: Maximum number of values to return.

        Returns:
            List of sample property values as strings.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._discovery_service.list_property_values(
            property_name, event=event, limit=limit
        )

    def subproperties(
        self,
        property_name: str,
        *,
        event: str | None = None,
        sample_size: int = 50,
    ) -> list[SubPropertyInfo]:
        """List inferred subproperties of a list-of-object event property.

        Samples values via :meth:`property_values`, parses each as JSON,
        and returns one :class:`SubPropertyInfo` per discovered scalar
        subproperty. Designed for properties like ``cart`` whose values
        are objects with subkeys (``Brand``, ``Category``, ``Price``,
        ``Item ID``). The returned ``name`` and ``type`` plug directly
        into :meth:`GroupBy.list_item` and :meth:`Filter.list_contains`.

        Scope: only **scalar** subproperty values (string / number /
        boolean / ISO datetime string) are reported. Subproperties whose
        values are themselves dicts or lists are silently skipped — they
        cannot be used by ``GroupBy.list_item`` or
        ``Filter.list_contains`` anyway.

        Args:
            property_name: Top-level list-of-object property name (e.g.
                ``"cart"``).
            event: Optional event name to scope the sample. Strongly
                recommended; without it the API may return values from
                across all events.
            sample_size: Number of raw values to sample. Default: 50.

        Returns:
            Alphabetically sorted list of :class:`SubPropertyInfo`.
            Empty list if no parseable dict values were found.

        Raises:
            ConfigError: If API credentials cannot be resolved.
            AuthenticationError: If credentials are configured but
                rejected by Mixpanel.

        Warns:
            UserWarning: When a subproperty has values of mixed scalar
                types across rows (collapses to ``"string"``); when a
                sub-key is observed with both scalar and nested-object
                shapes (reports the scalar form); or when a sub-key
                is observed but all sampled values were ``null``
                (excluded from output).

        Example:
            ```python
            for sp in ws.subproperties("cart", event="Cart Viewed"):
                print(sp.name, sp.type, sp.sample_values)
            # Brand string ('nike', 'puma', 'h&m')
            # Category string ('hats', 'jeans')
            # Item ID number (35317, 35318)
            # Price number (51, 87, 102)
            ```
        """
        return self._discovery_service.list_subproperties(
            property_name, event=event, sample_size=sample_size
        )

    def funnels(self) -> list[FunnelInfo]:
        """List saved funnels in the Mixpanel project.

        Results are cached for the lifetime of the Workspace.

        Returns:
            List of FunnelInfo objects (funnel_id, name).

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._discovery_service.list_funnels()

    def cohorts(self) -> list[SavedCohort]:
        """List saved cohorts in the Mixpanel project.

        Results are cached for the lifetime of the Workspace.

        Returns:
            List of SavedCohort objects.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._discovery_service.list_cohorts()

    def list_bookmarks(
        self,
        bookmark_type: BookmarkType | None = None,
    ) -> list[BookmarkInfo]:
        """List all saved reports (bookmarks) in the project.

        Retrieves metadata for all saved Insights, Funnel, Retention, and
        Flows reports in the project.

        Args:
            bookmark_type: Optional filter by report type. Valid values are
                'insights', 'funnels', 'retention', 'flows', 'launch-analysis'.
                If None, returns all bookmark types.

        Returns:
            List of BookmarkInfo objects with report metadata.
            Empty list if no bookmarks exist.

        Raises:
            ConfigError: If API credentials not available.
            QueryError: Permission denied or invalid type parameter.
        """
        return self._discovery_service.list_bookmarks(bookmark_type=bookmark_type)

    def top_events(
        self,
        *,
        type: Literal["general", "average", "unique"] = "general",
        limit: int | None = None,
    ) -> list[TopEvent]:
        """Get today's most active events.

        This method is NOT cached (returns real-time data).

        Args:
            type: Counting method (general, average, unique).
            limit: Maximum number of events to return.

        Returns:
            List of TopEvent objects with ``event``, ``count``, and
            ``percent_change`` fields.

        Raises:
            ConfigError: If API credentials not available.

        Example:
            ```python
            top = ws.top_events(limit=10)
            for t in top:
                print(f"{t.event}: {t.count:,} ({t.percent_change:+.1%})")
            ```
        """
        return self._discovery_service.list_top_events(type=type, limit=limit)

    def clear_discovery_cache(self) -> None:
        """Clear cached discovery results.

        Subsequent discovery calls will fetch fresh data from the API.
        """
        if self._discovery is not None:
            self._discovery.clear_cache()

    # =========================================================================
    # LEXICON SCHEMA METHODS
    # =========================================================================

    def lexicon_schemas(
        self,
        *,
        entity_type: EntityType | None = None,
    ) -> list[LexiconSchema]:
        """List Lexicon schemas in the project.

        Retrieves documented event and profile property schemas from the
        Mixpanel Lexicon (data dictionary).

        Results are cached for the lifetime of the Workspace.

        Args:
            entity_type: Optional filter by type ("event" or "profile").
                If None, returns all schemas.

        Returns:
            Alphabetically sorted list of LexiconSchema objects.

        Raises:
            ConfigError: If API credentials not available.
            AuthenticationError: If credentials are invalid.

        Note:
            The Lexicon API has a strict 5 requests/minute rate limit.
            Caching helps avoid hitting this limit; call clear_discovery_cache()
            only when fresh data is needed.
        """
        return self._discovery_service.list_schemas(entity_type=entity_type)

    def lexicon_schema(
        self,
        entity_type: EntityType,
        name: str,
    ) -> LexiconSchema:
        """Get a single Lexicon schema by entity type and name.

        Retrieves a documented schema for a specific event or profile property
        from the Mixpanel Lexicon (data dictionary).

        Results are cached for the lifetime of the Workspace.

        Args:
            entity_type: Entity type ("event" or "profile").
            name: Entity name.

        Returns:
            LexiconSchema for the specified entity.

        Raises:
            ConfigError: If API credentials not available.
            AuthenticationError: If credentials are invalid.
            QueryError: If schema not found.

        Note:
            The Lexicon API has a strict 5 requests/minute rate limit.
            Caching helps avoid hitting this limit; call clear_discovery_cache()
            only when fresh data is needed.
        """
        return self._discovery_service.get_schema(entity_type, name)

    # =========================================================================
    # STREAMING METHODS
    # =========================================================================

    def stream_events(
        self,
        *,
        from_date: str,
        to_date: str,
        events: list[str] | None = None,
        where: str | None = None,
        limit: int | None = None,
        raw: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """Stream events directly from Mixpanel API without storing.

        Yields events one at a time as they are received from the API.
        No database files or tables are created.

        Args:
            from_date: Start date inclusive (YYYY-MM-DD format).
            to_date: End date inclusive (YYYY-MM-DD format).
            events: Optional list of event names to filter. If None, all events returned.
            where: Optional Mixpanel filter expression (e.g., 'properties["country"]=="US"').
            limit: Optional maximum number of events to return (max 100000).
            raw: If True, return events in raw Mixpanel API format.
                 If False (default), return normalized format with datetime objects.

        Yields:
            dict[str, Any]: Event dictionaries in normalized or raw format.

        Raises:
            ConfigError: If API credentials are not available.
            AuthenticationError: If credentials are invalid.
            RateLimitError: If rate limit exceeded after max retries.
            QueryError: If filter expression is invalid.
            ValueError: If limit is outside valid range (1-100000).

        Example:
            ```python
            ws = Workspace()
            for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31"):
                process(event)
            ws.close()
            ```

            With raw format:

            ```python
            for event in ws.stream_events(
                from_date="2024-01-01", to_date="2024-01-31", raw=True
            ):
                legacy_system.ingest(event)
            ```
        """
        # Validate limit early to avoid wasted API calls
        _validate_limit(limit)

        api_client = self._require_api_client()
        event_iterator = api_client.export_events(
            from_date=from_date,
            to_date=to_date,
            events=events,
            where=where,
            limit=limit,
        )

        if raw:
            yield from event_iterator
        else:
            for event in event_iterator:
                yield transform_event(event)

    def stream_profiles(
        self,
        *,
        where: str | None = None,
        cohort_id: str | None = None,
        output_properties: list[str] | None = None,
        raw: bool = False,
        distinct_id: str | None = None,
        distinct_ids: list[str] | None = None,
        group_id: str | None = None,
        behaviors: list[dict[str, Any]] | None = None,
        as_of_timestamp: int | None = None,
        include_all_users: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """Stream user profiles directly from Mixpanel API without storing.

        Yields profiles one at a time as they are received from the API.
        No database files or tables are created.

        Args:
            where: Optional Mixpanel filter expression for profile properties.
            cohort_id: Optional cohort ID to filter by. Only profiles that are
                members of this cohort will be returned.
            output_properties: Optional list of property names to include in
                the response. If None, all properties are returned.
            raw: If True, return profiles in raw Mixpanel API format.
                 If False (default), return normalized format.
            distinct_id: Optional single user ID to fetch. Mutually exclusive
                with distinct_ids.
            distinct_ids: Optional list of user IDs to fetch. Mutually exclusive
                with distinct_id. Duplicates are automatically removed.
            group_id: Optional group type identifier (e.g., "companies") to fetch
                group profiles instead of user profiles.
            behaviors: Optional list of behavioral filters. Each dict should have
                'window' (e.g., "30d"), 'name' (identifier), and 'event_selectors'
                (list of {"event": "Name"}). Use with `where` parameter to filter,
                e.g., where='(behaviors["name"] > 0)'. Mutually exclusive with
                cohort_id.
            as_of_timestamp: Optional Unix timestamp to query profile state at
                a specific point in time. Must be in the past.
            include_all_users: If True, include all users and mark cohort membership.
                Only valid when cohort_id is provided.

        Yields:
            dict[str, Any]: Profile dictionaries in normalized or raw format.

        Raises:
            ConfigError: If API credentials are not available.
            AuthenticationError: If credentials are invalid.
            RateLimitError: If rate limit exceeded after max retries.
            ValueError: If mutually exclusive parameters are provided.

        Example:
            ```python
            ws = Workspace()
            for profile in ws.stream_profiles():
                sync_to_crm(profile)
            ws.close()
            ```

            Filter to premium users:

            ```python
            for profile in ws.stream_profiles(where='properties["plan"]=="premium"'):
                send_survey(profile)
            ```

            Filter by cohort and select specific properties:

            ```python
            for profile in ws.stream_profiles(
                cohort_id="12345",
                output_properties=["$email", "$name"]
            ):
                send_email(profile)
            ```

            Fetch specific users by ID:

            ```python
            for profile in ws.stream_profiles(distinct_ids=["user_1", "user_2"]):
                print(profile)
            ```

            Fetch group profiles:

            ```python
            for company in ws.stream_profiles(group_id="companies"):
                print(company)
            ```
        """
        api_client = self._require_api_client()
        profile_iterator = api_client.export_profiles(
            where=where,
            cohort_id=cohort_id,
            output_properties=output_properties,
            distinct_id=distinct_id,
            distinct_ids=distinct_ids,
            group_id=group_id,
            behaviors=behaviors,
            as_of_timestamp=as_of_timestamp,
            include_all_users=include_all_users,
        )

        if raw:
            yield from profile_iterator
        else:
            for profile in profile_iterator:
                yield transform_profile(profile)

    # =========================================================================
    # LIVE QUERY METHODS
    # =========================================================================

    def segmentation(
        self,
        event: str,
        *,
        from_date: str,
        to_date: str,
        on: str | None = None,
        unit: Literal["day", "week", "month"] = "day",
        where: str | None = None,
    ) -> SegmentationResult:
        """Run a segmentation query against Mixpanel API.

        Args:
            event: Event name to query.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            on: Optional property to segment by.
            unit: Time unit for aggregation.
            where: Optional WHERE clause.

        Returns:
            SegmentationResult with time-series data.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._live_query_service.segmentation(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=on,
            unit=unit,
            where=where,
        )

    def funnel(
        self,
        funnel_id: int,
        *,
        from_date: str,
        to_date: str,
        unit: str | None = None,
        on: str | None = None,
    ) -> FunnelResult:
        """Run a funnel analysis query.

        Args:
            funnel_id: ID of saved funnel.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            unit: Optional time unit.
            on: Optional property to segment by.

        Returns:
            FunnelResult with step conversion rates.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._live_query_service.funnel(
            funnel_id=funnel_id,
            from_date=from_date,
            to_date=to_date,
            unit=unit,
            on=on,
        )

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
        unit: Literal["day", "week", "month"] = "day",
    ) -> RetentionResult:
        """Run a retention analysis query.

        Args:
            born_event: Event that defines cohort entry.
            return_event: Event that defines return.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            born_where: Optional filter for born event.
            return_where: Optional filter for return event.
            interval: Retention interval.
            interval_count: Number of intervals.
            unit: Time unit.

        Returns:
            RetentionResult with cohort retention data.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._live_query_service.retention(
            born_event=born_event,
            return_event=return_event,
            from_date=from_date,
            to_date=to_date,
            born_where=born_where,
            return_where=return_where,
            interval=interval,
            interval_count=interval_count,
            unit=unit,
        )

    def jql(self, script: str, params: dict[str, Any] | None = None) -> JQLResult:
        """Execute a custom JQL script.

        Args:
            script: JQL script code.
            params: Optional parameters to pass to script.

        Returns:
            JQLResult with raw query results.

        Raises:
            ConfigError: If API credentials not available.
            JQLSyntaxError: If script has syntax errors.
        """
        return self._live_query_service.jql(script=script, params=params)

    def event_counts(
        self,
        events: list[str],
        *,
        from_date: str,
        to_date: str,
        type: Literal["general", "unique", "average"] = "general",
        unit: Literal["day", "week", "month"] = "day",
    ) -> EventCountsResult:
        """Get event counts for multiple events.

        Args:
            events: List of event names.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            type: Counting method.
            unit: Time unit.

        Returns:
            EventCountsResult with time-series per event.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._live_query_service.event_counts(
            events=events,
            from_date=from_date,
            to_date=to_date,
            type=type,
            unit=unit,
        )

    def property_counts(
        self,
        event: str,
        property_name: str,
        *,
        from_date: str,
        to_date: str,
        type: Literal["general", "unique", "average"] = "general",
        unit: Literal["day", "week", "month"] = "day",
        values: list[str] | None = None,
        limit: int | None = None,
    ) -> PropertyCountsResult:
        """Get event counts broken down by property values.

        Args:
            event: Event name.
            property_name: Property to break down by.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            type: Counting method.
            unit: Time unit.
            values: Optional list of property values to include.
            limit: Maximum number of property values.

        Returns:
            PropertyCountsResult with time-series per property value.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._live_query_service.property_counts(
            event=event,
            property_name=property_name,
            from_date=from_date,
            to_date=to_date,
            type=type,
            unit=unit,
            values=values,
            limit=limit,
        )

    def activity_feed(
        self,
        distinct_ids: list[str],
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> ActivityFeedResult:
        """Get activity feed for specific users.

        Args:
            distinct_ids: List of user identifiers.
            from_date: Optional start date filter.
            to_date: Optional end date filter.

        Returns:
            ActivityFeedResult with user events.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._live_query_service.activity_feed(
            distinct_ids=distinct_ids,
            from_date=from_date,
            to_date=to_date,
        )

    def query_saved_report(
        self,
        bookmark_id: int,
        *,
        bookmark_type: Literal[
            "insights", "funnels", "retention", "flows"
        ] = "insights",
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> SavedReportResult:
        """Query a saved report by bookmark type.

        Routes to the appropriate Mixpanel API endpoint based on bookmark_type
        and returns the normalized result.

        Args:
            bookmark_id: ID of saved report (from list_bookmarks or Mixpanel URL).
            bookmark_type: Type of bookmark to query. Determines which API endpoint
                is called. Defaults to 'insights'.
            from_date: Start date (YYYY-MM-DD). Required for funnels, optional otherwise.
            to_date: End date (YYYY-MM-DD). Required for funnels, optional otherwise.

        Returns:
            SavedReportResult with report data and report_type property.

        Raises:
            ConfigError: If API credentials not available.
            QueryError: If bookmark_id is invalid or report not found.
        """
        return self._live_query_service.query_saved_report(
            bookmark_id=bookmark_id,
            bookmark_type=bookmark_type,
            from_date=from_date,
            to_date=to_date,
        )

    def query_saved_flows(self, bookmark_id: int) -> FlowsResult:
        """Query a saved Flows report.

        Executes a saved Flows report by its bookmark ID, returning
        step data, breakdowns, and conversion rates.

        Args:
            bookmark_id: ID of saved flows report (from list_bookmarks or Mixpanel URL).

        Returns:
            FlowsResult with steps, breakdowns, and conversion rate.

        Raises:
            ConfigError: If API credentials not available.
            QueryError: If bookmark_id is invalid or report not found.
        """
        return self._live_query_service.query_saved_flows(bookmark_id=bookmark_id)

    def frequency(
        self,
        *,
        from_date: str,
        to_date: str,
        unit: Literal["day", "week", "month"] = "day",
        addiction_unit: Literal["hour", "day"] = "hour",
        event: str | None = None,
        where: str | None = None,
    ) -> FrequencyResult:
        """Analyze event frequency distribution.

        Args:
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            unit: Overall time unit.
            addiction_unit: Measurement granularity.
            event: Optional event filter.
            where: Optional WHERE clause.

        Returns:
            FrequencyResult with frequency distribution.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._live_query_service.frequency(
            from_date=from_date,
            to_date=to_date,
            unit=unit,
            addiction_unit=addiction_unit,
            event=event,
            where=where,
        )

    def segmentation_numeric(
        self,
        event: str,
        *,
        from_date: str,
        to_date: str,
        on: str,
        unit: Literal["hour", "day"] = "day",
        where: str | None = None,
        type: Literal["general", "unique", "average"] = "general",
    ) -> NumericBucketResult:
        """Bucket events by numeric property ranges.

        Args:
            event: Event name.
            from_date: Start date.
            to_date: End date.
            on: Numeric property expression.
            unit: Time unit.
            where: Optional filter.
            type: Counting method.

        Returns:
            NumericBucketResult with bucketed data.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._live_query_service.segmentation_numeric(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=on,
            unit=unit,
            where=where,
            type=type,
        )

    def segmentation_sum(
        self,
        event: str,
        *,
        from_date: str,
        to_date: str,
        on: str,
        unit: Literal["hour", "day"] = "day",
        where: str | None = None,
    ) -> NumericSumResult:
        """Calculate sum of numeric property over time.

        Args:
            event: Event name.
            from_date: Start date.
            to_date: End date.
            on: Numeric property expression.
            unit: Time unit.
            where: Optional filter.

        Returns:
            NumericSumResult with sum values per period.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._live_query_service.segmentation_sum(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=on,
            unit=unit,
            where=where,
        )

    def segmentation_average(
        self,
        event: str,
        *,
        from_date: str,
        to_date: str,
        on: str,
        unit: Literal["hour", "day"] = "day",
        where: str | None = None,
    ) -> NumericAverageResult:
        """Calculate average of numeric property over time.

        Args:
            event: Event name.
            from_date: Start date.
            to_date: End date.
            on: Numeric property expression.
            unit: Time unit.
            where: Optional filter.

        Returns:
            NumericAverageResult with average values per period.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._live_query_service.segmentation_average(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=on,
            unit=unit,
            where=where,
        )

    # =========================================================================
    # JQL-BASED REMOTE DISCOVERY METHODS
    # =========================================================================

    def property_distribution(
        self,
        event: str,
        property: str,
        *,
        from_date: str,
        to_date: str,
        limit: int = 20,
    ) -> PropertyDistributionResult:
        """Get distribution of values for a property.

        Uses JQL to count occurrences of each property value, returning
        counts and percentages sorted by frequency.

        Args:
            event: Event name to analyze.
            property: Property name to get distribution for.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            limit: Maximum number of values to return. Default: 20.

        Returns:
            PropertyDistributionResult with value counts and percentages.

        Raises:
            ConfigError: If API credentials not available.
            QueryError: Script execution error.

        Example:
            ```python
            result = ws.property_distribution(
                event="Purchase",
                property="country",
                from_date="2024-01-01",
                to_date="2024-01-31",
            )
            for v in result.values:
                print(f"{v.value}: {v.count} ({v.percentage:.1f}%)")
            ```
        """
        return self._live_query_service.property_distribution(
            event=event,
            property=property,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )

    def numeric_summary(
        self,
        event: str,
        property: str,
        *,
        from_date: str,
        to_date: str,
        percentiles: list[int] | None = None,
    ) -> NumericPropertySummaryResult:
        """Get statistical summary for a numeric property.

        Uses JQL to compute count, min, max, avg, stddev, and percentiles
        for a numeric property.

        Args:
            event: Event name to analyze.
            property: Numeric property name.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            percentiles: Percentiles to compute. Default: [25, 50, 75, 90, 95, 99].

        Returns:
            NumericPropertySummaryResult with statistics.

        Raises:
            ConfigError: If API credentials not available.
            QueryError: Script execution error or non-numeric property.

        Example:
            ```python
            result = ws.numeric_summary(
                event="Purchase",
                property="amount",
                from_date="2024-01-01",
                to_date="2024-01-31",
            )
            print(f"Avg: {result.avg}, Median: {result.percentiles[50]}")
            ```
        """
        return self._live_query_service.numeric_summary(
            event=event,
            property=property,
            from_date=from_date,
            to_date=to_date,
            percentiles=percentiles,
        )

    def daily_counts(
        self,
        *,
        from_date: str,
        to_date: str,
        events: list[str] | None = None,
    ) -> DailyCountsResult:
        """Get daily event counts.

        Uses JQL to count events by day, optionally filtered to specific events.

        Args:
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            events: Optional list of events to count. None = all events.

        Returns:
            DailyCountsResult with date/event/count tuples.

        Raises:
            ConfigError: If API credentials not available.
            QueryError: Script execution error.

        Example:
            ```python
            result = ws.daily_counts(
                from_date="2024-01-01",
                to_date="2024-01-07",
                events=["Purchase", "Signup"],
            )
            for c in result.counts:
                print(f"{c.date} {c.event}: {c.count}")
            ```
        """
        return self._live_query_service.daily_counts(
            from_date=from_date,
            to_date=to_date,
            events=events,
        )

    def engagement_distribution(
        self,
        *,
        from_date: str,
        to_date: str,
        events: list[str] | None = None,
        buckets: list[int] | None = None,
    ) -> EngagementDistributionResult:
        """Get user engagement distribution.

        Uses JQL to bucket users by their event count, showing how many
        users performed N events.

        Args:
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            events: Optional list of events to count. None = all events.
            buckets: Bucket boundaries. Default: [1, 2, 5, 10, 25, 50, 100].

        Returns:
            EngagementDistributionResult with user counts per bucket.

        Raises:
            ConfigError: If API credentials not available.
            QueryError: Script execution error.

        Example:
            ```python
            result = ws.engagement_distribution(
                from_date="2024-01-01",
                to_date="2024-01-31",
            )
            for b in result.buckets:
                print(f"{b.bucket_label}: {b.user_count} ({b.percentage:.1f}%)")
            ```
        """
        return self._live_query_service.engagement_distribution(
            from_date=from_date,
            to_date=to_date,
            events=events,
            buckets=buckets,
        )

    def property_coverage(
        self,
        event: str,
        properties: list[str],
        *,
        from_date: str,
        to_date: str,
    ) -> PropertyCoverageResult:
        """Get property coverage statistics.

        Uses JQL to count how often each property is defined (non-null)
        vs undefined for the specified event.

        Args:
            event: Event name to analyze.
            properties: List of property names to check.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).

        Returns:
            PropertyCoverageResult with coverage statistics per property.

        Raises:
            ConfigError: If API credentials not available.
            QueryError: Script execution error.

        Example:
            ```python
            result = ws.property_coverage(
                event="Purchase",
                properties=["coupon_code", "referrer"],
                from_date="2024-01-01",
                to_date="2024-01-31",
            )
            for c in result.coverage:
                print(f"{c.property}: {c.coverage_percentage:.1f}% defined")
            ```
        """
        return self._live_query_service.property_coverage(
            event=event,
            properties=properties,
            from_date=from_date,
            to_date=to_date,
        )

    # =========================================================================
    # INSIGHTS QUERY API (Phase 029)
    # =========================================================================

    def _build_query_params(
        self,
        *,
        events: Sequence[str | Metric | CohortMetric],
        math: MathType,
        math_property: str | None,
        per_user: PerUserAggregation | None,
        percentile_value: int | float | None = None,
        from_date: str | None,
        to_date: str | None,
        last: int,
        unit: QueryTimeUnit,
        group_by: str
        | GroupBy
        | CohortBreakdown
        | FrequencyBreakdown
        | list[str | GroupBy | CohortBreakdown | FrequencyBreakdown]
        | None,
        where: Filter | FrequencyFilter | list[Filter | FrequencyFilter] | None,
        formulas: Sequence[Formula],
        rolling: int | None,
        cumulative: bool,
        mode: str,
        time_comparison: TimeComparison | None = None,
        data_group_id: int | None = None,
    ) -> dict[str, Any]:
        """Build bookmark params dict from typed arguments.

        Generates the complete bookmark JSON structure expected by
        the Mixpanel insights query API.

        Args:
            events: Event names or Metric objects.
            math: Top-level aggregation function.
            math_property: Property for property-based math.
            per_user: Per-user pre-aggregation.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            last: Relative date range in days.
            unit: Time unit (hour, day, week, month, quarter).
            group_by: Breakdown specification.
            where: Filter conditions.
            formulas: Formula objects to append.
            rolling: Rolling window size.
            cumulative: Cumulative analysis mode.
            mode: Result mode (timeseries, total, table).
            time_comparison: Optional period-over-period comparison.
                Adds ``timeComparison`` to ``displayOptions``.
            data_group_id: Optional data group ID for group-level
                analytics. Default: ``None``.

        Returns:
            Bookmark params dict ready for insights query API.
        """
        # --- Build sections.show[] ---
        show: list[dict[str, Any]] = []
        for item in events:
            if isinstance(item, CohortMetric):
                # CohortMetric: cohort size tracking (CM3: ignore top-level math)
                cohort_behavior: dict[str, Any] = {
                    "type": "cohort",
                    "name": item.name or "",
                    "resourceType": "cohorts",
                    "dataGroupId": None,
                    "dataset": "$mixpanel",
                    "filtersDeterminer": "all",
                    "filters": [],
                }
                if isinstance(item.cohort, int):
                    cohort_behavior["id"] = item.cohort
                else:
                    raw = _sanitize_raw_cohort(item.cohort.to_dict())
                    # Server-side cohort processing expects `name` in
                    # the raw_cohort dict (matching get_raw_cohort_by_id
                    # DB format). Without it, label generation crashes.
                    raw["name"] = item.name or ""
                    cohort_behavior["raw_cohort"] = raw

                entry: dict[str, Any] = {
                    "type": "metric",
                    "behavior": cohort_behavior,
                    "measurement": {
                        "math": "unique",
                        "property": None,
                        "perUserAggregation": None,
                    },
                    "isHidden": bool(formulas),
                }
                show.append(entry)
                continue

            if isinstance(item, Metric):
                event_name = item.event
                item_math = item.math
                item_prop = item.property
                item_per_user = item.per_user
                item_percentile = item.percentile_value
                item_filters = item.filters
                item_filters_combinator = item.filters_combinator
                item_segment_method = item.segment_method
            else:
                event_name = item
                item_math = math
                item_prop = math_property
                item_per_user = per_user
                item_percentile = percentile_value
                item_filters = None
                item_filters_combinator = "all"
                item_segment_method = None

            # Map user-facing "percentile" to bookmark "custom_percentile"
            bookmark_math = (
                "custom_percentile" if item_math == "percentile" else item_math
            )

            measurement: dict[str, Any] = {"math": bookmark_math}
            if item_prop is not None:
                if isinstance(item_prop, CustomPropertyRef):
                    measurement["property"] = {
                        "customPropertyId": item_prop.id,
                        "name": "",
                        "resourceType": "events",
                    }
                elif isinstance(item_prop, InlineCustomProperty):
                    cp_dict: dict[str, Any] = {
                        "displayFormula": item_prop.formula,
                        "composedProperties": _build_composed_properties(
                            item_prop.inputs
                        ),
                        "name": "",
                        "description": "",
                        "resourceType": item_prop.resource_type,
                    }
                    if item_prop.property_type is not None:
                        cp_dict["propertyType"] = item_prop.property_type
                    measurement["property"] = {
                        "customProperty": cp_dict,
                        "name": "",
                        "resourceType": item_prop.resource_type,
                        "dataset": "$mixpanel",
                        "dataGroupId": None,
                    }
                else:
                    measurement["property"] = {
                        "name": item_prop,
                        "resourceType": "events",
                    }
            if item_per_user is not None:
                measurement["perUserAggregation"] = item_per_user
            if item_percentile is not None:
                measurement["percentile"] = item_percentile
            if item_segment_method is not None:
                measurement["segmentMethod"] = item_segment_method

            # Build behavior block with optional per-metric filters
            behavior_filters: list[dict[str, Any]] = []
            if item_filters:
                behavior_filters = [build_filter_entry(f) for f in item_filters]

            entry = {
                "type": "metric",
                "behavior": {
                    "type": "event",
                    "name": event_name,
                    "resourceType": "events",
                    "filtersDeterminer": item_filters_combinator,
                    "filters": behavior_filters,
                },
                "measurement": measurement,
            }

            # Mark hidden when formula is present
            if formulas:
                entry["isHidden"] = True

            show.append(entry)

        # Append formula entries to show[]
        for f in formulas:
            formula_entry: dict[str, Any] = {
                "type": "formula",
                "definition": f.expression,
                "measurement": {},
                "referencedMetrics": [],
            }
            if f.label:
                formula_entry["name"] = f.label
            show.append(formula_entry)

        # --- Build sections.time (array) ---
        time_section = build_time_section(
            from_date=from_date,
            to_date=to_date,
            last=last,
            unit=unit,
        )

        # --- Build sections.filter[] ---
        filter_section = build_filter_section(where)

        # --- Build sections.group[] ---
        group_section = build_group_section(group_by, data_group_id=data_group_id)

        # --- Build displayOptions ---
        chart_type_map = {
            "timeseries": "line",
            "total": "bar",
            "table": "table",
        }
        analysis = "linear"
        display_options: dict[str, Any] = {
            "chartType": chart_type_map.get(mode, "line"),
            "analysis": analysis,
        }
        if rolling is not None:
            display_options["analysis"] = "rolling"
            display_options["rollingWindowSize"] = rolling
        elif cumulative:
            display_options["analysis"] = "cumulative"

        if time_comparison is not None:
            display_options["timeComparison"] = build_time_comparison(time_comparison)

        # --- Assemble bookmark params ---
        sections: dict[str, Any] = {
            "show": show,
            "time": time_section,
            "filter": filter_section,
            "group": group_section,
        }
        if data_group_id is not None:
            sections["dataGroupId"] = data_group_id

        return {
            "sections": sections,
            "displayOptions": display_options,
        }

    def query(
        self,
        events: str
        | Metric
        | CohortMetric
        | Formula
        | Sequence[str | Metric | CohortMetric | Formula],
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        last: int = 30,
        unit: QueryTimeUnit = "day",
        math: MathType = "total",
        math_property: str | None = None,
        per_user: PerUserAggregation | None = None,
        percentile_value: int | float | None = None,
        group_by: str
        | GroupBy
        | CohortBreakdown
        | FrequencyBreakdown
        | list[str | GroupBy | CohortBreakdown | FrequencyBreakdown]
        | None = None,
        where: Filter | FrequencyFilter | list[Filter | FrequencyFilter] | None = None,
        formula: str | None = None,
        formula_label: str | None = None,
        rolling: int | None = None,
        cumulative: bool = False,
        mode: Literal["timeseries", "total", "table"] = "timeseries",
        time_comparison: TimeComparison | None = None,
        data_group_id: int | None = None,
    ) -> QueryResult:
        """Run a typed insights query against the Mixpanel API.

        Generates bookmark params from keyword arguments, POSTs them inline
        to ``/api/query/insights``, and returns a structured QueryResult
        with lazy DataFrame conversion.

        Args:
            events: Event name(s) to query. Accepts a single string,
                a Metric object, a CohortMetric object, a Formula
                object, or a sequence mixing strings, Metrics,
                CohortMetrics, and Formulas. Formula objects in the
                list are extracted and appended as formula show clauses.
                When events includes a CohortMetric, ``math``,
                ``math_property``, and ``per_user`` are silently
                ignored for that entry — cohort size is always counted
                as unique users (CM3).
            from_date: Start date (YYYY-MM-DD). If set, overrides ``last``.
            to_date: End date (YYYY-MM-DD). Requires ``from_date``.
            last: Relative time range in days. Default: 30.
                Ignored if ``from_date`` is set.
            unit: Time aggregation unit. Default: ``"day"``.
            math: Aggregation function for plain-string events.
                Default: ``"total"``.
            math_property: Property name for property-based math
                (average, sum, percentiles).
            per_user: Per-user pre-aggregation (average, total, min, max).
            percentile_value: Custom percentile value (e.g. 95 for p95).
                Required when ``math="percentile"``. Maps to ``percentile``
                in bookmark measurement. Ignored for other math types.
            group_by: Break down results by property or cohort membership.
                Accepts a string, ``GroupBy``, ``CohortBreakdown``, or
                list of any mix.
            where: Filter results by conditions. Accepts a Filter
                or list of Filters.
            formula: Formula expression referencing events by position
                (A, B, C...). Requires 2+ events. Cannot be combined
                with Formula objects in ``events``.
            formula_label: Display label for formula result.
            rolling: Rolling window size in periods.
                Mutually exclusive with ``cumulative``.
            cumulative: Enable cumulative analysis mode.
                Mutually exclusive with ``rolling``.
            mode: Result shape. ``"timeseries"`` returns per-period data,
                ``"total"`` returns a single aggregate, ``"table"`` returns
                tabular data. Default: ``"timeseries"``.
            time_comparison: Optional period-over-period comparison.
                Use ``TimeComparison.relative("month")`` for previous
                month, ``TimeComparison.absolute_start("2026-01-01")``
                for a fixed start date, etc. Default: ``None``.
            data_group_id: Optional data group ID for group-level
                analytics. Scopes the query to a specific data group.
                Default: ``None``.

        Returns:
            QueryResult with series data, DataFrame, and metadata.

        Raises:
            ValueError: If arguments violate validation rules.
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials.
            QueryError: Invalid query parameters.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            ws = Workspace()

            # Simple event query
            result = ws.query("Login")
            print(result.df.head())

            # With aggregation and time range
            result = ws.query("Login", math="unique", last=7, unit="day")

            # Multi-event with formula (top-level parameter)
            result = ws.query(
                [Metric("Signup", math="unique"), Metric("Purchase", math="unique")],
                formula="(B / A) * 100",
                formula_label="Conversion Rate",
            )

            # Multi-event with formula (Formula in list)
            result = ws.query(
                [Metric("Signup", math="unique"),
                 Metric("Purchase", math="unique"),
                 Formula("(B / A) * 100", label="Conversion Rate")],
            )
            ```
        """
        params = self._resolve_and_build_params(
            events=events,
            from_date=from_date,
            to_date=to_date,
            last=last,
            unit=unit,
            math=math,
            math_property=math_property,
            per_user=per_user,
            percentile_value=percentile_value,
            group_by=group_by,
            where=where,
            formula=formula,
            formula_label=formula_label,
            rolling=rolling,
            cumulative=cumulative,
            mode=mode,
            time_comparison=time_comparison,
            data_group_id=data_group_id,
        )

        return self._live_query_service.query(
            bookmark_params=params,
            project_id=int(self._session.project.id),
        )

    def build_params(
        self,
        events: str
        | Metric
        | CohortMetric
        | Formula
        | Sequence[str | Metric | CohortMetric | Formula],
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        last: int = 30,
        unit: QueryTimeUnit = "day",
        math: MathType = "total",
        math_property: str | None = None,
        per_user: PerUserAggregation | None = None,
        percentile_value: int | float | None = None,
        group_by: str
        | GroupBy
        | CohortBreakdown
        | FrequencyBreakdown
        | list[str | GroupBy | CohortBreakdown | FrequencyBreakdown]
        | None = None,
        where: Filter | FrequencyFilter | list[Filter | FrequencyFilter] | None = None,
        formula: str | None = None,
        formula_label: str | None = None,
        rolling: int | None = None,
        cumulative: bool = False,
        mode: Literal["timeseries", "total", "table"] = "timeseries",
        time_comparison: TimeComparison | None = None,
        data_group_id: int | None = None,
    ) -> dict[str, Any]:
        """Build validated bookmark params without executing the API call.

        Has the same signature as :meth:`query` but returns the generated
        bookmark params dict instead of querying the Mixpanel API. Useful
        for debugging, inspecting generated JSON, persisting via
        :meth:`create_bookmark`, or testing.

        Args:
            events: Event name(s) to query. Accepts a single string,
                a ``Metric``, ``CohortMetric``, ``Formula``, or a
                sequence mixing strings, ``Metric``s, ``CohortMetric``s,
                and ``Formula``s.
            from_date: Start date (YYYY-MM-DD). If set, overrides ``last``.
            to_date: End date (YYYY-MM-DD). Requires ``from_date``.
            last: Relative time range in days. Default: 30.
            unit: Time aggregation unit. Default: ``"day"``.
            math: Aggregation function for plain-string events.
                Default: ``"total"``.
            math_property: Property name for property-based math.
            per_user: Per-user pre-aggregation.
            percentile_value: Custom percentile value (e.g. 95).
                Required when ``math="percentile"``.
            group_by: Break down results by property or cohort membership.
                Accepts a string, ``GroupBy``, ``CohortBreakdown``, or
                list of any mix.
            where: Filter results by conditions.
            formula: Formula expression referencing events by position.
            formula_label: Display label for formula result.
            rolling: Rolling window size in periods.
            cumulative: Enable cumulative analysis mode.
            mode: Result shape. Default: ``"timeseries"``.
            time_comparison: Optional period-over-period comparison.
                Use ``TimeComparison.relative("month")`` for previous
                month, etc. Default: ``None``.
            data_group_id: Optional data group ID for group-level
                analytics. Scopes the query to a specific data group.
                Default: ``None``.

        Returns:
            Bookmark params dict with ``sections`` and ``displayOptions``
            keys, ready for use with the insights API or
            :meth:`create_bookmark`.

        Raises:
            BookmarkValidationError: If arguments violate validation rules.

        Example:
            ```python
            ws = Workspace()

            # Inspect generated bookmark JSON
            params = ws.build_params("Login", math="unique", last=7)
            print(json.dumps(params, indent=2))

            # Save as a bookmark (dashboard_id required)
            ws.create_bookmark(CreateBookmarkParams(
                name="Daily Unique Logins",
                bookmark_type="insights",
                params=params,
                dashboard_id=12345,
            ))
            ```
        """
        return self._resolve_and_build_params(
            events=events,
            from_date=from_date,
            to_date=to_date,
            last=last,
            unit=unit,
            math=math,
            math_property=math_property,
            per_user=per_user,
            percentile_value=percentile_value,
            group_by=group_by,
            where=where,
            formula=formula,
            formula_label=formula_label,
            rolling=rolling,
            cumulative=cumulative,
            mode=mode,
            time_comparison=time_comparison,
            data_group_id=data_group_id,
        )

    def _resolve_and_build_params(
        self,
        *,
        events: str
        | Metric
        | CohortMetric
        | Formula
        | Sequence[str | Metric | CohortMetric | Formula],
        from_date: str | None,
        to_date: str | None,
        last: int,
        unit: QueryTimeUnit,
        math: MathType,
        math_property: str | None,
        per_user: PerUserAggregation | None,
        percentile_value: int | float | None = None,
        group_by: str
        | GroupBy
        | CohortBreakdown
        | FrequencyBreakdown
        | list[str | GroupBy | CohortBreakdown | FrequencyBreakdown]
        | None = None,
        where: Filter | FrequencyFilter | list[Filter | FrequencyFilter] | None = None,
        formula: str | None = None,
        formula_label: str | None = None,
        rolling: int | None = None,
        cumulative: bool = False,
        mode: InsightsMode = "timeseries",
        time_comparison: TimeComparison | None = None,
        data_group_id: int | None = None,
    ) -> dict[str, Any]:
        """Normalize, validate, and build bookmark params.

        Shared implementation for :meth:`query` and :meth:`build_params`.
        Handles type guards, event/formula normalization, argument
        validation (Layer 1), bookmark construction, and bookmark
        structure validation (Layer 2).

        Args:
            events: Raw events input (str, Metric, CohortMetric,
                Formula, or sequence).
            from_date: Start date (YYYY-MM-DD) or None.
            to_date: End date (YYYY-MM-DD) or None.
            last: Relative time range in days.
            unit: Time aggregation unit.
            math: Aggregation function.
            math_property: Property for property-based math.
            per_user: Per-user pre-aggregation.
            percentile_value: Custom percentile value. Required when
                ``math="percentile"``. Maps to ``percentile`` in
                bookmark measurement JSON.
            group_by: Breakdown specification.
            where: Filter conditions.
            formula: Top-level formula expression.
            formula_label: Display label for formula.
            rolling: Rolling window size.
            cumulative: Cumulative analysis mode.
            mode: Result shape.
            time_comparison: Optional period-over-period comparison.
            data_group_id: Optional data group ID for group-level
                analytics. Default: ``None``.

        Returns:
            Validated bookmark params dict.

        Raises:
            BookmarkValidationError: If validation fails at any layer.
        """
        # Type guard: events must be str, Metric, CohortMetric, Formula, or sequence thereof
        if not isinstance(events, (str, Metric, CohortMetric, Formula, list, tuple)):
            raise BookmarkValidationError(
                [
                    ValidationError(
                        path="events",
                        message=(
                            f"events must be a string, Metric, CohortMetric, Formula, or "
                            f"sequence, got {type(events).__name__}"
                        ),
                        code="V21_INVALID_EVENT_TYPE",
                    )
                ]
            )

        # Type guard: where must be Filter, FrequencyFilter, or list
        if where is not None and not isinstance(where, (Filter, FrequencyFilter, list)):
            raise BookmarkValidationError(
                [
                    ValidationError(
                        path="where",
                        message=(
                            f"where must be a Filter, FrequencyFilter, or list, "
                            f"got {type(where).__name__}"
                        ),
                        code="V25_INVALID_FILTER_TYPE",
                    )
                ]
            )

        # Normalize events to sequence, separating Formula objects
        if isinstance(events, str):
            events_list: list[str | Metric | CohortMetric] = [events]
            formulas_from_list: list[Formula] = []
        elif isinstance(events, (Metric, CohortMetric)):
            events_list = [events]
            formulas_from_list = []
        elif isinstance(events, Formula):
            raise BookmarkValidationError(
                [
                    ValidationError(
                        path="events",
                        message="Formula cannot be the only item; provide event(s) too",
                        code="V0_NO_EVENTS",
                    )
                ]
            )
        else:
            events_list = []
            formulas_from_list = []
            for item in events:
                if isinstance(item, Formula):
                    formulas_from_list.append(item)
                else:
                    events_list.append(item)

        # Resolve formulas: can't use both approaches
        if formula is not None and formulas_from_list:
            raise BookmarkValidationError(
                [
                    ValidationError(
                        path="formula",
                        message=(
                            "Cannot combine top-level 'formula' parameter with "
                            "Formula objects in the events list; use one approach"
                        ),
                        code="V4_FORMULA_CONFLICT",
                    )
                ]
            )

        if formula is not None:
            resolved_formulas: Sequence[Formula] = [
                Formula(expression=formula, label=formula_label)
            ]
        else:
            resolved_formulas = formulas_from_list

        # Layer 1: Argument validation
        arg_errors = validate_query_args(
            events=events_list,
            math=math,
            math_property=math_property,
            per_user=per_user,
            percentile_value=percentile_value,
            from_date=from_date,
            to_date=to_date,
            last=last,
            has_formula=bool(resolved_formulas),
            rolling=rolling,
            cumulative=cumulative,
            group_by=group_by,
            formulas=resolved_formulas,
            data_group_id=data_group_id,
        )
        # CP1-CP6: Custom property validation for where filters
        arg_errors.extend(_scan_custom_properties(where=where))
        if any(e.severity == "error" for e in arg_errors):
            raise BookmarkValidationError(arg_errors)

        # Build bookmark params
        params = self._build_query_params(
            events=events_list,
            math=math,
            math_property=math_property,
            per_user=per_user,
            percentile_value=percentile_value,
            from_date=from_date,
            to_date=to_date,
            last=last,
            unit=unit,
            group_by=group_by,
            where=where,
            formulas=resolved_formulas,
            rolling=rolling,
            cumulative=cumulative,
            mode=mode,
            time_comparison=time_comparison,
            data_group_id=data_group_id,
        )

        # Layer 2: Bookmark structure validation
        bookmark_errors = validate_bookmark(params)
        if any(e.severity == "error" for e in bookmark_errors):
            raise BookmarkValidationError(bookmark_errors)

        return params

    # =========================================================================
    # Funnel Query (Phase 032)
    # =========================================================================

    def _build_funnel_params(
        self,
        *,
        steps: list[FunnelStep],
        conversion_window: int,
        conversion_window_unit: str,
        order: str,
        math: str,
        math_property: str | None,
        from_date: str | None,
        to_date: str | None,
        last: int,
        unit: QueryTimeUnit,
        group_by: str
        | GroupBy
        | CohortBreakdown
        | list[str | GroupBy | CohortBreakdown]
        | None,
        where: Filter | list[Filter] | None,
        exclusions: list[Exclusion],
        holding_constant: list[HoldingConstant],
        mode: str,
        reentry_mode: FunnelReentryMode | None = None,
        time_comparison: TimeComparison | None = None,
        data_group_id: int | None = None,
    ) -> dict[str, Any]:
        """Build funnel bookmark params dict from typed arguments.

        Generates the complete bookmark JSON structure expected by
        the Mixpanel insights query API for funnel-type bookmarks.

        Args:
            steps: Normalized FunnelStep objects.
            conversion_window: Conversion window size.
            conversion_window_unit: Conversion window time unit.
            order: Funnel step ordering mode.
            math: Aggregation function.
            math_property: Numeric property name for property-aggregation
                math types (average, median, etc.), or None.
            from_date: Start date (YYYY-MM-DD) or None.
            to_date: End date (YYYY-MM-DD) or None.
            last: Relative date range in days.
            unit: Time granularity.
            group_by: Breakdown specification.
            where: Filter conditions.
            exclusions: Normalized Exclusion objects.
            holding_constant: Normalized HoldingConstant objects.
            mode: Display mode (steps, trends, table).
            reentry_mode: Funnel reentry mode controlling how users
                re-enter the funnel after conversion. Maps to
                ``funnelReentryMode`` in the behavior block.
                Default: ``None`` (omitted from bookmark).
            time_comparison: Optional period-over-period comparison.
                Adds ``timeComparison`` to ``displayOptions``.
            data_group_id: Optional data group ID for group-level
                analytics. Default: ``None``.

        Returns:
            Bookmark params dict ready for insights query API.
        """
        # Build behaviors array from steps
        behaviors: list[dict[str, Any]] = []
        for step in steps:
            behavior_entry: dict[str, Any] = {
                "type": "event",
                "id": None,
                "name": step.event,
                "filters": [],
                "filtersDeterminer": step.filters_combinator,
                "funnelOrder": order,
            }
            # Per-step filters
            if step.filters:
                behavior_entry["filters"] = [
                    build_filter_entry(f) for f in step.filters
                ]
            # Per-step label → renamed
            if step.label is not None:
                behavior_entry["renamed"] = step.label
            # Per-step order override
            if step.order is not None:
                behavior_entry["funnelOrder"] = step.order
            behaviors.append(behavior_entry)

        # Build exclusions array
        exclusions_list: list[dict[str, Any]] = []
        for ex in exclusions:
            ex_entry: dict[str, Any] = {
                "event": ex.event,
            }
            # Step range — API uses 1-indexed, Exclusion uses 0-indexed
            api_from = ex.from_step + 1
            api_to = (ex.to_step + 1) if ex.to_step is not None else len(steps)
            ex_entry["steps"] = {
                "from": api_from,
                "to": api_to,
            }
            exclusions_list.append(ex_entry)

        # Build aggregateBy array
        aggregate_by: list[dict[str, Any]] = [
            {"value": hc.property, "resourceType": hc.resource_type}
            for hc in holding_constant
        ]

        # Build behavior block
        behavior: dict[str, Any] = {
            "type": "funnel",
            "resourceType": "events",
            "behaviors": behaviors,
            "conversionWindowDuration": conversion_window,
            "conversionWindowUnit": conversion_window_unit,
            "funnelOrder": order,
            "exclusions": exclusions_list,
            "aggregateBy": aggregate_by,
            "filter": [],
        }
        if reentry_mode is not None:
            behavior["funnelReentryMode"] = reentry_mode

        # Build measurement
        measurement: dict[str, Any] = {
            "math": math,
            "property": (
                {
                    "name": math_property,
                    "type": "number",
                    "resourceType": "events",
                }
                if math_property
                else None
            ),
            "stepIndex": None,
        }

        # Build show clause
        show: list[dict[str, Any]] = [
            {
                "type": "metric",
                "behavior": behavior,
                "measurement": measurement,
            }
        ]

        # Build sections using shared builders
        time_section = build_time_section(
            from_date=from_date,
            to_date=to_date,
            last=last,
            unit=unit,
        )
        filter_section = patch_custom_property_filters_for_transform(
            build_filter_section(where)
        )
        group_section = build_group_section(group_by, data_group_id=data_group_id)

        # Chart type mapping
        chart_type_map = {
            "steps": "funnel-steps",
            "trends": "line",
            "table": "table",
        }

        display_options: dict[str, Any] = {
            "chartType": chart_type_map.get(mode, "funnel-steps"),
        }
        if time_comparison is not None:
            display_options["timeComparison"] = build_time_comparison(time_comparison)

        sections: dict[str, Any] = {
            "show": show,
            "time": time_section,
            "filter": filter_section,
            "group": group_section,
            "formula": [],
        }
        if data_group_id is not None:
            sections["dataGroupId"] = data_group_id

        return {
            "sections": sections,
            "displayOptions": display_options,
        }

    def _resolve_and_build_funnel_params(
        self,
        *,
        steps: list[str | FunnelStep],
        conversion_window: int,
        conversion_window_unit: ConversionWindowUnit,
        order: FunnelOrder,
        math: FunnelMathType,
        math_property: str | None,
        from_date: str | None,
        to_date: str | None,
        last: int,
        unit: QueryTimeUnit,
        group_by: str
        | GroupBy
        | CohortBreakdown
        | list[str | GroupBy | CohortBreakdown]
        | None,
        where: Filter | list[Filter] | None,
        exclusions: list[str | Exclusion] | None,
        holding_constant: str | HoldingConstant | list[str | HoldingConstant] | None,
        mode: FunnelMode,
        reentry_mode: FunnelReentryMode | None = None,
        time_comparison: TimeComparison | None = None,
        data_group_id: int | None = None,
    ) -> dict[str, Any]:
        """Normalize, validate, and build funnel bookmark params.

        Shared implementation for :meth:`query_funnel` and
        :meth:`build_funnel_params`. Handles normalization of
        string shorthand to typed objects, argument validation
        (Layer 1), bookmark construction, and structure validation
        (Layer 2).

        Args:
            steps: Funnel step specs (strings or FunnelStep objects).
            conversion_window: Conversion window size.
            conversion_window_unit: Conversion window time unit.
            order: Funnel step ordering mode.
            math: Aggregation function.
            math_property: Numeric property name for property-aggregation
                math types, or None.
            from_date: Start date (YYYY-MM-DD) or None.
            to_date: End date (YYYY-MM-DD) or None.
            last: Relative date range in days.
            unit: Time granularity.
            group_by: Breakdown specification.
            where: Filter conditions.
            exclusions: Events to exclude, or None.
            holding_constant: Properties to hold constant, or None.
            mode: Display mode.
            reentry_mode: Funnel reentry mode controlling how users
                re-enter the funnel. Default: ``None`` (omitted).
            time_comparison: Optional period-over-period comparison.
            data_group_id: Optional data group ID for group-level
                analytics. Default: ``None``.

        Returns:
            Validated bookmark params dict.

        Raises:
            BookmarkValidationError: If validation fails at any layer.
        """
        # Normalize steps: str → FunnelStep
        normalized_steps = [FunnelStep(s) if isinstance(s, str) else s for s in steps]

        # Normalize exclusions: str → Exclusion
        normalized_exclusions: list[Exclusion] = []
        if exclusions is not None:
            normalized_exclusions = [
                Exclusion(e) if isinstance(e, str) else e for e in exclusions
            ]

        # Normalize holding_constant: str → HoldingConstant
        normalized_hc: list[HoldingConstant] = []
        if holding_constant is not None:
            if isinstance(holding_constant, (str, HoldingConstant)):
                hc_list: list[str | HoldingConstant] = [holding_constant]
            else:
                hc_list = list(holding_constant)
            normalized_hc = [
                HoldingConstant(h) if isinstance(h, str) else h for h in hc_list
            ]

        # Layer 1: Argument validation
        arg_errors = validate_funnel_args(
            steps=normalized_steps,
            conversion_window=conversion_window,
            conversion_window_unit=conversion_window_unit,
            math=math,
            math_property=math_property,
            exclusions=normalized_exclusions if normalized_exclusions else None,
            holding_constant=normalized_hc if normalized_hc else None,
            from_date=from_date,
            to_date=to_date,
            last=last,
            group_by=group_by,
            reentry_mode=reentry_mode,
            data_group_id=data_group_id,
        )
        # CP1-CP6: Custom property validation for where filters
        arg_errors.extend(_scan_custom_properties(where=where))
        if any(e.severity == "error" for e in arg_errors):
            raise BookmarkValidationError(arg_errors)

        # Build bookmark params
        params = self._build_funnel_params(
            steps=normalized_steps,
            conversion_window=conversion_window,
            conversion_window_unit=conversion_window_unit,
            order=order,
            math=math,
            math_property=math_property,
            from_date=from_date,
            to_date=to_date,
            last=last,
            unit=unit,
            group_by=group_by,
            where=where,
            exclusions=normalized_exclusions,
            holding_constant=normalized_hc,
            mode=mode,
            reentry_mode=reentry_mode,
            time_comparison=time_comparison,
            data_group_id=data_group_id,
        )

        # Layer 2: Bookmark structure validation
        bookmark_errors = validate_bookmark(params, bookmark_type="funnels")
        if any(e.severity == "error" for e in bookmark_errors):
            raise BookmarkValidationError(bookmark_errors)

        return params

    def query_funnel(
        self,
        steps: list[str | FunnelStep],
        *,
        conversion_window: int = 14,
        conversion_window_unit: Literal[
            "second", "minute", "hour", "day", "week", "month", "session"
        ] = "day",
        order: Literal["loose", "any"] = "loose",
        from_date: str | None = None,
        to_date: str | None = None,
        last: int = 30,
        unit: QueryTimeUnit = "day",
        math: FunnelMathType = "conversion_rate_unique",
        math_property: str | None = None,
        group_by: str
        | GroupBy
        | CohortBreakdown
        | list[str | GroupBy | CohortBreakdown]
        | None = None,
        where: Filter | list[Filter] | None = None,
        exclusions: list[str | Exclusion] | None = None,
        holding_constant: (
            str | HoldingConstant | list[str | HoldingConstant] | None
        ) = None,
        mode: Literal["steps", "trends", "table"] = "steps",
        reentry_mode: FunnelReentryMode | None = None,
        time_comparison: TimeComparison | None = None,
        data_group_id: int | None = None,
    ) -> FunnelQueryResult:
        """Run a typed funnel query against the Mixpanel API.

        Generates funnel bookmark params from keyword arguments, POSTs
        them inline to ``/api/query/insights``, and returns a structured
        FunnelQueryResult with lazy DataFrame conversion.

        Args:
            steps: Funnel step specifications. At least 2 required.
                Accepts event name strings or ``FunnelStep`` objects
                for per-step filters, labels, and ordering.
            conversion_window: How long users have to complete the
                funnel. Default: 14.
            conversion_window_unit: Time unit for conversion window.
                Default: ``"day"``.
            order: Step ordering mode. ``"loose"`` requires steps in
                order but allows other events between. ``"any"`` allows
                steps in any order. Default: ``"loose"``.
            from_date: Start date (YYYY-MM-DD). If set, overrides
                ``last``.
            to_date: End date (YYYY-MM-DD). Requires ``from_date``.
            last: Relative time range in days. Default: 30.
            unit: Time aggregation unit. Default: ``"day"``.
            math: Funnel aggregation function. Default:
                ``"conversion_rate_unique"``.
            math_property: Numeric property name for property-aggregation
                math types (``"average"``, ``"median"``, ``"min"``,
                ``"max"``, ``"p25"``, ``"p75"``, ``"p90"``, ``"p99"``).
                Required when using those math types; must be ``None``
                for count/rate math types. Default: ``None``.
            group_by: Break down results by property or cohort
                membership. Accepts a string, ``GroupBy``,
                ``CohortBreakdown``, or list of any mix.
            where: Filter results by conditions.
            exclusions: Events to exclude between steps. Accepts
                event name strings or ``Exclusion`` objects.
            holding_constant: Properties to hold constant across
                steps. Accepts strings, ``HoldingConstant`` objects,
                or a list mixing both.
            mode: Result display mode. ``"steps"`` shows step-level
                data, ``"trends"`` shows conversion over time,
                ``"table"`` shows tabular breakdown. Default:
                ``"steps"``.
            reentry_mode: Funnel reentry mode controlling how users
                re-enter the funnel after conversion. One of
                ``"default"``, ``"basic"``, ``"aggressive"``, or
                ``"optimized"``. Default: ``None`` (server default).
            time_comparison: Optional period-over-period comparison.
                Use ``TimeComparison.relative("month")`` for previous
                month, etc. Default: ``None``.
            data_group_id: Optional data group ID for group-level
                analytics. Scopes the query to a specific data group.
                Default: ``None``.

        Returns:
            FunnelQueryResult with step data, DataFrame, and metadata.

        Raises:
            BookmarkValidationError: If arguments violate validation
                rules (before API call).
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials.
            QueryError: Invalid query parameters.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            ws = Workspace()

            # Simple two-step funnel
            result = ws.query_funnel(["Signup", "Purchase"])
            print(result.overall_conversion_rate)

            # Configured funnel
            result = ws.query_funnel(
                ["Signup", "Add to Cart", "Checkout", "Purchase"],
                conversion_window=7,
                order="loose",
                last=90,
            )
            print(result.df)
            ```
        """
        params = self._resolve_and_build_funnel_params(
            steps=steps,
            conversion_window=conversion_window,
            conversion_window_unit=conversion_window_unit,
            order=order,
            math=math,
            math_property=math_property,
            from_date=from_date,
            to_date=to_date,
            last=last,
            unit=unit,
            group_by=group_by,
            where=where,
            exclusions=exclusions,
            holding_constant=holding_constant,
            mode=mode,
            reentry_mode=reentry_mode,
            time_comparison=time_comparison,
            data_group_id=data_group_id,
        )

        return self._live_query_service.query_funnel(
            bookmark_params=params,
            project_id=int(self._session.project.id),
        )

    def build_funnel_params(
        self,
        steps: list[str | FunnelStep],
        *,
        conversion_window: int = 14,
        conversion_window_unit: Literal[
            "second", "minute", "hour", "day", "week", "month", "session"
        ] = "day",
        order: Literal["loose", "any"] = "loose",
        from_date: str | None = None,
        to_date: str | None = None,
        last: int = 30,
        unit: QueryTimeUnit = "day",
        math: FunnelMathType = "conversion_rate_unique",
        math_property: str | None = None,
        group_by: str
        | GroupBy
        | CohortBreakdown
        | list[str | GroupBy | CohortBreakdown]
        | None = None,
        where: Filter | list[Filter] | None = None,
        exclusions: list[str | Exclusion] | None = None,
        holding_constant: (
            str | HoldingConstant | list[str | HoldingConstant] | None
        ) = None,
        mode: Literal["steps", "trends", "table"] = "steps",
        reentry_mode: FunnelReentryMode | None = None,
        time_comparison: TimeComparison | None = None,
        data_group_id: int | None = None,
    ) -> dict[str, Any]:
        """Build validated funnel bookmark params without executing.

        Has the same signature as :meth:`query_funnel` but returns the
        generated bookmark params dict instead of querying the API.
        Useful for debugging, inspecting generated JSON, persisting
        via :meth:`create_bookmark`, or testing.

        Args:
            steps: Funnel step specifications. At least 2 required.
            conversion_window: Conversion window size. Default: 14.
            conversion_window_unit: Time unit. Default: ``"day"``.
            order: Step ordering mode. Default: ``"loose"``.
            from_date: Start date (YYYY-MM-DD) or None.
            to_date: End date (YYYY-MM-DD) or None.
            last: Relative time range in days. Default: 30.
            unit: Time aggregation unit. Default: ``"day"``.
            math: Aggregation function. Default:
                ``"conversion_rate_unique"``.
            math_property: Numeric property name for property-aggregation
                math types. Required for ``"average"``, ``"median"``,
                etc. Default: ``None``.
            group_by: Break down results by property or cohort
                membership. Accepts a string, ``GroupBy``,
                ``CohortBreakdown``, or list of any mix.
            where: Filter results by conditions.
            exclusions: Events to exclude between steps.
            holding_constant: Properties to hold constant.
            mode: Display mode. Default: ``"steps"``.
            reentry_mode: Funnel reentry mode controlling how users
                re-enter the funnel after conversion. One of
                ``"default"``, ``"basic"``, ``"aggressive"``, or
                ``"optimized"``. Default: ``None`` (server default).
            time_comparison: Optional period-over-period comparison.
                Use ``TimeComparison.relative("month")`` for previous
                month, etc. Default: ``None``.
            data_group_id: Optional data group ID for group-level
                analytics. Scopes the query to a specific data group.
                Default: ``None``.

        Returns:
            Bookmark params dict with ``sections`` and
            ``displayOptions`` keys.

        Raises:
            BookmarkValidationError: If arguments violate validation
                rules.

        Example:
            ```python
            ws = Workspace()

            # Inspect generated JSON
            params = ws.build_funnel_params(["Signup", "Purchase"])
            print(json.dumps(params, indent=2))

            # Save as a report (dashboard_id required)
            ws.create_bookmark(CreateBookmarkParams(
                name="Signup → Purchase Funnel",
                bookmark_type="funnels",
                params=params,
                dashboard_id=12345,
            ))
            ```
        """
        return self._resolve_and_build_funnel_params(
            steps=steps,
            conversion_window=conversion_window,
            conversion_window_unit=conversion_window_unit,
            order=order,
            math=math,
            math_property=math_property,
            from_date=from_date,
            to_date=to_date,
            last=last,
            unit=unit,
            group_by=group_by,
            where=where,
            exclusions=exclusions,
            holding_constant=holding_constant,
            mode=mode,
            reentry_mode=reentry_mode,
            time_comparison=time_comparison,
            data_group_id=data_group_id,
        )

    # =========================================================================
    # Retention Query (Phase 033)
    # =========================================================================

    def _build_retention_params(
        self,
        *,
        born_event: RetentionEvent,
        return_event: RetentionEvent,
        retention_unit: TimeUnit,
        alignment: RetentionAlignment,
        bucket_sizes: list[int] | None,
        math: RetentionMathType,
        from_date: str | None,
        to_date: str | None,
        last: int,
        unit: QueryTimeUnit,
        group_by: str
        | GroupBy
        | CohortBreakdown
        | list[str | GroupBy | CohortBreakdown]
        | None,
        where: Filter | list[Filter] | None,
        mode: RetentionMode,
        unbounded_mode: RetentionUnboundedMode | None = None,
        retention_cumulative: bool = False,
        time_comparison: TimeComparison | None = None,
        data_group_id: int | None = None,
    ) -> dict[str, Any]:
        """Build retention bookmark params dict from typed arguments.

        Generates the complete bookmark JSON structure expected by
        the Mixpanel insights query API for retention-type bookmarks.

        Args:
            born_event: Normalized RetentionEvent for born event.
            return_event: Normalized RetentionEvent for return event.
            retention_unit: Retention period unit.
            alignment: Retention alignment mode.
            bucket_sizes: Custom bucket sizes or None.
            math: Aggregation function.
            from_date: Start date (YYYY-MM-DD) or None.
            to_date: End date (YYYY-MM-DD) or None.
            last: Relative date range in days.
            unit: Time granularity.
            group_by: Breakdown specification.
            where: Filter conditions.
            mode: Display mode (curve, trends, table).
            unbounded_mode: Retention unbounded mode controlling how
                retention is counted in unbounded periods. Maps to
                ``retentionUnboundedMode`` in the behavior block.
                Default: ``None`` (omitted from bookmark).
            retention_cumulative: Whether to use cumulative retention
                counting. Maps to ``retentionCumulative`` in the
                measurement block. Default: ``False``.
            time_comparison: Optional period-over-period comparison.
                Adds ``timeComparison`` to ``displayOptions``.
            data_group_id: Optional data group ID for group-level
                analytics. Default: ``None``.

        Returns:
            Bookmark params dict ready for insights query API.
        """
        # Build behaviors array (exactly 2: born + return)
        behaviors: list[dict[str, Any]] = []
        for evt in [born_event, return_event]:
            behavior_entry: dict[str, Any] = {
                "type": "event",
                "id": None,
                "name": evt.event,
                "filters": [],
                "filtersDeterminer": evt.filters_combinator,
            }
            # Per-event filters
            if evt.filters:
                behavior_entry["filters"] = [build_filter_entry(f) for f in evt.filters]
            behaviors.append(behavior_entry)

        # Build behavior block
        behavior: dict[str, Any] = {
            "type": "retention",
            "resourceType": "events",
            "behaviors": behaviors,
            "retentionUnit": retention_unit,
            "retentionAlignmentType": alignment,
            "retentionCustomBucketSizes": list(bucket_sizes) if bucket_sizes else [],
            "filter": [],
        }
        if unbounded_mode is not None:
            behavior["retentionUnboundedMode"] = unbounded_mode

        # Build measurement
        measurement: dict[str, Any] = {
            "math": math,
        }
        if retention_cumulative:
            measurement["retentionCumulative"] = True

        # Build show clause
        show: list[dict[str, Any]] = [
            {
                "type": "metric",
                "behavior": behavior,
                "measurement": measurement,
            }
        ]

        # Build sections using shared builders
        time_section = build_time_section(
            from_date=from_date,
            to_date=to_date,
            last=last,
            unit=unit,
        )
        filter_section = patch_custom_property_filters_for_transform(
            build_filter_section(where)
        )
        group_section = build_group_section(group_by, data_group_id=data_group_id)

        # Chart type mapping
        chart_type_map = {
            "curve": "retention-curve",
            "trends": "line",
            "table": "table",
        }

        display_options: dict[str, Any] = {
            "chartType": chart_type_map.get(mode, "retention-curve"),
        }
        if time_comparison is not None:
            display_options["timeComparison"] = build_time_comparison(time_comparison)

        sections: dict[str, Any] = {
            "show": show,
            "time": time_section,
            "filter": filter_section,
            "group": group_section,
            "formula": [],
        }
        if data_group_id is not None:
            sections["dataGroupId"] = data_group_id

        return {
            "sections": sections,
            "displayOptions": display_options,
            "sorting": {
                "bar": {"colSortAttrs": [], "sortBy": "column"},
                "line": {
                    "sortBy": "column",
                    "colSortAttrs": [
                        {
                            "sortBy": "value",
                            "sortOrder": "desc",
                            "valueField": "averageValue",
                        }
                    ],
                },
                "table": {
                    "sortBy": "column",
                    "colSortAttrs": [
                        {
                            "sortBy": "value",
                            "sortOrder": "desc",
                            "valueField": "size",
                            "viewNLimit": 12,
                        }
                    ],
                },
            },
            "columnWidths": {"bar": {}},
        }

    # =========================================================================
    # FLOW QUERY (inline ad-hoc)
    # =========================================================================

    def _build_flow_params(
        self,
        *,
        steps: list[FlowStep],
        from_date: str | None,
        to_date: str | None,
        last: int,
        conversion_window: int,
        conversion_window_unit: str,
        count_type: str,
        cardinality: int,
        collapse_repeated: bool,
        hidden_events: list[str] | None,
        mode: str,
        where: Filter | list[Filter] | None = None,
        data_group_id: int | None = None,
        segments: str
        | GroupBy
        | CohortBreakdown
        | FrequencyBreakdown
        | list[str | GroupBy | CohortBreakdown | FrequencyBreakdown]
        | None = None,
        exclusions: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build a flat flow bookmark params dict from typed arguments.

        Constructs the Mixpanel bookmark JSON structure for flow queries.
        Flows use a flat dict format (no ``sections``/``displayOptions``
        wrapper) with ``steps``, ``date_range``, and display options at
        the top level.

        Args:
            steps: List of FlowStep objects defining anchor events.
            from_date: Start date (YYYY-MM-DD) or ``None``.
            to_date: End date (YYYY-MM-DD) or ``None``.
            last: Relative time range in days.
            conversion_window: Conversion window size.
            conversion_window_unit: Conversion window unit
                (``"day"``, ``"week"``, ``"month"``, ``"session"``).
            count_type: Counting method (``"unique"``, ``"total"``,
                ``"session"``).
            cardinality: Number of top paths to display.
            collapse_repeated: Whether to merge consecutive repeated
                events.
            hidden_events: Events to hide from the flow visualization.
            mode: Display mode (``"sankey"``, ``"paths"``, or ``"tree"``).
            where: Filter results by cohort membership or property
                conditions. Cohort filters (``Filter.in_cohort`` /
                ``Filter.not_in_cohort``) produce ``filter_by_cohort``.
                Property filters produce ``filter_by_event``.
                Default: ``None``.
            data_group_id: Optional data group ID for group-level
                analytics. Default: ``None``.
            segments: Segment (breakdown) specification for flow
                results. Accepts a string, ``GroupBy``, or list of
                strings/``GroupBy`` objects. Default: ``None``.
            exclusions: List of event names to exclude from flow
                paths. Default: ``None``.

        Returns:
            Flat bookmark params dict ready for API submission.

        Example:
            ```python
            params = ws._build_flow_params(
                steps=[FlowStep("Login")],
                from_date=None,
                to_date=None,
                last=30,
                conversion_window=7,
                conversion_window_unit="day",
                count_type="unique",
                cardinality=3,
                collapse_repeated=False,
                hidden_events=None,
                mode="sankey",
            )
            ```
        """
        # Build step dicts, including session_event when present
        step_dicts: list[dict[str, Any]] = []
        for step in steps:
            step_dict: dict[str, Any] = {
                "event": step.event,
                "step_label": step.label or step.event,
                "forward": step.forward if step.forward is not None else 0,
                "reverse": step.reverse if step.reverse is not None else 0,
                "bool_op": ("or" if step.filters_combinator == "any" else "and"),
                "property_filter_params_list": [
                    build_segfilter_entry(f) for f in (step.filters or [])
                ],
            }
            if step.session_event is not None:
                step_dict["session_event"] = step.session_event
            step_dicts.append(step_dict)

        params: dict[str, Any] = {
            "steps": step_dicts,
            "date_range": build_date_range(
                from_date=from_date, to_date=to_date, last=last
            ),
            "chartType": "top-paths" if mode == "paths" else "sankey",
            "flows_merge_type": (
                "tree" if mode == "tree" else "list" if mode == "paths" else "graph"
            ),
            "count_type": count_type,
            "cardinality_threshold": cardinality,
            "version": 2,
            "conversion_window": {
                "unit": conversion_window_unit,
                "value": conversion_window,
            },
            "anchor_position": 1,
            "collapse_repeated": collapse_repeated,
            "show_custom_events": True,
            "hidden_events": hidden_events or [],
            "exclusions": exclusions if exclusions is not None else [],
        }

        if data_group_id is not None:
            params["data_group_id"] = data_group_id

        # Add filters if present — route cohort vs property filters
        if where is not None:
            filter_list = where if isinstance(where, list) else [where]
            cohort_filters = [f for f in filter_list if f._property == "$cohorts"]
            property_filters = [f for f in filter_list if f._property != "$cohorts"]

            if cohort_filters:
                cohort_filter = build_flow_cohort_filter(cohort_filters)
                if cohort_filter is not None:
                    params["filter_by_cohort"] = cohort_filter

            if property_filters:
                params["filter_by_event"] = build_flow_property_filter(property_filters)

        # Add segments if present
        if segments is not None:
            params["segments"] = build_group_section(segments)

        return params

    def _resolve_and_build_flow_params(
        self,
        *,
        event: str | FlowStep | Sequence[str | FlowStep],
        forward: int,
        reverse: int,
        from_date: str | None,
        to_date: str | None,
        last: int,
        conversion_window: int,
        conversion_window_unit: FlowConversionWindowUnit,
        count_type: FlowCountType,
        cardinality: int,
        collapse_repeated: bool,
        hidden_events: list[str] | None,
        mode: FlowChartType,
        where: Filter | list[Filter] | None = None,
        data_group_id: int | None = None,
        segments: str
        | GroupBy
        | CohortBreakdown
        | FrequencyBreakdown
        | list[str | GroupBy | CohortBreakdown | FrequencyBreakdown]
        | None = None,
        exclusions: list[str] | None = None,
    ) -> dict[str, Any]:
        """Normalize, validate, and build flow bookmark params.

        Shared implementation for :meth:`query_flow` and
        :meth:`build_flow_params`. Handles normalization of string
        shorthand to ``FlowStep`` objects, argument validation (Layer 1),
        bookmark construction, and structure validation (Layer 2).

        Args:
            event: Event specification — a string, ``FlowStep``, or a
                list of strings/``FlowStep`` objects.
            forward: Default forward step count for steps without one.
            reverse: Default reverse step count for steps without one.
            from_date: Start date (YYYY-MM-DD) or ``None``.
            to_date: End date (YYYY-MM-DD) or ``None``.
            last: Relative time range in days.
            conversion_window: Conversion window size.
            conversion_window_unit: Conversion window unit.
            count_type: Counting method.
            cardinality: Number of top paths to display.
            collapse_repeated: Whether to merge consecutive repeated
                events.
            hidden_events: Events to hide from visualization.
            mode: Display mode.
            where: Filter results by cohort membership or property
                conditions. Cohort filters produce ``filter_by_cohort``,
                property filters produce ``filter_by_event``.
                Default: ``None``.
            data_group_id: Optional data group ID for group-level
                analytics. Default: ``None``.
            segments: Segment (breakdown) specification for flow
                results. Default: ``None``.
            exclusions: List of event names to exclude from flow
                paths. Default: ``None``.

        Returns:
            Validated flow bookmark params dict.

        Raises:
            BookmarkValidationError: If validation fails at any layer.
        """
        # Normalize input: str → FlowStep, single → list
        if isinstance(event, str):
            raw_steps: list[str | FlowStep] = [FlowStep(event)]
        elif isinstance(event, FlowStep):
            raw_steps = [event]
        else:
            raw_steps = list(event)

        steps: list[FlowStep] = [
            FlowStep(s) if isinstance(s, str) else s for s in raw_steps
        ]

        # Apply top-level forward/reverse defaults to steps where None
        steps = [
            FlowStep(
                event=s.event,
                forward=s.forward if s.forward is not None else forward,
                reverse=s.reverse if s.reverse is not None else reverse,
                label=s.label,
                filters=s.filters,
                filters_combinator=s.filters_combinator,
                session_event=s.session_event,
            )
            for s in steps
        ]

        # Layer 0.5: Per-step validation (FlowStep-level fields that
        # validate_flow_args cannot see — it only receives event names)
        step_errors: list[ValidationError] = []

        # Top-level forward/reverse type checks (must be int, not bool/float)
        for fname, fval in [("forward", forward), ("reverse", reverse)]:
            if isinstance(fval, bool) or not isinstance(fval, int):
                step_errors.append(
                    ValidationError(
                        path=fname,
                        message=(
                            f"{fname} must be an integer (got {type(fval).__name__})"
                        ),
                        code=f"FL_TYPE_{fname.upper()}",
                    )
                )

        for i, s in enumerate(steps):
            spath = f"steps[{i}]"
            # Per-step forward/reverse type + range checks
            step_errors.extend(_check_step_direction(s.forward, "forward", spath))
            step_errors.extend(_check_step_direction(s.reverse, "reverse", spath))
            # Per-step filters_combinator must be "all" or "any"
            if s.filters_combinator not in ("all", "any"):
                step_errors.append(
                    ValidationError(
                        path=f"{spath}.filters_combinator",
                        message=(
                            f"filters_combinator must be 'all' or 'any' "
                            f"(got {s.filters_combinator!r})"
                        ),
                        code="FL_INVALID_FILTERS_COMBINATOR",
                    )
                )
        # Per-step filter property validation
        for i, s in enumerate(steps):
            if s.filters:
                for fi, f in enumerate(s.filters):
                    if isinstance(f._property, str) and contains_control_chars(
                        f._property
                    ):
                        step_errors.append(
                            ValidationError(
                                path=f"steps[{i}].filters[{fi}]",
                                message=(
                                    f"Filter property name contains "
                                    f"control characters: {f._property!r}"
                                ),
                                code="FL_FILTER_CONTROL_CHAR",
                            )
                        )

        # hidden_events type validation
        if hidden_events is not None:
            for i, he in enumerate(hidden_events):
                if not isinstance(he, str):
                    step_errors.append(
                        ValidationError(
                            path=f"hidden_events[{i}]",
                            message=(
                                f"hidden_events values must be strings "
                                f"(got {type(he).__name__})"
                            ),
                            code="FL_INVALID_HIDDEN_EVENT_TYPE",
                        )
                    )

        if any(e.severity == "error" for e in step_errors):
            raise BookmarkValidationError(step_errors)

        # Default to_date to today when from_date is set alone, so the
        # absolute date isn't silently ignored by build_date_range().
        if from_date is not None and to_date is None:
            to_date = _date.today().isoformat()

        # Layer 1: Argument validation — use effective direction values
        # from normalized steps so per-step overrides aren't rejected by FL5.
        effective_forward = max(s.forward or 0 for s in steps)
        effective_reverse = max(s.reverse or 0 for s in steps)
        event_names = [s.event for s in steps]
        arg_errors = validate_flow_args(
            steps=event_names,
            forward=effective_forward,
            reverse=effective_reverse,
            count_type=count_type,
            mode=mode,
            cardinality=cardinality,
            conversion_window=conversion_window,
            conversion_window_unit=conversion_window_unit,
            from_date=from_date,
            to_date=to_date,
            last=last,
            data_group_id=data_group_id,
        )
        # CP1-CP6: Custom property validation for flow step filters
        arg_errors.extend(_scan_custom_properties(flow_steps=steps, where=where))
        if any(e.severity == "error" for e in arg_errors):
            raise BookmarkValidationError(arg_errors)

        # Build bookmark params
        params = self._build_flow_params(
            steps=steps,
            from_date=from_date,
            to_date=to_date,
            last=last,
            conversion_window=conversion_window,
            conversion_window_unit=conversion_window_unit,
            count_type=count_type,
            cardinality=cardinality,
            collapse_repeated=collapse_repeated,
            hidden_events=hidden_events,
            mode=mode,
            where=where,
            data_group_id=data_group_id,
            segments=segments,
            exclusions=exclusions,
        )

        # Layer 2: Bookmark structure validation
        bookmark_errors = validate_flow_bookmark(params)
        if any(e.severity == "error" for e in bookmark_errors):
            raise BookmarkValidationError(bookmark_errors)

        return params

    def query_flow(
        self,
        event: str | FlowStep | Sequence[str | FlowStep],
        *,
        forward: int = 3,
        reverse: int = 0,
        from_date: str | None = None,
        to_date: str | None = None,
        last: int = 30,
        conversion_window: int = 7,
        conversion_window_unit: Literal["day", "week", "month", "session"] = "day",
        count_type: Literal["unique", "total", "session"] = "unique",
        cardinality: int = 3,
        collapse_repeated: bool = False,
        hidden_events: list[str] | None = None,
        mode: Literal["sankey", "paths", "tree"] = "sankey",
        where: Filter | list[Filter] | None = None,
        data_group_id: int | None = None,
        segments: str
        | GroupBy
        | CohortBreakdown
        | FrequencyBreakdown
        | list[str | GroupBy | CohortBreakdown | FrequencyBreakdown]
        | None = None,
        exclusions: list[str] | None = None,
    ) -> FlowQueryResult:
        """Run a typed flow query against the Mixpanel API.

        Generates flow bookmark params from keyword arguments, POSTs
        them inline to ``/arb_funnels``, and returns a structured
        ``FlowQueryResult`` with lazy DataFrame conversion.

        Args:
            event: Event specification. Accepts an event name string,
                a ``FlowStep`` object for per-step configuration, or
                a list of strings/``FlowStep`` objects for multi-step
                flows.
            forward: Default number of forward steps to trace from
                each anchor event. Overridden by per-step values.
                Default: ``3``.
            reverse: Default number of reverse steps to trace from
                each anchor event. Overridden by per-step values.
                Default: ``0``.
            from_date: Start date (YYYY-MM-DD). If set, overrides
                ``last``.
            to_date: End date (YYYY-MM-DD). Requires ``from_date``.
            last: Relative time range in days. Default: 30.
            conversion_window: Conversion window size. Default: 7.
            conversion_window_unit: Conversion window unit.
                Default: ``"day"``.
            count_type: Counting method for flow analysis.
                Default: ``"unique"``.
            cardinality: Number of top paths to display.
                Default: ``3``.
            collapse_repeated: Whether to merge consecutive repeated
                events. Default: ``False``.
            hidden_events: Events to hide from the flow visualization.
                Default: ``None``.
            mode: Flow visualization mode. Default: ``"sankey"``.
            where: Filter results by cohort membership or property
                conditions. Cohort filters (``Filter.in_cohort`` /
                ``Filter.not_in_cohort``) produce ``filter_by_cohort``.
                Property filters (``Filter.equals``, etc.) produce
                ``filter_by_event``. Default: ``None``.
            data_group_id: Optional data group ID for group-level
                analytics. Scopes the query to a specific data group.
                Default: ``None``.
            segments: Segment (breakdown) specification for flow
                results. Accepts a string, ``GroupBy``, or list of
                strings/``GroupBy`` objects. Default: ``None``.
            exclusions: List of event names to exclude from flow
                paths. Default: ``None``.

        Returns:
            FlowQueryResult with steps, flows, breakdowns, and
            metadata.

        Raises:
            BookmarkValidationError: If arguments violate validation
                rules (before API call).
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials.
            QueryError: Invalid query parameters.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            ws = Workspace()

            # Simple flow query
            result = ws.query_flow("Login")
            print(result.overall_conversion_rate)

            # With configuration
            result = ws.query_flow(
                FlowStep("Login", forward=5, reverse=2),
                mode="paths",
                last=90,
            )
            print(result.df)

            # With property filter and segments
            result = ws.query_flow(
                "Login",
                where=Filter.equals("country", "US"),
                segments=GroupBy("platform"),
                exclusions=["Error Event"],
            )
            ```
        """
        params = self._resolve_and_build_flow_params(
            event=event,
            forward=forward,
            reverse=reverse,
            from_date=from_date,
            to_date=to_date,
            last=last,
            conversion_window=conversion_window,
            conversion_window_unit=conversion_window_unit,
            count_type=count_type,
            cardinality=cardinality,
            collapse_repeated=collapse_repeated,
            hidden_events=hidden_events,
            mode=mode,
            where=where,
            data_group_id=data_group_id,
            segments=segments,
            exclusions=exclusions,
        )

        return self._live_query_service.query_flow(
            bookmark_params=params,
            project_id=int(self._session.project.id),
            mode=mode,
        )

    def build_flow_params(
        self,
        event: str | FlowStep | Sequence[str | FlowStep],
        *,
        forward: int = 3,
        reverse: int = 0,
        from_date: str | None = None,
        to_date: str | None = None,
        last: int = 30,
        conversion_window: int = 7,
        conversion_window_unit: Literal["day", "week", "month", "session"] = "day",
        count_type: Literal["unique", "total", "session"] = "unique",
        cardinality: int = 3,
        collapse_repeated: bool = False,
        hidden_events: list[str] | None = None,
        mode: Literal["sankey", "paths", "tree"] = "sankey",
        where: Filter | list[Filter] | None = None,
        data_group_id: int | None = None,
        segments: str
        | GroupBy
        | CohortBreakdown
        | FrequencyBreakdown
        | list[str | GroupBy | CohortBreakdown | FrequencyBreakdown]
        | None = None,
        exclusions: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build validated flow bookmark params without executing.

        Accepts the same arguments as :meth:`query_flow` but returns
        the generated bookmark params ``dict`` instead of querying
        the API. Useful for debugging, inspecting generated JSON,
        persisting via :meth:`create_bookmark`, or testing.

        Args:
            event: Event specification. Accepts an event name string,
                a ``FlowStep`` object, or a list of strings/``FlowStep``
                objects.
            forward: Default forward step count. Default: ``3``.
            reverse: Default reverse step count. Default: ``0``.
            from_date: Start date (YYYY-MM-DD) or ``None``.
            to_date: End date (YYYY-MM-DD) or ``None``.
            last: Relative time range in days. Default: 30.
            conversion_window: Conversion window size. Default: 7.
            conversion_window_unit: Conversion window unit.
                Default: ``"day"``.
            count_type: Counting method. Default: ``"unique"``.
            cardinality: Number of top paths. Default: ``3``.
            collapse_repeated: Merge repeated events. Default: ``False``.
            hidden_events: Events to hide. Default: ``None``.
            mode: Display mode. Default: ``"sankey"``.
            where: Filter results by cohort membership or property
                conditions. Cohort filters produce ``filter_by_cohort``,
                property filters produce ``filter_by_event``.
                Default: ``None``.
            data_group_id: Optional data group ID for group-level
                analytics. Scopes the query to a specific data group.
                Default: ``None``.
            segments: Segment (breakdown) specification for flow
                results. Accepts a string, ``GroupBy``, or list of
                strings/``GroupBy`` objects. Default: ``None``.
            exclusions: List of event names to exclude from flow
                paths. Default: ``None``.

        Returns:
            Flat bookmark params dict with ``steps``, ``date_range``,
            ``chartType``, ``count_type``, and ``version`` keys.

        Raises:
            BookmarkValidationError: If arguments violate validation
                rules.

        Example:
            ```python
            ws = Workspace()

            # Inspect generated JSON
            params = ws.build_flow_params("Login")
            print(json.dumps(params, indent=2))

            # With segments and exclusions
            params = ws.build_flow_params(
                "Login",
                segments=GroupBy("country"),
                exclusions=["Error Event"],
                where=Filter.equals("platform", "iOS"),
            )
            ```
        """
        return self._resolve_and_build_flow_params(
            event=event,
            forward=forward,
            reverse=reverse,
            from_date=from_date,
            to_date=to_date,
            last=last,
            conversion_window=conversion_window,
            conversion_window_unit=conversion_window_unit,
            count_type=count_type,
            cardinality=cardinality,
            collapse_repeated=collapse_repeated,
            hidden_events=hidden_events,
            mode=mode,
            where=where,
            data_group_id=data_group_id,
            segments=segments,
            exclusions=exclusions,
        )

    # =========================================================================
    # RETENTION QUERY (inline ad-hoc)
    # =========================================================================

    def _resolve_and_build_retention_params(
        self,
        *,
        born_event: str | RetentionEvent,
        return_event: str | RetentionEvent,
        retention_unit: TimeUnit,
        alignment: RetentionAlignment,
        bucket_sizes: list[int] | None,
        math: RetentionMathType,
        from_date: str | None,
        to_date: str | None,
        last: int,
        unit: QueryTimeUnit,
        group_by: str
        | GroupBy
        | CohortBreakdown
        | list[str | GroupBy | CohortBreakdown]
        | None,
        where: Filter | list[Filter] | None,
        mode: RetentionMode,
        unbounded_mode: RetentionUnboundedMode | None = None,
        retention_cumulative: bool = False,
        time_comparison: TimeComparison | None = None,
        data_group_id: int | None = None,
    ) -> dict[str, Any]:
        """Normalize, validate, and build retention bookmark params.

        Shared implementation for :meth:`query_retention` and
        :meth:`build_retention_params`. Handles normalization of
        string shorthand to RetentionEvent objects, argument validation
        (Layer 1), bookmark construction, and structure validation
        (Layer 2).

        Args:
            born_event: Born event spec (string or RetentionEvent).
            return_event: Return event spec (string or RetentionEvent).
            retention_unit: Retention period unit.
            alignment: Retention alignment mode.
            bucket_sizes: Custom bucket sizes or None.
            math: Aggregation function.
            from_date: Start date (YYYY-MM-DD) or None.
            to_date: End date (YYYY-MM-DD) or None.
            last: Relative date range in days.
            unit: Time granularity.
            group_by: Breakdown specification.
            where: Filter conditions.
            mode: Display mode.
            unbounded_mode: Retention unbounded mode. Default: ``None``.
            retention_cumulative: Cumulative retention counting.
                Default: ``False``.
            time_comparison: Optional period-over-period comparison.
            data_group_id: Optional data group ID for group-level
                analytics. Default: ``None``.

        Returns:
            Validated bookmark params dict.

        Raises:
            BookmarkValidationError: If validation fails at any layer.
        """
        # Normalize events: str → RetentionEvent
        norm_born = (
            RetentionEvent(born_event) if isinstance(born_event, str) else born_event
        )
        norm_return = (
            RetentionEvent(return_event)
            if isinstance(return_event, str)
            else return_event
        )

        # Layer 1: Argument validation
        arg_errors = validate_retention_args(
            born_event=norm_born.event,
            return_event=norm_return.event,
            retention_unit=retention_unit,
            alignment=alignment,
            bucket_sizes=bucket_sizes,
            math=math,
            mode=mode,
            unit=unit,
            from_date=from_date,
            to_date=to_date,
            last=last,
            group_by=group_by,
            unbounded_mode=unbounded_mode,
            data_group_id=data_group_id,
        )
        # CP1-CP6: Custom property validation for where and event filters
        arg_errors.extend(
            _scan_custom_properties(
                where=where,
                retention_events=[norm_born, norm_return],
            )
        )
        if any(e.severity == "error" for e in arg_errors):
            raise BookmarkValidationError(arg_errors)

        # Build bookmark params
        params = self._build_retention_params(
            born_event=norm_born,
            return_event=norm_return,
            retention_unit=retention_unit,
            alignment=alignment,
            bucket_sizes=bucket_sizes,
            math=math,
            from_date=from_date,
            to_date=to_date,
            last=last,
            unit=unit,
            group_by=group_by,
            where=where,
            mode=mode,
            unbounded_mode=unbounded_mode,
            retention_cumulative=retention_cumulative,
            time_comparison=time_comparison,
            data_group_id=data_group_id,
        )

        # Layer 2: Bookmark structure validation
        bookmark_errors = validate_bookmark(params, bookmark_type="retention")
        if any(e.severity == "error" for e in bookmark_errors):
            raise BookmarkValidationError(bookmark_errors)

        return params

    def query_retention(
        self,
        born_event: str | RetentionEvent,
        return_event: str | RetentionEvent,
        *,
        retention_unit: TimeUnit = "week",
        alignment: RetentionAlignment = "birth",
        bucket_sizes: list[int] | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        last: int = 30,
        unit: QueryTimeUnit = "day",
        math: RetentionMathType = "retention_rate",
        group_by: str
        | GroupBy
        | CohortBreakdown
        | list[str | GroupBy | CohortBreakdown]
        | None = None,
        where: Filter | list[Filter] | None = None,
        mode: RetentionMode = "curve",
        unbounded_mode: RetentionUnboundedMode | None = None,
        retention_cumulative: bool = False,
        time_comparison: TimeComparison | None = None,
        data_group_id: int | None = None,
    ) -> RetentionQueryResult:
        """Run a typed retention query against the Mixpanel API.

        Generates retention bookmark params from keyword arguments, POSTs
        them inline to ``/api/query/insights``, and returns a structured
        RetentionQueryResult with lazy DataFrame conversion.

        Args:
            born_event: Event that defines cohort membership. Accepts
                an event name string or a ``RetentionEvent`` object
                for per-event filters.
            return_event: Event that defines return. Accepts an event
                name string or a ``RetentionEvent`` object.
            retention_unit: Retention period unit. Default: ``"week"``.
            alignment: Retention alignment mode. Default: ``"birth"``.
            bucket_sizes: Custom bucket sizes (positive ints in
                ascending order). Default: ``None`` (uniform buckets).
            from_date: Start date (YYYY-MM-DD). If set, overrides
                ``last``.
            to_date: End date (YYYY-MM-DD). Requires ``from_date``.
            last: Relative time range in days. Default: 30.
            unit: Time aggregation unit (``day``, ``week``, or
                ``month`` — ``hour`` is not supported for retention).
                Default: ``"day"``.
            math: Retention aggregation function. Default:
                ``"retention_rate"``.
            group_by: Break down results by property or cohort
                membership. Accepts a string, ``GroupBy``,
                ``CohortBreakdown``, or list of any mix.
            where: Filter results by conditions.
            mode: Result display mode. Default: ``"curve"``.
            unbounded_mode: Retention unbounded mode controlling how
                retention is counted in unbounded periods. One of
                ``"none"``, ``"carry_back"``, ``"carry_forward"``, or
                ``"consecutive_forward"``. Default: ``None``
                (server default).
            retention_cumulative: Whether to use cumulative retention
                counting. Default: ``False``.
            time_comparison: Optional period-over-period comparison.
                Use ``TimeComparison.relative("month")`` for previous
                month, etc. Default: ``None``.
            data_group_id: Optional data group ID for group-level
                analytics. Scopes the query to a specific data group.
                Default: ``None``.

        Returns:
            RetentionQueryResult with cohort data, DataFrame, and
            metadata.

        Raises:
            BookmarkValidationError: If arguments violate validation
                rules (before API call).
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials.
            QueryError: Invalid query parameters.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            ws = Workspace()

            # Simple retention query
            result = ws.query_retention("Signup", "Login")
            print(result.average)

            # With configuration
            result = ws.query_retention(
                "Signup", "Login",
                retention_unit="day",
                bucket_sizes=[1, 3, 7, 14, 30],
                last=90,
            )
            print(result.df)
            ```
        """
        params = self._resolve_and_build_retention_params(
            born_event=born_event,
            return_event=return_event,
            retention_unit=retention_unit,
            alignment=alignment,
            bucket_sizes=bucket_sizes,
            math=math,
            from_date=from_date,
            to_date=to_date,
            last=last,
            unit=unit,
            group_by=group_by,
            where=where,
            mode=mode,
            unbounded_mode=unbounded_mode,
            retention_cumulative=retention_cumulative,
            time_comparison=time_comparison,
            data_group_id=data_group_id,
        )

        return self._live_query_service.query_retention(
            bookmark_params=params,
            project_id=int(self._session.project.id),
        )

    def build_retention_params(
        self,
        born_event: str | RetentionEvent,
        return_event: str | RetentionEvent,
        *,
        retention_unit: TimeUnit = "week",
        alignment: RetentionAlignment = "birth",
        bucket_sizes: list[int] | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        last: int = 30,
        unit: QueryTimeUnit = "day",
        math: RetentionMathType = "retention_rate",
        group_by: str
        | GroupBy
        | CohortBreakdown
        | list[str | GroupBy | CohortBreakdown]
        | None = None,
        where: Filter | list[Filter] | None = None,
        mode: RetentionMode = "curve",
        unbounded_mode: RetentionUnboundedMode | None = None,
        retention_cumulative: bool = False,
        time_comparison: TimeComparison | None = None,
        data_group_id: int | None = None,
    ) -> dict[str, Any]:
        """Build validated retention bookmark params without executing.

        Accepts the same arguments as :meth:`query_retention` but returns
        the generated bookmark params ``dict`` (not a
        ``RetentionQueryResult``) instead of querying the API. Useful for
        debugging, inspecting generated JSON, persisting via
        :meth:`create_bookmark`, or testing.

        Args:
            born_event: Event that defines cohort membership.
            return_event: Event that defines return.
            retention_unit: Retention period unit. Default: ``"week"``.
            alignment: Retention alignment mode. Default: ``"birth"``.
            bucket_sizes: Custom bucket sizes. Default: ``None``.
            from_date: Start date (YYYY-MM-DD) or None.
            to_date: End date (YYYY-MM-DD) or None.
            last: Relative time range in days. Default: 30.
            unit: Time aggregation unit (``day``, ``week``, or
                ``month`` — ``hour`` is not supported for retention).
                Default: ``"day"``.
            math: Aggregation function. Default:
                ``"retention_rate"``.
            group_by: Break down results by property or cohort
                membership. Accepts a string, ``GroupBy``,
                ``CohortBreakdown``, or list of any mix.
            where: Filter results by conditions.
            mode: Display mode. Default: ``"curve"``.
            unbounded_mode: Retention unbounded mode controlling how
                retention is counted in unbounded periods. One of
                ``"none"``, ``"carry_back"``, ``"carry_forward"``, or
                ``"consecutive_forward"``. Default: ``None``
                (server default).
            retention_cumulative: Whether to use cumulative retention
                counting. Default: ``False``.
            time_comparison: Optional period-over-period comparison.
                Use ``TimeComparison.relative("month")`` for previous
                month, etc. Default: ``None``.
            data_group_id: Optional data group ID for group-level
                analytics. Scopes the query to a specific data group.
                Default: ``None``.

        Returns:
            Bookmark params dict with ``sections`` and
            ``displayOptions`` keys.

        Raises:
            BookmarkValidationError: If arguments violate validation
                rules.

        Example:
            ```python
            ws = Workspace()

            # Inspect generated JSON
            params = ws.build_retention_params("Signup", "Login")
            print(json.dumps(params, indent=2))

            # Save as a report (dashboard_id required)
            ws.create_bookmark(CreateBookmarkParams(
                name="Signup → Login Retention",
                bookmark_type="retention",
                params=params,
                dashboard_id=12345,
            ))
            ```
        """
        return self._resolve_and_build_retention_params(
            born_event=born_event,
            return_event=return_event,
            retention_unit=retention_unit,
            alignment=alignment,
            bucket_sizes=bucket_sizes,
            math=math,
            from_date=from_date,
            to_date=to_date,
            last=last,
            unit=unit,
            group_by=group_by,
            where=where,
            mode=mode,
            unbounded_mode=unbounded_mode,
            retention_cumulative=retention_cumulative,
            time_comparison=time_comparison,
            data_group_id=data_group_id,
        )

    # =========================================================================
    # ESCAPE HATCHES
    # =========================================================================

    @property
    def api(self) -> MixpanelAPIClient:
        """Direct access to the Mixpanel API client.

        Use this escape hatch for Mixpanel API operations not covered by the
        Workspace class. The client handles authentication automatically.

        The client provides:
            - ``request(method, url, **kwargs)``: Make authenticated requests
              to any Mixpanel API endpoint.
            - ``project_id``: The configured project ID for constructing URLs.
            - ``region``: The configured region ('us', 'eu', or 'in').

        Returns:
            The underlying MixpanelAPIClient.

        Raises:
            ConfigError: If API credentials not available.

        Example:
            Fetch event schema from the Lexicon Schemas API::

                import mixpanel_headless as mp
                from urllib.parse import quote

                ws = mp.Workspace()
                client = ws.api

                # Build the URL with proper encoding
                event_name = quote("Added To Cart", safe="")
                url = f"https://mixpanel.com/api/app/projects/{client.project_id}/schemas/event/{event_name}"

                # Make the authenticated request
                schema = client.request("GET", url)
                print(schema)
        """
        return self._require_api_client()

    # =========================================================================
    # DASHBOARD CRUD (Phase 024)
    # =========================================================================

    def list_dashboards(self, *, ids: list[int] | None = None) -> list[Dashboard]:
        """List dashboards for the current project/workspace.

        Retrieves all dashboards visible to the authenticated user,
        optionally filtered by specific IDs.

        Args:
            ids: Optional list of dashboard IDs to filter by.

        Returns:
            List of ``Dashboard`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            dashboards = ws.list_dashboards()
            for d in dashboards:
                print(f"{d.title} (id={d.id})")
            ```
        """
        client = self._require_api_client()
        raw = client.list_dashboards(ids=ids)
        return [Dashboard.model_validate(d) for d in raw]

    def create_dashboard(self, params: CreateDashboardParams) -> Dashboard:
        """Create a new dashboard.

        Args:
            params: Dashboard creation parameters.

        Returns:
            The newly created ``Dashboard``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid parameters (400, 422).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            dashboard = ws.create_dashboard(
                CreateDashboardParams(title="Q1 Metrics")
            )
            ```
        """
        client = self._require_api_client()
        raw = client.create_dashboard(params.model_dump(exclude_none=True))
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for create_dashboard",
            )
        return Dashboard.model_validate(raw)

    def get_dashboard(self, dashboard_id: int) -> Dashboard:
        """Get a single dashboard by ID.

        Args:
            dashboard_id: Dashboard identifier.

        Returns:
            The ``Dashboard`` object.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            dashboard = ws.get_dashboard(12345)
            ```
        """
        client = self._require_api_client()
        raw = client.get_dashboard(dashboard_id)
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for get_dashboard",
            )
        return Dashboard.model_validate(raw)

    def update_dashboard(
        self, dashboard_id: int, params: UpdateDashboardParams
    ) -> Dashboard:
        """Update an existing dashboard.

        Args:
            dashboard_id: Dashboard identifier.
            params: Fields to update.

        Returns:
            The updated ``Dashboard``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found or invalid params (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            updated = ws.update_dashboard(
                12345, UpdateDashboardParams(title="New Title")
            )
            ```
        """
        client = self._require_api_client()
        raw = client.update_dashboard(
            dashboard_id, params.model_dump(exclude_none=True)
        )
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for update_dashboard",
            )
        return Dashboard.model_validate(raw)

    def delete_dashboard(self, dashboard_id: int) -> None:
        """Delete a dashboard.

        Args:
            dashboard_id: Dashboard identifier.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.delete_dashboard(12345)
            ```
        """
        client = self._require_api_client()
        client.delete_dashboard(dashboard_id)

    def bulk_delete_dashboards(self, ids: list[int]) -> None:
        """Delete multiple dashboards.

        Args:
            ids: List of dashboard IDs to delete.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: One or more IDs not found (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.bulk_delete_dashboards([1, 2, 3])
            ```
        """
        client = self._require_api_client()
        client.bulk_delete_dashboards(ids)

    # =========================================================================
    # DASHBOARD ADVANCED OPERATIONS (Phase 024)
    # =========================================================================

    def favorite_dashboard(self, dashboard_id: int) -> None:
        """Favorite a dashboard.

        Args:
            dashboard_id: Dashboard identifier.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.favorite_dashboard(12345)
            ```
        """
        client = self._require_api_client()
        client.favorite_dashboard(dashboard_id)

    def unfavorite_dashboard(self, dashboard_id: int) -> None:
        """Unfavorite a dashboard.

        Args:
            dashboard_id: Dashboard identifier.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.unfavorite_dashboard(12345)
            ```
        """
        client = self._require_api_client()
        client.unfavorite_dashboard(dashboard_id)

    def pin_dashboard(self, dashboard_id: int) -> None:
        """Pin a dashboard.

        Args:
            dashboard_id: Dashboard identifier.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.pin_dashboard(12345)
            ```
        """
        client = self._require_api_client()
        client.pin_dashboard(dashboard_id)

    def unpin_dashboard(self, dashboard_id: int) -> None:
        """Unpin a dashboard.

        Args:
            dashboard_id: Dashboard identifier.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.unpin_dashboard(12345)
            ```
        """
        client = self._require_api_client()
        client.unpin_dashboard(dashboard_id)

    def remove_report_from_dashboard(
        self, dashboard_id: int, bookmark_id: int
    ) -> Dashboard:
        """Remove a report from a dashboard.

        Args:
            dashboard_id: Dashboard identifier.
            bookmark_id: Bookmark/report identifier to remove.

        Returns:
            The updated ``Dashboard``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard or bookmark not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            updated = ws.remove_report_from_dashboard(12345, 42)
            ```
        """
        client = self._require_api_client()
        raw = client.remove_report_from_dashboard(dashboard_id, bookmark_id)
        return Dashboard.model_validate(raw)

    def add_report_to_dashboard(self, dashboard_id: int, bookmark_id: int) -> Dashboard:
        """Add a report to a dashboard.

        Clones the specified bookmark onto the dashboard. The cloned report
        appears as a new card in the dashboard layout.

        Args:
            dashboard_id: Dashboard identifier.
            bookmark_id: Bookmark/report identifier to add.

        Returns:
            The updated ``Dashboard``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard or bookmark not found (404).
            ServerError: Server-side errors (5xx).
            MixpanelHeadlessError: If the API response is not a valid dashboard dict.

        Example:
            ```python
            ws = Workspace()
            updated = ws.add_report_to_dashboard(12345, 42)
            ```
        """
        client = self._require_api_client()
        raw = client.add_report_to_dashboard(dashboard_id, bookmark_id)
        if not isinstance(raw, dict) or "id" not in raw:
            raise MixpanelHeadlessError(
                "Unexpected response from add_report_to_dashboard: "
                f"expected dashboard dict with 'id', got {raw!r}",
            )
        return Dashboard.model_validate(raw)

    def list_blueprint_templates(
        self, *, include_reports: bool = False
    ) -> list[BlueprintTemplate]:
        """List available dashboard blueprint templates.

        Args:
            include_reports: Whether to include report details.

        Returns:
            List of ``BlueprintTemplate`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            templates = ws.list_blueprint_templates()
            ```
        """
        client = self._require_api_client()
        raw = client.list_blueprint_templates(include_reports=include_reports)
        return [BlueprintTemplate.model_validate(t) for t in raw]

    def create_blueprint(self, template_type: str) -> Dashboard:
        """Create a dashboard from a blueprint template.

        Args:
            template_type: Blueprint template type identifier.

        Returns:
            The newly created ``Dashboard``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid template type (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            dashboard = ws.create_blueprint("onboarding")
            ```
        """
        client = self._require_api_client()
        raw = client.create_blueprint(template_type)
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for create_blueprint",
            )
        return Dashboard.model_validate(raw)

    def get_blueprint_config(self, dashboard_id: int) -> BlueprintConfig:
        """Get the blueprint configuration for a dashboard.

        Args:
            dashboard_id: Dashboard identifier.

        Returns:
            ``BlueprintConfig`` with template variables.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            config = ws.get_blueprint_config(12345)
            ```
        """
        client = self._require_api_client()
        raw = client.get_blueprint_config(dashboard_id)
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for get_blueprint_config",
            )
        return BlueprintConfig.model_validate(raw)

    def update_blueprint_cohorts(self, cohorts: list[dict[str, Any]]) -> None:
        """Update cohorts for blueprint configuration.

        Args:
            cohorts: List of cohort configuration dicts.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid cohort configuration (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.update_blueprint_cohorts([{"id": 1, "name": "Test"}])
            ```
        """
        client = self._require_api_client()
        client.update_blueprint_cohorts(cohorts)

    def finalize_blueprint(self, params: BlueprintFinishParams) -> Dashboard:
        """Finalize a blueprint dashboard with cards.

        Args:
            params: Blueprint finalization parameters.

        Returns:
            The finalized ``Dashboard``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid parameters (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            dashboard = ws.finalize_blueprint(
                BlueprintFinishParams(
                    dashboard_id=1,
                    cards=[BlueprintCard(card_type="report", bookmark_id=42)],
                )
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True, by_alias=True)
        raw = client.finalize_blueprint(body)
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for finalize_blueprint",
            )
        return Dashboard.model_validate(raw)

    def create_rca_dashboard(self, params: CreateRcaDashboardParams) -> Dashboard:
        """Create an RCA (Root Cause Analysis) dashboard.

        Args:
            params: RCA dashboard parameters.

        Returns:
            The newly created ``Dashboard``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid parameters (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            dashboard = ws.create_rca_dashboard(
                CreateRcaDashboardParams(
                    rca_source_id=42,
                    rca_source_data=RcaSourceData(source_type="anomaly"),
                )
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True, by_alias=True)
        raw = client.create_rca_dashboard(body)
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for create_rca_dashboard",
            )
        return Dashboard.model_validate(raw)

    def get_bookmark_dashboard_ids(self, bookmark_id: int) -> list[int]:
        """Get dashboard IDs containing a bookmark/report.

        Args:
            bookmark_id: Bookmark identifier.

        Returns:
            List of dashboard IDs.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Bookmark not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            dash_ids = ws.get_bookmark_dashboard_ids(42)
            ```
        """
        client = self._require_api_client()
        return client.get_bookmark_dashboard_ids(bookmark_id)

    def get_dashboard_erf(self, dashboard_id: int) -> dict[str, Any]:
        """Get ERF data for a dashboard.

        Args:
            dashboard_id: Dashboard identifier.

        Returns:
            Dict with ERF metrics data.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            erf = ws.get_dashboard_erf(12345)
            ```
        """
        client = self._require_api_client()
        return client.get_dashboard_erf(dashboard_id)

    def update_report_link(
        self,
        dashboard_id: int,
        report_link_id: int,
        params: UpdateReportLinkParams,
    ) -> None:
        """Update a report link on a dashboard.

        Args:
            dashboard_id: Dashboard identifier.
            report_link_id: Report link identifier.
            params: Update parameters.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard or link not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.update_report_link(
                12345, 42, UpdateReportLinkParams(link_type="embedded")
            )
            ```
        """
        client = self._require_api_client()
        client.update_report_link(
            dashboard_id,
            report_link_id,
            params.model_dump(by_alias=True, exclude_none=True),
        )

    def update_text_card(
        self,
        dashboard_id: int,
        text_card_id: int,
        params: UpdateTextCardParams,
    ) -> None:
        """Update a text card on a dashboard.

        Args:
            dashboard_id: Dashboard identifier.
            text_card_id: Text card identifier.
            params: Update parameters.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Dashboard or text card not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.update_text_card(
                12345, 99, UpdateTextCardParams(markdown="# Hello")
            )
            ```
        """
        client = self._require_api_client()
        client.update_text_card(
            dashboard_id,
            text_card_id,
            params.model_dump(exclude_none=True),
        )

    # =========================================================================
    # BOOKMARK/REPORT CRUD (Phase 024)
    # =========================================================================

    def list_bookmarks_v2(
        self,
        *,
        bookmark_type: BookmarkType | None = None,
        ids: list[int] | None = None,
    ) -> list[Bookmark]:
        """List bookmarks/reports via the App API v2 endpoint.

        Args:
            bookmark_type: Optional report type filter (e.g., ``"funnels"``).
            ids: Optional list of bookmark IDs to filter by.

        Returns:
            List of ``Bookmark`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            reports = ws.list_bookmarks_v2(bookmark_type="funnels")
            for r in reports:
                print(f"{r.name} ({r.bookmark_type})")
            ```
        """
        client = self._require_api_client()
        raw = client.list_bookmarks_v2(bookmark_type=bookmark_type, ids=ids)
        return [Bookmark.model_validate(b) for b in raw]

    @staticmethod
    def _validate_bookmark_params_schema(
        raw: dict[str, Any],
        bookmark_type: str | None,
        *,
        partial: bool = False,
    ) -> list[ValidationError]:
        """Validate a bookmark ``params`` dict against the canonical schema.

        Helper shared by ``create_bookmark`` and ``update_bookmark``.
        Two modes:

        - ``partial=False`` (create-path): when ``bookmark_type`` resolves
          to a canonical root model (insights/funnels/retention/flows),
          validates the entire ``raw`` (minus ``sorting``) against that
          model. Required-field rules apply.
        - ``partial=True`` (update-path): validates each present top-level
          key in ``raw`` against its canonical sub-model. Missing keys
          are intentional and not flagged — partial updates legitimately
          omit fields.

        ``sorting`` is always routed through ``validate_sorting_block``
        (regardless of mode) so the ``S4_UNKNOWN_CHART_TYPE`` warning
        surfaces consistently. Pydantic alone would emit a hard
        ``S3_UNKNOWN_FIELD`` error for unknown chart-type keys.

        Args:
            raw: The bookmark ``params`` dict to validate.
            bookmark_type: The bookmark type (one of ``"insights"``,
                ``"funnels"``, ``"retention"``, ``"flows"``, ``"user"``)
                or ``None`` when unknown (e.g. on update calls).
            partial: When True, run per-key sub-model validation; when
                False (default), run full root-model validation.

        Returns:
            List of ``ValidationError`` instances (errors and warnings).
            Empty if the payload validates cleanly.
        """
        errors: list[ValidationError] = []

        # Sorting is always validated via the wrapper so unknown chart
        # types surface as S4 warnings, not S3 errors. Strip from raw
        # so root/sub-model validation doesn't double-validate it.
        sorting = raw.get("sorting")
        if sorting is not None:
            errors.extend(validate_sorting_block(sorting))
        raw_no_sorting = {k: v for k, v in raw.items() if k != "sorting"}

        if not partial and bookmark_type is not None:
            root = get_root_model_for_bookmark_type(bookmark_type)
            if root is not None:
                errors.extend(validate_with_pydantic(root, raw_no_sorting))
                return errors

        # Partial mode (or unknown root): per-key sub-model validation.
        for key, model in PARTIAL_UPDATE_SUB_MODELS.items():
            if key in raw_no_sorting:
                errors.extend(
                    validate_with_pydantic(model, raw_no_sorting[key], path_prefix=key)
                )
        return errors

    def create_bookmark(self, params: CreateBookmarkParams) -> Bookmark:
        """Create a new bookmark (saved report).

        Args:
            params: Bookmark creation parameters.  ``dashboard_id``
                is required by the Mixpanel v2 API.

        Returns:
            The newly created ``Bookmark``.

        Raises:
            MixpanelHeadlessError: If ``params.dashboard_id`` is ``None``
                (required by the Mixpanel v2 API).
            BookmarkValidationError: If ``params.params`` fails
                client-side schema validation (mirrors Mixpanel's
                canonical Pydantic schema; raised before the API call).
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid parameters (400, 422).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            dashboard = ws.create_dashboard(
                CreateDashboardParams(title="My Dashboard")
            )
            report = ws.create_bookmark(CreateBookmarkParams(
                name="Signup Funnel",
                bookmark_type="funnels",
                params={"events": [{"event": "Signup"}]},
                dashboard_id=dashboard.id,
            ))
            ```
        """
        if params.dashboard_id is None:
            raise MixpanelHeadlessError(
                "dashboard_id is required when creating a bookmark. "
                "The Mixpanel v2 API requires every bookmark to be "
                "associated with a dashboard. Create a dashboard first "
                "with create_dashboard(), then pass its ID here.",
            )

        # Full Pydantic-schema validation against the canonical mirror
        # of Mixpanel's bookmark schema — catches malformed shapes
        # client-side before they're persisted with garbage that only
        # surfaces later at chart-render time.
        schema_errors = self._validate_bookmark_params_schema(
            params.params, params.bookmark_type
        )
        if any(e.severity == "error" for e in schema_errors):
            raise BookmarkValidationError(schema_errors)
        for w in (e for e in schema_errors if e.severity == "warning"):
            logger.warning(
                "create_bookmark validation warning: %s [%s]",
                w.message,
                w.code,
            )

        client = self._require_api_client()
        raw = client.create_bookmark(
            params.model_dump(by_alias=True, exclude_none=True)
        )
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for create_bookmark",
            )
        bookmark = Bookmark.model_validate(raw)

        # The v2 create endpoint associates the bookmark with the
        # dashboard in the database, but does NOT add it to the
        # dashboard's visual layout — that requires a separate
        # PATCH call.
        self.add_report_to_dashboard(params.dashboard_id, bookmark.id)

        return bookmark

    def get_bookmark(self, bookmark_id: int) -> Bookmark:
        """Get a single bookmark by ID.

        Args:
            bookmark_id: Bookmark identifier.

        Returns:
            The ``Bookmark`` object.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Bookmark not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            report = ws.get_bookmark(12345)
            ```
        """
        client = self._require_api_client()
        raw = client.get_bookmark(bookmark_id)
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for get_bookmark",
            )
        return Bookmark.model_validate(raw)

    def update_bookmark(
        self, bookmark_id: int, params: UpdateBookmarkParams
    ) -> Bookmark:
        """Update an existing bookmark.

        Args:
            bookmark_id: Bookmark identifier.
            params: Fields to update.

        Returns:
            The updated ``Bookmark``.

        Raises:
            BookmarkValidationError: If ``params.params`` (when supplied)
                fails partial-mode client-side schema validation
                (mirrors Mixpanel's canonical schema for the keys that
                ARE present; raised before the API call).
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Bookmark not found or invalid params (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            updated = ws.update_bookmark(
                12345, UpdateBookmarkParams(name="Renamed")
            )
            ```
        """
        # Partial-aware Pydantic validation: each present top-level key
        # in ``params.params`` is checked against its canonical sub-model.
        # Missing top-level keys are intentional (partial updates) and
        # not flagged. Catches the same malformations the create-path
        # catches on the keys that ARE present (chartType typos,
        # missing colSortAttrs, extra segmentation field, etc.).
        if params.params is not None:
            schema_errors = self._validate_bookmark_params_schema(
                params.params, bookmark_type=None, partial=True
            )
            if any(e.severity == "error" for e in schema_errors):
                raise BookmarkValidationError(schema_errors)
            for w in (e for e in schema_errors if e.severity == "warning"):
                logger.warning(
                    "update_bookmark validation warning: %s [%s]",
                    w.message,
                    w.code,
                )

        client = self._require_api_client()
        raw = client.update_bookmark(bookmark_id, params.model_dump(exclude_none=True))
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for update_bookmark",
            )
        return Bookmark.model_validate(raw)

    def delete_bookmark(self, bookmark_id: int) -> None:
        """Delete a bookmark.

        Args:
            bookmark_id: Bookmark identifier.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Bookmark not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.delete_bookmark(12345)
            ```
        """
        client = self._require_api_client()
        client.delete_bookmark(bookmark_id)

    def bulk_delete_bookmarks(self, ids: list[int]) -> None:
        """Delete multiple bookmarks.

        Args:
            ids: List of bookmark IDs to delete.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: One or more IDs not found (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.bulk_delete_bookmarks([1, 2, 3])
            ```
        """
        client = self._require_api_client()
        client.bulk_delete_bookmarks(ids)

    def bulk_update_bookmarks(self, entries: list[BulkUpdateBookmarkEntry]) -> None:
        """Update multiple bookmarks.

        Args:
            entries: List of bookmark update entries.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid entries or IDs not found (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.bulk_update_bookmarks([
                BulkUpdateBookmarkEntry(id=1, name="Renamed"),
            ])
            ```
        """
        client = self._require_api_client()
        client.bulk_update_bookmarks([e.model_dump(exclude_none=True) for e in entries])

    def bookmark_linked_dashboard_ids(self, bookmark_id: int) -> list[int]:
        """Get dashboard IDs linked to a bookmark.

        Args:
            bookmark_id: Bookmark identifier.

        Returns:
            List of dashboard IDs.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Bookmark not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            dash_ids = ws.bookmark_linked_dashboard_ids(42)
            ```
        """
        client = self._require_api_client()
        return client.bookmark_linked_dashboard_ids(bookmark_id)

    def get_bookmark_history(
        self,
        bookmark_id: int,
        *,
        cursor: str | None = None,
        page_size: int | None = None,
    ) -> BookmarkHistoryResponse:
        """Get the change history for a bookmark.

        Args:
            bookmark_id: Bookmark identifier.
            cursor: Opaque pagination cursor.
            page_size: Maximum entries per page.

        Returns:
            ``BookmarkHistoryResponse`` with results and pagination.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Bookmark not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            history = ws.get_bookmark_history(12345, page_size=10)
            ```
        """
        client = self._require_api_client()
        raw = client.get_bookmark_history(
            bookmark_id, cursor=cursor, page_size=page_size
        )
        return BookmarkHistoryResponse.model_validate(raw)

    # =========================================================================
    # COHORT CRUD (Phase 024)
    # =========================================================================

    def list_cohorts_full(
        self,
        *,
        data_group_id: str | None = None,
        ids: list[int] | None = None,
    ) -> list[Cohort]:
        """List cohorts via the App API (full detail).

        Unlike ``cohorts()`` which uses the discovery endpoint, this method
        uses the App API and returns full ``Cohort`` objects with all metadata.

        Args:
            data_group_id: Optional data group filter.
            ids: Optional list of cohort IDs to filter by.

        Returns:
            List of ``Cohort`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            cohorts = ws.list_cohorts_full()
            for c in cohorts:
                print(f"{c.name} ({c.count} users)")
            ```
        """
        client = self._require_api_client()
        raw = client.list_cohorts_app(data_group_id=data_group_id, ids=ids)
        return [Cohort.model_validate(c) for c in raw]

    def get_cohort(self, cohort_id: int) -> Cohort:
        """Get a single cohort by ID via the App API.

        Args:
            cohort_id: Cohort identifier.

        Returns:
            The ``Cohort`` object.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Cohort not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            cohort = ws.get_cohort(12345)
            ```
        """
        client = self._require_api_client()
        raw = client.get_cohort(cohort_id)
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for get_cohort",
            )
        return Cohort.model_validate(raw)

    def create_cohort(self, params: CreateCohortParams) -> Cohort:
        """Create a new cohort.

        Args:
            params: Cohort creation parameters.

        Returns:
            The newly created ``Cohort``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid parameters (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            cohort = ws.create_cohort(
                CreateCohortParams(name="Power Users")
            )
            ```
        """
        client = self._require_api_client()
        raw = client.create_cohort(params.model_dump(exclude_none=True))
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for create_cohort",
            )
        return Cohort.model_validate(raw)

    def update_cohort(self, cohort_id: int, params: UpdateCohortParams) -> Cohort:
        """Update an existing cohort.

        Args:
            cohort_id: Cohort identifier.
            params: Fields to update.

        Returns:
            The updated ``Cohort``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Cohort not found or invalid params (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            updated = ws.update_cohort(
                12345, UpdateCohortParams(name="Renamed")
            )
            ```
        """
        client = self._require_api_client()
        raw = client.update_cohort(cohort_id, params.model_dump(exclude_none=True))
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for update_cohort",
            )
        return Cohort.model_validate(raw)

    def delete_cohort(self, cohort_id: int) -> None:
        """Delete a cohort.

        Args:
            cohort_id: Cohort identifier.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Cohort not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.delete_cohort(12345)
            ```
        """
        client = self._require_api_client()
        client.delete_cohort(cohort_id)

    def bulk_delete_cohorts(self, ids: list[int]) -> None:
        """Delete multiple cohorts.

        Args:
            ids: List of cohort IDs to delete.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: One or more IDs not found (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.bulk_delete_cohorts([1, 2, 3])
            ```
        """
        client = self._require_api_client()
        client.bulk_delete_cohorts(ids)

    def bulk_update_cohorts(self, entries: list[BulkUpdateCohortEntry]) -> None:
        """Update multiple cohorts.

        Args:
            entries: List of cohort update entries.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid entries or IDs not found (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.bulk_update_cohorts([
                BulkUpdateCohortEntry(id=1, name="Renamed"),
            ])
            ```
        """
        client = self._require_api_client()
        client.bulk_update_cohorts([e.model_dump(exclude_none=True) for e in entries])

    # =========================================================================
    # FEATURE FLAG CRUD (Phase 025)
    # =========================================================================

    def list_feature_flags(
        self, *, include_archived: bool = False
    ) -> list[FeatureFlag]:
        """List feature flags for the current project/workspace.

        Args:
            include_archived: When True, include archived flags.

        Returns:
            List of ``FeatureFlag`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            flags = ws.list_feature_flags()
            for f in flags:
                print(f"{f.name} ({f.key})")
            ```
        """
        client = self._require_api_client()
        raw = client.list_feature_flags(include_archived=include_archived)
        return [FeatureFlag.model_validate(f) for f in raw]

    def create_feature_flag(self, params: CreateFeatureFlagParams) -> FeatureFlag:
        """Create a new feature flag.

        Args:
            params: Flag creation parameters.

        Returns:
            The newly created ``FeatureFlag``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Duplicate key or invalid parameters (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            flag = ws.create_feature_flag(
                CreateFeatureFlagParams(name="Dark Mode", key="dark_mode")
            )
            ```
        """
        client = self._require_api_client()
        raw = client.create_feature_flag(params.model_dump(exclude_none=True))
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for create_feature_flag",
            )
        return FeatureFlag.model_validate(raw)

    def get_feature_flag(self, flag_id: str) -> FeatureFlag:
        """Get a single feature flag by ID.

        Args:
            flag_id: Feature flag UUID.

        Returns:
            The ``FeatureFlag`` object.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            flag = ws.get_feature_flag("abc-123-uuid")
            ```
        """
        client = self._require_api_client()
        raw = client.get_feature_flag(flag_id)
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for get_feature_flag",
            )
        return FeatureFlag.model_validate(raw)

    def update_feature_flag(
        self, flag_id: str, params: UpdateFeatureFlagParams
    ) -> FeatureFlag:
        """Update a feature flag (full replacement, PUT semantics).

        Args:
            flag_id: Feature flag UUID.
            params: Complete flag configuration.

        Returns:
            The updated ``FeatureFlag``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found or invalid params (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            updated = ws.update_feature_flag(
                "abc-123", UpdateFeatureFlagParams(
                    name="X", key="x",
                    status=FeatureFlagStatus.ENABLED,
                    ruleset={"variants": []},
                )
            )
            ```
        """
        client = self._require_api_client()
        raw = client.update_feature_flag(flag_id, params.model_dump(exclude_none=True))
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for update_feature_flag",
            )
        return FeatureFlag.model_validate(raw)

    def delete_feature_flag(self, flag_id: str) -> None:
        """Delete a feature flag.

        Args:
            flag_id: Feature flag UUID.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.delete_feature_flag("abc-123-uuid")
            ```
        """
        client = self._require_api_client()
        client.delete_feature_flag(flag_id)

    # =========================================================================
    # FEATURE FLAG LIFECYCLE (Phase 025)
    # =========================================================================

    def archive_feature_flag(self, flag_id: str) -> None:
        """Archive a feature flag (soft-delete).

        Args:
            flag_id: Feature flag UUID.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.archive_feature_flag("abc-123-uuid")
            ```
        """
        client = self._require_api_client()
        client.archive_feature_flag(flag_id)

    def restore_feature_flag(self, flag_id: str) -> FeatureFlag:
        """Restore an archived feature flag.

        Args:
            flag_id: Feature flag UUID.

        Returns:
            The restored ``FeatureFlag``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            restored = ws.restore_feature_flag("abc-123-uuid")
            ```
        """
        client = self._require_api_client()
        raw = client.restore_feature_flag(flag_id)
        return FeatureFlag.model_validate(raw)

    def duplicate_feature_flag(self, flag_id: str) -> FeatureFlag:
        """Duplicate a feature flag.

        Args:
            flag_id: Feature flag UUID.

        Returns:
            The newly created duplicate ``FeatureFlag``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            dup = ws.duplicate_feature_flag("abc-123-uuid")
            ```
        """
        client = self._require_api_client()
        raw = client.duplicate_feature_flag(flag_id)
        return FeatureFlag.model_validate(raw)

    # =========================================================================
    # FEATURE FLAG OPERATIONS (Phase 025)
    # =========================================================================

    def set_flag_test_users(self, flag_id: str, params: SetTestUsersParams) -> None:
        """Set test user variant overrides for a feature flag.

        Args:
            flag_id: Feature flag UUID.
            params: Test user mapping.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404) or invalid payload (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.set_flag_test_users(
                "abc-123",
                SetTestUsersParams(users={"on": "user-1"}),
            )
            ```
        """
        client = self._require_api_client()
        client.set_flag_test_users(flag_id, params.model_dump())

    def get_flag_history(
        self,
        flag_id: str,
        *,
        page: str | None = None,
        page_size: int | None = None,
    ) -> FlagHistoryResponse:
        """Get paginated change history for a feature flag.

        Args:
            flag_id: Feature flag UUID.
            page: Pagination cursor.
            page_size: Results per page.

        Returns:
            ``FlagHistoryResponse`` with events and count.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Flag not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            history = ws.get_flag_history("abc-123", page_size=50)
            ```
        """
        client = self._require_api_client()
        query_params: dict[str, str] = {}
        if page is not None:
            query_params["page"] = page
        if page_size is not None:
            query_params["page_size"] = str(page_size)
        raw = client.get_flag_history(
            flag_id, params=query_params if query_params else None
        )
        return FlagHistoryResponse.model_validate(raw)

    def get_flag_limits(self) -> FlagLimitsResponse:
        """Get account-level feature flag limits and usage.

        Returns:
            ``FlagLimitsResponse`` with limit, usage, trial, and contract status.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            limits = ws.get_flag_limits()
            print(f"{limits.current_usage}/{limits.limit}")
            ```
        """
        client = self._require_api_client()
        raw = client.get_flag_limits()
        return FlagLimitsResponse.model_validate(raw)

    # =========================================================================
    # EXPERIMENT CRUD (Phase 025)
    # =========================================================================

    def list_experiments(self, *, include_archived: bool = False) -> list[Experiment]:
        """List experiments for the current project.

        Args:
            include_archived: When True, include archived experiments.

        Returns:
            List of ``Experiment`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            experiments = ws.list_experiments()
            for e in experiments:
                print(f"{e.name} (status={e.status})")
            ```
        """
        client = self._require_api_client()
        raw = client.list_experiments(include_archived=include_archived)
        return [Experiment.model_validate(e) for e in raw]

    def create_experiment(self, params: CreateExperimentParams) -> Experiment:
        """Create a new experiment in Draft status.

        Args:
            params: Experiment creation parameters.

        Returns:
            The newly created ``Experiment``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid parameters (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            exp = ws.create_experiment(
                CreateExperimentParams(name="Checkout Flow Test")
            )
            ```
        """
        client = self._require_api_client()
        raw = client.create_experiment(params.model_dump(exclude_none=True))
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for create_experiment",
            )
        return Experiment.model_validate(raw)

    def get_experiment(self, experiment_id: str) -> Experiment:
        """Get a single experiment by ID.

        Args:
            experiment_id: Experiment UUID.

        Returns:
            The ``Experiment`` object.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Experiment not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            exp = ws.get_experiment("xyz-456-uuid")
            ```
        """
        client = self._require_api_client()
        raw = client.get_experiment(experiment_id)
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for get_experiment",
            )
        return Experiment.model_validate(raw)

    def update_experiment(
        self, experiment_id: str, params: UpdateExperimentParams
    ) -> Experiment:
        """Update an experiment (PATCH semantics).

        Args:
            experiment_id: Experiment UUID.
            params: Fields to update.

        Returns:
            The updated ``Experiment``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Experiment not found or invalid params (400, 404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            updated = ws.update_experiment(
                "xyz-456", UpdateExperimentParams(description="Updated")
            )
            ```
        """
        client = self._require_api_client()
        raw = client.update_experiment(
            experiment_id, params.model_dump(exclude_none=True)
        )
        if raw is None:
            raise MixpanelHeadlessError(
                "API returned empty response for update_experiment",
            )
        return Experiment.model_validate(raw)

    def delete_experiment(self, experiment_id: str) -> None:
        """Delete an experiment.

        Args:
            experiment_id: Experiment UUID.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Experiment not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.delete_experiment("xyz-456-uuid")
            ```
        """
        client = self._require_api_client()
        client.delete_experiment(experiment_id)

    # =========================================================================
    # EXPERIMENT LIFECYCLE (Phase 025)
    # =========================================================================

    def launch_experiment(self, experiment_id: str) -> Experiment:
        """Launch an experiment (Draft → Active).

        Args:
            experiment_id: Experiment UUID.

        Returns:
            The launched ``Experiment`` with updated status.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid state transition (400) or not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            launched = ws.launch_experiment("xyz-456-uuid")
            ```
        """
        client = self._require_api_client()
        raw = client.launch_experiment(experiment_id)
        return Experiment.model_validate(raw)

    def conclude_experiment(
        self,
        experiment_id: str,
        *,
        params: ExperimentConcludeParams | None = None,
    ) -> Experiment:
        """Conclude an experiment (Active → Concluded).

        Always sends a JSON body (empty ``{}`` if no params).

        Args:
            experiment_id: Experiment UUID.
            params: Optional conclude parameters (e.g. end date override).

        Returns:
            The concluded ``Experiment``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid state transition (400) or not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            concluded = ws.conclude_experiment("xyz-456-uuid")
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True) if params else {}
        raw = client.conclude_experiment(experiment_id, body)
        return Experiment.model_validate(raw)

    def decide_experiment(
        self, experiment_id: str, params: ExperimentDecideParams
    ) -> Experiment:
        """Record the experiment decision (Concluded → Success/Fail).

        Args:
            experiment_id: Experiment UUID.
            params: Decision parameters (success, variant, message).

        Returns:
            The decided ``Experiment`` with terminal status.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid state transition (400) or not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            decided = ws.decide_experiment(
                "xyz-456",
                ExperimentDecideParams(success=True, variant="simplified"),
            )
            ```
        """
        client = self._require_api_client()
        raw = client.decide_experiment(
            experiment_id, params.model_dump(exclude_none=True)
        )
        return Experiment.model_validate(raw)

    # =========================================================================
    # EXPERIMENT MANAGEMENT (Phase 025)
    # =========================================================================

    def archive_experiment(self, experiment_id: str) -> None:
        """Archive an experiment.

        Args:
            experiment_id: Experiment UUID.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Experiment not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.archive_experiment("xyz-456-uuid")
            ```
        """
        client = self._require_api_client()
        client.archive_experiment(experiment_id)

    def restore_experiment(self, experiment_id: str) -> Experiment:
        """Restore an archived experiment.

        Args:
            experiment_id: Experiment UUID.

        Returns:
            The restored ``Experiment``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Experiment not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            restored = ws.restore_experiment("xyz-456-uuid")
            ```
        """
        client = self._require_api_client()
        raw = client.restore_experiment(experiment_id)
        return Experiment.model_validate(raw)

    def duplicate_experiment(
        self,
        experiment_id: str,
        params: DuplicateExperimentParams,
    ) -> Experiment:
        """Duplicate an experiment.

        A name is required because the Mixpanel API returns an empty
        response body when duplicating without one.

        Args:
            experiment_id: Experiment UUID.
            params: Duplication parameters (``name`` is required).

        Returns:
            The newly created duplicate ``Experiment``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Experiment not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            dup = ws.duplicate_experiment(
                "xyz-456-uuid",
                DuplicateExperimentParams(name="Copy"),
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.duplicate_experiment(experiment_id, body)
        return Experiment.model_validate(raw)

    def list_erf_experiments(self) -> list[dict[str, Any]]:
        """List experiments in ERF (Experiment Results Framework) format.

        Returns:
            List of experiment dicts in ERF format.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            erf = ws.list_erf_experiments()
            ```
        """
        client = self._require_api_client()
        return client.list_erf_experiments()

    # =========================================================================
    # Annotations (Phase 026)
    # =========================================================================

    def list_annotations(
        self,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        tags: list[int] | None = None,
    ) -> list[Annotation]:
        """List timeline annotations for the project.

        Args:
            from_date: Start date filter (ISO format, e.g. ``"2026-01-01"``).
            to_date: End date filter (ISO format, e.g. ``"2026-03-31"``).
            tags: Tag IDs to filter by.

        Returns:
            List of ``Annotation`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            annotations = ws.list_annotations(from_date="2026-01-01")
            for ann in annotations:
                print(f"{ann.date}: {ann.description}")
            ```
        """
        client = self._require_api_client()
        raw_list = client.list_annotations(
            from_date=from_date, to_date=to_date, tags=tags
        )
        return [Annotation.model_validate(item) for item in raw_list]

    def create_annotation(self, params: CreateAnnotationParams) -> Annotation:
        """Create a new timeline annotation.

        Args:
            params: Annotation creation parameters (date, description required).

        Returns:
            The created ``Annotation``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ann = ws.create_annotation(
                CreateAnnotationParams(
                    date="2026-03-31", description="v2.5 release"
                )
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.create_annotation(body)
        return Annotation.model_validate(raw)

    def get_annotation(self, annotation_id: int) -> Annotation:
        """Get a single annotation by ID.

        Args:
            annotation_id: Annotation ID.

        Returns:
            The ``Annotation`` object.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Annotation not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ann = ws.get_annotation(42)
            print(ann.description)
            ```
        """
        client = self._require_api_client()
        raw = client.get_annotation(annotation_id)
        return Annotation.model_validate(raw)

    def update_annotation(
        self, annotation_id: int, params: UpdateAnnotationParams
    ) -> Annotation:
        """Update an annotation (PATCH semantics).

        Args:
            annotation_id: Annotation ID.
            params: Fields to update (description, tags).

        Returns:
            The updated ``Annotation``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Annotation not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ann = ws.update_annotation(
                42, UpdateAnnotationParams(description="Updated text")
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.update_annotation(annotation_id, body)
        return Annotation.model_validate(raw)

    def delete_annotation(self, annotation_id: int) -> None:
        """Delete an annotation.

        Args:
            annotation_id: Annotation ID.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Annotation not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.delete_annotation(42)
            ```
        """
        client = self._require_api_client()
        client.delete_annotation(annotation_id)

    def list_annotation_tags(self) -> list[AnnotationTag]:
        """List annotation tags for the project.

        Returns:
            List of ``AnnotationTag`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            tags = ws.list_annotation_tags()
            for tag in tags:
                print(tag.name)
            ```
        """
        client = self._require_api_client()
        raw_list = client.list_annotation_tags()
        return [AnnotationTag.model_validate(item) for item in raw_list]

    def create_annotation_tag(self, params: CreateAnnotationTagParams) -> AnnotationTag:
        """Create a new annotation tag.

        Args:
            params: Tag creation parameters (name required).

        Returns:
            The created ``AnnotationTag``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            tag = ws.create_annotation_tag(
                CreateAnnotationTagParams(name="releases")
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.create_annotation_tag(body)
        return AnnotationTag.model_validate(raw)

    # =========================================================================
    # Webhook CRUD (Phase 026)
    # =========================================================================

    def list_webhooks(self) -> list[ProjectWebhook]:
        """List all webhooks for the current project.

        Returns:
            List of ``ProjectWebhook`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            webhooks = ws.list_webhooks()
            for wh in webhooks:
                print(f"{wh.name} -> {wh.url}")
            ```
        """
        client = self._require_api_client()
        raw_list = client.list_webhooks()
        return [ProjectWebhook.model_validate(item) for item in raw_list]

    def create_webhook(self, params: CreateWebhookParams) -> WebhookMutationResult:
        """Create a new webhook.

        Args:
            params: Webhook creation parameters.

        Returns:
            ``WebhookMutationResult`` with the new webhook's id and name.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            result = ws.create_webhook(
                CreateWebhookParams(name="Pipeline", url="https://example.com/hook")
            )
            print(result.id)
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.create_webhook(body)
        return WebhookMutationResult.model_validate(raw)

    def update_webhook(
        self, webhook_id: str, params: UpdateWebhookParams
    ) -> WebhookMutationResult:
        """Update an existing webhook.

        Args:
            webhook_id: Webhook UUID string.
            params: Fields to update (PATCH semantics).

        Returns:
            ``WebhookMutationResult`` with the updated webhook's id and name.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Webhook not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            result = ws.update_webhook(
                "wh-uuid-123",
                UpdateWebhookParams(name="Renamed Hook"),
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.update_webhook(webhook_id, body)
        return WebhookMutationResult.model_validate(raw)

    def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook.

        Args:
            webhook_id: Webhook UUID string.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Webhook not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.delete_webhook("wh-uuid-123")
            ```
        """
        client = self._require_api_client()
        client.delete_webhook(webhook_id)

    def test_webhook(self, params: WebhookTestParams) -> WebhookTestResult:
        """Test webhook connectivity.

        Args:
            params: Webhook test parameters (url is required).

        Returns:
            ``WebhookTestResult`` with success, status_code, and message.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            result = ws.test_webhook(
                WebhookTestParams(url="https://example.com/hook")
            )
            if result.success:
                print("Webhook is reachable")
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.test_webhook(body)
        return WebhookTestResult.model_validate(raw)

    # =========================================================================
    # Alert CRUD (Phase 026)
    # =========================================================================

    def list_alerts(
        self,
        *,
        bookmark_id: int | None = None,
        skip_user_filter: bool | None = None,
    ) -> list[CustomAlert]:
        """List custom alerts for the current project.

        Args:
            bookmark_id: Filter alerts by linked bookmark ID.
            skip_user_filter: If True, list alerts for all users.

        Returns:
            List of ``CustomAlert`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            alerts = ws.list_alerts()
            for alert in alerts:
                print(f"{alert.name} (paused={alert.paused})")
            ```
        """
        client = self._require_api_client()
        raw_list = client.list_alerts(
            bookmark_id=bookmark_id, skip_user_filter=skip_user_filter
        )
        return [CustomAlert.model_validate(item) for item in raw_list]

    def create_alert(self, params: CreateAlertParams) -> CustomAlert:
        """Create a new custom alert.

        Args:
            params: Alert creation parameters (bookmark_id, name, condition,
                frequency, paused, and subscriptions are required).

        Returns:
            The created ``CustomAlert``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            alert = ws.create_alert(
                CreateAlertParams(
                    bookmark_id=123,
                    name="Daily signups drop",
                    condition={"operator": "less_than", "value": 100},
                    frequency=86400,
                    paused=False,
                    subscriptions=[{"type": "email", "value": "team@co.com"}],
                )
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.create_alert(body)
        return CustomAlert.model_validate(raw)

    def get_alert(self, alert_id: int) -> CustomAlert:
        """Get a single custom alert by ID.

        Args:
            alert_id: Alert ID (integer).

        Returns:
            The ``CustomAlert`` object.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Alert not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            alert = ws.get_alert(42)
            print(alert.name)
            ```
        """
        client = self._require_api_client()
        raw = client.get_alert(alert_id)
        return CustomAlert.model_validate(raw)

    def update_alert(self, alert_id: int, params: UpdateAlertParams) -> CustomAlert:
        """Update a custom alert (PATCH semantics).

        Args:
            alert_id: Alert ID (integer).
            params: Fields to update.

        Returns:
            The updated ``CustomAlert``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Alert not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            alert = ws.update_alert(
                42, UpdateAlertParams(name="Renamed alert")
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.update_alert(alert_id, body)
        return CustomAlert.model_validate(raw)

    def delete_alert(self, alert_id: int) -> None:
        """Delete a custom alert.

        Args:
            alert_id: Alert ID (integer).

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Alert not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.delete_alert(42)
            ```
        """
        client = self._require_api_client()
        client.delete_alert(alert_id)

    def bulk_delete_alerts(self, ids: list[int]) -> None:
        """Bulk-delete custom alerts.

        Args:
            ids: List of alert IDs to delete.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.bulk_delete_alerts([1, 2, 3])
            ```
        """
        client = self._require_api_client()
        client.bulk_delete_alerts(ids)

    def get_alert_count(self, *, alert_type: str | None = None) -> AlertCount:
        """Get alert count and limits.

        Args:
            alert_type: Optional filter by alert type.

        Returns:
            ``AlertCount`` with count, limit, and is_below_limit.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            count = ws.get_alert_count()
            if count.is_below_limit:
                print(f"{count.anomaly_alerts_count}/{count.alert_limit}")
            ```
        """
        client = self._require_api_client()
        raw = client.get_alert_count(alert_type=alert_type)
        return AlertCount.model_validate(raw)

    def get_alert_history(
        self,
        alert_id: int,
        *,
        page_size: int | None = None,
        next_cursor: str | None = None,
        previous_cursor: str | None = None,
    ) -> AlertHistoryResponse:
        """Get alert trigger history (paginated).

        Args:
            alert_id: Alert ID (integer).
            page_size: Number of results per page.
            next_cursor: Cursor for the next page.
            previous_cursor: Cursor for the previous page.

        Returns:
            ``AlertHistoryResponse`` with results and pagination metadata.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Alert not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            history = ws.get_alert_history(42, page_size=10)
            for entry in history.results:
                print(entry)
            ```
        """
        client = self._require_api_client()
        raw = client.get_alert_history(
            alert_id,
            page_size=page_size,
            next_cursor=next_cursor,
            previous_cursor=previous_cursor,
        )
        return AlertHistoryResponse.model_validate(raw)

    def test_alert(self, params: CreateAlertParams) -> dict[str, Any]:
        """Send a test alert notification.

        Args:
            params: Alert parameters for the test (same shape as create).

        Returns:
            Dictionary with test result status (opaque response).

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            result = ws.test_alert(
                CreateAlertParams(
                    bookmark_id=123, name="Test",
                    condition={}, frequency=86400,
                    paused=False, subscriptions=[],
                )
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        return client.test_alert(body)

    def get_alert_screenshot_url(self, gcs_key: str) -> AlertScreenshotResponse:
        """Get a signed URL for an alert screenshot.

        Args:
            gcs_key: GCS object key for the screenshot.

        Returns:
            ``AlertScreenshotResponse`` with the signed URL.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Screenshot not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            resp = ws.get_alert_screenshot_url("screenshots/abc.png")
            print(resp.signed_url)
            ```
        """
        client = self._require_api_client()
        raw = client.get_alert_screenshot_url(gcs_key)
        return AlertScreenshotResponse.model_validate(raw)

    def validate_alerts_for_bookmark(
        self, params: ValidateAlertsForBookmarkParams
    ) -> ValidateAlertsForBookmarkResponse:
        """Validate alerts against a bookmark configuration.

        Args:
            params: Validation parameters (alert_ids, bookmark_type,
                bookmark_params are required).

        Returns:
            ``ValidateAlertsForBookmarkResponse`` with per-alert validations
            and invalid count.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            resp = ws.validate_alerts_for_bookmark(
                ValidateAlertsForBookmarkParams(
                    alert_ids=[1, 2],
                    bookmark_type="insights",
                    bookmark_params={"event": "Signup"},
                )
            )
            if resp.invalid_count > 0:
                for v in resp.alert_validations:
                    if not v.valid:
                        print(f"{v.alert_name}: {v.reason}")
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.validate_alerts_for_bookmark(body)
        return ValidateAlertsForBookmarkResponse.model_validate(raw)

    # =============================================================================
    # Data Governance — Data Definitions / Lexicon (Phase 027)
    # =============================================================================

    def get_event_definitions(self, *, names: list[str]) -> list[EventDefinition]:
        """Get event definitions from Lexicon by name.

        Retrieves metadata (description, tags, visibility, etc.) for the
        specified events from the Mixpanel Lexicon.

        Args:
            names: List of event names to look up.

        Returns:
            List of ``EventDefinition`` objects for the requested events.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            defs = ws.get_event_definitions(names=["Signup", "Login"])
            for d in defs:
                print(f"{d.name}: {d.description}")
            ```
        """
        client = self._require_api_client()
        raw_list = client.get_event_definitions(names)
        return [EventDefinition.model_validate(x) for x in raw_list]

    def update_event_definition(
        self, event_name: str, params: UpdateEventDefinitionParams
    ) -> EventDefinition:
        """Update an event definition in Lexicon.

        Args:
            event_name: Name of the event to update.
            params: Fields to update (hidden, dropped, merged,
                verified, tags, description).

        Returns:
            The updated ``EventDefinition``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Event not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            definition = ws.update_event_definition(
                "Signup",
                UpdateEventDefinitionParams(description="User signed up"),
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.update_event_definition(event_name, body)
        return EventDefinition.model_validate(raw)

    def delete_event_definition(self, event_name: str) -> None:
        """Delete an event definition from Lexicon.

        Args:
            event_name: Name of the event to delete.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Event not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.delete_event_definition("OldEvent")
            ```
        """
        client = self._require_api_client()
        client.delete_event_definition(event_name)

    def bulk_update_event_definitions(
        self, params: BulkUpdateEventsParams
    ) -> list[EventDefinition]:
        """Bulk-update event definitions in Lexicon.

        Args:
            params: Bulk update parameters containing a list of event
                updates (name + fields to change).

        Returns:
            List of updated ``EventDefinition`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            defs = ws.bulk_update_event_definitions(
                BulkUpdateEventsParams(events=[
                    {"name": "Signup", "description": "User signed up"},
                    {"name": "Login", "hidden": True},
                ])
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw_list = client.bulk_update_event_definitions(body)
        return [EventDefinition.model_validate(x) for x in raw_list]

    def get_property_definitions(
        self,
        *,
        names: list[str],
        resource_type: str | None = None,
    ) -> list[PropertyDefinition]:
        """Get property definitions from Lexicon by name.

        Retrieves metadata (description, tags, visibility, etc.) for the
        specified properties from the Mixpanel Lexicon.

        Args:
            names: List of property names to look up.
            resource_type: Optional resource type filter (e.g. ``"event"``,
                ``"user"``, ``"groupprofile"``).

        Returns:
            List of ``PropertyDefinition`` objects for the requested properties.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            defs = ws.get_property_definitions(
                names=["plan_type", "country"],
                resource_type="event",
            )
            for d in defs:
                print(f"{d.name}: {d.description}")
            ```
        """
        client = self._require_api_client()
        raw_list = client.get_property_definitions(names, resource_type=resource_type)
        return [PropertyDefinition.model_validate(x) for x in raw_list]

    def update_property_definition(
        self, property_name: str, params: UpdatePropertyDefinitionParams
    ) -> PropertyDefinition:
        """Update a property definition in Lexicon.

        Args:
            property_name: Name of the property to update.
            params: Fields to update (hidden, dropped, merged,
                sensitive, description).

        Returns:
            The updated ``PropertyDefinition``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Property not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            definition = ws.update_property_definition(
                "plan_type",
                UpdatePropertyDefinitionParams(description="User plan tier"),
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.update_property_definition(property_name, body)
        return PropertyDefinition.model_validate(raw)

    def bulk_update_property_definitions(
        self, params: BulkUpdatePropertiesParams
    ) -> list[PropertyDefinition]:
        """Bulk-update property definitions in Lexicon.

        Args:
            params: Bulk update parameters containing a list of property
                updates (name + fields to change).

        Returns:
            List of updated ``PropertyDefinition`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            defs = ws.bulk_update_property_definitions(
                BulkUpdatePropertiesParams(properties=[
                    {"name": "plan_type", "description": "User plan tier"},
                    {"name": "country", "hidden": True},
                ])
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True, by_alias=True)
        raw_list = client.bulk_update_property_definitions(body)
        return [PropertyDefinition.model_validate(x) for x in raw_list]

    # ---- Tags ----

    def list_lexicon_tags(self) -> list[LexiconTag]:
        """List all Lexicon tags.

        Returns:
            List of ``LexiconTag`` objects with ``id`` and ``name`` fields.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            tags = ws.list_lexicon_tags()
            for tag in tags:
                print(tag.name)
            ```

        Note:
            The list endpoint may return plain tag name strings without IDs.
            In that case, ``id`` is set to ``0`` as a sentinel value. Do not
            pass this sentinel to ``update_lexicon_tag()`` — use name-based
            operations (e.g. ``delete_lexicon_tag(tag.name)``) for tags
            obtained from this method.
        """
        client = self._require_api_client()
        raw_list = client.list_lexicon_tags()
        result: list[LexiconTag] = []
        for x in raw_list:
            if isinstance(x, str):
                # List endpoint returns plain tag name strings (no id);
                # id=0 is a sentinel — see docstring Note.
                result.append(LexiconTag(id=0, name=x))
            else:
                result.append(LexiconTag.model_validate(x))
        return result

    def create_lexicon_tag(self, params: CreateTagParams) -> LexiconTag:
        """Create a new Lexicon tag.

        Args:
            params: Tag creation parameters (name is required).

        Returns:
            The created ``LexiconTag``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400) or tag already exists.
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            tag = ws.create_lexicon_tag(CreateTagParams(name="core-events"))
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.create_lexicon_tag(body)
        return LexiconTag.model_validate(raw)

    def update_lexicon_tag(self, tag_id: int, params: UpdateTagParams) -> LexiconTag:
        """Update a Lexicon tag.

        Args:
            tag_id: Tag ID (integer).
            params: Fields to update (e.g. name).

        Returns:
            The updated ``LexiconTag``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Tag not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            tag = ws.update_lexicon_tag(
                5, UpdateTagParams(name="renamed-tag")
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.update_lexicon_tag(tag_id, body)
        return LexiconTag.model_validate(raw)

    def delete_lexicon_tag(self, tag_name: str) -> None:
        """Delete a Lexicon tag by name.

        Args:
            tag_name: Name of the tag to delete.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Tag not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.delete_lexicon_tag("deprecated-tag")
            ```
        """
        client = self._require_api_client()
        client.delete_lexicon_tag(tag_name)

    # =============================================================================
    # Data Governance — Drop Filters (Phase 027)
    # =============================================================================

    def list_drop_filters(self) -> list[DropFilter]:
        """List all drop filters.

        Returns:
            List of ``DropFilter`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            filters = ws.list_drop_filters()
            for f in filters:
                print(f"{f.event_name}: active={f.active}")
            ```
        """
        client = self._require_api_client()
        raw_list = client.list_drop_filters()
        return [DropFilter.model_validate(x) for x in raw_list]

    def create_drop_filter(self, params: CreateDropFilterParams) -> list[DropFilter]:
        """Create a new drop filter.

        Args:
            params: Drop filter creation parameters.

        Returns:
            Full list of ``DropFilter`` objects after creation.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            filters = ws.create_drop_filter(
                CreateDropFilterParams(
                    event_name="Debug Event",
                    filters={"property": "env", "value": "test"},
                )
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw_list = client.create_drop_filter(body)
        return [DropFilter.model_validate(x) for x in raw_list]

    def update_drop_filter(self, params: UpdateDropFilterParams) -> list[DropFilter]:
        """Update a drop filter.

        Args:
            params: Drop filter update parameters (must include the filter ID).

        Returns:
            Full list of ``DropFilter`` objects after update.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Filter not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            filters = ws.update_drop_filter(
                UpdateDropFilterParams(
                    id=42, event_name="Debug Event v2"
                )
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw_list = client.update_drop_filter(body)
        return [DropFilter.model_validate(x) for x in raw_list]

    def delete_drop_filter(self, drop_filter_id: int) -> list[DropFilter]:
        """Delete a drop filter.

        Args:
            drop_filter_id: Drop filter ID (integer).

        Returns:
            Full list of remaining ``DropFilter`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Filter not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            remaining = ws.delete_drop_filter(42)
            ```
        """
        client = self._require_api_client()
        raw_list = client.delete_drop_filter(drop_filter_id)
        return [DropFilter.model_validate(x) for x in raw_list]

    def get_drop_filter_limits(self) -> DropFilterLimitsResponse:
        """Get drop filter usage limits.

        Returns:
            ``DropFilterLimitsResponse`` with the maximum allowed
            drop filters for the project.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            limits = ws.get_drop_filter_limits()
            print(f"Drop filter limit: {limits.filter_limit}")
            ```
        """
        client = self._require_api_client()
        raw = client.get_drop_filter_limits()
        return DropFilterLimitsResponse.model_validate(raw)

    # =============================================================================
    # Data Governance — Custom Properties (Phase 027)
    # =============================================================================

    def list_custom_properties(self) -> list[CustomProperty]:
        """List all custom properties.

        Returns:
            List of ``CustomProperty`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Server-side data corruption (e.g. invalid
                ``displayFormula`` on a custom property).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            props = ws.list_custom_properties()
            for p in props:
                print(f"{p.name}: {p.display_formula}")
            ```
        """
        client = self._require_api_client()
        try:
            raw_list = client.list_custom_properties()
        except QueryError as exc:
            # Detect server-side data corruption: the API fails to serialize
            # when a custom property has an invalid displayFormula.
            details = exc.details if isinstance(exc.details, dict) else {}
            body = details.get("response_body", {}) if isinstance(details, dict) else {}
            if isinstance(body, dict) and body.get("field") == "displayFormula":
                raise QueryError(
                    "list_custom_properties() failed: the project contains a "
                    "custom property with an invalid displayFormula "
                    "(server-side data corruption). Use "
                    "get_custom_property(id) to retrieve individual "
                    "properties, or contact Mixpanel support.",
                    status_code=exc.status_code,
                    response_body=exc.response_body,
                    request_method=exc.request_method,
                    request_url=exc.request_url,
                    request_params=exc.request_params,
                ) from exc
            raise
        return [CustomProperty.model_validate(x) for x in raw_list]

    def create_custom_property(
        self, params: CreateCustomPropertyParams
    ) -> CustomProperty:
        """Create a new custom property.

        Args:
            params: Custom property creation parameters (name,
                display_formula or behavior, resource_type are required).

        Returns:
            The created ``CustomProperty``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            prop = ws.create_custom_property(
                CreateCustomPropertyParams(
                    name="Full Name",
                    display_formula='concat(properties["first"], " ", properties["last"])',
                    composed_properties={"first": ComposedPropertyValue(resource_type="event"), "last": ComposedPropertyValue(resource_type="event")},
                    resource_type="event",
                )
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True, by_alias=True, mode="json")
        raw = client.create_custom_property(body)
        return CustomProperty.model_validate(raw)

    def get_custom_property(self, property_id: str) -> CustomProperty:
        """Get a custom property by ID.

        Args:
            property_id: Custom property ID (string).

        Returns:
            The ``CustomProperty`` object.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Property not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            prop = ws.get_custom_property("abc123")
            print(prop.name)
            ```
        """
        client = self._require_api_client()
        raw = client.get_custom_property(property_id)
        return CustomProperty.model_validate(raw)

    def update_custom_property(
        self, property_id: str, params: UpdateCustomPropertyParams
    ) -> CustomProperty:
        """Update a custom property.

        Args:
            property_id: Custom property ID (string).
            params: Fields to update.

        Returns:
            The updated ``CustomProperty``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Property not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            prop = ws.update_custom_property(
                "abc123",
                UpdateCustomPropertyParams(name="Renamed Property"),
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True, by_alias=True)
        raw = client.update_custom_property(property_id, body)
        return CustomProperty.model_validate(raw)

    def delete_custom_property(self, property_id: str) -> None:
        """Delete a custom property.

        Args:
            property_id: Custom property ID (string).

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Property not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.delete_custom_property("abc123")
            ```
        """
        client = self._require_api_client()
        client.delete_custom_property(property_id)

    def validate_custom_property(
        self, params: CreateCustomPropertyParams
    ) -> dict[str, Any]:
        """Validate a custom property definition without creating it.

        Args:
            params: Custom property parameters to validate.

        Returns:
            Validation result as a raw dictionary.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            result = ws.validate_custom_property(
                CreateCustomPropertyParams(
                    name="Full Name",
                    display_formula='concat(properties["first"], " ", properties["last"])',
                    composed_properties={"first": ComposedPropertyValue(resource_type="event"), "last": ComposedPropertyValue(resource_type="event")},
                    resource_type="event",
                )
            )
            print(result)
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True, by_alias=True)
        return client.validate_custom_property(body)

    # =============================================================================
    # Data Governance — Lookup Tables (Phase 027)
    # =============================================================================

    def list_lookup_tables(
        self, *, data_group_id: int | None = None
    ) -> list[LookupTable]:
        """List lookup tables.

        Args:
            data_group_id: Optional filter by data group ID.

        Returns:
            List of ``LookupTable`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            tables = ws.list_lookup_tables()
            for t in tables:
                print(f"{t.name} (mapped={t.has_mapped_properties})")
            ```
        """
        client = self._require_api_client()
        raw_list = client.list_lookup_tables(data_group_id=data_group_id)
        return [LookupTable.model_validate(x) for x in raw_list]

    def upload_lookup_table(
        self,
        params: UploadLookupTableParams,
        *,
        poll_interval: float = 2.0,
        max_poll_seconds: float = 300.0,
    ) -> LookupTable:
        """Upload a CSV file as a new lookup table.

        Performs a 3-step upload process:
        1. Obtains a signed upload URL from the API.
        2. Uploads the CSV file to the signed URL.
        3. Registers the lookup table with the uploaded data.

        For files >= 5 MB, the API processes the upload asynchronously.
        This method automatically polls until processing completes.

        Args:
            params: Upload parameters including ``name``, ``file_path``
                (path to the CSV file), and optional ``data_group_id``.
            poll_interval: Seconds between status polls for async uploads.
            max_poll_seconds: Maximum seconds to wait for async processing.

        Returns:
            The created ``LookupTable`` object.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400) or file not found.
            ServerError: Server-side errors (5xx).
            FileNotFoundError: If the CSV file does not exist.
            MixpanelHeadlessError: Async processing timed out or failed.

        Example:
            ```python
            ws = Workspace()
            table = ws.upload_lookup_table(
                UploadLookupTableParams(
                    name="Country Codes",
                    file_path="/path/to/countries.csv",
                )
            )
            print(f"Created: {table.name}")
            ```
        """
        client = self._require_api_client()
        logger = logging.getLogger(__name__)

        # Step 1: Get signed upload URL
        url_info = client.get_lookup_upload_url()

        # Step 2: Read and upload the CSV file
        csv_bytes = Path(params.file_path).read_bytes()
        client.upload_to_signed_url(url_info["url"], csv_bytes)

        # Step 3: Register the lookup table
        form_data: dict[str, str] = {
            "name": params.name,
            "path": url_info["path"],
            "key": url_info["key"],
        }
        if params.data_group_id is not None:
            form_data["data-group-id"] = str(params.data_group_id)

        raw = client.register_lookup_table(form_data)

        # The API returns {"uploadId": "..."} for files >= 5 MB,
        # indicating async processing via Celery.
        upload_id = raw.get("uploadId") if isinstance(raw, dict) else None
        if upload_id is not None:
            logger.info(
                "Lookup table upload is processing asynchronously "
                "(uploadId=%s), polling for completion...",
                upload_id,
            )
            raw = self._poll_lookup_upload(
                client, upload_id, poll_interval, max_poll_seconds
            )

        # Upload response may only contain {'id': '...'} without 'name';
        # inject the name from params so LookupTable validation succeeds.
        if isinstance(raw, dict) and "name" not in raw:
            raw = {**raw, "name": params.name}
        return LookupTable.model_validate(raw)

    def _poll_lookup_upload(
        self,
        client: MixpanelAPIClient,
        upload_id: str,
        poll_interval: float,
        max_poll_seconds: float,
    ) -> dict[str, Any]:
        """Poll for async lookup table upload completion.

        Args:
            client: API client instance.
            upload_id: Async upload task ID.
            poll_interval: Seconds between polls.
            max_poll_seconds: Maximum total wait time.

        Returns:
            The result dictionary from the completed upload.

        Raises:
            MixpanelHeadlessError: If polling times out or the task fails.
        """
        logger = logging.getLogger(__name__)
        deadline = time.monotonic() + max_poll_seconds

        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            status = client.get_lookup_upload_status(upload_id)
            upload_status = status.get("uploadStatus", "UNKNOWN")

            if upload_status == "SUCCESS":
                result = status.get("result")
                if isinstance(result, dict):
                    return result
                raise MixpanelHeadlessError(
                    f"Lookup table upload succeeded but returned "
                    f"unexpected result: {status}",
                    code="INVALID_RESPONSE",
                )

            if upload_status in ("FAILURE", "REVOKED"):
                raise MixpanelHeadlessError(
                    f"Lookup table upload failed with status "
                    f"'{upload_status}': {status}",
                    code="UPLOAD_FAILED",
                    details={"upload_id": upload_id, "status": status},
                )

            if upload_status == "NOTFOUND":
                raise MixpanelHeadlessError(
                    f"Lookup table upload not found (uploadId={upload_id}). "
                    f"The upload may have expired.",
                    code="UPLOAD_NOT_FOUND",
                    details={"upload_id": upload_id},
                )

            logger.debug(
                "Lookup table upload status: %s (uploadId=%s)",
                upload_status,
                upload_id,
            )

        raise MixpanelHeadlessError(
            f"Lookup table upload timed out after {max_poll_seconds}s "
            f"(uploadId={upload_id}). Use get_lookup_upload_status() "
            f"to check progress manually.",
            code="UPLOAD_TIMEOUT",
            details={"upload_id": upload_id},
        )

    def mark_lookup_table_ready(
        self, params: MarkLookupTableReadyParams
    ) -> LookupTable:
        """Mark a lookup table as ready after upload.

        Args:
            params: Parameters including ``name``, ``key``, and optional
                ``data_group_id``.

        Returns:
            The updated ``LookupTable``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            table = ws.mark_lookup_table_ready(
                MarkLookupTableReadyParams(
                    name="Country Codes",
                    key="uploads/abc123.csv",
                )
            )
            ```
        """
        client = self._require_api_client()
        form_data: dict[str, str] = {
            "name": params.name,
            "key": params.key,
        }
        if params.data_group_id is not None:
            form_data["data-group-id"] = str(params.data_group_id)

        raw = client.mark_lookup_table_ready(form_data)
        return LookupTable.model_validate(raw)

    def get_lookup_upload_url(
        self, content_type: str = "text/csv"
    ) -> LookupTableUploadUrl:
        """Get a signed URL for uploading lookup table data.

        Args:
            content_type: MIME type of the file to upload
                (default: ``"text/csv"``).

        Returns:
            ``LookupTableUploadUrl`` with the signed URL, path, and key.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            url_info = ws.get_lookup_upload_url()
            print(url_info.url)
            ```
        """
        client = self._require_api_client()
        raw = client.get_lookup_upload_url(content_type)
        return LookupTableUploadUrl.model_validate(raw)

    def get_lookup_upload_status(self, upload_id: str) -> dict[str, Any]:
        """Get the processing status of a lookup table upload.

        Args:
            upload_id: Upload ID returned from the upload process.

        Returns:
            Raw status dictionary with processing details.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Upload not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            status = ws.get_lookup_upload_status("upload-abc123")
            print(status["state"])
            ```
        """
        client = self._require_api_client()
        return client.get_lookup_upload_status(upload_id)

    def update_lookup_table(
        self, data_group_id: int, params: UpdateLookupTableParams
    ) -> LookupTable:
        """Update a lookup table.

        Args:
            data_group_id: Data group ID of the lookup table.
            params: Fields to update.

        Returns:
            The updated ``LookupTable``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Table not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            table = ws.update_lookup_table(
                123,
                UpdateLookupTableParams(name="Renamed Table"),
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.update_lookup_table(data_group_id, body)
        return LookupTable.model_validate(raw)

    def delete_lookup_tables(self, data_group_ids: list[int]) -> None:
        """Delete one or more lookup tables.

        Args:
            data_group_ids: List of data group IDs to delete.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.delete_lookup_tables([123, 456])
            ```
        """
        client = self._require_api_client()
        client.delete_lookup_tables(data_group_ids)

    def download_lookup_table(
        self,
        data_group_id: int,
        *,
        file_name: str | None = None,
        limit: int | None = None,
    ) -> bytes:
        """Download lookup table data as raw bytes (CSV).

        Args:
            data_group_id: Data group ID of the lookup table.
            file_name: Optional file name filter.
            limit: Optional row limit.

        Returns:
            Raw CSV bytes of the lookup table data.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Table not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            csv_data = ws.download_lookup_table(123)
            Path("output.csv").write_bytes(csv_data)
            ```
        """
        client = self._require_api_client()
        return client.download_lookup_table(
            data_group_id, file_name=file_name, limit=limit
        )

    def get_lookup_download_url(self, data_group_id: int) -> str:
        """Get a signed download URL for a lookup table.

        Args:
            data_group_id: Data group ID of the lookup table.

        Returns:
            Signed URL string for downloading the lookup table data.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Table not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            url = ws.get_lookup_download_url(123)
            print(url)
            ```
        """
        client = self._require_api_client()
        return client.get_lookup_download_url(data_group_id)

    # =============================================================================
    # Data Governance — Custom Events (Phase 027)
    # =============================================================================

    def create_custom_event(self, params: CreateCustomEventParams) -> CustomEvent:
        """Create a new custom event.

        A custom event is a composite alias that groups one or more underlying
        events under a single name (e.g. a "Page View" custom event aliasing
        "Home Viewed", "Product Viewed", "Checkout Viewed"). Custom events
        appear alongside regular events in queries and dashboards but resolve
        to the union of their underlying events at query time.

        Args:
            params: Custom event creation parameters. Must include a non-empty
                ``name`` and a non-empty list of underlying event names in
                ``alternatives``.

        Returns:
            The created :class:`CustomEvent`, including its server-assigned
            ``id``, ``name``, and ``alternatives``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400) — for example, duplicate
                custom event name or unknown underlying event.
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ce = ws.create_custom_event(
                CreateCustomEventParams(
                    name="Metric Tree Opened",
                    alternatives=["Enter room"],
                )
            )
            print(ce.id, ce.name)
            ```
        """
        client = self._require_api_client()
        raw = client.create_custom_event(params.to_form_body())
        return CustomEvent.model_validate(raw)

    def list_custom_events(self) -> list[EventDefinition]:
        """List all custom events.

        Returns:
            List of ``EventDefinition`` objects for custom events.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            events = ws.list_custom_events()
            for e in events:
                print(e.name)
            ```
        """
        client = self._require_api_client()
        raw_list = client.list_custom_events()
        return [EventDefinition.model_validate(x) for x in raw_list]

    def update_custom_event(
        self, custom_event_id: int, params: UpdateEventDefinitionParams
    ) -> EventDefinition:
        """Update a custom event's lexicon entry (description, tags, etc.).

        The Mixpanel ``data-definitions/events/`` endpoint matches updates by
        the most specific identifier; for custom events that's the
        ``customEventId``. This SDK method requires the id (rather than the
        display name) to avoid creating orphan lexicon entries — passing a
        name alone causes the server to fabricate a new, unlinked entry.

        Get the id from :meth:`create_custom_event`'s return value
        (``CustomEvent.id``) or from the ``custom_event_id`` field on entries
        returned by :meth:`list_custom_events`.

        Args:
            custom_event_id: Server-assigned custom event ID.
            params: Fields to update. See
                :class:`UpdateEventDefinitionParams` for the full list of
                supported fields.

        Returns:
            The updated ``EventDefinition`` (lexicon view of the custom
            event, with ``custom_event_id`` populated).

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Event not found (404) or validation error (400).
            ServerError: Server-side errors (5xx).
            MixpanelHeadlessError: Server returned an entry with a different
                ``customEventId`` than requested
                (``code="UPDATE_TARGET_MISMATCH"``).

        Example:
            ```python
            ws = Workspace()
            ce = ws.create_custom_event(CreateCustomEventParams(
                name="Metric Tree Opened", alternatives=["Enter room"],
            ))
            event = ws.update_custom_event(
                ce.id,
                UpdateEventDefinitionParams(
                    description="Fires when a user opens a metric tree canvas.",
                    verified=True,
                ),
            )
            ```
        """
        client = self._require_api_client()
        body = params.model_dump(exclude_none=True)
        raw = client.update_custom_event(custom_event_id, body)
        return EventDefinition.model_validate(raw)

    def delete_custom_event(self, custom_event_id: int) -> None:
        """Delete a custom event.

        Identifies the entry by ``custom_event_id`` (not name) for the
        same reason :meth:`update_custom_event` does: a name-only DELETE
        against the data-definitions endpoint is ambiguous when multiple
        entries share a display name and may silently delete the wrong row,
        an auto-derived orphan lexicon entry, or no-op while still
        reporting success.

        Get the id from :meth:`create_custom_event`'s return value
        (``CustomEvent.id``) or from the ``custom_event_id`` field on
        entries returned by :meth:`list_custom_events`.

        Args:
            custom_event_id: Server-assigned custom event ID.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Event not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            ws.delete_custom_event(42)
            ```
        """
        client = self._require_api_client()
        client.delete_custom_event(custom_event_id)

    # =============================================================================
    # Data Governance — Tracking & History (Phase 027)
    # =============================================================================

    def get_tracking_metadata(self, event_name: str) -> dict[str, Any]:
        """Get tracking metadata for an event.

        Retrieves information about how an event is being tracked
        (sources, SDKs, volume, etc.).

        Args:
            event_name: Name of the event.

        Returns:
            Raw tracking metadata dictionary.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Event not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            metadata = ws.get_tracking_metadata("Signup")
            print(metadata)
            ```
        """
        client = self._require_api_client()
        return client.get_tracking_metadata(event_name)

    def get_event_history(self, event_name: str) -> list[dict[str, Any]]:
        """Get change history for an event definition.

        Args:
            event_name: Name of the event.

        Returns:
            List of history entries (raw dictionaries) showing changes
            to the event definition over time.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Event not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            history = ws.get_event_history("Signup")
            for entry in history:
                print(f"{entry['timestamp']}: {entry['action']}")
            ```
        """
        client = self._require_api_client()
        return client.get_event_history(event_name)

    def get_property_history(
        self, property_name: str, entity_type: str
    ) -> list[dict[str, Any]]:
        """Get change history for a property definition.

        Args:
            property_name: Name of the property.
            entity_type: Entity type (e.g. ``"event"``, ``"user"``,
                ``"group"``).

        Returns:
            List of history entries (raw dictionaries) showing changes
            to the property definition over time.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Property not found (404).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            history = ws.get_property_history("plan_type", "event")
            for entry in history:
                print(f"{entry['timestamp']}: {entry['action']}")
            ```
        """
        client = self._require_api_client()
        return client.get_property_history(property_name, entity_type)

    # ---- Export ----

    def export_lexicon(
        self, *, export_types: list[str] | None = None
    ) -> dict[str, Any]:
        """Export Lexicon data definitions.

        Exports event and property definitions from Lexicon, optionally
        filtered by type.

        Args:
            export_types: Optional list of types to export (e.g.
                ``["All Events and Properties", "All User Profile Properties"]``).

        Returns:
            Raw export dictionary containing the exported definitions.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            ServerError: Server-side errors (5xx).

        Example:
            ```python
            ws = Workspace()
            export = ws.export_lexicon(
                export_types=["All Events and Properties"]
            )
            print(len(export.get("events", [])))
            ```
        """
        client = self._require_api_client()
        return client.export_lexicon(export_types=export_types)

    # =========================================================================
    # Schema Registry CRUD (Phase 028)
    # =========================================================================

    def list_schema_registry(
        self,
        *,
        entity_type: str | None = None,
    ) -> list[SchemaEntry]:
        """List schema registry entries.

        Args:
            entity_type: Filter by entity type ("event", "custom_event",
                "profile"). If None, returns all schemas.

        Returns:
            List of ``SchemaEntry`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            RateLimitError: Rate limit exceeded (429).

        Example:
            ```python
            ws = Workspace()
            schemas = ws.list_schema_registry(entity_type="event")
            for s in schemas:
                print(f"{s.name}: {s.entity_type}")
            ```
        """
        client = self._require_api_client()
        raw_list = client.list_schema_registry(entity_type=entity_type)
        return [SchemaEntry.model_validate(r) for r in raw_list]

    def create_schema(
        self,
        entity_type: str,
        entity_name: str,
        schema_json: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a single schema definition.

        Args:
            entity_type: Entity type ("event", "custom_event", "profile").
            entity_name: Entity name (event name or "$user" for profile).
            schema_json: JSON Schema Draft 7 definition.

        Returns:
            Created schema as dict.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            RateLimitError: Rate limit exceeded (429).

        Example:
            ```python
            ws = Workspace()
            ws.create_schema("event", "Purchase", {
                "properties": {"amount": {"type": "number"}}
            })
            ```
        """
        client = self._require_api_client()
        return client.create_schema(entity_type, entity_name, schema_json)

    def create_schemas_bulk(
        self,
        params: BulkCreateSchemasParams,
    ) -> BulkCreateSchemasResponse:
        """Bulk create schemas.

        Args:
            params: Bulk creation parameters with entries list and
                optional truncate flag.

        Returns:
            Response with ``added`` and ``deleted`` counts.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).
            RateLimitError: Rate limit exceeded (429).

        Example:
            ```python
            ws = Workspace()
            result = ws.create_schemas_bulk(BulkCreateSchemasParams(
                entries=[SchemaEntry(...)], truncate=True
            ))
            print(f"Added: {result.added}")
            ```
        """
        client = self._require_api_client()
        raw = client.create_schemas_bulk(
            params.model_dump(exclude_none=True, by_alias=True)
        )
        return BulkCreateSchemasResponse.model_validate(raw)

    def update_schema(
        self,
        entity_type: str,
        entity_name: str,
        schema_json: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a single schema definition (merge semantics).

        Args:
            entity_type: Entity type.
            entity_name: Entity name.
            schema_json: Partial JSON Schema to merge with existing.

        Returns:
            Updated schema as dict.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Entity not found or validation error (400, 404).
            RateLimitError: Rate limit exceeded (429).

        Example:
            ```python
            ws = Workspace()
            ws.update_schema("event", "Purchase", {
                "properties": {"tax": {"type": "number"}}
            })
            ```
        """
        client = self._require_api_client()
        return client.update_schema(entity_type, entity_name, schema_json)

    def update_schemas_bulk(
        self,
        params: BulkCreateSchemasParams,
    ) -> list[BulkPatchResult]:
        """Bulk update schemas (merge semantics per entry).

        Args:
            params: Bulk update parameters with entries list.

        Returns:
            List of per-entry results with status ("ok" or "error").

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            RateLimitError: Rate limit exceeded (429).

        Example:
            ```python
            ws = Workspace()
            results = ws.update_schemas_bulk(BulkCreateSchemasParams(
                entries=[SchemaEntry(...)]
            ))
            for r in results:
                print(f"{r.name}: {r.status}")
            ```
        """
        client = self._require_api_client()
        raw_list = client.update_schemas_bulk(
            params.model_dump(exclude_none=True, by_alias=True)
        )
        return [BulkPatchResult.model_validate(r) for r in raw_list]

    def delete_schemas(
        self,
        *,
        entity_type: str | None = None,
        entity_name: str | None = None,
    ) -> DeleteSchemasResponse:
        """Delete schemas by entity type and/or name.

        If both provided, deletes a single schema. If only entity_type,
        deletes all schemas of that type. If neither, deletes all schemas.

        Args:
            entity_type: Filter by entity type.
            entity_name: Filter by entity name (requires entity_type).

        Returns:
            Response with ``delete_count``.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid parameters (400).
            RateLimitError: Rate limit exceeded (429).
            MixpanelHeadlessError: If entity_name is provided without entity_type.

        Example:
            ```python
            ws = Workspace()
            resp = ws.delete_schemas(entity_type="event", entity_name="Purchase")
            print(f"Deleted: {resp.delete_count}")
            ```
        """
        if entity_name is not None and entity_type is None:
            raise MixpanelHeadlessError(
                "entity_name requires entity_type: providing entity_name "
                "without entity_type would delete all schemas",
            )
        client = self._require_api_client()
        raw = client.delete_schemas(entity_type=entity_type, entity_name=entity_name)
        return DeleteSchemasResponse.model_validate(raw)

    # =========================================================================
    # Schema Enforcement (Phase 028)
    # =========================================================================

    def get_schema_enforcement(
        self,
        *,
        fields: str | None = None,
    ) -> SchemaEnforcementConfig:
        """Get current schema enforcement configuration.

        Args:
            fields: Comma-separated field names to return (e.g.,
                "ruleEvent,state"). If None, returns all fields.

        Returns:
            Schema enforcement configuration.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: No enforcement configured (404).

        Example:
            ```python
            ws = Workspace()
            config = ws.get_schema_enforcement()
            print(f"Rule: {config.rule_event}")
            ```
        """
        client = self._require_api_client()
        raw = client.get_schema_enforcement(fields=fields)
        return SchemaEnforcementConfig.model_validate(raw)

    def init_schema_enforcement(
        self,
        params: InitSchemaEnforcementParams,
    ) -> dict[str, Any]:
        """Initialize schema enforcement.

        Args:
            params: Init parameters with rule_event.

        Returns:
            Raw API response as dict.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Already initialized or invalid rule_event (400).

        Example:
            ```python
            ws = Workspace()
            ws.init_schema_enforcement(
                InitSchemaEnforcementParams(rule_event="Warn and Accept")
            )
            ```
        """
        client = self._require_api_client()
        return client.init_schema_enforcement(
            params.model_dump(exclude_none=True, by_alias=True)
        )

    def update_schema_enforcement(
        self,
        params: UpdateSchemaEnforcementParams,
    ) -> dict[str, Any]:
        """Partially update enforcement configuration.

        Args:
            params: Partial update parameters.

        Returns:
            Raw API response as dict.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: No enforcement configured or validation error (400).

        Example:
            ```python
            ws = Workspace()
            ws.update_schema_enforcement(
                UpdateSchemaEnforcementParams(rule_event="Warn and Drop")
            )
            ```
        """
        client = self._require_api_client()
        return client.update_schema_enforcement(
            params.model_dump(exclude_none=True, by_alias=True)
        )

    def replace_schema_enforcement(
        self,
        params: ReplaceSchemaEnforcementParams,
    ) -> dict[str, Any]:
        """Fully replace enforcement configuration.

        Args:
            params: Complete replacement parameters.

        Returns:
            Raw API response as dict.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).

        Example:
            ```python
            ws = Workspace()
            ws.replace_schema_enforcement(ReplaceSchemaEnforcementParams(
                events=[...], common_properties=[...],
                user_properties=[...], rule_event="Warn and Hide",
                notification_emails=["admin@example.com"],
            ))
            ```
        """
        client = self._require_api_client()
        return client.replace_schema_enforcement(
            params.model_dump(exclude_none=True, by_alias=True)
        )

    def delete_schema_enforcement(self) -> dict[str, Any]:
        """Delete enforcement configuration.

        Returns:
            Raw API response as dict.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: No enforcement configured (404).

        Example:
            ```python
            ws = Workspace()
            ws.delete_schema_enforcement()
            ```
        """
        client = self._require_api_client()
        return client.delete_schema_enforcement()

    # =========================================================================
    # Data Auditing (Phase 028)
    # =========================================================================

    def run_audit(self) -> AuditResponse:
        """Run a full data audit (events + properties).

        Returns:
            Audit response with violations and ``computed_at`` timestamp.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: No schemas defined (400).

        Example:
            ```python
            ws = Workspace()
            audit = ws.run_audit()
            for v in audit.violations:
                print(f"{v.violation}: {v.name} ({v.count})")
            ```
        """
        client = self._require_api_client()
        raw = client.run_audit()
        # raw is [violations_list, {"computed_at": ...}]
        if not raw:
            return AuditResponse(violations=[], computed_at="")
        if not isinstance(raw[0], list):
            raise MixpanelHeadlessError(
                f"Unexpected audit response: expected list of violations, "
                f"got {type(raw[0]).__name__}",
            )
        violations = [AuditViolation.model_validate(v) for v in raw[0]]
        metadata = raw[1] if len(raw) > 1 and isinstance(raw[1], dict) else {}
        return AuditResponse(
            violations=violations,
            computed_at=metadata.get("computed_at", ""),
        )

    def run_audit_events_only(self) -> AuditResponse:
        """Run an events-only data audit (faster).

        Returns:
            Audit response with event violations only.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: No schemas defined (400).

        Example:
            ```python
            ws = Workspace()
            audit = ws.run_audit_events_only()
            ```
        """
        client = self._require_api_client()
        raw = client.run_audit_events_only()
        if not raw:
            return AuditResponse(violations=[], computed_at="")
        if not isinstance(raw[0], list):
            raise MixpanelHeadlessError(
                f"Unexpected audit response: expected list of violations, "
                f"got {type(raw[0]).__name__}",
            )
        violations = [AuditViolation.model_validate(v) for v in raw[0]]
        metadata = raw[1] if len(raw) > 1 and isinstance(raw[1], dict) else {}
        return AuditResponse(
            violations=violations,
            computed_at=metadata.get("computed_at", ""),
        )

    # =========================================================================
    # Data Volume Anomalies (Phase 028)
    # =========================================================================

    def list_data_volume_anomalies(
        self,
        *,
        query_params: dict[str, str] | None = None,
    ) -> list[DataVolumeAnomaly]:
        """List detected data volume anomalies.

        Args:
            query_params: Optional filters (status, limit, event_id, etc.).

        Returns:
            List of ``DataVolumeAnomaly`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).

        Example:
            ```python
            ws = Workspace()
            anomalies = ws.list_data_volume_anomalies(
                query_params={"status": "open"}
            )
            ```
        """
        client = self._require_api_client()
        raw_list = client.list_data_volume_anomalies(query_params=query_params)
        return [DataVolumeAnomaly.model_validate(r) for r in raw_list]

    def update_anomaly(
        self,
        params: UpdateAnomalyParams,
    ) -> dict[str, Any]:
        """Update the status of a single anomaly.

        Args:
            params: Update parameters with id, status, and anomaly_class.

        Returns:
            Raw API response as dict.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Anomaly not found or invalid parameters (400).

        Example:
            ```python
            ws = Workspace()
            ws.update_anomaly(UpdateAnomalyParams(
                id=123, status="dismissed", anomaly_class="Event"
            ))
            ```
        """
        client = self._require_api_client()
        return client.update_anomaly(params.model_dump(by_alias=True))

    def bulk_update_anomalies(
        self,
        params: BulkUpdateAnomalyParams,
    ) -> dict[str, Any]:
        """Bulk update anomaly statuses.

        Args:
            params: Bulk update with anomalies list and target status.

        Returns:
            Raw API response as dict.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid parameters (400).

        Example:
            ```python
            ws = Workspace()
            ws.bulk_update_anomalies(BulkUpdateAnomalyParams(
                anomalies=[BulkAnomalyEntry(id=1, anomaly_class="Event")],
                status="dismissed",
            ))
            ```
        """
        client = self._require_api_client()
        return client.bulk_update_anomalies(params.model_dump(by_alias=True))

    # =========================================================================
    # Event Deletion Requests (Phase 028)
    # =========================================================================

    def list_deletion_requests(self) -> list[EventDeletionRequest]:
        """List all event deletion requests.

        Returns:
            List of ``EventDeletionRequest`` objects.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).

        Example:
            ```python
            ws = Workspace()
            for r in ws.list_deletion_requests():
                print(f"{r.event_name}: {r.status}")
            ```
        """
        client = self._require_api_client()
        raw_list = client.list_deletion_requests()
        return [EventDeletionRequest.model_validate(r) for r in raw_list]

    def create_deletion_request(
        self,
        params: CreateDeletionRequestParams,
    ) -> list[EventDeletionRequest]:
        """Create a new event deletion request.

        Args:
            params: Deletion parameters with event_name, from_date,
                to_date, and optional filters.

        Returns:
            Updated full list of deletion requests.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Validation error (400).

        Example:
            ```python
            ws = Workspace()
            requests = ws.create_deletion_request(
                CreateDeletionRequestParams(
                    event_name="Test", from_date="2026-01-01",
                    to_date="2026-01-31",
                )
            )
            ```
        """
        client = self._require_api_client()
        raw_list = client.create_deletion_request(
            params.model_dump(exclude_none=True, by_alias=True)
        )
        return [EventDeletionRequest.model_validate(r) for r in raw_list]

    def cancel_deletion_request(self, request_id: int) -> list[EventDeletionRequest]:
        """Cancel a pending deletion request.

        Args:
            request_id: Deletion request ID to cancel.

        Returns:
            Updated full list of deletion requests.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Request not found or not cancellable (400).

        Example:
            ```python
            ws = Workspace()
            requests = ws.cancel_deletion_request(42)
            ```
        """
        client = self._require_api_client()
        raw_list = client.cancel_deletion_request(request_id)
        return [EventDeletionRequest.model_validate(r) for r in raw_list]

    def preview_deletion_filters(
        self,
        params: PreviewDeletionFiltersParams,
    ) -> list[dict[str, Any]]:
        """Preview what events a deletion filter would match.

        This is a read-only operation that does not modify any data.

        Args:
            params: Preview parameters with event_name, date range,
                and optional filters.

        Returns:
            List of expanded/normalized filters.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Invalid filter parameters (400).

        Example:
            ```python
            ws = Workspace()
            preview = ws.preview_deletion_filters(
                PreviewDeletionFiltersParams(
                    event_name="Test", from_date="2026-01-01",
                    to_date="2026-01-31",
                )
            )
            ```
        """
        client = self._require_api_client()
        return client.preview_deletion_filters(
            params.model_dump(exclude_none=True, by_alias=True)
        )

    # =========================================================================
    # QUERY USER ENGINE
    # =========================================================================

    def _resolve_and_build_user_params(
        self,
        *,
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
        mode: Literal["profiles", "aggregate"] = "aggregate",
        aggregate: Literal[
            "count", "extremes", "percentile", "numeric_summary"
        ] = "count",
        aggregate_property: str | None = None,
        percentile: float | None = None,
        segment_by: list[int] | None = None,
        parallel: bool = False,
        workers: int = 5,
        limit: int | None = 1,
        include_all_users: bool = False,
    ) -> dict[str, Any]:
        """Validate arguments and build engage API params dict.

        Performs two-layer validation (argument-level then param-level)
        and translates high-level Python arguments into the flat dict
        expected by ``export_profiles_page()``.

        Args:
            where: Filter profiles by property values. Accepts a single
                ``Filter``, a list of ``Filter`` objects (AND-combined),
                a raw selector string, or ``None``.
            cohort: Filter by cohort membership. An ``int`` for a saved
                cohort ID, or a ``CohortDefinition`` for an inline
                cohort definition.
            properties: Output properties to include in results.
            sort_by: Property name to sort results by.
            sort_order: Sort direction (``"ascending"`` or ``"descending"``).
            search: Full-text search term applied to profile properties.
            distinct_id: Look up a single user by distinct ID.
            distinct_ids: Batch look up multiple users by distinct IDs.
            group_id: Query group profiles instead of user profiles.
            as_of: Point-in-time query. An ISO date string (``YYYY-MM-DD``)
                is converted to a Unix timestamp; an ``int`` is passed
                through directly.
            mode: Output mode (``"profiles"`` or ``"aggregate"``).
            aggregate: Aggregation function for aggregate mode. One of
                ``"count"`` (profile count), ``"extremes"`` (min/max),
                ``"percentile"`` (Nth percentile), or
                ``"numeric_summary"`` (count/mean/var/sum_of_squares).
            aggregate_property: Property to aggregate on (required for
                non-count aggregations).
            percentile: Percentile value (0-100 exclusive). Required
                when ``aggregate="percentile"``.
            segment_by: Cohort IDs for segmented aggregation.
            parallel: Whether to enable concurrent page fetching.
            workers: Maximum concurrent workers for parallel fetching.
            limit: Maximum profiles to return. Defaults to ``1``. Used
                for argument-level validation (U3); not included in the
                returned params dict.
            include_all_users: Include non-members in cohort query results.

        Returns:
            Engage API params dict ready for ``export_profiles_page()``.

        Raises:
            BookmarkValidationError: If any validation rule fails at
                either the argument level (U1-U28) or the param level
                (UP1-UP4).

        Example:
            ```python
            ws = Workspace()
            params = ws._resolve_and_build_user_params(
                where=Filter.equals("plan", "premium"),
                sort_by="ltv",
            )
            # {"where": 'properties["plan"] == "premium"',
            #  "sort_key": 'properties["ltv"]',
            #  "sort_order": "descending"}
            ```
        """
        # Type guard for where
        if where is not None and not isinstance(where, (Filter, list, str)):
            raise BookmarkValidationError(
                errors=[
                    ValidationError(
                        path="where",
                        message=(
                            f"where must be a Filter, list[Filter], str, or None "
                            f"(got {type(where).__name__})"
                        ),
                        code="U9",
                    )
                ],
            )

        # Layer 1: argument-level validation
        arg_errors = validate_user_args(
            where=where,
            cohort=cohort,
            properties=properties,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            search=search,
            distinct_id=distinct_id,
            distinct_ids=distinct_ids,
            group_id=group_id,
            as_of=as_of,
            mode=mode,
            aggregate=aggregate,
            aggregate_property=aggregate_property,
            percentile=percentile,
            segment_by=segment_by,
            parallel=parallel,
            workers=workers,
            include_all_users=include_all_users,
        )
        error_severity = [e for e in arg_errors if e.severity == "error"]
        if error_severity:
            raise BookmarkValidationError(errors=error_severity)

        # Build params dict
        params: dict[str, Any] = {}

        # --- where handling ---
        cohort_from_filter: Filter | None = None
        if isinstance(where, str):
            params["where"] = where
        elif isinstance(where, (Filter, list)):
            filters_list = [where] if isinstance(where, Filter) else where
            remaining, cohort_from_filter = extract_cohort_filter(filters_list)
            if remaining:
                try:
                    selector = filters_to_selector(remaining)
                except ValueError as exc:
                    raise BookmarkValidationError(
                        errors=[
                            ValidationError(
                                path="where",
                                message=str(exc),
                                code="U_FILTER",
                            )
                        ]
                    ) from exc
                if selector:
                    params["where"] = selector

        # --- cohort handling ---
        if cohort is not None:
            if isinstance(cohort, int):
                params["filter_by_cohort"] = json.dumps({"id": cohort})
            elif isinstance(cohort, CohortDefinition):
                params["filter_by_cohort"] = json.dumps(
                    {"raw_cohort": _sanitize_raw_cohort(cohort.to_dict())}
                )
        elif cohort_from_filter is not None:
            # Extract cohort ID from the Filter.in_cohort() value
            # Structure: [{"cohort": {"id": N, "negated": bool, "name": str}}]
            raw_value = cohort_from_filter._value
            if not isinstance(raw_value, list) or len(raw_value) == 0:
                raise BookmarkValidationError(
                    errors=[
                        ValidationError(
                            path="where",
                            message=(
                                "Expected non-empty list from Filter.in_cohort() "
                                f"value, got {type(raw_value).__name__}"
                            ),
                            code="U_COHORT",
                        )
                    ]
                )
            first_item = raw_value[0]
            if not isinstance(first_item, dict):
                raise BookmarkValidationError(
                    errors=[
                        ValidationError(
                            path="where",
                            message=(
                                "Expected dict in Filter.in_cohort() value, "
                                f"got {type(first_item).__name__}"
                            ),
                            code="U_COHORT",
                        )
                    ]
                )
            if "cohort" not in first_item:
                raise BookmarkValidationError(
                    errors=[
                        ValidationError(
                            path="where",
                            message=(
                                "Filter.in_cohort() value missing 'cohort' "
                                f"key: {first_item!r}"
                            ),
                            code="U_COHORT",
                        )
                    ]
                )
            cohort_wrapper: dict[str, Any] = first_item["cohort"]
            if "id" in cohort_wrapper:
                params["filter_by_cohort"] = json.dumps({"id": cohort_wrapper["id"]})
            elif "raw_cohort" in cohort_wrapper:
                params["filter_by_cohort"] = json.dumps(
                    {"raw_cohort": cohort_wrapper["raw_cohort"]}
                )
            else:
                raise BookmarkValidationError(
                    errors=[
                        ValidationError(
                            path="where",
                            message=(
                                "Filter.in_cohort() value has no 'id' or "
                                f"'raw_cohort' key: {cohort_wrapper!r}"
                            ),
                            code="U_COHORT",
                        )
                    ]
                )

        # --- properties → output_properties ---
        if properties is not None:
            params["output_properties"] = json.dumps(properties)

        # --- sort_by → sort_key ---
        if sort_by is not None:
            escaped_sort = sort_by.replace("\\", "\\\\").replace('"', '\\"')
            params["sort_key"] = f'properties["{escaped_sort}"]'
            params["sort_order"] = sort_order

        # --- as_of → as_of_timestamp ---
        if as_of is not None:
            if isinstance(as_of, str):
                params["as_of_timestamp"] = calendar.timegm(
                    _date.fromisoformat(as_of).timetuple()
                )
            elif isinstance(as_of, int):
                params["as_of_timestamp"] = as_of

        # --- distinct_id ---
        if distinct_id is not None:
            params["distinct_id"] = distinct_id

        # --- distinct_ids ---
        if distinct_ids is not None:
            params["distinct_ids"] = json.dumps(distinct_ids)

        # --- group_id → data_group_id ---
        if group_id is not None:
            params["data_group_id"] = group_id

        # --- search ---
        if search is not None:
            params["search"] = search

        # --- include_all_users (only when cohort is set) ---
        if "filter_by_cohort" in params:
            params["include_all_users"] = include_all_users

        # --- aggregate mode ---
        if mode == "aggregate":
            if aggregate == "count":
                action = "count()"
            else:
                escaped_agg_prop = (
                    aggregate_property.replace("\\", "\\\\").replace('"', '\\"')
                    if aggregate_property is not None
                    else ""
                )
                if aggregate == "percentile":
                    action = (
                        f'percentile(properties["{escaped_agg_prop}"], {percentile})'
                    )
                else:
                    action = f'{aggregate}(properties["{escaped_agg_prop}"])'
            params["action"] = action
            if segment_by is not None:
                params["segment_by_cohorts"] = json.dumps(
                    {str(sid): True for sid in segment_by}
                )

        # Layer 2: param-level validation
        param_errors = validate_user_params(params)
        if param_errors:
            raise BookmarkValidationError(errors=param_errors)

        return params

    def _execute_user_query_sequential(
        self,
        params: dict[str, Any],
        limit: int | None,
    ) -> tuple[list[dict[str, Any]], int, str, dict[str, Any]]:
        """Execute a user profile query with sequential page fetching.

        Fetches profiles from the Engage API one page at a time,
        collecting results until the requested limit is reached or
        all pages are exhausted.

        Args:
            params: Engage API params dict from
                ``_resolve_and_build_user_params()``.
            limit: Maximum number of profiles to collect. ``None`` means
                fetch all matching profiles.

        Returns:
            Tuple of ``(profiles, total, computed_at, meta)`` where:

            - **profiles**: List of normalized profile dicts (truncated
              to *limit*).
            - **total**: Number of profiles returned (equals
              ``len(profiles)``).
            - **computed_at**: ISO timestamp of when the query was
              executed.
            - **meta**: Execution metadata dict with ``session_id``,
              ``pages_fetched``, and ``parallel`` keys.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            RateLimitError: API rate limit exceeded (429).
            APIError: Other API communication errors.

        Example:
            ```python
            params = ws._resolve_and_build_user_params(
                where=Filter.equals("plan", "premium"),
            )
            profiles, total, computed_at, meta = (
                ws._execute_user_query_sequential(params, limit=10)
            )
            ```
        """
        api_client = self._require_api_client()

        # Reuse _build_page_kwargs for params→kwargs translation.
        # Pass limit server-side for efficient fetching.
        # We return len(profiles) as total — the count of profiles in
        # this response, not the API's total field (which reflects
        # the full matching population). Use mode="aggregate",
        # aggregate="count" for the full count.
        api_kwargs = self._build_page_kwargs(params)
        api_kwargs["limit"] = limit

        result = api_client.export_profiles_page(page=0, **api_kwargs)
        profiles: list[dict[str, Any]] = [transform_profile(p) for p in result.profiles]
        session_id = result.session_id
        pages_fetched = 1

        # Check if we already have enough
        if limit is not None and len(profiles) >= limit:
            profiles = profiles[:limit]
        elif result.has_more and result.profiles:
            # Paginate for more (guard: stop if page returns no profiles)
            current_page = 0
            while result.has_more:
                if limit is not None and len(profiles) >= limit:
                    break
                current_page += 1
                result = api_client.export_profiles_page(
                    page=current_page,
                    session_id=session_id,
                    **api_kwargs,
                )
                if not result.profiles:
                    break
                profiles.extend(transform_profile(p) for p in result.profiles)
                pages_fetched += 1

            # Slice with None returns all profiles (intentional for limit=None)
            profiles = profiles[:limit]

        computed_at = datetime.now(timezone.utc).isoformat()
        meta: dict[str, Any] = {
            "session_id": session_id,
            "pages_fetched": pages_fetched,
            "parallel": False,
        }

        return profiles, len(profiles), computed_at, meta

    def query_user(
        self,
        *,
        where: Filter | list[Filter] | str | None = None,
        cohort: int | CohortDefinition | None = None,
        properties: list[str] | None = None,
        sort_by: str | None = None,
        sort_order: Literal["ascending", "descending"] = "descending",
        limit: int | None = 1,
        search: str | None = None,
        distinct_id: str | None = None,
        distinct_ids: list[str] | None = None,
        group_id: str | None = None,
        as_of: str | int | None = None,
        mode: Literal["profiles", "aggregate"] = "aggregate",
        aggregate: Literal[
            "count", "extremes", "percentile", "numeric_summary"
        ] = "count",
        aggregate_property: str | None = None,
        percentile: float | None = None,
        segment_by: list[int] | None = None,
        parallel: bool = False,
        workers: int = 5,
        include_all_users: bool = False,
    ) -> UserQueryResult:
        """Query user profiles from Mixpanel's Engage API.

        Provides a high-level interface to Mixpanel's Engage API for
        querying user profiles with typed filters, cohort membership,
        sorting, and pagination. Results are returned as a structured
        ``UserQueryResult`` with lazy DataFrame conversion.

        Args:
            where: Filter profiles by property values. Accepts a single
                ``Filter``, a list of ``Filter`` objects (AND-combined),
                a raw selector string, or ``None``.
            cohort: Filter by cohort membership. An ``int`` for a saved
                cohort ID, or a ``CohortDefinition`` for an inline
                cohort definition.
            properties: Output properties to include in results.
            sort_by: Property name to sort results by.
            sort_order: Sort direction (``"ascending"`` or ``"descending"``).
            limit: Maximum profiles to return. Defaults to ``1`` for
                quick exploration. Use ``None`` to fetch all matching
                profiles.
            search: Full-text search term applied to profile properties.
            distinct_id: Look up a single user by distinct ID.
            distinct_ids: Batch look up multiple users by distinct IDs.
            group_id: Query group profiles instead of user profiles.
            as_of: Point-in-time query. An ISO date string (``YYYY-MM-DD``)
                is converted to a Unix timestamp; an ``int`` is passed
                through directly.
            mode: Output mode (``"profiles"`` or ``"aggregate"``).
            aggregate: Aggregation function for aggregate mode. One of
                ``"count"`` (profile count), ``"extremes"`` (min/max),
                ``"percentile"`` (Nth percentile), or
                ``"numeric_summary"`` (count/mean/var/sum_of_squares).
            aggregate_property: Property to aggregate on (required for
                non-count aggregations).
            percentile: Percentile value (0-100 exclusive). Required
                when ``aggregate="percentile"``.
            segment_by: Cohort IDs for segmented aggregation.
            parallel: Whether to enable concurrent page fetching.
            workers: Maximum concurrent workers for parallel fetching.
            include_all_users: Include non-members in cohort query results.

        Returns:
            ``UserQueryResult`` with profiles, total count, DataFrame,
            and execution metadata.

        Raises:
            BookmarkValidationError: If any validation rule fails.
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            RateLimitError: API rate limit exceeded (429).
            APIError: Other API communication errors.

        Example:
            ```python
            ws = Workspace()

            # Quick peek at one profile
            result = ws.query_user()
            print(result.df)

            # Filter premium users, sorted by LTV
            result = ws.query_user(
                where=Filter.equals("plan", "premium"),
                sort_by="ltv",
                sort_order="descending",
                limit=100,
            )
            print(f"Total premium users: {result.total}")
            print(result.df.head())

            # Batch lookup specific users
            result = ws.query_user(
                distinct_ids=["user_001", "user_002"],
                limit=None,
            )
            ```
        """
        params = self._resolve_and_build_user_params(
            where=where,
            cohort=cohort,
            properties=properties,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            search=search,
            distinct_id=distinct_id,
            distinct_ids=distinct_ids,
            group_id=group_id,
            as_of=as_of,
            mode=mode,
            aggregate=aggregate,
            aggregate_property=aggregate_property,
            percentile=percentile,
            segment_by=segment_by,
            parallel=parallel,
            workers=workers,
            include_all_users=include_all_users,
        )

        # Route by mode
        if mode == "aggregate":
            aggregate_data, total, computed_at, meta = self._execute_user_aggregate(
                params
            )
            return UserQueryResult(
                computed_at=computed_at,
                total=total,
                profiles=[],
                params=params,
                meta=meta,
                mode="aggregate",
                aggregate_data=aggregate_data,
            )

        # Profiles mode — choose sequential or parallel
        if parallel and limit != 1:
            profiles, total, computed_at, meta = self._execute_user_query_parallel(
                params, limit, workers
            )
        else:
            if parallel and limit == 1:
                logger.debug("parallel=True ignored: limit=1 uses sequential path")
            profiles, total, computed_at, meta = self._execute_user_query_sequential(
                params, limit
            )

        return UserQueryResult(
            computed_at=computed_at,
            total=total,
            profiles=profiles,
            params=params,
            meta=meta,
            mode="profiles",
            aggregate_data=None,
        )

    def build_user_params(
        self,
        *,
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
        mode: Literal["profiles", "aggregate"] = "aggregate",
        aggregate: Literal[
            "count", "extremes", "percentile", "numeric_summary"
        ] = "count",
        aggregate_property: str | None = None,
        percentile: float | None = None,
        segment_by: list[int] | None = None,
        limit: int | None = 1,
        parallel: bool = False,
        workers: int = 5,
        include_all_users: bool = False,
    ) -> dict[str, Any]:
        """Build engage API params without executing a query.

        Validates arguments and constructs the params dict that would be
        sent to the Engage API, without actually making an API call.
        Useful for debugging, testing, and inspecting the generated
        params before execution.

        Args:
            where: Filter profiles by property values. Accepts a single
                ``Filter``, a list of ``Filter`` objects (AND-combined),
                a raw selector string, or ``None``.
            cohort: Filter by cohort membership. An ``int`` for a saved
                cohort ID, or a ``CohortDefinition`` for an inline
                cohort definition.
            properties: Output properties to include in results.
            sort_by: Property name to sort results by.
            sort_order: Sort direction (``"ascending"`` or ``"descending"``).
            search: Full-text search term applied to profile properties.
            distinct_id: Look up a single user by distinct ID.
            distinct_ids: Batch look up multiple users by distinct IDs.
            group_id: Query group profiles instead of user profiles.
            as_of: Point-in-time query. An ISO date string (``YYYY-MM-DD``)
                is converted to a Unix timestamp; an ``int`` is passed
                through directly.
            mode: Output mode (``"profiles"`` or ``"aggregate"``).
            aggregate: Aggregation function for aggregate mode. One of
                ``"count"`` (profile count), ``"extremes"`` (min/max),
                ``"percentile"`` (Nth percentile), or
                ``"numeric_summary"`` (count/mean/var/sum_of_squares).
            aggregate_property: Property to aggregate on (required for
                non-count aggregations).
            percentile: Percentile value (0-100 exclusive). Required
                when ``aggregate="percentile"``.
            segment_by: Cohort IDs for segmented aggregation.
            limit: Maximum profiles to return. Defaults to ``1``. Used
                for argument-level validation (U3); not included in the
                returned params dict.
            parallel: Whether to enable concurrent page fetching.
                Accepted for signature compatibility with ``query_user()``
                but has no effect on the returned params dict.
            workers: Maximum concurrent workers for parallel fetching.
                Accepted for signature compatibility with ``query_user()``
                but has no effect on the returned params dict.
            include_all_users: Include non-members in cohort query results.

        Returns:
            Engage API params dict. Does not include pagination params
            (``page``, ``session_id``) or ``limit``, which are added at
            execution time by ``query_user()``.

        Raises:
            BookmarkValidationError: If any validation rule fails at
                either the argument level (U1-U28) or the param level
                (UP1-UP4).

        Example:
            ```python
            ws = Workspace()
            params = ws.build_user_params(
                where=Filter.equals("plan", "premium"),
                sort_by="ltv",
            )
            print(params)
            # {"where": 'properties["plan"] == "premium"',
            #  "sort_key": 'properties["ltv"]',
            #  "sort_order": "descending"}
            ```
        """
        return self._resolve_and_build_user_params(
            where=where,
            cohort=cohort,
            properties=properties,
            sort_by=sort_by,
            sort_order=sort_order,
            search=search,
            distinct_id=distinct_id,
            distinct_ids=distinct_ids,
            group_id=group_id,
            as_of=as_of,
            mode=mode,
            aggregate=aggregate,
            aggregate_property=aggregate_property,
            percentile=percentile,
            segment_by=segment_by,
            limit=limit,
            parallel=parallel,
            workers=workers,
            include_all_users=include_all_users,
        )

    # =========================================================================
    # User Query — Aggregate Execution (T018)
    # =========================================================================

    def _execute_user_aggregate(
        self,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any] | int | float | None, int, str, dict[str, Any]]:
        """Execute an aggregate query via the Engage stats endpoint.

        Calls ``api_client.engage_stats()`` with the appropriate parameters
        and parses the response into a structured tuple.

        Args:
            params: Engage API params dict from
                ``_resolve_and_build_user_params()``.

        Returns:
            Tuple of (aggregate_data, total, computed_at, meta) where
            aggregate_data is the raw result (scalar or dict), total is
            the count, computed_at is the ISO timestamp, and meta has
            execution metadata.

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            RateLimitError: API rate limit exceeded (429).
            APIError: Other API communication errors.
        """
        api_client = self._require_api_client()

        stats_kwargs: dict[str, Any] = {}
        if "where" in params:
            stats_kwargs["where"] = params["where"]
        if "action" in params:
            stats_kwargs["action"] = params["action"]
        if "filter_by_cohort" in params:
            stats_kwargs["filter_by_cohort"] = params["filter_by_cohort"]
        if "segment_by_cohorts" in params:
            raw = params["segment_by_cohorts"]
            stats_kwargs["segment_by_cohorts"] = (
                json.loads(raw) if isinstance(raw, str) else raw
            )
        if "data_group_id" in params:
            stats_kwargs["group_id"] = params["data_group_id"]
        if "as_of_timestamp" in params:
            stats_kwargs["as_of_timestamp"] = params["as_of_timestamp"]
        if "include_all_users" in params:
            stats_kwargs["include_all_users"] = params["include_all_users"]

        response = api_client.engage_stats(**stats_kwargs)

        aggregate_data = response.get("results")
        computed_at = response.get(
            "computed_at", datetime.now(timezone.utc).isoformat()
        )
        if isinstance(aggregate_data, (int, float)):
            total = int(aggregate_data) if params.get("action") == "count()" else 0
        else:
            total = 0

        action = params.get("action", "count()")
        segmented = "segment_by_cohorts" in params
        meta: dict[str, Any] = {"action": action, "segmented": segmented}

        return aggregate_data, total, computed_at, meta

    # =========================================================================
    # User Query — Parallel Execution (T022)
    # =========================================================================

    def _execute_user_query_parallel(
        self,
        params: dict[str, Any],
        limit: int | None,
        workers: int,
    ) -> tuple[list[dict[str, Any]], int, str, dict[str, Any]]:
        """Fetch profiles with concurrent page retrieval.

        Fetches page 0 sequentially for metadata, then dispatches
        remaining pages via ``ThreadPoolExecutor``. Failed pages are
        recorded in metadata rather than aborting the query.

        Args:
            params: Engage API params dict.
            limit: Maximum profiles to return, or ``None`` for all.
            workers: Maximum concurrent workers (capped at 5).

        Returns:
            Tuple of (profiles, total, computed_at, meta).

        Raises:
            ConfigError: If credentials are not available.
            AuthenticationError: Invalid credentials (401).
            RateLimitError: API rate limit exceeded (429).
            ServerError: Mixpanel server error (5xx).
            QueryError: Query execution failed (400).

        Example:
            ```python
            profiles, total, ts, meta = ws._execute_user_query_parallel(
                params={"where": 'properties["plan"] == "premium"'},
                limit=5000,
                workers=3,
            )
            ```
        """
        api_client = self._require_api_client()
        capped_workers = min(workers, 5)
        page_kwargs = self._build_page_kwargs(params)

        # Page 0: get metadata
        page0 = api_client.export_profiles_page(page=0, **page_kwargs)
        total = page0.total
        page_size = page0.page_size or 1000
        session_id = page0.session_id
        computed_at = datetime.now(timezone.utc).isoformat()

        all_profiles = [transform_profile(p) for p in page0.profiles]

        if limit is None:
            pages_needed = math.ceil(total / page_size)
        else:
            # Cap by total to avoid fetching empty pages when limit > total
            effective = min(limit, total) if total > 0 else limit
            pages_needed = math.ceil(effective / page_size)

        # Single page — skip parallel overhead
        if pages_needed <= 1 or not page0.has_more:
            all_profiles = all_profiles[:limit]
            return (
                all_profiles,
                len(all_profiles),
                computed_at,
                {
                    "session_id": session_id,
                    "pages_fetched": 1,
                    "failed_pages": [],
                    "parallel": True,
                    "workers": capped_workers,
                },
            )

        if pages_needed > 48:
            logger.warning(
                "Fetching %d pages may trigger rate limiting "
                "(engage API allows ~60 queries/hour).",
                pages_needed,
            )

        failed_pages: list[int] = []
        page_results: dict[int, list[dict[str, Any]]] = {}

        def _fetch_page(
            page_num: int,
        ) -> tuple[int, list[dict[str, Any]]]:
            """Fetch and normalize a single page."""
            result = api_client.export_profiles_page(
                page=page_num,
                session_id=session_id,
                **page_kwargs,
            )
            return page_num, [transform_profile(p) for p in result.profiles]

        with ThreadPoolExecutor(max_workers=capped_workers) as executor:
            futures = {
                executor.submit(_fetch_page, p): p for p in range(1, pages_needed)
            }
            for future in as_completed(futures):
                page_num = futures[future]
                try:
                    pnum, profiles = future.result()
                    page_results[pnum] = profiles
                except (
                    AuthenticationError,
                    RateLimitError,
                    ServerError,
                    QueryError,
                ):
                    for f in futures:
                        f.cancel()
                    raise
                except Exception as exc:
                    logger.warning(
                        "Failed to fetch page %d (%s: %s), "
                        "continuing with partial results",
                        page_num,
                        type(exc).__name__,
                        exc,
                        exc_info=True,
                    )
                    failed_pages.append(page_num)

        for p in sorted(page_results.keys()):
            all_profiles.extend(page_results[p])

        all_profiles = all_profiles[:limit]

        return (
            all_profiles,
            len(all_profiles),
            computed_at,
            {
                "session_id": session_id,
                "pages_fetched": pages_needed - len(failed_pages),
                "failed_pages": sorted(failed_pages),
                "parallel": True,
                "workers": capped_workers,
            },
        )

    def _build_page_kwargs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Extract export_profiles_page kwargs from engage params dict.

        Args:
            params: Engage API params dict.

        Returns:
            Keyword arguments for ``export_profiles_page()``.

        Example:
            ```python
            kwargs = ws._build_page_kwargs({"where": 'properties["x"] == 1'})
            # {"where": 'properties["x"] == 1'}
            ```
        """
        kwargs: dict[str, Any] = {}
        if "where" in params:
            kwargs["where"] = params["where"]
        if "output_properties" in params:
            val = params["output_properties"]
            kwargs["output_properties"] = (
                json.loads(val) if isinstance(val, str) else val
            )
        if "sort_key" in params:
            kwargs["sort_key"] = params["sort_key"]
        if "sort_order" in params:
            kwargs["sort_order"] = params["sort_order"]
        if "search" in params:
            kwargs["search"] = params["search"]
        if "filter_by_cohort" in params:
            kwargs["filter_by_cohort"] = params["filter_by_cohort"]
        if "data_group_id" in params:
            kwargs["group_id"] = params["data_group_id"]
        if "as_of_timestamp" in params:
            kwargs["as_of_timestamp"] = params["as_of_timestamp"]
        if "include_all_users" in params:
            kwargs["include_all_users"] = params["include_all_users"]
        if "distinct_id" in params:
            kwargs["distinct_id"] = params["distinct_id"]
        if "distinct_ids" in params:
            val = params["distinct_ids"]
            kwargs["distinct_ids"] = json.loads(val) if isinstance(val, str) else val
        return kwargs

    # =========================================================================
    # BUSINESS CONTEXT
    # =========================================================================
    # Markdown documentation that grounds AI assistants in the
    # organization's structure and goals. Two scopes:
    #   - "organization": shared across all projects
    #   - "project":      specific to the active project
    # Backed by /api/app/projects/{pid}/business-context and
    # /api/app/organizations/{org_id}/business-context. The /chain
    # endpoint returns both at once. Server enforces a 50,000-char limit
    # (mirrored client-side as BUSINESS_CONTEXT_MAX_CHARS).

    @staticmethod
    def _validate_level(level: str) -> None:
        """Reject any ``level`` value other than the two documented literals.

        Python's ``Literal[...]`` type annotations are erased at runtime,
        so without this check a caller passing ``level="org"`` would
        silently take the project-scope branch. We validate explicitly
        so the error surfaces at the call site.

        Args:
            level: The ``level`` argument from a public business-context
                method.

        Raises:
            ValueError: ``level`` is not ``"organization"`` or
                ``"project"``.
        """
        if level not in ("organization", "project"):
            raise ValueError(
                f"level must be 'organization' or 'project', got {level!r}"
            )

    def _resolve_organization_id(self, explicit: int | None = None) -> int:
        """Resolve the organization ID for org-scoped business context calls.

        Resolution order:

        1. ``explicit`` argument when not ``None`` (no I/O).
        2. ``MeResponse.projects[<active project id>].organization_id``
           via the cached ``/me`` response (24h ``MeCache``). This step
           may trigger a ``/me`` API call when both in-memory and disk
           caches miss.
        3. The single org in ``MeResponse.organizations`` when exactly
           one is accessible.
        4. Raise ``WorkspaceScopeError`` (``code="ORGANIZATION_AMBIGUOUS"``)
           listing the available org IDs.

        Args:
            explicit: Optional explicit organization ID. When provided,
                no /me lookup is performed and this value is returned
                as-is.

        Returns:
            Numeric organization ID for use in
            ``/organizations/{org_id}/business-context`` paths.

        Raises:
            ConfigError: ``/me`` cannot be fetched (e.g. credentials
                lack /me permission).
            WorkspaceScopeError: ``explicit`` was not provided AND the
                current project is not present in ``/me`` AND there is
                not exactly one accessible organization to fall back to.
        """
        if explicit is not None:
            return explicit
        me = self._me_svc.fetch()
        project_info = me.projects.get(self._session.project.id)
        if project_info is not None:
            return project_info.organization_id
        if len(me.organizations) == 1:
            sole = next(iter(me.organizations.values()))
            return sole.id
        raise WorkspaceScopeError(
            f"Cannot auto-resolve organization for project "
            f"{self._session.project.id!r}. Pass organization_id explicitly. "
            f"Available organizations: {sorted(me.organizations.keys())}",
            code="ORGANIZATION_AMBIGUOUS",
            details={
                "project_id": self._session.project.id,
                "available_organizations": sorted(me.organizations.keys()),
            },
        )

    def _cached_organization_id(self) -> int | None:
        """Return ``organization_id`` from cached ``/me``, never fetching.

        Used by ``get_business_context_chain()`` to enrich the response
        with ``organization_id`` *only when free* — preserving the
        chain endpoint's single-network-round-trip guarantee. If the
        cache is cold (neither in-memory nor on-disk), returns ``None``
        rather than triggering a ``/me`` API call. Callers that need a
        guaranteed org ID should use ``get_business_context(level=
        "organization")`` instead.

        Returns:
            Cached organization ID for the active project, the sole
            accessible org if exactly one exists, or ``None`` when the
            cache is cold or the project is not in the cached ``/me``
            and there are multiple orgs.
        """
        if self._me_service is None:
            return None
        me = self._me_service.peek()
        if me is None:
            return None
        project_info = me.projects.get(self._session.project.id)
        if project_info is not None:
            return int(project_info.organization_id)
        if len(me.organizations) == 1:
            sole = next(iter(me.organizations.values()))
            return int(sole.id)
        return None

    @staticmethod
    def _require_str_field(raw: dict[str, Any], key: str, *, method: str) -> str:
        """Read a required string field from an App API response.

        Treats a missing key as a server-contract violation (raises
        ``MixpanelHeadlessError``) rather than silently substituting the
        empty string, which would mask renames or schema drift on the
        server side.

        Args:
            raw: The unwrapped ``results`` dict returned by ``app_request``.
            key: Field name expected in ``raw``.
            method: Caller method name, embedded in the error message.

        Returns:
            The string value at ``raw[key]``. Empty strings are valid
            (unset business context returns ``""``).

        Raises:
            MixpanelHeadlessError: ``key`` is absent from ``raw`` or its
                value is not a string.
        """
        if key not in raw:
            raise MixpanelHeadlessError(
                f"Unexpected response from {method}: missing required field {key!r}",
                details={"missing_field": key, "response": raw},
            )
        value = raw[key]
        if not isinstance(value, str):
            raise MixpanelHeadlessError(
                f"Unexpected response from {method}: field {key!r} "
                f"is {type(value).__name__}, expected str",
                details={"field": key, "response": raw},
            )
        return value

    def get_business_context(
        self,
        *,
        level: Literal["organization", "project"] = "project",
        organization_id: int | None = None,
    ) -> BusinessContext:
        """Read business context content at the given scope.

        Calls ``GET /api/app/projects/{pid}/business-context`` (when
        ``level="project"``) or
        ``GET /api/app/organizations/{org_id}/business-context``
        (when ``level="organization"``). Returns a populated
        ``BusinessContext`` with ``content=""`` when no context is set.

        Args:
            level: ``"project"`` (default) reads the project-level
                context for the active session's project.
                ``"organization"`` reads the org-level context shared
                across all projects in the organization.
            organization_id: Optional explicit org ID, only honored
                when ``level="organization"``. When omitted, the org ID
                is auto-resolved from the cached ``/me`` response
                (which may trigger a ``/me`` API call when the cache
                is cold).

        Returns:
            ``BusinessContext`` whose ``content`` reflects the server's
            current state. ``organization_id`` is populated for
            org-level returns; ``project_id`` for project-level.

        Raises:
            ValueError: ``level`` is not ``"organization"`` or ``"project"``.
            ConfigError: Credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: API error (400, 403, 404).
            ServerError: Server-side errors (5xx).
            WorkspaceScopeError: ``level="organization"`` and the org
                ID could not be auto-resolved.
            MixpanelHeadlessError: API response is missing the ``content``
                field.

        Example:
            ```python
            ws = Workspace()
            project_ctx = ws.get_business_context(level="project")
            org_ctx = ws.get_business_context(
                level="organization", organization_id=100,
            )
            print(project_ctx.content)
            ```
        """
        self._validate_level(level)
        client = self._require_api_client()
        if level == "organization":
            org_id = self._resolve_organization_id(organization_id)
            raw = client.get_business_context(organization_id=org_id)
            return BusinessContext(
                level="organization",
                content=self._require_str_field(
                    raw,
                    "content",
                    method="get_business_context",
                ),
                organization_id=org_id,
            )
        raw = client.get_business_context()
        return BusinessContext(
            level="project",
            content=self._require_str_field(
                raw,
                "content",
                method="get_business_context",
            ),
            project_id=self._session.project.id,
        )

    def set_business_context(
        self,
        content: str,
        *,
        level: Literal["organization", "project"] = "project",
        organization_id: int | None = None,
    ) -> BusinessContext:
        """Replace business context content at the given scope.

        Validates ``len(content) <= BUSINESS_CONTEXT_MAX_CHARS`` (50,000)
        client-side BEFORE the HTTP call so callers fail fast and avoid
        a wasted round-trip to the server (which enforces the same limit
        and returns 400 above it). Then calls
        ``PUT /api/app/projects/{pid}/business-context`` (project) or
        ``PUT /api/app/organizations/{org_id}/business-context`` (org).

        The PUT is full-replace — pass an empty string to clear (or use
        ``clear_business_context`` for clarity).

        Args:
            content: New markdown content. Empty string clears the
                context at this scope.
            level: ``"project"`` (default) or ``"organization"``.
            organization_id: Optional explicit org ID, only honored
                when ``level="organization"``. Auto-resolved from
                ``/me`` when omitted.

        Returns:
            ``BusinessContext`` echoing the server's saved content.

        Raises:
            ValueError: ``level`` is not ``"organization"`` or ``"project"``.
            BusinessContextValidationError: ``len(content) > 50_000``
                (client-side check, no HTTP call made).
            ConfigError: Credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Caller lacks ``edit_project_info`` permission
                (403) or other API error (400).
            ServerError: Server-side errors (5xx).
            WorkspaceScopeError: ``level="organization"`` and the org
                ID could not be auto-resolved.
            MixpanelHeadlessError: API response is missing the ``content``
                field.

        Example:
            ```python
            ws = Workspace()
            ws.set_business_context("# Acme Corp\\n...", level="project")
            ws.set_business_context(
                "# Org-wide context", level="organization",
            )
            ```
        """
        self._validate_level(level)
        if len(content) > BUSINESS_CONTEXT_MAX_CHARS:
            raise BusinessContextValidationError(
                f"content exceeds maximum length of "
                f"{BUSINESS_CONTEXT_MAX_CHARS} characters (got {len(content)})",
                details={
                    "length": len(content),
                    "max": BUSINESS_CONTEXT_MAX_CHARS,
                },
            )
        client = self._require_api_client()
        if level == "organization":
            org_id = self._resolve_organization_id(organization_id)
            raw = client.set_business_context(content, organization_id=org_id)
            return BusinessContext(
                level="organization",
                content=self._require_str_field(
                    raw,
                    "content",
                    method="set_business_context",
                ),
                organization_id=org_id,
            )
        raw = client.set_business_context(content)
        return BusinessContext(
            level="project",
            content=self._require_str_field(
                raw,
                "content",
                method="set_business_context",
            ),
            project_id=self._session.project.id,
        )

    def clear_business_context(
        self,
        *,
        level: Literal["organization", "project"] = "project",
        organization_id: int | None = None,
    ) -> BusinessContext:
        """Clear business context at the given scope.

        Convenience wrapper that calls
        ``set_business_context("", level=..., organization_id=...)``.
        Useful for documenting intent — equivalent to passing an empty
        string explicitly.

        Args:
            level: ``"project"`` (default) or ``"organization"``.
            organization_id: Optional explicit org ID for
                ``level="organization"``.

        Returns:
            ``BusinessContext`` with ``content=""`` (the cleared state
            echoed back from the server).

        Raises:
            ValueError: ``level`` is not ``"organization"`` or ``"project"``.
            ConfigError: Credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Caller lacks ``edit_project_info`` permission
                (403) or other API error (400).
            ServerError: Server-side errors (5xx).
            WorkspaceScopeError: ``level="organization"`` and the org
                ID could not be auto-resolved.

        Example:
            ```python
            ws = Workspace()
            ws.clear_business_context(level="project")
            ```
        """
        return self.set_business_context(
            "",
            level=level,
            organization_id=organization_id,
        )

    def get_business_context_chain(self) -> BusinessContextChain:
        """Read both organization and project business context together.

        Issues exactly one App API request to
        ``GET /api/app/projects/{pid}/business-context/chain`` —
        a server-side convenience that returns both scopes for the
        active project. ``organization.organization_id`` is populated
        on a best-effort basis from the cached ``/me`` response (in-memory
        or disk); when the cache is cold it is left as ``None`` rather
        than triggering an extra ``/me`` round-trip. Callers that need a
        guaranteed org ID should use ``get_business_context(level=
        "organization")``, which performs full resolution.

        Returns:
            ``BusinessContextChain`` with populated ``organization`` and
            ``project`` fields. Either ``content`` may be empty when no
            context is set at that scope.
            ``organization.organization_id`` may be ``None`` when the
            ``/me`` cache is cold (see method description).

        Raises:
            ConfigError: Credentials are not available.
            AuthenticationError: Invalid credentials (401).
            QueryError: Caller lacks project access (403, 404) or
                other API error (400).
            ServerError: Server-side errors (5xx).
            MixpanelHeadlessError: API response is missing ``org_context``
                or ``project_context``.

        Example:
            ```python
            ws = Workspace()
            chain = ws.get_business_context_chain()
            print("ORG:", chain.organization.content)
            print("PROJECT:", chain.project.content)
            ```
        """
        client = self._require_api_client()
        raw = client.get_business_context_chain()
        org_content = self._require_str_field(
            raw,
            "org_context",
            method="get_business_context_chain",
        )
        project_content = self._require_str_field(
            raw,
            "project_context",
            method="get_business_context_chain",
        )
        org_id = self._cached_organization_id()
        return BusinessContextChain(
            organization=BusinessContext(
                level="organization",
                content=org_content,
                organization_id=org_id,
            ),
            project=BusinessContext(
                level="project",
                content=project_content,
                project_id=self._session.project.id,
            ),
        )
