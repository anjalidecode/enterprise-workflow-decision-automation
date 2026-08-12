"""Deterministic workflow router. Not a chatbot; no LLM calls."""

from __future__ import annotations

from dataclasses import dataclass

from app.workflows.contracts import RouterResult, WorkflowSpec
from app.workflows.registry import WorkflowRegistry, get_workflow_registry


@dataclass(frozen=True)
class _Match:
    workflow_type: str
    score: float
    matched_hints: tuple[str, ...]


class WorkflowRouter:
    """Classify a business request into a registered workflow_type."""

    def __init__(self, registry: WorkflowRegistry | None = None) -> None:
        self._registry = registry or get_workflow_registry()

    def classify(
        self,
        user_request: str,
        *,
        workflow_type: str | None = None,
    ) -> RouterResult:
        explicit = (workflow_type or "").strip()
        if explicit:
            if explicit not in self._registry.list_workflow_types():
                return RouterResult(
                    workflow_type="",
                    confidence=0.0,
                    matched_hints=[],
                    unsupported_reason=f"Explicit workflow_type '{explicit}' is not registered.",
                    status="unsupported",
                )
            return RouterResult(
                workflow_type=explicit,
                confidence=1.0,
                matched_hints=[],
                unsupported_reason="",
                status="routed",
            )

        matches = [
            match
            for match in (
                self._score_spec(user_request, spec)
                for spec in self._registry.list_workflows()
            )
            if match.score > 0
        ]
        matches.sort(key=lambda item: (-item.score, -len(item.matched_hints), item.workflow_type))

        if not matches:
            return RouterResult(
                workflow_type="",
                confidence=0.0,
                matched_hints=[],
                unsupported_reason="No registered workflow matched the request hints.",
                status="unsupported",
            )

        if len(matches) >= 2 and matches[0].score == matches[1].score:
            return RouterResult(
                workflow_type="",
                confidence=0.0,
                matched_hints=list(matches[0].matched_hints),
                unsupported_reason=(
                    "Ambiguous request matched multiple workflows with equal confidence: "
                    f"{matches[0].workflow_type}, {matches[1].workflow_type}."
                ),
                status="needs_clarification",
            )

        best = matches[0]
        # Confidence from hint coverage: longer/more hints → higher, capped at 0.99
        # (1.0 reserved for explicit overrides).
        confidence = min(0.99, 0.55 + 0.15 * len(best.matched_hints) + 0.01 * best.score)
        return RouterResult(
            workflow_type=best.workflow_type,
            confidence=round(confidence, 3),
            matched_hints=list(best.matched_hints),
            unsupported_reason="",
            status="routed",
        )

    def _score_spec(self, user_request: str, spec: WorkflowSpec) -> _Match:
        text = user_request.lower()
        matched: list[str] = []
        score = 0.0
        for hint in spec.supported_request_hints:
            normalized = hint.strip().lower()
            if not normalized:
                continue
            if normalized in text:
                matched.append(hint)
                # Prefer longer phrases slightly so future domain hints can win.
                score += 1.0 + (len(normalized) / 100.0)
        return _Match(
            workflow_type=spec.workflow_type,
            score=score,
            matched_hints=tuple(matched),
        )
