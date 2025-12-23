# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.11
FROM mcr.microsoft.com/devcontainers/python:${PYTHON_VERSION}

ARG CLAUDE_CODE_VERSION=latest

# Install additional system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Shell enhancements
    zsh \
    fzf \
    # Development tools
    jq \
    tree \
    htop \
    nano \
    vim \
    # Build dependencies (for compiled Python packages)
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install just command runner
RUN curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin

# Install Node.js for Claude Code
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Set up command history persistence and Claude config directory
ARG USERNAME=vscode
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
    && mkdir -p /commandhistory \
    && touch /commandhistory/.bash_history \
    && chown -R ${USERNAME}:${USERNAME} /commandhistory \
    && echo "${SNIPPET}" >> /home/${USERNAME}/.bashrc \
    && echo "${SNIPPET}" >> /home/${USERNAME}/.zshrc \
    && mkdir -p /home/${USERNAME}/.claude \
    && chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}/.claude \
    # Alias claude to always skip permissions in devcontainer
    && echo "alias claude='claude --dangerously-skip-permissions'" >> /home/${USERNAME}/.bashrc \
    && echo "alias claude='claude --dangerously-skip-permissions'" >> /home/${USERNAME}/.zshrc

# Install Claude Code and GitHub Copilot CLI to user-owned npm prefix (enables auto-updates)
RUN mkdir -p /home/${USERNAME}/.npm-global \
    && chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}/.npm-global \
    && echo "export NPM_CONFIG_PREFIX=/home/${USERNAME}/.npm-global" >> /home/${USERNAME}/.bashrc \
    && echo "export NPM_CONFIG_PREFIX=/home/${USERNAME}/.npm-global" >> /home/${USERNAME}/.zshrc \
    && echo "export PATH=/home/${USERNAME}/.npm-global/bin:\$PATH" >> /home/${USERNAME}/.bashrc \
    && echo "export PATH=/home/${USERNAME}/.npm-global/bin:\$PATH" >> /home/${USERNAME}/.zshrc

USER ${USERNAME}
ENV NPM_CONFIG_PREFIX=/home/vscode/.npm-global
ENV PATH=/home/vscode/.npm-global/bin:${PATH}
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} @github/copilot
USER root

# Configure uv for the vscode user
ENV UV_COMPILE_BYTECODE=1
ENV UV_PYTHON_DOWNLOADS=never
ENV PATH="/workspace/.venv/bin:${PATH}"

# Set working directory
WORKDIR /workspace
