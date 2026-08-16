"""LLM provider protocol. Application code depends on this, not Gemini."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel


class LLMProvider(Protocol):
    name: str
    model: str

    def generate(
        self,
        *,
        prompt: str,
        system: str,
        operation: str,
    ) -> str:
        """Return raw text. Must not log secrets."""

    def generate_structured(
        self,
        *,
        prompt: str,
        system: str,
        schema: type[BaseModel],
        operation: str,
    ) -> dict[str, Any]:
        """Return a dict that validates against schema."""
