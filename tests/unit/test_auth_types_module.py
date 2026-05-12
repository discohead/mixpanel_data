"""Pin the public ``mixpanel_headless.auth_types`` module surface (B3 / Fix 27).

The module is the single canonical re-export of the v3 auth types. The
tests here check that every name advertised in ``__all__`` resolves to
the same object as the underlying ``_internal/auth/...`` definition,
so we catch silent breakage if a future refactor swaps a re-export for
a copy.
"""

from __future__ import annotations

import mixpanel_headless
from mixpanel_headless import auth_types


def test_all_re_exports_resolve() -> None:
    """Every name in ``__all__`` exists on the module."""
    for name in auth_types.__all__:
        assert hasattr(auth_types, name), (
            f"{name} missing from mixpanel_headless.auth_types"
        )


def test_account_variants_match_internal() -> None:
    """``Account`` / ``ServiceAccount`` / ``OAuthBrowserAccount`` / ``OAuthTokenAccount``
    are the same objects as the internal canonical defs."""
    from mixpanel_headless._internal.auth import account as _account_mod

    assert auth_types.Account is _account_mod.Account
    assert auth_types.ServiceAccount is _account_mod.ServiceAccount
    assert auth_types.OAuthBrowserAccount is _account_mod.OAuthBrowserAccount
    assert auth_types.OAuthTokenAccount is _account_mod.OAuthTokenAccount


def test_session_axes_match_internal() -> None:
    """``Session`` / ``Project`` / ``WorkspaceRef`` / ``ActiveSession`` are canonical."""
    from mixpanel_headless._internal.auth import session as _session_mod

    assert auth_types.Session is _session_mod.Session
    assert auth_types.Project is _session_mod.Project
    assert auth_types.WorkspaceRef is _session_mod.WorkspaceRef
    assert auth_types.ActiveSession is _session_mod.ActiveSession


def test_token_plumbing_matches_internal() -> None:
    """``OAuthTokens`` / ``OAuthClientInfo`` / resolvers are canonical."""
    from mixpanel_headless._internal.auth import token as _token_mod
    from mixpanel_headless._internal.auth import token_resolver as _tr_mod

    assert auth_types.OAuthTokens is _token_mod.OAuthTokens
    assert auth_types.OAuthClientInfo is _token_mod.OAuthClientInfo
    assert auth_types.OnDiskTokenResolver is _tr_mod.OnDiskTokenResolver


def test_bridge_matches_internal() -> None:
    """``BridgeFile`` / ``load_bridge`` are canonical."""
    from mixpanel_headless._internal.auth import bridge as _bridge_mod

    assert auth_types.BridgeFile is _bridge_mod.BridgeFile
    assert auth_types.load_bridge is _bridge_mod.load_bridge


def test_top_level_re_exports_match_auth_types() -> None:
    """``mp.Account`` / ``mp.Session`` / etc. resolve to the same objects."""
    assert mixpanel_headless.Account is auth_types.Account
    assert mixpanel_headless.AccountType is auth_types.AccountType
    assert mixpanel_headless.Region is auth_types.Region
    assert mixpanel_headless.Session is auth_types.Session
    assert mixpanel_headless.Project is auth_types.Project
    assert mixpanel_headless.WorkspaceRef is auth_types.WorkspaceRef
    assert mixpanel_headless.ServiceAccount is auth_types.ServiceAccount
    assert mixpanel_headless.OAuthBrowserAccount is auth_types.OAuthBrowserAccount
    assert mixpanel_headless.OAuthTokenAccount is auth_types.OAuthTokenAccount


def test_types_account_summary_uses_canonical_literals() -> None:
    """``AccountSummary`` ``type`` and ``region`` fields use the canonical Literals.

    Fix 27 deletes the ``_AccountTypeLiteral`` / ``_RegionLiteral`` mirrors
    in ``types.py``. The fields should now be backed by the auth_types
    values so a Literal-extension never silently drifts.
    """
    from typing import get_args

    from mixpanel_headless.types import AccountSummary

    type_field = AccountSummary.model_fields["type"]
    region_field = AccountSummary.model_fields["region"]
    assert set(get_args(type_field.annotation)) == set(get_args(auth_types.AccountType))
    assert set(get_args(region_field.annotation)) == set(get_args(auth_types.Region))
