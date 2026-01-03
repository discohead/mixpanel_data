# Mixpanel Data Plugin - Distribution Guide

This guide explains how to distribute the Mixpanel Data plugin via different methods.

## Table of Contents

1. [Local Development Testing](#local-development-testing)
2. [Distribution Options](#distribution-options)
3. [Recommended: GitHub Direct Distribution](#recommended-github-direct-distribution)
4. [Alternative: Marketplace Distribution](#alternative-marketplace-distribution)
5. [Release Workflow](#release-workflow)

---

## Local Development Testing

For testing during development, use the included development marketplace:

### Setup

```bash
# From your workspace
cd /workspace

# Add the local development marketplace
/plugin marketplace add /workspace/mixpanel-plugin

# Install the plugin
/plugin install mixpanel-data@mixpanel-data-dev

# Restart Claude Code to load the plugin
```

### Verify Installation

```bash
# Check commands are available
/help

# Should show:
# - /mp-auth
# - /mp-fetch
# - /mp-funnel
# - /mp-inspect
# - /mp-query
# - /mp-report
# - /mp-retention

# Check subagents are available
/agents

# Should show:
# - mixpanel-analyst
# - funnel-optimizer
# - retention-specialist
# - jql-expert

# Test the skill
> "What Mixpanel analysis tools are available?"
# The mixpanel-data skill should activate
```

### Iterate During Development

```bash
# After making changes to the plugin:
/plugin uninstall mixpanel-data@mixpanel-data-dev

# Make your changes...

/plugin install mixpanel-data@mixpanel-data-dev

# Restart Claude Code
```

---

## Distribution Options

There are three main ways to distribute your plugin:

### Option 1: Direct GitHub Distribution (Recommended ⭐)

**Best for**: Public plugins, individual projects

**Pros**:
- Simple setup - no separate marketplace repository needed
- Users install directly from your GitHub repo
- Automatic version tracking via git tags
- Easy to maintain

**Cons**:
- One plugin per repository (or use subdirectories)
- Users need to know your GitHub repo URL

### Option 2: Marketplace Distribution

**Best for**: Multiple plugins, plugin collections, organizations

**Pros**:
- Distribute multiple plugins from one marketplace
- Centralized discovery
- Version control per plugin
- Professional presentation

**Cons**:
- Requires separate marketplace repository
- More setup complexity
- Must update marketplace.json for each release

### Option 3: Private/Team Distribution

**Best for**: Internal teams, private plugins

**Pros**:
- Control access via GitHub private repos
- Team-specific configuration
- No public marketplace needed

**Cons**:
- Requires team settings configuration
- Less discoverable

---

## Recommended: GitHub Direct Distribution

This is the simplest and most common approach.

### 1. Repository Structure

Your plugin can live in the main `mixpanel_data` repository:

```
mixpanel_data/                     # Main repo
├── src/                           # Python package code
├── tests/
├── docs/
├── mixpanel-plugin/               # Plugin subdirectory
│   ├── .claude-plugin/
│   │   ├── plugin.json
│   │   └── marketplace.json       # For local dev only
│   ├── commands/
│   ├── agents/
│   ├── skills/
│   └── README.md
├── README.md
└── pyproject.toml
```

### 2. Installation Instructions for Users

Add to your main README:

```markdown
## Claude Code Plugin

Install the Mixpanel Data plugin for Claude Code:

\`\`\`bash
/plugin marketplace add jaredmcfarland/mixpanel_data
/plugin install mixpanel-data
\`\`\`

Then restart Claude Code.
```

### 3. How It Works

When users run:
```bash
/plugin marketplace add jaredmcfarland/mixpanel_data
```

Claude Code:
1. Looks for `.claude-plugin/plugin.json` in the repo root
2. If not found, checks common subdirectories (like `mixpanel-plugin/`)
3. Uses `plugin.json` as the marketplace manifest
4. The repo itself becomes a single-plugin marketplace

### 4. Version Management

Use git tags for versions:

```bash
# Tag a release
git tag v1.0.0
git push origin v1.0.0

# Users install specific version
/plugin install mixpanel-data@1.0.0
```

---

## Alternative: Marketplace Distribution

If you want to create a dedicated marketplace (for multiple plugins in the future):

### 1. Create Marketplace Repository

Create a new repository: `mixpanel-claude-plugins`

Structure:
```
mixpanel-claude-plugins/
├── .claude-plugin/
│   └── marketplace.json           # Marketplace manifest
└── README.md
```

### 2. Use the Production Template

Copy the template from `marketplace-templates/production-marketplace.json`:

```json
{
  "name": "mixpanel-data-marketplace",
  "description": "Official marketplace for Mixpanel Data Claude Code plugins",
  "owner": {
    "name": "Mixpanel Data Team",
    "url": "https://github.com/jaredmcfarland"
  },
  "plugins": [
    {
      "name": "mixpanel-data",
      "description": "Mixpanel analytics data integration for Claude Code",
      "version": "1.0.0",
      "source": {
        "source": "url",
        "url": "https://github.com/jaredmcfarland/mixpanel_data.git",
        "subdirectory": "mixpanel-plugin"
      },
      "author": {
        "name": "Mixpanel Data Team",
        "email": "jared@example.com",
        "url": "https://github.com/jaredmcfarland"
      },
      "keywords": ["mixpanel", "analytics", "data-analysis"]
    }
  ]
}
```

### 3. Installation for Users

```bash
/plugin marketplace add jaredmcfarland/mixpanel-claude-plugins
/plugin install mixpanel-data@mixpanel-data-marketplace
```

### 4. Adding More Plugins Later

Just add them to the `plugins` array in marketplace.json:

```json
{
  "plugins": [
    {
      "name": "mixpanel-data",
      "version": "1.0.0",
      ...
    },
    {
      "name": "mixpanel-reporting",
      "version": "1.0.0",
      ...
    }
  ]
}
```

---

## Release Workflow

Follow this process for each release:

### 1. Prepare the Release

```bash
# Update version in plugin.json
# Update CHANGELOG.md or RELEASE-NOTES.md

# Test locally first
/plugin marketplace add /workspace/mixpanel-plugin
/plugin install mixpanel-data@mixpanel-data-dev
# Test all components...
/plugin uninstall mixpanel-data@mixpanel-data-dev
```

### 2. Commit and Tag

```bash
# Commit changes
git add mixpanel-plugin/.claude-plugin/plugin.json
git add mixpanel-plugin/CHANGELOG.md  # if applicable
git commit -m "Release v1.0.0: Add subagents and enhance analysis capabilities"

# Tag the release
git tag v1.0.0
git push origin main
git push origin v1.0.0
```

### 3. Test Fresh Installation

```bash
# Test from GitHub
/plugin marketplace add jaredmcfarland/mixpanel_data
/plugin install mixpanel-data

# Verify everything works
/help                    # Check commands
/agents                  # Check subagents
> "Test Mixpanel skill"  # Verify skill activation

# Clean up
/plugin uninstall mixpanel-data
```

### 4. Create GitHub Release (Optional)

On GitHub:
1. Go to Releases → Create new release
2. Choose tag: v1.0.0
3. Title: "v1.0.0 - Add Subagents"
4. Description:
   ```markdown
   ## What's New

   - 🤖 Added 4 specialized subagents for autonomous analysis
     - mixpanel-analyst: General-purpose data analyst
     - funnel-optimizer: Conversion funnel specialist
     - retention-specialist: Cohort retention expert
     - jql-expert: Advanced JQL query builder

   ## Installation

   \`\`\`bash
   /plugin marketplace add jaredmcfarland/mixpanel_data
   /plugin install mixpanel-data
   \`\`\`

   ## Full Changelog

   See CHANGELOG.md for complete details.
   ```

### 5. Announce

- Update main README with new features
- Post in relevant communities
- Notify existing users

---

## Semantic Versioning

Follow semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR** (1.0.0 → 2.0.0): Breaking changes
  - Example: Removed a command, changed skill name

- **MINOR** (1.0.0 → 1.1.0): New features, backwards compatible
  - Example: Added subagents, new commands

- **PATCH** (1.0.0 → 1.0.1): Bug fixes, small improvements
  - Example: Fixed command typo, updated documentation

---

## Troubleshooting

### Plugin Not Loading

1. Check directory structure:
   ```bash
   tree mixpanel-plugin/
   # Verify .claude-plugin/ is at root
   # Verify plugin.json exists
   ```

2. Validate JSON:
   ```bash
   cat mixpanel-plugin/.claude-plugin/plugin.json | jq .
   # Should pretty-print without errors
   ```

3. Check Claude Code logs:
   ```bash
   claude --debug
   # Look for plugin loading errors
   ```

### Commands Not Appearing

- Restart Claude Code after installation
- Check commands/ directory has .md files
- Verify frontmatter is valid YAML

### Subagents Not Available

- Restart Claude Code
- Check agents/ directory structure
- Verify each .md file has proper frontmatter with `name` and `description`

### Skill Not Triggering

- Check SKILL.md has proper frontmatter
- Verify description field is specific enough
- Test with explicit mention: "Use the mixpanel-data skill"

---

## Maintenance

### Regular Updates

- Monitor for user issues
- Keep dependencies updated (Python library versions)
- Improve documentation based on feedback
- Add new commands/subagents as needed

### Version Support

- Support at least the last 2 major versions
- Document breaking changes clearly
- Provide migration guides for major updates

---

## Resources

- [Claude Code Plugin Documentation](https://docs.claude.com/en/docs/claude-code/plugins)
- [Plugin Marketplaces Guide](https://docs.claude.com/en/docs/claude-code/plugin-marketplaces)
- [Main Project Documentation](https://jaredmcfarland.github.io/mixpanel_data/)
- [GitHub Repository](https://github.com/jaredmcfarland/mixpanel_data)
