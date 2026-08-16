"""Construct the process LLM client from settings. Never reads secrets into logs."""

from __future__ import annotations

import logging

from app.config.settings import get_settings
from app.llm.client import LLMClient
from app.llm.errors import LLMUnavailableError
from app.llm.gemini import GeminiProvider

logger = logging.getLogger(__name__)

_CLIENT: LLMClient | None = None


def build_llm_client(*, settings: object | None = None) -> LLMClient:
    cfg = settings or get_settings()
    api_key = str(getattr(cfg, "google_api_key", "") or "").strip()
    if not api_key:
        return LLMClient(None)
    model = str(getattr(cfg, "gemini_model", "") or "gemini-3.5-flash").strip()
    timeout = float(getattr(cfg, "llm_timeout_seconds", 20.0) or 20.0)
    try:
        provider = GeminiProvider(api_key=api_key, model=model, timeout_seconds=timeout)
    except LLMUnavailableError:
        logger.info("Gemini provider unavailable; deterministic fallback will be used.")
        return LLMClient(None)
    return LLMClient(provider)


def get_llm_client() -> LLMClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = build_llm_client()
    return _CLIENT


def reset_llm_client(client: LLMClient | None = None) -> LLMClient:
    global _CLIENT
    if client is not None:
        _CLIENT = client
    else:
        _CLIENT = LLMClient(None)
    return _CLIENT
