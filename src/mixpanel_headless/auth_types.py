"""Public auth-types module — single source of truth for the auth surface.

Consolidates the stable types from the ``_internal/auth/*`` package into
one importable module so callers can ``from mixpanel_headless.auth_types
import Account, Session, ...`` without reaching into ``_internal``.

The actual class definitions still live under ``_internal/auth/`` because
they need to share helper functions and a mature module structure;
``auth_types`` re-exports them so the public surface is one focused
import path. ``mixpanel_headless.__init__`` imports from here too, which
keeps the top-level ``mp.Account`` / ``mp.Session`` / etc. names backed
by the same single source.

Reference: ``specs/042-auth-architecture-redesign/contracts/python-api.md``.
"""

from mixpanel_headless._internal.auth.account import (
    Account,
    AccountName,
    AccountType,
    OAuthBrowserAccount,
    OAuthTokenAccount,
    ProjectId,
    Region,
    ServiceAccount,
    TargetName,
    TokenResolver,
    WorkspaceId,
)
from mixpanel_headless._internal.auth.bridge import BridgeFile, load_bridge
from mixpanel_headless._internal.auth.session import (
    ActiveSession,
    Project,
    Session,
    WorkspaceRef,
)
from mixpanel_headless._internal.auth.token import OAuthClientInfo, OAuthTokens
from mixpanel_headless._internal.auth.token_resolver import OnDiskTokenResolver

__all__ = [
    # Discriminated-union account type + variants
    "Account",
    "AccountType",
    "OAuthBrowserAccount",
    "OAuthTokenAccount",
    "ServiceAccount",
    "Region",
    # Phantom-typed identifiers (NewType — str/int at runtime, distinct in mypy)
    "AccountName",
    "ProjectId",
    "WorkspaceId",
    "TargetName",
    # Session + axes
    "ActiveSession",
    "Project",
    "Session",
    "WorkspaceRef",
    # OAuth token plumbing
    "OAuthClientInfo",
    "OAuthTokens",
    "TokenResolver",
    "OnDiskTokenResolver",
    # Cowork bridge
    "BridgeFile",
    "load_bridge",
]
