# Python API Contract: Frictionless Auth

**Feature**: 043-frictionless-auth
**Module**: `mixpanel_headless.accounts` (existing) + new helpers in `_internal/auth/`

This contract is normative. Any change to a signature, return type, raised exception, or documented side-effect requires bumping the package minor version and updating the changelog.

---

## 1. `accounts.login_unified()`

The single new public entry point. Lives in `src/mixpanel_headless/accounts.py`.

```python
def login_unified(
    *,
    name: str | None = None,
    region: Region | None = None,
    project: str | None = None,
    account_type: AccountType | None = None,
    no_browser: bool = False,
    secret_stdin: bool = False,
    token_env: str | None = None,
    service_account: bool = False,
    project_picker: ProjectPicker | None = None,
) -> AccountSummary:
    """Add and activate a Mixpanel account in one call.

    Auth-type detection priority (first match wins):
        1. ``account_type`` parameter (explicit override)
        2. ``token_env`` set → ``oauth_token``
        3. ``MP_USERNAME`` + ``MP_SECRET`` env both set → ``service_account``
        4. ``MP_OAUTH_TOKEN`` env set → ``oauth_token``
        5. Default → ``oauth_browser``

    Project-selection priority (first match wins, applied AFTER ``/me``):
        1. ``project`` parameter (must exist in ``/me``)
        2. ``MP_PROJECT_ID`` env (soft default; warn-and-fall-through if missing)
        3. Single project in ``/me`` → auto-pick
        4. Caller-supplied interactive picker (CLI handles this; the
           library raises ``ConfigError`` with the project list when the
           caller does not provide a picker callback)

    Region resolution:
        - ``oauth_browser``: ``region`` (default ``"us"``) committed
          before the PKCE redirect; ``/me`` consulted after callback;
          mismatch with picked project's ``domain`` raises ``ConfigError``.
        - ``service_account`` / ``oauth_token``: if ``region`` is None,
          probes ``us`` → ``eu`` → ``in`` against ``/me`` until first 200.

    Account naming:
        - If ``name`` is supplied, it wins unconditionally.
        - Otherwise derived via ``naming.default_account_name(me, existing)``.
          See §2.2 below.

    Re-login (when the resolved name matches an existing account):
        - Refreshes tokens (oauth_browser) or updates credential fields
          (service_account / oauth_token).
        - Leaves ``default_project`` UNCHANGED. ``project`` and
          ``MP_PROJECT_ID`` are ignored on the re-login path.
        - Region change is REFUSED with ``ConfigError`` directing the
          user to remove the account first.

    Args:
        name: Explicit local account name. Wins over derived names.
        region: Explicit region. If None, browser auth defaults to
            ``"us"`` and probes for SA / token.
        project: Explicit project ID. Must exist in ``/me``.
        account_type: Explicit auth-type override. If None, detected
            from env.
        no_browser: For oauth_browser, print the authorization URL
            instead of opening the browser. Useful for headless setups.
        secret_stdin: For service_account, read the secret from stdin
            instead of env / interactive prompt.
        token_env: For oauth_token, name of the env var holding the
            bearer token. Defaults to ``MP_OAUTH_TOKEN`` when not set.

    Returns:
        ``AccountSummary`` for the newly added (or refreshed) account.
        The returned summary's ``user_email`` / ``project_id`` /
        ``project_name`` fields are populated from the ``/me``
        round-trip (None on payloads where ``/me`` lacked the data).

    Raises:
        InvalidArgumentError: For mutually-incompatible flag
            combinations: ``service_account`` + ``token_env``;
            ``no_browser`` against a non-browser auth type;
            ``secret_stdin`` against a non-SA auth type. Carries a
            ``violation`` discriminator (``"mutually_exclusive"`` /
            ``"no_browser_misuse"`` / ``"secret_stdin_misuse"``) and
            ``detected_auth_type`` in ``details`` so non-CLI callers
            can dispatch programmatically. The CLI ``handle_errors``
            decorator maps this subclass to exit code 3
            (``INVALID_ARGS``).
        ConfigError: On project mismatch, region mismatch, type
            mismatch on re-login, missing required env vars, or
            non-interactive context with no project / org default.
        OAuthError: On PKCE failure or all-region probe failure
            (raised as ``RegionProbeError`` subclass).
        AccountInUseError: When the account is currently active and
            being recreated (re-login refresh path bypasses this; only
            triggers if the user passes a different ``account_type``
            for an existing name).
    """
```

The new ``service_account`` keyword mirrors the CLI's
``--service-account`` flag. Library callers that pass
``account_type="service_account"`` directly can leave it ``False``;
both spellings produce identical downstream behavior.

The new ``project_picker`` keyword is the callable invoked when more
than one project is visible in ``/me`` and no other project source
resolved. Library callers that omit it get a hard-failing
``ConfigError`` listing the accessible projects (E-8).

**Side effects** (in addition to the documented return):
- Writes / updates `~/.mp/accounts/{name}/tokens.json` (mode `0o600`) and `client.json` (mode `0o600`) for `oauth_browser`.
- Writes `~/.mp/accounts/{name}/me.json` (the populated `MeCache`) on every code path — new browser, new credential, AND re-login. Failed cache writes inside the new-browser path are caught by the same `add()` rollback that handles config-write failures.
- Writes / updates `~/.mp/config.toml` via `ConfigManager.add_account()` and promotes the account to `[active]` via `accounts.use()`. Activation runs unconditionally (not just on first-account creation), so library callers see the same "Add and activate" semantics the docstring promises.
- For new-account creation (not re-login), creates `~/.mp/accounts/.tmp-{nonce}/` first and atomically renames after `/me` resolution. On failure, removes the placeholder.
- Writes one stderr line on each of: region probe progress (one line per attempt), `MP_PROJECT_ID` fallthrough warning, and re-login `--project` ignored note.

**Re-login storage-mode preservation**: when the named account already exists with `token_env=NAME` (env-reference storage) and the caller does NOT pass `token_env=`, the orchestrator preserves the env-reference mode rather than silently overwriting it with the inline `SecretStr(bearer)`. To switch storage modes, pass `token_env=NAME` (or a different env var name) explicitly.

**Idempotency**: Re-running `login_unified(name="foo")` against an existing `foo` account preserves `default_project`. See data-model.md §4.

---

## 2. New pure helpers

Both modules are pure-functional (no I/O, no `os.environ` access, no globals). All inputs are explicit parameters. This is what makes them mutation-testable.

### 2.1 `region_probe.probe_region`

Lives in `src/mixpanel_headless/_internal/auth/region_probe.py`.

```python
from typing import Callable
import httpx
from mixpanel_headless._internal.auth.account import Region


ClientFactory = Callable[[Region], httpx.Client]


def probe_region(
    client_factory: ClientFactory,
    headers: dict[str, str],
    *,
    timeout_seconds: float = 5.0,
    order: tuple[Region, ...] = ("us", "eu", "in"),
) -> RegionProbeResult:
    """Sequentially probe regions until one accepts the credential.

    For each region in ``order``, builds an ``httpx.Client`` via
    ``client_factory(region)``, issues GET ``/api/app/me`` with
    ``headers``, and returns the first 200. Stops at first success.

    Args:
        client_factory: Builds a region-scoped httpx Client. Allows
            tests to inject mock transports without monkey-patching.
        headers: Request headers carrying the credential
            (``Authorization: Basic ...`` for SA, ``Bearer ...`` for
            token). The caller constructs these so this function does
            not have to know about credential types.
        timeout_seconds: Per-region request timeout. Default 5 s.
        order: Probe order. Default (``us``, ``eu``, ``in``) per R-1.

    Returns:
        ``RegionProbeResult`` carrying the first successful region and
        the ordered attempts list.

    Raises:
        RegionProbeError: When every region in ``order`` returns
            non-200. Carries the full attempt list for diagnostic use.
    """
```

**Behavior contracts**:
- MUST short-circuit at first 200. Subsequent regions in `order` MUST NOT be probed.
- MUST raise `RegionProbeError` when no region returns 200, with `attempts` populated for every probed region.
- MUST treat network errors (`httpx.RequestError`) as one of the per-region failures (status code recorded as `0` in `attempts`).
- MUST NOT log or print anything. Caller is responsible for stderr progress lines.

### 2.2 `naming.slugify` and `naming.default_account_name`

Lives in `src/mixpanel_headless/_internal/auth/naming.py`.

```python
from mixpanel_headless._internal.me import MeResponse


_SLUG_MAX_LEN = 32  # leaves headroom under _AccountBase.name's 64-char ceiling


def slugify(value: str | None) -> str:
    """Reduce an org name to the [a-z0-9-]{0,32} subset.

    Rules (applied in order):
        1. Coerce None / empty to "".
        2. NFKD-normalize and ASCII-fold (drops accents: "Café" -> "cafe").
        3. Lowercase.
        4. Replace any run of non-[a-z0-9] characters with a single "-".
        5. Strip leading / trailing "-".
        6. Truncate to 32 chars; strip trailing "-" left by truncation.

    Returns the slug, or "" if no characters survived. Callers MUST
    handle the empty-string fallback (typically ``f"org-{org_id}"``).

    Args:
        value: Org name (or any string).

    Returns:
        Slugified string matching ``^[a-z0-9-]{0,32}$``. Empty when
        no input characters survived normalization.
    """


def default_account_name(me: MeResponse, existing: set[str]) -> str:
    """Pick a default account name from /me, suffixing on collision.

    Uses the first org returned by ``me.organizations`` (insertion order
    of the dict) as the slug source. If the org name is empty after
    slugification, falls back to ``f"org-{org_id}"``.

    Collision suffixing: if the base slug is already in ``existing``,
    appends ``-2``, ``-3``, ... until a unique name is found.

    Args:
        me: Parsed ``/me`` response.
        existing: Set of already-taken local account names. Caller
            populates from ``ConfigManager.list_accounts()``.

    Returns:
        Unique account name matching ``^[a-zA-Z0-9_-]{1,64}$``.
    """
```

**Behavior contracts**:
- `slugify` MUST be idempotent: `slugify(slugify(x)) == slugify(x)` for all `x`.
- `slugify` output, when non-empty, MUST satisfy the account-name regex.
- `default_account_name` MUST never return a name in `existing`.
- Collision suffix MUST start at `-2` (not `-1`).
- Collision suffix MUST scan upward monotonically (no random sampling).
- If `me.organizations` is empty, MUST return `"account"` (and apply collision suffixing).
- Both functions MUST be deterministic — no use of `random`, no clock reads, no env access.

---

## 3. Reused public surface (no signature changes)

These existing public functions keep their signatures and behavior. The frictionless-auth feature only relaxes their *requiredness*, not their shape.

| Function | Change |
|----------|--------|
| `accounts.add(...)` | Existing signature preserved. New optional kwarg `derive_name: bool = False` to opt into `default_account_name`-based naming. New optional kwarg `probe_region_if_missing: bool = False` to opt into `region_probe`-based region detection. Both default to False so the existing call sites are unaffected. |
| `accounts.list()` | Unchanged. |
| `accounts.use(name)` | Unchanged. |
| `accounts.login(name)` | Unchanged for existing semantics (oauth_browser refresh by name). `accounts.login_unified()` is the new entry point that handles the broader flow. |
| `accounts.test(name)` | Unchanged. |

---

## 4. Public namespace impact

`src/mixpanel_headless/__init__.py` re-exports add:

```python
from mixpanel_headless.accounts import (  # existing
    add,
    list,
    use,
    login,
    test,
    # ... existing exports
    login_unified,  # NEW
)
from mixpanel_headless.exceptions import (
    # ... existing exports
    InvalidArgumentError,   # NEW (043 — login_unified flag-combination guard)
    RegionProbeError,       # NEW (043 — region probe)
    RegionProbeNetworkError,# NEW (043 — region probe network-failure subclass)
)
```

The two pure helpers (`region_probe.probe_region` and `naming.*`) live under `_internal/` and are NOT re-exported at the package root. They are still importable for internal callers and tests.

`AccountSummary` (in `mixpanel_headless.types`) gains three optional fields populated by `login_unified()` from the `/me` round-trip:
- `user_email: str | None` — authenticated user email
- `project_id: str | None` — resolved project ID
- `project_name: str | None` — human-readable project name from `/me`

All three default to `None` so existing constructors (e.g. those used by `mp account add` paths that never touched `/me`) keep compiling unchanged.

---

## 5. Exception hierarchy

`RegionProbeError` is added as a subclass of the existing `OAuthError` (which itself subclasses `MixpanelHeadlessError`). `InvalidArgumentError` is added as a subclass of `ConfigError` so the existing `except ConfigError` catch-all keeps working, while the CLI's `handle_errors` decorator dispatches the subclass to a different exit code.

```text
MixpanelHeadlessError
├── ConfigError                 (existing — region mismatch, type mismatch, project not visible)
│   └── InvalidArgumentError    (NEW — flag-combination misuse, exit code 3)
├── OAuthError                  (existing)
│   └── RegionProbeError        (NEW — when no region returns 200)
└── ...
```

`RegionProbeError.to_dict()` includes the `attempts` list so that JSON-formatted error output preserves diagnostic detail. `RegionProbeError.attempts` truncates each probed region's `response.text` at 4 KiB so a misconfigured server returning multi-MB HTML cannot bloat the in-memory exception or downstream serialization.

`InvalidArgumentError` carries the discriminator `violation` (one of `"mutually_exclusive"`, `"no_browser_misuse"`, `"secret_stdin_misuse"`) plus an optional `detected_auth_type` so non-CLI callers can dispatch programmatically without parsing the human-readable message.

---

## 6. Type aliases (no new entries)

All new code uses existing type aliases:
- `Region = Literal["us", "eu", "in"]` — from `_internal/auth/account.py`.
- `AccountType = Literal["service_account", "oauth_browser", "oauth_token"]` — from `_internal/auth/account.py`.
- `ProjectId = str` — from `_internal/auth/account.py`.

No new `Literal` or `TypeAlias` declarations are introduced.
