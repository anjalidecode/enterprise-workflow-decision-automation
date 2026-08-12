"""Typed errors for tool selection and execution."""

from __future__ import annotations


class ToolError(Exception):
    """Base class for tool-layer failures."""

    error_code: str = "SERVICE_ERROR"
    retryable: bool = False

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ToolInvalidInputError(ToolError):
    error_code = "INVALID_INPUT"
    retryable = False


class ToolForbiddenError(ToolError):
    error_code = "FORBIDDEN"
    retryable = False


class ToolNotFoundError(ToolError):
    """Unknown tool/capability, or a missing business record."""

    error_code = "NOT_FOUND"
    retryable = False


class ToolServiceError(ToolError):
    """Transient failure in an underlying service. May be retried."""

    error_code = "SERVICE_ERROR"
    retryable = True


class ToolSelectionError(ToolError):
    """Selector could not authorize or resolve a tool."""

    error_code = "FORBIDDEN"
    retryable = False


def from_service_error(error: Exception) -> ToolServiceError:
    """Convert a simulated backend failure into a retryable tool error."""

    return ToolServiceError(str(error))
