#!/bin/bash
set -euo pipefail
# This script runs inside the container on every start
# It syncs staged credentials if they exist

# Ensure staging directories are cleaned up even on failure
trap 'rm -rf "/workspace/.devcontainer/.gcloud-staging" "/workspace/.devcontainer/.gh-staging"' EXIT

# Sync gcloud credentials if staged
if [ -d "/workspace/.devcontainer/.gcloud-staging" ] && [ -f "/workspace/.devcontainer/.gcloud-staging/application_default_credentials.json" ]; then
    echo "Syncing gcloud credentials into container..."
    mkdir -p /home/vscode/.config/gcloud
    # Fix ownership of volume (may have been created as root by Docker)
    sudo chown -R vscode:vscode /home/vscode/.config/gcloud 2>/dev/null || true
    cp -a "/workspace/.devcontainer/.gcloud-staging/." /home/vscode/.config/gcloud/
    echo "GCloud credentials synced"
fi

# Sync GitHub CLI config if staged
if [ -d "/workspace/.devcontainer/.gh-staging" ] && [ -f "/workspace/.devcontainer/.gh-staging/hosts.yml" ]; then
    echo "Syncing GitHub CLI config into container..."
    mkdir -p /home/vscode/.config/gh
    # Fix ownership of volume (may have been created as root by Docker)
    sudo chown -R vscode:vscode /home/vscode/.config/gh 2>/dev/null || true
    cp -a "/workspace/.devcontainer/.gh-staging/." /home/vscode/.config/gh/
    echo "GitHub CLI config synced"
fi