"""Pure-functional account-name derivation from /me (043 / AIE-116).

Provides two helpers used by the ``mp login`` orchestrator and the
relaxed ``mp account add`` to invent a sensible local account name
when the user does not supply one explicitly:

- :func:`slugify` — reduces an arbitrary org name (or any string) to
  the ``[a-z0-9-]{0,32}`` subset using NFKD normalization, ASCII
  folding, lowercasing, and run-collapsing.
- :func:`default_account_name` — picks the first organization from a
  :class:`MeResponse`, slugifies its name, and applies a ``-2`` /
  ``-3`` / ... collision suffix when the slug is already taken.

Both functions are pure: no I/O, no ``os.environ`` access, no clock
reads, no random sampling. Determinism is required for the property
tests in ``tests/pbt/test_naming_pbt.py`` and for the mutation-testing
guarantee in ``just mutate``.

Reference: ``specs/043-frictionless-auth/contracts/python-api.md`` §2.2.
"""

from __future__ import annotations

import re
import unicodedata

from mixpanel_headless._internal.auth.account import AccountName
from mixpanel_headless._internal.me import MeResponse

_SLUG_MAX_LEN = 32
"""Upper bound on slug length. Leaves headroom under the
``_AccountBase.name`` 64-char ceiling so ``-2`` collision suffixes never
push a derived name over the model constraint."""

_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")
"""Matches any run of characters that are not part of the slug alphabet
(lowercase ASCII letters or digits). Replaced with a single ``-``."""


def slugify(value: str | None) -> str:
    """Reduce an org name to the ``[a-z0-9-]{0,32}`` subset.

    Six-step normalization (applied in order):

    1. Coerce ``None`` / empty input to ``""``.
    2. NFKD-normalize and ASCII-fold (drops accents:
       ``"Café"`` → ``"cafe"``; collapses ligatures and width
       variants).
    3. Lowercase.
    4. Replace any run of non-``[a-z0-9]`` characters with a single
       ``"-"``.
    5. Strip leading and trailing ``"-"``.
    6. Truncate to 32 characters; strip any trailing ``"-"`` left by
       the truncation.

    Args:
        value: An arbitrary string (typically an organization name).
            ``None`` is treated as the empty string.

    Returns:
        The slug, matching ``^[a-z0-9-]{0,32}$``. Empty string when no
        input characters survived normalization (e.g. for ``"---"``).
        Callers MUST handle the empty-string case (typically by
        falling back to ``f"org-{org_id}"``).

    Example:
        ```python
        slugify("Acme Corp")           # "acme-corp"
        slugify("Café Industries")     # "cafe-industries"
        slugify("  Acme  &  Sons ")    # "acme-sons"
        slugify("---")                 # ""
        ```
    """
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    folded = normalized.encode("ascii", errors="ignore").decode("ascii")
    lowered = folded.lower()
    dashed = _NON_SLUG_CHARS.sub("-", lowered).strip("-")
    if len(dashed) <= _SLUG_MAX_LEN:
        return dashed
    return dashed[:_SLUG_MAX_LEN].rstrip("-")


def default_account_name(me: MeResponse, existing: set[str]) -> AccountName:
    """Pick a default account name from ``/me``, suffixing on collision.

    Picks the first organization from ``me.organizations`` (insertion
    order of the dict — Python 3.7+ preserves this) as the slug
    source. When the slugified org name is empty, falls back to
    ``f"org-{org_id}"``. When ``me.organizations`` is itself empty,
    falls back to the literal ``"account"``. Collision suffixes start
    at ``-2`` (not ``-1``) and increment monotonically until a unique
    name is found.

    Args:
        me: Parsed ``/me`` response.
        existing: Set of already-taken local account names. Caller
            populates from ``ConfigManager.list_accounts()``. Treated
            as immutable; not modified.

    Returns:
        A unique :data:`AccountName` matching ``^[a-zA-Z0-9_-]{1,64}$``.
        Wrapped in the NewType so callers that thread the value
        through typed signatures (``ConfigManager._apply_add_account``,
        the orchestrator helpers) keep mypy's discrimination between
        "any string" and "validated account name".

    Example:
        ```python
        # me.organizations == {"100": MeOrgInfo(id=100, name="Acme Corp")}
        default_account_name(me, set())
        # AccountName("acme-corp")

        default_account_name(me, {"acme-corp"})
        # AccountName("acme-corp-2")
        ```
    """
    if not me.organizations:
        base = "account"
    else:
        first_org_id, first_org = next(iter(me.organizations.items()))
        base = slugify(first_org.name)
        if not base:
            base = f"org-{first_org_id}"
    if base not in existing:
        return AccountName(base)
    suffix = 2
    while True:
        candidate = f"{base}-{suffix}"
        if candidate not in existing:
            return AccountName(candidate)
        suffix += 1
