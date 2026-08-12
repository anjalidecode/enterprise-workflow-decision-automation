import json
from pathlib import Path

from app.services.hr_data import DATA_DIR
from app.services.hr_store import get_hr_store, reset_hr_store


def test_store_is_seeded_from_json() -> None:
    employee = get_hr_store().get_employee("E001")
    assert employee is not None
    assert employee["name"] == "Alex Rivera"
    assert employee["leave_balances"]["annual"] == 12


def test_store_balance_update_and_reset() -> None:
    store = get_hr_store()
    result = store.update_leave_balance(
        workflow_id="wf-1",
        employee_id="E001",
        days=3,
        leave_type="annual",
        start_date="2026-08-17",
    )
    assert result["previous_balance"] == 12
    assert result["new_balance"] == 9
    assert store.get_employee("E001")["leave_balances"]["annual"] == 9

    replay = store.update_leave_balance(
        workflow_id="wf-1",
        employee_id="E001",
        days=3,
        leave_type="annual",
        start_date="2026-08-17",
    )
    assert replay["idempotent_replay"] is True
    assert store.get_employee("E001")["leave_balances"]["annual"] == 9

    reset_hr_store()
    assert get_hr_store().get_employee("E001")["leave_balances"]["annual"] == 12


def test_store_update_does_not_change_seed_json() -> None:
    get_hr_store().update_leave_balance(
        workflow_id="wf-2",
        employee_id="E001",
        days=3,
        leave_type="annual",
        start_date="2026-08-17",
    )
    payload = json.loads((Path(DATA_DIR) / "employees" / "employees.json").read_text(encoding="utf-8"))
    e001 = next(item for item in payload if item["employee_id"] == "E001")
    assert e001["leave_balances"]["annual"] == 12
