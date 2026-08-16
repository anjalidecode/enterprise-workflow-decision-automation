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
from app.agents.training.action import training_action_agent
from app.agents.training.decision import build_training_pending_actions
from app.agents.training.response import training_response_agent
from app.agents.offboarding.action import offboarding_action_agent
from app.agents.offboarding.decision import build_offboarding_pending_actions
from app.agents.offboarding.response import offboarding_response_agent
from app.agents.hr_services.service_action import service_action_agent
from app.agents.hr_services.service_decision import build_hr_services_pending_actions
from app.agents.hr_services.service_response import service_response_agent
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

    if workflow_type == "training":
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
        primary = dict(
            (working.get("metadata") or {}).get("recommended_course")
            or (working.get("analysis_results") or {}).get("recommended_course")
            or {}
        )
        if not primary.get("course_id"):
            course_id = (
                (decision.get("entity_refs") or {}).get("course_id")
                or (working.get("metadata") or {}).get("recommended_course_id")
            )
            if course_id:
                primary = {"course_id": course_id, "title": str(course_id)}
        alternatives = list(
            (working.get("metadata") or {}).get("alternative_courses")
            or (working.get("analysis_results") or {}).get("alternative_courses")
            or []
        )
        skill_gaps = list(
            (decision.get("entity_refs") or {}).get("skill_gaps")
            or (working.get("metadata") or {}).get("skill_gaps")
            or [
                str(item.get("skill") or item)
                for item in ((working.get("analysis_results") or {}).get("skill_gaps") or [])
            ]
        )
        rationale = str(decision.get("rationale") or "Training enrollment after human approval.")
        return build_training_pending_actions(
            employee_id=employee_id,
            manager_id=str(manager_id) if manager_id else None,
            primary_course=primary or None,
            alternative_courses=alternatives,
            skill_gaps=skill_gaps,
            rationale=rationale,
            include_manager_notify=True,
        )

    if workflow_type == "offboarding":
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
        analysis = dict(working.get("analysis_results") or {})
        rationale = str(decision.get("rationale") or "Offboarding preparation after human approval.")
        return build_offboarding_pending_actions(
            employee_id=employee_id,
            manager_id=str(manager_id) if manager_id else None,
            analysis=analysis,
            rationale=rationale,
            include_privileged=True,
            include_standard_access_revoke=True,
        )

    if workflow_type == "hr_services":
        employee_id = str(
            (decision.get("entity_refs") or {}).get("employee_id")
            or (working.get("entities") or {}).get("employee_id")
            or (working.get("employee_data") or {}).get("employee_id")
            or ""
        )
        analysis = dict(working.get("analysis_results") or {})
        category = str(
            (decision.get("entity_refs") or {}).get("category")
            or analysis.get("category")
            or "general_hr"
        )
        rationale = str(decision.get("rationale") or "HR services request after human approval.")
        return build_hr_services_pending_actions(
            employee_id=employee_id,
            category=category,
            analysis=analysis,
            rationale=rationale,
            include_approval_actions=True,
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
    metadata: dict[str, Any] | None = None,
    status: str | None = None,
    final_response: str | None = None,
    record_error: bool = True,
) -> WorkflowState:
    state = create_initial_state(
        user_request,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        entities=entities,
        workflow_type=router.workflow_type or "",
    )
    resolved_status = status or router.status
    state["status"] = resolved_status
    state["current_stage"] = "router"
    state["final_response"] = (
        final_response
        or router.unsupported_reason
        or "Request could not be routed to a registered workflow."
    )
    state["errors"] = [state["final_response"]] if record_error else []
    extra = dict(metadata or {})
    extra["router"] = router.model_dump()
    state["metadata"] = extra
    return state


def _safe_llm_metadata(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    allowed = {
        "provider",
        "model",
        "operation",
        "status",
        "duration_ms",
        "token_usage",
        "error_type",
    }
    return {key: payload[key] for key in allowed if key in payload and payload[key] not in (None, "")}


def _merge_understood_entities(
    base: dict[str, Any] | None,
    extracted: dict[str, Any],
    *,
    user_role: str,
) -> dict[str, Any]:
    merged = dict(base or {})
    jwt_employee = str(merged.get("employee_id") or "").strip()
    for key, value in extracted.items():
        if value in (None, "", []):
            continue
        if key == "employee_id" and (user_role or "").lower() == "employee" and jwt_employee:
            continue
        if key not in merged or merged.get(key) in (None, "", []):
            merged[key] = value
    if extracted.get("duration_days") and not merged.get("days"):
        merged["days"] = extracted["duration_days"]
    if (user_role or "").lower() == "employee" and jwt_employee:
        merged["employee_id"] = jwt_employee
    return merged


class WorkflowEngine:
    """Platform entrypoint for running and resuming registered workflows."""

    def __init__(
        self,
        registry: WorkflowRegistry | None = None,
        router: WorkflowRouter | None = None,
        *,
        persist_result: Any | None = None,
        load_checkpoint: Any | None = None,
    ) -> None:
        self._registry = registry or get_workflow_registry()
        self._router = router or WorkflowRouter(self._registry)
        self._checkpoints: dict[str, WorkflowState] = {}
        # Optional Module 5C hooks — do not require PostgreSQL for unit runners.
        self._persist_result = persist_result
        self._load_checkpoint = load_checkpoint

    def _maybe_persist(self, result: WorkflowResult) -> WorkflowResult:
        if self._persist_result is None:
            return result
        self._persist_result(result)
        return result

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

        from app.llm.models import GroundedResponseInput, UserContext
        from app.llm.understanding import public_understanding, understand_request
        from app.llm.responses import generate_grounded_response

        explicit_type = (workflow_type or "").strip() or None
        user_context = UserContext(
            role=user_role or "",
            employee_id=str((entities or {}).get("employee_id") or ""),
            organization_id=organization_id or "",
            user_id=user_id or "",
        )
        understanding = understand_request(
            user_request,
            user=user_context,
            explicit_workflow_type=explicit_type,
            skip_llm=bool(explicit_type),
        )
        public = public_understanding(understanding).model_dump()
        llm_trace = {
            "provider": understanding.provider,
            "model": "",
            "operation": "understand",
            "status": "success",
        }
        if understanding.provider == "gemini":
            from app.llm.factory import get_llm_client

            llm_trace["model"] = get_llm_client().model

        merged_entities = _merge_understood_entities(
            entities,
            understanding.entities.model_dump(exclude_none=True),
            user_role=user_role,
        )

        if not explicit_type and understanding.request_kind == "unsupported":
            router_result = RouterResult(
                workflow_type="",
                confidence=understanding.confidence,
                matched_hints=[],
                unsupported_reason=understanding.reason or "Request is outside WorkSphere AI scope.",
                status="unsupported",
            )
            state = _unsupported_state(
                user_request,
                organization_id=organization_id,
                user_id=user_id,
                user_role=user_role,
                initiated_by=initiated_by or user_id,
                entities=merged_entities,
                router=router_result,
                metadata={"request_understanding": public, "llm": _safe_llm_metadata(llm_trace)},
                status="unsupported",
                final_response=understanding.reason,
                record_error=True,
            )
            duration_ms = (time.perf_counter() - started) * 1000
            return self._maybe_persist(
                WorkflowResult(
                    state=dict(state),
                    audit=build_audit_snapshot(state, completed_at=completed_at),
                    metrics=build_run_metrics(state, duration_ms=duration_ms),
                    router=router_result,
                )
            )

        if not explicit_type and understanding.needs_clarification:
            router_result = RouterResult(
                workflow_type=understanding.workflow_type,
                confidence=understanding.confidence,
                matched_hints=[],
                unsupported_reason=understanding.clarification_question,
                status="needs_clarification",
            )
            state = _unsupported_state(
                user_request,
                organization_id=organization_id,
                user_id=user_id,
                user_role=user_role,
                initiated_by=initiated_by or user_id,
                entities=merged_entities,
                router=router_result,
                metadata={"request_understanding": public, "llm": _safe_llm_metadata(llm_trace)},
                status="needs_clarification",
                final_response=understanding.clarification_question,
                record_error=False,
            )
            duration_ms = (time.perf_counter() - started) * 1000
            return self._maybe_persist(
                WorkflowResult(
                    state=dict(state),
                    audit=build_audit_snapshot(state, completed_at=completed_at),
                    metrics=build_run_metrics(state, duration_ms=duration_ms),
                    router=router_result,
                )
            )

        routed_type = explicit_type or (understanding.workflow_type or None)
        router_result = self._router.classify(
            user_request,
            workflow_type=routed_type,
        )

        if router_result.status != "routed" or not router_result.workflow_type:
            state = _unsupported_state(
                user_request,
                organization_id=organization_id,
                user_id=user_id,
                user_role=user_role,
                initiated_by=initiated_by or user_id,
                entities=merged_entities,
                router=router_result,
                metadata={"request_understanding": public, "llm": _safe_llm_metadata(llm_trace)},
            )
            duration_ms = (time.perf_counter() - started) * 1000
            return self._maybe_persist(
                WorkflowResult(
                    state=dict(state),
                    audit=build_audit_snapshot(state, completed_at=completed_at),
                    metrics=build_run_metrics(state, duration_ms=duration_ms),
                    router=router_result,
                )
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
                entities=merged_entities,
                router=router_result,
                metadata={"request_understanding": public, "llm": _safe_llm_metadata(llm_trace)},
            )
            duration_ms = (time.perf_counter() - started) * 1000
            return self._maybe_persist(
                WorkflowResult(
                    state=dict(state),
                    audit=build_audit_snapshot(state, completed_at=completed_at),
                    metrics=build_run_metrics(state, duration_ms=duration_ms),
                    router=router_result,
                )
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
            entities=merged_entities,
            workflow_type=router_result.workflow_type,
        )
        completed_at = _utc_now()
        duration_ms = (time.perf_counter() - started) * 1000

        metadata = dict(state.get("metadata") or {})
        metadata["router"] = router_result.model_dump()
        metadata["request_understanding"] = public
        metadata["llm"] = _safe_llm_metadata(llm_trace)

        if understanding.provider == "gemini" and state.get("final_response"):
            decision = state.get("decision") or {}
            rewritten, respond_call = generate_grounded_response(
                GroundedResponseInput(
                    workflow_type=str(state.get("workflow_type") or ""),
                    status=str(state.get("status") or ""),
                    outcome=str(decision.get("outcome") or ""),
                    rationale=str(decision.get("rationale") or ""),
                    blockers=list(decision.get("blockers") or []),
                    warnings=list(decision.get("warnings") or []),
                    evidence=list(decision.get("evidence") or []),
                    requires_human_approval=bool(state.get("requires_human_approval")),
                    deterministic_response=str(state.get("final_response") or ""),
                )
            )
            if rewritten:
                state = {**state, "final_response": rewritten}  # type: ignore[assignment]
            if respond_call is not None:
                metadata["llm_response"] = _safe_llm_metadata(
                    {
                        "provider": respond_call.provider,
                        "model": respond_call.model,
                        "operation": "respond",
                        "status": respond_call.status,
                        "duration_ms": respond_call.duration_ms,
                        "token_usage": respond_call.usage.model_dump(),
                        "error_type": respond_call.error_type,
                    }
                )
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
        return self._maybe_persist(result)

    def resume(
        self,
        workflow_id: str,
        approval: ApprovalDecision,
        *,
        state: WorkflowState | None = None,
        organization_id: str = "",
    ) -> WorkflowResult:
        """Resume a paused awaiting_human_approval run.

        Prefer the in-process checkpoint. When missing, load the persisted
        approval checkpoint from PostgreSQL (business/approval state). This is
        not full LangGraph graph checkpoint reconstruction.
        """

        started = time.perf_counter()
        checkpoint = state or self._checkpoints.get(workflow_id)
        if checkpoint is None and self._load_checkpoint is not None:
            org = organization_id.strip()
            if org:
                loaded = self._load_checkpoint(workflow_id, organization_id=org)
                if isinstance(loaded, dict):
                    checkpoint = loaded  # type: ignore[assignment]
        if checkpoint is None:
            raise WorkflowResumeError(
                f"No approval checkpoint found for workflow_id '{workflow_id}'."
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
            return self._maybe_persist(
                WorkflowResult(
                    state=dict(working),
                    audit=build_audit_snapshot(working, completed_at=completed_at),
                    metrics=build_run_metrics(working, duration_ms=duration_ms),
                )
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
        elif str(working.get("workflow_type") or "") == "training":
            working = _apply_node_patch(working, training_action_agent(working))
            working = _apply_node_patch(working, training_response_agent(working))
        elif str(working.get("workflow_type") or "") == "offboarding":
            working = _apply_node_patch(working, offboarding_action_agent(working))
            working = _apply_node_patch(working, offboarding_response_agent(working))
        elif str(working.get("workflow_type") or "") == "hr_services":
            working = _apply_node_patch(working, service_action_agent(working))
            working = _apply_node_patch(working, service_response_agent(working))
        else:
            working = _apply_node_patch(working, action_agent(working))
            working = _apply_node_patch(working, response_agent(working))
        self._checkpoints.pop(workflow_id, None)

        completed_at = _utc_now()
        duration_ms = (time.perf_counter() - started) * 1000
        return self._maybe_persist(
            WorkflowResult(
                state=dict(working),
                audit=build_audit_snapshot(working, completed_at=completed_at),
                metrics=build_run_metrics(working, duration_ms=duration_ms),
            )
        )


_ENGINE: WorkflowEngine | None = None


def _default_persist_result(result: WorkflowResult) -> None:
    from app.config.settings import get_settings
    from app.database.persistence import PersistenceService
    from app.database.session import session_scope

    if not get_settings().has_database_url:
        return
    with session_scope() as session:
        PersistenceService(session).persist_workflow_result(result)


def _default_load_checkpoint(workflow_id: str, *, organization_id: str) -> dict[str, Any] | None:
    from app.config.settings import get_settings
    from app.database.persistence import PersistenceService
    from app.database.session import session_scope

    if not get_settings().has_database_url:
        return None
    with session_scope() as session:
        return PersistenceService(session).load_approval_checkpoint(
            workflow_id,
            organization_id=organization_id,
        )


def get_workflow_engine(*, with_persistence: bool | None = None) -> WorkflowEngine:
    """Return process WorkflowEngine.

    Persistence hooks attach when DATABASE_URL is configured (API / integration).
    Pure unit tests call reset_workflow_engine() which starts without requiring DB.
    """

    global _ENGINE
    if _ENGINE is None:
        from app.config.settings import get_settings

        enable = with_persistence
        if enable is None:
            enable = get_settings().has_database_url
        if enable:
            _ENGINE = WorkflowEngine(
                persist_result=_default_persist_result,
                load_checkpoint=_default_load_checkpoint,
            )
        else:
            _ENGINE = WorkflowEngine()
    return _ENGINE


def reset_workflow_engine(*, with_persistence: bool = False) -> WorkflowEngine:
    global _ENGINE
    from app.workflows.registry import reset_workflow_registry

    reset_workflow_registry()
    if with_persistence:
        _ENGINE = WorkflowEngine(
            persist_result=_default_persist_result,
            load_checkpoint=_default_load_checkpoint,
        )
    else:
        _ENGINE = WorkflowEngine()
    return _ENGINE
