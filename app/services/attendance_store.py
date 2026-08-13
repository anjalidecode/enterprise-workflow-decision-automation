"""In-memory attendance store: records, summaries, policy, reviews.

JSON seeds are loaded once per reset and never written back.
"""

from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.services.attendance_data import load_attendance_policy, load_attendance_records
from app.services.errors import SimulatedServiceError
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


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _iter_weekdays(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _max_consecutive(dates: list[date]) -> int:
    if not dates:
        return 0
    ordered = sorted(dates)
    best = 1
    run = 1
    for index in range(1, len(ordered)):
        if (ordered[index] - ordered[index - 1]).days == 1:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best


class SimulatedAttendanceStore:
    """Mutable attendance records and review writes for workflow runs."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []
        self._policy: dict[str, Any] = {}
        self._reviews: dict[str, dict[str, Any]] = {}
        self._statuses: dict[str, dict[str, Any]] = {}
        self._faults: dict[str, int] = {}
        self.reset()

    def reset(self) -> None:
        self._records = [copy.deepcopy(item) for item in load_attendance_records()]
        self._policy = copy.deepcopy(load_attendance_policy())
        self._reviews = {}
        self._statuses = {}
        self._faults = {}

    def inject_error(self, operation: str, times: int = 1) -> None:
        self._faults[operation] = times

    def _maybe_fault(self, operation: str) -> None:
        remaining = self._faults.get(operation, 0)
        if remaining > 0:
            self._faults[operation] = remaining - 1
            raise SimulatedServiceError(f"Simulated attendance error during {operation}.")

    def get_records(
        self,
        employee_id: str,
        *,
        start_date: str,
        end_date: str,
        organization_id: str = "",
    ) -> list[dict[str, Any]]:
        self._maybe_fault("get_records")
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        key = _employee_key(employee_id)
        results: list[dict[str, Any]] = []
        for item in self._records:
            if _employee_key(str(item.get("employee_id") or "")) != key:
                continue
            if not _org_matches(item, organization_id):
                continue
            item_date = _parse_date(str(item.get("date") or ""))
            if start <= item_date <= end:
                results.append(copy.deepcopy(item))
        results.sort(key=lambda row: str(row.get("date") or ""))
        return results

    def calculate_summary(
        self,
        records: list[dict[str, Any]],
        *,
        start_date: str,
        end_date: str,
        employee_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("calculate_summary")
        policy = self.get_policy()
        rules = dict(policy.get("rules") or {})
        present_statuses = set(rules.get("present_statuses") or ["present", "late", "early_departure"])
        late_statuses = set(rules.get("late_statuses") or ["late"])
        absent_statuses = set(rules.get("absent_statuses") or ["absent"])

        start = _parse_date(start_date)
        end = _parse_date(end_date)
        expected_days = _iter_weekdays(start, end)
        by_date = {
            str(item.get("date")): item
            for item in records
            if item.get("date")
        }

        present_days = 0
        absent_days = 0
        late_arrivals = 0
        early_departures = 0
        missing_records = 0
        absent_dates: list[date] = []

        for day in expected_days:
            key = day.isoformat()
            item = by_date.get(key)
            if item is None or str(item.get("status") or "") == "missing":
                missing_records += 1
                continue
            status = str(item.get("status") or "")
            if status in present_statuses:
                present_days += 1
            if status in late_statuses:
                late_arrivals += 1
            if status == "early_departure":
                early_departures += 1
            if status in absent_statuses:
                absent_days += 1
                absent_dates.append(day)

        expected_count = len(expected_days)
        percentage = (
            round((present_days / expected_count) * 100, 2) if expected_count else 0.0
        )
        consecutive_absence = _max_consecutive(absent_dates)

        return {
            "employee_id": _employee_key(employee_id) if employee_id else "",
            "start_date": start_date,
            "end_date": end_date,
            "expected_working_days": expected_count,
            "present_days": present_days,
            "absent_days": absent_days,
            "late_arrivals": late_arrivals,
            "early_departures": early_departures,
            "missing_records": missing_records,
            "attendance_percentage": percentage,
            "consecutive_absence": consecutive_absence,
            "record_count": len(records),
            "source": "simulated_attendance_store",
        }

    def get_policy(self, *, organization_id: str = "") -> dict[str, Any]:
        self._maybe_fault("get_policy")
        policy = copy.deepcopy(self._policy)
        if organization_id:
            policy["organization_id"] = organization_id
        return policy

    def validate_attendance_policy(
        self,
        *,
        employee: dict[str, Any],
        attendance_summary: dict[str, Any],
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("validate_attendance_policy")
        policy = self.get_policy(organization_id=organization_id)
        thresholds = dict(policy.get("thresholds") or {})
        rules = dict(policy.get("rules") or {})
        severity_map = dict(policy.get("severity") or {})

        violations: list[str] = []
        warnings: list[str] = []
        exceptions: list[str] = []

        if rules.get("employee_must_be_active") and employee.get("employment_status") != "active":
            violations.append("Employee must be active for attendance review.")

        percentage = float(attendance_summary.get("attendance_percentage") or 0)
        late_arrivals = int(attendance_summary.get("late_arrivals") or 0)
        consecutive = int(attendance_summary.get("consecutive_absence") or 0)
        missing = int(attendance_summary.get("missing_records") or 0)
        early = int(attendance_summary.get("early_departures") or 0)
        expected = int(attendance_summary.get("expected_working_days") or 0)
        record_count = int(attendance_summary.get("record_count") or 0)

        missing_threshold = int(thresholds.get("missing_records_blocked") or 3)
        normal_pct = float(thresholds.get("min_attendance_percentage_normal") or 90)
        warning_pct = float(thresholds.get("min_attendance_percentage_warning") or 80)
        late_threshold = int(thresholds.get("late_arrival_warning_count") or 5)
        consecutive_threshold = int(thresholds.get("consecutive_absence_escalation") or 3)
        early_threshold = int(thresholds.get("early_departure_warning_count") or 3)

        severity = "normal"
        requires_human_approval = False

        if expected == 0 or (record_count == 0 and missing >= missing_threshold):
            severity = "blocked"
            violations.append("Insufficient attendance records for the requested period.")
        elif missing >= missing_threshold:
            severity = "blocked"
            violations.append(
                f"Missing attendance records ({missing}) meet or exceed threshold ({missing_threshold})."
            )
        else:
            if percentage < warning_pct:
                severity = "escalation"
                violations.append(
                    f"Attendance percentage {percentage}% is below escalation threshold {warning_pct}%."
                )
            elif percentage < normal_pct:
                severity = "warning"
                warnings.append(
                    f"Attendance percentage {percentage}% is below normal threshold {normal_pct}%."
                )

            if consecutive >= consecutive_threshold:
                severity = "escalation"
                violations.append(
                    f"Consecutive absences ({consecutive}) meet or exceed threshold ({consecutive_threshold})."
                )

            if late_arrivals >= late_threshold:
                if severity == "normal":
                    severity = "warning"
                warnings.append(
                    f"Late arrivals ({late_arrivals}) meet or exceed warning threshold ({late_threshold})."
                )

            if early >= early_threshold:
                if severity == "normal":
                    severity = "warning"
                warnings.append(
                    f"Early departures ({early}) meet or exceed warning threshold ({early_threshold})."
                )

        if severity == "escalation" and rules.get("escalation_requires_human_approval"):
            requires_human_approval = True

        outcome_hint = severity_map.get(severity, severity)
        eligible_for_action = severity in {"warning", "escalation"} and severity != "blocked"

        return {
            "policy_id": policy.get("policy_id"),
            "severity": severity,
            "outcome_hint": outcome_hint,
            "eligible_for_action": eligible_for_action and severity == "warning",
            "requires_human_approval": requires_human_approval,
            "violations": violations,
            "warnings": warnings,
            "exceptions": exceptions,
            "thresholds_applied": {
                "min_attendance_percentage_normal": normal_pct,
                "min_attendance_percentage_warning": warning_pct,
                "late_arrival_warning_count": late_threshold,
                "consecutive_absence_escalation": consecutive_threshold,
                "missing_records_blocked": missing_threshold,
            },
            "summary_snapshot": {
                "attendance_percentage": percentage,
                "late_arrivals": late_arrivals,
                "consecutive_absence": consecutive,
                "missing_records": missing,
            },
            "source": "simulated_attendance_store",
        }

    def find_employees_with_issues(
        self,
        *,
        start_date: str,
        end_date: str,
        department: str | None = None,
        organization_id: str = "",
        employee_directory: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        self._maybe_fault("find_employees_with_issues")
        directory = employee_directory or []
        findings: list[dict[str, Any]] = []
        seen: set[str] = set()
        for employee in directory:
            employee_id = str(employee.get("employee_id") or "")
            if not employee_id:
                continue
            if department and str(employee.get("department") or "").lower() != department.lower():
                continue
            if organization_id and not _org_matches(employee, organization_id):
                continue
            key = _employee_key(employee_id)
            if key in seen:
                continue
            seen.add(key)
            records = self.get_records(
                employee_id,
                start_date=start_date,
                end_date=end_date,
                organization_id=organization_id,
            )
            if not records:
                continue
            summary = self.calculate_summary(
                records,
                start_date=start_date,
                end_date=end_date,
                employee_id=employee_id,
            )
            validation = self.validate_attendance_policy(
                employee=employee,
                attendance_summary=summary,
                organization_id=organization_id,
            )
            if validation.get("severity") in {"warning", "escalation", "blocked"}:
                findings.append(
                    {
                        "employee_id": key,
                        "name": employee.get("name"),
                        "department": employee.get("department"),
                        "severity": validation.get("severity"),
                        "attendance_percentage": summary.get("attendance_percentage"),
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
        severity: str = "warning",
        assignee: str = "",
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("create_review")
        key = build_idempotency_key(
            capability="attendance.review.create",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            channel=severity,
        )
        existing = self._reviews.get(key)
        if existing is not None:
            replay = copy.deepcopy(existing)
            replay["idempotent_replay"] = True
            return replay

        record = {
            "review_id": f"AR-{_employee_key(employee_id)}-{len(self._reviews) + 1}",
            "employee_id": _employee_key(employee_id),
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "reason": reason,
            "severity": severity,
            "assignee": assignee or "manager",
            "status": "open",
            "created_at": _utc_now(),
            "source": "simulated_attendance_store",
            "idempotent_replay": False,
        }
        self._reviews[key] = record
        return copy.deepcopy(record)

    def update_status(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        status: str,
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("update_status")
        key = build_idempotency_key(
            capability="attendance.status.update",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            channel=status,
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
            "status": status,
            "updated_at": _utc_now(),
            "source": "simulated_attendance_store",
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


_STORE: SimulatedAttendanceStore | None = None


def get_attendance_store() -> SimulatedAttendanceStore:
    global _STORE
    if _STORE is None:
        _STORE = SimulatedAttendanceStore()
    return _STORE


def reset_attendance_store() -> SimulatedAttendanceStore:
    global _STORE
    _STORE = SimulatedAttendanceStore()
    return _STORE
