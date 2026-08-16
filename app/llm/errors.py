"""LLM-layer errors. These never authorize enterprise actions."""

from __future__ import annotations


class LLMError(Exception):
    """Base error for the request-understanding LLM layer."""


class LLMUnavailableError(LLMError):
    """Provider is not configured or cannot be reached."""


class LLMTimeoutError(LLMError):
    """Provider exceeded the configured timeout."""


class LLMStructuredOutputError(LLMError):
    """Model output could not be parsed into the expected schema."""
