# Contract: Filesystem Layout

**Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md) · **Config schema**: [config-schema.md](config-schema.md)

This document defines the on-disk filesystem layout for `mixpanel_data` 0.4.0+. Any change to a path, permission, or content-format invariant is a breaking change.

---

## 1. Layout

```
~/.mp/                                       # mode 0o700 (created if absent)
├── config.toml                              # mode 0o600 — main config
│                                            # NOTE: ~~config.toml.legacy~~ never written
│                                            # — `mp config convert` was descoped (see ../spec.md
│                                            # post-implementation notes); upgrading users wipe
│                                            # config.toml and re-add accounts per
│                                            # RELEASE_NOTES_0.4.0.md
├── accounts/                                # mode 0o700
│   ├── {account-name-1}/                    # mode 0o700, one dir per account
│   │   ├── tokens.json                      # mode 0o600 (oauth_browser only)
│   │   ├── client.json                      # mode 0o600 (oauth_browser only)
│   │   └── me.json                          # mode 0o600 (any account; optional)
│   ├── {account-name-2}/
│   │   └── ...
│   └── ...
├── oauth/                                   # LEGACY (pre-0.4.0). Not deleted by 0.4.0;
│   ├── tokens_us.json                       # the user removes it manually if desired.
│   ├── client_us.json                       # No automatic migration into ~/.mp/accounts/{name}/
│   └── me_us_{name}.json                    # — re-run `mp account login NAME` instead.
└── ... (no other files written by mixpanel_data)

~/.claude/mixpanel/                          # Cowork bridge default location (created by `mp account export-bridge`)
└── auth.json                                # mode 0o600 — bridge file (v2 schema)

<workspace-root>/mixpanel_auth.json          # ALTERNATE bridge location (when running in a Cowork workspace)
```

---

## 2. Path conventions

| Purpose | Path |
|---|---|
| Main config | `~/.mp/config.toml` |
| Legacy config archive | `~/.mp/config.toml.legacy` |
| Account state directory | `~/.mp/accounts/{name}/` |
| OAuth tokens | `~/.mp/accounts/{name}/tokens.json` |
| OAuth client info (DCR) | `~/.mp/accounts/{name}/client.json` |
| `/me` cache | `~/.mp/accounts/{name}/me.json` |
| Bridge file (default) | `~/.claude/mixpanel/auth.json` |
| Bridge file (workspace alt) | `<workspace-root>/mixpanel_auth.json` |

### Override paths

| Env var | Effect |
|---|---|
| `MP_CONFIG_PATH` | Overrides `~/.mp/config.toml` location (existing convention) |
| `MP_AUTH_FILE` | Overrides bridge file location |
| `HOME` (POSIX) / `USERPROFILE` (Windows) | Standard home-dir resolution |

---

## 3. Permission invariants

| Path | POSIX mode | Windows |
|---|---|---|
| `~/.mp/` | `0o700` | DACL: owner Full Control, others none |
| `~/.mp/config.toml` | `0o600` | as above |
| `~/.mp/config.toml.legacy` | `0o600` | as above |
| `~/.mp/accounts/` | `0o700` | as above |
| `~/.mp/accounts/{name}/` | `0o700` | as above |
| `~/.mp/accounts/{name}/tokens.json` | `0o600` | as above |
| `~/.mp/accounts/{name}/client.json` | `0o600` | as above |
| `~/.mp/accounts/{name}/me.json` | `0o600` | as above |
| `~/.claude/mixpanel/auth.json` | `0o600` | as above |
| `<workspace>/mixpanel_auth.json` | `0o600` | as above |

Permissions are enforced at every write. On read, the loader logs a warning to stderr if a file's mode is more permissive than expected (consistent with existing v2 behavior).

---

## 4. Atomic writes

All writes use the standard atomic-write pattern:

1. Write to `<path>.tmp.<pid>` with target mode `0o600`.
2. `os.replace(<path>.tmp.<pid>, <path>)` — atomic rename.

Failure modes:
- If the temp write fails (disk full, permission denied), the original file is preserved and an exception propagates.
- If the rename fails (race with another process), the temp file is cleaned up and the operation retries once.

Applies to: `config.toml`, `tokens.json`, `client.json`, `me.json`, bridge files, `config.toml.legacy`.

---

## 5. Directory creation

`ensure_directory(path, mode=0o700)` is the single helper for directory creation. It:

1. Creates intermediate dirs as needed (`os.makedirs(path, exist_ok=True)`).
2. Sets mode `0o700` on each directory (cures the historical "umask was 022" problem on POSIX).
3. On Windows, sets the equivalent ACL via `pywin32` if available; otherwise emits a warning and continues (existing v2 behavior).

Applied to:
- `~/.mp/` — at first write of any file in `~/.mp/`
- `~/.mp/accounts/` — at first per-account file write
- `~/.mp/accounts/{name}/` — at first write of any file in that account dir
- `~/.claude/mixpanel/` — at first bridge write (`mp account export-bridge` only)

---

## 6. File content invariants

### 6.1 `~/.mp/config.toml`

- TOML-encoded per [config-schema.md](config-schema.md).
- Key ordering preserved across writes (using `tomli_w.dumps(...)` with stable key order).
- No trailing whitespace; one newline at EOF.

### 6.2 `~/.mp/accounts/{name}/tokens.json`

```json
{
  "access_token": "ey...",
  "refresh_token": "...",
  "expires_at": "2026-04-22T12:00:00Z",
  "token_type": "Bearer",
  "scope": "..."
}
```

- Pydantic `OAuthTokens.model_dump_json(...)` produces the canonical form.
- No `project_id` field (dropped per FR-062).
- Forward-compat: unknown fields accepted on read (`extra="ignore"`), preserved on rewrite via merge.

### 6.3 `~/.mp/accounts/{name}/client.json`

```json
{
  "client_id": "...",
  "client_secret": "...",
  "registration_endpoint": "...",
  "issued_at": "...",
  "redirect_uris": ["http://localhost:8765/callback"],
  "scopes": ["openid", "..."]
}
```

- `OAuthClientInfo.model_dump_json(...)` canonical.
- Forward-compat: `extra="ignore"`.

### 6.4 `~/.mp/accounts/{name}/me.json`

```json
{
  "fetched_at": "2026-04-21T12:34:56Z",
  "ttl_seconds": 86400,
  "response": {
    "user": { "id": 42, "email": "..." },
    "projects": { "...": { ... } },
    "...": "..."
  }
}
```

- Wraps the raw `/me` response in a cache envelope with `fetched_at` + `ttl_seconds`.
- Cache is invalidated when (a) `now() > fetched_at + ttl_seconds`, or (b) `--refresh` flag, or (c) the user runs `mp account login NAME` (login implies new identity).
- TTL is 24 h by default.

### 6.5 `~/.claude/mixpanel/auth.json` (bridge)

Per [config-schema.md §2](config-schema.md). Strict v2 schema.

### 6.6 `~/.mp/config.toml.legacy`

- Verbatim copy of the original `config.toml` at the moment of conversion.
- Created with `0o600`.
- Never modified after creation.
- Its presence indicates `mp config convert` ran at least once on this machine.
- Safe to delete manually post-verification.

---

## 7. Cleanup semantics

### 7.1 `mp account remove NAME`

- Deletes `~/.mp/accounts/{name}/` and all files within (recursive).
- Does NOT delete the parent `~/.mp/accounts/` directory even if empty.
- Removes `[accounts.NAME]` from `~/.mp/config.toml`.
- If `[active].account == NAME`, clears `[active].account` (subsequent commands raise `ConfigError("No account configured")`).

### 7.2 `mp account logout NAME`

- Deletes `~/.mp/accounts/{name}/tokens.json` only.
- Preserves `client.json` (DCR registration is reusable for re-login).
- Preserves `me.json` (cache; will refresh on next access).
- Does NOT modify `~/.mp/config.toml`.

### 7.3 `mp config convert`

- Renames `~/.mp/config.toml` → `~/.mp/config.toml.legacy`.
- Writes new `~/.mp/config.toml` (v3 schema).
- Migrates token files from `~/.mp/oauth/tokens_{region}.json` → `~/.mp/accounts/{name}/tokens.json` per Research R1.
- Leaves `~/.mp/oauth/` directory intact (does NOT delete remaining files); reports them in the conversion summary so the user can decide.

### 7.4 `mp account remove-bridge`

- Deletes the bridge file at the resolved path (default or `--at PATH`).
- Does NOT delete the parent `~/.claude/mixpanel/` directory.

### 7.5 No automatic cleanup

The library never deletes files outside the documented cleanup commands. Stale `me.json` files (after their TTL) are overwritten on next fetch but never deleted. Stale `client.json` files (after `mp account remove-bridge` or rotation) survive — DCR registration cleanup is the user's responsibility (Mixpanel does not currently expose DCR deregistration).

---

## 8. Cross-platform notes

### POSIX (macOS, Linux)

- File modes enforced via `os.chmod(path, mode)`.
- Directory modes enforced via `os.makedirs(path, mode=mode)` followed by `os.chmod(path, mode)` (some POSIX systems honor umask differently for makedirs).
- Symlinks: `~/.mp/config.toml` may be a symlink (e.g., to a dotfiles repo); the library follows symlinks for reads and writes through them. The mode check checks the *target's* mode.

### Windows

- File modes enforced via Windows ACL when `pywin32` is available; otherwise a warning is emitted and the standard "owner-only" default ACL of the user profile is relied upon.
- Path separator: `pathlib.Path` handles both forward and backslash; library always presents user-facing paths with `os.sep`.
- `~/.claude/mixpanel/auth.json` resolves to `%USERPROFILE%\.claude\mixpanel\auth.json`.

### WSL

- Treated as POSIX; uses `~/.mp/` under the WSL home, not the Windows home, unless `MP_CONFIG_PATH` is set.

---

## 9. Storage size expectations

- `config.toml`: <100 KB typical; <1 MB upper bound.
- `tokens.json`: <2 KB typical.
- `client.json`: <2 KB typical.
- `me.json`: 10–500 KB (depends on the user's project count; ~1 KB per project).
- Bridge file: <5 KB typical.

Total per-machine footprint: typically <1 MB across all `~/.mp/` files.

---

## 10. Test surface

- **Unit (`tests/unit/test_storage_v3.py`)**: directory creation, mode enforcement, atomic writes, file content schema.
- **Integration (`tests/integration/test_config_conversion.py`)**: end-to-end conversion of legacy fixtures including OAuth token migration.
- **Cross-platform**: the test suite runs on macOS and Linux in CI; Windows runs on a nightly pipeline (existing project convention).
