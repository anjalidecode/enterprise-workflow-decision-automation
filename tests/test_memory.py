from app.memory.errors import MemoryPermissionError, MemorySafetyError
from app.memory.facade import (
    append_short_term,
    recall_long_term,
    search_short_term,
    write_long_term,
)
from app.memory.long_term import get_long_term_store
from app.memory.safety import sanitize_long_term_payload
from app.memory.short_term import get_short_term_store
from app.orchestration.state import create_initial_state


def _state(request: str = "Check whether employee E001 can take 3 days of leave from 2026-08-17.") -> dict:
    state = create_initial_state(request)
    state["workflow_type"] = "leave_attendance"
    state["metadata"] = {"leave_request": {"employee_id": "E001", "days": 3, "start_date": "2026-08-17"}}
    return state


def test_short_term_write_read_and_isolation() -> None:
    state_a = _state()
    state_b = create_initial_state("other")
    state_b["workflow_type"] = "leave_attendance"

    append_short_term(state_a, agent="planner", content="Planner parsed employee E001 requesting 3 annual leave days.")
    records_a, _patch = search_short_term(state_a, agent="analysis")
    records_b, _patch_b = search_short_term(state_b, agent="analysis")

    assert len(records_a) == 1
    assert "E001" in records_a[0].content
    assert records_b == []


def test_short_term_reset() -> None:
    state = _state()
    append_short_term(state, agent="orchestrator", content="Workflow started.")
    get_short_term_store().reset()
    records, _patch = search_short_term(state, agent="analysis")
    assert records == []


def test_long_term_write_query_and_employee_isolation() -> None:
    state = _state()
    write_long_term(
        state,
        agent="response",
        payload={
            "employee_id": "E001",
            "workflow_type": "leave_attendance",
            "outcome": "approved",
            "days": 3,
            "start_date": "2026-08-17",
            "rationale_summary": "Leave balance and policy conditions were satisfied.",
            "requires_human_approval": False,
        },
    )
    other = _state()
    other["metadata"] = {"leave_request": {"employee_id": "E002"}}
    write_long_term(
        other,
        agent="response",
        payload={
            "employee_id": "E002",
            "workflow_type": "leave_attendance",
            "outcome": "rejected",
            "days": 3,
            "start_date": "2026-08-17",
            "rationale_summary": "Insufficient balance.",
            "requires_human_approval": False,
        },
    )

    e001, _patch = recall_long_term(state, agent="research", employee_id="E001")
    assert len(e001) == 1
    assert e001[0].employee_id == "E001"
    assert all(item.employee_id == "E001" for item in e001)


def test_long_term_reset() -> None:
    state = _state()
    write_long_term(
        state,
        agent="response",
        payload={
            "employee_id": "E001",
            "workflow_type": "leave_attendance",
            "outcome": "approved",
            "days": 3,
            "rationale_summary": "ok",
        },
    )
    get_long_term_store().reset()
    records, _patch = recall_long_term(state, agent="research", employee_id="E001")
    assert records == []


def test_safety_allowlist_and_rejection() -> None:
    cleaned = sanitize_long_term_payload(
        {
            "employee_id": "E001",
            "workflow_type": "leave_attendance",
            "outcome": "approved",
            "days": 3,
            "start_date": "2026-08-17",
            "rationale_summary": "ok",
            "requires_human_approval": False,
            "workflow_id": "wf-1",
            "timestamp": "2026-08-12T00:00:00+00:00",
            "name": "should be dropped",
        }
    )
    assert "name" not in cleaned
    assert cleaned["employee_id"] == "E001"

    try:
        sanitize_long_term_payload(
            {
                "employee_id": "E001",
                "google_api_key": "secret",
                "outcome": "approved",
            }
        )
        raise AssertionError("expected MemorySafetyError")
    except MemorySafetyError:
        pass

    try:
        write_long_term(
            _state(),
            agent="response",
            payload={
                "employee_id": "E001",
                "notification": "Leave approved email body",
                "outcome": "approved",
            },
        )
        raise AssertionError("expected MemorySafetyError")
    except MemorySafetyError:
        pass


def test_memory_permissions() -> None:
    state = _state()
    try:
        recall_long_term(state, agent="planner")
        raise AssertionError("planner should not read long-term memory")
    except MemoryPermissionError:
        pass
    try:
        write_long_term(state, agent="action", payload={"employee_id": "E001", "outcome": "approved"})
        raise AssertionError("action should not write long-term memory")
    except MemoryPermissionError:
        pass


def test_memory_access_trace_on_read_and_write() -> None:
    state = _state()
    state["organization_id"] = "org-demo"
    state["user_id"] = "u-1"
    _record, write_patch = append_short_term(state, agent="planner", content="Planner parsed request.")
    _records, read_patch = search_short_term(state, agent="analysis")
    access = write_patch["memory_accesses"][0]
    assert access["operation"] == "write"
    assert access["layer"] == "short_term"
    assert access["organization_id"] == "org-demo"
    assert access["workflow_id"] == state["workflow_id"]
    assert access["user_id"] == "u-1"
    assert access["timestamp"]
    assert read_patch["memory_accesses"][0]["operation"] == "read"
    assert "google_api_key" not in str(write_patch)


def test_long_term_organization_isolation_same_employee_id() -> None:
    org_a = _state()
    org_a["organization_id"] = "org-a"
    org_b = _state()
    org_b["organization_id"] = "org-b"

    write_long_term(
        org_a,
        agent="response",
        payload={
            "employee_id": "E001",
            "workflow_type": "leave_attendance",
            "outcome": "approved",
            "days": 3,
            "rationale_summary": "Org A leave history.",
        },
    )
    write_long_term(
        org_b,
        agent="response",
        payload={
            "employee_id": "E001",
            "workflow_type": "leave_attendance",
            "outcome": "rejected",
            "days": 2,
            "rationale_summary": "Org B leave history.",
        },
    )

    a_records, _ = recall_long_term(org_a, agent="research", employee_id="E001")
    b_records, _ = recall_long_term(org_b, agent="research", employee_id="E001")
    assert len(a_records) == 1
    assert len(b_records) == 1
    assert a_records[0].organization_id == "org-a"
    assert b_records[0].organization_id == "org-b"
    assert "Org A" in a_records[0].content
    assert "Org B" in b_records[0].content


def test_short_term_organization_isolation() -> None:
    org_a = _state()
    org_a["organization_id"] = "org-a"
    org_b = create_initial_state(org_a["user_request"])
    org_b["workflow_id"] = org_a["workflow_id"]
    org_b["workflow_type"] = "leave_attendance"
    org_b["organization_id"] = "org-b"

    append_short_term(org_a, agent="planner", content="Org A notebook note.")
    a_records, _ = search_short_term(org_a, agent="analysis")
    b_records, _ = search_short_term(org_b, agent="analysis")
    assert len(a_records) == 1
    assert b_records == []


def test_employee_role_scope_extension_point() -> None:
    state = _state()
    state["organization_id"] = "org-a"
    state["user_role"] = "employee"
    state["metadata"] = {"leave_request": {"employee_id": "E001"}}
    write_long_term(
        state,
        agent="response",
        payload={
            "employee_id": "E001",
            "workflow_type": "leave_attendance",
            "outcome": "approved",
            "days": 1,
            "rationale_summary": "own record",
        },
    )
    own, _ = recall_long_term(state, agent="research", employee_id="E001")
    other, patch = recall_long_term(state, agent="research", employee_id="E002")
    assert len(own) == 1
    assert other == []
    assert "role scope" in patch["memory_accesses"][0]["summary"].lower()
