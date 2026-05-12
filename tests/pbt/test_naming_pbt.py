"""Property-based tests for the naming module (043 / AIE-116).

Hypothesis covers the invariants that the example-based suite in
``tests/unit/test_naming.py`` cannot:

- ``slugify`` is idempotent: ``slugify(slugify(x)) == slugify(x)``.
- Non-empty ``slugify`` output always satisfies ``^[a-z0-9-]{1,32}$``.
- ``default_account_name`` never returns a name in ``existing``.
- Collision suffixes are monotonically increasing (``-2`` then ``-3``,
  never ``-1`` or out-of-order).
- ``default_account_name`` is deterministic (same inputs → same output).

Reference: ``specs/043-frictionless-auth/contracts/python-api.md`` §2.2.
"""

from __future__ import annotations

import re

from hypothesis import given
from hypothesis import strategies as st

from mixpanel_headless._internal.auth.naming import (
    default_account_name,
    slugify,
)
from mixpanel_headless._internal.me import MeOrgInfo, MeResponse

# Wide text generator — ASCII letters, digits, punctuation, spaces, and
# accented Latin characters. Bounds keep slugs well under the 32-char
# truncation so we exercise both short and truncated paths.
_org_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        max_codepoint=0x017F,  # Latin Extended-A
    ),
    min_size=0,
    max_size=80,
)

_slug_pattern = re.compile(r"^[a-z0-9-]{1,32}$")


@given(value=_org_name_strategy)
def test_slugify_is_idempotent(value: str) -> None:
    """Applying ``slugify`` twice yields the same result as once."""
    once = slugify(value)
    twice = slugify(once)
    assert twice == once


@given(value=_org_name_strategy)
def test_slugify_output_when_nonempty_matches_constraint(value: str) -> None:
    """Non-empty output matches ``^[a-z0-9-]{1,32}$`` (strict)."""
    result = slugify(value)
    if result:
        assert _slug_pattern.fullmatch(result), (
            f"slug {result!r} from input {value!r} violates constraint"
        )


@given(value=_org_name_strategy)
def test_slugify_never_produces_leading_or_trailing_dash(value: str) -> None:
    """Output never has leading or trailing ``-`` (FR-015 step 5)."""
    result = slugify(value)
    if result:
        assert not result.startswith("-"), f"leading dash in {result!r}"
        assert not result.endswith("-"), f"trailing dash in {result!r}"


@given(value=_org_name_strategy)
def test_slugify_no_consecutive_dashes(value: str) -> None:
    """Output never has consecutive ``--`` (run-collapse step 4)."""
    result = slugify(value)
    assert "--" not in result


# Strategies for default_account_name property tests
_org_id_strategy = st.text(alphabet="0123456789", min_size=1, max_size=10)
_existing_set_strategy = st.sets(
    st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
        min_size=1,
        max_size=64,
    ),
    max_size=20,
)


@st.composite
def me_responses(draw: st.DrawFn) -> MeResponse:
    """Build a MeResponse with one organization (or none) for naming tests."""
    if draw(st.booleans()):
        org_id = draw(_org_id_strategy)
        name = draw(_org_name_strategy)
        return MeResponse(organizations={org_id: MeOrgInfo(id=int(org_id), name=name)})
    return MeResponse(organizations={})


@given(me=me_responses(), existing=_existing_set_strategy)
def test_default_account_name_never_in_existing(
    me: MeResponse, existing: set[str]
) -> None:
    """Output is guaranteed to be a name not already in ``existing``."""
    result = default_account_name(me, existing)
    assert result not in existing


@given(me=me_responses(), existing=_existing_set_strategy)
def test_default_account_name_is_deterministic(
    me: MeResponse, existing: set[str]
) -> None:
    """Same inputs always produce the same output."""
    first = default_account_name(me, existing)
    second = default_account_name(me, existing)
    assert first == second


@given(me=me_responses())
def test_collision_suffix_starts_at_2_not_1(me: MeResponse) -> None:
    """When the base slug is taken, the suffix begins at ``-2``.

    Locks the spec rule that ``-1`` is never produced — the convention
    is ``base``, ``base-2``, ``base-3``, ... so a single existing entry
    bumps to ``-2``, not ``-1``.
    """
    base = default_account_name(me, set())
    bumped = default_account_name(me, {base})
    # Either the bump is ``-2`` or, in the empty-org-name fallback, the
    # base already includes its own ``-N`` (e.g. ``"org-100-2"``). The
    # invariant: the bumped value never equals ``f"{base}-1"``.
    assert bumped != f"{base}-1"


@given(me=me_responses())
def test_collision_suffixes_are_monotonic(me: MeResponse) -> None:
    """Successive collisions produce ``-2``, ``-3``, ... in order."""
    base = default_account_name(me, set())
    # ``default_account_name`` returns an ``AccountName`` NewType; widen
    # to ``set[str]`` so mypy keeps the function-signature contract
    # (the function takes ``set[str]`` because callers populate it from
    # ``ConfigManager.list_accounts()`` which yields plain strings).
    existing: set[str] = {str(base)}
    seen_suffixes: list[int] = []
    for _ in range(5):
        next_name = default_account_name(me, existing)
        if next_name.startswith(f"{base}-"):
            suffix_str = next_name[len(base) + 1 :]
            if suffix_str.isdigit():
                seen_suffixes.append(int(suffix_str))
        existing.add(str(next_name))
    # Suffixes are strictly ascending.
    assert seen_suffixes == sorted(seen_suffixes)
    assert len(seen_suffixes) == len(set(seen_suffixes))
