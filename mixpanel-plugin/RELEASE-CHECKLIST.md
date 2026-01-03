# Release Checklist

Use this checklist for each plugin release.

## Pre-Release

- [ ] Update version in `.claude-plugin/plugin.json`
- [ ] Update CHANGELOG.md with changes
- [ ] Update README.md if needed (new features, installation steps)
- [ ] Test all components locally:
  ```bash
  /plugin marketplace add /workspace/mixpanel-plugin
  /plugin install mixpanel-data@mixpanel-data-dev
  ```
- [ ] Verify commands work: `/mp-auth`, `/mp-fetch`, `/mp-query`, etc.
- [ ] Verify subagents available: `/agents` (check all 4 agents)
- [ ] Verify skill triggers: Ask "What Mixpanel tools are available?"
- [ ] Run any tests for the Python library (`just check`)
- [ ] Review documentation for accuracy
- [ ] Uninstall test version: `/plugin uninstall mixpanel-data@mixpanel-data-dev`

## Release

- [ ] Commit all changes:
  ```bash
  git add mixpanel-plugin/
  git commit -m "Release vX.Y.Z: [Brief description]"
  ```
- [ ] Create and push git tag:
  ```bash
  git tag vX.Y.Z
  git push origin main
  git push origin vX.Y.Z
  ```
- [ ] Create GitHub Release (optional but recommended):
  - Go to GitHub → Releases → New Release
  - Choose tag: vX.Y.Z
  - Add release notes
  - Publish

## Post-Release Testing

- [ ] Test fresh installation from GitHub:
  ```bash
  /plugin marketplace add jaredmcfarland/mixpanel_data
  /plugin install mixpanel-data
  ```
- [ ] Restart Claude Code
- [ ] Verify all components loaded correctly
- [ ] Test at least one workflow end-to-end
- [ ] Check for any errors in Claude Code logs

## Announcement

- [ ] Update main project README if needed
- [ ] Announce in relevant channels (Discord, Twitter, etc.)
- [ ] Respond to any immediate feedback or issues

## Version Numbers

Follow semantic versioning:

- **PATCH** (X.Y.Z → X.Y.Z+1): Bug fixes, documentation updates
  - Example: 1.0.0 → 1.0.1

- **MINOR** (X.Y.Z → X.Y+1.0): New features, backwards compatible
  - Example: 1.0.0 → 1.1.0
  - Added subagents ← This would be 1.0.0 → 1.1.0

- **MAJOR** (X.Y.Z → X+1.0.0): Breaking changes
  - Example: 1.2.3 → 2.0.0
  - Removed/renamed commands, changed skill name

## Rollback Plan

If critical issues found after release:

1. Document the issue
2. Decide: Hot fix or rollback?
3. If rollback:
   ```bash
   # Users can install previous version
   /plugin install mixpanel-data@X.Y.Z-previous
   ```
4. Fix the issue
5. Release new patch version
