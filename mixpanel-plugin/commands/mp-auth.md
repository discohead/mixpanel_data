---
description: Interactive wizard for Mixpanel authentication and account management
allowed-tools: Bash(mp auth:*)
argument-hint: [account-name] [list|switch|test]
---

# Mixpanel Authentication

Manage Mixpanel credentials and account configuration.

## Operation Selection

Determine operation based on arguments:
- **No arguments or account name only ($1)**: Setup new account (default workflow)
- **$1 = "list"**: List all configured accounts
- **$1 = "switch"**: Switch default account
- **$1 = "test"**: Test credentials
- **$2 = "list", "switch", or "test"**: Execute that operation

## Current Configuration Status

Check existing accounts:

```bash
!$(mp auth list --format table 2>&1)
```

---

## Operation 1: Setup New Account (Default)

Guide the user through configuring Mixpanel credentials interactively.

### 1. Determine Account Name

**Account name**:
- Use `$1` if provided as argument (and it's not "list", "switch", or "test")
- Otherwise, ask user for a name like "production", "staging", or "default"
- This helps manage multiple Mixpanel projects

### 2. Collect Non-Sensitive Credentials

Use AskUserQuestion to collect:
- **Username**: Mixpanel service account username (e.g., name.xxxxxx.mp-service-account)
- **Project ID**: Numeric project ID from Mixpanel project settings
- **Region**: Data residency region (us, eu, or in)

**Where to find these:**
- Mixpanel Project Settings → Service Accounts
- Username and Project ID are shown there

### 3. Validate Inputs

Before proceeding, validate:
- Project ID is numeric
- Region is one of: `us`, `eu`, `in`
- Username follows the pattern `*.mp-service-account`

### 4. Complete Setup Securely

**IMPORTANT: Do NOT ask the user for their secret in this conversation.**

After collecting non-sensitive credentials, provide instructions for the user to complete setup in their own terminal:

> To complete the setup securely, please run this command in your terminal:
>
> ```bash
> mp auth add <account-name> -u <username> -p <project-id> -r <region> --interactive
> ```
>
> This will prompt you for your secret securely without it appearing in this conversation or being sent to Anthropic's servers.
>
> **Alternative**: If you prefer to use an environment variable:
>
> ```bash
> export MP_SECRET="your-secret-here"
> mp auth add <account-name> -u <username> -p <project-id> -r <region>
> unset MP_SECRET
> ```
>
> Or in a single command:
>
> ```bash
> MP_SECRET="your-secret" mp auth add <account-name> -u <username> -p <project-id> -r <region>
> ```

### 5. Verify Setup

After the user completes the setup in their terminal, verify the account was added:

```bash
!$(mp auth list --format table)
```

### 6. Test Connection

Test that the credentials work:

```bash
!$(mp auth test <account-name>)
```

### 7. Set as Default (Optional)

Ask if they want to set this as the default account:

```bash
!$(mp auth switch <account-name>)
```

### Success Message

Once complete, show:
- ✅ Credentials configured successfully
- Account name and project ID
- Suggest next steps:
  - Run `/mp-inspect` to explore your Mixpanel schema
  - Run `/mp-fetch` to start fetching data
  - Check the mixpanel-data skill for complete workflow guidance

---

## Operation 2: List Accounts

Show all configured Mixpanel accounts with their details.

```bash
!$(mp auth list --format table)
```

The output shows:
- Account name
- Username
- Project ID
- Region
- Default account (marked with *)

### Next Steps

- **Switch to different account**: Run `/mp-auth switch`
- **Test account credentials**: Run `/mp-auth test`
- **Setup new account**: Run `/mp-auth` with no arguments

---

## Operation 3: Switch Default Account

Change which account is used by default when no `--account` flag is specified.

### 1. Show Available Accounts

```bash
!$(mp auth list --format table)
```

### 2. Determine Target Account

- Use `$2` if provided (when called as `/mp-auth switch <account-name>`)
- Otherwise, ask user which account to switch to

### 3. Execute Switch

```bash
!$(mp auth switch <account-name>)
```

### 4. Verify Switch

Confirm the default was changed:

```bash
!$(mp auth list --format table)
```

The new default account should be marked with *.

### Success Message

- ✅ Default account switched to `<account-name>`
- Ready to use with all `mp` commands

---

## Operation 4: Test Credentials

Validate that account credentials work and can access the Mixpanel API.

### 1. Determine Account to Test

- Use `$2` if provided (when called as `/mp-auth test <account-name>`)
- Use default account if no name specified
- Ask user if multiple accounts exist and no default set

### 2. Execute Test

```bash
!$(mp auth test <account-name>)
```

### 3. Interpret Results

**Success:**
- ✅ Credentials valid
- Shows account details (name, project ID, region)
- Shows event count if data accessible

**Failure:**
- Check error message for details:
  - **Authentication error**: Credentials incorrect or expired
  - **Network error**: Connectivity issues
  - **Permission error**: Service account lacks required permissions
  - **API error**: Mixpanel service issues

### Troubleshooting

If test fails:
- Verify credentials are correct in Mixpanel project settings
- Check network connectivity
- Ensure service account has appropriate permissions
- Try reconfiguring: Run `/mp-auth` to setup new credentials
- Review error message for specific issues

---

## General Troubleshooting

### No Accounts Configured

If `mp auth list` shows no accounts:
- Run `/mp-auth` (default operation) to setup your first account

### Multiple Accounts, No Default

If you have accounts but none marked as default:
- Run `/mp-auth switch <account-name>` to set one

### Credentials Stopped Working

If `mp auth test` suddenly fails:
- Service account secret may have been rotated
- Service account may have been disabled
- Reconfigure: Run `/mp-auth` to add updated credentials
