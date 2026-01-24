"""Tests for audit logging middleware.

These tests verify the AuditMiddleware logs tool invocations correctly.
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from mp_mcp.middleware.audit import (
    AuditConfig,
    AuditMiddleware,
    create_audit_middleware,
)


class TestAuditConfig:
    """Tests for AuditConfig dataclass."""

    def test_default_values(self) -> None:
        """AuditConfig should have sensible defaults."""
        config = AuditConfig()
        assert config.log_level == logging.INFO
        assert config.include_params is True
        assert config.include_results is False
        assert config.max_param_length == 200
        assert config.max_result_length == 500

    def test_custom_values(self) -> None:
        """AuditConfig should accept custom values."""
        config = AuditConfig(
            log_level=logging.DEBUG,
            include_params=False,
            include_results=True,
            max_param_length=100,
            max_result_length=200,
        )
        assert config.log_level == logging.DEBUG
        assert config.include_params is False
        assert config.include_results is True
        assert config.max_param_length == 100
        assert config.max_result_length == 200


class TestAuditMiddleware:
    """Tests for AuditMiddleware class."""

    def test_init_with_default_config(self) -> None:
        """AuditMiddleware should use default config when none provided."""
        middleware = AuditMiddleware()
        assert middleware.config is not None
        assert middleware.config.log_level == logging.INFO

    def test_init_with_custom_config(self) -> None:
        """AuditMiddleware should use provided config."""
        config = AuditConfig(log_level=logging.DEBUG)
        middleware = AuditMiddleware(config=config)
        assert middleware.config.log_level == logging.DEBUG

    def test_truncate_short_string(self) -> None:
        """_truncate should not modify strings under max length."""
        middleware = AuditMiddleware()
        result = middleware._truncate("short", 100)
        assert result == "short"

    def test_truncate_long_string(self) -> None:
        """_truncate should truncate strings over max length."""
        middleware = AuditMiddleware()
        long_string = "a" * 100
        result = middleware._truncate(long_string, 20)
        assert len(result) == 20
        assert result.endswith("...")
        assert result == "a" * 17 + "..."

    def test_truncate_exact_length(self) -> None:
        """_truncate should not modify strings at exact max length."""
        middleware = AuditMiddleware()
        exact_string = "a" * 50
        result = middleware._truncate(exact_string, 50)
        assert result == exact_string

    def test_format_params_empty(self) -> None:
        """_format_params should return empty braces for empty dict."""
        middleware = AuditMiddleware()
        result = middleware._format_params({})
        assert result == "{}"

    def test_format_params_with_values(self) -> None:
        """_format_params should format parameters correctly."""
        middleware = AuditMiddleware()
        params = {"event": "signup", "from_date": "2024-01-01"}
        result = middleware._format_params(params)
        assert "event=signup" in result
        assert "from_date=2024-01-01" in result

    def test_format_params_skips_name(self) -> None:
        """_format_params should skip the 'name' parameter."""
        middleware = AuditMiddleware()
        params = {"name": "my_tool", "event": "signup"}
        result = middleware._format_params(params)
        assert "name=" not in result
        assert "event=signup" in result

    def test_format_params_truncates_long_values(self) -> None:
        """_format_params should truncate long parameter values."""
        config = AuditConfig(max_param_length=10)
        middleware = AuditMiddleware(config=config)
        params = {"query": "a" * 100}
        result = middleware._format_params(params)
        assert "..." in result

    def test_format_result(self) -> None:
        """_format_result should convert result to truncated string."""
        middleware = AuditMiddleware()
        result = middleware._format_result({"data": "value"})
        assert "data" in result

    def test_format_result_truncates(self) -> None:
        """_format_result should truncate long results."""
        config = AuditConfig(max_result_length=20)
        middleware = AuditMiddleware(config=config)
        long_result = {"data": "a" * 100}
        result = middleware._format_result(long_result)
        assert len(result) == 20
        assert result.endswith("...")

    @pytest.mark.asyncio
    async def test_on_call_tool_logs_invocation(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """on_call_tool should log tool invocations."""
        middleware = AuditMiddleware()

        # Create mock context
        mock_context = MagicMock()
        mock_context.message.name = "segmentation"
        mock_context.message.arguments = {"event": "login"}

        # Create mock call_next
        mock_result = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_result)

        with caplog.at_level(logging.INFO, logger="mp_mcp.audit"):
            result = await middleware.on_call_tool(mock_context, mock_call_next)

        assert result == mock_result
        mock_call_next.assert_called_once_with(mock_context)
        assert "Tool invoked: segmentation" in caplog.text

    @pytest.mark.asyncio
    async def test_on_call_tool_logs_completion(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """on_call_tool should log successful completion with timing."""
        middleware = AuditMiddleware()

        mock_context = MagicMock()
        mock_context.message.name = "list_events"
        mock_context.message.arguments = None

        mock_call_next = AsyncMock(return_value=["event1", "event2"])

        with caplog.at_level(logging.INFO, logger="mp_mcp.audit"):
            await middleware.on_call_tool(mock_context, mock_call_next)

        assert "Tool completed: list_events" in caplog.text
        assert "ms" in caplog.text

    @pytest.mark.asyncio
    async def test_on_call_tool_logs_result_when_enabled(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """on_call_tool should include result when configured."""
        config = AuditConfig(include_results=True)
        middleware = AuditMiddleware(config=config)

        mock_context = MagicMock()
        mock_context.message.name = "list_events"
        mock_context.message.arguments = {}

        mock_call_next = AsyncMock(return_value=["event1", "event2"])

        with caplog.at_level(logging.INFO, logger="mp_mcp.audit"):
            await middleware.on_call_tool(mock_context, mock_call_next)

        assert "->" in caplog.text

    @pytest.mark.asyncio
    async def test_on_call_tool_hides_params_when_disabled(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """on_call_tool should hide params when include_params is False."""
        config = AuditConfig(include_params=False)
        middleware = AuditMiddleware(config=config)

        mock_context = MagicMock()
        mock_context.message.name = "segmentation"
        mock_context.message.arguments = {"secret": "password"}

        mock_call_next = AsyncMock(return_value={})

        with caplog.at_level(logging.INFO, logger="mp_mcp.audit"):
            await middleware.on_call_tool(mock_context, mock_call_next)

        assert "(params hidden)" in caplog.text
        assert "password" not in caplog.text

    @pytest.mark.asyncio
    async def test_on_call_tool_logs_failure(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """on_call_tool should log failures with error info."""
        middleware = AuditMiddleware()

        mock_context = MagicMock()
        mock_context.message.name = "failing_tool"
        mock_context.message.arguments = {}

        mock_call_next = AsyncMock(side_effect=ValueError("Something went wrong"))

        with (
            caplog.at_level(logging.ERROR, logger="mp_mcp.audit"),
            pytest.raises(ValueError),
        ):
            await middleware.on_call_tool(mock_context, mock_call_next)

        assert "Tool failed: failing_tool" in caplog.text
        assert "ValueError" in caplog.text
        assert "Something went wrong" in caplog.text

    @pytest.mark.asyncio
    async def test_on_call_tool_propagates_exception(self) -> None:
        """on_call_tool should re-raise exceptions from tool."""
        middleware = AuditMiddleware()

        mock_context = MagicMock()
        mock_context.message.name = "test_tool"
        mock_context.message.arguments = {}

        expected_error = RuntimeError("Expected error")
        mock_call_next = AsyncMock(side_effect=expected_error)

        with pytest.raises(RuntimeError) as exc_info:
            await middleware.on_call_tool(mock_context, mock_call_next)

        assert exc_info.value is expected_error


class TestCreateAuditMiddleware:
    """Tests for create_audit_middleware factory function."""

    def test_default_params(self) -> None:
        """create_audit_middleware should use default parameters."""
        middleware = create_audit_middleware()
        assert middleware.config.log_level == logging.INFO
        assert middleware.config.include_params is True
        assert middleware.config.include_results is False

    def test_custom_log_level(self) -> None:
        """create_audit_middleware should accept custom log level."""
        middleware = create_audit_middleware(log_level=logging.DEBUG)
        assert middleware.config.log_level == logging.DEBUG

    def test_custom_include_params(self) -> None:
        """create_audit_middleware should accept include_params."""
        middleware = create_audit_middleware(include_params=False)
        assert middleware.config.include_params is False

    def test_custom_include_results(self) -> None:
        """create_audit_middleware should accept include_results."""
        middleware = create_audit_middleware(include_results=True)
        assert middleware.config.include_results is True

    def test_all_custom_params(self) -> None:
        """create_audit_middleware should accept all custom parameters."""
        middleware = create_audit_middleware(
            log_level=logging.WARNING,
            include_params=False,
            include_results=True,
        )
        assert middleware.config.log_level == logging.WARNING
        assert middleware.config.include_params is False
        assert middleware.config.include_results is True
