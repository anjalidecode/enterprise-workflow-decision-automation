"""Generic agent and workflow contracts for the Module 1 orchestration layer.

These contracts describe the core agent framework. Domain workflows (leave,
recruitment, onboarding, etc.) plug into the same shapes without changing
LangGraph shared-state coordination.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

WorkflowType = Literal[
    "leave_attendance",
    "recruitment",
    "onboarding",
    "attendance",
    "performance",
    "training",
    "offboarding",
    "unsupported",
    "",
]

UserRole = Literal[
    "system",
    "hr_admin",
    "manager",
    "employee",
    "recruiter",
    "",
]


class AgentSpec(BaseModel):
    """Contract for a specialized agent node in the orchestration graph."""

    name: str
    responsibility: str
    reads_state: list[str] = Field(default_factory=list)
    writes_state: list[str] = Field(default_factory=list)
    workflow_agnostic: bool = True
    supports_domain_extension: bool = True


CORE_AGENT_SPECS: dict[str, AgentSpec] = {
    "orchestrator": AgentSpec(
        name="orchestrator",
        responsibility="Classify the request and set workflow_type for the run.",
        reads_state=["user_request", "organization_id", "user_role"],
        writes_state=["workflow_type", "status", "metadata"],
    ),
    "planner": AgentSpec(
        name="planner",
        responsibility="Parse the request into tasks and entity context for the workflow.",
        reads_state=["user_request", "workflow_type", "entities"],
        writes_state=["tasks", "entities", "metadata"],
    ),
    "research": AgentSpec(
        name="research",
        responsibility="Retrieve enterprise records for the active entities via tools.",
        reads_state=["entities", "workflow_type", "metadata"],
        writes_state=["employee_data", "retrieved_data", "entities"],
    ),
    "policy": AgentSpec(
        name="policy",
        responsibility="Evaluate authoritative policy rules for the workflow type.",
        reads_state=["entities", "employee_data", "workflow_type", "metadata"],
        writes_state=["policy_results"],
    ),
    "analysis": AgentSpec(
        name="analysis",
        responsibility="Compare retrieved data, policy findings, and memory context.",
        reads_state=[
            "entities",
            "employee_data",
            "policy_results",
            "retrieved_data",
            "workflow_type",
        ],
        writes_state=["analysis_results"],
    ),
    "decision": AgentSpec(
        name="decision",
        responsibility="Produce a reusable workflow decision and pending actions.",
        reads_state=["analysis_results", "policy_results", "entities", "workflow_type"],
        writes_state=["decision", "confidence", "pending_actions", "requires_human_approval"],
    ),
    "validation": AgentSpec(
        name="validation",
        responsibility="Validate the decision against structured policy and write-tool rules.",
        reads_state=["decision", "analysis_results", "policy_results", "pending_actions"],
        writes_state=["status", "metadata", "errors"],
    ),
    "action": AgentSpec(
        name="action",
        responsibility="Execute approved write actions through the tool layer.",
        reads_state=["decision", "pending_actions", "requires_human_approval", "metadata"],
        writes_state=["completed_actions", "employee_data", "pending_actions", "status"],
    ),
    "response": AgentSpec(
        name="response",
        responsibility="Compose the final response and persist long-term outcome memory.",
        reads_state=["decision", "employee_data", "entities", "metadata", "analysis_results"],
        writes_state=["final_response", "status"],
    ),
}


def get_agent_spec(name: str) -> AgentSpec:
    """Return the contract for a core agent. Raises KeyError if unknown."""

    return CORE_AGENT_SPECS[name]
