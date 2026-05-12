# Quickstart: Frictionless Auth

**Feature**: 043-frictionless-auth
**Audience**: New users setting up the CLI for the first time, and existing users who want to add a second account.

This walkthrough exercises every documented user story (P1–P3) in spec.md. Treat it as the smoke-test recipe for verifying the feature works end-to-end before merge.

---

## Story 1 (P1): One-command browser login for first-time users

### 1.1 Brand-new machine, single project

```bash
# Confirm no prior config
ls ~/.mp/ 2>/dev/null   # expected: no such file or directory

# One command. Browser opens. You authenticate. Done.
mp login
```

**Expected stdout** (single line, after the browser flow completes):

```
Logged in as alice@acme.com → acme-corp · Production
```

**Expected stderr** (during the flow):

```
Opening browser to https://mixpanel.com/oauth/authorize?...
Waiting for OAuth callback on http://127.0.0.1:53219/callback ...
Got tokens. Looking up account details ...
Found 1 project. Selected automatically.
```

**Verify**:

```bash
mp account list
# acme-corp  oauth_browser  us  *

mp project show
# id: 3713224
# name: Production
# region: us

mp query segmentation -e Login --from 2025-01-01 --to 2025-01-31
# (returns data)
```

### 1.2 Multi-project, interactive

```bash
mp login
```

**Expected stderr** when 3 projects are accessible across 2 orgs:

```
Found 3 projects across 2 organizations:

  1) Acme · Production       (id 3713224, us)
  2) Acme · Staging          (id 3713225, us)
  3) Acme Labs · Sandbox     (id 4001122, eu)

Which project? [1]: 2
```

User picks `2`. Then:

```
Logged in as alice@acme.com → acme · Staging
```

(stdout, single line; the `acme · Staging` formatting is from the multi-project context — the local account name `acme` is the slug of the chosen org.)

### 1.3 Multi-project, non-interactive (CI / agent path)

```bash
mp login </dev/null
```

**Expected stderr**:

```
ERROR: Multiple projects accessible to this account; no default could be picked.

Accessible projects:
  - 3713224 : Acme · Production (us)
  - 3713225 : Acme · Staging (us)
  - 4001122 : Acme Labs · Sandbox (eu)

Pass --project ID to select one explicitly, or set MP_PROJECT_ID.
```

**Exit code**: 3.

**Recover**:

```bash
mp login --project 3713225 </dev/null
# stdout: Logged in as alice@acme.com → acme · Staging
```

### 1.4 Re-login (refresh tokens, keep project)

```bash
# Initial setup: alice has acme-corp account with default_project=3713224
mp login --name acme-corp
```

**Expected stderr**: refresh-only flow, no project picker shown.

**Expected stdout**:

```
Logged in as alice@acme.com → acme-corp · Production
```

**Verify** the project state did not change:

```bash
mp project show
# id: 3713224  (same as before)
```

**With `--project`** (should be ignored, with a note):

```bash
mp login --name acme-corp --project 3713225
```

**Expected stderr**:

```
note: --project ignored on re-login; use 'mp project use 3713225' to change the active project.
Refreshing tokens for 'acme-corp' ...
```

**Exit code**: 0. `default_project` remains `3713224`.

---

## Story 2 (P2): Region auto-detection for service accounts

### 2.1 Service account with EU data, no `--region` typed

```bash
# alice has an SA whose data lives on eu.mixpanel.com
echo "$ALICE_SA_SECRET" | mp login \
    --service-account \
    --secret-stdin \
    --name acme-prod-sa \
    --project 4001122
```

**Expected stderr**:

```
Probing region us ... ✗ (401 Unauthorized)
Probing region eu ... ✓
Validating /me ...
```

**Expected stdout**:

```
Logged in as svc-alice@acme.com → acme-prod-sa · Production
```

**Verify**:

```bash
mp account show acme-prod-sa | grep region
# region: eu
```

### 2.2 Service account, all regions reject

```bash
echo "wrong-secret" | mp login \
    --service-account \
    --secret-stdin \
    --name oops
```

**Expected stderr**:

```
Probing region us ... ✗ (401 Unauthorized)
Probing region eu ... ✗ (401 Unauthorized)
Probing region in ... ✗ (401 Unauthorized)

ERROR: Credential not valid in any region.

Probe results:
  us: 401 Unauthorized
  eu: 401 Unauthorized
  in: 401 Unauthorized

If you know the region, pass --region {us|eu|in} explicitly to skip the probe.
If your service account is new, verify the username and secret are correct.
```

**Exit code**: 2.

### 2.3 Browser auth with explicit region mismatch

```bash
# alice's projects live on EU, but she passes --region us
mp login --region us
```

User completes the browser flow against the US cluster. After `/me`:

**Expected stderr**:

```
Got tokens. Looking up account details ...

ERROR: Region mismatch.

You authenticated against the us cluster, but project 4001122
(Acme Labs · Sandbox) lives in the eu cluster (eu.mixpanel.com).

Re-run with the correct region:
    mp login --region eu
```

**Exit code**: 1. The orphan placeholder dir under `~/.mp/accounts/.tmp-*/` is cleaned up before the error is raised.

### 2.4 Env-var-only auth (CI), `MP_REGION` still required

```bash
unset MP_REGION
MP_USERNAME=svc MP_SECRET=$ALICE_SA_SECRET MP_PROJECT_ID=4001122 \
    mp query segmentation -e Login --from 2025-01-01
```

**Expected stderr** (from the resolver, NOT from `mp login` — the env-var path bypasses login):

```
ERROR: MP_USERNAME and MP_SECRET are set but MP_REGION is not.

The resolver does not perform region probes (probing only happens at
add-time via 'mp login'). Set MP_REGION=us|eu|in or use 'mp login' to
add a persistent account.
```

**Exit code**: 1.

---

## Story 3 (P2): Service-account project discovery without `--project`

### 3.1 Add SA without `--project`, then list

```bash
echo "$ALICE_SA_SECRET" | mp account add acme-prod-sa \
    --type service_account \
    --username svc-alice@acme.com \
    --secret-stdin \
    --region us
```

**Expected stdout**: confirmation line.

**Verify** the account has no `default_project`:

```bash
mp account show acme-prod-sa | grep default_project
# default_project:
```

### 3.2 List accessible projects through the SA

```bash
mp project list --account acme-prod-sa
```

**Expected output** (table format, default for `list`):

```
ID         NAME                   ORG       REGION
3713224    Production             Acme      us
3713225    Staging                Acme      us
4001122    Sandbox                Acme Labs eu
```

### 3.3 SA missing `user_details` scope

```bash
echo "$LIMITED_SA_SECRET" | mp account add limited-sa \
    --type service_account \
    --username limited@acme.com \
    --secret-stdin \
    --region us
mp project list --account limited-sa
```

**Expected stderr**:

```
ERROR: Service account 'limited-sa' is missing the `user_details` scope.

Re-mint the SA in Mixpanel Settings → Service Accounts with that scope checked,
or pass --project ID explicitly to skip the /me lookup.
```

**Exit code**: 1.

**Workaround**:

```bash
mp project use 3713224 --account limited-sa
mp query segmentation -e Login --from 2025-01-01 --account limited-sa
# (works; SA scope only affects /me, not query endpoints)
```

---

## Story 4 (P3): Auto-derived account names

### 4.1 First account, derived from org

```bash
# alice's org is "Acme Corp"
mp login
```

**Expected stdout**:

```
Logged in as alice@acme.com → acme-corp · Production
```

**Verify**:

```bash
mp account list
# acme-corp  oauth_browser  us  *
```

### 4.2 Second account, different org, name collision

```bash
# bob (different Mixpanel user) also belongs to an "Acme Corp" org
mp login
```

**Expected stdout**:

```
Logged in as bob@acme.com → acme-corp-2 · Production
```

**Verify**:

```bash
mp account list
# acme-corp    oauth_browser  us
# acme-corp-2  oauth_browser  us  *
```

### 4.3 Non-ASCII org name

```bash
# carol's org is "Café Industries"
mp login
```

**Expected stdout**:

```
Logged in as carol@cafe.fr → cafe-industries · Production
```

### 4.4 Multi-org user, interactive prompt

```bash
# diana belongs to "Acme Inc." and "Acme Labs"
mp login
```

**Expected stderr** (after browser completes):

```
Account spans 2 organizations:

  1) Acme Inc.        (id 1234)
  2) Acme Labs        (id 5678)

Which org's name should the local account be slugged from? [1]: 2
```

User picks `2`. Then:

```
Logged in as diana@acme.com → acme-labs · Sandbox
```

### 4.5 Multi-org user, `--name` overrides

```bash
mp login --name personal
```

**Expected stderr**: NO org prompt (--name supplied).

**Expected stdout**:

```
Logged in as diana@acme.com → personal · Sandbox
```

---

## End-to-end smoke test (single command)

For pre-merge verification, this one-liner exercises the full happy path:

```bash
rm -rf ~/.mp && \
mp login && \
mp account list && \
mp project show && \
mp query segmentation -e Login --from 2025-01-01 --to 2025-01-31 -f json | jq '.series | length'
```

Expected outcome: a JSON number printed at the end (the count of series in the segmentation result), with no errors anywhere in the chain.

---

## Backward-compat smoke test

For verifying no regression in existing `mp account add` callers:

```bash
echo "$ALICE_SA_SECRET" | mp account add legacy-sa \
    --type service_account \
    --username svc-alice@acme.com \
    --secret-stdin \
    --region us \
    --project 3713224
mp account use legacy-sa
mp query segmentation -e Login --from 2025-01-01 --to 2025-01-31
```

Expected outcome: account added with all flags exactly as before, query succeeds. Zero behavior change for callers that pass every flag.
