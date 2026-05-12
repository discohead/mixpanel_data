"""Public ``mp.targets`` namespace.

Thin wrapper around :class:`~mixpanel_headless._internal.config.ConfigManager`
exposing target CRUD and activation. Targets are saved
(account, project, workspace?) triples used as named cursor positions:
``mp.targets.use("ecom")`` writes all three axes to ``[active]`` in a
single config save.

Reference: specs/042-auth-architecture-redesign/contracts/python-api.md §6.
"""

from __future__ import annotations

import builtins

from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless.types import Target


def _config() -> ConfigManager:
    """Return a fresh ConfigManager honoring ``MP_CONFIG_PATH``."""
    return ConfigManager()


def list() -> builtins.list[Target]:  # noqa: A001 — public namespace shadow
    """Return all configured targets sorted by name.

    Returns:
        Sorted list of :class:`Target` records.
    """
    return _config().list_targets()


def add(
    name: str,
    *,
    account: str,
    project: str,
    workspace: int | None = None,
) -> Target:
    """Add a new target block.

    Args:
        name: Target name (block key).
        account: Referenced account name (must exist).
        project: Project ID (digit string).
        workspace: Optional workspace ID.

    Returns:
        The constructed :class:`Target`.

    Raises:
        ConfigError: Duplicate name, missing account, or validation failure.
    """
    return _config().add_target(
        name, account=account, project=project, workspace=workspace
    )


def remove(name: str) -> None:
    """Remove a target block.

    Args:
        name: Target to remove.

    Raises:
        ConfigError: Target does not exist.
    """
    _config().remove_target(name)


def use(name: str) -> None:
    """Apply the target — write all three axes to ``[active]`` atomically.

    Args:
        name: Target to apply.

    Raises:
        ConfigError: Target does not exist OR its referenced account is gone.
    """
    _config().apply_target(name)


def show(name: str) -> Target:
    """Return the named :class:`Target`.

    Args:
        name: Target name.

    Returns:
        The Target record.

    Raises:
        ConfigError: Target does not exist.
    """
    return _config().get_target(name)


__all__ = ["add", "list", "remove", "show", "use"]
