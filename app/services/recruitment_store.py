"""In-memory recruitment store: jobs, candidates, shortlists, interviews.

JSON seeds are loaded once per reset and never written back.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from app.services.errors import SimulatedServiceError
from app.services.recruitment_data import (
    load_candidates,
    load_jobs,
    load_recruitment_policy,
)
from app.tools.idempotency import build_idempotency_key


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_key(job_id: str) -> str:
    return job_id.strip().upper()


def _candidate_key(candidate_id: str) -> str:
    return candidate_id.strip().upper()


def _org_matches(record: dict[str, Any], organization_id: str) -> bool:
    if not organization_id:
        return True
    record_org = str(record.get("organization_id") or "")
    return record_org in {"", organization_id}


def _normalize_skills(skills: list[str] | None) -> list[str]:
    return [str(item).strip() for item in (skills or []) if str(item).strip()]


def _skill_set(skills: list[str]) -> set[str]:
    return {item.lower() for item in skills}


class SimulatedRecruitmentStore:
    """Mutable recruitment records for workflow runs."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._candidates: dict[str, dict[str, Any]] = {}
        self._policy: dict[str, Any] = {}
        self._shortlists: dict[str, dict[str, Any]] = {}
        self._interviews: dict[str, dict[str, Any]] = {}
        self._faults: dict[str, int] = {}
        self.reset()

    def reset(self) -> None:
        self._jobs = {
            _job_key(str(job["job_id"])): copy.deepcopy(job) for job in load_jobs()
        }
        self._candidates = {
            _candidate_key(str(item["candidate_id"])): copy.deepcopy(item)
            for item in load_candidates()
        }
        self._policy = copy.deepcopy(load_recruitment_policy())
        self._shortlists = {}
        self._interviews = {}
        self._faults = {}

    def inject_error(self, operation: str, times: int = 1) -> None:
        self._faults[operation] = times

    def _maybe_fault(self, operation: str) -> None:
        remaining = self._faults.get(operation, 0)
        if remaining > 0:
            self._faults[operation] = remaining - 1
            raise SimulatedServiceError(f"Simulated recruitment error during {operation}.")

    def get_job(self, job_id: str, *, organization_id: str = "") -> dict[str, Any] | None:
        self._maybe_fault("get_job")
        job = self._jobs.get(_job_key(job_id))
        if job is None or not _org_matches(job, organization_id):
            return None
        return copy.deepcopy(job)

    def search_jobs(
        self,
        *,
        organization_id: str = "",
        query: str = "",
        status: str | None = "open",
    ) -> list[dict[str, Any]]:
        self._maybe_fault("search_jobs")
        needle = query.strip().lower()
        results: list[dict[str, Any]] = []
        for job in self._jobs.values():
            if not _org_matches(job, organization_id):
                continue
            if status and str(job.get("status") or "") != status:
                continue
            haystack = " ".join(
                [
                    str(job.get("job_id") or ""),
                    str(job.get("title") or ""),
                    str(job.get("department") or ""),
                    " ".join(job.get("required_skills") or []),
                ]
            ).lower()
            if needle and needle not in haystack and not all(
                token in haystack for token in needle.split()
            ):
                continue
            results.append(copy.deepcopy(job))
        return results

    def get_candidate(
        self,
        candidate_id: str,
        *,
        organization_id: str = "",
    ) -> dict[str, Any] | None:
        self._maybe_fault("get_candidate")
        candidate = self._candidates.get(_candidate_key(candidate_id))
        if candidate is None or not _org_matches(candidate, organization_id):
            return None
        return copy.deepcopy(candidate)

    def search_candidates(
        self,
        *,
        organization_id: str = "",
        required_skills: list[str] | None = None,
        application_status: str = "active",
    ) -> list[dict[str, Any]]:
        self._maybe_fault("search_candidates")
        required = _skill_set(_normalize_skills(required_skills))
        results: list[dict[str, Any]] = []
        for candidate in self._candidates.values():
            if not _org_matches(candidate, organization_id):
                continue
            if application_status and candidate.get("application_status") != application_status:
                continue
            # Soft relevance hint only; scoring/policy decide outcomes.
            if required:
                skills = _skill_set(_normalize_skills(candidate.get("skills")))
                candidate = copy.deepcopy(candidate)
                candidate["_skill_overlap"] = sorted(skills & required)
            else:
                candidate = copy.deepcopy(candidate)
            results.append(candidate)
        return results

    def get_recruitment_policy(self, *, organization_id: str = "") -> dict[str, Any]:
        self._maybe_fault("get_recruitment_policy")
        policy = copy.deepcopy(self._policy)
        if organization_id:
            policy["organization_id"] = organization_id
        return policy

    def calculate_candidate_score(
        self,
        *,
        job: dict[str, Any],
        candidate: dict[str, Any],
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("calculate_candidate_score")
        policy = self.get_recruitment_policy(organization_id=organization_id)
        weights = policy.get("weights") or {}
        required = _normalize_skills(job.get("required_skills"))
        preferred = _normalize_skills(job.get("preferred_skills"))
        candidate_skills = _normalize_skills(candidate.get("skills"))
        cand_set = _skill_set(candidate_skills)
        req_set = _skill_set(required)
        pref_set = _skill_set(preferred)

        matched_required = sorted(req_set & cand_set)
        missing_required = sorted(req_set - cand_set)
        matched_preferred = sorted(pref_set & cand_set)
        required_ratio = (len(matched_required) / len(req_set)) if req_set else 1.0
        preferred_ratio = (len(matched_preferred) / len(pref_set)) if pref_set else 0.0

        min_exp = float(job.get("minimum_experience") or 0)
        years = float(candidate.get("experience_years") or 0)
        if min_exp <= 0:
            experience_ratio = 1.0
        else:
            experience_ratio = min(years / min_exp, 1.25) / 1.25

        education_levels = {"high_school": 1, "associate": 2, "bachelor": 3, "master": 4, "phd": 5}
        job_edu = education_levels.get(str(job.get("education") or "bachelor").lower(), 3)
        cand_edu = education_levels.get(str(candidate.get("education") or "").lower(), 0)
        education_ratio = 1.0 if cand_edu >= job_edu else (cand_edu / job_edu if job_edu else 0.0)

        job_location = str(job.get("location") or "").lower()
        cand_location = str(candidate.get("location") or "").lower()
        cand_pref = str(candidate.get("preferred_location") or "").lower()
        if not job_location or job_location in {cand_location, cand_pref}:
            location_ratio = 1.0
        elif "remote" in {job_location, cand_location, cand_pref}:
            location_ratio = 0.8
        else:
            location_ratio = 0.3

        breakdown = {
            "required_skills": round(100 * required_ratio * float(weights.get("required_skills", 0.4)), 2),
            "experience": round(100 * experience_ratio * float(weights.get("experience", 0.25)), 2),
            "education": round(100 * education_ratio * float(weights.get("education", 0.1)), 2),
            "location": round(100 * location_ratio * float(weights.get("location", 0.1)), 2),
            "preferred_skills": round(
                100 * preferred_ratio * float(weights.get("preferred_skills", 0.15)), 2
            ),
        }
        total = round(sum(breakdown.values()), 2)
        return {
            "candidate_id": candidate.get("candidate_id"),
            "job_id": job.get("job_id"),
            "score": total,
            "breakdown": breakdown,
            "matched_required_skills": matched_required,
            "missing_required_skills": missing_required,
            "matched_preferred_skills": matched_preferred,
            "weights": weights,
            "source": "simulated_recruitment_store",
        }

    def validate_recruitment_policy(
        self,
        *,
        job: dict[str, Any],
        candidate: dict[str, Any],
        score_result: dict[str, Any],
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("validate_recruitment_policy")
        policy = self.get_recruitment_policy(organization_id=organization_id)
        rules = policy.get("rules") or {}
        thresholds = policy.get("thresholds") or {}
        violations: list[str] = []
        warnings: list[str] = []

        if rules.get("job_must_be_open") and str(job.get("status") or "") != "open":
            violations.append("Job is not open for recruitment.")
        if rules.get("candidate_must_be_active") and candidate.get("application_status") != "active":
            violations.append("Candidate application is not active.")

        missing = list(score_result.get("missing_required_skills") or [])
        if rules.get("require_all_required_skills_for_shortlist") and missing:
            violations.append(
                "Missing required skills for shortlist: " + ", ".join(missing)
            )

        score = float(score_result.get("score") or 0)
        shortlist_min = float(thresholds.get("shortlist_min_score") or 80)
        review_min = float(thresholds.get("review_min_score") or 60)
        if score < review_min:
            classification = "reject"
        elif score < shortlist_min or missing:
            classification = "review"
            if missing:
                warnings.append("Candidate is below shortlist criteria due to skill gaps.")
            else:
                warnings.append("Candidate score is below the shortlist threshold.")
        else:
            classification = "shortlist"

        if violations:
            # Policy violations cannot be shortlisted even with a high score.
            if classification == "shortlist":
                classification = "review" if score >= review_min else "reject"
            # Treat skill-gap shortlist bans as blockers for shortlist eligibility.
            eligible_for_shortlist = False
        else:
            eligible_for_shortlist = classification == "shortlist"

        return {
            "policy_id": policy.get("policy_id"),
            "candidate_id": candidate.get("candidate_id"),
            "job_id": job.get("job_id"),
            "eligible_for_shortlist": eligible_for_shortlist,
            "classification_hint": classification,
            "violations": violations,
            "warnings": warnings,
            "requires_human_approval": bool(rules.get("human_approval_before_shortlist")),
            "thresholds": thresholds,
            "source": "simulated_recruitment_store",
        }

    def shortlist_candidate(
        self,
        *,
        workflow_id: str,
        job_id: str,
        candidate_id: str,
        organization_id: str = "",
        score: float | None = None,
    ) -> dict[str, Any]:
        self._maybe_fault("shortlist_candidate")
        key = build_idempotency_key(
            capability="recruitment.shortlist",
            workflow_id=workflow_id,
            organization_id=organization_id,
            job_id=_job_key(job_id),
            candidate_id=_candidate_key(candidate_id),
        )
        if key in self._shortlists:
            replay = dict(self._shortlists[key])
            replay["idempotent_replay"] = True
            return replay

        job = self.get_job(job_id, organization_id=organization_id)
        candidate = self.get_candidate(candidate_id, organization_id=organization_id)
        if job is None:
            raise SimulatedServiceError(f"Unknown job {job_id}.")
        if candidate is None:
            raise SimulatedServiceError(f"Unknown candidate {candidate_id}.")

        record = {
            "job_id": _job_key(job_id),
            "candidate_id": _candidate_key(candidate_id),
            "organization_id": organization_id,
            "workflow_id": workflow_id,
            "score": score,
            "status": "shortlisted",
            "shortlisted_at": _utc_now(),
            "source": "simulated_recruitment_store",
            "idempotent_replay": False,
        }
        self._shortlists[key] = dict(record)
        candidate_ref = self._candidates[_candidate_key(candidate_id)]
        candidate_ref["application_status"] = "shortlisted"
        return dict(record)

    def schedule_interview(
        self,
        *,
        workflow_id: str,
        job_id: str,
        candidate_id: str,
        organization_id: str = "",
        slot: str = "next_business_day_10:00",
    ) -> dict[str, Any]:
        self._maybe_fault("schedule_interview")
        key = build_idempotency_key(
            capability="interview.schedule",
            workflow_id=workflow_id,
            organization_id=organization_id,
            job_id=_job_key(job_id),
            candidate_id=_candidate_key(candidate_id),
            slot=slot,
        )
        if key in self._interviews:
            replay = dict(self._interviews[key])
            replay["idempotent_replay"] = True
            return replay

        if self.get_job(job_id, organization_id=organization_id) is None:
            raise SimulatedServiceError(f"Unknown job {job_id}.")
        if self.get_candidate(candidate_id, organization_id=organization_id) is None:
            raise SimulatedServiceError(f"Unknown candidate {candidate_id}.")

        record = {
            "job_id": _job_key(job_id),
            "candidate_id": _candidate_key(candidate_id),
            "organization_id": organization_id,
            "workflow_id": workflow_id,
            "slot": slot,
            "status": "scheduled",
            "scheduled_at": _utc_now(),
            "source": "simulated_recruitment_store",
            "idempotent_replay": False,
        }
        self._interviews[key] = dict(record)
        return dict(record)


_STORE: SimulatedRecruitmentStore | None = None


def get_recruitment_store() -> SimulatedRecruitmentStore:
    global _STORE
    if _STORE is None:
        _STORE = SimulatedRecruitmentStore()
    return _STORE


def reset_recruitment_store() -> SimulatedRecruitmentStore:
    store = get_recruitment_store()
    store.reset()
    return store
