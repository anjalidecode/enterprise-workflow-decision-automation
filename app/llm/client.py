"""LLM client with tracing, timeouts, and safe metadata."""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import BaseModel

from app.llm.errors import LLMError, LLMStructuredOutputError, LLMTimeoutError, LLMUnavailableError
from app.llm.metrics import record_llm_call
from app.llm.models import LLMCallResult, LLMUsage
from app.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class LLMClient:
    """Application-facing LLM API. Never executes HR tools."""

    def __init__(self, provider: LLMProvider | None) -> None:
        self._provider = provider

    @property
    def available(self) -> bool:
        return self._provider is not None

    @property
    def provider_name(self) -> str:
        if self._provider is None:
            return "none"
        return getattr(self._provider, "name", "none")

    @property
    def model(self) -> str:
        if self._provider is None:
            return ""
        return getattr(self._provider, "model", "") or ""

    def generate(self, *, prompt: str, system: str, operation: str = "respond") -> LLMCallResult:
        return self._invoke(operation=operation, prompt=prompt, system=system, schema=None)

    def generate_structured(
        self,
        *,
        prompt: str,
        system: str,
        schema: type[BaseModel],
        operation: str = "understand",
    ) -> LLMCallResult:
        return self._invoke(operation=operation, prompt=prompt, system=system, schema=schema)

    def _invoke(
        self,
        *,
        operation: str,
        prompt: str,
        system: str,
        schema: type[BaseModel] | None,
    ) -> LLMCallResult:
        provider = self._provider
        if provider is None:
            record_llm_call(
                operation=operation,
                provider="none",
                status="unavailable",
                duration_seconds=0.0,
            )
            return LLMCallResult(
                provider="none",
                model="",
                operation=operation,  # type: ignore[arg-type]
                status="unavailable",
                error_type="LLMUnavailableError",
            )

        started = time.perf_counter()
        status = "error"
        error_type = ""
        text = ""
        parsed: dict[str, Any] = {}
        usage = LLMUsage()
        try:
            if schema is None:
                text = provider.generate(prompt=prompt, system=system, operation=operation)
            else:
                parsed = provider.generate_structured(
                    prompt=prompt,
                    system=system,
                    schema=schema,
                    operation=operation,
                )
            status = "success"
        except LLMTimeoutError:
            status = "timeout"
            error_type = "LLMTimeoutError"
            raise
        except LLMStructuredOutputError:
            status = "malformed"
            error_type = "LLMStructuredOutputError"
            raise
        except LLMUnavailableError:
            status = "unavailable"
            error_type = "LLMUnavailableError"
            raise
        except LLMError:
            status = "error"
            error_type = "LLMError"
            raise
        except Exception:
            status = "error"
            error_type = "LLMError"
            logger.warning("LLM provider raised unexpected error", exc_info=False)
            raise LLMError("LLM provider failed.") from None
        finally:
            duration = time.perf_counter() - started
            raw_usage = getattr(provider, "last_usage", None)
            if isinstance(raw_usage, dict):
                usage = LLMUsage(
                    prompt_tokens=raw_usage.get("prompt_tokens"),
                    completion_tokens=raw_usage.get("completion_tokens"),
                    total_tokens=raw_usage.get("total_tokens"),
                )
            record_llm_call(
                operation=operation,
                provider=getattr(provider, "name", "gemini"),
                status=status,
                duration_seconds=duration,
            )
            logger.info(
                "llm_call provider=%s model=%s operation=%s status=%s duration_ms=%.1f",
                getattr(provider, "name", "unknown"),
                getattr(provider, "model", ""),
                operation,
                status,
                duration * 1000,
            )
            result = LLMCallResult(
                provider="gemini",
                model=getattr(provider, "model", "") or "",
                operation=operation,  # type: ignore[arg-type]
                status=status,
                duration_ms=round(duration * 1000, 3),
                usage=usage,
                error_type=error_type,
                text=text,
                parsed=parsed,
            )
        return result
