# Development of Enterprise Workflow Platform with Decision Automation System — Group 1

HR operations workflow automation and decision-support platform. Specialized agents collaborate through shared structured state, coordinated by a LangGraph orchestrator. This is **not** a chatbot and not a single LLM with tools.

## Current status (Modules 1–4 complete)

| Module | Scope |
|--------|--------|
| **1** | Agent foundation, `WorkflowState`, leave workflow prototype |
| **2** | Tool registry / selector / executor, simulated HR adapters |
| **3** | MemoryFacade (short-term, knowledge, long-term) |
| **4A** | Platform spine: `WorkflowSpec`, Registry, Router, Engine, audit, metrics |
| **4B–4H** | Eight domain workflows on the same engine |

**Module 4 evaluation / hardening** verified that all workflows share one platform path:

`Router → Registry → WorkflowEngine → LangGraph → Agents → Tools → Policies → Memory/Knowledge → Decision → Validation → Actions → Human approval → Audit → Metrics`

**Do not treat this as production deployment.** HR stores, notifications, and approval checkpoints are simulated.

## Architecture

```
User Request
    │
    ▼
WorkflowRouter  ──► WorkflowRegistry
    │
    ▼
WorkflowEngine.run() / resume()
    │
    ▼
Domain LangGraph workflow (WorkflowState)
    │
    ├── Agents (planner → research → policy → analysis → decision → validation → action/response)
    ├── Tools (Selector → Registry → Executor → simulated services)
    ├── MemoryFacade (short-term / knowledge / long-term)
    └── KnowledgeStore (offline lexical handbook search)
    │
    ▼
WorkflowResult { state, audit, metrics, router, spec_version }
```

Shared platform contracts live under `app/workflows/` (`contracts`, `registry`, `router`, `engine`, `results`, `builtins`). Domain graphs live beside them as `*_workflow.py`. Agents never invent a parallel engine.

### Decision authority (invariant)

| Layer | Role |
|-------|------|
| Structured tools + policy JSON | **Authoritative** for eligibility, violations, balances, prerequisites, authorization |
| Memory + knowledge | **Context only** — warnings, citations, confidence, explanation |

Memory must never override policy violations, missing prerequisites, insufficient leave balance, attendance/performance/training/offboarding rules, or authorization restrictions.

## Registered workflow types

| `workflow_type` | Purpose |
|-----------------|--------|
| `leave_attendance` | Leave request evaluation (balances + leave policy). Name is historical; **not** the attendance analytics workflow. |
| `recruitment` | Job/candidate scoring, shortlist/interview with approval |
| `onboarding` | Documents, tasks, equipment, system access (privileged access approval) |
| `attendance` | Attendance analytics, irregularities, warnings/escalations |
| `performance` | Goals/KPIs, reviews, improvement plans |
| `training` | Skill gaps, catalog match, enrollment (high-cost approval) |
| `offboarding` | Exit checklist, assets, handover, access revoke (privileged approval) |
| `hr_services` | Coordination/service layer: certificates, tickets, inquiries, routing — **not** a replacement for domain workflows |

Informational phrasing such as `leave balance inquiry` / `attendance inquiry` routes to `hr_services`. Actionable domain phrasing (e.g. “take 3 days of leave”, “analyze attendance”, “recommend training”) routes to the matching domain workflow.

## Agent architecture

Each workflow is a LangGraph `StateGraph(WorkflowState)` of specialized nodes (planner/research/policy/analysis/decision/validation/action/response, with domain naming). Validation branches to action only when the decision is executable and not awaiting human approval.

Agents request capabilities; they do not call stores or SMTP directly.

## Tool architecture

- **Registry** (`app/tools/registry.py`): fail-closed name/capability lookup
- **Selector** (`app/tools/selector.py`): agent allowlist + write guards (`validated=True`)
- **Executor** (`app/tools/executor.py`): schema validation, authorization, retries for transient `SERVICE_ERROR`, redacted traces
- **Idempotency** (`app/tools/idempotency.py`): org + workflow + capability keys so retries do not double-apply writes
- **Implementations**: leave, recruitment, onboarding, attendance, performance, training, offboarding, hr_services, notifications — all against in-memory simulated stores

## Memory architecture

Agents use `app.memory.facade` only:

| Layer | Scope |
|-------|--------|
| Short-term | `organization_id` + `workflow_id` notebook (cleared between runs) |
| Knowledge | Lexical search over `data/knowledge/` via `KnowledgeStore` (global + matching org) |
| Long-term | Compact outcomes scoped by `organization_id` + `employee_id` + `workflow_type` (JSONL development backend) |

Every access appends a redacted record to `WorkflowState.memory_accesses`.

## Knowledge architecture

Offline markdown handbooks under `data/knowledge/{domain}/` plus optional `organizations/{organization_id}/`. Search never overrides structured `data/policies/*.json`.

## Decision engine

Per-domain decision agents produce a shared `WorkflowDecision` shape (`approve` / `reject` / `pending_approval` / `escalate` / `recommend` / `ready` / `blocked`, plus evidence/blockers/warnings). Validation agents gate write tools and set `metadata.route`.

## Human approval

When outcome is `pending_approval` / `escalate` with `requires_human_approval`:

1. Validation routes to response (no high-impact writes)
2. Engine stores an **in-memory** checkpoint and returns `WorkflowResult` with `approval_checkpoint`
3. `WorkflowEngine.resume(workflow_id, ApprovalDecision(approved=True|False))` executes or rejects pending writes

There is no approval UI yet (Module 5). Checkpoints are process-local and lost on restart.

## Audit and metrics

Built once in `app/workflows/results.py` for every workflow (not per-domain builders):

- **Audit:** workflow id/type/org, timing, status, agents, tool executions, memory accesses, decision, actions, errors, approval checkpoint, final outcome
- **Metrics:** duration, agent/tool counts, success/retry rates, validation_failed, human_approval_required, confidence, action_success_rate, escalated, status

Returned inside the shared `WorkflowResult`.

## Setup

Python 3.12 is required.

```bash
cd /home/vinay/Documents/Code/enterprise-workflow-decision-automation
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

```
GOOGLE_API_KEY=
GEMINI_MODEL=
APP_ENV=development
```

Default model is `gemini-2.5-flash`. Modules 1–4 do not require Gemini for the deterministic agent paths used in tests and CLI demos.

## CLI examples

```bash
source .venv/bin/activate

# Leave
python run.py "Check whether employee E001 can take 3 days of leave."

# Recruitment
python run.py "Find candidates for the Python Backend Developer position."

# Onboarding
python run.py "Start onboarding for employee E003."

# Attendance
python run.py "Analyze attendance for employee E003 for July 2026."

# Performance
python run.py "Analyze performance for employee E003 for Q2 2026."

# Training
python run.py "Recommend training for employee E003."

# Offboarding
python run.py "Start offboarding for employee E006."

# HR Services
python run.py "Request an employment certificate for employee E003."

# Explicit override / tenant context
python run.py "Please process this case." --workflow-type hr_services --organization-id org-demo --user-id E003 --user-role employee
```

`run.py` is a thin `WorkflowEngine` client. It prints state, tools, memory, decision, actions, audit, and metrics.

## Tests

```bash
source .venv/bin/activate
python -m pytest tests -q
```

Tests are deterministic and do not call Gemini. Platform evaluation coverage lives in `tests/test_module4_platform_eval.py` plus per-domain suites. Current suite: **280** tests passing.

## Simulated components (explicit)

- In-memory HR / recruitment / onboarding / attendance / performance / training / offboarding / HR services stores (JSON under `data/` is seed only; not written back)
- In-memory notification inbox with fault injection
- In-memory human-approval checkpoints
- Lexical (non-vector) knowledge search
- Deterministic agents (no live LLM required for current paths)

## Current limitations

- No frontend, dashboard, authentication, REST API, PostgreSQL, Docker, or cloud deployment (Module 5)
- No real email or external HRIS integrations
- Human approval has no UI; resume is programmatic via `WorkflowEngine.resume`
- Approval checkpoints are not durable across process restarts
- Empty `organization_id` on many seed records matches any tenant filter (demo convenience; document as evaluation constraint)
- Agent nodes are deterministic; LLM enrichment is optional/future
- `leave_attendance` expects actionable leave requests; pure balance questions are better as `leave balance inquiry` → `hr_services`

## Module 5 (not started)

REST APIs, web dashboard, monitoring/logging, durable persistence, authentication, and deployment belong to Module 5. Do not start them in this repository phase.
