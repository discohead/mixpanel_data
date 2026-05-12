# Research: Auth, Project & Workspace Management Redesign

**Phase 0 Output** | **Date**: 2026-04-07

## Research Summary

All technical unknowns have been resolved through deep research of three codebases:
1. `mixpanel_data` (Python) — current implementation
2. `analytics/` (Django) — canonical Mixpanel API reference
3. `mixpanel-desktop` (Rust) — production /me caching reference

No NEEDS CLARIFICATION markers remain from the spec.

---

## R1: /me API Compatibility with Service Accounts

**Decision**: Service accounts CAN call the /me API.

**Rationale**: The Django source code (`webapp/app_api/me/views.py:247`) uses `@auth_required(["user_details"])` which, per `webapp/app_api/decorators.py:107-182`, accepts Session, Bearer, AND Basic auth. Service accounts authenticate via Basic Auth and are backed by a `User` object in Django (`user/models.py:276-359`), meaning they have organizations, grants, and project access — all of which `/me` returns.

**Alternatives considered**:
- Assume SA can't call /me, require explicit project_id → Rejected because Django source confirms support, and testing with real SA credentials can verify at runtime.
- Use a different endpoint for SA discovery → Rejected because no other endpoint returns the same comprehensive data.

**Risk mitigation**: If a specific SA receives 403 on /me (e.g., missing `user_details` scope), the system falls back to requiring explicit `--project` specification with a clear error message.

---

## R2: /me Response Structure and Stability

**Decision**: Use forward-compatible Pydantic models with `extra="allow"`.

**Rationale**: The Rust crate uses `#[serde(flatten)] pub extra: HashMap<String, Value>` on all /me types (`types/me.rs:17-56`), proving this pattern works in production. The Django `/me` response includes many fields beyond the core set (feature flags, demo status, custom roles, etc.) that may change. Forward-compatible models ensure unknown fields don't break deserialization.

**Alternatives considered**:
- Strict models rejecting unknown fields → Rejected because API changes would break clients.
- Raw dict without models → Rejected because type safety is a project requirement (mypy --strict).

---

## R3: Cache TTL Strategy

**Decision**: 24-hour default TTL with on-demand refresh.

**Rationale**: The Rust crate uses NO TTL (cache until logout), which is simpler but can serve stale data indefinitely. A 24-hour TTL provides a reasonable balance:
- Organization/project/workspace membership changes are rare (days/weeks between changes)
- The /me endpoint is slow (2-5 seconds, confirmed by `me/utils.py:109-186` making 10+ DB queries)
- Users can force-refresh via `mp projects refresh` for immediate updates
- Cache invalidation on auth events (login/logout) handles the most common freshness scenarios

**Alternatives considered**:
- No TTL (like Rust crate) → Rejected because Python users may have longer-running processes where membership changes matter.
- Short TTL (1 hour) → Rejected because the /me endpoint's 2-5 second latency makes frequent refreshes disruptive.
- TTL per field → Rejected as unnecessarily complex; the entire response changes together.

---

## R4: Config Schema v2 Design

**Decision**: Separate `[credentials]` and `[projects]` sections with `[active]` context.

**Rationale**: The core problem is that v1 bundles auth + project into a single `[accounts.X]` entry, causing N duplicate entries for N projects sharing one service account. The v2 schema normalizes this: one credential entry per unique (username, secret, region) tuple, with project aliases referencing credentials by name.

**Alternatives considered**:
- Keep v1 format, add `project_ids = [...]` array per account → Rejected because it doesn't solve the active context persistence problem and makes "which project am I using?" ambiguous.
- JSON config instead of TOML → Rejected because TOML is already established and works well for this use case.
- Separate files per credential → Rejected as unnecessarily fragmented; a single config file is simpler.

---

## R5: Backward Compatibility Strategy

**Decision**: Dual-version support with opt-in migration.

**Rationale**: Users should never be forced to migrate. The system detects config version by the presence of `config_version = 2` key. All existing methods (`resolve_credentials()`, `Workspace(account="name")`, env var override) continue working with both v1 and v2 configs. New methods (`resolve_session()`, `Workspace(credential="name")`) work with both versions too — v1 configs are treated as if each account is both a credential and a project alias.

**Alternatives considered**:
- Auto-migrate on first access → Rejected because silent config changes could surprise users and break scripts.
- Deprecate v1 immediately → Rejected because existing users shouldn't be forced to change working setups.
- Compatibility shim that wraps v1 as v2 in memory → This IS part of the chosen approach — `resolve_session()` handles v1 configs by treating accounts as combined credential+project entries.

---

## R6: Atomic Config Writes

**Decision**: Write to temp file + `os.replace()` for atomicity.

**Rationale**: Multiple terminal sessions writing to the same config file could cause corruption. The `os.replace()` syscall is atomic on all supported platforms (POSIX and Windows). This is a small change to `ConfigManager._write_config()`.

**Alternatives considered**:
- File locking (fcntl/msvcrt) → Rejected as platform-specific and complex; atomic rename is simpler and sufficient.
- Advisory lock file → Rejected as unnecessary for single-user config management.

---

## R7: /me Cache Storage Location

**Decision**: Store at `~/.mp/oauth/me_{region}.json` alongside OAuth tokens.

**Rationale**: The Rust crate already uses this location and pattern (`auth/storage.rs:66-69`). Reusing the same directory:
- Maintains consistency between Python and Rust implementations
- Inherits the existing 0o700 directory permissions
- Cache files get 0o600 permissions (same as token files)
- Logout already clears this directory, providing natural cache invalidation

**Alternatives considered**:
- Separate cache directory (`~/.mp/cache/`) → Rejected because it fragments storage and requires separate permission management.
- XDG cache directory → Rejected because the project already uses `~/.mp/` as its home.

---

## R8: OAuth Token project_id Handling

**Decision**: Ignore OAuth token's `project_id` field; use `active.project_id` from config instead.

**Rationale**: The current system stores an optional `project_id` in the OAuth token (`auth/token.py:60`), which can be `None` and causes a multi-level fallback chain that's hard to predict. In the new design, project selection is fully decoupled from authentication. The token's `project_id` becomes purely informational (for display/debugging); the actual project used comes from the `[active]` config section.

**Alternatives considered**:
- Keep using token's project_id as primary → Rejected because this IS the current bug — it causes silent project switching when defaults change.
- Remove project_id from token model entirely → Rejected because it would break existing stored tokens; instead, it's simply deprioritized.
