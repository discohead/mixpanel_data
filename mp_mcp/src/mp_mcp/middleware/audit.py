"""Audit logging middleware for MCP server.

This module provides audit logging middleware that records tool invocations,
timing information, and outcomes for debugging and monitoring.

Example:
    ```python
    from mp_mcp.middleware.audit import create_audit_middleware

    mcp.add_middleware(create_audit_middleware())
    ```
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

import mcp.types as mt
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.tool import ToolResult

# Configure module logger
logger = logging.getLogger("mp_mcp.audit")


@dataclass
class AuditConfig:
    """Configuration for audit logging.

    Attributes:
        log_level: Logging level for audit entries.
        include_params: Whether to include tool parameters in logs.
        include_results: Whether to include result summaries in logs.
        max_param_length: Maximum length of parameter values to log.
        max_result_length: Maximum length of result summaries to log.

    Example:
        ```python
        config = AuditConfig(
            log_level=logging.INFO,
            include_params=True,
            max_param_length=100,
        )
        ```
    """

    log_level: int = logging.INFO
    """Logging level for audit entries."""

    include_params: bool = True
    """Whether to include tool parameters in logs."""

    include_results: bool = False
    """Whether to include result summaries in logs."""

    max_param_length: int = 200
    """Maximum length of parameter values to log."""

    max_result_length: int = 500
    """Maximum length of result summaries to log."""


class AuditMiddleware(Middleware):
    """Audit logging middleware for MCP tool invocations.

    This middleware logs tool calls with timing information and outcomes,
    useful for debugging and monitoring server activity.

    Attributes:
        config: Audit logging configuration.

    Example:
        ```python
        middleware = AuditMiddleware()
        mcp.add_middleware(middleware)
        ```
    """

    def __init__(self, config: AuditConfig | None = None) -> None:
        """Initialize the audit middleware.

        Args:
            config: Audit logging configuration. Uses defaults if not provided.
        """
        self.config = config or AuditConfig()

    def _truncate(self, value: str, max_length: int) -> str:
        """Truncate a string to maximum length.

        Args:
            value: String to truncate.
            max_length: Maximum allowed length.

        Returns:
            Truncated string with ellipsis if needed.
        """
        if len(value) <= max_length:
            return value
        return value[: max_length - 3] + "..."

    def _format_params(self, params: dict[str, Any]) -> str:
        """Format parameters for logging.

        Args:
            params: Tool parameters dictionary.

        Returns:
            Formatted string representation of parameters.
        """
        if not params:
            return "{}"

        formatted_parts: list[str] = []
        for key, value in params.items():
            if key == "name":
                continue  # Skip the tool name
            str_value = str(value)
            truncated = self._truncate(str_value, self.config.max_param_length)
            formatted_parts.append(f"{key}={truncated}")

        return "{" + ", ".join(formatted_parts) + "}"

    def _format_result(self, result: object) -> str:
        """Format result for logging.

        Args:
            result: Tool execution result.

        Returns:
            Formatted string summary of result.
        """
        str_result = str(result)
        return self._truncate(str_result, self.config.max_result_length)

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        """Log tool invocations with timing and outcomes.

        Args:
            context: The middleware context with request information.
            call_next: Function to call the next middleware or tool.

        Returns:
            The result from the tool execution.
        """
        tool_name = context.message.name
        tool_args = context.message.arguments or {}

        # Log the invocation start
        param_str = (
            self._format_params(tool_args)
            if self.config.include_params
            else "(params hidden)"
        )

        logger.log(
            self.config.log_level,
            "Tool invoked: %s %s",
            tool_name,
            param_str,
        )

        start_time = time.perf_counter()
        try:
            result = await call_next(context)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Log successful completion
            result_str = (
                self._format_result(result) if self.config.include_results else ""
            )
            log_msg = f"Tool completed: {tool_name} ({elapsed_ms:.1f}ms)"
            if result_str:
                log_msg += f" -> {result_str}"

            logger.log(self.config.log_level, log_msg)
            return result

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Log failure
            logger.error(
                "Tool failed: %s (%0.1fms) - %s: %s",
                tool_name,
                elapsed_ms,
                type(e).__name__,
                str(e),
            )
            raise


def create_audit_middleware(
    log_level: int = logging.INFO,
    include_params: bool = True,
    include_results: bool = False,
) -> AuditMiddleware:
    """Create a configured audit logging middleware.

    Args:
        log_level: Logging level for audit entries. Default INFO.
        include_params: Whether to include tool parameters. Default True.
        include_results: Whether to include result summaries. Default False.

    Returns:
        A configured AuditMiddleware instance.

    Example:
        ```python
        # Basic audit logging
        middleware = create_audit_middleware()
        mcp.add_middleware(middleware)

        # Verbose logging with results
        middleware = create_audit_middleware(
            log_level=logging.DEBUG,
            include_results=True,
        )
        ```
    """
    return AuditMiddleware(
        config=AuditConfig(
            log_level=log_level,
            include_params=include_params,
            include_results=include_results,
        )
    )
