# Phase 0 Research: Frictionless Auth

**Feature**: 043-frictionless-auth
**Date**: 2026-05-06
**Status**: Complete — no NEEDS CLARIFICATION markers in plan.md remain.

The source design draft (`context/frictionless-auth.md`) already settled most of the open questions through code-archaeology and explicit decisions. This document records the load-bearing decisions, their rationale, and the rejected alternatives so reviewers can audit the choices without re-deriving them.

---

## R-1. Region probe order: sequential US-first

**Decision**: For service-account and OAuth-token credentials, probe `us` → `eu` → `in` against `/api/app/me` until one returns 200. First success wins.

**Rationale**:
- ~85% of Mixpanel customers live on the US cluster (per the source design's claim, supported by Mixpanel's published infrastructure breakdown). Sequential US-first keeps the common-case cost at one round-trip.
- The probe runs once at add-time. The resolved region is cached on the `Account` record, so the cost amortizes to zero for every subsequent invocation.
- Worst case is two extra round-trips (US fails, EU fails, IN succeeds) — still under 1 s in practice.

**Alternatives considered**:
- **Parallel probe across all three regions**: Would resolve in one round-trip wall-clock but tripples server load *for the common case*. The "common case" here is the US user who would otherwise have paid one round-trip. Rejected on net-server-load grounds.
- **Probe only the user-supplied default**: Would defeat the feature (users do not know their region).
- **Cache last-resolved region as a process-wide hint**: Adds state-management for an operation that runs at most once per account-add. Not worth it.

---

## R-2. Browser auth commits region before the redirect

**Decision**: For `oauth_browser` auth, the user-supplied `--region` (default `us`) is committed to *before* the PKCE authorize URL is constructed. After the OAuth callback fires, `/me` is consulted to verify the chosen project's `domain` matches the auth region; on mismatch, the system aborts with an actionable error rather than rewriting the user's choice.

**Rationale**:
- The PKCE `authorize` endpoint is region-scoped — `https://{region}.mixpanel.com/oauth/authorize` for non-US regions. The redirect URL has to be constructed before the browser opens, which means region must be known up-front.
- Once tokens are issued by the EU cluster, they cannot authenticate against the US cluster. Probing after the fact would require throwing away EU-issued tokens and re-auth in US — confusing and slow.
- The mismatch detection (auth region vs. project's `domain`) catches the "user has projects in multiple regions and picked the wrong default" case explicitly.

**Alternatives considered**:
- **Probe before opening the browser**: Browser flow has no credential to probe with yet. Rejected.
- **Open three browser tabs, one per region**: Hostile UX.
- **Default to letting the user-side IDP discovery pick the region**: Mixpanel's auth surface does not expose IDP discovery for region routing.

---

## R-3. Re-login preserves `default_project`

**Decision**: When `mp login` is invoked with a `--name` (or default-derived name) that matches an existing account, tokens are refreshed (for `oauth_browser`) or credential fields are updated (for `service_account` / `oauth_token`), but `default_project` is left alone. `--project` and `MP_PROJECT_ID` are ignored on the re-login path; a one-line stderr note tells the user to use `mp project use ID` to change projects.

**Rationale**:
- The intent of re-login is to refresh a credential that has expired or rotated. Silently rebinding the project would surprise users who run `mp login` in a shell where `MP_PROJECT_ID` is set from a sibling repo's dotenv.
- `mp project use` is the explicit, documented way to change projects. The 042 redesign deliberately separated credential lifecycle from project state for this reason.
- The stderr note keeps the behavior discoverable without forcing a hard failure.

**Alternatives considered**:
- **Fail re-login if `--project` is set with a value different from the existing `default_project`**: Hostile to dotenv users.
- **Always rewrite `default_project` from the new context**: Explicit-over-implicit violation; surprises users.
- **Remove `--project` from `mp login` entirely**: Breaks the symmetry with `mp account add` and prevents the explicit "I am setting up a brand new account targeting project N" use case.

---

## R-4. Placeholder-then-rename during browser PKCE flow

**Decision**: The PKCE flow writes `tokens.json` and `client.json` to a temporary placeholder directory under `~/.mp/accounts/.tmp-{nonce}/` *before* `/me` is consulted. After the `/me` lookup returns and the final account name is computed, the directory is atomically renamed to `~/.mp/accounts/{final_name}/`. If `/me` fails, the placeholder is removed.

**Rationale**:
- The OAuth browser flow needs disk persistence for the tokens before `/me` can be hit (the tokens *are* the credential `/me` will authenticate with).
- Atomic rename (`os.rename` on POSIX) is the canonical "publish-after-build" pattern for filesystem state.
- Failure cleanup keeps `ls ~/.mp/accounts/` from growing orphan dirs across aborted login attempts.

**Alternatives considered**:
- **Hold tokens in memory until naming completes**: A failed rename loses the tokens and forces a full re-auth. Worse UX on partial failure.
- **Require the user to supply `--name` for browser auth**: Defeats the feature's value proposition.
- **Copy-and-delete**: Non-atomic, race-prone (another `mp` invocation could see the half-written state).

---

## R-5. TTY-gated interactive prompts (vs. always-interactive or always-fail)

**Decision**: When `mp login` needs a project / org choice and one is not supplied, behavior is gated on `sys.stdin.isatty()`:
- TTY → render numbered list, prompt for selection (default `[1]`, three retries, then abort).
- Non-TTY → print the same numbered list to stderr and exit with `INVALID_ARGS=3`. The error message instructs the user to pass `--project ID` (or `--name`) explicitly.

**Rationale**:
- Constitution Principle II (Agent-Native) requires that every command has a deterministic non-interactive path. TTY gating provides that without abandoning the conversational happy path.
- The "non-TTY fail-fast" mode prints the same data structurally that the prompt would have shown, so an agent can parse the failure message and re-invoke with the right flag.
- Three retries (rather than infinite loop) caps the worst case for misbehaving terminals.

**Alternatives considered**:
- **Always prompt** (even non-TTY): blocks CI and agent invocations indefinitely on stdin reads.
- **Always fail** (no prompts): forces interactive users to run the command twice and copy-paste an ID. Defeats the feature.
- **Prompt with a 10-second auto-default**: Surprising default-application is worse than an explicit choice.

---

## R-6. `MP_PROJECT_ID` is a soft default

**Decision**: When `MP_PROJECT_ID` is set and the value does not appear in the authenticated account's `/me` projects list, `mp login` prints a one-line warning to stderr (`note: MP_PROJECT_ID=NNNNN not visible to this account; falling through to project picker`) and continues with the standard priority chain (single auto-pick / interactive prompt / non-interactive fail).

**Rationale**:
- Users frequently inherit `MP_PROJECT_ID` from a sibling repo's dotenv, a CI matrix entry, or a previous shell session. A hard failure on a stale env value is hostile.
- Treating it as a soft default keeps the resolver's normal priority order (env > param > target > bridge > config) intact for the *successful* case while gracefully degrading for the stale case.
- `--project ID` (the flag) remains a hard failure if the value is not visible — the user typed it explicitly, so the failure is informative rather than hostile.

**Alternatives considered**:
- **Hard failure on stale `MP_PROJECT_ID`**: hostile to dotenv users.
- **Silently fall through with no warning**: would mask the user's mistake and surprise them when the resulting account binds to a different project than they expected.

---

## R-7. `MP_REGION` stays required for env-var-only auth

**Decision**: For env-var-only auth (`MP_USERNAME` + `MP_SECRET` set, or `MP_OAUTH_TOKEN` set, with no configured `~/.mp/config.toml` account), `MP_REGION` remains required. The resolver does not perform region probes.

**Rationale**:
- The resolver (`_internal/auth/resolver.py`) is contractually pure-functional — no network I/O, no side effects. Probing from inside the resolver would break this contract and force every cold session in CI to pay 1–2 wasted round-trips.
- CI / agent contexts want determinism. A probe can succeed against the wrong region for a credential that has access to multiple clusters (rare but real for cross-region SAs), which would silently bind the agent to the wrong cluster.
- Discovery work belongs at *add-time* (inside `mp login` / `mp account add`), not *resolve-time*. This is a load-bearing invariant from the 042 redesign.

**Alternatives considered**:
- **Probe inside the resolver if `MP_REGION` is missing**: breaks the pure-functional contract.
- **Make `MP_REGION` optional and default to `us` silently**: misroutes EU/IN env-var users.
- **Run a one-shot probe at SDK import time and cache to a file**: introduces import-time I/O — violates Principle V (Explicit Over Implicit) and creates a hidden file the user did not author.

---

## R-8. Slug max length is 32 chars (vs. 64)

**Decision**: `naming.slugify()` truncates to 32 characters, leaving 32 chars of headroom under the existing `_AccountBase.name` 64-char ceiling. Truncated trailing `-` is stripped.

**Rationale**:
- The collision suffix `-NN` (or `-NNN` if a user adds 100+ accounts with the same org slug — pathological but bounded) needs room. 32 chars of headroom covers `-2` through `-99999999999999999999999999999999`, well past any realistic case.
- 32-char slugs are still informative for the org-name use case (most org names slug down to <20 chars).
- Truncation rule is deterministic and unambiguous: take the first 32 chars after slugification, then strip a trailing `-` if present (so `acme-corporation-international-` becomes `acme-corporation-international`, not `acme-corporation-international-`).

**Alternatives considered**:
- **64-char slug, no headroom for collisions**: 100-collision case (or any case where the 64-char org name exists) would breach the underlying constraint.
- **Variable slug length based on collision detection**: complicates the pure function for marginal benefit.

---

## R-9. Reuse the existing PKCE flow as-is

**Decision**: `accounts.login_unified()` for the `oauth_browser` path delegates to the existing `_internal/auth/flow.OAuthFlow.login()` with no modifications. The wrapper layer adds region commitment, `/me` consultation, name derivation, and persistence.

**Rationale**:
- The existing PKCE machinery (`flow.py`, `pkce.py`, `callback_server.py`, `client_registration.py`) has been hardened by the 042 redesign and earlier OAuth work. No reason to fork it.
- The new code surface (region probe, naming, project picker) is purely additive — composable, individually testable, individually mutation-tested.

**Alternatives considered**:
- **Rewrite the PKCE flow to inline `/me` consultation**: tangles concerns, expands the test surface for `flow.py`, breaks the layering.

---

## R-10. Multi-org handling: prompt or fail with org list

**Decision**: When `/me` returns multiple orgs and the user did not pass `--name`, `mp login` prompts in TTY for an org selection (the slug of which becomes the default name). In non-TTY contexts, it fails with the org list and instructs the user to pass `--name` (which fixes the account name explicitly) or `--org` (a future enhancement, deferred).

**Rationale**:
- Multi-org is rare but real (consultants, agency users, employees with personal-org access).
- Picking the first org silently could bind to the wrong org. Picking by some heuristic (most-recent-active, alphabetical-first) would be wrong sometimes and is harder to explain.
- The user's intent "I want to add an account named X" (`--name X`) implicitly resolves the org question because the user has chosen the local name regardless of which org the credential ultimately points to.

**Alternatives considered**:
- **Auto-pick the first org alphabetically**: Predictable but wrong sometimes; surprising.
- **Add `--org NAME` flag in v1**: Deferred — `--name` covers the explicit case, and `--org` would need separate disambiguation logic. Punt to a follow-up if users ask.

---

## R-11. `MeService` and `MeResponse` accommodate the new fields without schema changes

**Confirmed against current code**:
- `_internal/me.py:65 class MeProjectInfo` already carries the `domain: str | None = None` field (line 102), populated by `webapp/project/utils.py::get_domain_for_cluster_id`.
- `MeService.fetch()` already maps 403 → `ConfigError("lacks /me permission")`, which we extend in Commit 1 to name the missing scope.
- `MeResponse.organizations` already returns the org list as `dict[str, MeOrgInfo]`, where `MeOrgInfo.name` is the slug source.
- `MeResponse.projects` already returns the project list with `MeProjectInfo.domain` and `MeProjectInfo.name`.

**No new Pydantic models are needed.** The two new pure modules consume `MeResponse` and produce `Region` / `str` outputs.

---

## Open follow-ups (deferred, not blocking)

- **`--org NAME` flag** for explicit org disambiguation in multi-org cases. Tracked in R-10. Add when a user reports the case.
- **Parallel region probe with a `--probe-parallel` opt-in flag** for users on slow networks who want wall-clock latency over server load. Tracked in R-1. Add when latency complaints appear.
- **Auto-detect `--no-browser` mode from `$DISPLAY` / `$WAYLAND_DISPLAY` / `$SSH_CONNECTION`**: Out of scope for v1; `--no-browser` is currently an explicit flag.
