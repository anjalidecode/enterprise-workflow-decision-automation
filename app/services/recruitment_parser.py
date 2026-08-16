"""Parse recruitment requests into job identifiers (deterministic, no LLM)."""

from __future__ import annotations

import re
from typing import Any


_JOB_ID_RE = re.compile(r"\b(J\d{3})\b", re.IGNORECASE)

_TITLE_HINTS: list[tuple[str, str]] = [
    ("python backend", "J001"),
    ("backend developer", "J001"),
    ("python developer", "J001"),
    ("fastapi", "J001"),
    ("frontend developer", "J002"),
    ("front-end developer", "J002"),
    ("react developer", "J002"),
]


def parse_recruitment_request(user_request: str) -> dict[str, Any]:
    """Extract job_id / title hints from a business recruitment request."""

    text = user_request.strip()
    lowered = text.lower()
    job_id = None
    match = _JOB_ID_RE.search(text)
    if match:
        job_id = match.group(1).upper()
    else:
        for hint, mapped in _TITLE_HINTS:
            if hint in lowered:
                job_id = mapped
                break
        if job_id is None and "python" in lowered and any(
            token in lowered for token in ("candidate", "applicant", "shortlist", "backend")
        ):
            job_id = "J001"

    return {
        "job_id": job_id,
        "query": text,
        "wants_shortlist": any(
            token in lowered for token in ("shortlist", "interview", "hire", "recruit")
        ),
    }
