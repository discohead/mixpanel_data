"""Unit tests for Me API types, MeCache, and MeService.

Tests cover:
- T011: MeOrgInfo, MeProjectInfo, MeWorkspaceInfo models
- T012: MeResponse model (construction, extra="allow", round-trip)
- T013: MeCache (get, put, TTL expiry, invalidate, file permissions)
- T037-T040: MeService (fetch, caching, 401/403 handling, list/find)
- T041c: MeService integration with MeCache
"""

from __future__ import annotations

import stat
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mixpanel_headless._internal.me import (
    MeCache,
    MeOrgInfo,
    MeProjectInfo,
    MeResponse,
    MeService,
    MeWorkspaceInfo,
)
from mixpanel_headless.exceptions import AuthenticationError, ConfigError, QueryError


class TestMeOrgInfo:
    """T011: Tests for MeOrgInfo model."""

    def test_construct(self) -> None:
        """Test constructing MeOrgInfo with required fields."""
        org = MeOrgInfo(id=100, name="Acme Corp")
        assert org.id == 100
        assert org.name == "Acme Corp"
        assert org.role is None
        assert org.permissions is None

    def test_construct_full(self) -> None:
        """Test constructing MeOrgInfo with all fields."""
        org = MeOrgInfo(
            id=100,
            name="Acme Corp",
            role="admin",
            permissions=["manage_users", "view_billing"],
        )
        assert org.role == "admin"
        assert org.permissions == ["manage_users", "view_billing"]

    def test_extra_fields_allowed(self) -> None:
        """Test forward compatibility: unknown fields are preserved."""
        org = MeOrgInfo.model_validate(
            {"id": 1, "name": "Test", "future_field": "value"}
        )
        assert org.id == 1
        # Extra fields should be accessible via model_extra
        assert org.model_extra is not None
        assert org.model_extra.get("future_field") == "value"


class TestMeProjectInfo:
    """T011: Tests for MeProjectInfo model."""

    def test_construct(self) -> None:
        """Test constructing MeProjectInfo with required fields."""
        project = MeProjectInfo(name="AI Demo", organization_id=100)
        assert project.name == "AI Demo"
        assert project.organization_id == 100
        assert project.timezone is None
        assert project.has_workspaces is None

    def test_construct_full(self) -> None:
        """Test constructing MeProjectInfo with all known fields."""
        project = MeProjectInfo(
            name="AI Demo",
            organization_id=100,
            timezone="US/Pacific",
            has_workspaces=True,
            domain="mixpanel.com",
            type="PROJECT",
        )
        assert project.timezone == "US/Pacific"
        assert project.has_workspaces is True

    def test_extra_fields_allowed(self) -> None:
        """Test forward compatibility: unknown fields are preserved."""
        project = MeProjectInfo.model_validate(
            {
                "name": "Test",
                "organization_id": 1,
                "experimental_feature": True,
            }
        )
        assert project.model_extra is not None
        assert project.model_extra.get("experimental_feature") is True


class TestMeWorkspaceInfo:
    """T011: Tests for MeWorkspaceInfo model."""

    def test_construct(self) -> None:
        """Test constructing MeWorkspaceInfo with required fields."""
        ws = MeWorkspaceInfo(id=3448413, name="Default", project_id=3713224)
        assert ws.id == 3448413
        assert ws.name == "Default"
        assert ws.project_id == 3713224
        assert ws.is_default is None

    def test_construct_full(self) -> None:
        """Test constructing MeWorkspaceInfo with all known fields."""
        ws = MeWorkspaceInfo(
            id=3448413,
            name="Default",
            project_id=3713224,
            is_default=True,
            is_global=False,
            is_restricted=False,
            is_visible=True,
            description="The default workspace",
            creator_name="admin",
        )
        assert ws.is_default is True
        assert ws.is_global is False

    def test_extra_fields_allowed(self) -> None:
        """Test forward compatibility: unknown fields are preserved."""
        ws = MeWorkspaceInfo.model_validate(
            {
                "id": 1,
                "name": "Test",
                "project_id": 100,
                "new_api_field": "surprise",
            }
        )
        assert ws.model_extra is not None
        assert ws.model_extra.get("new_api_field") == "surprise"


class TestMeResponse:
    """T012: Tests for MeResponse model."""

    def test_construct_minimal(self) -> None:
        """Test constructing MeResponse with no fields (all optional)."""
        me = MeResponse()
        assert me.user_id is None
        assert me.user_email is None
        assert me.user_name is None
        assert me.organizations == {}
        assert me.projects == {}
        assert me.workspaces == {}

    def test_construct_full(self) -> None:
        """Test constructing MeResponse with all fields populated."""
        me = MeResponse(
            user_id=42,
            user_email="jared@example.com",
            user_name="Jared",
            organizations={
                "100": MeOrgInfo(id=100, name="Acme"),
            },
            projects={
                "3713224": MeProjectInfo(name="AI Demo", organization_id=100),
            },
            workspaces={
                "3448413": MeWorkspaceInfo(
                    id=3448413, name="Default", project_id=3713224
                ),
            },
        )
        assert me.user_id == 42
        assert "3713224" in me.projects
        assert me.projects["3713224"].name == "AI Demo"

    def test_extra_fields_allowed(self) -> None:
        """Test forward compatibility: unknown top-level fields preserved."""
        me = MeResponse.model_validate(
            {
                "user_id": 1,
                "feature_flags": {"new_ui": True},
                "demo_account": False,
            }
        )
        assert me.model_extra is not None
        assert me.model_extra.get("demo_account") is False

    def test_serialization_round_trip(self) -> None:
        """Test MeResponse can be serialized to JSON and deserialized back."""
        original = MeResponse(
            user_id=42,
            user_email="test@example.com",
            organizations={
                "100": MeOrgInfo(id=100, name="Acme", role="admin"),
            },
            projects={
                "3713224": MeProjectInfo(
                    name="AI Demo",
                    organization_id=100,
                    timezone="US/Pacific",
                ),
            },
            workspaces={
                "3448413": MeWorkspaceInfo(
                    id=3448413,
                    name="Default",
                    project_id=3713224,
                    is_default=True,
                ),
            },
        )
        json_str = original.model_dump_json()
        restored = MeResponse.model_validate_json(json_str)
        assert restored.user_id == original.user_id
        assert restored.user_email == original.user_email
        assert restored.projects["3713224"].name == "AI Demo"
        assert restored.workspaces["3448413"].is_default is True


class TestMeCache:
    """T013: Tests for MeCache (per-account v3 layout — T043)."""

    @pytest.fixture
    def cache_dir(self, tmp_path: Path) -> Path:
        """Create a temporary per-account cache directory."""
        d = tmp_path / "accounts" / "personal"
        d.mkdir(parents=True)
        return d

    @pytest.fixture
    def cache(self, cache_dir: Path) -> MeCache:
        """Create a MeCache instance bound to a tmp account directory."""
        return MeCache(account_name="personal", storage_dir=cache_dir)

    @pytest.fixture
    def sample_response(self) -> MeResponse:
        """Create a sample MeResponse for testing."""
        return MeResponse(
            user_id=42,
            user_email="test@example.com",
            projects={
                "3713224": MeProjectInfo(name="AI Demo", organization_id=100),
            },
        )

    def test_put_and_get(self, cache: MeCache, sample_response: MeResponse) -> None:
        """Test storing and retrieving a cached response."""
        cache.put(sample_response)
        result = cache.get()
        assert result is not None
        assert result.user_id == 42
        assert result.projects["3713224"].name == "AI Demo"

    def test_get_miss(self, cache: MeCache) -> None:
        """Test cache miss returns None."""
        result = cache.get()
        assert result is None

    def test_ttl_expiry(self, cache_dir: Path, sample_response: MeResponse) -> None:
        """Test cache entries expire after TTL."""
        cache = MeCache(account_name="personal", storage_dir=cache_dir, ttl_seconds=1)
        cache.put(sample_response)
        assert cache.get() is not None
        time.sleep(1.1)
        assert cache.get() is None

    def test_invalidate(self, cache: MeCache, sample_response: MeResponse) -> None:
        """Test invalidating the account cache."""
        cache.put(sample_response)
        assert cache.get() is not None
        cache.invalidate()
        assert cache.get() is None

    def test_account_name_isolates_cache(
        self, tmp_path: Path, sample_response: MeResponse
    ) -> None:
        """Two accounts in the same tmp parent get isolated cache files."""
        cache_a = MeCache(account_name="alice", storage_dir=tmp_path / "alice")
        cache_b = MeCache(account_name="bob", storage_dir=tmp_path / "bob")

        response_b = MeResponse(user_id=99, user_email="other@example.com")

        cache_a.put(sample_response)
        cache_b.put(response_b)

        result_a = cache_a.get()
        result_b = cache_b.get()

        assert result_a is not None
        assert result_a.user_id == 42
        assert result_b is not None
        assert result_b.user_id == 99

    def test_file_permissions(
        self, cache: MeCache, cache_dir: Path, sample_response: MeResponse
    ) -> None:
        """Test cache files are created with 0o600 permissions."""
        cache.put(sample_response)
        cache_file = cache_dir / "me.json"
        assert cache_file.exists()
        # Check file permissions (owner read/write only)
        file_stat = cache_file.stat()
        file_mode = stat.S_IMODE(file_stat.st_mode)
        assert file_mode == 0o600

    def test_corrupted_cache_returns_none(
        self, cache: MeCache, cache_dir: Path
    ) -> None:
        """Test corrupted cache file returns None gracefully."""
        cache_file = cache_dir / "me.json"
        cache_file.write_text("not valid json{{{")
        assert cache.get() is None

    def test_default_storage_dir_resolves_to_per_account_path(self) -> None:
        """Without ``storage_dir`` the cache file lives at ``~/.mp/accounts/{name}/me.json``."""
        cache = MeCache(account_name="demo-sa")
        assert (
            cache._cache_path()
            == Path.home() / ".mp" / "accounts" / "demo-sa" / "me.json"
        )


class TestMeCacheConcurrency:
    """``MeCache.put()`` must be safe under concurrent same-process writers.

    Routes through :func:`atomic_write_bytes`, which derives the tmp filename
    from ``pid + tid`` so two threads writing different payloads to the same
    cache pick distinct tmp paths and one of them wins atomically — neither
    can observe a torn or partial file.
    """

    def test_two_threads_writing_same_cache_produce_valid_file(
        self, tmp_path: Path
    ) -> None:
        """Two threads racing through ``put()`` MUST leave a parseable file.

        Regression: the prior implementation used a fixed
        ``path.with_suffix('.tmp')`` for the tmp filename, so concurrent
        writers' ``write_text`` calls clobbered each other and the rename
        could land a half-written file.
        """
        import threading

        cache_dir = tmp_path / "accounts" / "personal"
        cache_dir.mkdir(parents=True)
        cache = MeCache(account_name="personal", storage_dir=cache_dir)

        # Two distinct payloads — only one should win, but both must be
        # individually well-formed.
        resp_a = MeResponse(user_id=1, user_email="a@example.com")
        resp_b = MeResponse(user_id=2, user_email="b@example.com")

        barrier = threading.Barrier(2)
        errors: list[BaseException] = []

        def writer(payload: MeResponse) -> None:
            try:
                barrier.wait()  # release both threads simultaneously
                cache.put(payload)
            except BaseException as exc:  # noqa: BLE001 — surface to assertion
                errors.append(exc)

        t1 = threading.Thread(target=writer, args=(resp_a,))
        t2 = threading.Thread(target=writer, args=(resp_b,))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors, f"Concurrent writers raised: {errors}"
        result = cache.get()
        assert result is not None, "Cache file is unparseable after concurrent writes"
        # Whichever thread won, the file has a valid user_id from one of them.
        assert result.user_id in (1, 2)

    def test_chmod_failure_on_dir_raises_config_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An OS that refuses ``0o700`` on the dir surfaces a ConfigError.

        Cache holds PII (user emails, project names) — silent fall-through
        to the default umask would leak that material.
        """
        cache_dir = tmp_path / "accounts" / "personal"
        cache_dir.mkdir(parents=True)
        cache = MeCache(account_name="personal", storage_dir=cache_dir)
        resp = MeResponse(user_id=1, user_email="a@example.com")

        original_chmod = __import__("os").chmod

        def chmod_fail(path: Any, mode: int) -> None:
            if str(path) == str(cache_dir):
                raise OSError(13, "Permission denied")
            original_chmod(path, mode)

        monkeypatch.setattr("os.chmod", chmod_fail)
        with pytest.raises(ConfigError, match="0o700"):
            cache.put(resp)


# ── MeService Tests ─────────────────────────────────────────────────


def _make_me_response_dict() -> dict[str, object]:
    """Build a raw /me response dict for mocking api_client.me()."""
    return {
        "user_id": 42,
        "user_email": "test@example.com",
        "user_name": "Test User",
        "organizations": {
            "100": {"id": 100, "name": "Acme Corp"},
        },
        "projects": {
            "3713224": {
                "name": "AI Demo",
                "organization_id": 100,
                "timezone": "US/Pacific",
                "has_workspaces": True,
            },
            "3018488": {
                "name": "E-Commerce",
                "organization_id": 100,
                "timezone": "US/Eastern",
                "has_workspaces": False,
            },
        },
        "workspaces": {
            "3448413": {
                "id": 3448413,
                "name": "Default",
                "project_id": 3713224,
                "is_default": True,
            },
            "3448414": {
                "id": 3448414,
                "name": "Staging",
                "project_id": 3713224,
                "is_default": False,
            },
            "9999999": {
                "id": 9999999,
                "name": "Other",
                "project_id": 3018488,
                "is_default": True,
            },
        },
    }


class TestMeService:
    """T037-T040: Tests for MeService."""

    @pytest.fixture
    def cache_dir(self, tmp_path: Path) -> Path:
        """Create a temporary cache directory."""
        d = tmp_path / "oauth"
        d.mkdir()
        return d

    @pytest.fixture
    def cache(self, cache_dir: Path) -> MeCache:
        """Create a MeCache with temporary per-account directory."""
        return MeCache(account_name="personal", storage_dir=cache_dir)

    @pytest.fixture
    def mock_api(self) -> MagicMock:
        """Create a mock API client with a .me() method."""
        api = MagicMock()
        api.me.return_value = _make_me_response_dict()
        return api

    @pytest.fixture
    def service(self, mock_api: MagicMock, cache: MeCache) -> MeService:
        """Create a MeService with mock API client."""
        return MeService(mock_api, cache, "us")

    # ── fetch() ──────────────────────────────────────────────────────

    def test_fetch_calls_api(self, service: MeService, mock_api: MagicMock) -> None:
        """Test that fetch() calls api_client.me() on first call."""
        result = service.fetch()
        mock_api.me.assert_called_once()
        assert result.user_id == 42
        assert result.user_email == "test@example.com"

    def test_fetch_returns_cached_on_second_call(
        self, service: MeService, mock_api: MagicMock
    ) -> None:
        """Test that fetch() uses in-memory cache on second call."""
        service.fetch()
        service.fetch()
        mock_api.me.assert_called_once()

    def test_fetch_force_refresh_bypasses_cache(
        self, service: MeService, mock_api: MagicMock
    ) -> None:
        """Test that fetch(force_refresh=True) bypasses all caches."""
        service.fetch()
        service.fetch(force_refresh=True)
        assert mock_api.me.call_count == 2

    def test_fetch_uses_disk_cache(self, mock_api: MagicMock, cache: MeCache) -> None:
        """Test that fetch() uses disk cache if in-memory cache is empty."""
        # First service populates disk cache
        svc1 = MeService(mock_api, cache, "us")
        svc1.fetch()
        assert mock_api.me.call_count == 1

        # Second service should use disk cache
        svc2 = MeService(mock_api, cache, "us")
        result = svc2.fetch()
        assert mock_api.me.call_count == 1  # no additional API call
        assert result.user_id == 42

    def test_fetch_stores_in_disk_cache(
        self, service: MeService, cache: MeCache
    ) -> None:
        """Test that fetch() stores response in disk cache."""
        service.fetch()
        cached = cache.get()
        assert cached is not None
        assert cached.user_id == 42

    # ── fetch() error handling (T041b) ───────────────────────────────

    def test_fetch_401_raises_config_error(self, cache: MeCache) -> None:
        """401 → actionable ConfigError mentioning re-login (not /me access)."""
        api = MagicMock()
        api.me.side_effect = AuthenticationError("Invalid credentials", status_code=401)
        svc = MeService(api, cache, "us")
        with pytest.raises(ConfigError, match="invalid \\(401\\)") as exc_info:
            svc.fetch()
        # 401 error should mention `mp account login` as the actionable fix
        assert "mp account login" in exc_info.value.message
        assert exc_info.value.details["status_code"] == 401
        assert exc_info.value.details["account_name"] == "personal"

    def test_fetch_403_for_service_account_surfaces_scope_hint(
        self, cache: MeCache
    ) -> None:
        """SA 403 → ConfigError matching error catalog E-10 verbatim.

        Per 043 FR-014, an SA missing the ``user_details`` scope must be
        told exactly which scope to enable and where to enable it
        (Mixpanel Settings → Service Accounts), not the generic 042
        "lacks /me permission" line.
        """
        api = MagicMock()
        api.me.side_effect = QueryError("Permission denied", status_code=403)
        svc = MeService(api, cache, "us", account_type="service_account")
        with pytest.raises(ConfigError) as exc_info:
            svc.fetch()
        # E-10 verbatim — wording, scope name, and Settings reference all
        # locked down so a copy-edit during refactor breaks CI.
        expected = (
            "Service account 'personal' is missing the `user_details` scope.\n\n"
            "Re-mint the SA in Mixpanel Settings → Service Accounts with "
            "that scope checked,\n"
            "or pass --project ID explicitly to skip the /me lookup."
        )
        assert exc_info.value.message == expected
        assert exc_info.value.details["status_code"] == 403
        assert exc_info.value.details["account_name"] == "personal"

    def test_fetch_403_without_account_type_uses_generic_message(
        self, cache: MeCache
    ) -> None:
        """Non-SA 403 → ConfigError with the generic ``--project`` advice.

        oauth_browser / oauth_token credentials don't have a ``user_details``
        scope to add via Mixpanel Settings, so the SA-specific E-10
        wording would be misleading. The generic message stays.
        """
        api = MagicMock()
        api.me.side_effect = QueryError("Permission denied", status_code=403)
        svc = MeService(api, cache, "us")  # account_type defaults to None
        with pytest.raises(ConfigError, match="lacks /me permission") as exc_info:
            svc.fetch()
        assert "--project" in exc_info.value.message
        assert exc_info.value.details["status_code"] == 403
        assert exc_info.value.details["account_name"] == "personal"

    def test_fetch_other_error_propagates(self, cache: MeCache) -> None:
        """Test that non-401/403 errors propagate unchanged."""
        api = MagicMock()
        api.me.side_effect = QueryError("Bad request", status_code=400)
        svc = MeService(api, cache, "us")
        with pytest.raises(QueryError, match="Bad request"):
            svc.fetch()

    # ── list_projects() ──────────────────────────────────────────────

    def test_list_projects_returns_sorted(self, service: MeService) -> None:
        """Test that list_projects() returns projects sorted by name."""
        projects = service.list_projects()
        assert len(projects) == 2
        # "AI Demo" sorts before "E-Commerce"
        assert projects[0][0] == "3713224"
        assert projects[0][1].name == "AI Demo"
        assert projects[1][0] == "3018488"
        assert projects[1][1].name == "E-Commerce"

    def test_list_projects_fetches_if_not_cached(
        self, service: MeService, mock_api: MagicMock
    ) -> None:
        """Test that list_projects() calls fetch() if needed."""
        service.list_projects()
        mock_api.me.assert_called_once()

    # ── find_project() ───────────────────────────────────────────────

    def test_find_project_found(self, service: MeService) -> None:
        """Test finding an existing project by ID."""
        info = service.find_project("3713224")
        assert info is not None
        assert info.name == "AI Demo"

    def test_find_project_not_found(self, service: MeService) -> None:
        """Test finding a non-existent project returns None."""
        info = service.find_project("999999")
        assert info is None

    # ── list_workspaces() ────────────────────────────────────────────

    def test_list_workspaces_all(self, service: MeService) -> None:
        """Test listing all workspaces across projects."""
        workspaces = service.list_workspaces()
        assert len(workspaces) == 3

    def test_list_workspaces_filtered(self, service: MeService) -> None:
        """Test listing workspaces filtered by project_id."""
        workspaces = service.list_workspaces(project_id="3713224")
        assert len(workspaces) == 2
        names = {ws.name for ws in workspaces}
        assert names == {"Default", "Staging"}

    def test_list_workspaces_sorted_by_name(self, service: MeService) -> None:
        """Test that workspaces are sorted by name."""
        workspaces = service.list_workspaces(project_id="3713224")
        assert workspaces[0].name == "Default"
        assert workspaces[1].name == "Staging"

    def test_list_workspaces_empty_for_unknown_project(
        self, service: MeService
    ) -> None:
        """Test listing workspaces for an unknown project returns empty."""
        workspaces = service.list_workspaces(project_id="999999")
        assert workspaces == []

    # ── find_default_workspace() ─────────────────────────────────────

    def test_find_default_workspace_found(self, service: MeService) -> None:
        """Test finding the default workspace for a project."""
        ws = service.find_default_workspace("3713224")
        assert ws is not None
        assert ws.name == "Default"
        assert ws.id == 3448413

    def test_find_default_workspace_not_found(self, service: MeService) -> None:
        """Test finding default workspace returns None when no default."""
        # Modify response to have no default workspace for a project
        service._cached_response = MeResponse(
            user_id=42,
            workspaces={
                "100": MeWorkspaceInfo(
                    id=100,
                    name="NonDefault",
                    project_id=555,
                    is_default=False,
                ),
            },
        )
        ws = service.find_default_workspace("555")
        assert ws is None
