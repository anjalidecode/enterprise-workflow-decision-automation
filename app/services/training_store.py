"""In-memory training store: courses, history, skills, policy, plans, enrollments.

JSON seeds are loaded once per reset and never written back.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from app.services.errors import SimulatedServiceError
from app.services.training_data import (
    load_training_courses,
    load_training_history,
    load_training_policy,
    load_training_skills,
)
from app.tools.idempotency import build_idempotency_key

_LEVEL_RANK = {"beginner": 1, "intermediate": 2, "advanced": 3}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _employee_key(employee_id: str) -> str:
    return employee_id.strip().upper()


def _org_matches(record: dict[str, Any], organization_id: str) -> bool:
    if not organization_id:
        return True
    record_org = str(record.get("organization_id") or "")
    return record_org in {"", organization_id}


def _normalize_skill(name: str) -> str:
    return str(name or "").strip().lower()


def _level_rank(level: str) -> int:
    return _LEVEL_RANK.get(str(level or "").strip().lower(), 0)


def _skill_map(skills: list[dict[str, Any]] | list[str]) -> dict[str, int]:
    mapped: dict[str, int] = {}
    for item in skills:
        if isinstance(item, str):
            key = _normalize_skill(item)
            mapped[key] = max(mapped.get(key, 0), 1)
            continue
        key = _normalize_skill(str(item.get("name") or item.get("skill") or ""))
        if not key:
            continue
        mapped[key] = max(mapped.get(key, 0), _level_rank(str(item.get("level") or "beginner")))
    return mapped


class SimulatedTrainingStore:
    """Mutable training catalog, history, and enrollment writes for workflow runs."""

    def __init__(self) -> None:
        self._courses: list[dict[str, Any]] = []
        self._history: list[dict[str, Any]] = []
        self._skills: list[dict[str, Any]] = []
        self._policy: dict[str, Any] = {}
        self._plans: dict[str, dict[str, Any]] = {}
        self._enrollments: dict[str, dict[str, Any]] = {}
        self._statuses: dict[str, dict[str, Any]] = {}
        self._faults: dict[str, int] = {}
        self.reset()

    def reset(self) -> None:
        self._courses = [copy.deepcopy(item) for item in load_training_courses()]
        self._history = [copy.deepcopy(item) for item in load_training_history()]
        self._skills = [copy.deepcopy(item) for item in load_training_skills()]
        self._policy = copy.deepcopy(load_training_policy())
        self._plans = {}
        self._enrollments = {}
        self._statuses = {}
        self._faults = {}

    def inject_error(self, operation: str, times: int = 1) -> None:
        self._faults[operation] = times

    def _maybe_fault(self, operation: str) -> None:
        remaining = self._faults.get(operation, 0)
        if remaining > 0:
            self._faults[operation] = remaining - 1
            raise SimulatedServiceError(f"Simulated training error during {operation}.")

    def get_history(
        self,
        employee_id: str,
        *,
        organization_id: str = "",
    ) -> list[dict[str, Any]]:
        self._maybe_fault("get_history")
        key = _employee_key(employee_id)
        results: list[dict[str, Any]] = []
        for item in self._history:
            if _employee_key(str(item.get("employee_id") or "")) != key:
                continue
            if not _org_matches(item, organization_id):
                continue
            results.append(copy.deepcopy(item))
        results.sort(key=lambda row: str(row.get("record_id") or ""))
        return results

    def get_skills_profile(
        self,
        employee_id: str,
        *,
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("get_skills_profile")
        key = _employee_key(employee_id)
        for item in self._skills:
            if _employee_key(str(item.get("employee_id") or "")) != key:
                continue
            if not _org_matches(item, organization_id):
                continue
            return copy.deepcopy(item)
        return {
            "employee_id": key,
            "organization_id": organization_id,
            "role": "",
            "skills": [],
            "role_requirements": [],
        }

    def get_course(self, course_id: str, *, organization_id: str = "") -> dict[str, Any] | None:
        self._maybe_fault("get_course")
        target = str(course_id or "").strip().upper()
        for item in self._courses:
            if str(item.get("course_id") or "").upper() != target:
                continue
            if not _org_matches(item, organization_id):
                continue
            return copy.deepcopy(item)
        return None

    def search_catalog(
        self,
        *,
        organization_id: str = "",
        skill: str = "",
        query: str = "",
        level: str = "",
    ) -> list[dict[str, Any]]:
        self._maybe_fault("search_catalog")
        skill_key = _normalize_skill(skill)
        query_key = str(query or "").strip().lower()
        level_key = str(level or "").strip().lower()
        results: list[dict[str, Any]] = []
        for item in self._courses:
            if not _org_matches(item, organization_id):
                continue
            course_skills = [_normalize_skill(s) for s in (item.get("skills") or [])]
            haystack = " ".join(
                [
                    str(item.get("course_id") or ""),
                    str(item.get("title") or ""),
                    str(item.get("provider") or ""),
                    " ".join(str(s) for s in (item.get("skills") or [])),
                ]
            ).lower()
            if skill_key and skill_key not in course_skills and skill_key not in haystack:
                continue
            if query_key and query_key not in haystack:
                continue
            if level_key and str(item.get("level") or "").lower() != level_key:
                continue
            results.append(copy.deepcopy(item))
        results.sort(key=lambda row: str(row.get("course_id") or ""))
        return results

    def calculate_skill_gaps(
        self,
        *,
        employee_skills: list[dict[str, Any]] | list[str] | None = None,
        role_requirements: list[dict[str, Any]] | list[str] | None = None,
        performance_context: dict[str, Any] | None = None,
        employee_id: str = "",
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("calculate_skill_gaps")
        skills = list(employee_skills or [])
        requirements = list(role_requirements or [])
        if employee_id and (not skills or not requirements):
            profile = self.get_skills_profile(employee_id, organization_id=organization_id)
            if not skills:
                skills = list(profile.get("skills") or [])
            if not requirements:
                requirements = list(profile.get("role_requirements") or [])

        have = _skill_map(skills)
        need = _skill_map(requirements)
        gaps: list[dict[str, Any]] = []
        for skill_name, required_rank in need.items():
            current_rank = have.get(skill_name, 0)
            if current_rank < required_rank:
                gaps.append(
                    {
                        "skill": skill_name,
                        "required_level": next(
                            (
                                str(item.get("level") or "intermediate")
                                for item in requirements
                                if isinstance(item, dict)
                                and _normalize_skill(str(item.get("name") or "")) == skill_name
                            ),
                            "intermediate",
                        ),
                        "current_level": next(
                            (
                                str(item.get("level") or "none")
                                for item in skills
                                if isinstance(item, dict)
                                and _normalize_skill(str(item.get("name") or "")) == skill_name
                            ),
                            "none",
                        ),
                        "priority": "high" if current_rank == 0 else "medium",
                        "source": "role_requirements",
                    }
                )

        performance_context = performance_context or {}
        for raw in list(performance_context.get("skill_gaps") or []):
            skill_name = _normalize_skill(str(raw))
            if not skill_name:
                continue
            if any(item["skill"] == skill_name for item in gaps):
                continue
            gaps.append(
                {
                    "skill": skill_name,
                    "required_level": "intermediate",
                    "current_level": "none",
                    "priority": "medium",
                    "source": "performance_context",
                }
            )

        priority_rank = {"high": 0, "medium": 1, "low": 2}
        gaps.sort(key=lambda item: (priority_rank.get(str(item.get("priority")), 9), item["skill"]))
        return {
            "employee_id": _employee_key(employee_id) if employee_id else "",
            "employee_skills": copy.deepcopy(skills),
            "role_requirements": copy.deepcopy(requirements),
            "skill_gaps": gaps,
            "gap_count": len(gaps),
            "prioritized_skills": [item["skill"] for item in gaps],
            "source": "simulated_training_store",
        }

    def match_courses_to_gaps(
        self,
        skill_gaps: list[dict[str, Any]],
        *,
        organization_id: str = "",
        exclude_course_ids: set[str] | None = None,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        exclude = {str(item).upper() for item in (exclude_course_ids or set())}
        gap_skills = {_normalize_skill(str(item.get("skill") or "")) for item in skill_gaps}
        gap_skills.discard("")
        matches: list[dict[str, Any]] = []
        for course in self._courses:
            course_id = str(course.get("course_id") or "").upper()
            if course_id in exclude:
                continue
            if not _org_matches(course, organization_id):
                continue
            if str(course.get("status") or "").lower() != "active":
                continue
            course_skills = [_normalize_skill(s) for s in (course.get("skills") or [])]
            covered = sorted(skill for skill in course_skills if skill in gap_skills)
            if not covered:
                continue
            matches.append(
                {
                    **copy.deepcopy(course),
                    "matched_skills": covered,
                    "match_score": len(covered),
                }
            )
        matches.sort(
            key=lambda row: (
                -int(row.get("match_score") or 0),
                float(row.get("cost") or 0),
                str(row.get("course_id") or ""),
            )
        )
        return matches[:max_results]

    def get_policy(self, *, organization_id: str = "") -> dict[str, Any]:
        self._maybe_fault("get_policy")
        policy = copy.deepcopy(self._policy)
        if organization_id:
            policy["organization_id"] = organization_id
        return policy

    def _active_enrollment_count(self, employee_id: str, *, organization_id: str = "") -> int:
        key = _employee_key(employee_id)
        count = 0
        for item in self._history:
            if _employee_key(str(item.get("employee_id") or "")) != key:
                continue
            if not _org_matches(item, organization_id):
                continue
            if str(item.get("status") or "").lower() in {"in_progress", "enrolled"}:
                count += 1
        for item in self._enrollments.values():
            if _employee_key(str(item.get("employee_id") or "")) != key:
                continue
            if not _org_matches(item, organization_id):
                continue
            if str(item.get("status") or "").lower() in {"enrolled", "in_progress"}:
                count += 1
        return count

    def _employee_skill_names(
        self,
        employee_id: str,
        *,
        organization_id: str = "",
        employee_skills: list[Any] | None = None,
    ) -> set[str]:
        names = set(_skill_map(list(employee_skills or [])).keys())
        if employee_id:
            profile = self.get_skills_profile(employee_id, organization_id=organization_id)
            names.update(_skill_map(list(profile.get("skills") or [])).keys())
            for item in self.get_history(employee_id, organization_id=organization_id):
                if str(item.get("status") or "").lower() != "completed":
                    continue
                for skill in item.get("skills_gained") or []:
                    names.add(_normalize_skill(str(skill)))
        return names

    def validate_training_policy(
        self,
        *,
        employee: dict[str, Any],
        course: dict[str, Any] | None = None,
        courses: list[dict[str, Any]] | None = None,
        prerequisites: list[str] | None = None,
        policy: dict[str, Any] | None = None,
        organization_id: str = "",
        employee_skills: list[Any] | None = None,
        estimated_annual_spend: float | None = None,
    ) -> dict[str, Any]:
        self._maybe_fault("validate_training_policy")
        policy_doc = policy or self.get_policy(organization_id=organization_id)
        thresholds = dict(policy_doc.get("thresholds") or {})
        rules = dict(policy_doc.get("rules") or {})
        outcomes = dict(policy_doc.get("outcomes") or {})

        selected_courses = list(courses or [])
        if course:
            selected_courses = [course] + [
                item
                for item in selected_courses
                if str(item.get("course_id")) != str(course.get("course_id"))
            ]
        primary = selected_courses[0] if selected_courses else None

        violations: list[str] = []
        warnings: list[str] = []
        exceptions: list[str] = []
        requires_human_approval = False
        approval_level = None
        outcome_hint = outcomes.get("recommend", "recommend")
        severity = "recommend"

        employee_id = str(employee.get("employee_id") or "")
        if rules.get("employee_must_be_active") and employee.get("employment_status") != "active":
            violations.append("Employee must be active for training enrollment.")
            severity = "blocked"
            outcome_hint = outcomes.get("blocked", "blocked")

        if not primary:
            violations.append("No training course selected for policy validation.")
            severity = "blocked"
            outcome_hint = outcomes.get("blocked", "blocked")
            return {
                "policy_id": policy_doc.get("policy_id"),
                "severity": severity,
                "outcome_hint": outcome_hint,
                "eligible_for_action": False,
                "requires_human_approval": False,
                "approval_level": None,
                "violations": violations,
                "warnings": warnings,
                "exceptions": exceptions,
                "primary_course_id": None,
                "thresholds_applied": thresholds,
                "source": "simulated_training_store",
            }

        course_status = str(primary.get("status") or "").lower()
        if rules.get("course_must_be_active") and course_status != "active":
            violations.append(f"Course {primary.get('course_id')} is inactive.")
            severity = "blocked"
            outcome_hint = outcomes.get("blocked", "blocked")
        if rules.get("inactive_course_blocks_enrollment") and course_status == "inactive":
            if f"Course {primary.get('course_id')} is inactive." not in violations:
                violations.append(f"Course {primary.get('course_id')} is inactive.")
            severity = "blocked"
            outcome_hint = outcomes.get("blocked", "blocked")

        seats = primary.get("seats_available")
        if seats is not None and int(seats) <= 0:
            violations.append(f"Course {primary.get('course_id')} has no available seats.")
            severity = "blocked"
            outcome_hint = outcomes.get("blocked", "blocked")

        required_prereqs = [
            str(item) for item in (prerequisites if prerequisites is not None else primary.get("prerequisites") or [])
        ]
        if rules.get("prerequisites_required") and required_prereqs:
            owned = self._employee_skill_names(
                employee_id,
                organization_id=organization_id,
                employee_skills=employee_skills,
            )
            missing = [
                prereq
                for prereq in required_prereqs
                if _normalize_skill(prereq) not in owned
            ]
            if missing:
                violations.append(
                    f"Missing prerequisites for {primary.get('course_id')}: {', '.join(missing)}."
                )
                severity = "blocked"
                outcome_hint = outcomes.get("blocked", "blocked")

        cost = float(primary.get("cost") or 0)
        manager_cost = float(thresholds.get("manager_approval_cost") or 500)
        hr_cost = float(thresholds.get("hr_approval_cost") or 1500)
        if severity != "blocked":
            if rules.get("high_cost_requires_hr_approval") and cost >= hr_cost:
                requires_human_approval = True
                approval_level = "hr_manager"
                severity = "pending_approval"
                outcome_hint = outcomes.get("pending_approval", "pending_approval")
                warnings.append(
                    f"Course cost {cost} exceeds HR approval threshold {hr_cost}."
                )
            elif rules.get("cost_requires_manager_approval") and cost >= manager_cost:
                requires_human_approval = True
                approval_level = "manager"
                severity = "pending_approval"
                outcome_hint = outcomes.get("pending_approval", "pending_approval")
                warnings.append(
                    f"Course cost {cost} exceeds manager approval threshold {manager_cost}."
                )
            else:
                severity = "ready"
                outcome_hint = outcomes.get("ready", "ready")

        if rules.get("enforce_concurrent_enrollment_limit") and employee_id:
            max_concurrent = int(thresholds.get("max_concurrent_enrollments") or 2)
            active = self._active_enrollment_count(employee_id, organization_id=organization_id)
            if active >= max_concurrent and severity != "blocked":
                violations.append(
                    f"Employee already has {active} active enrollment(s); "
                    f"maximum concurrent courses is {max_concurrent}."
                )
                severity = "blocked"
                outcome_hint = outcomes.get("blocked", "blocked")
                requires_human_approval = False

        if rules.get("enforce_annual_budget") and estimated_annual_spend is not None:
            budget = float(thresholds.get("annual_training_budget") or 3000)
            if float(estimated_annual_spend) + cost > budget and severity != "blocked":
                warnings.append(
                    f"Estimated spend {float(estimated_annual_spend) + cost} may exceed "
                    f"annual training budget {budget}."
                )
                if not requires_human_approval:
                    requires_human_approval = True
                    approval_level = approval_level or "manager"
                    severity = "pending_approval"
                    outcome_hint = outcomes.get("pending_approval", "pending_approval")

        if rules.get("no_automatic_high_impact_employment_action"):
            exceptions.append("Automatic high-impact employment actions are not permitted.")

        eligible_for_action = severity == "ready" and not requires_human_approval and not violations
        return {
            "policy_id": policy_doc.get("policy_id"),
            "severity": severity,
            "outcome_hint": outcome_hint,
            "eligible_for_action": eligible_for_action,
            "requires_human_approval": requires_human_approval,
            "approval_level": approval_level,
            "violations": violations,
            "warnings": warnings,
            "exceptions": exceptions,
            "primary_course_id": primary.get("course_id"),
            "primary_course_cost": cost,
            "thresholds_applied": {
                "manager_approval_cost": manager_cost,
                "hr_approval_cost": hr_cost,
                "max_concurrent_enrollments": int(thresholds.get("max_concurrent_enrollments") or 2),
                "annual_training_budget": float(thresholds.get("annual_training_budget") or 3000),
            },
            "source": "simulated_training_store",
        }

    def create_plan(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        course_ids: list[str],
        skill_gaps: list[str] | None = None,
        reason: str = "",
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("create_plan")
        key = build_idempotency_key(
            capability="training.plan.create",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            channel=",".join(sorted(str(item).upper() for item in course_ids)),
        )
        existing = self._plans.get(key)
        if existing is not None:
            replay = copy.deepcopy(existing)
            replay["idempotent_replay"] = True
            return replay

        record = {
            "plan_id": f"TP-{_employee_key(employee_id)}-{len(self._plans) + 1}",
            "employee_id": _employee_key(employee_id),
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "course_ids": [str(item).upper() for item in course_ids],
            "skill_gaps": list(skill_gaps or []),
            "reason": reason,
            "status": "created",
            "created_at": _utc_now(),
            "source": "simulated_training_store",
            "idempotent_replay": False,
        }
        self._plans[key] = record
        return copy.deepcopy(record)

    def create_enrollment(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        course_id: str,
        organization_id: str = "",
        reason: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("create_enrollment")
        course = self.get_course(course_id, organization_id=organization_id)
        if course is None:
            raise SimulatedServiceError(f"Course {course_id} not found.")
        key = build_idempotency_key(
            capability="training.enrollment.create",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            channel=str(course_id).upper(),
        )
        existing = self._enrollments.get(key)
        if existing is not None:
            replay = copy.deepcopy(existing)
            replay["idempotent_replay"] = True
            return replay

        record = {
            "enrollment_id": f"EN-{_employee_key(employee_id)}-{str(course_id).upper()}",
            "employee_id": _employee_key(employee_id),
            "course_id": str(course_id).upper(),
            "course_title": course.get("title"),
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "reason": reason,
            "status": "enrolled",
            "created_at": _utc_now(),
            "source": "simulated_training_store",
            "idempotent_replay": False,
        }
        self._enrollments[key] = record
        # Reduce available seats for subsequent checks in the same run.
        for item in self._courses:
            if str(item.get("course_id") or "").upper() == str(course_id).upper():
                seats = item.get("seats_available")
                if seats is not None and int(seats) > 0:
                    item["seats_available"] = int(seats) - 1
                break
        return copy.deepcopy(record)

    def update_status(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        status: str,
        course_id: str = "",
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("update_status")
        key = build_idempotency_key(
            capability="training.status.update",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            channel=f"{status}:{str(course_id).upper()}",
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
            "course_id": str(course_id).upper() if course_id else "",
            "status": status,
            "updated_at": _utc_now(),
            "source": "simulated_training_store",
            "idempotent_replay": False,
        }
        self._statuses[key] = record
        return copy.deepcopy(record)

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

    def list_enrollments(
        self,
        *,
        employee_id: str = "",
        workflow_id: str = "",
        organization_id: str = "",
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for item in self._enrollments.values():
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


_STORE: SimulatedTrainingStore | None = None


def get_training_store() -> SimulatedTrainingStore:
    global _STORE
    if _STORE is None:
        _STORE = SimulatedTrainingStore()
    return _STORE


def reset_training_store() -> SimulatedTrainingStore:
    global _STORE
    _STORE = SimulatedTrainingStore()
    return _STORE
