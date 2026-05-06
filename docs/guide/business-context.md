# Business Context

Read and write the markdown documentation that grounds AI assistants in your organization's structure and goals, exposed as a Python API and `mp business-context` CLI group.

!!! info "What is Business Context?"
    Business Context is plain markdown text (up to **50,000 characters per scope**) that you attach to a Mixpanel organization or project. AI assistants read it before answering questions, so they know *what your product does*, *what your events mean*, *which dashboards are canonical*, and *how your team defines key metrics*. See the [official Mixpanel Business Context docs](https://docs.mixpanel.com/docs/business-context) for the broader product picture.

!!! note "Prerequisites"
    Business Context requires **authentication**. Project-level reads work with any account that has project access; project-level writes additionally require `edit_project_info` permission. Org-level operations require org membership (read) plus `edit_project_info` at the org level (write). Service accounts can read/write at the project level for projects they're attached to; for org-level operations or for org-id auto-resolution, an OAuth account (`oauth_browser` or `oauth_token`) is the cleanest path.

## Two scopes

| Scope | Lives at | Shared by |
|---|---|---|
| `organization` | The Mixpanel organization | Every project in the org |
| `project` | A single project | That project only |

`mixpanel_data` exposes both scopes through the same API, gated by a `level: Literal["organization", "project"]` argument.

## Quick reference

=== "Python"

    ```python
    import mixpanel_data as mp

    ws = mp.Workspace()

    # Read
    project_ctx = ws.get_business_context(level="project")
    org_ctx = ws.get_business_context(level="organization")

    # Read both at once (single round-trip via /business-context/chain)
    chain = ws.get_business_context_chain()

    # Write
    ws.set_business_context("# About Acme\n…", level="project")
    ws.set_business_context("# Org-wide context", level="organization")

    # Clear (equivalent to set_business_context(""))
    ws.clear_business_context(level="project")
    ```

=== "CLI"

    ```bash
    # Read
    mp business-context get --level project
    mp business-context get --level organization
    mp business-context chain                       # both at once

    # Write — three input modes
    mp business-context set --level project --content "# About Acme..."
    mp business-context set --level project --file context.md
    cat context.md | mp business-context set --level project

    # Clear
    mp business-context clear --level project
    ```

## Reading context

### Project scope

Project-scope reads use the active session's project ID. If no context has been set, the API returns the empty string — no special "not found" error to handle.

=== "Python"

    ```python
    ctx = ws.get_business_context(level="project")
    print(f"{ctx.character_count} chars")
    if ctx.is_empty:
        print("No project context configured.")
    else:
        print(ctx.content)
    ```

=== "CLI"

    ```bash
    # Pretty-printed JSON (default)
    mp business-context get --level project

    # Just the markdown body via jq
    mp business-context get --level project --jq '.content'

    # Compact rich table
    mp business-context get --level project --format table
    ```

### Organization scope

Organization-scope reads default to the org that owns the active session's project. The org ID is auto-resolved from the cached `/me` response (24-hour TTL). To read context from a different org without switching projects, pass `organization_id` explicitly.

=== "Python"

    ```python
    # Auto-resolve org_id from the active project's organization
    org_ctx = ws.get_business_context(level="organization")
    print(f"org={org_ctx.organization_id}: {org_ctx.character_count} chars")

    # Explicit override (skips the /me lookup)
    other = ws.get_business_context(level="organization", organization_id=42)
    ```

=== "CLI"

    ```bash
    # Auto-resolve from active project
    mp business-context get --level organization

    # Explicit org id
    mp business-context get --level organization --organization-id 42
    ```

If auto-resolution can't determine the org (e.g. the active project isn't in the cached `/me` and the user belongs to multiple orgs), the call raises `WorkspaceScopeError` with `code="ORGANIZATION_AMBIGUOUS"` and lists the accessible org IDs.

### Both scopes in one call

The server exposes a `/business-context/chain` endpoint that returns both org and project context together, scoped to the active project. Use `get_business_context_chain()` (Python) or `mp business-context chain` (CLI) to avoid two round-trips.

=== "Python"

    ```python
    chain = ws.get_business_context_chain()
    print("ORG:    ", chain.organization.content)
    print("PROJECT:", chain.project.content)
    ```

=== "CLI"

    ```bash
    mp business-context chain
    mp business-context chain --jq '.project.content'
    ```

## Writing context

`set_business_context` is **full-replace** semantics — what you pass becomes the entire stored content for that scope. There is no append, no patch, no diff. Pass the empty string to clear, or use `clear_business_context` for clarity.

=== "Python"

    ```python
    new_content = """# Acme Analytics

    ## Product overview

    Acme is a SaaS dashboard for SMBs.

    ## Event taxonomy

    - `signup_completed` — user creates an account
    - `subscription_started` — paid plan begins
    - `feature_X_used` — pattern for feature engagement

    ## Definitions

    - **Active user**: any user with ≥1 event in the last 28 days
    """

    ws.set_business_context(new_content, level="project")
    ws.set_business_context("# Org-wide standards…", level="organization")
    ws.set_business_context("", level="project")  # clear
    ws.clear_business_context(level="project")    # same thing, more explicit
    ```

=== "CLI"

    The `set` command accepts content from three sources, in priority order:

    1. `--content TEXT` — inline markdown (best for short content)
    2. `--file PATH` — read from a file on disk
    3. **stdin** — when no flags are given and stdin is not a TTY

    `--content` and `--file` are mutually exclusive. Stdin is only consulted when neither flag is provided.

    ```bash
    # Inline
    mp business-context set --level project --content "# Quick note"

    # From file (typical for version-controlled context)
    mp business-context set --level project --file ./context.md

    # From stdin (works well in scripts)
    cat ./context.md | mp business-context set --level project

    # Heredoc
    mp business-context set --level project <<'EOF'
    # Acme Analytics

    Updated by deploy job at $(date).
    EOF
    ```

### Validation

`set_business_context` validates `len(content) <= 50_000` **client-side, before** making any HTTP call. Oversize input raises `BusinessContextValidationError` with `details={"length": N, "max": 50_000}` so you fail fast and don't waste a round-trip. The server enforces the same cap and would otherwise return HTTP 400.

=== "Python"

    ```python
    from mixpanel_data import BUSINESS_CONTEXT_MAX_CHARS
    print(BUSINESS_CONTEXT_MAX_CHARS)  # 50000

    try:
        ws.set_business_context("x" * 60_000)
    except mp.BusinessContextValidationError as e:
        print(f"Too long: {e.details['length']} > {e.details['max']}")
    ```

=== "CLI"

    ```bash
    # Oversize content from a file
    mp business-context set --level project --file too_big.md
    # → exits with code 1 (GENERAL_ERROR) and a clear message,
    #   without making a network request
    ```

### Clearing

`clear_business_context()` is a thin convenience over `set_business_context("")`. Use whichever reads better at the call site.

=== "Python"

    ```python
    ws.clear_business_context(level="project")
    ws.clear_business_context(level="organization")
    ```

=== "CLI"

    ```bash
    mp business-context clear --level project
    mp business-context clear --level organization
    ```

## Common workflows

### Version-control project context as a file

Treat `context.md` like any other source file in your repo, and re-apply it as part of deploy:

```bash
# In CI or a deploy hook
mp business-context set --level project --file ./context.md
```

### Bootstrap a new project from the org default

```python
import mixpanel_data as mp

ws = mp.Workspace()
chain = ws.get_business_context_chain()

# Seed the project with the org content (e.g. for a new project that should
# inherit org standards as a starting point)
if chain.project.is_empty and not chain.organization.is_empty:
    ws.set_business_context(chain.organization.content, level="project")
```

### Audit context across many projects

```python
import mixpanel_data as mp

ws = mp.Workspace()
for project in ws.projects():
    ws.use(project=project.id)
    ctx = ws.get_business_context(level="project")
    if ctx.is_empty:
        print(f"⚠️  {project.id} ({project.name}) has no project context")
    else:
        print(f"✅ {project.id} ({project.name}) — {ctx.character_count} chars")
```

## Result types

`get_business_context` and `set_business_context` return [`BusinessContext`](../api/types.md#mixpanel_data.BusinessContext) — a frozen Pydantic model with the markdown content plus the scope-appropriate identifier:

| Field | Project scope | Org scope |
|---|---|---|
| `level` | `"project"` | `"organization"` |
| `content` | markdown body (or `""`) | markdown body (or `""`) |
| `project_id` | active project ID | `None` |
| `organization_id` | `None` | resolved org ID |

Two convenience properties (Python only — not in `model_dump()`):

- `is_empty: bool` — `True` when `content == ""`
- `character_count: int` — `len(content)`; compare against `BUSINESS_CONTEXT_MAX_CHARS`

`get_business_context_chain()` returns [`BusinessContextChain`](../api/types.md#mixpanel_data.BusinessContextChain), which is just `{organization: BusinessContext, project: BusinessContext}`.

## Error handling

| Exception | Raised when |
|---|---|
| [`BusinessContextValidationError`](../api/exceptions.md#mixpanel_data.BusinessContextValidationError) | Client-side: content > 50,000 chars (no HTTP call made) |
| [`QueryError`](../api/exceptions.md#mixpanel_data.QueryError) | Server-side 400 (malformed body, server-side oversize), 403 (missing `edit_project_info`), 404 (org/project not visible) |
| [`AuthenticationError`](../api/exceptions.md#mixpanel_data.AuthenticationError) | 401 — credentials are invalid |
| [`WorkspaceScopeError`](../api/exceptions.md#mixpanel_data.WorkspaceScopeError) | `level="organization"` and the org ID could not be auto-resolved (`code="ORGANIZATION_AMBIGUOUS"`) |
| [`ServerError`](../api/exceptions.md#mixpanel_data.ServerError) | 5xx |

```python
import mixpanel_data as mp

ws = mp.Workspace()
try:
    ws.set_business_context("…", level="organization")
except mp.BusinessContextValidationError as e:
    print(f"Too long ({e.details['length']} chars), max {e.details['max']}")
except mp.WorkspaceScopeError as e:
    print(f"Cannot resolve org: {e.message}")
except mp.QueryError as e:
    print(f"API rejected the write: {e.status_code} {e.message}")
```

## Permissions summary

| Operation | Required permission |
|---|---|
| Project-level read | Project access (read) |
| Project-level write | Project access + `edit_project_info` |
| Org-level read | Org membership |
| Org-level write | Org membership + `edit_project_info` at the org level |

Service accounts attached to a project can read and write that project's context. Org-level writes typically require an OAuth account (`oauth_browser` or `oauth_token`) whose principal has org-level edit permissions. The 50,000-character cap is enforced both client-side (before any HTTP call) and server-side.

## Next steps

- Reference: [Workspace API](../api/workspace.md) for the full method surface.
- Reference: [Result Types — Business Context](../api/types.md#business-context-types) and [Exceptions — Business Context](../api/exceptions.md#business-context-exceptions).
- CLI: [`mp business-context` command reference](../cli/commands.md) (auto-generated from the Typer app).
- Product docs: the [Mixpanel Business Context product page](https://docs.mixpanel.com/docs/business-context) for organization-level rollout guidance.
