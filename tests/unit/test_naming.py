"""Unit tests for the pure-functional naming module (043 / AIE-116).

Locks the FR-015 (``slugify``) and FR-016 (``default_account_name``)
input/output tables from the spec verbatim, plus a few edge cases that
exercise the boundary conditions of the 32-character truncation and
collision-suffix loops.

Reference: ``specs/043-frictionless-auth/spec.md`` FR-015, FR-016.
"""

from __future__ import annotations

import pytest

from mixpanel_headless._internal.auth.naming import (
    default_account_name,
    slugify,
)
from mixpanel_headless._internal.me import MeOrgInfo, MeResponse

# ---- slugify (FR-015) -------------------------------------------------


class TestSlugify:
    """``slugify`` reduces input to ``[a-z0-9-]{0,32}``."""

    @pytest.mark.parametrize(
        ("input_value", "expected"),
        [
            ("Acme Corp", "acme-corp"),
            ("ACME, Inc.", "acme-inc"),
            ("Café Industries", "cafe-industries"),
            ("  Acme  &  Sons ", "acme-sons"),
            ("1Password", "1password"),
            ("---", ""),
            ("", ""),
            (None, ""),
            ("Mixpanel 🎉 Co", "mixpanel-co"),
        ],
    )
    def test_fr015_table(self, input_value: str | None, expected: str) -> None:
        """The spec's FR-015 input/output table is locked verbatim."""
        assert slugify(input_value) == expected

    def test_truncation_to_32_chars_strips_trailing_dash(self) -> None:
        """A 50-char input truncates to ≤32 chars and trims trailing ``-``.

        Input: ``"AAAAAAAAAA BBBBBBBBBB CCCCCCCCCC DDDDDDDDDD"`` — five 10-char
        words separated by spaces. Slugified → 53-char run with ``-`` between
        groups; truncated to 32 chars; trailing ``-`` (if any) stripped.
        """
        long_input = "AAAAAAAAAA BBBBBBBBBB CCCCCCCCCC DDDDDDDDDD"
        result = slugify(long_input)
        assert len(result) <= 32
        assert not result.endswith("-")

    def test_idempotent(self) -> None:
        """``slugify(slugify(x)) == slugify(x)`` for representative values."""
        for value in [
            "Acme Corp",
            "Café",
            "1234567890",
            "  spaces  ",
            "ünïçødé",
            "",
        ]:
            once = slugify(value)
            twice = slugify(once)
            assert twice == once, f"slugify not idempotent for {value!r}"

    def test_output_matches_account_name_constraint(self) -> None:
        """Non-empty output satisfies ``^[a-z0-9-]{1,32}$``."""
        import re

        pattern = re.compile(r"^[a-z0-9-]{1,32}$")
        for value in [
            "Acme Corp",
            "ACME, Inc.",
            "Café Industries",
            "1Password",
            "Mixpanel 🎉",
        ]:
            result = slugify(value)
            if result:
                assert pattern.fullmatch(result), (
                    f"slug {result!r} from {value!r} violates name constraint"
                )


# ---- default_account_name (FR-016) -----------------------------------


def _me_with_org(org_id: str, name: str) -> MeResponse:
    """Build a MeResponse with a single organization for testing."""
    return MeResponse(
        organizations={org_id: MeOrgInfo(id=int(org_id), name=name)},
    )


class TestDefaultAccountName:
    """``default_account_name`` picks org slug, suffixing on collision."""

    def test_no_collision_returns_base_slug(self) -> None:
        """Empty ``existing`` set → returns the base slug unchanged."""
        me = _me_with_org("100", "Acme Corp")
        assert default_account_name(me, set()) == "acme-corp"

    def test_first_collision_returns_dash_two(self) -> None:
        """One existing matching name → suffix ``-2``."""
        me = _me_with_org("100", "Acme Corp")
        assert default_account_name(me, {"acme-corp"}) == "acme-corp-2"

    def test_second_collision_returns_dash_three(self) -> None:
        """Two existing matching names → suffix ``-3`` (skips ``-1``)."""
        me = _me_with_org("100", "Acme Corp")
        result = default_account_name(me, {"acme-corp", "acme-corp-2"})
        assert result == "acme-corp-3"

    def test_collision_suffix_finds_first_unused(self) -> None:
        """``-2`` and ``-4`` taken → returns ``-3``."""
        me = _me_with_org("100", "Acme Corp")
        result = default_account_name(me, {"acme-corp", "acme-corp-2", "acme-corp-4"})
        assert result == "acme-corp-3"

    def test_empty_org_name_falls_back_to_org_id(self) -> None:
        """Org with non-slugifiable name → ``f"org-{org_id}"`` fallback."""
        me = _me_with_org("100", "---")
        assert default_account_name(me, set()) == "org-100"

    def test_empty_org_name_with_collision(self) -> None:
        """Org-id fallback also gets the ``-N`` suffix on collision."""
        me = _me_with_org("100", "---")
        assert default_account_name(me, {"org-100"}) == "org-100-2"

    def test_empty_organizations_falls_back_to_account(self) -> None:
        """Empty ``me.organizations`` → literal ``"account"`` fallback."""
        me = MeResponse(organizations={})
        assert default_account_name(me, set()) == "account"

    def test_account_fallback_with_collision(self) -> None:
        """``"account"`` fallback also receives suffix treatment."""
        me = MeResponse(organizations={})
        assert default_account_name(me, {"account"}) == "account-2"

    def test_first_org_wins_when_multiple(self) -> None:
        """Multiple orgs → ``next(iter(me.organizations))`` (insertion order)."""
        me = MeResponse(
            organizations={
                "100": MeOrgInfo(id=100, name="Alpha"),
                "200": MeOrgInfo(id=200, name="Beta"),
            }
        )
        assert default_account_name(me, set()) == "alpha"
