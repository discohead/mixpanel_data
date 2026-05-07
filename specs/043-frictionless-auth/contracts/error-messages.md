# Error Message Catalog: Frictionless Auth

**Feature**: 043-frictionless-auth
**Purpose**: Single source of truth for the user-facing error strings introduced by `mp login` and the relaxed `mp account add` paths. Every message listed here is asserted in `tests/unit/cli/test_login_cli.py` (or the matching `test_account_add.py`) so a drift in wording breaks CI.

The string templates use `{placeholder}` syntax. Capitalization, punctuation, and line breaks are normative. All messages are written to stderr; none appear on stdout.

---

## E-1. Region probe — all regions failed

**Source**: `region_probe.RegionProbeError` formatted by `cli/utils.py::handle_errors`.

```text
ERROR: Credential not valid in any region.

Probe results:
  us: 401 Unauthorized
  eu: 401 Unauthorized
  in: 401 Unauthorized

If you know the region, pass --region {us|eu|in} explicitly to skip the probe.
If your service account is new, verify the username and secret are correct.
```

**Exit code**: `2` (`AuthenticationError`).
**Triggered by**: `accounts.login_unified()` when `region_probe.probe_region` raises `RegionProbeError`. The status-code list is the literal `RegionProbeResult.attempts` content; network errors render as `0 (network error: <reason>)`.

---

## E-2. Region mismatch (browser auth, picked project's region differs from auth region)

**Source**: `accounts.login_unified()` after `/me` returns and project is picked.

```text
ERROR: Region mismatch.

You authenticated against the {auth_region} cluster, but project {project_id}
({project_name}) lives in the {project_region} cluster ({project_domain}).

Re-run with the correct region:
    mp login --region {project_region}
```

**Exit code**: `1` (`ConfigError`).
**Triggered by**: oauth_browser path only (SA / token paths probe the right region).

---

## E-3. Re-login refused (region change)

**Source**: `accounts.login_unified()` re-login path.

```text
ERROR: Account '{name}' is bound to region '{existing_region}'; cannot
change to '{requested_region}' on re-login.

To switch regions, remove the existing account first:
    mp account remove {name}
    mp login --region {requested_region}
```

**Exit code**: `1` (`ConfigError`).
**Triggered by**: re-login with `--region` differing from the existing account's region.

---

## E-4. Re-login refused (auth-type change)

**Source**: `accounts.login_unified()` re-login path.

```text
ERROR: Account '{name}' is type '{existing_type}'; cannot re-login as
type '{requested_type}'.

To change the auth type, remove the existing account first:
    mp account remove {name}
    mp login {requested_type_flag}
```

**Exit code**: `1` (`ConfigError`).
**Triggered by**: re-login with an explicit `--service-account` / `--token-env` against an existing account of a different type.

---

## E-5. Re-login project change ignored (informational, not an error)

**Source**: `accounts.login_unified()` re-login path. Written to stderr, exit code stays 0.

```text
note: --project ignored on re-login; use 'mp project use {project_id}' to change the active project.
```

**Variant** (when `MP_PROJECT_ID` is set instead of `--project`):

```text
note: MP_PROJECT_ID ignored on re-login; use 'mp project use {project_id}' to change the active project.
```

**Exit code**: `0` (success — refresh proceeds normally).

---

## E-6. Project not visible (`--project` flag)

**Source**: `accounts.login_unified()` after `/me` returns.

```text
ERROR: Project ID {project_id} is not visible to this account.

Accessible projects:
  - {pid_1} : {project_name_1} ({region_1})
  - {pid_2} : {project_name_2} ({region_2})
  ...

Pick one and re-run:
    mp login --project {accessible_pid}
```

**Exit code**: `1` (`ConfigError`).
**Triggered by**: `--project N` where N is not in `/me` projects.

---

## E-7. `MP_PROJECT_ID` stale (informational, not an error)

**Source**: `accounts.login_unified()` after `/me` returns. Written to stderr.

```text
note: MP_PROJECT_ID={project_id} is not visible to this account; falling through to project picker.
```

**Exit code**: depends on what the picker does next (0 on success, 3 if the picker itself fails non-interactively).
**Triggered by**: `MP_PROJECT_ID` set, the value not in `/me`, AND no `--project` flag passed.

---

## E-8. Non-interactive context, no project default

**Source**: `accounts.login_unified()` when `stdin.isatty() == False` AND no project picker callback supplied.

```text
ERROR: Multiple projects accessible to this account; no default could be picked.

Accessible projects:
  - {pid_1} : {project_name_1} ({region_1})
  - {pid_2} : {project_name_2} ({region_2})
  ...

Pass --project ID to select one explicitly, or set MP_PROJECT_ID.
```

**Exit code**: `3` (`INVALID_ARGS`).

---

## E-9. Non-interactive context, multi-org, no `--name`

**Source**: `accounts.login_unified()` when `stdin.isatty() == False` AND `len(me.organizations) > 1` AND no `--name`.

```text
ERROR: Account spans multiple organizations; cannot derive a default local name.

Accessible organizations:
  - {org_id_1} : {org_name_1}
  - {org_id_2} : {org_name_2}
  ...

Pass --name LOCAL_NAME to set the local account name explicitly.
```

**Exit code**: `3` (`INVALID_ARGS`).

---

## E-10. Service account missing `user_details` scope

**Source**: `cli/commands/account.py::project_list` (and any other callsite that hits `/me` for a SA). Extends the existing 403 → `ConfigError` mapping.

```text
ERROR: Service account '{name}' is missing the `user_details` scope.

Re-mint the SA in Mixpanel Settings → Service Accounts with that scope checked,
or pass --project ID explicitly to skip the /me lookup.
```

**Exit code**: `1` (`ConfigError`).
**Triggered by**: `MeService.fetch()` returns 403 for a service-account credential.

---

## E-11. Mutually exclusive auth-type flags

**Source**: `cli/commands/login.py` argument validation (before any network I/O).

```text
ERROR: --service-account and --token-env are mutually exclusive.

Pick one auth type:
    mp login --service-account
    mp login --token-env MY_OAUTH_TOKEN_VAR
```

**Exit code**: `3` (`INVALID_ARGS`).

---

## E-12. `--no-browser` with non-browser auth

**Source**: `cli/commands/login.py` argument validation.

```text
ERROR: --no-browser is only meaningful for the oauth_browser auth type.

Detected auth type: {detected_type}.
```

**Exit code**: `3` (`INVALID_ARGS`).

---

## E-13. `--secret-stdin` with non-SA auth

**Source**: `cli/commands/login.py` argument validation.

```text
ERROR: --secret-stdin is only meaningful for the service_account auth type.

Detected auth type: {detected_type}.
```

**Exit code**: `3` (`INVALID_ARGS`).

---

## E-14. Project picker — too many invalid responses

**Source**: `cli/commands/login.py` interactive prompt loop.

```text
ERROR: Could not pick a project after 3 attempts. Aborting.
```

**Exit code**: `1` (`ConfigError`).
**Triggered by**: three consecutive invalid responses to the `Which project?` prompt.

---

## E-15. Org picker — too many invalid responses

**Source**: `cli/commands/login.py` interactive prompt loop.

```text
ERROR: Could not pick an organization after 3 attempts. Aborting.
```

**Exit code**: `1` (`ConfigError`).

---

## E-16. Slug derivation produced empty result, fallback to `org-{id}` collided

**Source**: `naming.default_account_name` exhausting the suffix sequence is treated as impossible (suffixes go to infinity), so this case is **not** a user-facing error. If a user has 100 accounts collide on the same `org-12345-N` base, that is a config-management issue worth surfacing — but the function will keep counting up. No error string defined.

**Exit code**: not applicable.

---

## E-17. Account name supplied collides with existing account of a different type

**Source**: `accounts.login_unified()`. This is the same as E-4 (auth-type mismatch on re-login).

**Cross-reference**: see E-4.

---

## Naming conventions used in this catalog

- All ERROR lines start with `ERROR: ` (capital, with colon-space).
- All informational stderr lines start with `note: ` (lowercase, with colon-space). These do NOT change exit code.
- Multi-line errors are separated by one blank line between sections.
- Suggested-fix commands are indented 4 spaces and rendered without backticks (so they paste cleanly into a terminal).
- Placeholders use `{snake_case_name}` and are documented in each entry.

This catalog is the source of truth. If a developer wants to change a message, the change lands in this file first, then in the implementation, then in the matching test snapshot.
