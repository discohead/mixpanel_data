"""OAuth 2.0 PKCE authentication and Cowork bridge module.

Implements the OAuth 2.0 Authorization Code + PKCE flow for Mixpanel,
including Dynamic Client Registration (RFC 7591), token management,
secure local storage, and the v2 JSON-based credential bridge for
Claude Cowork VMs.

Components:
- PkceChallenge: PKCE verifier/challenge generation (RFC 7636)
- OAuthTokens: Immutable token model with expiry tracking
- OAuthClientInfo: Cached DCR client registration info
- OAuthStorage: Secure JSON file storage for tokens and client info
- OAuthFlow: Flow orchestrator (login, token exchange, refresh)
- CallbackResult: Authorization callback result model
- ensure_client_registered: Dynamic Client Registration helper
- BridgeFile: v2 Cowork credential bridge schema
- load_bridge: Load and validate a bridge file from disk
- default_bridge_search_paths: Default lookup paths consulted by load_bridge
"""

from mixpanel_headless._internal.auth.account import (
    Account,
    AccountType,
    OAuthBrowserAccount,
    OAuthTokenAccount,
    Region,
    ServiceAccount,
    TokenResolver,
)
from mixpanel_headless._internal.auth.bridge import (
    BridgeFile,
    default_bridge_search_paths,
    load_bridge,
)
from mixpanel_headless._internal.auth.callback_server import CallbackResult
from mixpanel_headless._internal.auth.client_registration import (
    ensure_client_registered,
)
from mixpanel_headless._internal.auth.flow import OAuthFlow
from mixpanel_headless._internal.auth.pkce import PkceChallenge
from mixpanel_headless._internal.auth.session import (
    ActiveSession,
    Project,
    Session,
    WorkspaceRef,
)
from mixpanel_headless._internal.auth.storage import (
    OAuthStorage,
    account_dir,
    ensure_account_dir,
)
from mixpanel_headless._internal.auth.token import OAuthClientInfo, OAuthTokens
from mixpanel_headless._internal.auth.token_resolver import OnDiskTokenResolver

__all__ = [
    "Account",
    "AccountType",
    "ActiveSession",
    "BridgeFile",
    "CallbackResult",
    "OAuthBrowserAccount",
    "OAuthClientInfo",
    "OAuthFlow",
    "OAuthStorage",
    "OAuthTokenAccount",
    "OAuthTokens",
    "OnDiskTokenResolver",
    "PkceChallenge",
    "Project",
    "Region",
    "ServiceAccount",
    "Session",
    "TokenResolver",
    "WorkspaceRef",
    "account_dir",
    "default_bridge_search_paths",
    "ensure_account_dir",
    "ensure_client_registered",
    "load_bridge",
]
