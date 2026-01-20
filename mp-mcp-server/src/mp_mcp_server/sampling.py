"""OpenAI sampling handler for MCP server fallback.

This module provides a factory function that creates an OpenAISamplingHandler
configured with the appropriate API key. The handler is used as a fallback
when MCP clients don't support sampling (e.g., Claude Code with Agent SDK).

Credentials are loaded from:
1. Environment variables (OPENAI_API_KEY, OPENAI_ORG_ID)
2. Mixpanel's internal secrets system (mp_secrets) as fallback

Example:
    >>> from mp_mcp_server.sampling import create_sampling_handler
    >>> handler = create_sampling_handler()
    >>> if handler:
    ...     print("OpenAI fallback enabled")
"""

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp.client.sampling import SamplingHandler

logger = logging.getLogger(__name__)

# Default model for sampling operations
# Note: Must use a model that supports max_tokens (the FastMCP OpenAI handler uses this).
# gpt-5 requires max_completion_tokens instead, which FastMCP doesn't support yet.
DEFAULT_MODEL = "gpt-4o"


def _get_openai_credentials() -> tuple[str | None, str | None]:
    """Get OpenAI credentials from environment or mp_secrets.

    Returns:
        Tuple of (api_key, org_id). Either may be None if not configured.
    """
    # First check environment variables (set via ai/get_open_ai_key.sh)
    api_key = os.environ.get("OPENAI_API_KEY")
    org_id = os.environ.get("OPENAI_ORG_ID")

    if api_key:
        logger.debug("Using OpenAI credentials from environment variables")
        return api_key, org_id

    # Fall back to mp_secrets (for production/GCP environments)
    try:
        from analytics import mp_secrets as secrets

        api_key = secrets.get("openai.api-key")
        org_id = secrets.get("openai.org-id")
        if api_key:
            logger.debug("Using OpenAI credentials from mp_secrets")
        return api_key, org_id
    except ImportError:
        logger.debug("mp_secrets not available")
        return None, None


def create_sampling_handler(
    model: str = DEFAULT_MODEL,
) -> "SamplingHandler | None":
    """Create an OpenAI sampling handler if API key is available.

    Attempts to create an OpenAISamplingHandler configured with credentials
    from environment variables or Mixpanel's internal secrets system.
    Returns None if credentials are unavailable.

    Credential sources (in order of precedence):
    1. OPENAI_API_KEY / OPENAI_ORG_ID environment variables
    2. mp_secrets.get("openai.api-key") / mp_secrets.get("openai.org-id")

    Args:
        model: OpenAI model to use for sampling. Defaults to gpt-4o-mini
            for cost-effective operation.

    Returns:
        OpenAISamplingHandler instance if API key is available, None otherwise.

    Example:
        >>> handler = create_sampling_handler()
        >>> if handler:
        ...     print("OpenAI fallback enabled")
        ... else:
        ...     print("No OpenAI key, using graceful degradation")
    """
    api_key, org_id = _get_openai_credentials()

    if not api_key:
        logger.info(
            "OpenAI API key not configured. Sampling fallback disabled. "
            "Set OPENAI_API_KEY env var or run: source ai/get_open_ai_key.sh"
        )
        return None

    try:
        from fastmcp.client.sampling.handlers.openai import OpenAISamplingHandler
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, organization=org_id)
        handler = OpenAISamplingHandler(default_model=model, client=client)

        logger.info(
            f"OpenAI sampling handler configured with model '{model}'. "
            "Will be used as fallback when client doesn't support sampling."
        )
        return handler

    except ImportError:
        logger.warning(
            "openai package not installed. "
            "Install with: pip install mp-mcp-server[openai]"
        )
        return None
    except Exception as e:
        logger.warning(f"Failed to create OpenAI sampling handler: {e}")
        return None
