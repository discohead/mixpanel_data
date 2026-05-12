# Phase 0 Research: Authentication Architecture Redesign

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Source design**: [`context/auth-architecture-redesign.md`](../../context/auth-architecture-redesign.md)

This document resolves the Phase 0 research questions surfaced by `plan.md`. The spec itself has zero `[NEEDS CLARIFICATION]` markers because the source design resolves all 8 prior open questions in §18 (Decisions). The remaining research surface is implementation-shape:

1. **R1** — How do we safely move OAuth tokens and client info from `~/.mp/oauth/tokens_{region}.json` to `~/.mp/accounts/{name}/tokens.json` during `mp config convert`?
2. **R2** — What is the minimal Hypothesis test surface for resolver determinism + axis independence?
3. **R3** — What corpus of legacy fixture configs adequately covers v1 + v2 conversion paths?
4. **R4** — What is the stable JSON contract for `auth_manager.py session` that the plugin's slash command can rely on across versions?
5. **R5** — How do we preserve the `httpx.Client` instance across `Workspace.use(account=...)` switches without leaking auth headers from the previous account?
6. **R6** — What testing strategy verifies the lazy workspace auto-resolution (FR-025) without flooding CI with real-API calls?

---

## R1 — OAuth token migration during `mp config convert`

**Decision**: For each legacy `~/.mp/oauth/tokens_{region}.json`, identify the destination account by walking the source config in this order:

1. If the source config has a v2 `[active].credential = "X"` whose region matches the token file's region, move tokens to `~/.mp/accounts/X/tokens.json`.
2. Else if the source config has any v2 `[credentials.X]` with `type = "oauth"` and matching region, prefer the account with the same region as the token file; if multiple, pick the one referenced by the most `[projects.X]` aliases (heuristic for the user's primary OAuth account).
3. Else if the source config has only v1 accounts (no v2 OAuth credentials), the conversion creates a synthetic account named `oauth-{region}` with `type = "oauth_browser"` and adopts the token file.
4. Companion `client_{region}.json` and `me_{region}.json` files move alongside `tokens_{region}.json` to the same destination directory; mismatched standalone files (no token sibling) are left in place and reported in the conversion summary.

**Rationale**: This handles the three realistic alpha-tester states (v2-active OAuth, v2-multi OAuth, v1-only with stray OAuth tokens from a half-completed login flow) without requiring the user to disambiguate. The synthetic name convention (`oauth-{region}`) is unambiguous and discoverable.

**Alternatives considered**:
- **Prompt the user during conversion**: Rejected — violates Principle II (Agent-Native Design); breaks scriptability.
- **Refuse conversion when ambiguous**: Rejected — strands users with valid tokens that just need a home; the heuristic above always produces *a* defensible mapping.
- **Delete legacy token files instead of moving them**: Rejected — would force OAuth users to re-run `mp account login NAME` post-conversion. Moving preserves the user's authenticated state.
- **Create per-region directories under `accounts/`**: Rejected — design decision §18 #7 keeps region per-account, and per-region directories would re-introduce scoping ambiguity.

**Edge case handling**:
- If the destination directory already exists with a `tokens.json` (unlikely on a v3-greenfield conversion path), abort the conversion with a clear error and instruct the user to remove `~/.mp/accounts/{name}/tokens.json` first.
- If the legacy `tokens_{region}.json` is malformed, the conversion still succeeds (account is created), but the broken file is preserved at `~/.mp/oauth/tokens_{region}.json.broken` and the conversion summary names it; the user runs `mp account login NAME` to restore.
- The legacy `~/.mp/oauth/` directory is left intact post-conversion (in case the user wants to roll back); the conversion summary mentions it can be safely deleted manually.

---

## R2 — Hypothesis test surface for resolver determinism + axis independence

**Decision**: Three Hypothesis property classes:

### Property 2a: Determinism

```python
@given(
    env_state=env_state_strategy(),       # arbitrary subset of MP_USERNAME/MP_SECRET/MP_REGION/MP_OAUTH_TOKEN/MP_PROJECT_ID/MP_WORKSPACE_ID/MP_TARGET/MP_ACCOUNT/MP_AUTH_FILE
    config_state=config_state_strategy(), # arbitrary v3 ConfigManager snapshot (accounts/targets/active)
    explicit_args=explicit_args_strategy(),
)
def test_resolver_determinism(env_state, config_state, explicit_args):
    """resolve_session() with identical inputs returns identical Session instances."""
    with patched_env(env_state), patched_config(config_state):
        if not _inputs_should_succeed(env_state, config_state, explicit_args):
            assume(False)  # discard cases that would raise
        s1 = resolve_session(**explicit_args)
        s2 = resolve_session(**explicit_args)
        assert s1 == s2
```

### Property 2b: Axis independence

```python
@given(
    base_inputs=valid_inputs_strategy(),
    perturbed_axis=axis_strategy(),       # one of "account", "project", "workspace"
    new_value=axis_value_strategy(),
)
def test_axis_independence(base_inputs, perturbed_axis, new_value):
    """Changing one axis input never changes the resolved value of the other axes."""
    s_base = resolve_session(**base_inputs.kwargs)
    perturbed_kwargs = dict(base_inputs.kwargs)
    perturbed_kwargs[perturbed_axis] = new_value
    s_perturbed = resolve_session(**perturbed_kwargs)
    other_axes = {"account", "project", "workspace"} - {perturbed_axis}
    for axis in other_axes:
        assert getattr(s_base, axis) == getattr(s_perturbed, axis), (
            f"Perturbing {perturbed_axis} unexpectedly changed {axis}"
        )
```

### Property 2c: Env-wins invariant

```python
@given(
    env_value=axis_value_strategy(),
    config_value=axis_value_strategy(),
    axis=axis_strategy(),
)
def test_env_wins(env_value, config_value, axis):
    """For every axis, env value wins over config value when both are set."""
    assume(env_value != config_value)
    with patched_env({_env_var_for(axis): env_value}), patched_config({axis: config_value}):
        session = resolve_session()
        assert getattr(session, _attr_for(axis)) == _expected(env_value, axis)
```

**Rationale**: These three properties together verify the two key invariants from FR-016 (axis independence) and FR-021 (determinism) plus the FR-017/FR-019 priority guarantee. With the dev profile (10 examples) they run in <1 s; with the CI profile (200 examples) they run in <10 s and exhaust most reasonable input combinations.

**Alternatives considered**:
- **Single mega-property**: Rejected — failures would be hard to diagnose; better to have three orthogonal properties whose failures point at one specific invariant.
- **Stateful Hypothesis (RuleBasedStateMachine)**: Rejected — adds machinery without exercising the resolver's pure-functional contract; the resolver does not have meaningful state transitions across calls.
- **Cover bridge file as a fourth axis source**: Defer to integration tests — the bridge is a synthetic config source consumed by the same axis-priority code, so the existing properties suffice for the resolver itself; bridge-specific behavior (file format, header attachment) is integration-tested in `test_bridge_v2.py`.

**Strategies needed**:
- `env_state_strategy()` — `dictionaries(sampled_from(env_var_names), text(min_size=1, max_size=64))` plus a `from_regex(...)` for region values
- `config_state_strategy()` — builds `ConfigManager` snapshots with N accounts (0–5), M targets (0–3), arbitrary `[active]`
- `axis_value_strategy()` — distinguishes account names (text), project IDs (digit-only strings), workspace IDs (positive ints)
- `valid_inputs_strategy()` — composite strategy that filters to inputs guaranteed to resolve successfully

---

## R3 — Conversion fixture corpus

**Decision**: Six fixture configs covering the realistic alpha-tester surface, paired with assertion fixtures that capture the expected post-conversion state:

| Fixture | Source schema | What it tests |
|---|---|---|
| `v1_simple.toml` | v1, one `[accounts.X]` with project_id, no `default` | Default account is auto-promoted; project becomes a target; active points at account |
| `v1_multi.toml` | v1, 7 accounts with identical creds and 7 different project_ids, `default = "demo-sa"` | Account dedupe (7 source accounts → 1 account + 7 targets); active points at "demo-sa" account; `[active].project` matches the demo-sa project |
| `v1_with_oauth_orphan.toml` | v1 + stray `~/.mp/oauth/tokens_us.json` from a half-completed login | Synthetic `oauth-us` account created; tokens move to `~/.mp/accounts/oauth-us/tokens.json` |
| `v2_simple.toml` | v2, one `[credentials.X]` SA, one `[projects.X]`, `[active]` complete | `[credentials]` → `[accounts]` rename only; alias → target; active.credential → active.account |
| `v2_multi.toml` | v2, two `[credentials]` (one SA + one OAuth), three `[projects.X]` aliases, `[active].credential` set | Both credential types preserved; OAuth tokens at `~/.mp/oauth/tokens_us.json` move to `~/.mp/accounts/{oauth-account-name}/tokens.json` |
| `v2_with_custom_header.toml` | v2 with `[settings] custom_header` | Header survives unchanged in `[settings]` |

**Rationale**: This corpus covers (a) the simplest possible v1, (b) the high-value v1 dedup case from spec §1.1, (c) the v1+stray-OAuth ambiguity case from R1, (d) the simplest v2, (e) the multi-credential v2 with OAuth migration, and (f) the custom-header preservation case. It does NOT include malformed configs (those are handled by the load-time validator, not the converter) or v3 configs (idempotency is tested separately with the v3 fixtures already in the corpus).

**Alternatives considered**:
- **Snapshot every alpha-tester's actual config**: Rejected — privacy, auditing burden, and most tester configs are slight variations of the cases above. We will additionally run `mp config convert --dry-run` against each tester's config during Phase 8 release prep to catch surprises, but the test corpus is curated.
- **Generate fixtures with Hypothesis**: Rejected for conversion (vs. resolver) — conversion correctness depends on specific edge cases (orphaned tokens, dedup heuristics) that are easier to encode as named fixtures than as property generators. The PBT surface stays focused on the resolver and Account union round-trip.

**Test layout**:
```
tests/fixtures/configs/v1_simple.toml         (and v1_simple.expected.toml)
tests/fixtures/configs/v1_multi.toml          (and v1_multi.expected.toml)
tests/fixtures/configs/v1_with_oauth_orphan.toml + tests/fixtures/oauth/tokens_us.json
tests/fixtures/configs/v2_simple.toml         (and v2_simple.expected.toml)
tests/fixtures/configs/v2_multi.toml          (and v2_multi.expected.toml)
tests/fixtures/configs/v2_with_custom_header.toml
tests/integration/test_config_conversion.py   — parametrized over fixture pairs
```

Each fixture pair has an `.expected.toml` golden file. The integration test loads the source, runs `mp config convert` (programmatically), serializes the result, and diffs against the expected file. Diffs surface as helpful failure messages.

---

## R4 — Stable JSON contract for `auth_manager.py session`

**Decision**: Three discriminated states with a fixed top-level `state` field:

```json
{ "state": "ok",
  "account":   { "name": "personal", "type": "oauth_browser", "region": "us" },
  "project":   { "id": "3713224", "name": "AI Demo", "organization_id": 12 },
  "workspace": { "id": 3448413, "name": "Default" },
  "user":      { "email": "jared@example.com", "id": 42 } }

{ "state": "needs_account",
  "next": [
    { "command": "mp account add personal --type oauth_browser --region us", "label": "OAuth (recommended)" },
    { "command": "mp account add team --type service_account --username '...'", "label": "Service account" },
    { "command": "export MP_OAUTH_TOKEN=... MP_REGION=us MP_PROJECT_ID=...",     "label": "Static bearer (CI)" }
  ] }

{ "state": "needs_project",
  "account": { "name": "personal", "type": "oauth_browser", "region": "us" },
  "next": [
    { "command": "mp project list",            "label": "List accessible projects" },
    { "command": "mp project use <id>",        "label": "Select a project" }
  ] }
```

**Rationale**: Discriminated by `state`, with three closed values. The `next` array is always a list of `{command, label}` objects so the slash command can render a natural-language summary without parsing free-form prose. The `account`/`project`/`workspace`/`user` objects are subsets of the public Pydantic model dumps (Pydantic's `.model_dump(mode="json")` with stable field order). All three response shapes are JSON Schema-validatable.

**Alternatives considered**:
- **One flat shape with `null` fields**: Rejected — agents would need to inspect each field for `null` to decide which onboarding step to suggest; the discriminated `state` is self-documenting.
- **Embed CLI commands as templated strings with `{name}` placeholders**: Rejected — leaves rendering to the agent and risks formatting drift. The current shape pre-renders example commands.
- **Include `bridge` in the top-level shape always**: Defer to `auth_manager.py bridge status` subcommand; keeping `session` focused on the (account, project, workspace) triple matches FR-046.

**Versioning**: A `schema_version: 1` field is added so future plugin versions can introduce new states. The plugin's slash command can switch on `schema_version` if/when it changes.

---

## R5 — `httpx.Client` preservation across `Workspace.use(account=...)` switches

**Decision**: The `MixpanelAPIClient` holds the `httpx.Client` as an instance attribute; `use(account=...)` rebuilds the per-request auth header (via `Account.auth_header(token_resolver)`) and stores it as an instance attribute (`self._auth_header`). Every outbound request reads `self._auth_header` at call time (not at client construction) and attaches it to the request via the existing `event_hooks`/per-request header injection path. The HTTP transport, connection pool, and httpx client config are never touched by `use()`.

When `use(account=...)` runs, the client also clears:
- The cached resolved workspace (per-session lifetime cache from FR-025) — because `(account, project)` may have a different default workspace
- The cached `/me` reference (the cache file itself stays on disk, scoped to the new account) — because `ws.account` returns a different identity now

When `use(project=...)` runs, the client clears:
- The cached resolved workspace (project changed, default workspace likely differs)
- Discovery caches (events, properties — schema differs per project)

When `use(workspace=...)` runs, the client clears:
- Nothing — workspace ID is just a request param; no state invalidation needed

**Rationale**: Reading the auth header at request time (rather than baking it into the client) is the standard httpx pattern for rotating auth and matches the `httpx.Auth` interface. Preserving the connection pool is critical for cross-account iteration performance — re-creating an `httpx.Client` would tear down all connections to the same Mixpanel host (`mixpanel.com` for both SA and OAuth). The cache invalidation is conservative: per-axis switches only invalidate caches that the switched axis logically depends on.

**Alternatives considered**:
- **Use httpx's `Auth` mechanism directly**: Rejected — `httpx.Auth` is per-request, but our auth construction needs `TokenResolver` (which does disk I/O for OAuth refresh). Cleaner to compute the auth header at `use()` time and store it.
- **Separate `MixpanelAPIClient` instance per account**: Rejected — defeats the point of preserving the connection pool; cross-account iteration becomes expensive.
- **Implement a custom transport wrapper**: Over-engineered for the redesign; the simple `_auth_header` attribute approach is testable and predictable.

**Failure mode**: If `use(account=...)` is called with an `oauth_browser` account whose tokens are expired and unrefreshable, the auth header construction raises `OAuthError` immediately (before any request); the API client's previous auth header is preserved (atomic swap on success) so the Workspace remains usable on the previous account. The user runs `mp account login NAME` to refresh.

---

## R6 — Testing lazy workspace auto-resolution

**Decision**: Three test layers:

### Layer 1: Unit (mocked)

```python
# tests/unit/test_workspace_use.py — workspace lazy resolve
def test_lazy_workspace_resolves_on_first_workspace_scoped_call(mock_api):
    mock_api.set_workspace_response("3713224", workspaces=[{"id": 9999, "name": "Default", "is_default": True}])
    ws = mp.Workspace(session=Session(account=fake_sa, project=Project(id="3713224"), workspace=None))
    assert ws.workspace is None  # not yet resolved
    ws.alerts()  # workspace-scoped endpoint
    assert ws.workspace == WorkspaceRef(id=9999, name="Default")
    mock_api.assert_workspaces_called_exactly_once_for("3713224")
```

### Layer 2: Integration (contract)

```python
# tests/integration/test_workspace_lazy_resolve.py
@pytest.mark.contract
def test_lazy_resolve_against_recorded_workspaces_response(recorded_responses):
    """Use vcrpy/respx-recorded /api/app/projects/{pid}/workspaces/public response."""
    ws = mp.Workspace(session=Session(account=fake_sa, project=Project(id="3713224"), workspace=None))
    list(ws.alerts())  # triggers resolve
    assert ws.workspace.is_default is True
```

### Layer 3: Live (smoke)

```python
# tests/integration/test_workspace_lazy_resolve.py — live, opt-in
@pytest.mark.live
def test_lazy_resolve_against_live_api():
    ws = mp.Workspace()  # uses configured active account/project
    ws.use(workspace=None)  # explicitly clear
    ws.alerts()
    assert ws.workspace is not None
    assert ws.workspace.id > 0
```

**Rationale**: The unit layer covers the cache/dispatch logic without network. The integration layer locks the contract against the actual Mixpanel response shape (recorded once, replayed in CI). The live layer runs only when `MP_LIVE_TESTS=1` is set (so contributors can verify against their account); it does not run in CI by default.

**Alternatives considered**:
- **Live-only**: Rejected — flaky in CI (network required, rate limits, account-specific data drift).
- **Mock-only**: Rejected — risks divergence from real API shape; the contract layer guards against that.
- **Schema validation only**: Rejected — Pydantic already validates the response model on parse; the test verifies the dispatch+cache logic, which is independent of model shape.

**Failure observability**: When live tests fail, the failure message includes the recorded contract response shape so the contributor can diff against the live response and update both the recording and the model.

---

## Cross-cutting: PR sequencing & feature flags

The 9-phase implementation lands as ~9 PRs in sequence; each PR is independently mergeable but downstream PRs depend on upstream merges. There is **no feature flag** for the redesign — the breaking change is the point. The conversion script (`mp config convert`) lands in Phase 8 along with the version bump and release notes; alpha testers run it once when they upgrade.

The Python public surface for Phases 1–3 is internal-facing (no `import mixpanel_data; mp.accounts.list()` until Phase 3 lands). During Phases 1–2, the existing `Workspace`, `Credentials`, and CLI commands keep working against the old code paths; during Phase 3, the rewire happens atomically (one PR replaces the API client constructor, the Workspace facade, and removes the bridge methods together). Phases 4–6 are CLI/plugin/bridge wrappers over the new Phase 3 surface.

Test isolation: Each PR includes its own tests against the new code, plus deletes the obsolete tests for the code it replaces. CI runs the full test suite on every PR; coverage thresholds (90%) and mutation thresholds (≥85% on the three auth files) are enforced from Phase 1 onward.

## Summary of resolutions

| # | Question | Resolution |
|---|---|---|
| R1 | OAuth token migration during conversion | Walk source config in priority order (active credential → matching v2 OAuth credential → synthetic `oauth-{region}`); move `tokens_/client_/me_` siblings together; preserve original `~/.mp/oauth/` directory |
| R2 | Hypothesis test surface for resolver | Three properties: determinism, axis independence, env-wins invariant. ~10 strategies. Dev profile <1 s; CI profile <10 s. |
| R3 | Legacy fixture corpus | Six curated fixtures (v1 simple/multi/OAuth-orphan + v2 simple/multi/custom-header) with golden `.expected.toml` files. PBT does NOT cover conversion. |
| R4 | Stable JSON contract for `auth_manager.py session` | Discriminated `state ∈ {ok, needs_account, needs_project}`; `next` array of `{command, label}`; `schema_version: 1`. |
| R5 | `httpx.Client` preservation across switches | Read `_auth_header` at request time; rebuild on `use(account=...)`; preserve transport. Atomic swap on auth construction success. Conservative cache invalidation per axis. |
| R6 | Testing lazy workspace auto-resolution | Three layers: unit (mocked), integration (recorded contract response), live (opt-in via `MP_LIVE_TESTS=1`). |
