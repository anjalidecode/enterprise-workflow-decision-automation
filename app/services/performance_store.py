"""In-memory performance store: records, goals, policy, reviews, plans.

JSON seeds are loaded once per reset and never written back.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from app.services.errors import SimulatedServiceError
from app.services.performance_data import (
    load_performance_goals,
    load_performance_policy,
    load_performance_records,
)
from app.tools.idempotency import build_idempotency_key


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _employee_key(employee_id: str) -> str:
    return employee_id.strip().upper()


def _org_matches(record: dict[str, Any], organization_id: str) -> bool:
    if not organization_id:
        return True
    record_org = str(record.get("organization_id") or "")
    return record_org in {"", organization_id}


def _goal_achievement_pct(actual: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return round(min(100.0, (actual / target) * 100.0), 2)


def _goal_status(achievement_pct: float, *, completed_min: float, partial_min: float) -> str:
    if achievement_pct >= completed_min:
        return "completed"
    if achievement_pct >= partial_min:
        return "partial"
    return "unmet"


class SimulatedPerformanceStore:
    """Mutable performance records and review writes for workflow runs."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []
        self._goals: list[dict[str, Any]] = []
        self._policy: dict[str, Any] = {}
        self._reviews: dict[str, dict[str, Any]] = {}
        self._plans: dict[str, dict[str, Any]] = {}
        self._statuses: dict[str, dict[str, Any]] = {}
        self._faults: dict[str, int] = {}
        self.reset()

    def reset(self) -> None:
        self._records = [copy.deepcopy(item) for item in load_performance_records()]
        self._goals = [copy.deepcopy(item) for item in load_performance_goals()]
        self._policy = copy.deepcopy(load_performance_policy())
        self._reviews = {}
        self._plans = {}
        self._statuses = {}
        self._faults = {}

    def inject_error(self, operation: str, times: int = 1) -> None:
        self._faults[operation] = times

    def _maybe_fault(self, operation: str) -> None:
        remaining = self._faults.get(operation, 0)
        if remaining > 0:
            self._faults[operation] = remaining - 1
            raise SimulatedServiceError(f"Simulated performance error during {operation}.")

    def get_records(
        self,
        employee_id: str,
        *,
        review_period: str,
        organization_id: str = "",
    ) -> list[dict[str, Any]]:
        self._maybe_fault("get_records")
        key = _employee_key(employee_id)
        results: list[dict[str, Any]] = []
        for item in self._records:
            if _employee_key(str(item.get("employee_id") or "")) != key:
                continue
            if str(item.get("review_period") or "") != review_period:
                continue
            if not _org_matches(item, organization_id):
                continue
            results.append(copy.deepcopy(item))
        return results

    def get_goals(
        self,
        employee_id: str,
        *,
        review_period: str,
        organization_id: str = "",
    ) -> list[dict[str, Any]]:
        self._maybe_fault("get_goals")
        key = _employee_key(employee_id)
        results: list[dict[str, Any]] = []
        for item in self._goals:
            if _employee_key(str(item.get("employee_id") or "")) != key:
                continue
            if str(item.get("review_period") or "") != review_period:
                continue
            if not _org_matches(item, organization_id):
                continue
            results.append(copy.deepcopy(item))
        results.sort(key=lambda row: str(row.get("goal_id") or ""))
        return results

    def calculate_summary(
        self,
        records: list[dict[str, Any]],
        goals: list[dict[str, Any]],
        *,
        employee_id: str = "",
        review_period: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("calculate_summary")
        policy = self.get_policy()
        thresholds = dict(policy.get("thresholds") or {})
        completed_min = float(thresholds.get("completed_goal_min_pct") or 90.0)
        partial_min = float(thresholds.get("partial_goal_min_pct") or 50.0)

        goal_rows: list[dict[str, Any]] = []
        weighted_total = 0.0
        weight_sum = 0.0
        completed: list[dict[str, Any]] = []
        partial: list[dict[str, Any]] = []
        unmet: list[dict[str, Any]] = []

        for goal in goals:
            target = float(goal.get("target") or 0)
            actual = float(goal.get("actual") or 0)
            weight = float(goal.get("weight") or 1.0)
            achievement = _goal_achievement_pct(actual, target)
            status = _goal_status(
                achievement,
                completed_min=completed_min,
                partial_min=partial_min,
            )
            row = {
                "goal_id": goal.get("goal_id"),
                "title": goal.get("title"),
                "category": goal.get("category"),
                "target": target,
                "actual": actual,
                "unit": goal.get("unit"),
                "weight": weight,
                "achievement_pct": achievement,
                "status": status,
            }
            goal_rows.append(row)
            weighted_total += achievement * weight
            weight_sum += weight
            if status == "completed":
                completed.append(row)
            elif status == "partial":
                partial.append(row)
            else:
                unmet.append(row)

        overall = round(weighted_total / weight_sum, 2) if weight_sum else 0.0
        record = records[0] if records else {}
        kpis = dict(record.get("kpis") or {})

        return {
            "employee_id": _employee_key(employee_id) if employee_id else "",
            "review_period": review_period,
            "goal_count": len(goal_rows),
            "completed_count": len(completed),
            "partial_count": len(partial),
            "unmet_count": len(unmet),
            "goal_achievement_pct": overall,
            "goals": goal_rows,
            "completed_goals": completed,
            "partial_goals": partial,
            "unmet_goals": unmet,
            "kpis": kpis,
            "projects": list(record.get("projects") or []),
            "strengths": list(record.get("strengths") or []),
            "improvement_areas": list(record.get("improvement_areas") or []),
            "skill_gaps": list(record.get("skill_gaps") or []),
            "previous_outcome": record.get("previous_outcome"),
            "record_count": len(records),
            "source": "simulated_performance_store",
        }

    def get_policy(self, *, organization_id: str = "") -> dict[str, Any]:
        self._maybe_fault("get_policy")
        policy = copy.deepcopy(self._policy)
        if organization_id:
            policy["organization_id"] = organization_id
        return policy

    def validate_performance_policy(
        self,
        *,
        employee: dict[str, Any],
        performance_summary: dict[str, Any],
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("validate_performance_policy")
        policy = self.get_policy(organization_id=organization_id)
        thresholds = dict(policy.get("thresholds") or {})
        rules = dict(policy.get("rules") or {})
        severity_map = dict(policy.get("severity") or {})

        violations: list[str] = []
        warnings: list[str] = []
        exceptions: list[str] = []

        if rules.get("employee_must_be_active") and employee.get("employment_status") != "active":
            violations.append("Employee must be active for performance review.")

        goal_count = int(performance_summary.get("goal_count") or 0)
        record_count = int(performance_summary.get("record_count") or 0)
        minimum_goals = int(thresholds.get("minimum_goals_required") or 1)
        achievement = float(performance_summary.get("goal_achievement_pct") or 0)
        unmet_count = int(performance_summary.get("unmet_count") or 0)
        strong_min = float(thresholds.get("strong_min_goal_achievement") or 90.0)
        development_min = float(thresholds.get("development_min_goal_achievement") or 70.0)
        concern_min = float(thresholds.get("concern_min_goal_achievement") or 50.0)

        severity = "blocked"
        requires_human_approval = False

        if record_count == 0 or goal_count < minimum_goals:
            severity = "blocked"
            violations.append("Insufficient performance records or goals for the requested period.")
        elif achievement >= strong_min:
            severity = "strong"
        elif achievement >= development_min:
            severity = "development"
            warnings.append(
                f"Goal achievement {achievement}% is below strong threshold {strong_min}%."
            )
        elif achievement >= concern_min:
            severity = "concern"
            warnings.append(
                f"Goal achievement {achievement}% is below development threshold {development_min}%."
            )
        else:
            severity = "escalation"
            violations.append(
                f"Goal achievement {achievement}% is below concern threshold {concern_min}%."
            )
            if unmet_count:
                violations.append(f"Unmet goals ({unmet_count}) require manager/HR review.")

        if severity == "escalation" and rules.get("escalation_requires_human_approval"):
            requires_human_approval = True
        if rules.get("high_impact_requires_human_approval") and severity == "escalation":
            requires_human_approval = True

        if rules.get("no_automatic_disciplinary_action"):
            exceptions.append("Automated disciplinary action is not permitted.")
        if rules.get("no_automatic_termination"):
            exceptions.append("Automatic termination is not permitted.")
        if rules.get("no_automatic_demotion"):
            exceptions.append("Automatic demotion is not permitted.")
        if rules.get("no_automatic_salary_change"):
            exceptions.append("Automatic salary reduction is not permitted.")

        outcome_hint = severity_map.get(severity, severity)
        eligible_for_action = severity in {"development", "concern"} and not requires_human_approval
        if severity == "development" and not rules.get("development_allows_review_and_plan"):
            eligible_for_action = False
        if severity == "concern" and not rules.get("concern_allows_review_and_plan"):
            eligible_for_action = False

        return {
            "policy_id": policy.get("policy_id"),
            "severity": severity,
            "outcome_hint": outcome_hint,
            "eligible_for_action": eligible_for_action,
            "requires_human_approval": requires_human_approval,
            "violations": violations,
            "warnings": warnings,
            "exceptions": exceptions,
            "plan_type": (
                "development"
                if severity == "development"
                else "performance_improvement"
                if severity in {"concern", "escalation"}
                else None
            ),
            "consider_attendance_signals": bool(rules.get("consider_attendance_signals")),
            "thresholds_applied": {
                "strong_min_goal_achievement": strong_min,
                "development_min_goal_achievement": development_min,
                "concern_min_goal_achievement": concern_min,
                "minimum_goals_required": minimum_goals,
            },
            "summary_snapshot": {
                "goal_achievement_pct": achievement,
                "goal_count": goal_count,
                "unmet_count": unmet_count,
                "record_count": record_count,
            },
            "source": "simulated_performance_store",
        }

    def find_employees_needing_support(
        self,
        *,
        review_period: str,
        organization_id: str = "",
        employee_directory: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        self._maybe_fault("find_employees_needing_support")
        directory = employee_directory or []
        findings: list[dict[str, Any]] = []
        seen: set[str] = set()
        for employee in directory:
            employee_id = str(employee.get("employee_id") or "")
            if not employee_id:
                continue
            if organization_id and not _org_matches(employee, organization_id):
                continue
            key = _employee_key(employee_id)
            if key in seen:
                continue
            seen.add(key)
            records = self.get_records(
                employee_id,
                review_period=review_period,
                organization_id=organization_id,
            )
            goals = self.get_goals(
                employee_id,
                review_period=review_period,
                organization_id=organization_id,
            )
            if not records and not goals:
                continue
            summary = self.calculate_summary(
                records,
                goals,
                employee_id=employee_id,
                review_period=review_period,
            )
            validation = self.validate_performance_policy(
                employee=employee,
                performance_summary=summary,
                organization_id=organization_id,
            )
            if validation.get("severity") in {"development", "concern", "escalation"}:
                findings.append(
                    {
                        "employee_id": key,
                        "name": employee.get("name"),
                        "department": employee.get("department"),
                        "severity": validation.get("severity"),
                        "goal_achievement_pct": summary.get("goal_achievement_pct"),
                        "unmet_count": summary.get("unmet_count"),
                        "violations": validation.get("violations") or [],
                        "warnings": validation.get("warnings") or [],
                    }
                )
        findings.sort(key=lambda item: str(item.get("employee_id")))
        return findings

    def create_review(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        reason: str,
        severity: str = "development",
        assignee: str = "",
        organization_id: str = "",
        review_period: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("create_review")
        key = build_idempotency_key(
            capability="performance.review.create",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            channel=severity,
            review_period=review_period,
        )
        existing = self._reviews.get(key)
        if existing is not None:
            replay = copy.deepcopy(existing)
            replay["idempotent_replay"] = True
            return replay

        record = {
            "review_id": f"PR-{_employee_key(employee_id)}-{len(self._reviews) + 1}",
            "employee_id": _employee_key(employee_id),
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "review_period": review_period,
            "reason": reason,
            "severity": severity,
            "assignee": assignee or "manager",
            "status": "open",
            "created_at": _utc_now(),
            "source": "simulated_performance_store",
            "idempotent_replay": False,
        }
        self._reviews[key] = record
        return copy.deepcopy(record)

    def create_improvement_plan(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        reason: str,
        plan_type: str = "performance_improvement",
        focus_areas: list[str] | None = None,
        organization_id: str = "",
        review_period: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("create_improvement_plan")
        key = build_idempotency_key(
            capability="performance.improvement_plan.create",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            channel=plan_type,
            review_period=review_period,
        )
        existing = self._plans.get(key)
        if existing is not None:
            replay = copy.deepcopy(existing)
            replay["idempotent_replay"] = True
            return replay

        record = {
            "plan_id": f"PIP-{_employee_key(employee_id)}-{len(self._plans) + 1}",
            "employee_id": _employee_key(employee_id),
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "review_period": review_period,
            "plan_type": plan_type,
            "reason": reason,
            "focus_areas": list(focus_areas or []),
            "status": "recommended",
            "disciplinary": False,
            "created_at": _utc_now(),
            "source": "simulated_performance_store",
            "idempotent_replay": False,
        }
        self._plans[key] = record
        return copy.deepcopy(record)

    def update_status(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        status: str,
        organization_id: str = "",
        review_period: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("update_status")
        key = build_idempotency_key(
            capability="performance.status.update",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            channel=status,
            review_period=review_period,
        )
        existing = self._statuses.get(key)
        if existing is not None:
            replay = copy.deepcopy(existing)
            replay["idempotent_replay"] = True
            return replay
        record = {
            "employee_id": _employee_key(employee_id),
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "review_period": review_period,
            "status": status,
            "updated_at": _utc_now(),
            "source": "simulated_performance_store",
            "idempotent_replay": False,
        }
        self._statuses[key] = record
        return copy.deepcopy(record)

    def list_reviews(
        self,
        *,
        employee_id: str = "",
        workflow_id: str = "",
        organization_id: str = "",
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for item in self._reviews.values():
            if employee_id and _employee_key(str(item.get("employee_id") or "")) != _employee_key(
                employee_id
            ):
                continue
            if workflow_id and item.get("workflow_id") != workflow_id:
                continue
            if not _org_matches(item, organization_id):
                continue
            results.append(copy.deepcopy(item))
        return results

    def list_plans(
        self,
        *,
        employee_id: str = "",
        workflow_id: str = "",
        organization_id: str = "",
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for item in self._plans.values():
            if employee_id and _employee_key(str(item.get("employee_id") or "")) != _employee_key(
                employee_id
            ):
                continue
            if workflow_id and item.get("workflow_id") != workflow_id:
                continue
            if not _org_matches(item, organization_id):
                continue
            results.append(copy.deepcopy(item))
        return results


_STORE: SimulatedPerformanceStore | None = None


def get_performance_store() -> SimulatedPerformanceStore:
    global _STORE
    if _STORE is None:
        _STORE = SimulatedPerformanceStore()
    return _STORE


def reset_performance_store() -> SimulatedPerformanceStore:
    global _STORE
    _STORE = SimulatedPerformanceStore()
    return _STORE
