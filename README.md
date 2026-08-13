# Development of Enterprise Workflow Platform with Decision Automation System — Group 1

HR operations workflow automation and decision-support platform. Specialized agents collaborate through shared structured state, coordinated by a LangGraph orchestrator. This is **not** a chatbot and not a single LLM with tools.

## Current status (Modules 1–5A)

| Module | Scope |
|--------|--------|
| **1** | Agent foundation, `WorkflowState`, leave workflow prototype |
| **2** | Tool registry / selector / executor, simulated HR adapters |
| **3** | MemoryFacade (short-term, knowledge, long-term) |
| **4A** | Platform spine: `WorkflowSpec`, Registry, Router, Engine, audit, metrics |
| **4B–4H** | Eight domain workflows on the same engine |
| **5A** | FastAPI REST API layer over `WorkflowEngine` (no auth / DB / frontend yet) |

**Do not treat the API as production-ready.** There is no authentication, no durable database, and approval/execution indexes are in-memory for the current process only. Modules 5B/5C will add authentication/RBAC and persistence.

## Architecture

```
HTTP Client / CLI
    │
    ▼
FastAPI (app/api) ── schemas / org isolation / request id
    │
    ▼
WorkflowEngine.run() / resume()
    │
    ▼
WorkflowRouter  ──► WorkflowRegistry
    │
    ▼
Domain LangGraph workflow (WorkflowState)
    │
    ├── Agents → Tools → Policies → Memory / Knowledge
    └── Decision → Validation → Action / Human approval
    │
    ▼
WorkflowResult { state, audit, metrics, router }
    │
    ▼
API schemas + in-memory execution index (process-local)
```

The API is a **thin application layer**. It must not call LangGraph nodes, agents, JSON data files, domain stores, memory stores, or tools directly.

## FastAPI (Module 5A)

### Start the API

```bash
source .venv/bin/activate
uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

| Resource | URL |
|----------|-----|
| Base API | `http://127.0.0.1:8000/api/v1` |
| Swagger UI | `http://127.0.0.1:8000/docs` |
| ReDoc | `http://127.0.0.1:8000/redoc` |
| OpenAPI JSON | `http://127.0.0.1:8000/openapi.json` |

CLI remains available and unchanged:

```bash
python run.py "Check whether employee E001 can take 3 days of leave."
```

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/health` | Liveness (no API key) |
| `GET` | `/api/v1/workflows/types` | Registered workflow types from `WorkflowRegistry` |
| `POST` | `/api/v1/workflows/run` | Run via `WorkflowEngine.run()` |
| `GET` | `/api/v1/workflows` | List runs in the process-local API index |
| `GET` | `/api/v1/workflows/{workflow_id}` | Get a run (org-scoped) |
| `GET` | `/api/v1/workflows/{workflow_id}/audit` | Existing `WorkflowAuditSnapshot` |
| `GET` | `/api/v1/workflows/{workflow_id}/metrics` | Existing `WorkflowRunMetrics` |
| `POST` | `/api/v1/workflows/{workflow_id}/approve` | `WorkflowEngine.resume(approved=True)` |
| `POST` | `/api/v1/workflows/{workflow_id}/reject` | `WorkflowEngine.resume(approved=False)` |

Retrieval and approval endpoints require `organization_id` as a query parameter for isolation (development context until Module 5B).

### Example: run a workflow

```bash
curl -s http://127.0.0.1:8000/api/v1/workflows/run \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: demo-1' \
  -d '{
    "request": "Check whether employee E001 can take 3 days of leave.",
    "organization_id": "demo-org",
    "user_id": "demo-user",
    "user_role": "hr"
  }'
```

Example response shape:

```json
{
  "workflow_id": "...",
  "workflow_type": "leave_attendance",
  "status": "completed",
  "current_stage": "response",
  "organization_id": "demo-org",
  "decision": {
    "outcome": "approve",
    "rationale": "...",
    "confidence": 0.92,
    "requires_human_approval": false
  },
  "response": "...",
  "audit": { "...": "..." },
  "metrics": { "...": "..." },
  "request_id": "demo-1"
}
```

### Example: approval

```bash
# After a run returns status=awaiting_human_approval
curl -s -X POST \
  "http://127.0.0.1:8000/api/v1/workflows/{workflow_id}/approve?organization_id=demo-org" \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "manager-001",
    "user_role": "manager",
    "reason": "Approved after review."
  }'
```

Reject uses the same body against `/reject`.

### Request correlation

Every response includes `X-Request-ID`. If the client sends `X-Request-ID`, it is preserved; otherwise the API generates one. This is distinct from `workflow_id`.

### CORS

Origins come from `CORS_ORIGINS` (comma-separated). Development defaults allow localhost frontend ports. The API does **not** use `allow_origins=["*"]` as a pretend production setting.

### Development context (not authentication)

`organization_id`, `user_id`, and `user_role` are explicit development fields preparing Module 5B auth/RBAC. They are **not** trusted production identity claims yet.

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

## Agent / tool / memory architecture

Unchanged from Modules 1–4. Agents request capabilities through the Tool Registry/Selector/Executor. Memory goes through `MemoryFacade` only. Structured policy/tools remain authoritative; memory/knowledge are context only.

## Human approval

When a run pauses at `awaiting_human_approval`:

1. Engine stores an **in-memory** checkpoint
2. API indexes the `WorkflowResult` for the process
3. `/approve` or `/reject` calls `WorkflowEngine.resume`

Checkpoints and the API execution index are process-local and lost on restart.

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
APP_VERSION=0.5.0
API_V1_PREFIX=/api/v1
API_HOST=127.0.0.1
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173
```

Default model is `gemini-2.5-flash`. Current deterministic agent paths used in tests/CLI/API demos do not require Gemini.

## CLI examples

```bash
source .venv/bin/activate

python run.py "Check whether employee E001 can take 3 days of leave."
python run.py "Find candidates for the Python Backend Developer position."
python run.py "Start onboarding for employee E003."
python run.py "Analyze attendance for employee E003 for July 2026."
python run.py "Analyze performance for employee E003 for Q2 2026."
python run.py "Recommend training for employee E003."
python run.py "Start offboarding for employee E006."
python run.py "Request an employment certificate for employee E003."
python run.py "Please process this case." --workflow-type hr_services --organization-id org-demo --user-id E003 --user-role employee
```

## Tests

```bash
source .venv/bin/activate
python -m pytest tests -q
```

Tests are deterministic and do not call Gemini. API coverage lives in `tests/test_api.py` (FastAPI `TestClient`; no live server required).

## Simulated components (explicit)

- In-memory HR / recruitment / onboarding / attendance / performance / training / offboarding / HR services stores
- In-memory notification inbox with fault injection
- In-memory human-approval checkpoints
- In-memory API execution index (list/get for the current process)
- Lexical (non-vector) knowledge search
- Deterministic agents (no live LLM required for current paths)

## Current limitations

- **Not production-ready** — no authentication, JWT/OAuth, PostgreSQL, Redis, Docker, or cloud deployment
- No frontend / dashboard yet
- API execution index and approval checkpoints are not durable across process restarts
- Organization/user/role fields are development context only until Module 5B
- No real email or external HRIS integrations
- Empty `organization_id` on many seed records matches any tenant filter (demo convenience)
- `leave_attendance` expects actionable leave requests; pure balance questions are better as `leave balance inquiry` → `hr_services`

## Later Module 5 phases (not started)

| Phase | Planned |
|-------|---------|
| **5B** | Authentication / RBAC |
| **5C** | Durable persistence (e.g. PostgreSQL) |
| Later | Frontend, monitoring, Docker, cloud deployment |

Stop after Module 5A in this repository phase for API delivery.
