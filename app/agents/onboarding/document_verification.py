"""Document Verification Agent: retrieve and verify document metadata via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def document_verification_agent(state: WorkflowState) -> dict[str, Any]:
    employee_id = (
        (state.get("entities") or {}).get("employee_id")
        or (state.get("employee_data") or {}).get("employee_id")
    )
    patches: list[dict[str, Any]] = []
    errors: list[str] = []
    documents: list[dict[str, Any]] = []
    verification: dict[str, Any] = {}

    if not employee_id:
        errors.append("Document verification skipped because employee_id is missing.")
    else:
        list_result, list_patch = invoke_tool(
            state,
            agent="document_verification",
            name="get_employee_documents",
            payload={"employee_id": employee_id},
        )
        patches.append(list_patch)
        if list_result.success and list_result.data:
            documents = list(list_result.data.get("documents") or [])
        else:
            errors.append(list_result.error_message or "get_employee_documents failed.")

        verify_result, verify_patch = invoke_tool(
            state,
            agent="document_verification",
            name="verify_employee_documents",
            payload={"employee_id": employee_id},
        )
        patches.append(verify_patch)
        if verify_result.success and verify_result.data:
            verification = dict(verify_result.data)
        else:
            errors.append(verify_result.error_message or "verify_employee_documents failed.")

    retrieved = dict(state.get("retrieved_data") or {})
    retrieved["documents"] = documents
    retrieved["document_verification"] = verification

    _, memory_patch = append_short_term(
        state,
        agent="document_verification",
        content=(
            f"Document check for {employee_id}: "
            f"verified={verification.get('verified_documents') or []}; "
            f"missing={verification.get('missing_documents') or []}; "
            f"invalid={verification.get('invalid_documents') or []}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "document_verification",
        (
            f"Documents verified={len(verification.get('verified_documents') or [])}; "
            f"missing={len(verification.get('missing_documents') or [])}; "
            f"invalid={len(verification.get('invalid_documents') or [])}."
        ),
        retrieved_data=retrieved,
        errors=errors,
        **combine_patches(*patches),
    )
