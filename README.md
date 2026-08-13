# Development of Enterprise Workflow Platform with Decision Automation System — Group 1

HR operations workflow automation and decision-support platform. Specialized agents collaborate through shared structured state, coordinated by a LangGraph orchestrator. This is **not** a chatbot and not a single LLM with tools.

## Current status (Modules 1–5C)

| Module | Scope |
|--------|--------|
| **1** | Agent foundation, `WorkflowState`, leave workflow prototype |
| **2** | Tool registry / selector / executor, simulated HR adapters |
| **3** | MemoryFacade (short-term, knowledge, long-term) |
| **4A–4H** | Platform spine + eight domain workflows |
| **5A** | FastAPI REST API layer over `WorkflowEngine` |
| **5B** | JWT authentication + development RBAC |
| **5C** | PostgreSQL persistence for platform/application records |

**Do not treat the API as production-ready.** Domain HR JSON stores remain simulated. Frontend, Docker, and cloud deployment are later phases.

## Architecture

```
HTTP Client
    │
    ▼
FastAPI (app/api) ── JWT auth / RBAC / schemas / request id
    │
    ▼
WorkflowEngine.run() / resume()
    │
    ▼
WorkflowRouter → WorkflowRegistry → LangGraph + WorkflowState (live run state)
    │
    ▼
PersistenceService → PostgreSQL
    (organizations, users, workflow runs, decisions, approvals, audit, metrics)
```

**Separation of concerns**

| Concern | Store |
|---------|--------|
| Live workflow coordination | `WorkflowState` / LangGraph (in-process) |
| Platform records | PostgreSQL (Module 5C) |
| Domain HR simulation | JSON under `data/` |
| Knowledge corpus | `data/knowledge/` + KnowledgeStore |
| Long-term memory | JSONL via MemoryFacade |
| Short-term memory | Process-local |

CLI (`python run.py`) remains a **local development/testing** interface.  
FastAPI is the **authenticated application interface**.

## PostgreSQL setup (Module 5C)

### Requirements

- PostgreSQL 14+ (16 recommended)
- Python 3.12+ virtualenv with `requirements.txt`

### Environment

```bash
cp .env.example .env
```

Set at least:

```bash
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/enterprise_workflow
```

Optional pool settings: `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`.

If `DATABASE_URL` is missing, persistent operations fail clearly (no silent fake database).

### Migrations

```bash
source .venv/bin/activate
alembic upgrade head
```

### Seed development users

```bash
python -m app.database.seed
```

Seeds demo organizations and users with **bcrypt password hashes** (never plaintext).

### Demo credentials (local development only)

Password for all active demo users: `dev-password-123`

| Username | Role | Organization | Employee ID |
|----------|------|--------------|-------------|
| `employee001` | employee | `demo-org` | `E001` |
| `manager001` | manager | `demo-org` | `E100` |
| `hr001` | hr | `demo-org` | — |
| `admin001` | admin | `demo-org` | — |
| `inactive001` | employee (inactive) | `demo-org` | `E099` |
| `employee_other` | employee | `other-org` | `E050` |
| `hr_other` | hr | `other-org` | — |

### What is persisted

- Organizations
- Users (auth)
- Workflow runs (status, stage, outcome, API result snapshot)
- Decisions
- Approvals (including approval checkpoint for resume after restart)
- Audit snapshots
- Run metrics

### What remains simulated / non-Postgres

- Domain HR JSON stores (`data/employees`, jobs, attendance, …)
- Knowledge corpus (`data/knowledge/`)
- Long-term memory JSONL (`data/memory/long_term.jsonl`)
- Short-term memory
- Full LangGraph graph checkpointing (not implemented)

### Approval persistence limitation

Pending approvals store a **business/approval `WorkflowState` snapshot** so `WorkflowEngine.resume()` can continue after an application restart. This is **not** full LangGraph checkpoint persistence. Arbitrary mid-graph reconstruction is out of scope for Module 5C.

## FastAPI

```bash
source .venv/bin/activate
uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

| Resource | URL |
|----------|-----|
| Base API | `http://127.0.0.1:8000/api/v1` |
| Swagger UI | `http://127.0.0.1:8000/docs` |
| ReDoc | `http://127.0.0.1:8000/redoc` |

### Authentication

1. `POST /api/v1/auth/login` → JWT `access_token` (PostgreSQL user lookup)
2. Call protected endpoints with `Authorization: Bearer <token>`
3. In Swagger: **Authorize** → paste the token (BearerAuth)

```bash
curl -s http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"hr001","password":"dev-password-123"}'
```

### Roles and permissions (development scope)

| Role | Can | Cannot |
|------|-----|--------|
| **employee** | Run allowed self-service workflows for own `employee_id`; view own runs | Other employees' data; recruitment/offboarding; approvals; spoof identity |
| **manager** | Org workflows; approve/reject paused runs | Cross-organization access |
| **hr** | Org HR workflows; approve/reject; review employees | Cross-organization access |
| **admin** | Platform/org administration within org; approvals | Cross-organization access |

Authenticated JWT is the source of truth for `user_id`, `organization_id`, and `role`.  
Request body/query identity fields are **ignored**.

Repository queries always scope by `organization_id` — org-a cannot retrieve org-b workflows even when `workflow_id` is known.

### Endpoints

| Method | Path | Auth |
|--------|------|------|
| `GET` | `/api/v1/health` | Public |
| `POST` | `/api/v1/auth/login` | Public |
| `GET` | `/api/v1/auth/me` | Bearer |
| `GET` | `/api/v1/workflows/types` | Bearer |
| `POST` | `/api/v1/workflows/run` | Bearer |
| `GET` | `/api/v1/workflows` | Bearer |
| `GET` | `/api/v1/workflows/{id}` | Bearer + ownership |
| `GET` | `/api/v1/workflows/{id}/audit` | Bearer + ownership |
| `GET` | `/api/v1/workflows/{id}/metrics` | Bearer + ownership |
| `POST` | `/api/v1/workflows/{id}/approve` | Bearer + approver role |
| `POST` | `/api/v1/workflows/{id}/reject` | Bearer + approver role |

### Example authenticated workflow

```bash
TOKEN=$(curl -s http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"hr001","password":"dev-password-123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://127.0.0.1:8000/api/v1/workflows/run \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"request":"Check whether employee E001 can take 3 days of leave."}'
```

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# create PostgreSQL database, set DATABASE_URL
alembic upgrade head
python -m app.database.seed
```

Set `JWT_SECRET_KEY` for any non-development environment.

## Tests

Tests use an isolated PostgreSQL database (default):

```bash
TEST_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5433/enterprise_workflow_test
```

Create the test database once, then:

```bash
export DATABASE_URL="$TEST_DATABASE_URL"   # or rely on tests/conftest.py default
alembic upgrade head
python -m pytest tests -q
```

Tests truncate platform tables between cases and re-seed demo users. They do **not** target a developer’s production database when `TEST_DATABASE_URL` / the default test URL is used.

## CLI examples

```bash
python run.py "Check whether employee E001 can take 3 days of leave."
python run.py "Find candidates for the Python Backend Developer position."
```

## Current limitations / security notes

- Not production-ready security or IAM
- Domain HR data remains JSON-simulated
- Knowledge and long-term memory are not in PostgreSQL yet
- No full LangGraph checkpoint persistence
- No OAuth / SSO / Redis / Docker / frontend yet
- Demo passwords are shared and documented for local use only
- Do not commit real JWT secrets, database credentials, or `.env`

## Later phases (not started)

| Phase | Planned |
|-------|---------|
| **5D+** | Frontend, monitoring, deployment, deeper persistence |
