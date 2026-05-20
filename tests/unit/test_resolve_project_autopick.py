"""Tests for ``accounts._resolve_project`` — auto-pick algorithm and fallbacks.

Covers the new ``ProjectPickResult`` shape, the auto-pick filter cascade
(region → drop demos → drop unintegrated → primary-org-lowest-id), the
fallback chain (re-include unintegrated → re-include demos), and the
``cross_region_only`` raise. The existing legacy ``auto_pick=False``
behavior (TTY picker / E-8 raise) is also exercised so the refactor
doesn't regress same-machine ``mp login``.
"""

from __future__ import annotations

import pytest

from mixpanel_headless._internal.me import MeOrgInfo, MeProjectInfo, MeResponse
from mixpanel_headless.accounts import _resolve_project
from mixpanel_headless.exceptions import (
    ConfigError,
    NeedsRegionSwitchError,
    ProjectNotFoundError,
)


def _proj(
    *,
    name: str,
    org_id: int,
    domain: str = "mixpanel.com",
    is_demo: bool = False,
    has_integrated: bool = True,
) -> MeProjectInfo:
    """Build a MeProjectInfo with the auto-pick-relevant fields set.

    ``is_demo`` and ``has_integrated`` are undeclared on the model
    (live API returns them via ``model_extra``); pass them as keyword
    args here and Pydantic's ``extra="allow"`` shovels them into
    ``model_extra``.
    """
    return MeProjectInfo(
        name=name,
        organization_id=org_id,
        domain=domain,
        is_demo=is_demo,
        has_integrated=has_integrated,
    )


def _me(
    *,
    projects: dict[str, MeProjectInfo],
    org_names: dict[int, str] | None = None,
) -> MeResponse:
    """Build a MeResponse, deriving organizations from project org_ids."""
    org_names = org_names or {}
    org_ids = {p.organization_id for p in projects.values()}
    organizations = {
        str(oid): MeOrgInfo(id=oid, name=org_names.get(oid, f"Org {oid}"))
        for oid in org_ids
    }
    return MeResponse(
        user_id=1,
        user_email="user@example.com",
        projects=projects,
        organizations=organizations,
    )


class TestExplicitProject:
    """``--project ID`` always wins, regardless of filters or auto_pick."""

    def test_explicit_project_overrides_demo(self) -> None:
        """User passed --project even on a demo? They get the demo."""
        me = _me(projects={"3": _proj(name="A demo", org_id=1, is_demo=True)})
        pick = _resolve_project(
            me_resp=me,
            explicit_project="3",
            project_picker=None,
            auto_pick=True,
            region="us",
        )
        assert pick.project_id == "3"
        assert pick.method == "explicit"

    def test_explicit_project_not_visible_raises(self) -> None:
        """--project ID not in /me → ProjectNotFoundError."""
        me = _me(projects={"3": _proj(name="A", org_id=1)})
        with pytest.raises(ProjectNotFoundError):
            _resolve_project(
                me_resp=me,
                explicit_project="999",
                project_picker=None,
                auto_pick=True,
                region="us",
            )

    def test_explicit_skips_region_filter(self) -> None:
        """--project on a wrong-region project still resolves (caller's
        ``_assert_project_region_matches`` catches the mismatch with E-2)."""
        me = _me(projects={"3": _proj(name="EU", org_id=1, domain="eu.mixpanel.com")})
        pick = _resolve_project(
            me_resp=me,
            explicit_project="3",
            project_picker=None,
            auto_pick=True,
            region="us",
        )
        assert pick.project_id == "3"
        assert pick.method == "explicit"


class TestSoleSurvivor:
    """When the filter chain leaves exactly one project, no question to ask."""

    def test_single_region_compat_project(self) -> None:
        """One region-compat project → method='sole_survivor'."""
        me = _me(projects={"3": _proj(name="Only", org_id=1)})
        pick = _resolve_project(
            me_resp=me,
            explicit_project=None,
            project_picker=None,
            auto_pick=True,
            region="us",
        )
        assert pick.project_id == "3"
        assert pick.method == "sole_survivor"

    def test_single_project_legacy_path(self) -> None:
        """auto_pick=False path also short-circuits on 1 project."""
        me = _me(projects={"3": _proj(name="Only", org_id=1)})
        pick = _resolve_project(
            me_resp=me,
            explicit_project=None,
            project_picker=None,
            auto_pick=False,
            region="us",
        )
        assert pick.project_id == "3"
        assert pick.method == "sole_survivor"

    def test_sole_survivor_filtered_when_demos_filtered_out(self) -> None:
        """Two region-compat projects, one demo → ``sole_survivor_filtered``.

        With multiple region-compat projects the line 2684 short-circuit
        does NOT fire — the auto-pick filter cascade runs and reduces
        the survivor set to one. The method should reflect that the
        single survivor came out of a *filtered* pool, so user-facing
        copy ("the only non-demo, integrated project") is accurate.
        """
        me = _me(
            projects={
                "10": _proj(name="Real", org_id=1),
                "20": _proj(name="Demo", org_id=1, is_demo=True),
            },
        )
        pick = _resolve_project(
            me_resp=me,
            explicit_project=None,
            project_picker=None,
            auto_pick=True,
            region="us",
        )
        assert pick.project_id == "10"
        assert pick.method == "sole_survivor_filtered"
        # Funnel still reflects the broader region-compatible pool.
        assert pick.region_compatible_count == 2
        assert pick.filtered_count == 1
        assert pick.demo_excluded == 1


class TestPrimaryOrgLowestId:
    """Normal auto-pick: highest-survivor-count org, lowest project ID."""

    def test_picks_from_higher_count_org(self) -> None:
        """Two orgs of unequal survivor counts → pick from the bigger one."""
        me = _me(
            projects={
                "10": _proj(name="A", org_id=1),
                "20": _proj(name="B", org_id=1),
                "30": _proj(name="C", org_id=2),
            },
            org_names={1: "Big", 2: "Small"},
        )
        pick = _resolve_project(
            me_resp=me,
            explicit_project=None,
            project_picker=None,
            auto_pick=True,
            region="us",
        )
        assert pick.method == "primary_org_lowest_id"
        assert pick.primary_org_id == "1"
        assert pick.primary_org_name == "Big"
        assert pick.primary_org_survivor_count == 2
        # Lowest project ID in the primary org wins.
        assert pick.project_id == "10"

    def test_org_tiebreak_lowest_org_id(self) -> None:
        """Orgs with equal survivor counts → lowest org ID wins."""
        me = _me(
            projects={
                "100": _proj(name="P1", org_id=2),
                "200": _proj(name="P2", org_id=1),
            },
        )
        pick = _resolve_project(
            me_resp=me,
            explicit_project=None,
            project_picker=None,
            auto_pick=True,
            region="us",
        )
        assert pick.primary_org_id == "1"
        assert pick.project_id == "200"


class TestFallbackWithUnintegrated:
    """When no integrated projects exist, re-include unintegrated ones."""

    def test_fallback_when_all_unintegrated(self) -> None:
        """All projects unintegrated → method='fallback_with_unintegrated'."""
        me = _me(
            projects={
                "10": _proj(name="A", org_id=1, has_integrated=False),
                "20": _proj(name="B", org_id=1, has_integrated=False),
            },
        )
        pick = _resolve_project(
            me_resp=me,
            explicit_project=None,
            project_picker=None,
            auto_pick=True,
            region="us",
        )
        assert pick.method == "fallback_with_unintegrated"
        assert pick.project_id == "10"


class TestFallbackWithDemos:
    """When all projects are demos AND unintegrated, re-include both."""

    def test_fallback_when_all_demos(self) -> None:
        """All projects are demos → method='fallback_with_demos'."""
        me = _me(
            projects={
                "10": _proj(name="A", org_id=1, is_demo=True),
                "20": _proj(name="B", org_id=1, is_demo=True),
            },
        )
        pick = _resolve_project(
            me_resp=me,
            explicit_project=None,
            project_picker=None,
            auto_pick=True,
            region="us",
        )
        assert pick.method == "fallback_with_demos"
        assert pick.project_id == "10"


class TestCrossRegionOnly:
    """0 region-compat projects → NeedsRegionSwitchError."""

    def test_eu_user_authed_to_us_raises(self) -> None:
        """All projects in eu, auth is us → NeedsRegionSwitchError."""
        me = _me(
            projects={
                "10": _proj(name="EU-A", org_id=1, domain="eu.mixpanel.com"),
                "20": _proj(name="EU-B", org_id=1, domain="eu.mixpanel.com"),
            },
        )
        with pytest.raises(NeedsRegionSwitchError) as exc:
            _resolve_project(
                me_resp=me,
                explicit_project=None,
                project_picker=None,
                auto_pick=True,
                region="us",
            )
        assert exc.value.pick.method == "cross_region_only"
        assert exc.value.pick.cross_region_projects is not None
        assert len(exc.value.pick.cross_region_projects) == 2

    def test_message_suggests_correct_region(self) -> None:
        """Error message points the user at the right --region flag."""
        me = _me(
            projects={"10": _proj(name="E", org_id=1, domain="eu.mixpanel.com")},
        )
        with pytest.raises(NeedsRegionSwitchError) as exc:
            _resolve_project(
                me_resp=me,
                explicit_project=None,
                project_picker=None,
                auto_pick=True,
                region="us",
            )
        assert "--region eu" in exc.value.message


class TestPickerPriority:
    """Picker preempts auto-pick when both are wired."""

    def test_picker_wins_over_auto_pick(self) -> None:
        """auto_pick=True with a picker present → picker fires."""
        me = _me(
            projects={
                "10": _proj(name="A", org_id=1),
                "20": _proj(name="B", org_id=1),
            },
        )

        def picker(_me, sorted_projects):
            """Pick the LAST entry to prove the picker ran."""
            return sorted_projects[-1][0]

        pick = _resolve_project(
            me_resp=me,
            explicit_project=None,
            project_picker=picker,
            auto_pick=True,
            region="us",
        )
        assert pick.method == "tty_picker"
        assert pick.project_id == "20"

    def test_explicit_skips_picker(self) -> None:
        """explicit_project set → picker is NOT called."""
        me = _me(
            projects={
                "10": _proj(name="A", org_id=1),
                "20": _proj(name="B", org_id=1),
            },
        )

        def picker(_me, _projects):
            """Should never be called when explicit_project is set."""
            pytest.fail("picker should not have been called")

        pick = _resolve_project(
            me_resp=me,
            explicit_project="10",
            project_picker=picker,
            auto_pick=True,
            region="us",
        )
        assert pick.method == "explicit"


class TestLegacyPathPreservesBehavior:
    """auto_pick=False paths preserve the pre-043 same-machine behavior."""

    def test_multi_project_no_picker_raises_e8(self) -> None:
        """auto_pick=False, multi-project, no picker → ConfigError E-8."""
        me = _me(
            projects={
                "10": _proj(name="A", org_id=1),
                "20": _proj(name="B", org_id=1),
            },
        )
        with pytest.raises(ConfigError) as exc:
            _resolve_project(
                me_resp=me,
                explicit_project=None,
                project_picker=None,
                auto_pick=False,
                region="us",
            )
        assert "Multiple projects" in exc.value.message

    def test_legacy_path_does_not_filter_by_region(self) -> None:
        """auto_pick=False does NOT region-filter (preserves pre-043 behavior).

        Legacy path was: picker sees all projects, post-pick E-2 catches
        wrong-region. We preserve that — auto_pick=False with multiple
        wrong-region projects raises E-8 (multi-project / no picker)
        rather than NeedsRegionSwitchError.
        """
        me = _me(
            projects={
                "10": _proj(name="EU-A", org_id=1, domain="eu.mixpanel.com"),
                "20": _proj(name="EU-B", org_id=1, domain="eu.mixpanel.com"),
            },
        )
        with pytest.raises(ConfigError) as exc:
            _resolve_project(
                me_resp=me,
                explicit_project=None,
                project_picker=None,
                auto_pick=False,
                region="us",
            )
        # Importantly: NOT NeedsRegionSwitchError.
        assert not isinstance(exc.value, NeedsRegionSwitchError)


class TestNoProjects:
    """Account with zero accessible projects."""

    def test_empty_me_returns_no_projects(self) -> None:
        """me_resp.projects empty → method='no_projects', project_id=None."""
        me = _me(projects={})
        pick = _resolve_project(
            me_resp=me,
            explicit_project=None,
            project_picker=None,
            auto_pick=True,
            region="us",
        )
        assert pick.method == "no_projects"
        assert pick.project_id is None


class TestFunnelCounts:
    """ProjectPickResult carries the right exclusion counts."""

    def test_demo_excluded_count(self) -> None:
        """demo_excluded reflects how many region-compat were dropped."""
        me = _me(
            projects={
                "10": _proj(name="A", org_id=1),  # kept
                "20": _proj(name="B", org_id=1, is_demo=True),  # dropped
                "30": _proj(name="C", org_id=1, is_demo=True),  # dropped
            },
        )
        pick = _resolve_project(
            me_resp=me,
            explicit_project=None,
            project_picker=None,
            auto_pick=True,
            region="us",
        )
        assert pick.demo_excluded == 2
        assert pick.unintegrated_excluded == 0
        assert pick.region_compatible_count == 3
        assert pick.filtered_count == 1

    def test_unintegrated_excluded_count(self) -> None:
        """unintegrated_excluded counts non-demo projects without integration."""
        me = _me(
            projects={
                "10": _proj(name="A", org_id=1),  # kept
                "20": _proj(name="B", org_id=1, has_integrated=False),  # dropped
            },
        )
        pick = _resolve_project(
            me_resp=me,
            explicit_project=None,
            project_picker=None,
            auto_pick=True,
            region="us",
        )
        assert pick.demo_excluded == 0
        assert pick.unintegrated_excluded == 1
        assert pick.filtered_count == 1
