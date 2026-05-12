# Feature Specification: Authentication, Project & Workspace Management Redesign

**Feature Branch**: `038-auth-project-workspace-redesign`  
**Created**: 2026-04-07  
**Status**: Draft  
**Input**: User description: "ALL phases of @context/auth-project-workspace-redesign.md"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Add Credentials Without Project Binding (Priority: P1)

A user wants to register their Mixpanel service account credentials without needing to know or specify a project ID upfront. Today, adding an account requires a project ID, forcing users to find it externally before they can even authenticate. With the redesign, users register their credentials (username + secret + region) as a standalone identity, then discover and select projects afterward.

**Why this priority**: This is the foundational change — decoupling "who you are" from "what you're working on." Every other feature depends on credentials existing independently of projects. Without this, the current duplication problem persists (7 identical credential entries differing only in project_id).

**Independent Test**: Can be fully tested by adding a credential via `mp auth add <name> -u <username>` without any `--project` flag, verifying it is stored in the config file, and confirming the credential can generate valid authorization headers.

**Acceptance Scenarios**:

1. **Given** a user has a service account username and secret, **When** they run `mp auth add my-sa -u "user.abc.mp-service-account"` and provide their secret interactively, **Then** a credential entry is saved to the config file containing only authentication fields (username, secret, region) with no project_id.
2. **Given** a user has an existing v1 config with 7 accounts sharing the same credentials, **When** they add a new credential in v2 format, **Then** it is stored as a single credential entry without duplication.
3. **Given** a user provides the `--project` flag during `mp auth add`, **Then** the system creates both a credential entry and a project alias for backward compatibility.
4. **Given** a user has only credentials configured (no active project selected), **When** they attempt to run a query command, **Then** the system provides a clear error message directing them to select a project via `mp projects switch` or `mp projects list`.

---

### User Story 2 - Discover Accessible Projects (Priority: P1)

A user who has registered their credentials wants to see all Mixpanel projects they have access to. Today, users must know their project IDs from external sources (Mixpanel webapp, documentation, or colleagues). With the redesign, users run a single command or API call to list all accessible projects with names, IDs, organizations, and metadata.

**Why this priority**: Discovery is the bridge between authentication (Story 1) and productive work. Without it, users still need out-of-band project ID knowledge, defeating the purpose of the redesign.

**Independent Test**: Can be fully tested by running `mp projects list` after adding credentials, verifying the output contains project names, IDs, and organization information matching what the user can access in the Mixpanel webapp.

**Acceptance Scenarios**:

1. **Given** a user has valid credentials configured, **When** they run `mp projects list`, **Then** they see a list of all projects accessible by those credentials, including project ID, name, organization name, and whether the project has workspaces.
2. **Given** a user has valid credentials configured, **When** they call `ws.discover_projects()` in Python, **Then** they receive a list of project objects with the same information.
3. **Given** the project list was fetched within the last 24 hours, **When** the user runs `mp projects list` again, **Then** the cached result is returned instantly without calling the remote API.
4. **Given** the user wants fresh data, **When** they run `mp projects list --refresh`, **Then** the cache is bypassed and the remote API is called.
5. **Given** the credentials are invalid or expired, **When** the user runs `mp projects list`, **Then** a clear authentication error is shown with instructions to re-authenticate.

---

### User Story 3 - Select and Persist Active Project (Priority: P1)

A user who has discovered their projects wants to select one as their active project. This selection should persist across sessions — when they open a new terminal or start a new Python script, they should automatically be working with their previously selected project.

**Why this priority**: Persistent context eliminates the most common friction: re-specifying project IDs every session. This is what makes the system feel "stateful" and natural.

**Independent Test**: Can be fully tested by running `mp projects switch <id>`, closing the terminal, opening a new one, and running a query command — confirming it targets the previously selected project without any additional flags.

**Acceptance Scenarios**:

1. **Given** a user has discovered their projects, **When** they run `mp projects switch 3713224`, **Then** the active project is set to 3713224 and persisted to the config file.
2. **Given** an active project is persisted, **When** the user opens a new terminal and runs `mp query segmentation -e Login --from 2025-01-01 --to 2025-01-31`, **Then** the query targets the persisted project without needing `--project`.
3. **Given** an active project is persisted, **When** the user creates a new `Workspace()` in Python without arguments, **Then** the Workspace uses the persisted active project.
4. **Given** the user wants to temporarily override the active project, **When** they pass `--project <id>` on the command line, **Then** the override is used for that command only; the persisted active project remains unchanged.
5. **Given** the user switches projects, **When** they run `mp context show`, **Then** they see their current credential, active project name/ID, and active workspace (if any).

---

### User Story 4 - Discover and Select Workspaces (Priority: P2)

A user working with a project that has workspaces wants to discover available workspaces and select one. Today, workspace IDs must be set programmatically per session and are lost when the session ends.

**Why this priority**: Workspace management is important for users working in multi-workspace projects, but many projects don't use workspaces at all. This story builds on the project selection foundation (P1 stories).

**Independent Test**: Can be fully tested by running `mp workspaces list` for a project with workspaces, selecting one via `mp workspaces switch <id>`, and verifying it persists and is used by subsequent commands.

**Acceptance Scenarios**:

1. **Given** the active project has workspaces, **When** the user runs `mp workspaces list`, **Then** they see all workspaces with ID, name, and which one is the default.
2. **Given** the user selects a workspace via `mp workspaces switch <id>`, **Then** the workspace is persisted to the config and used by subsequent commands.
3. **Given** the user selects a project that has workspaces but no workspace is explicitly selected, **Then** the system auto-selects the default workspace.
4. **Given** the active project has no workspaces, **When** the user runs `mp workspaces list`, **Then** they see a clear message indicating the project does not use workspaces.
5. **Given** a user calls `ws.discover_workspaces()` in Python, **Then** they receive a list of workspace objects for the current project.

---

### User Story 5 - Switch Projects In-Session (Priority: P2)

A developer or AI agent working in a Python session wants to switch between projects without creating a new Workspace instance. They want to query one project, switch, and query another — all with the same credentials and session.

**Why this priority**: Multi-project workflows are common for agents and power users who need to compare data across projects. In-session switching avoids the overhead of re-constructing Workspace objects.

**Independent Test**: Can be fully tested by creating a Workspace, querying events, calling `ws.switch_project("other-id")`, querying events again, and verifying the results come from two different projects.

**Acceptance Scenarios**:

1. **Given** a Workspace is created with one project, **When** the user calls `ws.switch_project("other-id")`, **Then** subsequent queries target the new project.
2. **Given** a project switch occurs, **Then** the discovery cache (events, properties) is cleared since schema differs per project.
3. **Given** a project switch occurs, **Then** the authentication credentials remain the same (no re-authentication).
4. **Given** a user calls `ws.switch_workspace(workspace_id)`, **Then** the workspace changes without affecting the project or credentials.
5. **Given** a Workspace after switching, **When** the user accesses `ws.current_project`, **Then** they see the updated project context.

---

### User Story 6 - Migrate Existing Configuration (Priority: P2)

A user with an existing v1 configuration (multiple accounts with duplicated credentials) wants to migrate to the new v2 format. The migration should be safe, reversible, and preserve all access — they should be able to do everything they could before, with less config duplication.

**Why this priority**: Migration is essential for existing users but is a one-time operation. It enables the new features but doesn't itself provide new functionality.

**Independent Test**: Can be fully tested by running `mp auth migrate` on a v1 config, verifying the v2 config is correct, verifying a backup was created, and confirming all previous projects are still accessible.

**Acceptance Scenarios**:

1. **Given** a v1 config with 7 accounts sharing the same credentials, **When** the user runs `mp auth migrate`, **Then** a v2 config is created with 1 credential entry and 7 project aliases.
2. **Given** migration is run, **Then** a backup of the original config is saved to `config.toml.v1.bak`.
3. **Given** a migrated config, **When** the user runs `mp projects list`, **Then** all previously accessible projects are still accessible.
4. **Given** a v2 config, **When** the user uses the legacy `Workspace(account="ai-demo")` syntax, **Then** it resolves correctly via the project alias.
5. **Given** a user who hasn't migrated, **When** they continue using v1 config, **Then** all existing functionality works unchanged — migration is never forced.

---

### User Story 7 - Create and Use Project Aliases (Priority: P3)

A user who frequently works with specific projects wants to create named shortcuts that bundle a project ID, credential, and optional default workspace into a single name. This lets them switch contexts with a single command.

**Why this priority**: Aliases are a quality-of-life feature that builds on top of the core switching mechanism. Useful but not essential.

**Independent Test**: Can be fully tested by creating an alias via `mp projects alias add ecom --project 3018488 --credential demo-sa`, then switching via `mp context switch ecom`, and verifying the correct project and credential are active.

**Acceptance Scenarios**:

1. **Given** a user has credentials and knows their project IDs, **When** they run `mp projects alias add ecom --project 3018488 --credential demo-sa`, **Then** an alias named "ecom" is saved to the config.
2. **Given** an alias exists, **When** the user runs `mp context switch ecom`, **Then** the active credential, project, and workspace all update to match the alias.
3. **Given** an alias includes a default workspace, **Then** switching to that alias also sets the active workspace.
4. **Given** the user runs `mp projects alias list`, **Then** they see all aliases with their project IDs, credential names, and workspace IDs.

---

### User Story 8 - View Current Context (Priority: P3)

A user or agent wants to quickly see their current working context: which credential they're authenticated with, which project they're targeting, and which workspace is active.

**Why this priority**: Context visibility is a diagnostic/UX feature. Important but not blocking — users can always check their config file directly.

**Independent Test**: Can be fully tested by running `mp context show` and verifying the output includes credential name, type, region, project name/ID, and workspace name/ID.

**Acceptance Scenarios**:

1. **Given** a fully configured active context, **When** the user runs `mp context show`, **Then** they see credential name, type, region, project name, project ID, workspace name, and workspace ID.
2. **Given** no active project is set, **When** the user runs `mp context show`, **Then** they see their credential info and a message indicating no project is selected.
3. **Given** a Workspace instance in Python, **When** the user accesses `ws.current_project` and `ws.current_credential`, **Then** they receive structured objects with the active context.

---

### User Story 9 - OAuth Authentication with Project Discovery (Priority: P2)

A user wants to log in via OAuth (browser-based) and then discover and select a project — without needing to specify a project ID during login. Today, OAuth login optionally accepts `--project-id`, and if omitted, the token's project_id is None, causing confusing fallback behavior.

**Why this priority**: OAuth is a key auth method, especially for interactive users. Fixing the project_id=None problem is important for reliability.

**Independent Test**: Can be fully tested by running `mp auth login` (without --project), then `mp projects list` to see accessible projects, then `mp projects switch <id>` to select one.

**Acceptance Scenarios**:

1. **Given** a user runs `mp auth login` without `--project-id`, **When** they authenticate successfully, **Then** the OAuth token is stored without a project_id, and the user is prompted to select a project via `mp projects list` and `mp projects switch`.
2. **Given** a valid OAuth token exists and an active project is set in config, **When** the user runs any query command, **Then** the OAuth token is used for authentication and the active project from config determines the target project (not from the token).
3. **Given** a valid OAuth token and valid service account credentials both exist, **When** the active credential in config is the OAuth one, **Then** OAuth is used; when the active credential is the service account, **Then** Basic Auth is used — no ambiguity or silent override.

---

### User Story 10 - Environment Variable Override (Priority: P3)

A user in a CI/CD or scripting environment wants to use environment variables to fully specify credentials and project, overriding all config file settings. This existing behavior must be preserved exactly.

**Why this priority**: Environment variable override is an existing feature that must not regress. It's critical for automation but doesn't need new design — just preservation.

**Independent Test**: Can be fully tested by setting `MP_USERNAME`, `MP_SECRET`, `MP_PROJECT_ID`, and `MP_REGION`, then running any command and verifying the env vars take priority over all config settings.

**Acceptance Scenarios**:

1. **Given** all four environment variables are set (`MP_USERNAME`, `MP_SECRET`, `MP_PROJECT_ID`, `MP_REGION`), **When** any command is run, **Then** environment variables take absolute priority over config file, OAuth tokens, and all other resolution methods.
2. **Given** partial environment variables are set (e.g., only `MP_PROJECT_ID`), **Then** they do not trigger env var resolution; the system falls through to config-based resolution.
3. **Given** environment variables are set AND a `--credential` flag is provided, **Then** environment variables still take priority.

---

### Edge Cases

- What happens when a credential is removed but project aliases still reference it? The system should warn about orphaned aliases.
- What happens when the /me cache contains stale data (e.g., user lost access to a project)? Query commands should return clear authentication/permission errors, and `mp projects refresh` should update the cache.
- What happens during concurrent config writes from multiple terminal sessions? Writes should be atomic (write to temp file + rename) to prevent corruption.
- What happens when a user has credentials for multiple regions? Each region has its own OAuth tokens and /me cache; credentials specify their region, and the system uses the correct endpoint for each.
- What happens when the /me API returns unexpected new fields? Forward-compatible deserialization should preserve unknown fields without errors.
- What happens if a service account cannot call the /me endpoint? The system should gracefully fall back to requiring explicit project_id specification, with a clear error message.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow adding credentials (username + secret + region) without requiring a project ID.
- **FR-002**: System MUST allow adding credentials with an optional project ID for backward compatibility (creates both credential and project alias).
- **FR-003**: System MUST store credentials and project selections as separate entities in the config file.
- **FR-004**: System MUST persist an "active context" (credential + project + workspace) across sessions in the config file.
- **FR-005**: System MUST provide project discovery by querying the Mixpanel /me API and returning all accessible projects with names, IDs, and organization info.
- **FR-006**: System MUST cache /me API responses to disk with a default 24-hour TTL to avoid repeated slow API calls.
- **FR-007**: System MUST allow users to force-refresh the /me cache on demand.
- **FR-008**: System MUST invalidate the /me cache on logout, login, and credential changes.
- **FR-009**: System MUST allow switching the active project via CLI command, persisting the selection to config.
- **FR-010**: System MUST allow switching the active workspace via CLI command, persisting the selection to config.
- **FR-011**: System MUST provide workspace discovery (list workspaces for a project) via CLI and Python API.
- **FR-012**: System MUST auto-select the default workspace when a project is selected and no workspace is explicitly specified.
- **FR-013**: System MUST support in-session project switching in the Python API without creating a new Workspace instance.
- **FR-014**: System MUST clear discovery caches (events, properties) when switching projects in-session.
- **FR-015**: System MUST support named project aliases that bundle a credential, project ID, and optional workspace ID.
- **FR-016**: System MUST provide a context display command showing current credential, project, and workspace.
- **FR-017**: System MUST migrate v1 config to v2 format on user request, grouping duplicate credentials and creating project aliases.
- **FR-018**: System MUST back up the v1 config before migration and never force migration.
- **FR-019**: System MUST continue to support v1 config format for users who don't migrate.
- **FR-020**: System MUST support both v1 and v2 configs simultaneously — all existing commands work with either format.
- **FR-021**: System MUST preserve existing environment variable override behavior (all four env vars required, highest priority).
- **FR-022**: System MUST preserve the existing `Workspace(account="name")` constructor for backward compatibility.
- **FR-023**: System MUST support OAuth authentication without requiring a project ID at login time.
- **FR-024**: System MUST resolve OAuth project context from the active config (not from the token's optional project_id field).
- **FR-025**: System MUST use forward-compatible deserialization for /me API responses (unknown fields preserved, not rejected).
- **FR-026**: System MUST use atomic file writes (temp file + rename) for config changes to prevent corruption.
- **FR-027**: System MUST store cached /me responses with restricted file permissions (owner-only read/write).
- **FR-028**: System MUST provide global CLI flags (`--credential`, `--project`) for per-command overrides without modifying the persisted active context.

### Key Entities

- **Credential**: An authentication identity (service account or OAuth) with a name, type, and region. Independent of any project. One credential can access many projects.
- **Project**: A Mixpanel project identified by its ID, with a name and organization. Discovered via the /me API. Can contain zero or more workspaces.
- **Workspace**: A sub-division within a project, identified by ID. Has a name and a default flag. Discovered via the /me API or the workspaces API.
- **Project Alias**: A named shortcut that binds a credential, project ID, and optional workspace ID for quick context switching.
- **Active Context**: The currently selected credential + project + workspace, persisted in the config file and used as the default for all operations.
- **Me Response**: Cached response from the /me API containing all organizations, projects, and workspaces accessible by a credential. Stored to disk with TTL-based expiration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can register credentials and begin querying data in under 3 commands (add credential, list projects, switch project), compared to the current minimum of 1 command that requires prior knowledge of the project ID.
- **SC-002**: A service account with access to N projects requires exactly 1 credential entry in the config file, compared to the current N duplicate entries.
- **SC-003**: Active project and workspace selections persist across 100% of new sessions (terminal restarts, new Python scripts) without re-specification.
- **SC-004**: Project discovery returns results within 2 seconds on subsequent calls (via cache), regardless of the number of accessible projects.
- **SC-005**: All existing tests pass without modification after the redesign — zero regressions in backward compatibility.
- **SC-006**: Users can switch between projects within a Python session without re-authenticating or creating new Workspace instances.
- **SC-007**: Config migration from v1 to v2 preserves 100% of project access — every project accessible before migration remains accessible after.
- **SC-008**: The system correctly resolves credentials in all priority scenarios: env vars > explicit params > active context > OAuth fallback, with no silent incorrect resolution.
- **SC-009**: OAuth users can authenticate and begin working without ever specifying a project ID during the login flow.
- **SC-010**: AI agents can programmatically discover all accessible projects and switch between them using only the Python API (no CLI required).

## Assumptions

- The Mixpanel /me API supports both Service Account (Basic Auth) and OAuth (Bearer) authentication, as confirmed by the Django source code's `@auth_required(["user_details"])` decorator.
- The /me API response structure is stable enough that forward-compatible deserialization (accepting unknown fields) will handle minor API changes without breaking.
- Organization/project/workspace membership changes infrequently enough that a 24-hour cache TTL provides acceptable freshness for most users.
- Users are willing to run an explicit migration command (`mp auth migrate`) to convert their v1 config; the system will never auto-migrate.
- The existing `~/.mp/` directory structure and `~/.mp/oauth/` token storage locations will be preserved and extended (not replaced).
- Python 3.10+ is the minimum supported version, consistent with the existing project requirements.
- The config file format remains TOML, consistent with the existing implementation.
- Concurrent multi-user access to the same config file is not a supported use case; atomic writes protect against corruption from the same user's concurrent terminal sessions.
- The /me API may be slow (2-5 seconds observed) on first call, which is acceptable given aggressive caching.
