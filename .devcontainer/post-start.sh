#!/bin/bash
# This script runs inside the container on every start
# It syncs staged credentials if they exist

# Sync gcloud credentials if staged
if [ -d "/workspace/.devcontainer/.gcloud-staging" ] && [ -f "/workspace/.devcontainer/.gcloud-staging/application_default_credentials.json" ]; then
    echo "Syncing gcloud credentials into container..."
    # Fix ownership of volume (created as root by Docker)
    sudo chown -R vscode:vscode /home/vscode/.config/gcloud 2>/dev/null || true
    mkdir -p /home/vscode/.config/gcloud
    cp -r "/workspace/.devcontainer/.gcloud-staging/"* /home/vscode/.config/gcloud/
    rm -rf "/workspace/.devcontainer/.gcloud-staging"
    echo "GCloud credentials synced"
fi

# Sync GitHub CLI config if staged
if [ -d "/workspace/.devcontainer/.gh-staging" ] && [ -f "/workspace/.devcontainer/.gh-staging/hosts.yml" ]; then
    echo "Syncing GitHub CLI config into container..."
    # Fix ownership of volume (created as root by Docker)
    sudo chown -R vscode:vscode /home/vscode/.config/gh 2>/dev/null || true
    mkdir -p /home/vscode/.config/gh
    cp -r "/workspace/.devcontainer/.gh-staging/"* /home/vscode/.config/gh/
    rm -rf "/workspace/.devcontainer/.gh-staging"
    echo "GitHub CLI config synced"
fi