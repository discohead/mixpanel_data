# Frictionless Auth: `mp login` and `/me`-Driven Discovery

**Status**: Design draft
**Created**: 2026-05-06
**Author**: Jared McFarland
**Closes**: AIE-114, AIE-115, AIE-116, AIE-117
**Source feedback**: [Santi's thread in #ai-engine-feedback](https://mixpanel.slack.com/archives/C0AUQGGCLRM/p1777252029970359?thread_ts=1777252012.509189&cid=C0AUQGGCLRM)

---

## Problem

Adding a Mixpanel account today requires the user to know — and type — facts the API can already tell us. To run `mp account add personal --type oauth_browser --region us --project 3713224`, you must:

1. Know the region your data lives in.
2. Know your project ID (a number that doesn't appear in the URL bar).
3. Invent a local alias.
4. Run a second command (`mp account login`) to actually authenticate.

Santi summarized: *"my ideal auth experience would be: type `mp login`, authenticate in the browser, and everything is configured automatically."*

The four Linear tickets break this into three discovery improvements (114/115/116) plus an umbrella command (117) that orchestrates them.

## What `/me` actually returns

Verified against `analytics/webapp/app_api/me/views.py` and `me_resp.schema.json`:

- **Auth-method agnostic.** `decorators.py:107` (`auth_required`) supports Session, Bearer (OAuth), and Basic (service account). The `/me` view requires the `user_details` scope; nothing else.
- **Per-project**: `name`, `domain`, `organization_id`, `timezone`, `type`, `has_workspaces`, `permissions`, `role`.
- **Per-org**: `id`, `name`, `permissions`, `role`.
- **Per-workspace**: `id`, `name`, `project_id`, `is_default`, `is_global`, ...
- **Per-user**: `user_id`, `user_email`, `user_name`.

The `domain` field is populated by `webapp/project/utils.py::get_domain_for_cluster_id` and is one of:

| `domain` value      | Region |
|---------------------|--------|
| `mixpanel.com`      | `us`   |
| `eu.mixpanel.com`   | `eu`   |
| `in.mixpanel.com`   | `in`   |
| `""` (flag off)     | treat as `us` |

## Key constraints surfaced by the audit

1. **A single credential is bound to one cluster.** OAuth bearers and SA secrets only authenticate against one region's API. A Mixpanel *user* may have projects spanning regions, but each `Account` record represents one credential against one cluster.
2. **Region must be picked before the first request.** The base URL lookup in `MixpanelAPIClient` is region-keyed. The OAuth PKCE authorize URL is also region-scoped, so OAuth login must commit to a region before launching the browser.
3. **The resolver is pure-functional.** `auth/resolver.py` must not perform network I/O, so it cannot probe `/me` to discover region. Discovery has to happen at *add-time* (in `mp login` / `mp account add`), not at *resolve-time* (in `Workspace()` construction).
4. **One SA can address many projects.** SA scope is org-wide (subject to project-level permissions). A single account record + `mp project use ID` is the right model for multi-project SA usage. We don't create one account per project.

## Design

### Region detection (AIE-114)

- **OAuth browser**: PKCE flow uses `--region` (default `us`). After the callback, `/me` is hit and the project's `domain` is recorded. If the user-chosen project's domain disagrees with the auth region, raise a `ConfigError` directing them to re-run `mp login --region <domain-region>`.
- **Service account**: probe `us` → `eu` → `in` against `/me` until one returns 200. First success wins; failures fall through. Three requests max, almost always one. Cache the resolved region on the `Account` record.
- **Env-var auth (CI)**: `MP_REGION` stays required for `MP_USERNAME`+`MP_SECRET` and `MP_OAUTH_TOKEN` setups. CI/agents want determinism; probing across three clusters from a synthesized env account would cost up to 2 wasted RTTs per cold session. The resolver remains pure-functional.
- **Storage**: `region` stays a required field on `Account` (it gates base URL lookup on every request). Just stop *asking* for it at add-time. `mp account update NAME --region X` keeps working as the manual escape hatch.

**Backward compat**: existing config files keep working unchanged. `region` is still serialized and round-trips through TOML.

### Service-account project listing (AIE-115)

`mp project list` already works against `/me` via `_open_account_scoped_workspace()` (project.py:54-95) using a placeholder project ID when none is configured. The block is account-type agnostic — once we stop requiring `--project` at add-time for SAs, the existing code path works.

**Scope handling**: `MeService.fetch()` already maps 403 → `ConfigError("lacks /me permission")`. We extend the message for SAs to name the missing scope explicitly: *"Service account 'X' is missing the `user_details` scope. Re-mint the SA in Mixpanel Settings → Service Accounts with that scope checked, or specify --project ID explicitly."*

**Multi-project SAs**: one account record, project switched via `mp project use ID`. No special handling. The /me list shows all accessible projects.

### Account name defaults (AIE-116)

Default name is `slugify(org.name)` of the first org returned by `/me`. Suffix `-2`, `-3`, ... on collision (`mp account list` lookup against existing names).

```python
import re
import unicodedata

_SLUG_MAX_LEN = 32  # leaves headroom under _AccountBase.name's 64-char ceiling


def slugify(value: str | None) -> str:
    """Reduce an org name to the [a-z0-9_-]{1,32} subset accepted by Account.name.

    Rules (applied in order):
        1. Coerce None/empty to "".
        2. NFKD-normalize and ASCII-fold (drops accents: "Café" -> "cafe").
        3. Lowercase.
        4. Replace any run of non-[a-z0-9] characters with a single "-".
        5. Strip leading/trailing "-".
        6. Truncate to 32 chars; strip trailing "-" left by the truncation.

    Returns the slug, or "" if no characters survived. Callers must handle
    the empty-string fallback (typically `org-{org_id}`).
    """
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if len(slug) > _SLUG_MAX_LEN:
        slug = slug[:_SLUG_MAX_LEN].rstrip("-")
    return slug


def default_account_name(me: MeResponse, existing: set[str]) -> str:
    """Pick a default account name from /me, suffixing on collision."""
    if not me.organizations:
        base = "account"
    else:
        first_org_id, first_org = next(iter(me.organizations.items()))
        base = slugify(first_org.name) or f"org-{first_org_id}"
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"
```

Examples:

| Input                | Output           |
|----------------------|------------------|
| `"Acme Corp"`        | `acme-corp`      |
| `"ACME, Inc."`       | `acme-inc`       |
| `"Café Industries"`  | `cafe-industries`|
| `"  Acme  &  Sons "` | `acme-sons`      |
| `"1Password"`        | `1password`      |
| `"---"`              | `""` (caller falls back to `org-{org_id}`) |
| 50-char org name     | first 32 chars, trailing `-` stripped |

Output always satisfies `_AccountBase.name`'s `^[a-zA-Z0-9_-]+$` constraint (it's the lowercase subset). The 32-char ceiling leaves room for the `-NN` collision suffix without breaching the 64-char wall.

**Multi-org**: if `len(me.organizations) > 1` and the user didn't pass `--name`, prompt interactively with the list. In `--no-interactive` mode (or stdin-not-a-TTY), fail with the org list and ask for `--name` or `--org`.

**Override**: `mp login --name foo` always wins; `mp account add NAME ...` keeps the explicit-name positional arg unchanged.

### `mp login` — the umbrella command (AIE-117)

```
mp login [--region us|eu|in] [--service-account] [--name NAME] [--project ID]
         [--no-browser] [--token-env NAME]
```

**Auth-type detection priority** (first match wins):
1. `--service-account` flag
2. `--token-env NAME` flag → `oauth_token`
3. `MP_USERNAME` + `MP_SECRET` env both set → `service_account`
4. `MP_OAUTH_TOKEN` env set → `oauth_token`
5. Default → `oauth_browser`

**Flow** (oauth_browser):
1. Run PKCE against `--region` (default `us`). Identical to today's `OAuthFlow.login`.
2. Persist tokens to `~/.mp/accounts/{tmp}/tokens.json` under a placeholder name.
3. Hit `/me`. Pick project per the [project-selection priority](#project-selection-priority) below.
4. Cross-check project's `domain` against auth region. Mismatch → unwind, error.
5. Compute name (`--name` > `slugify(org.name)` > collision suffix). Rename token directory.
6. Write `[accounts.NAME]` and promote to `[active].account` (existing add+activate flow).
7. Print `Logged in as {user_email} → {account_name} · {project_name}`.

**Flow** (service_account):
1. Collect `username` + `secret` from env / `--secret-stdin` / interactive `getpass`.
2. Probe `us` → `eu` → `in` until `/me` returns 200. First success → region.
3. Same project / name / persist steps as above.
4. On 403, surface the scope-hint error.

**Flow** (oauth_token):
1. Read token from env (`--token-env NAME` or `MP_OAUTH_TOKEN`).
2. Probe regions same as SA.
3. Same project / name / persist.

#### Project-selection priority

After `/me` returns, pick the project in this order (first match wins):

1. **`--project ID`** flag → must appear in `me.projects`; otherwise raise `ConfigError("Project ID NNN not visible to this account; accessible projects: ...")`.
2. **`MP_PROJECT_ID`** env var → same validation as `--project`. The env value is treated as a soft default — if it doesn't appear in `/me`, fall through to step 3 with a one-line warning to stderr (rather than failing). Rationale: `MP_PROJECT_ID` is commonly inherited from a different shell context (CI matrix, dotenv from a sibling repo) and silently failing the login flow over a stale env var would be hostile.
3. **Exactly one project** in `me.projects` → auto-pick.
4. **Multiple projects** → interactive prompt if stdin is a TTY, otherwise fail with the project list and instruct the user to pass `--project ID` or set `MP_PROJECT_ID`.

#### Interactive project prompt

When step 4 prompts, render a numbered list sorted alphabetically by project name. The default is `[1]` (the first project). Empty input accepts the default. Invalid input re-prompts up to three times before aborting.

```
Found 3 projects across 2 organizations:

  1) Acme · Production       (id 3713224, us)
  2) Acme · Staging          (id 3713225, us)
  3) Acme Labs · Sandbox     (id 4001122, eu)

Which project? [1]: _
```

Format details:
- `<org_name> · <project_name>` keeps the org context visible when a user has projects across multiple orgs. Single-org runs render as just `<project_name>`.
- Project ID and region are right-padded so the columns line up (`{:<MAX_ORG_LEN}` / `{:<MAX_PROJ_LEN}`).
- The region marker uses the project's `domain` field, mapped via the same table in §[What `/me` actually returns](#what-me-actually-returns).
- Re-prompts say `Enter a number between 1 and N: `; the third invalid response raises `ConfigError("Could not pick a project after 3 attempts.")` rather than looping forever.

#### Idempotency for re-login
- If `--name` matches an existing account: refresh tokens (oauth_browser only) and **leave `default_project` alone**. The user explicitly asked to re-authenticate, not to rebuild the account. Project changes go through `mp project use`. The project-selection priority above is *skipped entirely* for re-login — passing `--project` or having `MP_PROJECT_ID` set on a re-login attempt has no effect on the stored `default_project`. Print a one-line note to stderr if either is set so the user isn't surprised (`note: --project ignored on re-login; use 'mp project use ID' to change`).
- For SA / oauth_token re-login: equivalent to `mp account update` for the credential fields; project untouched.

### `mp account add` — kept as the power-user path

`mp account add` stays. It remains the explicit, scriptable, all-flags-required path. `mp login` is the conversational path. Both share the same `accounts.add()` Python API; the divergence is only in *what defaults are computed automatically* before calling it.

### Resolver impact

Minimal. The resolver still consults `account.region` and `account.default_project`. Region is now populated by `mp login`'s probe (or supplied by hand for `mp account add` / env-var setups) instead of being typed in every time. No changes to priority order or per-axis chains.

## Affected files

| File | Change |
|------|--------|
| `cli/commands/login.py` (new) | Implements `mp login` Typer command |
| `cli/main.py` | Register `login` command at top level |
| `accounts.py` | Add `accounts.login_unified(...)` Python API mirroring CLI |
| `_internal/auth/region_probe.py` (new) | `probe_region(credential) -> Region` — sequential `/me` probe across us/eu/in |
| `_internal/auth/naming.py` (new) | `slugify`, `default_account_name(me, existing)` |
| `_internal/me.py` | No schema changes; `MeProjectInfo.domain` already there |
| `cli/commands/account.py` | `--region` becomes optional in `add_account`; mention in help that `mp login` is the recommended path |
| `accounts.py::add` | `region` becomes `Region | None`; when `None`, raise informative error directing to `mp login` (we don't probe inside `add` — that's `login`'s job) |

LoC budget: estimated +400 LoC for the four new components. Will check against `tests/unit/test_loc_budget.py` ceiling (~6,500 across 20 files).

## Sequencing

Ship as four PRs in order. Each is independently shippable and the umbrella `mp login` PR depends on the three below it.

1. **AIE-115 first** — extends `mp project list` and `mp account add` to make `--project` optional for SAs (it's already optional for `oauth_browser`). Smallest change, validates that SA `/me` works end-to-end.
2. **AIE-114 next** — region probe utility lands as a library function; `mp account add` accepts `--region` as optional and probes when omitted. Existing configs untouched.
3. **AIE-116 next** — naming utility lands; `mp account add` accepts `NAME` as optional positional, defaults via `default_account_name()`.
4. **AIE-117 last** — `mp login` lands as a thin orchestrator. Re-uses everything from the three prior PRs.

Each PR is mergeable on its own and improves the existing `mp account add` / `mp account login` ergonomics. The umbrella PR is the polish layer.

## Migration / backward compat

- Existing `~/.mp/config.toml` files are unchanged. `region` is still required on disk; what changes is that we don't *prompt* for it.
- `mp account add NAME --type X --region Y --project Z` keeps working identically.
- New optional behavior is opt-in: leave `--region` off and we probe; leave `NAME` off and we default; leave `--project` off and we list.
- `MP_REGION` stays required for env-only auth (CI / agents). Documented in CLAUDE.md and the env-var table.

## Risks / open questions

1. **Region probe latency on EU/IN users**: a US-default probe means EU/IN service-account users pay ~2 extra round-trips on first `mp login`. Acceptable: it's a one-time cost cached forever after. Alternative: parallel probe across all three regions (3x server load for the common us case). Decision: sequential, US-first.
2. **Slug collisions across orgs with the same name**: handled by `-2` suffix. The collision space is the user's local config, not global.
3. **Org with empty name**: fallback to `org-{org_id}` then suffix as needed. Defensive; unlikely in practice.
4. **`/me` returning zero projects**: legitimate edge case (user is org-only with no project access). `mp login` succeeds with `default_project=None`; first query against the workspace surfaces the standard "no project configured" error chain.
5. **Re-login with `--region` different from existing account's region**: refuse with a clear error. Region change requires `mp account remove NAME && mp login --region X` (or `mp account update NAME --region X` if the user really knows what they're doing).
6. **OAuth scope for `/me`**: PKCE flow already requests the scopes needed for `/me`; SA scope is the user's responsibility (we surface the hint on 403). No new scope work.

## Success criteria

A user with no prior config can run `mp login` and a `mp query segmentation -e Login --from 2025-01-01` without typing a region, project ID, or local alias. The flow is the same shape for OAuth and service accounts; the only divergence is *how* the credential is collected (browser vs. env / prompt).

The four Linear tickets close as one shippable feature, with the three sibling PRs each closing on merge and AIE-117 closing when `mp login` ships.
