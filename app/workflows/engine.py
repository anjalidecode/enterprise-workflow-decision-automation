"""Workflow engine: route, resolve, execute, and package results."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.agents.action import action_agent
from app.agents.response import response_agent
from app.agents.attendance.action import attendance_action_agent
from app.agents.attendance.decision import build_attendance_pending_actions
from app.agents.attendance.response import attendance_response_agent
from app.agents.onboarding.action import onboarding_action_agent
from app.agents.onboarding.response import onboarding_response_agent
from app.agents.performance.action import performance_action_agent
from app.agents.performance.decision import build_performance_pending_actions
from app.agents.performance.response import performance_response_agent
from app.agents.recruitment.action import recruitment_action_agent
from app.agents.recruitment.response import recruitment_response_agent
from app.memory.facade import reset_short_term_memory
from app.orchestration.state import WorkflowState, create_initial_state
from app.workflows.contracts import (
    ApprovalDecision,
    RouterResult,
    WorkflowResult,
)
from app.workflows.errors import UnknownWorkflowError, WorkflowResumeError
from app.workflows.registry import WorkflowRegistry, get_workflow_registry
from app.workflows.results import build_audit_snapshot, build_run_metrics
from app.workflows.router import WorkflowRouter


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _apply_node_patch(state: WorkflowState, patch: dict[str, Any]) -> WorkflowState:
    """Merge a LangGraph-style node patch into a concrete state dict."""

    merged: dict[str, Any] = dict(state)
    for key, value in patch.items():
        if key in {
            "completed_tasks",
            "completed_actions",
            "errors",
            "agent_outputs",
            "tool_executions",
            "memory_accesses",
        }:
            existing = list(merged.get(key) or [])
            if isinstance(value, list):
                existing.extend(value)
            else:
                existing.append(value)
            merged[key] = existing
        else:
            merged[key] = value
    return merged  # type: ignore[return-value]


def _pending_actions_after_approval(working: WorkflowState, decision: dict[str, Any]) -> list[dict[str, Any]]:
    """Build executable write actions after human approval, by workflow type."""

    metadata = working.get("metadata") or {}
    workflow_type = str(working.get("workflow_type") or "")

    if workflow_type == "recruitment":
        job_id = (metadata.get("recruitment_request") or {}).get("job_id") or (
            working.get("entities") or {}
        ).get("job_id")
        shortlist = list(
            metadata.get("shortlist_candidates")
            or (decision.get("entity_refs") or {}).get("shortlist")
            or (working.get("analysis_results") or {}).get("shortlist_candidates")
            or []
        )
        scores = {
            str(item.get("candidate_id")): item
            for item in (working.get("analysis_results") or {}).get("candidate_scores") or []
        }
        actions: list[dict[str, Any]] = []
        for candidate_id in shortlist:
            score = (scores.get(str(candidate_id)) or {}).get("score")
            actions.append(
                {
                    "type": "shortlist_candidate",
                    "job_id": job_id,
                    "candidate_id": candidate_id,
                    "score": score,
                }
            )
            actions.append(
                {
                    "type": "schedule_interview",
                    "job_id": job_id,
                    "candidate_id": candidate_id,
                }
            )
            actions.append(
                {
                    "type": "notify_candidate",
                    "recipient_id": candidate_id,
                    "message": f"You have been shortlisted for job {job_id}. Interview scheduling in progress.",
                }
            )
        if shortlist:
            actions.append(
                {
                    "type": "notify_recruiter",
                    "recipient_id": "RECRUITER-001",
                    "message": (
                        f"Shortlist approved for job {job_id}: {', '.join(str(item) for item in shortlist)}."
                    ),
                }
            )
        return actions

    if workflow_type == "onboarding":
        from app.agents.onboarding.decision import build_onboarding_pending_actions

        analysis = working.get("analysis_results") or {}
        employee_id = str(
            (decision.get("entity_refs") or {}).get("employee_id")
            or (working.get("entities") or {}).get("employee_id")
            or (working.get("employee_data") or {}).get("employee_id")
            or ""
        )
        return build_onboarding_pending_actions(
            employee_id=employee_id,
            analysis=analysis,
            include_privileged=True,
        )

    if workflow_type == "attendance":
        employee_id = str(
            (decision.get("entity_refs") or {}).get("employee_id")
            or (working.get("entities") or {}).get("employee_id")
            or (working.get("employee_data") or {}).get("employee_id")
            or ""
        )
        manager_id = (
            (decision.get("entity_refs") or {}).get("manager_id")
            or (working.get("employee_data") or {}).get("manager")
        )
        severity = str(
            (decision.get("entity_refs") or {}).get("severity")
            or (working.get("metadata") or {}).get("attendance_severity")
            or "escalation"
        )
        rationale = str(decision.get("rationale") or "Attendance review after human approval.")
        return build_attendance_pending_actions(
            employee_id=employee_id,
            manager_id=str(manager_id) if manager_id else None,
            severity=severity if severity in {"warning", "escalation"} else "escalation",
            rationale=rationale,
            include_manager_notify=True,
        )

    if workflow_type == "performance":
        employee_id = str(
            (decision.get("entity_refs") or {}).get("employee_id")
            or (working.get("entities") or {}).get("employee_id")
            or (working.get("employee_data") or {}).get("employee_id")
            or ""
        )
        manager_id = (
            (decision.get("entity_refs") or {}).get("manager_id")
            or (working.get("employee_data") or {}).get("manager")
        )
        severity = str(
            (decision.get("entity_refs") or {}).get("severity")
            or (working.get("metadata") or {}).get("performance_severity")
            or "escalation"
        )
        review_period = str(
            (decision.get("entity_refs") or {}).get("review_period")
            or (working.get("entities") or {}).get("review_period")
            or "2026-Q2"
        )
        plan_type = (
            (decision.get("entity_refs") or {}).get("plan_type")
            or (working.get("metadata") or {}).get("performance_plan_type")
            or "performance_improvement"
        )
        focus_areas = list(
            (decision.get("entity_refs") or {}).get("focus_areas")
            or (working.get("analysis_results") or {}).get("skill_gaps")
            or []
        )
        rationale = str(decision.get("rationale") or "Performance review after human approval.")
        return build_performance_pending_actions(
            employee_id=employee_id,
            manager_id=str(manager_id) if manager_id else None,
            severity=severity if severity in {"development", "concern", "escalation"} else "escalation",
            rationale=rationale,
            review_period=review_period,
            plan_type=str(plan_type) if plan_type else "performance_improvement",
            focus_areas=focus_areas,
            include_manager_notify=True,
        )

    # Default: leave-compatible write actions
    leave_request = dict(metadata.get("leave_request") or {})
    employee_id = (
        leave_request.get("employee_id")
        or decision.get("employee_id")
        or (working.get("entities") or {}).get("employee_id")
    )
    days = leave_request.get("days") or decision.get("requested_days")
    leave_type = leave_request.get("leave_type") or decision.get("leave_type") or "annual"
    return [
        {
            "type": "update_leave_balance",
            "employee_id": employee_id,
            "days": days,
            "leave_type": leave_type,
            "start_date": leave_request.get("start_date"),
        },
        {
            "type": "notify_employee",
            "employee_id": employee_id,
            "message": "Leave request approved after human review.",
        },
    ]


def _unsupported_state(
    user_request: str,
    *,
    organization_id: str,
    user_id: str,
    user_role: str,
    initiated_by: str,
    entities: dict[str, Any] | None,
    router: RouterResult,
) -> WorkflowState:
    state = create_initial_state(
        user_request,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        entities=entities,
        workflow_type="",
    )
    state["status"] = router.status
    state["current_stage"] = "router"
    state["final_response"] = (
        router.unsupported_reason
        or "Request could not be routed to a registered workflow."
    )
    state["errors"] = [state["final_response"]]
    state["metadata"] = {
        "router": router.model_dump(),
    }
    return state


class WorkflowEngine:
    """Platform entrypoint for running and resuming registered workflows."""

    def __init__(
        self,
        registry: WorkflowRegistry | None = None,
        router: WorkflowRouter | None = None,
    ) -> None:
        self._registry = registry or get_workflow_registry()
        self._router = router or WorkflowRouter(self._registry)
        self._checkpoints: dict[str, WorkflowState] = {}

    def run(
        self,
        user_request: str,
        *,
        organization_id: str = "",
        user_id: str = "",
        user_role: str = "",
        initiated_by: str = "",
        workflow_type: str | None = None,
        entities: dict[str, Any] | None = None,
        reset_runtime: bool = True,
        request_id: str | None = None,
    ) -> WorkflowResult:
        started = time.perf_counter()
        completed_at = _utc_now()

        router_result = self._router.classify(
            user_request,
            workflow_type=workflow_type,
        )

        if router_result.status != "routed" or not router_result.workflow_type:
            state = _unsupported_state(
                user_request,
                organization_id=organization_id,
                user_id=user_id,
                user_role=user_role,
                initiated_by=initiated_by or user_id,
                entities=entities,
                router=router_result,
            )
            duration_ms = (time.perf_counter() - started) * 1000
            return WorkflowResult(
                state=dict(state),
                audit=build_audit_snapshot(state, completed_at=completed_at),
                metrics=build_run_metrics(state, duration_ms=duration_ms),
                router=router_result,
            )

        try:
            registered = self._registry.get(router_result.workflow_type)
        except UnknownWorkflowError:
            router_result = RouterResult(
                workflow_type="",
                confidence=0.0,
                matched_hints=router_result.matched_hints,
                unsupported_reason=f"Workflow '{router_result.workflow_type}' is not registered.",
                status="unsupported",
            )
            state = _unsupported_state(
                user_request,
                organization_id=organization_id,
                user_id=user_id,
                user_role=user_role,
                initiated_by=initiated_by or user_id,
                entities=entities,
                router=router_result,
            )
            duration_ms = (time.perf_counter() - started) * 1000
            return WorkflowResult(
                state=dict(state),
                audit=build_audit_snapshot(state, completed_at=completed_at),
                metrics=build_run_metrics(state, duration_ms=duration_ms),
                router=router_result,
            )

        # Short-term memory reset is owned by the leave runner today; engine also
        # resets here so future runners that forget still start clean.
        reset_short_term_memory()

        state = registered.runner(
            user_request,
            reset_runtime=reset_runtime,
            organization_id=organization_id,
            user_id=user_id,
            initiated_by=initiated_by or user_id,
            user_role=user_role,
            request_id=request_id,
            entities=entities,
            workflow_type=router_result.workflow_type,
        )
        completed_at = _utc_now()
        duration_ms = (time.perf_counter() - started) * 1000

        metadata = dict(state.get("metadata") or {})
        metadata["router"] = router_result.model_dump()
        if state.get("requires_human_approval") or state.get("status") == "awaiting_human_approval":
            metadata["approval"] = {
                "status": "awaiting",
                "workflow_id": state.get("workflow_id"),
                "organization_id": state.get("organization_id") or "",
                "workflow_type": state.get("workflow_type") or "",
                "reason": (state.get("decision") or {}).get("rationale") or "",
                "pending_actions": list(state.get("pending_actions") or []),
                "required_role": "manager",
                "created_at": completed_at,
            }
            state = {**state, "metadata": metadata}  # type: ignore[assignment]
            self._checkpoints[str(state["workflow_id"])] = dict(state)  # type: ignore[arg-type]
        else:
            state = {**state, "metadata": metadata}  # type: ignore[assignment]

        result = WorkflowResult(
            state=dict(state),
            audit=build_audit_snapshot(state, completed_at=completed_at),
            metrics=build_run_metrics(state, duration_ms=duration_ms),
            router=router_result,
            spec_version=registered.spec.version,
        )
        return result

    def resume(
        self,
        workflow_id: str,
        approval: ApprovalDecision,
        *,
        state: WorkflowState | None = None,
    ) -> WorkflowResult:
        """Resume a paused awaiting_human_approval run (in-memory for Phase 4A)."""

        started = time.perf_counter()
        checkpoint = state or self._checkpoints.get(workflow_id)
        if checkpoint is None:
            raise WorkflowResumeError(
                f"No in-memory checkpoint found for workflow_id '{workflow_id}'."
            )
        if checkpoint.get("status") != "awaiting_human_approval":
            raise WorkflowResumeError(
                f"Workflow '{workflow_id}' is not awaiting human approval "
                f"(status={checkpoint.get('status')})."
            )

        working: WorkflowState = dict(checkpoint)  # type: ignore[assignment]
        metadata = dict(working.get("metadata") or {})
        decision = dict(working.get("decision") or {})

        if not approval.approved:
            decision["outcome"] = "reject"
            decision["executable"] = False
            decision["requires_human_approval"] = False
            decision["rationale"] = (
                approval.comment
                or decision.get("rationale")
                or "Human reviewer rejected the pending request."
            )
            metadata["approval"] = {
                **(metadata.get("approval") or {}),
                "status": "rejected",
                "decided_by": approval.decided_by,
                "comment": approval.comment,
                "decided_at": _utc_now(),
            }
            working["decision"] = decision
            working["requires_human_approval"] = False
            working["status"] = "completed"
            working["final_response"] = (
                f"Request rejected by human reviewer"
                f"{f' ({approval.decided_by})' if approval.decided_by else ''}."
            )
            working["pending_actions"] = []
            working["metadata"] = metadata
            self._checkpoints.pop(workflow_id, None)
            completed_at = _utc_now()
            duration_ms = (time.perf_counter() - started) * 1000
            return WorkflowResult(
                state=dict(working),
                audit=build_audit_snapshot(working, completed_at=completed_at),
                metrics=build_run_metrics(working, duration_ms=duration_ms),
            )

        # Approved: clear the pause, mark executable, restore write actions, run Action → Response.
        decision["outcome"] = "approve"
        decision["executable"] = True
        decision["requires_human_approval"] = False
        if approval.comment:
            decision["rationale"] = (
                f"{decision.get('rationale') or ''} Human approved: {approval.comment}".strip()
            )
        metadata["approval"] = {
            **(metadata.get("approval") or {}),
            "status": "approved",
            "decided_by": approval.decided_by,
            "comment": approval.comment,
            "decided_at": _utc_now(),
        }
        metadata["route"] = "action"
        validation = dict(metadata.get("validation") or {})
        validation["passed"] = True
        metadata["validation"] = validation

        working["pending_actions"] = _pending_actions_after_approval(working, decision)
        working["decision"] = decision
        working["requires_human_approval"] = False
        working["metadata"] = metadata
        working["status"] = "in_progress"

        if str(working.get("workflow_type") or "") == "recruitment":
            working = _apply_node_patch(working, recruitment_action_agent(working))
            working = _apply_node_patch(working, recruitment_response_agent(working))
        elif str(working.get("workflow_type") or "") == "onboarding":
            working = _apply_node_patch(working, onboarding_action_agent(working))
            working = _apply_node_patch(working, onboarding_response_agent(working))
        elif str(working.get("workflow_type") or "") == "attendance":
            working = _apply_node_patch(working, attendance_action_agent(working))
            working = _apply_node_patch(working, attendance_response_agent(working))
        elif str(working.get("workflow_type") or "") == "performance":
            working = _apply_node_patch(working, performance_action_agent(working))
            working = _apply_node_patch(working, performance_response_agent(working))
        else:
            working = _apply_node_patch(working, action_agent(working))
            working = _apply_node_patch(working, response_agent(working))
        self._checkpoints.pop(workflow_id, None)

        completed_at = _utc_now()
        duration_ms = (time.perf_counter() - started) * 1000
        return WorkflowResult(
            state=dict(working),
            audit=build_audit_snapshot(working, completed_at=completed_at),
            metrics=build_run_metrics(working, duration_ms=duration_ms),
        )


_ENGINE: WorkflowEngine | None = None


def get_workflow_engine() -> WorkflowEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = WorkflowEngine()
    return _ENGINE


def reset_workflow_engine() -> WorkflowEngine:
    global _ENGINE
    from app.workflows.registry import reset_workflow_registry

    reset_workflow_registry()
    _ENGINE = WorkflowEngine()
    return _ENGINE
