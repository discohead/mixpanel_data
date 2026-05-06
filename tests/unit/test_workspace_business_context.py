"""Unit tests for Workspace business context methods (AIE-147).

Covers all four facade methods plus the ``_resolve_organization_id``
helper. Each method delegates to MixpanelAPIClient via httpx.MockTransport
and returns typed BusinessContext / BusinessContextChain instances.

Verifies:

- Project- and org-level GET / SET / CLEAR
- Org ID auto-resolution from /me cache (project lookup, sole-org fallback)
- Org ID explicit override (no /me fetch)
- Ambiguous-org raises WorkspaceScopeError
- 50,000-character boundary on set (client-side validation)
- Chain endpoint parses both fields and populates org_id + project_id
- Server-side 400 surfaces as QueryError
"""

# ruff: noqa: ARG001, ARG005

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.auth.session import Session
from mixpanel_data._internal.me import MeOrgInfo, MeProjectInfo, MeResponse
from mixpanel_data.exceptions import (
    BusinessContextValidationError,
    QueryError,
    WorkspaceScopeError,
)
from mixpanel_data.types import (
    BUSINESS_CONTEXT_MAX_CHARS,
    BusinessContext,
    BusinessContextChain,
)
from mixpanel_data.workspace import Workspace
from tests.conftest import make_session

# =============================================================================
# Helpers
# =============================================================================


def _session() -> Session:
    """Return a Session bound to test project 12345.

    Returns:
        A Session usable for ``MixpanelAPIClient(session=...)``.
    """
    return make_session(project_id="12345", region="us", oauth_token="test-token")


def _make_workspace(handler: Any) -> Workspace:
    """Build a Workspace whose API client routes through ``handler``.

    Args:
        handler: ``httpx.MockTransport`` handler accepting ``Request``.

    Returns:
        A Workspace wired to the mock transport.
    """
    sess = _session()
    transport = httpx.MockTransport(handler)
    client = MixpanelAPIClient(session=sess, _transport=transport)
    return Workspace(session=sess, _api_client=client)


def _stub_me(
    ws: Workspace,
    *,
    project_org: int | None = 100,
    extra_orgs: dict[str, int] | None = None,
    no_active_project: bool = False,
) -> None:
    """Pre-populate ``ws._me_service`` with a canned MeResponse.

    Args:
        ws: Workspace whose MeService should be replaced.
        project_org: Owning organization ID for the active project
            (12345). Set to ``None`` to omit the project from the
            ``/me`` payload (forces fallback paths).
        extra_orgs: Additional ``{org_id: int_id}`` entries to add to
            ``MeResponse.organizations``. The active project's org is
            always present (when ``project_org`` is set) plus these.
        no_active_project: When True, omit the active project entirely
            (combine with empty ``extra_orgs`` to test ambiguous-org
            failure, or with one ``extra_orgs`` to test sole-org
            fallback).
    """

    class _StubMeSvc:
        """Minimal MeService stand-in returning a canned MeResponse."""

        def __init__(self, response: MeResponse) -> None:
            """Store the canned response."""
            self._response = response

        def fetch(self, *, force_refresh: bool = False) -> MeResponse:
            """Return the canned response (cache parameters ignored)."""
            del force_refresh
            return self._response

    orgs: dict[str, MeOrgInfo] = {}
    projects: dict[str, MeProjectInfo] = {}

    if project_org is not None and not no_active_project:
        orgs[str(project_org)] = MeOrgInfo(id=project_org, name=f"Org {project_org}")
        projects["12345"] = MeProjectInfo(name="Active", organization_id=project_org)

    if extra_orgs:
        for key, oid in extra_orgs.items():
            orgs[key] = MeOrgInfo(id=oid, name=f"Org {oid}")

    response = MeResponse(organizations=orgs, projects=projects)
    ws._me_service = _StubMeSvc(response)  # type: ignore[assignment]


def _ok(results: dict[str, Any]) -> httpx.Response:
    """Build a 200 OK App-API response wrapping ``results``."""
    return httpx.Response(200, json={"status": "ok", "results": results})


# =============================================================================
# Project-scoped GET
# =============================================================================


class TestGetBusinessContextProject:
    """get_business_context(level='project') behavior."""

    def test_returns_populated_context(self, temp_dir: Path) -> None:
        """GET returns BusinessContext with project_id and content."""
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL + method, return canned content."""
            seen.append(f"{request.method} {request.url.path}")
            return _ok({"content": "# Project context\n\nHello."})

        ws = _make_workspace(handler)
        ctx = ws.get_business_context(level="project")

        assert isinstance(ctx, BusinessContext)
        assert ctx.level == "project"
        assert ctx.project_id == "12345"
        assert ctx.organization_id is None
        assert ctx.content == "# Project context\n\nHello."
        assert ctx.is_empty is False
        assert ctx.character_count == len("# Project context\n\nHello.")
        assert seen == ["GET /api/app/projects/12345/business-context"]

    def test_default_level_is_project(self, temp_dir: Path) -> None:
        """Calling without ``level`` defaults to 'project'."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty content."""
            return _ok({"content": ""})

        ws = _make_workspace(handler)
        ctx = ws.get_business_context()
        assert ctx.level == "project"
        assert ctx.is_empty is True

    def test_empty_content_yields_is_empty(self, temp_dir: Path) -> None:
        """Empty string from API → BusinessContext.is_empty is True."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return the unset state."""
            return _ok({"content": ""})

        ws = _make_workspace(handler)
        ctx = ws.get_business_context(level="project")
        assert ctx.content == ""
        assert ctx.is_empty is True
        assert ctx.character_count == 0


# =============================================================================
# Project-scoped SET / CLEAR
# =============================================================================


class TestSetBusinessContextProject:
    """set_business_context(level='project') behavior."""

    def test_sends_put_with_correct_body(self, temp_dir: Path) -> None:
        """SET issues PUT with ``{"content": ...}`` body."""
        seen: list[tuple[str, str, dict[str, Any]]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method, path, body and echo content back."""
            body: dict[str, Any] = json.loads(request.content)
            seen.append((request.method, request.url.path, body))
            return _ok({"content": body["content"]})

        ws = _make_workspace(handler)
        ctx = ws.set_business_context("# New content", level="project")

        assert ctx.level == "project"
        assert ctx.project_id == "12345"
        assert ctx.content == "# New content"
        assert seen == [
            (
                "PUT",
                "/api/app/projects/12345/business-context",
                {"content": "# New content"},
            ),
        ]

    def test_validation_blocks_oversize_before_http(self, temp_dir: Path) -> None:
        """50_001 chars → BusinessContextValidationError, no HTTP call."""
        called = False

        def handler(request: httpx.Request) -> httpx.Response:
            """Should never be called when validation rejects input."""
            nonlocal called
            called = True
            return _ok({"content": ""})

        ws = _make_workspace(handler)
        with pytest.raises(BusinessContextValidationError) as exc_info:
            ws.set_business_context("x" * (BUSINESS_CONTEXT_MAX_CHARS + 1))

        assert called is False
        details = exc_info.value.details
        assert details["length"] == BUSINESS_CONTEXT_MAX_CHARS + 1
        assert details["max"] == BUSINESS_CONTEXT_MAX_CHARS
        assert exc_info.value.code == "BUSINESS_CONTEXT_TOO_LONG"

    def test_exact_max_length_is_accepted(self, temp_dir: Path) -> None:
        """Exactly 50,000 chars passes client-side validation."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Echo content back to caller."""
            body: dict[str, Any] = json.loads(request.content)
            return _ok({"content": body["content"]})

        ws = _make_workspace(handler)
        payload = "x" * BUSINESS_CONTEXT_MAX_CHARS
        ctx = ws.set_business_context(payload, level="project")
        assert ctx.character_count == BUSINESS_CONTEXT_MAX_CHARS

    def test_server_400_surfaces_as_query_error(self, temp_dir: Path) -> None:
        """A 400 from the API is mapped to QueryError."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return the server-side rejection shape."""
            return httpx.Response(
                400,
                json={
                    "status": "error",
                    "error": "content exceeds maximum length of 50000 characters",
                },
            )

        ws = _make_workspace(handler)
        with pytest.raises(QueryError):
            ws.set_business_context("# legal here", level="project")


class TestClearBusinessContextProject:
    """clear_business_context delegates to set with empty content."""

    def test_clear_sends_empty_content_put(self, temp_dir: Path) -> None:
        """CLEAR issues PUT with ``{"content": ""}``."""
        seen: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body, echo cleared state."""
            body: dict[str, Any] = json.loads(request.content)
            seen.append(body)
            return _ok({"content": body["content"]})

        ws = _make_workspace(handler)
        ctx = ws.clear_business_context(level="project")

        assert ctx.level == "project"
        assert ctx.is_empty is True
        assert seen == [{"content": ""}]


# =============================================================================
# Org-scoped GET / SET (with org-id resolution)
# =============================================================================


class TestGetBusinessContextOrganization:
    """get_business_context(level='organization') behavior."""

    def test_explicit_org_id_skips_me_fetch(self, temp_dir: Path) -> None:
        """Passing organization_id avoids any /me lookup."""
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return canned org content."""
            seen.append(f"{request.method} {request.url.path}")
            return _ok({"content": "# Org content"})

        ws = _make_workspace(handler)

        class _ExplodingMeSvc:
            """Stand-in that raises if fetch() is called."""

            def fetch(self, *, force_refresh: bool = False) -> MeResponse:
                """Should never be invoked when organization_id is explicit."""
                raise AssertionError("MeService.fetch should not be called")

        ws._me_service = _ExplodingMeSvc()  # type: ignore[assignment]

        ctx = ws.get_business_context(level="organization", organization_id=42)
        assert ctx.level == "organization"
        assert ctx.organization_id == 42
        assert ctx.project_id is None
        assert ctx.content == "# Org content"
        assert seen == ["GET /api/app/organizations/42/business-context"]

    def test_auto_resolve_from_active_project(self, temp_dir: Path) -> None:
        """Without explicit org_id, derives it from /me.projects[pid]."""
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return canned org content."""
            seen.append(request.url.path)
            return _ok({"content": "# Auto-resolved"})

        ws = _make_workspace(handler)
        _stub_me(ws, project_org=100)

        ctx = ws.get_business_context(level="organization")
        assert ctx.organization_id == 100
        assert seen == ["/api/app/organizations/100/business-context"]

    def test_auto_resolve_falls_through_to_sole_org(self, temp_dir: Path) -> None:
        """When project missing from /me but only one org exists, use it."""
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Return canned content."""
            seen.append(request.url.path)
            return _ok({"content": ""})

        ws = _make_workspace(handler)
        _stub_me(
            ws,
            project_org=None,
            extra_orgs={"77": 77},
            no_active_project=True,
        )

        ctx = ws.get_business_context(level="organization")
        assert ctx.organization_id == 77
        assert seen == ["/api/app/organizations/77/business-context"]

    def test_ambiguous_org_raises_workspace_scope_error(self, temp_dir: Path) -> None:
        """Multiple orgs + project not in /me → WorkspaceScopeError."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Should never be called when resolution fails first."""
            raise AssertionError("HTTP call should not happen on resolution failure")

        ws = _make_workspace(handler)
        _stub_me(
            ws,
            project_org=None,
            extra_orgs={"1": 1, "2": 2},
            no_active_project=True,
        )

        with pytest.raises(WorkspaceScopeError) as exc_info:
            ws.get_business_context(level="organization")

        assert exc_info.value.code == "ORGANIZATION_AMBIGUOUS"
        assert exc_info.value.details["project_id"] == "12345"
        assert exc_info.value.details["available_organizations"] == ["1", "2"]


class TestSetBusinessContextOrganization:
    """set_business_context(level='organization') behavior."""

    def test_set_org_uses_org_path(self, temp_dir: Path) -> None:
        """Org SET hits /organizations/{id}/business-context."""
        seen: list[tuple[str, str, dict[str, Any]]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method, path, body."""
            body: dict[str, Any] = json.loads(request.content)
            seen.append((request.method, request.url.path, body))
            return _ok({"content": body["content"]})

        ws = _make_workspace(handler)
        ctx = ws.set_business_context(
            "# Org-wide",
            level="organization",
            organization_id=100,
        )

        assert ctx.level == "organization"
        assert ctx.organization_id == 100
        assert ctx.content == "# Org-wide"
        assert seen == [
            (
                "PUT",
                "/api/app/organizations/100/business-context",
                {"content": "# Org-wide"},
            ),
        ]


# =============================================================================
# Chain endpoint
# =============================================================================


class TestGetBusinessContextChain:
    """get_business_context_chain() behavior."""

    def test_chain_parses_both_scopes(self, temp_dir: Path) -> None:
        """Chain returns BusinessContextChain with org + project content."""
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL, return both fields."""
            seen.append(f"{request.method} {request.url.path}")
            return _ok(
                {
                    "org_context": "# Org info",
                    "project_context": "# Project info",
                }
            )

        ws = _make_workspace(handler)
        _stub_me(ws, project_org=100)

        chain = ws.get_business_context_chain()

        assert isinstance(chain, BusinessContextChain)
        assert chain.organization.level == "organization"
        assert chain.organization.organization_id == 100
        assert chain.organization.content == "# Org info"
        assert chain.project.level == "project"
        assert chain.project.project_id == "12345"
        assert chain.project.content == "# Project info"
        assert seen == ["GET /api/app/projects/12345/business-context/chain"]

    def test_chain_with_empty_scopes(self, temp_dir: Path) -> None:
        """Empty strings in chain response yield is_empty BusinessContexts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return the unset state for both scopes."""
            return _ok({"org_context": "", "project_context": ""})

        ws = _make_workspace(handler)
        _stub_me(ws, project_org=100)

        chain = ws.get_business_context_chain()
        assert chain.organization.is_empty is True
        assert chain.project.is_empty is True
