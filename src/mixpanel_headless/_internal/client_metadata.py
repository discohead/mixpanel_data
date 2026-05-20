"""Client-identification metadata for outbound Mixpanel API requests.

Holds the User-Agent string and ``query_origin`` value that identify
``mixpanel-headless`` traffic. Consumed by
:meth:`MixpanelAPIClient._request_headers` and the Query API request path.
"""

from __future__ import annotations

import sys
from typing import Final, Literal

QUERY_ORIGIN: Final[str] = "mixpanel-headless"
"""Value sent as the ``query_origin`` parameter on Query API calls.

Lets downstream consumers attribute analytics traffic to this library.
"""

_EntryPoint = Literal["lib", "cli"]
_entry_point: _EntryPoint = "lib"


def set_entry_point(value: _EntryPoint) -> None:
    """Record how this process was launched (call once at startup).

    The CLI calls this with ``"cli"`` on import so the User-Agent tag
    reflects interactive vs programmatic use. Library callers leave the
    default ``"lib"``.

    Args:
        value: One of ``"lib"`` or ``"cli"``.

    Example:
        ```python
        from mixpanel_headless._internal.client_metadata import set_entry_point
        set_entry_point("cli")
        ```
    """
    global _entry_point
    _entry_point = value


def get_entry_point() -> _EntryPoint:
    """Return the currently recorded entry point.

    Returns:
        ``"lib"`` (default) or ``"cli"`` once flipped.
    """
    return _entry_point


def get_user_agent() -> str:
    """Build the User-Agent string for outbound requests.

    Format: ``mixpanel-headless/<version> (entry=<lib|cli>; python/<x.y>)``

    Returns:
        The User-Agent header value. Re-read on every call so an
        entry-point change after import is reflected immediately.

    Example:
        ```python
        get_user_agent()
        # "mixpanel-headless/0.1.0 (entry=lib; python/3.11)"
        ```
    """
    # Lazy import: mixpanel_headless/__init__.py defines __version__ after
    # eagerly importing workspace -> api_client -> this module. Top-level
    # import here would deadlock package initialization.
    from mixpanel_headless import __version__

    py = f"{sys.version_info.major}.{sys.version_info.minor}"
    return f"mixpanel-headless/{__version__} (entry={_entry_point}; python/{py})"
