#!/usr/bin/env python3
"""Thin CLI client for the enterprise workflow engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.workflows.engine import get_workflow_engine

DEFAULT_REQUEST = "Check whether employee E001 can take 3 days of leave from 2026-08-17."


def _print_section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an HR workflow through the WorkflowEngine."
    )
    parser.add_argument(
        "request",
        nargs="?",
        default=DEFAULT_REQUEST,
        help="Natural-language business request",
    )
    parser.add_argument(
        "--workflow-type",
        default=None,
        help="Optional explicit workflow_type override (e.g. leave_attendance)",
    )
    parser.add_argument("--organization-id", default="", help="Optional organization id")
    parser.add_argument("--user-id", default="", help="Optional user id")
    parser.add_argument("--user-role", default="", help="Optional user role")
    args = parser.parse_args()

    engine_result = get_workflow_engine().run(
        args.request,
        organization_id=args.organization_id,
        user_id=args.user_id,
        user_role=args.user_role,
        workflow_type=args.workflow_type,
    )
    result = engine_result.state
    audit = engine_result.audit
    metrics = engine_result.metrics

    title = "Leave & Attendance Workflow"
    if result.get("workflow_type") and result.get("workflow_type") != "leave_attendance":
        title = f"HR Workflow ({result.get('workflow_type')})"
    elif engine_result.router and engine_result.router.status != "routed":
        title = "Workflow Routing"

    print("=" * 64)
    print(title)
    print("=" * 64)
    print(f"Workflow ID:     {result.get('workflow_id')}")
    print(f"Request ID:      {result.get('request_id')}")
    print(f"Workflow type:   {result.get('workflow_type') or '(none)'}")
    print(f"Organization:    {result.get('organization_id') or '(none)'}")
    print(f"Initiated by:    {result.get('initiated_by') or result.get('user_id') or '(none)'}")
    print(f"User role:       {result.get('user_role') or '(none)'}")
    print(f"Status:          {result.get('status')}")
    print(f"Current stage:   {result.get('current_stage')}")
    print(f"Created at:      {result.get('created_at')}")
    if engine_result.router:
        print(
            f"Router:          status={engine_result.router.status} "
            f"confidence={engine_result.router.confidence} "
            f"hints={engine_result.router.matched_hints}"
        )
    entities = result.get("entities") or {}
    if entities:
        print(f"Entities:        {entities}")

    _print_section("Agents executed")
    outputs = result.get("agent_outputs") or []
    if not outputs:
        print("  (none)")
    for index, output in enumerate(outputs, start=1):
        print(f"  {index}. {output.get('agent')}: {output.get('summary')}")

    _print_section("Tool executions")
    traces = result.get("tool_executions") or []
    if not traces:
        print("  (none)")
    for index, trace in enumerate(traces, start=1):
        status = "success" if trace.get("success") else "failure"
        line = (
            f"  {index}. {trace.get('tool_name')} "
            f"agent={trace.get('agent')} {status} "
            f"attempts={trace.get('attempts')} "
            f"duration_ms={trace.get('duration_ms'):.1f}"
        )
        if trace.get("organization_id"):
            line += f" org={trace.get('organization_id')}"
        if trace.get("error_code"):
            line += f" error={trace.get('error_code')}"
        print(line)

    _print_section("Memory accesses")
    accesses = result.get("memory_accesses") or []
    if not accesses:
        print("  (none)")
    for index, access in enumerate(accesses, start=1):
        influenced = "yes" if access.get("influenced_decision") else "no"
        print(
            f"  {index}. agent={access.get('agent')} "
            f"op={access.get('operation')} "
            f"layer={access.get('layer')} "
            f"ids={len(access.get('memory_ids') or [])} "
            f"influenced={influenced} "
            f"summary={access.get('summary')}"
        )

    _print_section("Important state changes")
    employee = result.get("employee_data") or {}
    retrieved = result.get("retrieved_data") or {}
    policy = result.get("policy_results") or {}
    analysis = result.get("analysis_results") or {}
    if result.get("workflow_type") == "recruitment":
        job = retrieved.get("job") or {}
        print(f"  Job:               {job.get('title', 'n/a')} ({job.get('job_id', 'n/a')})")
        print(f"  Candidates found:  {retrieved.get('candidate_count', 0)}")
        print(f"  Shortlist:         {analysis.get('shortlist_candidates') or []}")
        print(f"  Review:            {analysis.get('review_candidates') or []}")
        print(f"  Rejected:          {analysis.get('rejected_candidates') or []}")
        scores = analysis.get("candidate_scores") or []
        if scores:
            top = ", ".join(
                f"{item.get('candidate_id')}={item.get('score')}" for item in scores[:5]
            )
            print(f"  Top scores:        {top}")
    elif result.get("workflow_type") == "onboarding":
        print(f"  Employee:          {employee.get('name', 'n/a')} ({employee.get('employee_id', 'n/a')})")
        print(f"  Role:              {employee.get('role', analysis.get('role', 'n/a'))}")
        print(f"  Department:        {employee.get('department', analysis.get('department', 'n/a'))}")
        print(f"  Joining date:      {employee.get('joining_date', analysis.get('joining_date', 'n/a'))}")
        print(f"  Policy:            {policy.get('policy_id', 'n/a')} eligible={policy.get('eligible')}")
        print(f"  Missing docs:      {analysis.get('missing_documents') or []}")
        print(f"  Invalid docs:      {analysis.get('invalid_documents') or []}")
        print(f"  Privileged access: {analysis.get('privileged_access_required') or []}")
        print(f"  Recommendation:    {analysis.get('recommendation', 'n/a')}")
    elif result.get("workflow_type") == "attendance":
        summary = analysis.get("summary") or {}
        print(f"  Employee:          {employee.get('name', 'n/a')} ({employee.get('employee_id', 'n/a')})")
        print(f"  Department:        {employee.get('department', analysis.get('department', 'n/a'))}")
        print(f"  Period:            {analysis.get('start_date', 'n/a')} to {analysis.get('end_date', 'n/a')}")
        print(f"  Present days:      {summary.get('present_days', 'n/a')}")
        print(f"  Absent days:       {summary.get('absent_days', 'n/a')}")
        print(f"  Late arrivals:     {summary.get('late_arrivals', 'n/a')}")
        print(f"  Attendance %:      {summary.get('attendance_percentage', 'n/a')}")
        print(f"  Policy:            {policy.get('policy_id', 'n/a')} severity={policy.get('severity')}")
        print(f"  Violations:        {policy.get('violations') or []}")
        print(f"  Warnings:          {policy.get('warnings') or []}")
        print(f"  Issue findings:    {len(analysis.get('issue_findings') or [])}")
    elif result.get("workflow_type") == "performance":
        summary = analysis.get("summary") or {}
        print(f"  Employee:          {employee.get('name', 'n/a')} ({employee.get('employee_id', 'n/a')})")
        print(f"  Department:        {employee.get('department', analysis.get('department', 'n/a'))}")
        print(f"  Review period:     {analysis.get('review_period', 'n/a')}")
        print(f"  Goal achievement:  {summary.get('goal_achievement_pct', analysis.get('goal_achievement_pct', 'n/a'))}%")
        print(f"  Completed goals:   {summary.get('completed_count', len(analysis.get('completed_goals') or []))}")
        print(f"  Partial goals:     {summary.get('partial_count', len(analysis.get('partial_goals') or []))}")
        print(f"  Unmet goals:       {summary.get('unmet_count', len(analysis.get('unmet_goals') or []))}")
        print(f"  Strengths:         {analysis.get('strengths') or []}")
        print(f"  Concerns:          {analysis.get('improvement_areas') or []}")
        print(f"  Skill gaps:        {analysis.get('skill_gaps') or []}")
        print(f"  Policy:            {policy.get('policy_id', 'n/a')} severity={policy.get('severity')}")
        print(f"  Violations:        {policy.get('violations') or []}")
        print(f"  Warnings:          {policy.get('warnings') or []}")
        print(f"  Support findings:  {len(analysis.get('support_findings') or [])}")
    else:
        print(f"  Employee:          {employee.get('name', 'n/a')} ({employee.get('employee_id', 'n/a')})")
        print(
            f"  Employment status: "
            f"{employee.get('employment_status', retrieved.get('employment_status', 'n/a'))}"
        )
        print(f"  Policy:            {policy.get('policy_id', 'n/a')} eligible={policy.get('eligible')}")
        print(f"  Policy violations: {policy.get('violations') or []}")
        print(
            f"  Analysis:          {analysis.get('recommendation')} "
            f"remaining_after={analysis.get('remaining_after')}"
        )
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

    _print_section("Audit summary")
    print(f"  Final outcome:     {audit.final_outcome or '(none)'}")
    print(f"  Started at:        {audit.started_at}")
    print(f"  Completed at:      {audit.completed_at}")
    print(f"  Agents:            {len(audit.agents_executed)}")
    print(f"  Tools:             {len(audit.tool_executions)}")
    print(f"  Memory accesses:   {len(audit.memory_accesses)}")
    if audit.approval_checkpoint:
        print(f"  Approval:          {audit.approval_checkpoint.get('status')}")

    _print_section("Metrics summary")
    print(f"  Duration ms:       {metrics.duration_ms}")
    print(f"  Agent count:       {metrics.agent_count}")
    print(f"  Tool count:        {metrics.tool_count}")
    print(f"  Tool success rate: {metrics.tool_success_rate:.2f}")
    print(f"  Retry count:       {metrics.retry_count}")
    print(f"  Validation failed: {metrics.validation_failed}")
    print(f"  Human approval:    {metrics.human_approval_required}")
    print(f"  Decision conf:     {metrics.decision_confidence}")
    print(f"  Action success:    {metrics.action_success_rate:.2f}")
    print(f"  Escalated:         {metrics.escalated}")

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
