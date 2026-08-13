"""Exit details research: resignation, assets, access, handover via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def exit_details_research_agent(state: WorkflowState) -> dict[str, Any]:
    request = (state.get("metadata") or {}).get("offboarding_request") or {}
    employee = state.get("employee_data") or {}
    employee_id = str(
        request.get("employee_id")
        or employee.get("employee_id")
        or (state.get("entities") or {}).get("employee_id")
        or ""
    )
    patches: list[dict[str, Any]] = []
    errors: list[str] = []
    exit_record: dict[str, Any] = {}
    assets: list[dict[str, Any]] = []
    handover: dict[str, Any] = {}

    if employee_id:
        exit_result, exit_patch = invoke_tool(
            state,
            agent="exit_details_research",
            name="get_offboarding_exit",
            payload={"employee_id": employee_id},
        )
        patches.append(exit_patch)
        if exit_result.success and exit_result.data:
            exit_payload = dict(exit_result.data)
            handover = dict(exit_payload.pop("handover", None) or {})
            exit_record = exit_payload
        else:
            errors.append(exit_result.error_message or "get_offboarding_exit failed.")

        assets_result, assets_patch = invoke_tool(
            state,
            agent="exit_details_research",
            name="list_offboarding_assets",
            payload={"employee_id": employee_id},
        )
        patches.append(assets_patch)
        if assets_result.success and assets_result.data:
            assets = list(assets_result.data.get("assets") or [])
        else:
            errors.append(assets_result.error_message or "list_offboarding_assets failed.")
    else:
        errors.append("Employee ID is required for exit details research.")

    last_working_day = (
        exit_record.get("approved_last_working_day")
        or exit_record.get("requested_last_working_day")
        or request.get("requested_date")
    )
    retrieved = {
        **(state.get("retrieved_data") or {}),
        "exit_record": exit_record,
        "assets": assets,
        "asset_count": len(assets),
        "handover": handover,
        "open_obligations": list(exit_record.get("open_obligations") or []),
        "access_systems": list(exit_record.get("access_systems") or []),
        "privileged_access": bool(exit_record.get("privileged_access")),
        "privileged_systems": list(exit_record.get("privileged_systems") or []),
        "handover_required": bool(
            exit_record.get("handover_required") or handover.get("required")
        ),
        "last_working_day": last_working_day,
        "exit_type": exit_record.get("exit_type") or request.get("exit_type"),
        "resignation_date": exit_record.get("resignation_date"),
        "notice_period_days": exit_record.get("notice_period_days")
        or employee.get("notice_period_days"),
    }

    _, memory_patch = append_short_term(
        state,
        agent="exit_details_research",
        content=(
            f"Exit details for {employee_id or 'unknown'}: "
            f"type={retrieved.get('exit_type')} last_day={last_working_day} "
            f"assets={len(assets)} privileged={retrieved.get('privileged_access')}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "exit_details_research",
        (
            f"Researched exit details for {employee_id or 'unknown'}: "
            f"{len(assets)} asset(s), privileged={retrieved.get('privileged_access')}."
        ),
        retrieved_data=retrieved,
        errors=errors,
        **combine_patches(*patches),
    )
