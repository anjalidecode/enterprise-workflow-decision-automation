"""Job Research Agent: retrieve job requisition via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def job_research_agent(state: WorkflowState) -> dict[str, Any]:
    entities = dict(state.get("entities") or {})
    job_id = entities.get("job_id")
    patches: list[dict[str, Any]] = []
    job: dict[str, Any] | None = None
    errors: list[str] = []

    if job_id:
        result, patch = invoke_tool(
            state,
            agent="job_research",
            name="get_job",
            payload={"job_id": job_id},
        )
        patches.append(patch)
        if result.success and (result.data or {}).get("found"):
            job = (result.data or {}).get("job")
        elif result.success:
            errors.append(f"Job {job_id} was not found.")
        else:
            errors.append(result.error_message or "get_job failed.")
    else:
        query = entities.get("query") or state.get("user_request") or ""
        result, patch = invoke_tool(
            state,
            agent="job_research",
            name="search_jobs",
            payload={"query": query},
        )
        patches.append(patch)
        jobs = (result.data or {}).get("jobs") or []
        if result.success and jobs:
            job = jobs[0]
            job_id = job.get("job_id")
        elif result.success:
            errors.append("No matching open jobs were found.")
        else:
            errors.append(result.error_message or "search_jobs failed.")

    entities = merge_entities(
        state,
        job_id=job_id,
        job_title=(job or {}).get("title"),
        department=(job or {}).get("department"),
    )
    retrieved = dict(state.get("retrieved_data") or {})
    retrieved["job"] = job
    retrieved["job_found"] = job is not None

    _, memory_patch = append_short_term(
        {**state, "entities": entities},
        agent="job_research",
        content=(
            f"Job research found={job is not None} "
            f"job_id={job_id or 'n/a'} title={(job or {}).get('title') or 'n/a'}."
        ),
    )
    patches.append(memory_patch)

    summary = (
        f"Retrieved job {(job or {}).get('title')} ({job_id})."
        if job
        else "Job research did not resolve a job requisition."
    )
    return node_update(
        "job_research",
        summary,
        entities=entities,
        retrieved_data=retrieved,
        errors=errors,
        **combine_patches(*patches),
    )
