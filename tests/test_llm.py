"""Module 5F — LLM provider, fallback, and request understanding (mocked Gemini)."""

from __future__ import annotations

from datetime import date

import json

import pytest

from app.config.settings import get_settings
from app.llm.client import LLMClient
from app.llm.errors import LLMStructuredOutputError, LLMTimeoutError, LLMUnavailableError
from app.llm.factory import build_llm_client, reset_llm_client
from app.llm.gemini import GeminiProvider
from app.llm.metrics import llm_metrics_snapshot, reset_llm_metrics
from app.llm.models import GroundedResponseInput, UserContext
from app.llm.responses import generate_grounded_response
from app.llm.understanding import understand_request


class FakeProvider:
    name = "gemini"
    model = "gemini-2.5-flash"
    last_usage = {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12}

    def __init__(self, payload=None, *, error=None, text="Grounded summary.", calls=None):
        self.payload = payload or {}
        self.error = error
        self.text = text
        self.calls = calls if calls is not None else []

    def generate(self, *, prompt: str, system: str, operation: str) -> str:
        self.calls.append(("generate", operation))
        if self.error:
            raise self.error
        return self.text

    def generate_structured(self, *, prompt: str, system: str, schema, operation: str) -> dict:
        self.calls.append(("structured", operation))
        if self.error:
            raise self.error
        return dict(self.payload)


def _leave_payload(**overrides) -> dict:
    data = {
        "intent": "leave_request",
        "workflow_type": "leave_attendance",
        "request_kind": "action",
        "entities": {
            "duration_days": 3,
            "start_date": "2026-08-17",
            "dates": ["2026-08-17", "2026-08-18", "2026-08-19"],
        },
        "confidence": 0.94,
        "needs_clarification": False,
        "clarification_question": "",
        "reason": "",
        "summary_label": "Leave request",
    }
    data.update(overrides)
    return data


def test_gemini_provider_requires_api_key() -> None:
    with pytest.raises(LLMUnavailableError):
        GeminiProvider(api_key="", model="gemini-2.5-flash")


def test_missing_api_key_builds_unavailable_client(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    get_settings.cache_clear()
    client = build_llm_client()
    assert client.available is False
    assert client.provider_name == "none"


def test_gemini_provider_initialization_with_injected_client() -> None:
    provider = GeminiProvider(api_key="unused", model="gemini-2.5-flash", client=object())
    assert provider.name == "gemini"
    assert provider.model == "gemini-2.5-flash"


def test_developer_api_schema_strips_additional_properties() -> None:
    from app.llm.gemini import developer_api_response_schema
    from app.llm.models import LLMUnderstandingSchema

    raw = LLMUnderstandingSchema.model_json_schema()
    assert "additionalProperties" in str(raw)
    cleaned = developer_api_response_schema(LLMUnderstandingSchema)
    dumped = json.dumps(cleaned)
    assert "additionalProperties" not in dumped
    assert "additional_properties" not in dumped
    assert cleaned["properties"]["intent"]["type"] == "string"

    from google.genai import _transformers as transformers

    class _MldevClient:
        vertexai = False

    schema = transformers.t_schema(_MldevClient(), cleaned)
    assert schema is not None


def test_structured_config_uses_json_schema_not_pydantic_class() -> None:
    from app.llm.models import LLMUnderstandingSchema

    captured: dict = {}

    class _Models:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            raise TimeoutError("deadline")

    class _Client:
        models = _Models()

    provider = GeminiProvider(api_key="k", model="gemini-2.5-flash", client=_Client())
    with pytest.raises(LLMTimeoutError):
        provider.generate_structured(
            prompt="x",
            system="y",
            schema=LLMUnderstandingSchema,
            operation="understand",
        )
    config = captured["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is not LLMUnderstandingSchema
    assert isinstance(config.response_schema, dict)
    assert "additionalProperties" not in json.dumps(config.response_schema)


def test_mocked_gemini_success() -> None:
    provider = FakeProvider(_leave_payload())
    client = LLMClient(provider)
    result = client.generate_structured(
        prompt="unused",
        system="unused",
        schema=type("S", (), {}),
        operation="understand",
    )
    assert result.status == "success"
    assert result.provider == "gemini"
    assert result.parsed["workflow_type"] == "leave_attendance"
    assert result.usage.total_tokens == 12


def test_mocked_gemini_failure() -> None:
    client = LLMClient(FakeProvider(error=LLMTimeoutError("timeout")))
    with pytest.raises(LLMTimeoutError):
        client.generate(prompt="x", system="y", operation="respond")
    snap = llm_metrics_snapshot()
    assert any(item["status"] == "timeout" for item in snap["llm_requests_total"])
    assert snap["llm_failures_total"]


def test_timeout_from_gemini_sdk() -> None:
    class _Models:
        def generate_content(self, **kwargs):
            raise TimeoutError("deadline")

    class _Client:
        models = _Models()

    provider = GeminiProvider(api_key="k", model="gemini-2.5-flash", client=_Client())
    with pytest.raises(LLMTimeoutError):
        provider.generate(prompt="hi", system="sys", operation="respond")


def test_malformed_structured_output() -> None:
    class _Response:
        parsed = None
        text = "not-json"
        usage_metadata = None

    class _Models:
        def generate_content(self, **kwargs):
            return _Response()

    class _Client:
        models = _Models()

    provider = GeminiProvider(api_key="k", model="gemini-2.5-flash", client=_Client())
    from pydantic import BaseModel

    class Box(BaseModel):
        intent: str

    with pytest.raises(LLMStructuredOutputError):
        provider.generate_structured(prompt="x", system="y", schema=Box, operation="understand")


def test_deterministic_fallback_without_key() -> None:
    result = understand_request(
        "Check whether employee E001 can take 3 days of leave from 2026-08-17.",
        today=date(2026, 8, 16),
    )
    assert result.provider == "deterministic_fallback"
    assert result.workflow_type == "leave_attendance"
    assert result.entities.employee_id == "E001"
    assert result.entities.duration_days == 3


def test_request_understanding_mocked_gemini() -> None:
    reset_llm_client(LLMClient(FakeProvider(_leave_payload())))
    result = understand_request("I need three days off next week.")
    assert result.provider == "gemini"
    assert result.workflow_type == "leave_attendance"
    assert result.summary_label == "Leave request"


def test_leave_natural_language_variants() -> None:
    phrases = [
        "Request 3 days leave.",
        "I need three days off.",
        "Can I take Monday through Wednesday off?",
        "I'd like to take three days off next week.",
    ]
    today = date(2026, 8, 16)
    types = {
        understand_request(phrase, today=today).workflow_type
        for phrase in phrases
    }
    assert types == {"leave_attendance"}


def test_recruitment_natural_language_variants() -> None:
    phrases = [
        "Find Python backend candidates.",
        "Who are the strongest Python applicants?",
        "Which candidates fit the backend position?",
        "Shortlist the strongest candidates for J001.",
    ]
    types = {understand_request(phrase).workflow_type for phrase in phrases}
    assert types == {"recruitment"}


def test_onboarding_natural_language_variants() -> None:
    phrases = [
        "Start onboarding for E003.",
        "Help me onboard E003.",
        "Is E003 ready for onboarding?",
        "Check what's missing for E004.",
    ]
    results = [understand_request(phrase) for phrase in phrases]
    assert {item.workflow_type for item in results} == {"onboarding"}
    assert results[0].entities.employee_id == "E003"
    assert results[-1].entities.employee_id == "E004"


def test_clarification_leave_and_recruitment_and_onboarding() -> None:
    leave = understand_request("I need leave.")
    assert leave.needs_clarification is True
    assert "date" in leave.clarification_question.lower()

    recruiting = understand_request("Find candidates.")
    assert recruiting.needs_clarification is True
    assert "job" in recruiting.clarification_question.lower() or "position" in recruiting.clarification_question.lower()

    onboard = understand_request("Start onboarding.")
    assert onboard.needs_clarification is True
    assert "employee" in onboard.clarification_question.lower()


def test_unsupported_request() -> None:
    result = understand_request("What is the weather today?")
    assert result.request_kind == "unsupported"
    assert result.workflow_type == ""
    assert "HR" in result.reason


def test_authenticated_employee_context_overrides_extracted_id() -> None:
    reset_llm_client(
        LLMClient(
            FakeProvider(
                _leave_payload(
                    entities={
                        "employee_id": "E999",
                        "duration_days": 3,
                        "start_date": "2026-08-17",
                    }
                )
            )
        )
    )
    user = UserContext(role="employee", employee_id="E001", organization_id="demo-org")
    result = understand_request("I need three days off next week.", user=user)
    assert result.entities.employee_id == "E001"


def test_explicit_workflow_skips_gemini() -> None:
    provider = FakeProvider(_leave_payload())
    reset_llm_client(LLMClient(provider))
    result = understand_request(
        "Please process this generic case.",
        explicit_workflow_type="hr_services",
        skip_llm=True,
    )
    assert provider.calls == []
    assert result.workflow_type == "hr_services"
    assert result.provider == "deterministic_fallback"


def test_deterministic_response_fallback() -> None:
    from app.llm.errors import LLMError

    reset_llm_client(LLMClient(FakeProvider(error=LLMError("boom"))))
    text, meta = generate_grounded_response(
        GroundedResponseInput(
            outcome="reject",
            blockers=["insufficient_leave_balance"],
            deterministic_response="Leave was rejected because balance is insufficient.",
        )
    )
    assert "insufficient" in text.lower()
    assert meta is None


def test_grounded_response_uses_mock_text() -> None:
    reset_llm_client(LLMClient(FakeProvider(text="Your leave request was approved.")))
    text, meta = generate_grounded_response(
        GroundedResponseInput(deterministic_response="Leave approved for E001.")
    )
    assert text == "Your leave request was approved."
    assert meta is not None
    assert meta.operation == "respond"


def test_llm_metrics_recorded() -> None:
    reset_llm_metrics()
    understand_request("Find candidates for J001.")
    snap = llm_metrics_snapshot()
    assert snap["llm_requests_total"]
    assert all("prompt" not in str(item).lower() for item in snap["llm_requests_total"])
