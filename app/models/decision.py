"""Reusable decision model for all HR workflows."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

DecisionOutcome = Literal[
    "approve",
    "reject",
    "pending_approval",
    "escalate",
    "recommend",
    "ready",
    "blocked",
]

# Outcomes that pause the workflow for a human before write actions run.
HUMAN_APPROVAL_OUTCOMES = frozenset({"pending_approval", "escalate"})

# Outcomes that may execute write tools after validation.
EXECUTABLE_OUTCOMES = frozenset({"approve", "ready"})


class WorkflowDecision(BaseModel):
    """Structured decision shared by leave, recruitment, onboarding, and future workflows.

    Tools and structured policy validation remain authoritative. evidence / blockers /
    warnings / influenced_by support explanations and confidence — they must not
    override policy or tool validation outcomes.
    """

    outcome: DecisionOutcome
    rationale: str
    executable: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_human_approval: bool = False
    entity_refs: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    influenced_by: list[str] = Field(default_factory=list)

    def needs_human_approval(self) -> bool:
        return self.requires_human_approval or self.outcome in HUMAN_APPROVAL_OUTCOMES
