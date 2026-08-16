"""Gemini provider using the official google-genai SDK."""

from __future__ import annotations

import copy
import json
import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from app.llm.errors import LLMError, LLMStructuredOutputError, LLMTimeoutError, LLMUnavailableError

logger = logging.getLogger(__name__)

_SAFE_ERROR_MAX = 240
_SECRET_MARKERS = ("api_key", "apikey", "authorization", "bearer ", "password", "token")


def _safe_error_text(exc: BaseException) -> str:
    """Return a short exception message with secrets stripped. Never logs prompts."""

    text = str(exc).replace("\n", " ").strip()
    lowered = text.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return type(exc).__name__
    return text[:_SAFE_ERROR_MAX]


def _strip_unsupported_schema_keys(node: Any) -> Any:
    """Gemini Developer API rejects additionalProperties in response_schema."""

    if isinstance(node, dict):
        cleaned: dict[str, Any] = {}
        for key, value in node.items():
            if key in {"additionalProperties", "additional_properties"}:
                continue
            cleaned[key] = _strip_unsupported_schema_keys(value)
        return cleaned
    if isinstance(node, list):
        return [_strip_unsupported_schema_keys(item) for item in node]
    return node


def developer_api_response_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model to a Schema dict accepted by google-genai 2.x.

    Passing the Pydantic class as response_schema triggers SDK t_schema(), which
    raises ValueError for dict[str, Any] fields (additionalProperties) on the
    Gemini Developer API.
    """

    return _strip_unsupported_schema_keys(copy.deepcopy(schema.model_json_schema()))


def _usage_from_response(response: Any) -> dict[str, int | None]:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    prompt = getattr(meta, "prompt_token_count", None)
    completion = getattr(meta, "candidates_token_count", None)
    total = getattr(meta, "total_token_count", None)
    return {
        "prompt_tokens": int(prompt) if prompt is not None else None,
        "completion_tokens": int(completion) if completion is not None else None,
        "total_tokens": int(total) if total is not None else None,
    }


class GeminiProvider:
    """Primary LLM provider. Never used to execute HR tools or decisions."""

    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 20.0,
        client: Any | None = None,
    ) -> None:
        if not (api_key or "").strip() and client is None:
            raise LLMUnavailableError("GOOGLE_API_KEY is not configured.")
        self.model = (model or "gemini-3.5-flash").strip() or "gemini-3.5-flash"
        self._timeout_ms = max(int(timeout_seconds * 1000), 1000)
        self._last_usage: dict[str, int | None] = {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }
        if client is not None:
            self._client = client
            return
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - dependency is in requirements
            raise LLMUnavailableError("google-genai is not installed.") from exc
        self._client = genai.Client(
            api_key=api_key.strip(),
            http_options=types.HttpOptions(timeout=self._timeout_ms),
        )

    @property
    def last_usage(self) -> dict[str, int | None]:
        return dict(self._last_usage)

    def _config(self, *, system: str, schema: type[BaseModel] | None) -> Any:
        from google.genai import types

        kwargs: dict[str, Any] = {
            "system_instruction": system,
            "temperature": 0.1,
            "http_options": types.HttpOptions(timeout=self._timeout_ms),
        }
        if schema is not None:
            kwargs["response_mime_type"] = "application/json"
            kwargs["response_schema"] = developer_api_response_schema(schema)
        return types.GenerateContentConfig(**kwargs)

    def _generate(self, *, prompt: str, system: str, schema: type[BaseModel] | None) -> Any:
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=self._config(system=system, schema=schema),
            )
        except TimeoutError as exc:
            raise LLMTimeoutError("Gemini request timed out.") from exc
        except Exception as exc:
            message = str(exc).lower()
            if "timeout" in message or "deadline" in message:
                raise LLMTimeoutError("Gemini request timed out.") from exc
            logger.warning(
                "Gemini generate_content failed: %s: %s",
                type(exc).__name__,
                _safe_error_text(exc),
            )
            raise LLMError(f"Gemini request failed: {type(exc).__name__}") from exc
        self._last_usage = _usage_from_response(response)
        return response

    def generate(self, *, prompt: str, system: str, operation: str) -> str:
        del operation
        response = self._generate(prompt=prompt, system=system, schema=None)
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            raise LLMError("Gemini returned an empty response.")
        return text

    def generate_structured(
        self,
        *,
        prompt: str,
        system: str,
        schema: type[BaseModel],
        operation: str,
    ) -> dict[str, Any]:
        del operation
        response = self._generate(prompt=prompt, system=system, schema=schema)
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            if isinstance(parsed, BaseModel):
                return parsed.model_dump()
            if isinstance(parsed, dict):
                try:
                    return schema.model_validate(parsed).model_dump()
                except ValidationError as exc:
                    raise LLMStructuredOutputError("Gemini structured output failed validation.") from exc
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            raise LLMStructuredOutputError("Gemini returned empty structured output.")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMStructuredOutputError("Gemini did not return valid JSON.") from exc
        try:
            return schema.model_validate(payload).model_dump()
        except ValidationError as exc:
            raise LLMStructuredOutputError("Gemini structured output failed validation.") from exc
