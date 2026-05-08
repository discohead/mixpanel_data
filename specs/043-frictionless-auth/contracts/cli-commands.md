# CLI Commands Contract: Frictionless Auth

**Feature**: 043-frictionless-auth
**Modules**: `src/mixpanel_headless/cli/commands/login.py` (new), `src/mixpanel_headless/cli/commands/account.py` (modified)

---

## 1. `mp login` (new)

The conversational entry point. Thin Typer wrapper over `accounts.login_unified()`.

### 1.1 Synopsis

```
mp login [OPTIONS]
```

### 1.2 Options

| Flag | Type | Default | Notes |
|------|------|---------|-------|
| `--name TEXT` | str | (derived) | Local account name. Wins over derived names. |
| `--region {us\|eu\|in}` | enum | `us` for browser; (probed) for SA / token | Forces a specific region. |
| `--project TEXT` | str | (interactive / single auto-pick) | Project ID to bind to the new account. Hard-fails if not visible. |
| `--service-account / -S` | flag | False | Force the `service_account` auth path. |
| `--token-env TEXT` | str | (None) | Force `oauth_token` auth from the named env var. Defaults to `MP_OAUTH_TOKEN` when `--token-env` is passed without a value. |
| `--no-browser` | flag | False | For `oauth_browser`, print the authorization URL instead of opening the browser. |
| `--secret-stdin` | flag | False | For `service_account`, read the secret from stdin instead of `MP_SECRET` / interactive prompt. |
| `-h / --help` | flag | — | Print help and exit. |

### 1.3 Auth-type detection priority

`mp login` resolves which credential type to collect using:

1. `--service-account` flag → `service_account`
2. `--token-env NAME` flag (or env var when bare) → `oauth_token`
3. `MP_USERNAME` + `MP_SECRET` env both set → `service_account`
4. `MP_OAUTH_TOKEN` env set → `oauth_token`
5. Default → `oauth_browser`

The first match wins. Subsequent rules are not evaluated.

### 1.4 Stdout / stderr split

| Stream | Content |
|--------|---------|
| **stdout** | Final success summary line ONLY. Format: `Logged in as {user_email} → {account_name} · {project_name}` (single line, terminated with newline). |
| **stderr** | All progress output: region probe attempts (one line each), `MP_PROJECT_ID` fallthrough warning, re-login `--project` ignored note, browser-flow URL when `--no-browser`, project / org picker prompts. |

This split makes `mp login | tee log.txt` capture only the structured success line, leaving conversational output in the terminal.

### 1.5 Exit codes

| Code | Source | When |
|------|--------|------|
| 0 | success | New account added (or refreshed) and activated. |
| 1 | `ConfigError` (general) | Project not visible, config write failure, naming collision exhausted, `mp account add` would have errored. |
| 2 | `AuthenticationError` | OAuth callback returned an auth error; service-account credential rejected by every region. |
| 3 | `INVALID_ARGS` | Mutually exclusive flags supplied (`--service-account` and `--token-env`); non-interactive context with no project / org default; `--project ID` not visible to the credential. |
| 5 | `RateLimitError` | `/me` returned 429 from one of the probed clusters. |

Exit codes match the existing `cli/utils.py::ExitCode` enum exactly. The `@handle_errors` decorator handles all mapping.

### 1.6 Interactive prompt formats

#### 1.6.1 Project picker (rendered to stderr when `stdin.isatty()`)

```
Found 3 projects across 2 organizations:

  1) Acme · Production       (id 3713224, us)
  2) Acme · Staging          (id 3713225, us)
  3) Acme Labs · Sandbox     (id 4001122, eu)

Which project? [1]: _
```

Format rules:
- Sort alphabetically by project name within org, then by org name.
- `<org_name> · <project_name>` shown when more than one org is present; otherwise just `<project_name>`.
- `(id N, region)` right-padded so columns align.
- Default `[1]`; pressing Enter accepts.
- Invalid input re-prompts up to 3 times. The third invalid response raises `ConfigError("Could not pick a project after 3 attempts.")`.

#### 1.6.2 Org picker (rendered to stderr when `stdin.isatty()` AND `len(me.organizations) > 1` AND `--name` not supplied)

```
Account spans 2 organizations:

  1) Acme Inc.        (id 1234)
  2) Acme Labs        (id 5678)

Which org's name should the local account be slugged from? [1]: _
```

The chosen org's name is fed into `naming.default_account_name` to compute the slug. If `--name` is set, this prompt is skipped entirely (the explicit name wins).

### 1.7 Non-interactive failure modes

When `stdin.isatty()` is False AND a picker would have been shown:

```text
ERROR: Multiple projects accessible to this account; no default could be picked.

Accessible projects:
  1) Acme · Production       (id 3713224, us)
  2) Acme · Staging          (id 3713225, us)
  3) Acme Labs · Sandbox     (id 4001122, eu)

Pass --project ID to select one explicitly, or set MP_PROJECT_ID.
```

Exit code: `3` (`INVALID_ARGS`). The org-picker case has the analogous structured failure.

### 1.8 Examples (from `--help`)

```text
# Browser login, fully automatic
mp login

# Service account from env, region auto-detected
MP_USERNAME=svc MP_SECRET=$(cat secret.txt) mp login

# Service account from stdin
cat secret.txt | mp login --service-account --secret-stdin --name prod-sa

# OAuth token from a named env var
MY_TOKEN=eyJhbG... mp login --token-env MY_TOKEN

# Browser login with explicit project (skip prompt)
mp login --project 3713224

# Headless browser flow
mp login --no-browser
```

---

## 2. `mp account add` (modified)

Existing command with two relaxations. All existing flags preserved; new behavior is opt-in (omit a flag to trigger the new path).

### 2.1 Changes from current behavior

| Field | Before | After |
|-------|--------|-------|
| `NAME` positional | required | optional — when omitted, derives from org via `naming.default_account_name(/me, existing)`. Requires the type-specific credential collection to succeed first so `/me` is reachable. |
| `--region` option | required | optional for `service_account` and `oauth_token` — when omitted, probes via `region_probe.probe_region`. Already optional for `oauth_browser`. |
| `--project` option | required for `service_account` and `oauth_token` | optional for all three types. SA without `--project` produces an account with no `default_project`; user must run `mp project use ID` before queries. |

### 2.2 Help text update

The `--help` epilog gains:

```text
TIP: For new setups, prefer `mp login` for a guided flow. `mp account add`
remains the explicit, scriptable path for CI and automation.
```

### 2.3 No exit code changes

All exit codes preserved. New error paths reuse existing codes.

---

## 3. `mp project list` (modified — message extension only)

When the underlying `MeService.fetch()` returns 403 for a service account, the existing `ConfigError("Service account 'X' lacks /me permission")` message is extended:

**Before**:
```
ERROR: Service account 'prod-sa' lacks /me permission.
```

**After**:
```
ERROR: Service account 'prod-sa' is missing the `user_details` scope.
Re-mint the SA in Mixpanel Settings → Service Accounts with that scope
checked, or pass --project ID explicitly.
```

The behavior change is the message only. Exit code, return value, and call site remain the same.

---

## 4. CLI registration

`src/mixpanel_headless/cli/main.py::_register_commands()` adds one new line:

```python
app.command(
    name="login",
    help="Add a Mixpanel account with guided region / project / name resolution.",
)(login.login)
```

`mp login` lands as a top-level command alongside `mp account`, `mp project`, `mp workspace`, `mp target`, `mp session`, `mp query`, etc.

---

## 5. Argument validation rules

| Combination | Result |
|-------------|--------|
| `--service-account` AND `--token-env` | `INVALID_ARGS` (mutually exclusive auth-type flags). |
| `--no-browser` AND `--service-account` | `INVALID_ARGS` (`--no-browser` is meaningful only for `oauth_browser`). |
| `--secret-stdin` AND auth type detected as `oauth_browser` or `oauth_token` | `INVALID_ARGS` (`--secret-stdin` is meaningful only for `service_account`). |
| `--region X` with re-login on existing account that has region != X | `ConfigError` exit 1 (per FR-022). |
| `--project N` with N not in `/me` | `ConfigError` exit 1, message lists accessible projects. |

Validation runs before any network I/O so failures are fast.

---

## 6. Snapshot test coverage matrix

`tests/unit/cli/test_login_cli.py` covers (via Typer's `CliRunner` + Rich snapshot fixtures):

| Test | Scenario | Expected stdout / stderr / exit |
|------|----------|--------------------------------|
| `test_login_browser_happy_single_project` | Browser login, single project | stdout: success summary; exit 0 |
| `test_login_browser_multi_project_prompt` | Browser login, 3 projects, picks #2 via TTY | stderr prompt rendered; stdout success; exit 0 |
| `test_login_browser_non_tty_no_project` | Browser login, multi-project, no TTY | stderr structured failure; exit 3 |
| `test_login_browser_explicit_project` | Browser login with `--project 3713224` | no prompt; stdout success; exit 0 |
| `test_login_browser_project_not_visible` | `--project 99999` not in `/me` | exit 1 with project list in stderr |
| `test_login_browser_region_mismatch` | `--region us` but picked project's `domain` is `eu.mixpanel.com` | exit 1 with region-mismatch error |
| `test_login_sa_probe_us_success` | SA login, no `--region`, US succeeds first | stderr "trying us…✓"; exit 0 |
| `test_login_sa_probe_eu_success` | SA login, no `--region`, US fails, EU succeeds | stderr "trying us…✗ trying eu…✓"; exit 0 |
| `test_login_sa_probe_all_fail` | SA login, every region returns 401 | exit 2 with consolidated error |
| `test_login_sa_403_scope_hint` | SA missing `user_details` | exit 1 with scope-hint message |
| `test_login_relogin_browser_preserves_project` | Re-login same name, `default_project` unchanged | exit 0; config inspection |
| `test_login_relogin_with_project_emits_warning` | Re-login with `--project N` | stderr "note: --project ignored…"; exit 0 |
| `test_login_relogin_region_change_refused` | Re-login with `--region eu` against us account | exit 1 with refusal message |
| `test_login_explicit_name_wins` | `--name foo` with derived would-be `acme` | account `foo` written; exit 0 |
| `test_login_collision_suffix` | Existing `acme-corp`, login as different acme org | account `acme-corp-2` written; exit 0 |
| `test_login_mp_project_id_stale_warning` | `MP_PROJECT_ID=999` not visible | stderr fallthrough warning; exit 0 with picker |
| `test_login_mutually_exclusive_flags` | `--service-account --token-env X` | exit 3 |

Each test asserts on (a) exit code, (b) stdout content, (c) stderr content, and (d) the resulting `~/.mp/config.toml` state where applicable.
