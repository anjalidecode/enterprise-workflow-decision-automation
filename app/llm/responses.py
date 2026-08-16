"""Optional grounded response rewrite. Never invents workflow facts."""

from __future__ import annotations

import logging

from app.llm.client import LLMClient
from app.llm.errors import LLMError, LLMTimeoutError, LLMUnavailableError
from app.llm.factory import get_llm_client
from app.llm.models import GroundedResponseInput, LLMCallResult
from app.llm.prompts import RESPONSE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def generate_grounded_response(
    payload: GroundedResponseInput,
    *,
    client: LLMClient | None = None,
) -> tuple[str, LLMCallResult | None]:
    """Return (response_text, llm_metadata). Falls back to deterministic text."""

    deterministic = (payload.deterministic_response or "").strip()
    llm = client or get_llm_client()
    if not llm.available or not deterministic:
        return deterministic, None

    prompt = (
        "Rewrite the user-facing message using only these facts.\n"
        f"workflow_type: {payload.workflow_type}\n"
        f"status: {payload.status}\n"
        f"outcome: {payload.outcome}\n"
        f"rationale: {payload.rationale}\n"
        f"blockers: {payload.blockers}\n"
        f"warnings: {payload.warnings}\n"
        f"evidence: {payload.evidence}\n"
        f"requires_human_approval: {payload.requires_human_approval}\n"
        f"deterministic_response: {deterministic}\n"
    )
    try:
        call = llm.generate(prompt=prompt, system=RESPONSE_SYSTEM_PROMPT, operation="respond")
        text = (call.text or "").strip()
        if not text:
            return deterministic, call
        return text, call
    except (LLMTimeoutError, LLMUnavailableError, LLMError) as exc:
        logger.info("Grounded response generation failed (%s); using deterministic text.", type(exc).__name__)
        return deterministic, None
