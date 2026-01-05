#!/bin/bash
# This script runs on the host machine before the container starts
# It stages credentials for the container to use

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Clean up any previous staging
rm -rf "$SCRIPT_DIR/.gcloud-staging" "$SCRIPT_DIR/.gh-staging"

# Stage gcloud credentials if they exist
if [ -f "$HOME/.config/gcloud/application_default_credentials.json" ]; then
    echo "Staging gcloud credentials for container..."
    mkdir -p "$SCRIPT_DIR/.gcloud-staging"
    cp "$HOME/.config/gcloud/application_default_credentials.json" "$SCRIPT_DIR/.gcloud-staging/"

    # Copy other useful gcloud files if they exist
    [ -f "$HOME/.config/gcloud/active_config" ] && cp "$HOME/.config/gcloud/active_config" "$SCRIPT_DIR/.gcloud-staging/"
    [ -d "$HOME/.config/gcloud/configurations" ] && cp -r "$HOME/.config/gcloud/configurations" "$SCRIPT_DIR/.gcloud-staging/"
    echo "GCloud credentials staged"
fi

# Stage GitHub CLI config if it exists
if [ -f "$HOME/.config/gh/hosts.yml" ]; then
    echo "Staging GitHub CLI config for container..."
    mkdir -p "$SCRIPT_DIR/.gh-staging"
    cp -r "$HOME/.config/gh/"* "$SCRIPT_DIR/.gh-staging/"
    echo "GitHub CLI config staged"
fi
