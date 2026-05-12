# Feature Specification: OAuth PKCE & App API Infrastructure

**Feature Branch**: `023-oauth-app-api-infra`
**Created**: 2026-03-25
**Status**: Draft
**Input**: Phase 0 architectural prerequisites — OAuth 2.0 PKCE authentication and App API request infrastructure enabling all future CRUD operations across 15+ Mixpanel entity domains.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Interactive OAuth Login (Priority: P1)

A developer using the `mp` CLI wants to authenticate with their Mixpanel account so they can access App API endpoints (dashboards, reports, cohorts, flags, etc.) that require OAuth credentials rather than service account Basic Auth.

**Why this priority**: Without OAuth authentication, no App API CRUD operation is possible. This is the foundational prerequisite for all subsequent features (Phases 1–5).

**Independent Test**: Can be fully tested by running `mp auth login`, completing the browser-based OAuth flow, and verifying that tokens are persisted locally. Delivers value by unlocking App API access.

**Acceptance Scenarios**:

1. **Given** the user has no stored OAuth tokens, **When** they run `mp auth login`, **Then** the system opens their default browser to Mixpanel's authorization page, starts a local callback server, and waits for the redirect.
2. **Given** the browser redirect completes with an authorization code, **When** the system exchanges the code for tokens, **Then** access and refresh tokens are securely stored on disk with restricted file permissions.
3. **Given** the user completes login successfully, **When** they run `mp auth status`, **Then** they see confirmation of their authenticated state including token expiry information.
4. **Given** the user is already authenticated, **When** they run `mp auth login` again, **Then** the system refreshes their existing tokens (or re-authenticates if refresh fails).
5. **Given** the user wants to switch accounts or clear tokens, **When** they run `mp auth logout`, **Then** all stored OAuth tokens are removed from disk.

---

### User Story 2 - Automatic Token Lifecycle Management (Priority: P1)

A developer using the library programmatically wants token refresh and expiry to be handled automatically so they don't need to manage OAuth token lifecycle themselves.

**Why this priority**: Without transparent token management, every API call would require manual token checks, making the library impractical for automation and scripting.

**Independent Test**: Can be tested by authenticating once, waiting for token expiry (or simulating it), and verifying that a subsequent API call automatically refreshes the token without user intervention.

**Acceptance Scenarios**:

1. **Given** a valid access token exists, **When** the user makes an App API request, **Then** the system uses the stored Bearer token without prompting.
2. **Given** the access token has expired but the refresh token is valid, **When** the user makes an App API request, **Then** the system automatically refreshes the access token and retries the request transparently.
3. **Given** both access and refresh tokens are expired or invalid, **When** the user makes an App API request, **Then** the system raises a clear error indicating re-authentication is needed.
4. **Given** a token refresh is in progress, **When** the refreshed token is obtained, **Then** the new tokens are persisted to disk so other processes can use them.

---

### User Story 3 - App API Requests with Workspace Scoping (Priority: P1)

A developer wants to make requests to Mixpanel's App API endpoints (e.g., list dashboards, create cohorts) with automatic workspace scoping so that API calls target the correct organizational context.

**Why this priority**: App API infrastructure (request method, Bearer auth, workspace scoping, pagination) is required by every domain that follows. Without it, no CRUD operations can be built.

**Independent Test**: Can be tested by calling `list_workspaces()` to discover available workspaces, then making a workspace-scoped App API request (e.g., listing dashboards) and verifying the correct workspace context is applied.

**Acceptance Scenarios**:

1. **Given** valid OAuth credentials and a project ID, **When** the user calls `list_workspaces()`, **Then** the system returns a list of workspaces available in the project.
2. **Given** no explicit workspace ID is set, **When** the user makes an App API request for a domain that requires workspace scoping, **Then** the system auto-discovers the workspace ID from the project's available workspaces.
3. **Given** the user provides an explicit workspace ID (via parameter or CLI flag), **When** they make an App API request, **Then** the system uses the provided workspace ID for scoping.
4. **Given** App API results span multiple pages, **When** the user requests all results, **Then** the system automatically follows cursor-based pagination and aggregates all pages.
5. **Given** a workspace cannot be resolved (no workspaces found or ambiguous), **When** the user makes a workspace-scoped request, **Then** the system raises a clear error explaining the issue and how to resolve it.

---

### User Story 4 - Credential Resolution with OAuth Support (Priority: P2)

A developer wants the existing credential resolution system to seamlessly support OAuth as an additional authentication method alongside Basic Auth, so they can use whichever method is appropriate for their use case.

**Why this priority**: Backward compatibility with existing Basic Auth workflows is essential. OAuth should augment, not replace, the existing auth system.

**Independent Test**: Can be tested by verifying that existing Basic Auth workflows continue working unchanged, and that OAuth credentials are preferred when available for App API endpoints.

**Acceptance Scenarios**:

1. **Given** environment variables (`MP_USERNAME`, `MP_SECRET`, etc.) are set, **When** the user creates a Workspace, **Then** Basic Auth credentials resolve exactly as before (no regression).
2. **Given** stored OAuth tokens exist and no environment variables are set, **When** the user makes an App API request, **Then** OAuth Bearer auth is used automatically.
3. **Given** both Basic Auth credentials and OAuth tokens are available, **When** the user makes a request to a query/export endpoint, **Then** Basic Auth is used (as before). **When** they make a request to an App API endpoint, **Then** the appropriate auth method is selected based on endpoint type.
4. **Given** OAuth tokens exist but are for a different project, **When** the user makes a request, **Then** the system handles the mismatch gracefully with a clear error.

---

### User Story 5 - CLI Workspace Selection (Priority: P2)

A CLI user wants to specify which workspace to target for App API operations, either via a global flag or automatic discovery, so they can manage multi-workspace projects.

**Why this priority**: Many Mixpanel projects have multiple workspaces. CLI users need a way to target the correct one without hardcoding.

**Independent Test**: Can be tested by running any App API CLI command with and without `--workspace-id` and verifying correct workspace targeting.

**Acceptance Scenarios**:

1. **Given** the user provides `--workspace-id 12345` as a global CLI flag, **When** they run an App API command, **Then** the system uses workspace 12345 for scoping.
2. **Given** the user does not provide `--workspace-id`, **When** they run an App API command on a single-workspace project, **Then** the system auto-discovers and uses the sole workspace.
3. **Given** the user does not provide `--workspace-id` on a multi-workspace project, **When** they run an App API command, **Then** the system informs them of available workspaces and asks them to specify one.
4. **Given** the user runs `mp auth token`, **When** the command executes, **Then** it outputs the current access token (useful for debugging and external tool integration).

---

### User Story 6 - Secure Token Storage (Priority: P2)

A developer wants OAuth tokens to be stored securely on their local filesystem with appropriate access controls so that credentials are not exposed to other users or processes.

**Why this priority**: OAuth tokens grant broad access to Mixpanel project data. Secure storage is essential for preventing unauthorized access.

**Independent Test**: Can be tested by verifying file permissions on token storage files and confirming tokens are not logged or exposed in CLI output.

**Acceptance Scenarios**:

1. **Given** OAuth tokens are saved, **When** the storage directory and files are created, **Then** the directory has 0o700 permissions and files have 0o600 permissions (owner-only access).
2. **Given** the default storage location (`~/.mp/oauth/`), **When** the user wants a custom location, **Then** they can set the `MP_OAUTH_STORAGE_DIR` environment variable to override it.
3. **Given** token data is stored as JSON, **When** any part of the system logs or displays credential information, **Then** access tokens and refresh tokens are redacted (never shown in plain text).
4. **Given** tokens are persisted on disk, **When** the user runs `mp auth logout`, **Then** all token files are securely deleted.

---

### Edge Cases

- What happens when the local callback server port is already in use? The system tries multiple fallback ports (19284, 19285, 19286, 19287) before failing with a clear error.
- What happens when the browser fails to open? The system displays the authorization URL in the terminal so the user can manually navigate to it.
- What happens when the OAuth callback times out? The system fails gracefully with a clear timeout message after a reasonable wait period.
- What happens when the user's network drops mid-token-exchange? The system reports a clear connection error, not a cryptic OAuth error.
- What happens when the token storage directory has incorrect permissions? The system attempts to fix permissions or warns the user.
- What happens when pagination returns an empty cursor? The system treats this as the final page and stops paginating.
- What happens when a workspace-scoped endpoint is called without any auth? The system raises an error explaining that OAuth login is required for App API operations.
- What happens when the PKCE verifier or challenge fails validation? The system raises a clear error (this would indicate a bug in the implementation).
- What happens when Dynamic Client Registration fails? The system provides a clear error message about the registration failure.

## Requirements *(mandatory)*

### Functional Requirements

**OAuth 2.0 PKCE Authentication**

- **FR-001**: System MUST implement OAuth 2.0 Authorization Code flow with PKCE (RFC 7636) using S256 challenge method.
- **FR-002**: System MUST generate cryptographically secure PKCE verifiers (64 random bytes, base64url-encoded) and compute SHA-256 challenges.
- **FR-003**: System MUST support Dynamic Client Registration (RFC 7591) for registering the CLI application with Mixpanel's OAuth provider.
- **FR-004**: System MUST start an ephemeral local HTTP server to receive the OAuth redirect callback, trying ports 19284–19287 in sequence.
- **FR-005**: System MUST exchange authorization codes for access/refresh token pairs and persist them securely.
- **FR-006**: System MUST automatically refresh expired access tokens using the refresh token, with a 30-second expiry buffer.
- **FR-007**: System MUST store tokens in JSON format at `~/.mp/oauth/` (or `MP_OAUTH_STORAGE_DIR`) with restricted Unix permissions (directory: 0o700, files: 0o600).
- **FR-008**: System MUST provide `login`, `logout`, `status`, and `token` subcommands under `mp auth`.
- **FR-009**: System MUST never expose raw token values in logs, error messages, or standard output (except `mp auth token` which intentionally outputs the access token).

**App API Infrastructure**

- **FR-010**: System MUST support HTTP requests to Mixpanel's App API (`/api/app/...`) endpoints using OAuth Bearer token authentication.
- **FR-011**: System MUST support workspace scoping for App API requests, with both explicit workspace ID and auto-discovery modes.
- **FR-012**: System MUST implement cursor-based pagination for App API responses, automatically fetching all pages when requested.
- **FR-013**: System MUST provide a `--workspace-id` global CLI option for specifying the workspace context.
- **FR-014**: System MUST expose `list_workspaces()` and `resolve_workspace_id()` methods on the Workspace class.
- **FR-015**: System MUST support both optional workspace scoping (top-level URL pattern) and required workspace scoping (project-nested URL pattern) for different App API endpoint styles.

**Credential Resolution**

- **FR-016**: System MUST extend the credential resolution order to: environment variables > OAuth tokens > named account > default account.
- **FR-017**: System MUST preserve full backward compatibility with existing Basic Auth credential resolution.
- **FR-018**: System MUST select the appropriate authentication method (Basic Auth vs. Bearer) based on the API endpoint category (query/export vs. app).

**Error Handling**

- **FR-019**: System MUST define `OAuthError` and `WorkspaceScopeError` exception types within the existing exception hierarchy.
- **FR-020**: System MUST map OAuth-specific HTTP errors (invalid grant, expired token, invalid scope) to structured exception types with actionable messages.
- **FR-021**: System MUST handle App API 4xx/5xx errors through the existing error hierarchy.

### Key Entities

- **Credentials**: Extended to support both Basic Auth (username/secret) and OAuth (access/refresh tokens) authentication methods. Includes an auth method indicator.
- **OAuth Tokens**: Access token, refresh token, expiry timestamp, and scope. Immutable after creation; refreshed tokens produce a new token object.
- **PKCE Challenge**: A verifier/challenge pair used once per authorization flow. The verifier is a cryptographic random string; the challenge is its SHA-256 hash.
- **Workspace**: An organizational unit within a Mixpanel project. Has an ID, name, and project association. Used for scoping App API requests.
- **Paginated Response**: A generic wrapper for App API responses containing a page of results and cursor-based pagination metadata (next cursor, has more).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can complete the full OAuth login flow (browser auth + token storage) in under 60 seconds on a standard connection.
- **SC-002**: Existing Basic Auth workflows (environment variables, named accounts, config file) continue working with zero changes required by users.
- **SC-003**: Token refresh happens transparently — users making sequential App API calls never see an authentication interruption for expired tokens when a valid refresh token exists.
- **SC-004**: All App API requests correctly target the intended workspace, with auto-discovery succeeding on first attempt for single-workspace projects.
- **SC-005**: Paginated App API responses return complete result sets — no data is lost due to pagination boundaries.
- **SC-006**: Token storage files are created with owner-only permissions (verified by file permission checks on the storage directory and files).
- **SC-007**: The system handles all edge cases (port conflicts, browser failures, network errors, timeout) with user-actionable error messages rather than stack traces or cryptic errors.
- **SC-008**: All new code achieves 90%+ test coverage, consistent with the project's existing quality gate.

## Assumptions

- Users have a modern web browser available for the OAuth authorization flow (the browser-based consent step cannot be bypassed).
- Mixpanel's OAuth provider supports Dynamic Client Registration (RFC 7591) for CLI applications. If not, a pre-registered client ID will be hardcoded.
- The existing synchronous HTTP client is sufficient for all OAuth and App API operations; no async HTTP client is needed.
- Token storage uses the local filesystem (`~/.mp/oauth/`). Keychain/credential-store integration is out of scope for this phase.
- The App API's cursor-based pagination uses a consistent scheme across all domains (consistent `next` cursor field and `has_more` indicator).
- Workspace auto-discovery uses the `list_workspaces()` endpoint, which is available to all authenticated users.
- Only Unix-style file permissions (0o700/0o600) are enforced; Windows ACL support is out of scope.
- The OAuth callback server runs on localhost only; it does not need to be accessible from external networks.
- The `mp auth token` command intentionally outputs the raw access token for debugging and external tool integration — this is by design, not a security gap.
- App API endpoints accept both Basic Auth (service accounts) and OAuth Bearer tokens, as indicated by the reference codebase's auth decorators.
