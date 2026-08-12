#!/usr/bin/env python3
"""Temporary CLI for running the Module 1 leave & attendance workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.workflows.leave_workflow import run_leave_workflow

DEFAULT_REQUEST = "Check whether employee E001 can take 3 days of leave from 2026-08-17."


def _print_section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the HR leave & attendance decision workflow."
    )
    parser.add_argument(
        "request",
        nargs="?",
        default=DEFAULT_REQUEST,
        help="Natural-language leave request",
    )
    args = parser.parse_args()

    result = run_leave_workflow(args.request)

    print("=" * 64)
    print("Leave & Attendance Workflow")
    print("=" * 64)
    print(f"Workflow ID:     {result.get('workflow_id')}")
    print(f"Workflow type:   {result.get('workflow_type')}")
    print(f"Status:          {result.get('status')}")
    print(f"Current stage:   {result.get('current_stage')}")

    _print_section("Agents executed")
    outputs = result.get("agent_outputs") or []
    if not outputs:
        print("  (none)")
    for index, output in enumerate(outputs, start=1):
        print(f"  {index}. {output.get('agent')}: {output.get('summary')}")

    _print_section("Important state changes")
    employee = result.get("employee_data") or {}
    retrieved = result.get("retrieved_data") or {}
    policy = result.get("policy_results") or {}
    analysis = result.get("analysis_results") or {}
    print(f"  Employee:          {employee.get('name', 'n/a')} ({employee.get('employee_id', 'n/a')})")
    print(f"  Employment status: {employee.get('employment_status', retrieved.get('employment_status', 'n/a'))}")
    print(f"  Policy:            {policy.get('policy_id', 'n/a')} eligible={policy.get('eligible')}")
    print(f"  Policy violations: {policy.get('violations') or []}")
    print(f"  Analysis:          {analysis.get('recommendation')} remaining_after={analysis.get('remaining_after')}")
    print(f"  Planned tasks:     {result.get('tasks')}")
    print(f"  Completed tasks:   {result.get('completed_tasks')}")

    decision = result.get("decision") or {}
    _print_section("Decision")
    print(f"  Outcome:           {decision.get('outcome', 'n/a')}")
    print(f"  Confidence:        {result.get('confidence')}")
    print(f"  Executable:        {decision.get('executable')}")
    print(f"  Human approval:    {result.get('requires_human_approval')}")
    print(f"  Rationale:         {decision.get('rationale', 'n/a')}")

    _print_section("Actions")
    completed_actions = result.get("completed_actions") or []
    pending_actions = result.get("pending_actions") or []
    if completed_actions:
        for action in completed_actions:
            print(f"  completed: {json.dumps(action, default=str)}")
    elif pending_actions:
        for action in pending_actions:
            print(f"  pending:   {json.dumps(action, default=str)}")
    else:
        print("  (none)")

    _print_section("Final response")
    print(f"  {result.get('final_response') or '(empty)'}")

    _print_section("Errors")
    errors = result.get("errors") or []
    if errors:
        for error in errors:
            print(f"  - {error}")
    else:
        print("  (none)")
    print()


if __name__ == "__main__":
    main()
