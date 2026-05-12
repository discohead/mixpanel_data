# PR #126 Review Re-Assessment & 1.0-Readiness Plan

**Branch:** `042-auth-architecture-redesign` · **PR:** [#126](https://github.com/jaredmcfarland/mixpanel_data/pull/126) · **HEAD:** `6a01afd` · **Coverage:** ~91% (5,956 tests + 18 / 18 live) · **mypy --strict + ruff:** clean · **Build:** `mixpanel_data-0.4.0.tar.gz` ✓

## Execution Status (as of 2026-04-22)

**🎉 042 spec is closed — release-ready at 0.4.0.** All eight clusters landed across 13 commits. PR #126 review (35/35), A2 plugin rewrite, C2 bridge writer, C1 cross-cutting iteration coverage, **D release polish**. B1 cluster (Fix 9 / 10 / 14) — `12471c6`/`024a291`/`18283b4`; A1 — `4d21c3e`; B2 (×4) — `3f74cd7`/`651bf66`/`b1c7a74`/`50ccd9d`; B3 — `f18f1aa`; A2 — `478160f`; C2 — `9147b1d`; C1 — `18233dc`; **D — `6a01afd`** (version bump 0.3.0 → 0.4.0, `RELEASE_NOTES_0.4.0.md`, three CLAUDE.md sweeps, `tests/unit/test_loc_budget.py`).

| Group | Done | Notes |
|-------|------|-------|
| A — atomicity & security | ✅ 8 / 8 | atomic_write_bytes, _mutate ctx mgr, per-request headers, accounts.use clears workspace, immutable Session.headers, strict=True default, MP_OAUTH_STORAGE_DIR routing, account_dir traversal tests |
| B — legacy elimination | ✅ 7 / 7 | Earlier: deleted legacy CLI modules + v1/v2 fixtures + legacy detection. **B1 (`12471c6` / `024a291` / `18283b4`)**: Fix 10 flattened `Workspace.__init__` to v3-only kwargs (matches `contracts/python-api.md` §1) + dropped `_resolved_session` / `_init_v3` / `_has_v3_config` / 5× `hasattr(_v3_session)` guards / legacy `mp` CLI globals (`--credential` / `--workspace-id`); Fix 14 deleted v1 `AuthBridgeFile` + 9 helpers + `ConfigManager._resolve_*_from_bridge` chain; Fix 9 merged `_internal/config_v3.py` → `_internal/config.py` and removed legacy `ConfigManager` (`resolve_credentials`, `resolve_session`, `add_account(project_id=, region=)`, `set_default`, `add_credential`, `add_project_alias`, `migrate_v1_to_v2`) + `AccountInfo` / `CredentialInfo` / `ActiveContext` / `ProjectAlias` / `MigrationResult` dataclasses + `Credentials.from_oauth_token` / `to_resolved_session` factories + `Workspace.test_credentials` static method (FR-038 routes to `mp.accounts.test`). Test sweep: ~85 `_config_manager=`-injecting sites migrated to `session=_TEST_SESSION`; 14 dead-legacy test files deleted with rationale. |
| C — behavior gaps | ✅ 4 / 4 | `mp target` CLI shipped earlier (5 commands + 10 smoke tests). **A1 (`4d21c3e`)**: Fix 16 wired `OnDiskTokenResolver._refresh_and_persist` (OAuthFlow.refresh_tokens + atomic_write_bytes per-account); Fix 17 implemented `accounts.login(name)` and `mp account login NAME` (PKCE + /me probe + default_project backfill); Fix 18 made `MixpanelAPIClient._get_auth_header` re-resolve OAuth bearers per request via the bound `TokenResolver`. |
| D — unused code & cleanup | ✅ 4 / 4 | Deleted DEFAULT_STORAGE_DIR shim, AccountAccessError, `--refresh`/`--bridge` flags; hid stub fns from `accounts.__all__` |
| E — input validation hardening | ✅ 3 / 3 | MP_REGION/MP_WORKSPACE_ID/MP_PROJECT_ID strict, expires_at validation, `--secret-stdin` 64 KiB |
| F — public-API surface design | ✅ 4 / 4 | Account.match() exhaustiveness, AccountTestResult/OAuthLoginResult tightening, promoted resolver helpers, `mixpanel_data.auth_types` public module (`f18f1aa` — single source of truth for the v3 auth surface, drops `_AccountTypeLiteral` / `_RegionLiteral` mirrors in types.py). |
| G — test/doc hygiene | ✅ 5 / 5 | Comment-rot scrub, `current_auth_header` docstring, ConfigManager + Session PBT, atomic-write resilience tests, real-`~/.mp/` write guard fixture |

**No deferred PR #126 fixes remain.** No open spec-level workstreams. Optional follow-ups (deferred from Phase 11 as nice-to-haves, can land post-0.4.0): T120 mutation testing on the auth subsystem, T125 manual quickstart walkthrough, T126 security audit, T126a `pydocstyle` gate.

**Live QA**: `tests/live/test_042_auth_redesign_live.py` (18 scenarios across SA / oauth_browser / oauth_token / cross-mode switching / bridge file / CLI / edge cases) — 18 / 18 pass against the real Mixpanel API at HEAD `6a01afd`.

---

## Context

PR #126 (auth architecture redesign) underwent a 6-agent comprehensive review (`/pr-review-toolkit:review-pr ALL ASPECTS ALL AGENTS`). The agents produced ~120 distinct claims spanning correctness, security, atomicity, type design, test coverage, comment accuracy, and over-engineering. The user requested an **impartial re-assessment** of every finding's validity, with a fix plan for the valid ones and reasoning for any rejected.

**Verification methodology:** every major claim was fact-checked against the actual code via 3 parallel Explore agents reading the cited file:line spans. The implementation approach for the highest-risk fixes was further critiqued by a Plan agent, which flagged several flaws in initial sketches (`os.umask` thread-safety, transaction-helper API sprawl, strict-default behavior change, header-comparison fragility) — those critiques are folded into the recommendations below.

**Operating context (2026-04-22 update):** `mixpanel_data` is **pre-release alpha** with a handful of internal testers. There are **no migration constraints** and **no public-API stability constraints**. This work is explicitly **1.0-readiness** — now is the right time to delete dead paths, break unintentional surface, and make design decisions instead of compatibility decisions. The plan is rewritten under that lens.

**Outcome:** ~80% of original findings verified as real bugs/gaps. Several findings that were previously REJECTED or DEFERRED on backward-compatibility grounds are now PROMOTED. Several "ship paired with" / "deferred to followup" hedges are eliminated — the legacy paths get deleted instead of preserved.

---

## Reframing under "free to break"

The original plan was constrained by:
- "Don't break v1/v2 users" → ship `mp config convert` paired with legacy ConfigError propagation
- "Preserve `Workspace()` lazy-init contract" → defer-and-raise shim instead of `strict=True` default
- "Keep legacy CLI commands working" → add deprecation banners
- "Phase N / FR-NNN references are load-bearing during rollout" → defer scrub
- "Phase 5+ scope" → ship `mp account login` / refresh / per-request bearer / `mp target` CLI as known-broken / deferred

Under the new context, **every one of those constraints disappears**. The revised plan therefore:
- **Deletes** the legacy `_internal/config.py` / dual-init `Workspace` / `_LEGACY_DETECTED_MESSAGE` machinery / `mp config convert` stub / legacy CLI command groups / v1 `load_bridge_file` / v1+v2 test fixtures.
- **Defaults `strict=True`** on `session_to_credentials` and **deletes the `_OAUTH_TOKEN_PENDING` placeholder** (no defer-shim — that was a backward-compat workaround for a constraint we no longer have).
- **Promotes** OAuth refresh wiring (C10), `mp account login` (C11), per-request bearer resolution (C12), and `mp target` CLI (I17) from P2/Phase 5 → P0. The SDK is unusable for its three-account-types contract until these land; 1.0 cannot ship without them.
- **Promotes** the Phase-N / FR-NNN / Research-R5 / "regression caught by QA" docstring rot scrub from REJECTED → P1. With the rollout collapsing into one PR, those references become rot the moment this PR merges; sweep them now.
- **Promotes** intentional public-API surface design (auth types module location, `Workspace` factory split, discriminated-union helpers, `AccountTestResult` tightening) from suggestions → P1.
- **Drops the "scope decision points" section entirely** — the four open questions all resolve to "ship it."

---

## Index of Original Findings (revised dispositions)

| Unified ID | Source review | Original finding (paraphrased) | Revised disposition |
|---|---|---|---|
| **C1** | code-reviewer #1 | `mp config convert` is a stub blocking v1/v2 users | **DELETE** the legacy detection + the stub command (no migration path needed) — P0 |
| **C2** | code-reviewer #2 | `MixpanelAPIClient.use(account=…)` doesn't refresh `httpx.Client` headers | ✓ VALID — P0 (per-request header attachment) |
| **C3** | code-reviewer #3 + silent-failure I2 | Bridge file + inline OAuth-token writers skip `umask(0o077)` | ✓ VALID — P0 (folded into atomic-write helper) |
| **C4** | silent-failure C1 | Filesystem writes are non-atomic; spec mandates `os.replace()` | ✓ VALID — P0 |
| **C5** | silent-failure C2 + code-reviewer #9 | Multi-write sequences in `_persist_active`/`session.use`/`accounts.add` | ✓ VALID — P0 (`_mutate()` context manager) |
| **C6** | code-reviewer #4 | `accounts.use(name)` leaves stale workspace; docstring lies | ✓ VALID — P0 |
| **C7** | silent-failure C3 + simplifier H5 + comment-analyzer Critical 2 | `pending-login` placeholder ships fake bearer | ✓ VALID — P0 (`strict=True` default + delete `_OAUTH_TOKEN_PENDING`; no defer-shim needed) |
| **C8** | test-analyzer Critical 3 | `MP_OAUTH_STORAGE_DIR` ignored by per-account layout | ✓ VALID — P0 |
| **C9** | silent-failure C5 | `_has_v3_config()` swallows ConfigError, hides migration prompt | **MOOT** — `_has_v3_config()` deleted along with legacy path |
| **C10** | code-reviewer #5 | OAuth browser tokens never refresh | ✓ VALID — **PROMOTED to P0** (1.0 needs working OAuth) |
| **C11** | code-reviewer #6 | `mp account login` is a stub | ✓ VALID — **PROMOTED to P0** (1.0 needs oauth_browser usable) |
| **C12** | silent-failure C4 | OAuth bearer cached at construction, never re-resolved | ✓ VALID — **PROMOTED to P0** (depends on C10) |
| **C13** | type-design C2 | `Session.headers` is mutable on frozen model | ✓ VALID — P0 |
| **C14** | test-analyzer Critical 1 | No tests for `account_dir(name)` path-traversal defense | ✓ VALID — P0 |
| **I2/I3/I4** | silent-failure C6/C7 + code-reviewer #8/#10 | Env var validation silently degrades (`MP_REGION`, `MP_WORKSPACE_ID`, `MP_PROJECT_ID`) | ✓ VALID — P1 |
| **I5** | silent-failure I1 | `OnDiskTokenResolver` skips expiry when `expires_at` non-string/None | ✓ VALID — P1 |
| **I7** | silent-failure I-tier + comment-analyzer Critical | `current_auth_header` docstring "cached" lie | ✓ VALID — P1 |
| **I9** | silent-failure I9 | v1 `load_bridge_file` swallows bare Exception | **MOOT** — v1 `load_bridge_file` deleted (only v2 `load_bridge` survives) |
| **I11** | code-reviewer #12 + type-design C1 | `ActiveSession`/`TokenResolver` not exported | ✓ VALID — P1 (folded into intentional public-API design) |
| **I17** | code-reviewer #7 | No `mp target` CLI commands | ✓ VALID — **PROMOTED to P0** (1.0 needs it) |
| **I20** | code-reviewer #13 + silent-failure I10 | `--secret-stdin` 4096-byte truncation | ✓ VALID — P1 |
| **I22** | comment-analyzer Critical 1 | `accounts.use()` docstring lies about `[active].project` | ✓ VALID — P0 (folded into C6) |
| **I27** | code-reviewer #14 | `Workspace` imports private resolver helpers | ✓ VALID — P1 |
| **S1** | code-reviewer #14 + simplifier H3 | Five `_v3_session` `hasattr` guards | **MOOT after legacy deletion** — `Workspace` becomes single-mode; guards disappear |
| **S2** | simplifier H6 | `DEFAULT_*` unused property shims | ✓ VALID — P0 (delete now) |
| **S3** | simplifier H7 | `AccountAccessError` defined but never raised | ✓ VALID — P0 (delete now) |
| **S6** | simplifier S6 | `_SentinelType` over-engineering | ✗ REJECTED — works correctly; loses useful repr |
| **TD-C1** | type-design C1 | "Internal types leaked through `__init__.py`" | **PROMOTED to P1** — intentional public-API surface design (move auth types to `mixpanel_data.types` or new `mixpanel_data.auth_types`; have `_internal/auth/...` import from public) |
| **TD-C3** | type-design C3 | `Workspace` dual-init invariants not type-enforced | **PROMOTED to P0** — full factory split via legacy deletion (no longer "too invasive vs. backward-compat") |
| **TD-C4** | type-design C4 | `OnDiskTokenResolver(TokenResolver)` Protocol inheritance | ✗ REJECTED — works correctly |
| **TD-AccountTestResult** | type-design Important | `AccountTestResult.user: dict[str, Any] \| None`; no `ok ⟺ error` validator | ✓ VALID — P1 |
| **TD-Account.match** | type-design suggestion | Discriminated-union helper to push exhaustiveness into one place | ✓ VALID — P1 |
| **CA-rot** | comment-analyzer (~90 references) | Phase-N / FR-NNN / Research-R5 / "regression caught by QA" task-specific references | **PROMOTED to P1** — sweep now (rollout collapsing into this PR; references become rot on merge) |
| **CLI-dual-stack** | code-reviewer #18 | Legacy `mp auth`/`mp context`/`mp projects`/`mp workspaces` coexist with new commands | **DELETE** the legacy commands entirely — P0 |
| **CLI-ignored-flags** | code-reviewer #18 | `--refresh` on `workspace`/`project`, `--bridge` on `session` accepted but ignored | ✓ VALID — P0 (delete the unwired flags) |

---

## P0 — must land in this PR

### Group A: atomicity & security foundation (unchanged from prior plan)

#### Fix 1: Atomic-write helper → closes C3, C4

- New file: `src/mixpanel_data/_internal/io_utils.py`
- Function: `atomic_write_bytes(path: Path, data: bytes, *, mode: int = 0o600) -> None`
- Implementation:
  - Tmp path: `path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{threading.get_ident()}")` — collision-free under threads/async.
  - `os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)` — sets perms at create time without `os.umask` (which is process-global, not thread-safe).
  - Write via `os.write(fd, data)`, `os.close(fd)`.
  - `os.replace(tmp, path)` for atomic rename.
  - `try/finally` cleanup: `Path(tmp).unlink(missing_ok=True)` on exception.
  - Skip `os.fsync` — atomicity ≠ durability; fsync costs 5–50ms per CLI invocation.
- Migrate call sites:
  - `_internal/config_v3.py:_write_raw` (~227-231)
  - `_internal/auth/storage.py:_write_file` (~282-289)
  - `_internal/auth/bridge.py:write_bridge_file` (~392-407)
  - `workspace.py:_init_v3` inline tokens write (~645-646) — though `_init_v3` itself goes away in Group B
- Tests: `tests/unit/test_io_utils.py` covering success, EXCL collision, exception cleanup, mode preservation.

#### Fix 2: `ConfigManager._mutate()` context manager → closes C5

- File: `src/mixpanel_data/_internal/config_v3.py`
- Add private `_mutate()` context manager (single read at `__enter__`, single write at `__exit__`).
- Refactor existing mutators (`set_active`, `clear_active`, `update_account`, `add_account`, `apply_target`) to use `_mutate()` internally.
- Refactor multi-call sites:
  - `workspace.py:_persist_active` (~867-894): collapses 3-4 calls into one block.
  - `session.py:use` (~62-88): collapses 2 calls.
  - `accounts.py:add` first-account path (~91-104): inline the `is_first` `set_active` into the `_mutate` block.

#### Fix 3: Per-request custom header attachment → closes C2

- File: `src/mixpanel_data/_internal/api_client.py`
- Drop `headers=headers` from `_ensure_client` `httpx.Client(...)` call (~352-356); only `timeout` and `transport` remain.
- In `_execute_with_retry` / per-request paths (~563, ~593), build headers as: `{"Authorization": auth_header, **(self._session.headers if self._session else {})}`.
- Connection pool preserved across `use()`; header staleness eliminated.

#### Fix 4: `accounts.use(name)` clears workspace + corrects docstring → closes C6, I22

- File: `src/mixpanel_data/accounts.py:155-185`
- Body uses `_mutate()`: write `[active].account`, pop `[active].workspace` in same transaction.
- Docstring: drop the `[active].project` reference (project lives on the account in v3); explain "workspaces are project-scoped, so an account swap clears the previous workspace."

#### Fix 5: `Session.headers` immutable → closes C13

- File: `src/mixpanel_data/_internal/auth/session.py:117`
- Field type: `headers: Mapping[str, str] = Field(default_factory=dict)`.
- `model_validator(mode="after")` wrapping in `MappingProxyType` — runtime `TypeError` on mutation.
- Update consumers to copy via `dict(self._session.headers)` when passing to httpx.

#### Fix 6: Make `strict=True` the default + delete `_OAUTH_TOKEN_PENDING` → closes C7

- File: `src/mixpanel_data/_internal/api_client.py:42-150`
- Delete `_OAUTH_TOKEN_PENDING = "pending-login"` constant.
- Delete the `if strict: raise` / `else: token = _OAUTH_TOKEN_PENDING` branches.
- Change `session_to_credentials(strict: bool = True)` default.
- Delete the `strict` kwarg entirely if no caller wants `strict=False` after Group B (legacy paths gone).
- `Workspace.__init__` (after Group B) surfaces `OAuthError("Run mp account login NAME")` at construction. No fake bearer ever exists in the process.

#### Fix 7: `MP_OAUTH_STORAGE_DIR` honored everywhere → closes C8

- File: `src/mixpanel_data/_internal/auth/storage.py`
- Extract module-level `_storage_root() -> Path`: returns `Path(os.environ["MP_OAUTH_STORAGE_DIR"])` if set, else `Path.home() / ".mp"`.
- Refactor `account_dir(name)` → `_storage_root() / "accounts" / name`.
- Refactor `OAuthStorage._default_storage_dir()` → `_storage_root() / "oauth"`.
- Verify: `grep -rn "MP_OAUTH_STORAGE_DIR" tests/` — confirm no test depends on the old asymmetric behavior.
- Add a test asserting `account_dir("foo")` honors the env var.
- **Optional design refinement:** rename to `MP_DATA_DIR` (or `MP_HOME`) since the env var now governs more than OAuth-only state. If renamed, drop the old name entirely (free to break alpha API).

#### Fix 8: Path-traversal tests for `account_dir` → closes C14

- File: `tests/unit/test_storage.py` (new) or `tests/unit/test_token_resolver.py`
- Parametrized test:
  ```python
  @pytest.mark.parametrize("malicious", ["../etc", "a/b", "a\x00b", "..", ".", "name with space", "", "."])
  def test_account_dir_rejects_invalid_names(self, malicious: str) -> None:
      with pytest.raises(ValueError):
          account_dir(malicious)
  ```

### Group B: legacy elimination (newly enabled by free-to-break context)

#### Fix 9: Delete legacy `_internal/config.py` (v1/v2 ConfigManager)

- File to delete: `src/mixpanel_data/_internal/config.py`
- Update all importers to use `_internal/config_v3.py` (which can then be renamed to `config.py` — single source of truth).
- Delete every reference to `Credentials.from_basic`, `Credentials.from_oauth_token`, `AuthMethod`, etc., that exists only to serve the legacy path. Keep what `MixpanelAPIClient` actually consumes (the `Credentials` shim — but consider whether it survives at all once the OAuth shim simplifies in Fix 6).

#### Fix 10: Flatten `Workspace` to single-mode (v3 only) — closes TD-C3 and S1

- File: `src/mixpanel_data/workspace.py`
- Delete `_init_v3` / `_has_v3_config` dual-init machinery.
- Delete the legacy resolver branch and `_resolved_session: ResolvedSession | None` field.
- Delete the 5× `if not hasattr(self, "_v3_session")` guards (lines 677, 695, 704, 713, 768).
- Decision: either flatten `__init__` to require/build a `Session` directly, OR introduce factories — `Workspace.from_session(session)`, `Workspace.from_credentials(...)`, `Workspace.from_config(account=, target=)`. Factory approach gives mypy invariant tracking and is the right shape for 1.0.
- Properties (`account`, `project`, `workspace`, `session`) become typed accesses on `self._session`, no runtime guards.

#### Fix 11: Delete legacy detection in `config_v3.py` — closes C1, C9

- Delete `_LEGACY_DETECTED_MESSAGE` constant (config_v3.py:57-66).
- Delete `_is_legacy()` function (config_v3.py:106-107).
- Delete the `if _is_legacy(raw): raise ConfigError(...)` branch in `_read_raw`.
- A v1/v2 TOML file will now fail at the Pydantic validation layer with a generic-but-honest "unexpected key" error. That's acceptable for alpha.

#### Fix 12: Delete `mp config convert` command

- Delete `src/mixpanel_data/cli/commands/config_cmd.py`.
- Remove its registration from `cli/main.py`.
- No replacement needed — no users to migrate.

#### Fix 13: Delete legacy CLI command groups — closes CLI-dual-stack

- Delete `cli/commands/auth.py` (legacy `mp auth`).
- Delete `cli/commands/context.py` (legacy `mp context`).
- Delete `cli/commands/projects.py` (legacy `mp projects`, plural).
- Delete `cli/commands/workspaces.py` (legacy `mp workspaces`, plural). Confirm via `ls`.
- Remove their registrations from `cli/main.py:191-296`.
- Audit any tests under `tests/unit/cli/` that exercise the legacy commands and delete them.

#### Fix 14: Delete v1 `load_bridge_file` from `bridge.py` — closes I9

- Delete `AuthBridgeFile`, `load_bridge_file`, `write_bridge_file` (v1) — keep only `BridgeFile`, `load_bridge` (v2).
- Move v2 to module-top imports, drop the `# noqa: E402` block at lines 686-714.
- Update any callers (legacy `_internal/config.py:766` already deleted in Fix 9; `cli/commands/auth.py:1148` already deleted in Fix 13).

#### Fix 15: Delete legacy test fixtures and tests

- Delete `tests/fixtures/configs/v1_*.toml`, `tests/fixtures/configs/v2_*.toml` (keep only v3).
- Delete `tests/unit/cli/test_config_legacy_detection.py` (no more legacy detection).
- Audit `tests/unit/test_042_edge_cases.py` for legacy-discrimination tests; delete the `TestWorkspaceV3Discrimination` class and similar.

### Group C: behavior gaps — newly P0 because 1.0 needs them

#### Fix 16: Wire OAuth refresh in `OnDiskTokenResolver` → closes C10

- File: `src/mixpanel_data/_internal/auth/token_resolver.py:140-165`
- Replace the `OAUTH_REFRESH_ERROR` raise with a real refresh: call `OAuthFlow.refresh_tokens(refresh_token)`, persist new tokens via `atomic_write_bytes` (using the on-disk JSON shape produced by `OAuthStorage._write_file`).
- Mirror error semantics from `bridge.refresh_bridge_token` (which already does refresh).
- Tests: assert successful refresh updates tokens.json + returns new bearer; assert refresh failure raises `OAuthError` with actionable message.

#### Fix 17: Implement `mp account login` → closes C11

- File: `src/mixpanel_data/cli/commands/account.py:434-441`
- File: `src/mixpanel_data/accounts.py:237-253`
- Wire `OAuthFlow` into `accounts.login(name, *, open_browser=True) -> OAuthLoginResult`. Call PKCE + browser callback + `/me` probe to backfill `default_project`.
- CLI calls into the namespace function. Remove `NotImplementedError` and the stub message.
- Persist tokens via `atomic_write_bytes` to `account_dir(name) / "tokens.json"`.
- Tests: at minimum a unit test mocking the OAuth flow; an integration test gated by `MP_LIVE_TESTS=1`.

#### Fix 18: Per-request OAuth bearer resolution → closes C12 (depends on Fix 16)

- File: `src/mixpanel_data/_internal/api_client.py`
- For OAuth accounts, `_get_auth_header()` should call `TokenResolver.get_browser_token(...)` (or `get_static_token(...)`) per request — not read from a `Credentials` shim built once.
- Service-account path keeps the existing per-request basic auth (already cheap).
- Closes the C7 recovery gap: process can recover from refresh elsewhere without re-construction.

#### Fix 19: Add `mp target` CLI commands → closes I17

- New file: `src/mixpanel_data/cli/commands/target.py`
- Commands: `mp target add NAME --account A --project P [--workspace W]`, `mp target use NAME`, `mp target list`, `mp target show [NAME]`, `mp target remove NAME`.
- Each delegates to the existing `mp.targets` Python namespace (which already has the methods per `targets.py`).
- Register in `cli/main.py`.
- Tests: smoke tests in `tests/unit/cli/test_target_cli.py`.

### Group D: unused code & cleanup (newly enabled by free-to-break)

#### Fix 20: Delete `DEFAULT_*` property shims → closes S2

- Delete `OAuthStorage.DEFAULT_STORAGE_DIR` property (`storage.py:159-162`).
- Delete `ConfigManager.DEFAULT_CONFIG_PATH` property (`config.py:440-442`, but note `config.py` is being deleted in Fix 9 anyway).

#### Fix 21: Delete `AccountAccessError` → closes S3

- Delete the class from `exceptions.py:401-461`.
- Remove from `__init__.py:63, 309`.
- Re-add when first raise site lands.

#### Fix 22: Delete unwired CLI flags → closes CLI-ignored-flags

- File: `src/mixpanel_data/cli/commands/workspace.py:33` — remove `--refresh` flag.
- File: `src/mixpanel_data/cli/commands/project.py:61-65` — remove `--refresh` flag.
- File: `src/mixpanel_data/cli/commands/session.py:32-37` — remove `--bridge` flag (and the stub branch that reads it).

#### Fix 23: Hide stub functions from `accounts.__all__`

- File: `src/mixpanel_data/accounts.py`
- After Fix 17 wires `login`, only `test()`, `export_bridge()`, `remove_bridge()` remain stubs. Either wire them in this PR or remove them from `__all__` until they're real.
- For `accounts.test()` — it's a one-shot `/me` probe wrapper; consider implementing it now alongside Fix 17's `/me` integration.

---

## P1 — should also land in this PR (1.0-readiness polish)

### Group E: input validation hardening

#### Fix 24: Env var validation → closes I2/I3/I4

- File: `src/mixpanel_data/_internal/auth/resolver.py`
- `_env_region()` (line ~52-57): raise `ConfigError(f"MP_REGION='{val}' is not one of {sorted(_VALID_REGIONS)}")` when set-but-invalid.
- `_resolve_workspace_axis` (line ~221-228): raise `ConfigError(f"MP_WORKSPACE_ID={env_val!r} is not a positive integer")` when set-but-unparsable / non-positive.
- `_resolve_project_axis` (line ~184-186): validate digit-string format.
- Tests for each.

#### Fix 25: `OnDiskTokenResolver` rejects missing/invalid `expires_at` → closes I5

- File: `src/mixpanel_data/_internal/auth/token_resolver.py:118-134`
- Treat missing/null/non-string `expires_at` as fatal — raise `OAuthError`.
- File: bridge courier in `workspace._init_v3` (now in factory or `__init__` after Fix 10): stop writing `expires_at: None` — either don't write the file or compute a real expiry. Better: validate at the `BridgeFile` model level (require `tokens.expires_at` be tz-aware datetime) and the bridge can never produce a token without expiry.
- Tightens `OAuthTokens.expires_at` with a `field_validator` requiring `tzinfo is not None`.

#### Fix 26: `--secret-stdin` no truncation → closes I20

- Files: `src/mixpanel_data/cli/commands/account.py:183, 283`
- Replace `os.read(0, 4096)` with `sys.stdin.buffer.read()` (no cap) plus `.strip()` (handles pipes from `pass`, `cat`, etc.).
- Add a sanity cap (64 KiB) with explicit error if exceeded.

### Group F: intentional public-API surface design

#### Fix 27: Move auth types to a public module → closes TD-C1, I11

- New file: `src/mixpanel_data/auth_types.py` (or extend `mixpanel_data/types.py` if it stays sub-2000 lines).
- Move canonical definitions of: `Account`, `OAuthBrowserAccount`, `OAuthTokenAccount`, `ServiceAccount`, `AccountType`, `Region`, `Project`, `Session`, `WorkspaceRef`, `ActiveSession`, `TokenResolver`, `OnDiskTokenResolver`, `BridgeFile`, `OAuthTokens`.
- `_internal/auth/...` modules become thin re-exporters that import from the public module — flips the import direction (currently `__init__.py` reaches into `_internal/auth/...`).
- Drop the duplicate `_RegionLiteral` / `_AccountTypeLiteral` in `types.py:11820-11859` — single source of truth eliminates drift risk.
- `__init__.py` re-exports cleanly from `mixpanel_data.auth_types`.
- Update `__all__` to reflect the intentional public surface.

#### Fix 28: Discriminated-union helper for `Account` → closes TD-Account.match

- File: `src/mixpanel_data/auth_types.py`
- Add `account.match(*, on_service, on_oauth_browser, on_oauth_token)` method to push exhaustiveness into one place. Replace the 3+ scattered `isinstance` chains in `accounts.py:292-298`, `config_v3.py:_account_to_block`, `api_client.py:session_to_credentials`.

#### Fix 29: Tighten `AccountTestResult` → closes TD-AccountTestResult

- File: `src/mixpanel_data/types.py:11862-11885`
- Replace `user: dict[str, Any] | None` with a `MeUserInfo(BaseModel)` having explicit `id: int`, `email: str` fields.
- Add `model_validator(mode="after")` enforcing `ok=True ⟺ error is None`.
- Apply same treatment to `OAuthLoginResult` (types.py:11915-11939).

#### Fix 30: Promote `_resolve_project_axis` and `_format_no_project_error` to public → closes I27

- File: `src/mixpanel_data/_internal/auth/resolver.py`
- Drop leading underscores; update `__all__`.
- `Workspace.use(account=...)` (or its factory equivalent post-Fix 10) imports without underscore aliases.

### Group G: test coverage & documentation hygiene

#### Fix 31: Comment-rot scrub → closes CA-rot

- Sweep across `src/mixpanel_data/_internal/auth/`, `_internal/config_v3.py`, `_internal/api_client.py`, `accounts.py`, `session.py`, `targets.py`, `workspace.py`, `cli/commands/account.py`, `cli/commands/project.py`, `cli/commands/session.py`, `cli/commands/workspace.py`, `cli/main.py`, `cli/utils.py`, `_internal/auth/__init__.py`, `_internal/auth/storage.py`, `_internal/auth/bridge.py`, `_internal/auth/token_resolver.py`, `_internal/auth/resolver.py`.
- Replace each "Phase N", "FR-NNN", "Research R5", "PR #125", "(regression caught by QA)", "042 redesign" reference with the actual invariant being asserted (e.g., "atomic-on-success swap" instead of "Per Research R5"). Where the comment was just a phase tag, delete entirely.
- Use grep to verify zero remaining matches: `grep -rn "Phase [0-9]\|FR-[0-9]\|Research R[0-9]\|PR #[0-9]\|042 redesign\|regression caught by QA"`.
- Drop empty `if TYPE_CHECKING: pass` blocks in 4 files (account.py:25-26, token_resolver.py:34-35, config_v3.py:53-54, accounts.py:35-36).
- Sync `_internal/auth/__init__.py` "Components" section — currently stale (doesn't mention v3 redesign exports).

#### Fix 32: `current_auth_header` docstring fix → closes I7

- File: `src/mixpanel_data/_internal/api_client.py:833-840`
- "cached" → "current"; add note that the value is computed from current credentials per call.

#### Fix 33: PBT for `ConfigManager` round-trips and `Session.auth_header`

- New PBT files or extend existing ones:
  - `tests/pbt/test_config_v3_pbt.py`: write account → read back → equal property.
  - `tests/pbt/test_session_pbt.py`: extend with `auth_header()` invariant ("returns string starting with `Basic ` or `Bearer `").

#### Fix 34: Atomic-write resilience tests

- `tests/unit/test_io_utils.py`: simulated SIGKILL between tmp-write and replace; verify target file is either old-content or new-content (never partial).
- `tests/unit/test_config_v3.py`: same scenario at the `_mutate()` boundary.

#### Fix 35: Session-scoped fixture asserting test isolation

- `tests/conftest.py`: add an autouse fixture or `pytest_collection_modifyitems` hook that asserts no test ever writes under real `$HOME/.mp/`. Catches env-isolation regressions before they leak tokens.

---

## REJECTED — invalid or low-value (with reasoning)

### TD-C4: `OnDiskTokenResolver(TokenResolver)` Protocol inheritance

**Original claim:** "Inheriting from a Protocol is unusual; disables structural typing guarantee."

**Reasoning:** Inheriting from a Protocol is legal Python; the implementation satisfies it structurally regardless. Refactoring to a separate ABC adds churn for no functional benefit. Skip.

### S6: `_SentinelType` over-engineering

**Original claim:** "22 lines for what could be `_SENTINEL = object()`."

**Reasoning:** Works correctly. The simpler `object()` would lose the human-readable `<UNSET>` repr that's genuinely useful in error traces and debugger output for the public `Session.replace` API. Not worth churning.

### Plan-agent rejected: `apply_active(...)` public method

**Reasoning:** Adds API sprawl overlapping `apply_target` / `set_active` / `update_account`. The internal `_mutate()` context manager (Fix 2) is the right level.

### Plan-agent rejected: header comparison in `MixpanelAPIClient.use()`

**Reasoning:** Fragile (case sensitivity, ordering edge cases). Per-request header attachment (Fix 3) is strictly cleaner.

### Plan-agent originally rejected: `strict=True` as default on `session_to_credentials`

**Original reasoning:** Behavior change too broad — breaks "construct cheap, fail at request" contract.

**Now ACCEPTED (Fix 6):** under the alpha-no-compat constraint, the contract that needed preserving doesn't apply. Default to strict; delete the placeholder.

### Plan-agent originally rejected: `Workspace` factory split

**Original reasoning:** Major refactor for marginal mypy benefit; backward-compat made it expensive.

**Now ACCEPTED (Fix 10):** under the alpha-no-compat constraint, the cost calculus inverts. Full factory split is the right shape for 1.0; legacy `__init__` deletion is now a feature, not a regression.

---

## Files to Modify / Delete

### NEW files
- `src/mixpanel_data/_internal/io_utils.py` (Fix 1)
- `src/mixpanel_data/auth_types.py` (Fix 27) — or extend `mixpanel_data/types.py`
- `src/mixpanel_data/cli/commands/target.py` (Fix 19)
- `tests/unit/test_io_utils.py` (Fix 1)
- `tests/unit/cli/test_target_cli.py` (Fix 19)
- `tests/unit/test_storage.py` (Fix 8) — or extend existing
- `tests/pbt/test_config_v3_pbt.py` (Fix 33)

### DELETED files
- `src/mixpanel_data/_internal/config.py` (Fix 9)
- `src/mixpanel_data/cli/commands/config_cmd.py` (Fix 12)
- `src/mixpanel_data/cli/commands/auth.py` (Fix 13)
- `src/mixpanel_data/cli/commands/context.py` (Fix 13)
- `src/mixpanel_data/cli/commands/projects.py` (Fix 13)
- `src/mixpanel_data/cli/commands/workspaces.py` (Fix 13)
- `tests/fixtures/configs/v1_*.toml`, `v2_*.toml` (Fix 15)
- `tests/unit/cli/test_config_legacy_detection.py` (Fix 15)
- Any other tests exercising deleted legacy commands/paths (audit during Fix 13/15)

### MODIFIED files (P0 + P1)

| File | Fixes |
|------|-------|
| `_internal/config_v3.py` (likely renamed to `_internal/config.py` after Fix 9) | 1, 2, 11 |
| `_internal/auth/storage.py` | 1, 7, 20 |
| `_internal/auth/bridge.py` | 1, 14, 25, 31 |
| `_internal/auth/session.py` | 5, 27, 31 |
| `_internal/auth/resolver.py` | 24, 30, 31 |
| `_internal/auth/token_resolver.py` | 16, 25, 27, 31 |
| `_internal/auth/__init__.py` | 27, 31 |
| `_internal/api_client.py` | 3, 6, 18, 32, 31 |
| `workspace.py` | 1, 2, 3, 10, 31 |
| `accounts.py` | 4, 17, 23, 28, 31 |
| `session.py` | 2, 31 |
| `targets.py` | 31 |
| `__init__.py` | 21, 27 |
| `cli/commands/account.py` | 17, 23, 26, 31 |
| `cli/commands/workspace.py` | 22, 31 |
| `cli/commands/project.py` | 22, 31 |
| `cli/commands/session.py` | 22, 31 |
| `cli/main.py` | 12, 13, 19, 31 |
| `cli/utils.py` | 31 |
| `exceptions.py` | 21 |
| `types.py` | 27, 29 |
| `tests/unit/test_*.py` (broad) | regression coverage for all P0 behavior changes |
| `tests/conftest.py` | 35 |

---

## Verification

### After P0 lands

- `just check` passes (lint + fmt + typecheck + tests-with-coverage + build).
- `pytest tests/unit/test_io_utils.py` covers EXCL collision, exception cleanup, mode preservation, simulated SIGKILL.
- Manual: trace `_atomic_write` and `kill -9` mid-write of `~/.mp/config.toml` → verify config remains parseable on next read.
- Manual: construct `Workspace()` with no `MP_*` env, no config, no bridge → expect `ConfigError("No account configured")`.
- Manual: `mp account use A` → `mp session` shows workspace cleared (not stale from prior account).
- Manual: `mp account add --type oauth_browser foo --default-project 12345 && mp account login foo` → completes PKCE flow, writes valid tokens.
- Manual: `Workspace()` with an oauth_browser account that has expired tokens but valid refresh_token → succeeds via auto-refresh (Fix 16).
- Manual: `MP_OAUTH_STORAGE_DIR=/tmp/x mp account add foo …` → files land under `/tmp/x/accounts/foo/`.
- `python -c "from mixpanel_data import Session; s = Session(...); s.headers['X']='Y'"` → raises `TypeError`.
- Manual: `mp target add ecom --account team --project 3018488 --workspace 3448414 && mp target use ecom` works per `quickstart.md`.
- `account_dir("../etc")` → `ValueError`.
- Manual: legacy CLI commands gone — `mp auth` → "No such command" (Typer help).
- Manual: legacy config gone — placing a v1/v2 config at `~/.mp/config.toml` → fails Pydantic validation; user is told to delete and re-add (no `mp config convert` exists).
- `grep -rn "_OAUTH_TOKEN_PENDING\|pending-login" src/` → zero matches.
- `grep -rn "_LEGACY_DETECTED_MESSAGE\|_is_legacy" src/` → zero matches.
- `grep -rn "_v3_session\|_init_v3\|_has_v3_config" src/` → zero matches.
- `grep -rn "AuthBridgeFile\|load_bridge_file" src/` → zero matches (only `BridgeFile` / `load_bridge` remain).

### After P1 lands

- `MP_REGION=usa mp account list` → `ConfigError("MP_REGION='usa' is not one of [eu, in, us]")`.
- `MP_WORKSPACE_ID=abc mp session` → `ConfigError("MP_WORKSPACE_ID='abc' is not a positive integer")`.
- `from mixpanel_data import ActiveSession, TokenResolver, Account` all work.
- `from mixpanel_data.auth_types import Session` (or whichever public path is chosen) works.
- `account.match(on_service=lambda a: ..., on_oauth_browser=..., on_oauth_token=...)` callable.
- `AccountTestResult(ok=True, error="x")` → `ValidationError`.
- PBT round-trip property holds for `ConfigManager` over hundreds of generated configs.
- `grep -rn "Phase [0-9]\|FR-[0-9]\|Research R[0-9]\|PR #[0-9]\|042 redesign\|regression caught by QA" src/mixpanel_data/` → zero matches.
- Test isolation fixture catches an intentionally-bad test that writes outside `$HOME/.mp/` redirect.

### Post-merge: 1.0-readiness check

- All four agent-types from `mp.accounts.add(type='X', ...)` work end-to-end (`service_account`, `oauth_browser`, `oauth_token`).
- All three CLI namespaces (`mp account`, `mp project`, `mp workspace`, `mp session`, `mp target`) round-trip cleanly with their Python equivalents.
- A user can run a notebook for >1h on an oauth_browser account without 401s (token refresh works).
- No CLI command exits 1 with a "Phase X stub" message; either the command works or it doesn't exist.
- `quickstart.md` runs cleanly start-to-finish without hitting any deferred / stub paths.

---

## Estimated impact

- **Code deleted:** ~2,500–3,500 LoC (legacy `config.py` + 4 legacy CLI command files + v1 bridge + dual-init Workspace branches + legacy fixtures + tests for those).
- **Code added:** ~800–1,200 LoC (atomic-write helper + `_mutate` context manager + `mp target` CLI + OAuth refresh wiring + login wiring + new auth_types module + per-request header refactor + tightened types + new tests).
- **Net:** ~1,500–2,500 LoC reduction with measurably better correctness, security, and 1.0-readiness.
- **Files touched:** ~30 modified + ~7 deleted + ~7 created.
- **Test count:** likely modest decrease (legacy-discrimination tests deleted) offset by new atomic-write, target-CLI, OAuth refresh, login, and PBT tests.
