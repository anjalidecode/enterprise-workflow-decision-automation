# Development of Enterprise Workflow Platform with Decision Automation System — Group 1

HR Operations workflow automation and decision-support platform. Specialized agents collaborate through shared structured state, coordinated by a LangGraph orchestrator. This is not a chatbot and not a single LLM with tools.

## Current implementation (Modules 1–3)

**Module 1 — Agent Foundation** delivered the Leave & Attendance workflow: nine specialized LangGraph nodes, shared `WorkflowState`, conditional routing, and human-approval handling.

**Module 2 — Tool Integration & Intelligent Action Execution** adds a reusable tool layer between agents and enterprise services. Agents request capabilities through a selector, registry, and executor.

**Module 3 — Agent Coordination & Memory Management** adds short-term, knowledge, and long-term memory beside LangGraph. `WorkflowState` remains the live coordination contract. Memory may explain, warn, or adjust confidence; structured tools and `validate_leave_policy` remain authoritative.

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
- **Executor** (`app/tools/executor.py`): Pydantic input validation, authorization, tenacity retries for transient `SERVICE_ERROR` only, duration/attempt tracing, notification log fallback.

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

Memory exists so agents can share a run notebook, retrieve handbook explanations, and recall compact prior outcomes. It does **not** replace `WorkflowState`, tools, or the structured leave policy.

- **WorkflowState:** current request, employee data, policy/analysis/decision, tool traces, `memory_accesses`.
- **Short-term memory:** in-process notes scoped to `workflow_id`. Cleared between runs. Not a chatbot history.
- **Knowledge memory:** curated handbook text under `data/knowledge/leave/handbook.md`, searched with an offline lexical retriever. Replaceable later with Chroma. Never overrides `leave_policy.json`.
- **Long-term memory:** JSONL file of allowlisted outcome facts (`data/memory/long_term.jsonl`, gitignored). Query by `employee_id` + `workflow_type`.
- **Facade:** agents call `app.memory.facade` only. Permissions are enforced per agent.
- **Safety:** long-term writes drop unknown fields and reject secrets, tool payloads, and notification bodies.
- **Tracing:** every read/write appends a `MemoryAccess` to `WorkflowState` for the CLI/UI.

Context-aware example: handbook text explains 5-day manager approval; prior overlapping leave can add a warning and lower confidence; insufficient balance still rejects.

| Requirement | Implementation |
|-------------|----------------|
| Specialized agents | Unchanged nine LangGraph nodes |
| Communication / information exchange | State + short-term notes + memory_accesses |
| Short-term conversational memory | Workflow-scoped notebook |
| Long-term knowledge retention | Handbook retriever + JSONL outcomes |
| Shared memory repositories | Facade over three stores |
| Context-aware decisions | Warnings/citations/confidence only |

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

- **Module 4:** Remaining HR workflows (recruitment, onboarding, policy queries, performance, offboarding), dynamic orchestration, recommendations.
- **Module 5:** REST APIs, web dashboard, monitoring, logging, deployment, and performance work.
