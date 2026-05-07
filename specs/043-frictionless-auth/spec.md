# Feature Specification: Frictionless Auth (`mp login` and `/me`-driven discovery)

**Feature Branch**: `043-frictionless-auth`
**Created**: 2026-05-06
**Status**: Draft
**Input**: User description: "@context/frictionless-auth.md"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One-command browser login for first-time users (Priority: P1)

A new user who has never run the CLI before types `mp login`, completes a browser authentication, and is left with a fully configured account ready to query — no region, no project ID, no local alias typed by hand.

**Why this priority**: This is the headline user experience and the reason the feature exists. Santi's feedback specifically named this flow: *"my ideal auth experience would be: type `mp login`, authenticate in the browser, and everything is configured automatically."* It collapses what is currently a four-fact memorization exercise into a single command. Without this story shipped, none of the other stories matter to a brand-new user.

**Independent Test**: On a machine with no `~/.mp/` directory, run `mp login`, complete the OAuth flow in the browser, and confirm that a subsequent `mp query segmentation -e Login --from 2025-01-01` succeeds without any further configuration. The success line printed at the end of `mp login` names the user, the chosen account name, and the chosen project.

**Acceptance Scenarios**:

1. **Given** a user with one accessible Mixpanel organization containing exactly one project, **When** they run `mp login`, **Then** the browser opens to authenticate, the account name defaults to a slug of the org name, the single project is selected automatically, and the new account is set active.
2. **Given** a user with multiple accessible projects across one or more orgs, **When** they run `mp login` in an interactive terminal, **Then** they are presented with a numbered list of projects sorted alphabetically (with org context shown when more than one org is present) and can pick one by number; pressing Enter accepts the first item.
3. **Given** an existing account with the same name already configured, **When** the user re-runs `mp login` and authenticates as the same user, **Then** tokens are refreshed in place and the previously configured default project is preserved (re-login does not silently rewrite project selection).
4. **Given** the user passes `--name foo`, **When** `mp login` completes, **Then** the configured account name is exactly `foo`, overriding any org-derived default.

---

### User Story 2 - Region auto-detection for service-account and token credentials (Priority: P2)

A user with a Mixpanel service account (or a raw OAuth bearer token) supplies the credential and the CLI figures out which data region (us / eu / in) it belongs to without the user having to know or type it.

**Why this priority**: Region is the most surprising thing a user is asked to know today. Most users do not consciously track which cluster their data lives on, and getting it wrong yields an opaque 401. Removing this question is a large quality-of-life improvement for service-account users and is a prerequisite for `mp login` (P1) to work for non-browser auth types.

**Independent Test**: Configure a service account with valid `MP_USERNAME` / `MP_SECRET` for an EU project. Run `mp login --service-account` (or `mp account add --type service_account --username U --secret-stdin`) without supplying `--region`. Confirm the resulting account record has `region = eu` and that `mp project list` succeeds against the EU cluster.

**Acceptance Scenarios**:

1. **Given** a valid service account whose data lives in `eu`, **When** the user authenticates without specifying region, **Then** the system probes the `us`, `eu`, and `in` clusters and persists `region = eu` after the first successful response.
2. **Given** a credential that is invalid in every region, **When** region detection runs, **Then** the user receives a single clear "credential not valid in any region" error rather than three separate 401s.
3. **Given** a user supplies `--region us` explicitly with a credential that actually belongs to `eu`, **When** the OAuth browser flow completes and `/me` is consulted, **Then** the system detects the mismatch and aborts with an actionable error directing the user to re-run with the correct region.
4. **Given** the user is running in a non-interactive environment with only `MP_USERNAME` + `MP_SECRET` env vars set (no `MP_REGION`), **When** the SDK resolves the session, **Then** it raises a clear configuration error stating that `MP_REGION` is required for env-var auth (the resolver does not perform network probes).

---

### User Story 3 - Service-account project discovery without `--project` (Priority: P2)

A user with a service account that can address multiple projects can run `mp project list` (and add the account) without supplying any project ID up front, then pick a project to use with `mp project use ID`.

**Why this priority**: Today, adding a service account requires `--project N`. That value is hard to find — it does not appear in the Mixpanel URL bar — and it forces a decision before the user has a way to enumerate their options. Removing this requirement is independently valuable even before `mp login` lands, and it is a prerequisite for the P1 flow to work for the service-account variant.

**Independent Test**: With a service account that has the `user_details` scope and access to ≥2 projects, run `mp account add my-sa --type service_account --username U --secret-stdin --region us` (no `--project`). Confirm the account is created with no `default_project`. Then run `mp project list` and confirm all accessible projects are returned.

**Acceptance Scenarios**:

1. **Given** a service account with the `user_details` scope and access to ≥1 projects, **When** `mp project list` runs without a configured `default_project`, **Then** all visible projects are returned with their org, name, ID, and region.
2. **Given** a service account that lacks the `user_details` scope, **When** the user attempts project discovery, **Then** the error message names the missing scope and tells the user how to re-mint the SA, or to fall back to `--project ID` explicitly.
3. **Given** a service account is added without a project, **When** the user later runs a query, **Then** the standard "no project configured" error chain fires (handled by the existing resolver), pointing the user to `mp project use ID`.

---

### User Story 4 - Auto-derived account names (Priority: P3)

A user who runs `mp login` (or `mp account add` without a positional name) gets a sensible local account name derived from their organization name, with collisions suffixed automatically.

**Why this priority**: Inventing a local alias is low-stakes but adds one more decision per setup. It is the smallest of the friction points and is dependent on `/me` being consulted anyway, so it falls out cheaply once Stories 2 and 3 land. Naming defaults are independently valuable: even users who keep `mp account add` get a free name.

**Independent Test**: On a fresh config, run `mp login` against an account belonging to "Acme Corp". Confirm the configured account name is `acme-corp`. Run `mp login` again against a *different* account from a separate org also named "Acme Corp" and confirm the second account is named `acme-corp-2`.

**Acceptance Scenarios**:

1. **Given** an org named "Acme Corp", **When** the user runs `mp login` without `--name`, **Then** the default account name is `acme-corp`.
2. **Given** an org named "Café Industries" (with non-ASCII characters), **When** the user runs `mp login` without `--name`, **Then** the default account name is `cafe-industries` (ASCII-folded, lowercased).
3. **Given** an account named `acme-corp` already exists in local config, **When** the user adds another for a different org (also named "Acme Corp"), **Then** the new account is named `acme-corp-2`; subsequent collisions become `-3`, `-4`, …
4. **Given** the user has access to multiple orgs, **When** they run `mp login` in an interactive terminal without `--name`, **Then** they are prompted to pick one (the slug of that org becomes the default name); in a non-interactive environment, the command fails with the org list and instructs the user to pass `--name` or `--org`.
5. **Given** the user passes `--name foo`, **When** `mp login` runs, **Then** the explicit name wins regardless of org count or slug derivation.

---

### Edge Cases

- **No accessible projects**: `mp login` succeeds with an account that has no `default_project`. The first query then surfaces the existing "no project configured" error chain; this is not a `mp login` error.
- **Multi-region user**: a single credential is bound to one cluster. A user whose Mixpanel projects span multiple regions needs one account record per region. `mp login` makes one account per invocation; switching regions requires a second `mp login --region X` (or `mp account remove` + re-login).
- **Org with empty name**: name defaults to `org-{org_id}` with the same collision suffix logic.
- **`MP_PROJECT_ID` set in environment but not visible to the authenticated account**: the env value is treated as a *soft* default. If it does not appear in `/me`, the login flow falls through to project picking with a one-line warning to stderr (rather than failing). This is a deliberate concession to dotenv files inherited from a sibling repo or CI matrix.
- **Re-login with `--region` different from the existing account's region**: refused with a clear error. Region change requires removing the account and re-running `mp login`, or `mp account update NAME --region X` for power users.
- **Re-login with `--project` or `MP_PROJECT_ID`**: ignored on re-login (project changes go through `mp project use`); a one-line note is written to stderr so the user is not surprised.
- **`mp account add` left as the power-user path**: explicit, scriptable, all-flags-required. `mp login` is the conversational path. Both succeed with the same end state.
- **Existing config files**: continue to work unchanged. `region` is still required on disk; what changes is that we stop *prompting* for it interactively.

## Requirements *(mandatory)*

### Functional Requirements

#### `mp login` command surface

- **FR-001**: The system MUST provide an `mp login` command that, in its zero-argument form, walks the user through credential collection, region resolution, project selection, and account naming, then writes a fully-functional account record and sets it active.
- **FR-002**: `mp login` MUST accept the following options: `--region {us|eu|in}`, `--service-account`, `--name NAME`, `--project ID`, `--no-browser`, `--token-env NAME`, `--secret-stdin`. Defaults: region defaults to `us` for browser auth (the only flow that must commit to a region *before* `/me` is reachable); other auth types probe.
- **FR-003**: `mp login` MUST detect the credential type from flags and environment using the priority: `--service-account` flag → `--token-env NAME` flag → `MP_USERNAME` + `MP_SECRET` env both set → `MP_OAUTH_TOKEN` env set → default `oauth_browser`.
- **FR-004**: `mp login` MUST persist the resulting account using the existing add-and-activate semantics so that the account immediately becomes the session's active account.
- **FR-005**: `mp login` MUST print, on success, a single human-readable summary line that names the authenticated user (email), the chosen local account name, and the chosen project name.

#### Region resolution

- **FR-006**: For `oauth_browser` auth, the system MUST commit to the `--region` value (default `us`) before launching the browser, then consult `/me` after the callback to verify the chosen project's region matches; on mismatch the system MUST abort with an actionable error and MUST NOT silently overwrite the user's chosen region.
- **FR-007**: For `service_account` and `oauth_token` auth, the system MUST probe the `us`, `eu`, and `in` clusters in that order against `/me` until one returns success, persisting the resolved region on the account record. The first success wins; if none succeed the user MUST receive a single consolidated "credential not valid in any region" error.
- **FR-008**: For env-var-only auth (`MP_USERNAME` + `MP_SECRET` or `MP_OAUTH_TOKEN`), the system MUST require `MP_REGION` and MUST NOT perform network probes from the resolver. This preserves the pure-functional resolver contract and avoids burning round-trips on every cold session in CI.
- **FR-009**: `region` MUST remain a required field on every persisted account record (it gates base-URL lookup on every request). Existing config files with `region` already populated MUST continue to load and work unchanged.

#### Project selection

- **FR-010**: After authentication, the system MUST select the project to associate with the new account using this priority (first match wins): (1) `--project ID` if supplied — must exist in `/me`, otherwise error with the accessible-project list; (2) `MP_PROJECT_ID` env var if set — must exist in `/me`, otherwise warn to stderr and fall through; (3) auto-pick the only project if exactly one is accessible; (4) prompt interactively if stdin is a TTY; (5) fail with the project list and instructions to pass `--project ID` if non-interactive.
- **FR-011**: The interactive project prompt MUST render a numbered list sorted alphabetically by project name, formatted as `<org_name> · <project_name>` when more than one org is present (otherwise just `<project_name>`), with project ID and region right-padded into aligned columns. The default selection MUST be `[1]` (Enter accepts). Invalid input MUST re-prompt up to three times before aborting with an error.

#### Service-account project discovery

- **FR-012**: `mp account add` MUST treat `--project` as optional for service-account credentials (it is already optional for `oauth_browser`). Adding a service account without a project MUST succeed and produce an account with no `default_project`.
- **FR-013**: `mp project list` MUST work against an account that has no `default_project`, returning all projects visible to the credential via `/me`.
- **FR-014**: When `/me` returns 403 for a service account (typically missing `user_details` scope), the error message MUST name the missing scope explicitly and MUST tell the user how to re-mint the SA or fall back to `--project ID`.

#### Account naming

- **FR-015**: When the user does not supply `--name` (or a positional name to `mp account add`), the system MUST derive a default account name from the first org returned by `/me`, normalized via the rules: NFKD-normalize, ASCII-fold (drops accents), lowercase, replace runs of non-`[a-z0-9]` with a single `-`, strip leading/trailing `-`, truncate to 32 characters, strip any trailing `-` left by truncation. The result MUST conform to the existing `^[a-zA-Z0-9_-]+$` constraint.
- **FR-016**: When the derived slug collides with an existing local account name, the system MUST suffix `-2`, `-3`, … until a unique name is found.
- **FR-017**: When the user has access to more than one org and does not pass `--name`, the system MUST prompt interactively in a TTY to pick one, or MUST fail in non-interactive mode with the org list and instructions to pass `--name` or `--org`.
- **FR-018**: When the org name normalizes to an empty string (e.g., punctuation-only), the system MUST fall back to `org-{org_id}` and apply the same collision suffix logic.
- **FR-019**: An explicit `--name` MUST always win over derived naming, regardless of org count or slug derivation.

#### Re-login idempotency

- **FR-020**: When `mp login` is invoked with a `--name` (or default-derived name) that matches an existing account, the system MUST refresh tokens (for `oauth_browser`) or update the credential fields (for `service_account` / `oauth_token`) without rewriting `default_project`.
- **FR-021**: On re-login, `--project` and `MP_PROJECT_ID` MUST be ignored for the purpose of changing `default_project`. A one-line note to stderr MUST be emitted when either is set, telling the user to use `mp project use ID` to change projects.
- **FR-022**: On re-login with a `--region` different from the existing account's region, the system MUST refuse and direct the user to `mp account remove NAME && mp login --region X` (or `mp account update NAME --region X`).

#### Backward compatibility

- **FR-023**: `mp account add NAME --type X --region Y --project Z` MUST keep working identically to its current behavior — all flags accepted, all behavior unchanged.
- **FR-024**: New optional behavior MUST be opt-in: omit `--region` to trigger the probe (where applicable); omit positional `NAME` to derive from org; omit `--project` to defer project selection.
- **FR-025**: Existing `~/.mp/config.toml` files MUST continue to load and round-trip unchanged. The `region` field stays serialized.

### Key Entities

- **Account**: A persisted credential record bound to one Mixpanel cluster (region). Three subtypes: `service_account`, `oauth_browser`, `oauth_token`. Carries a unique local name, a region, and an optional `default_project`.
- **`/me` response**: The authoritative source of region (via the per-project `domain` field), accessible projects, organizations, workspaces, and authenticated-user identity. Available to all three credential types under the `user_details` scope.
- **Org → project → workspace hierarchy**: A user belongs to one or more orgs; each org owns one or more projects; each project owns one or more workspaces. Account naming defaults derive from org name; project selection happens at the project level.
- **Local account name**: A `^[a-zA-Z0-9_-]+$` slug under 64 characters used as the key in `~/.mp/config.toml` and as the directory name under `~/.mp/accounts/`. Default derivation is bounded to 32 characters of slug to leave room for collision suffixes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with no prior configuration can go from "package installed" to "first successful query result" by typing exactly two commands: `mp login` and one query (e.g., `mp query segmentation -e Login --from 2025-01-01`). They MUST NOT be required to type a region, project ID, or local account alias on the common path.
- **SC-002**: For users with exactly one accessible project, the entire `mp login` browser flow (excluding the time the user spends in the browser tab) completes in under 3 seconds of CLI work after the OAuth callback fires.
- **SC-003**: For service-account users whose data lives in `eu` or `in`, the region auto-detection costs at most two extra round-trips on first login (US-first sequential probe). After the first login the resolved region is persisted; subsequent invocations cost zero extra round-trips.
- **SC-004**: 100% of existing `~/.mp/config.toml` files in production keep working without migration after the feature ships. No breaking changes to the on-disk format.
- **SC-005**: 100% of users who today run `mp account add NAME --type X --region Y --project Z` can keep using that exact command unchanged. The new defaults are purely additive.
- **SC-006**: For multi-org users in an interactive terminal, the org/project picker resolves a selection within at most three keystrokes (number + Enter) and never silently picks an org or project the user did not see.
- **SC-007**: Re-running `mp login` against an existing account is idempotent for project state: the persisted `default_project` after re-login equals the value before re-login in every case where the user did not explicitly issue `mp project use`.

## Assumptions

- Users running `mp login` typically have a working browser and a default browser application registered with the OS. The `--no-browser` fallback covers headless or remote-shell environments.
- Service-account users supplying credentials to `mp login` are willing to accept up to two extra round-trips on first login in exchange for not typing a region. The probe is sequential (US-first) rather than parallel to keep the common-case load on Mixpanel servers low — most users are on `us`.
- The `user_details` scope on `/me` is the canonical source of region and project membership for all three credential types. This is verified against the existing webapp `/me` decorator chain.
- Org names are short enough in practice to slugify into useful local account names. The 32-character truncation ceiling leaves room for `-NN` collision suffixes without breaching the underlying 64-character `^[a-zA-Z0-9_-]+$` constraint.
- Existing `mp account add` callers (scripts, CI configs, docs) treat `--region` and `--project` as required today. Making them optional is purely additive and does not break any caller that continues to pass them.
- `MP_PROJECT_ID` is commonly inherited from a different shell context (CI matrix, dotenv file from a sibling repo). Treating a stale `MP_PROJECT_ID` as a soft default rather than a hard error avoids hostile failure modes.
- Multi-region usage by a single Mixpanel user is rare enough that requiring one local account per region (rather than one credential that spans regions) is acceptable. The data plane itself enforces this; the spec only surfaces the constraint cleanly.
- The Cowork bridge (`MP_AUTH_FILE` / `~/.claude/mixpanel/auth.json`) and the env-var resolver paths remain untouched by this work. Frictionless login improves the *interactive add-time* path; the resolver chain is unchanged.

## Dependencies

- The `/me` endpoint must remain accessible to all three credential types under the `user_details` scope.
- The PKCE OAuth browser flow already requests scopes sufficient for `/me`. No new OAuth scope work is required.
- The existing `Workspace` resolver remains pure-functional. All discovery work moves to *add-time* (inside `mp login` / `mp account add`), not *resolve-time*.
- The existing `Account` discriminated union, `MeService`, and `MeResponse` types accommodate the new fields without schema changes — the per-project `domain` field already carries the region marker.
- The existing `mp project list` and `mp account add` code paths are account-type-agnostic where the work intersects; making `--project` optional for service accounts surfaces existing behavior rather than building new paths.
