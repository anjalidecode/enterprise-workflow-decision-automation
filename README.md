# Development of Enterprise Workflow Platform with Decision Automation System — Group 1

HR Operations workflow automation and decision-support platform. Specialized agents collaborate through shared structured state, coordinated by a LangGraph orchestrator. This is not a chatbot and not a single LLM with tools.

## Current implementation (Modules 1–4A)

**Module 1 — Agent Foundation** delivered the Leave & Attendance workflow: nine specialized LangGraph nodes, shared `WorkflowState`, conditional routing, and human-approval handling. The agent layer is now workflow-agnostic and organization-ready: optional `organization_id` / `user_id` / `user_role`, reusable `entities`, generic `WorkflowDecision` outcomes (`approve` / `reject` / `pending_approval` / `escalate` / `recommend`), and `AgentSpec` contracts for each core agent. Leave remains the first working domain workflow on top of that engine.

**Module 2 — Tool Integration & Intelligent Action Execution** adds a reusable tool layer between agents and enterprise services. Agents request capabilities through a selector, registry, and executor.

**Module 3 — Agent Coordination & Memory Management** adds short-term, knowledge, and long-term memory beside LangGraph. `WorkflowState` remains the live coordination contract. Memory may explain, warn, or adjust confidence; structured tools and `validate_leave_policy` remain authoritative.

**Module 4A — Workflow Platform Spine** adds `WorkflowSpec`, `WorkflowRegistry`, deterministic `WorkflowRouter`, and `WorkflowEngine` returning `WorkflowResult` (state + audit snapshot + metrics). `run.py` is a thin engine client. Only Leave & Attendance is registered; other HR workflows come in later phases.

## Architecture

```
                    WORKFLOW
                        |
                        v
                  WorkflowState
                        |
           +------------+------------+
           |            |            |
           v            v            v
      Short-Term    Knowledge    Long-Term
        Memory        Memory       Memory
           |            |            |
           +------------+------------+
                        |
                        v
                     Agents
```

```
User Request
    │
    ▼
Orchestrator Agent
    │
    ▼
Planner Agent
    │
    ▼
Research Agent ──► employee.lookup, employee.leave_balance
    │
    ▼
Policy Agent ──► policy.lookup, policy.validate_leave
    │
    ▼
Analysis Agent ──► leave.impact
    │
    ▼
Decision Agent
    │
    ▼
Validation Agent
    │
    ├── reject / invalid / human approval ──► Response ──► END
    │
    └── approved + executable
          └──► Action Agent ──► leave.balance.update, notification.send
                 └──► Response ──► END
```

Tool path used by Research, Policy, Analysis, and Action:

```
Agent
  → Tool Selector     capability + allowlist + write guards
  → Tool Registry     explicit name/capability lookup
  → Tool Executor     validate, authorize, retry, log
  → Tool
  → Simulated HR store / notification service
  → ToolResult
  → WorkflowState (including tool_executions)
```

## Why the tool layer exists

Module 1 agents imported services directly. That does not scale to Recruitment, Onboarding, or real HR/email APIs.

The tool layer gives every workflow the same contract: typed inputs, authorization, retries, and an execution trace. Future Calendar, Email, or HRIS adapters register as tools with the same capabilities; agents do not change.

## Tool registry, selector, and executor

- **Registry** (`app/tools/registry.py`): explicit registration. Unknown names fail closed.
- **Selector** (`app/tools/selector.py`): deterministic. An agent may only use `allowed_agents`. Write tools require the Action Agent and `validated=True`. No LLM tool-picking.
- **Executor** (`app/tools/executor.py`): Pydantic input validation, authorization, tenacity retries for transient `SERVICE_ERROR` only, duration/attempt tracing, notification log fallback. ToolContext now carries optional `organization_id` / `user_id` / `user_role` from WorkflowState into every execution and audit trace.
- **Service boundary** (`app/services/interfaces.py`): tools depend on `HREmployeeService` and `NotificationServicePort`. The current in-memory store and inbox are implementations; PostgreSQL/email adapters can replace them later without changing agents or ToolExecutor.
- **Idempotency** (`app/tools/idempotency.py`): reusable write keys include organization + workflow + capability so retries cannot double-apply leave updates or notifications.
- **Planned domains** (`app/tools/domains.py`): documented recruitment/onboarding/attendance/performance/training/offboarding capabilities for future registration. Not implemented yet.

## Seven leave tools

| Tool | Capability | Side effect | Agent |
|------|------------|-------------|-------|
| `get_employee` | `employee.lookup` | read | research |
| `get_leave_balance` | `employee.leave_balance` | read | research, analysis |
| `get_leave_policy` | `policy.lookup` | read | policy |
| `validate_leave_policy` | `policy.validate_leave` | read | policy |
| `calculate_leave_impact` | `leave.impact` | read | analysis |
| `update_leave_balance` | `leave.balance.update` | write | action |
| `notify_employee` | `notification.send` | write | action |

`update_leave_balance` is idempotent per `workflow_id` + employee + leave request, so retries cannot double-deduct. If notification still fails after retries, the executor records a log-only fallback and does not undo the leave update.

## Simulated HR store

JSON under `data/` is seed data only. `app/services/hr_store.py` loads it into memory. Workflow updates change the in-memory store. JSON files are never written. Tests call `reset_hr_store()` between runs.

## Monitoring, validation, and errors

Each tool call appends a `tool_executions` record to `WorkflowState` (tool, agent, success, attempts, duration, error code, redacted input). The CLI prints this trace.

Validation is two-layered: tool input schemas plus the existing Validation Agent, which also checks that approve-path pending actions are registered write tools.

Error codes: `NOT_FOUND`, `INVALID_INPUT`, `SERVICE_ERROR`, `FORBIDDEN`. Invalid input, forbidden access, and missing records are not retried.

## Internship Module 2 mapping

| Requirement | Implementation |
|-------------|----------------|
| Tool integration | Seven tools + catalog |
| APIs / external systems | Service adapters behind tools (simulated now) |
| Intelligent tool selection | Capability/allowlist selector |
| Action execution | Action Agent + write tools |
| Monitoring | `tool_executions` + CLI |
| Validation and error handling | Schemas, write guards, typed errors |
| Retry / fallback | tenacity + notification log fallback |

## Module 3 — Memory

Memory exists so agents can share a run notebook, retrieve handbook explanations, and recall compact prior outcomes. It does **not** replace `WorkflowState`, tools, or the structured leave policy. Structured rules/tools remain authoritative for balance checks, policy violations, validation, and authorization.

- **WorkflowState:** current request, employee data, policy/analysis/decision, tool traces, `memory_accesses`. Live coordination contract.
- **Short-term memory:** in-process notes scoped to `organization_id + workflow_id`. Cleared between runs. Not a chatbot history.
- **Knowledge memory:** offline lexical search over `data/knowledge/` (global/domain folders today; future `organizations/{organization_id}/...`). `KnowledgeStore.search(query, organization_id, workflow_type, filters)` returns global docs plus that org only. Never overrides `leave_policy.json`.
- **Long-term memory:** JSONL development backend (`data/memory/long_term.jsonl`, gitignored) behind `LongTermMemoryPort`. Scoped by `organization_id + employee_id + workflow_type` so the same employee id in two companies never collides. Swappable to PostgreSQL later without changing agents.
- **Facade:** agents call `app.memory.facade` only (`MemoryAccessContext` carries org/user/role extension points). No direct JSONL, file, or vector-DB access from agents.
- **Safety:** long-term writes keep an allowlist and reject secrets, tokens, tool payloads, notification bodies, and full employee records.
- **Tracing:** every read/write appends a `MemoryAccess` (agent, layer, operation, memory ids, summary, org/workflow/user, timestamp, influenced_decision) without sensitive content.

Cross-workflow lifecycle context (recruitment → onboarding → leave → …) is supported by `workflow_type` scoping, not one unstructured employee dump.

| Requirement | Implementation |
|-------------|----------------|
| Specialized agents | Unchanged nine LangGraph nodes |
| Communication / information exchange | State + short-term notes + memory_accesses |
| Short-term conversational memory | Org + workflow-scoped notebook |
| Long-term knowledge retention | Org-aware handbook retriever + JSONL outcomes |
| Shared memory repositories | Facade over three replaceable stores |
| Context-aware decisions | Warnings/citations/confidence only |
| Multi-tenant isolation | organization_id on records + knowledge visibility |

## Setup

Python 3.12 is required.

```bash
cd /home/vinay/Documents/Code/enterprise-workflow-decision-automation
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If `.venv` already exists:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

```bash
cp .env.example .env
```

```
GOOGLE_API_KEY=
GEMINI_MODEL=
APP_ENV=development
```

Do not commit a real API key. Module 1 and Module 2 do not require Gemini. Default model in settings is `gemini-2.5-flash`.

## Run the leave workflow

```bash
python run.py
python run.py "Check whether employee E001 can take 3 days of leave from 2026-08-17."
python run.py "Check whether employee E002 can take 3 days of leave from 2026-08-17."
python run.py "Check whether employee E001 can take 8 days of leave from 2026-08-17."
```

| ID | Name | Annual balance | Status | Typical result for 3 days |
|----|------|----------------|--------|---------------------------|
| E001 | Alex Rivera | 12 | active | approved (under 5-day approval threshold) |
| E002 | Jordan Chen | 2 | active | rejected (insufficient balance) |
| E003 | Sam Patel | 10 | inactive | rejected |
| E001 with 8 days | Alex Rivera | 12 | active | pending human approval |

## Run tests

```bash
source .venv/bin/activate
python -m pytest tests -q
```

Tests are deterministic and do not call Gemini.

## Current limitations

- Only the Leave & Attendance workflow is implemented.
- Agent nodes are deterministic; they do not call the LLM yet.
- HR and notification systems are simulated in memory.
- JSON seed files are not updated on disk (by design).
- There is no dashboard, REST API, PostgreSQL, RAG, or cloud deployment yet.
- Human approval is detected and reported; there is no approval UI.
- Tool selection is policy-based, not LLM-based.
- Knowledge search is lexical and offline, not a production vector database.

## Planned modules

- **Module 4:** Workflow platform spine (4A done: registry/router/engine). Remaining phases add recruitment, onboarding, attendance, performance, training, offboarding, and employee services on the same engine.
- **Module 5:** REST APIs, web dashboard, monitoring, logging, deployment, and performance work.
