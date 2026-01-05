# Dev Container Setup

This project uses a Dev Container for consistent development environments across different machines.

## Configuration Storage & Syncing

The devcontainer uses Docker volumes for configuration directories to ensure it works on any machine, with automatic syncing from your host if configurations exist:

### Automatic Credential Syncing
- **GitHub CLI config** (`~/.config/gh`): Automatically synced from host if it exists
- **GCloud credentials** (`~/.config/gcloud`): Automatically synced from host if it exists
- **Mixpanel config** (`~/.mp`): Stored in volume (create with `mp auth add` if needed)

When you rebuild the container, your existing GitHub and GCloud authentication from the host will be automatically available inside the container. No manual steps required!

### Manual Authentication (if needed)
If credentials aren't found on your host, you can authenticate inside the container:

```bash
# GitHub CLI
gh auth login

# Mixpanel
mp auth add
```

Note: GCloud is not installed in the devcontainer. If you need gcloud credentials for Vertex AI, authenticate on your host machine first and the credentials will be synced automatically.

## Benefits of This Approach

- **No setup required**: The container works immediately on new machines without creating directories
- **Persistent configuration**: Your settings are preserved across container rebuilds
- **Isolation**: Each project can have its own configuration without affecting your host system
- **Portability**: The same setup works on macOS, Linux, and Windows

## Environment Variables

The dev container will automatically pass through the following environment variables from your host machine if they are set:

- `CLAUDE_CODE_USE_VERTEX`: Enable Vertex AI for Claude Code
- `ANTHROPIC_VERTEX_PROJECT_ID`: Vertex AI project ID
- `CLOUD_ML_REGION`: Cloud ML region
- `BASH_DEFAULT_TIMEOUT_MS`: Default timeout for bash commands

These are particularly useful if you're using Claude Code with Google Cloud Vertex AI. If these variables aren't set on your host machine, they simply won't be defined in the container.

## Troubleshooting

If you encounter mount errors when building the container, ensure you have the latest version of this repository with the updated `.devcontainer/devcontainer.json` that uses volumes instead of bind mounts for optional directories.