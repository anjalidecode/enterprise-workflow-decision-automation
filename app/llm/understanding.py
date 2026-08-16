"""Request understanding: Gemini first, deterministic fallback when unavailable.

This layer does not execute HR actions. WorkflowRouter remains authoritative
for registered workflow types after validation.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from app.llm.client import LLMClient
from app.llm.dates import extract_dates, parse_duration_days, reference_today
from app.llm.errors import LLMError, LLMStructuredOutputError, LLMTimeoutError, LLMUnavailableError
from app.llm.factory import get_llm_client
from app.llm.metrics import record_llm_call
from app.llm.models import (
    LLMUnderstandingSchema,
    RequestUnderstanding,
    RequestUnderstandingPublic,
    UnderstandingEntities,
    UserContext,
)
from app.llm.prompts import (
    HR_SCOPE_CLARIFICATION,
    OUT_OF_SCOPE_MESSAGE,
    UNDERSTANDING_SYSTEM_PROMPT,
)
from app.services.leave_parser import parse_leave_request
from app.services.onboarding_parser import parse_onboarding_request
from app.services.recruitment_parser import parse_recruitment_request
from app.workflows.registry import get_workflow_registry
from app.workflows.router import WorkflowRouter

logger = logging.getLogger(__name__)

_EMPLOYEE_ID = re.compile(r"\b(E\d{3,})\b", re.IGNORECASE)
_JOB_ID = re.compile(r"\b(J\d{3})\b", re.IGNORECASE)

_OUT_OF_SCOPE_HINTS = (
    "weather",
    "sports score",
    "recipe",
    "marketing campaign",
    "stock price",
    "bitcoin",
    "write a poem",
    "tell me a joke",
)

_INFO_HINTS = (
    "what is",
    "what's",
    "explain",
    "policy",
    "handbook",
    "do i have enough",
    "enough leave",
    "check my balance",
    "leave balance",
    "is e0",
    "ready for onboarding",
    "what is missing",
    "what's missing",
    "status of",
)

_LEAVE_ACTION_HINTS = (
    "apply",
    "request",
    "take",
    "submit",
    "book",
    "need",
    "want",
    "days off",
    "time off",
    "pto",
    "vacation",
)

_SUMMARY = {
    "leave_attendance": "Leave request",
    "recruitment": "Recruitment candidate search",
    "onboarding": "Onboarding",
    "attendance": "Attendance analysis",
    "performance": "Performance review",
    "training": "Training recommendation",
    "offboarding": "Offboarding",
    "hr_services": "HR services request",
}


def public_understanding(item: RequestUnderstanding) -> RequestUnderstandingPublic:
    entities = item.entities.model_dump(exclude_none=True)
    return RequestUnderstandingPublic(
        intent=item.intent,
        workflow_type=item.workflow_type,
        request_kind=item.request_kind,
        summary_label=item.summary_label or _SUMMARY.get(item.workflow_type, ""),
        needs_clarification=item.needs_clarification,
        clarification_question=item.clarification_question,
        confidence=item.confidence,
        entities=entities,
    )


def _registered_types() -> set[str]:
    return set(get_workflow_registry().list_workflow_types())


def _sanitize_workflow_type(value: str, registered: set[str]) -> str:
    cleaned = (value or "").strip()
    if cleaned in registered:
        return cleaned
    return ""


def _bind_identity(
    understanding: RequestUnderstanding,
    *,
    user: UserContext | None,
) -> RequestUnderstanding:
    """JWT employee identity wins over any extracted employee_id."""

    if user is None:
        return understanding
    role = (user.role or "").strip().lower()
    own = (user.employee_id or "").strip().upper()
    extracted = (understanding.entities.employee_id or "").strip().upper() or None
    if extracted:
        understanding.entities.employee_id = extracted
    if role == "employee" and own:
        understanding.entities.employee_id = own
    return understanding


def _apply_clarification_rules(
    understanding: RequestUnderstanding,
    *,
    user: UserContext | None,
) -> RequestUnderstanding:
    if understanding.request_kind == "unsupported":
        understanding.needs_clarification = False
        understanding.workflow_type = ""
        understanding.summary_label = "Unsupported request"
        if not understanding.reason:
            understanding.reason = OUT_OF_SCOPE_MESSAGE
        return understanding

    wf = understanding.workflow_type
    kind = understanding.request_kind
    entities = understanding.entities
    role = (user.role if user else "") or ""
    own = (user.employee_id if user else "") or ""

    if wf == "leave_attendance" and kind == "action":
        if not entities.start_date and not entities.dates and entities.duration_days is None:
            understanding.needs_clarification = True
            understanding.clarification_question = (
                understanding.clarification_question
                or "What dates would you like to request leave for?"
            )
    elif wf == "recruitment" and kind == "action":
        if not entities.job_id and not entities.job_title and not (entities.skills or []):
            understanding.needs_clarification = True
            understanding.clarification_question = (
                understanding.clarification_question
                or "Which job position should I search for?"
            )
    elif wf == "onboarding":
        if not entities.employee_id and not (role == "employee" and own):
            understanding.needs_clarification = True
            understanding.clarification_question = (
                understanding.clarification_question
                or "Which employee should I onboard?"
            )

    if understanding.needs_clarification and not understanding.clarification_question:
        understanding.clarification_question = HR_SCOPE_CLARIFICATION
    if not understanding.summary_label:
        understanding.summary_label = _SUMMARY.get(wf, understanding.intent.replace("_", " ").title())
    return understanding


def _validate_understanding(
    raw: dict[str, Any],
    *,
    registered: set[str],
    provider: str,
    user: UserContext | None,
) -> RequestUnderstanding:
    item = RequestUnderstanding.model_validate(raw)
    item.provider = provider  # type: ignore[assignment]
    item.workflow_type = _sanitize_workflow_type(item.workflow_type, registered)
    if item.entities.employee_id:
        match = _EMPLOYEE_ID.search(item.entities.employee_id)
        item.entities.employee_id = match.group(1).upper() if match else None
    if item.entities.job_id:
        match = _JOB_ID.search(item.entities.job_id)
        item.entities.job_id = match.group(1).upper() if match else None
    item = _bind_identity(item, user=user)
    return _apply_clarification_rules(item, user=user)


def _looks_out_of_scope(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in _OUT_OF_SCOPE_HINTS)


def _looks_information(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in _INFO_HINTS)


def _fallback_understanding(
    user_request: str,
    *,
    user: UserContext | None,
    registered: set[str],
    today: date,
    explicit_workflow_type: str | None,
) -> RequestUnderstanding:
    """Keyword/router fallback. Clearly not Gemini. Used when no API key or LLM fails."""

    if not explicit_workflow_type and _looks_out_of_scope(user_request):
        record_llm_call(
            operation="understand",
            provider="deterministic_fallback",
            status="success",
            duration_seconds=0.0,
        )
        return RequestUnderstanding(
            intent="unsupported",
            workflow_type="",
            request_kind="unsupported",
            confidence=0.9,
            reason=OUT_OF_SCOPE_MESSAGE,
            summary_label="Unsupported request",
            provider="deterministic_fallback",
        )

    workflow_type = _sanitize_workflow_type(explicit_workflow_type or "", registered)
    matched_hints: list[str] = []
    if not workflow_type:
        routed = WorkflowRouter().classify(user_request)
        workflow_type = routed.workflow_type if routed.status == "routed" else ""
        matched_hints = list(routed.matched_hints)

    lowered = user_request.lower()
    if not workflow_type:
        if any(token in lowered for token in ("leave", "time off", "days off", "pto", "vacation", "off next", "take monday", "take tuesday")):
            workflow_type = "leave_attendance"
        elif any(token in lowered for token in ("candidate", "applicants", "shortlist", "hire", "job opening", "recruit")):
            workflow_type = "recruitment"
        elif any(token in lowered for token in ("onboard", "onboarding", "new hire", "new employee")):
            workflow_type = "onboarding"
        elif _EMPLOYEE_ID.search(user_request) and any(
            token in lowered for token in ("missing", "ready for", "access")
        ):
            workflow_type = "onboarding"

    info = _looks_information(user_request)
    leave_action = any(token in lowered for token in _LEAVE_ACTION_HINTS) and not info
    kind = "information" if info else "action"

    entities = UnderstandingEntities()
    if workflow_type == "leave_attendance" or (not workflow_type and leave_action):
        workflow_type = workflow_type or "leave_attendance"
        parsed = parse_leave_request(user_request)
        dates, start, end, duration = extract_dates(user_request, today=today)
        entities.employee_id = parsed.employee_id
        entities.duration_days = duration or parsed.days
        entities.start_date = start or parsed.start_date
        entities.end_date = end
        entities.dates = dates
        entities.reason = None
        intent = "leave_policy_question" if info else "leave_request"
        if info and any(token in lowered for token in ("policy", "explain")):
            workflow_type = "leave_attendance"
            kind = "information"
    elif workflow_type == "recruitment":
        parsed = parse_recruitment_request(user_request)
        entities.job_id = parsed.get("job_id")
        entities.query = parsed.get("query")
        intent = "recruitment_search"
        if "python" in lowered:
            entities.skills = ["Python"]
        if "fastapi" in lowered:
            entities.skills = list(dict.fromkeys([*(entities.skills or []), "FastAPI"]))
        if not entities.job_title and "backend" in lowered:
            entities.job_title = "Python Backend Developer"
            entities.job_id = entities.job_id or "J001"
    elif workflow_type == "onboarding":
        parsed = parse_onboarding_request(user_request)
        entities.employee_id = parsed.get("employee_id")
        intent = "onboarding_check" if info else "onboarding_start"
    else:
        intent = workflow_type or "unknown"

    if workflow_type == "hr_services" or (
        info and any(token in lowered for token in ("certificate", "letter", "benefits"))
    ):
        intent = "hr_services_request"

    understanding = RequestUnderstanding(
        intent=intent,
        workflow_type=_sanitize_workflow_type(workflow_type, registered),
        request_kind=kind,  # type: ignore[arg-type]
        entities=entities,
        parameters={"matched_hints": matched_hints, "fallback": True},
        confidence=0.7 if workflow_type else 0.2,
        reason="Deterministic fallback understanding (Gemini was not used).",
        provider="deterministic_fallback",
    )
    record_llm_call(
        operation="understand",
        provider="deterministic_fallback",
        status="success",
        duration_seconds=0.0,
    )
    understanding = _bind_identity(understanding, user=user)
    return _apply_clarification_rules(understanding, user=user)


def _understanding_prompt(
    user_request: str,
    *,
    user: UserContext | None,
    registered: list[str],
    today: date,
) -> str:
    role = (user.role if user else "") or "anonymous"
    employee_id = (user.employee_id if user else "") or ""
    return (
        f"Current date: {today.isoformat()} ({today.strftime('%A')})\n"
        f"Authenticated role: {role}\n"
        f"Authenticated employee_id: {employee_id or '(none)'}\n"
        f"Registered workflow types: {', '.join(registered)}\n"
        "Do not include passwords, tokens, or API keys in your reasoning.\n\n"
        f"User request:\n{user_request.strip()}\n"
    )


def understand_request(
    user_request: str,
    *,
    user: UserContext | None = None,
    explicit_workflow_type: str | None = None,
    skip_llm: bool = False,
    client: LLMClient | None = None,
    today: date | None = None,
) -> RequestUnderstanding:
    """Interpret a free-form request. Explicit workflow selection skips Gemini routing."""

    registered = _registered_types()
    now = today or reference_today()
    explicit = _sanitize_workflow_type(explicit_workflow_type or "", registered)

    if skip_llm or explicit:
        result = _fallback_understanding(
            user_request,
            user=user,
            registered=registered,
            today=now,
            explicit_workflow_type=explicit or None,
        )
        if explicit:
            result.workflow_type = explicit
            result.needs_clarification = False
            result.clarification_question = ""
            if not result.summary_label:
                result.summary_label = _SUMMARY.get(explicit, explicit)
        return result

    llm = client or get_llm_client()
    if not llm.available:
        return _fallback_understanding(
            user_request,
            user=user,
            registered=registered,
            today=now,
            explicit_workflow_type=None,
        )

    prompt = _understanding_prompt(
        user_request,
        user=user,
        registered=sorted(registered),
        today=now,
    )
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            call = llm.generate_structured(
                prompt=prompt,
                system=UNDERSTANDING_SYSTEM_PROMPT,
                schema=LLMUnderstandingSchema,
                operation="understand",
            )
            return _validate_understanding(
                call.parsed,
                registered=registered,
                provider="gemini",
                user=user,
            )
        except (LLMStructuredOutputError, LLMTimeoutError, LLMUnavailableError, LLMError) as exc:
            last_error = exc
            logger.info("Gemini understanding failed (%s); retry or fallback.", type(exc).__name__)
            continue

    logger.info("Using deterministic fallback after Gemini understanding failure: %s", type(last_error).__name__ if last_error else "unknown")
    return _fallback_understanding(
        user_request,
        user=user,
        registered=registered,
        today=now,
        explicit_workflow_type=None,
    )
