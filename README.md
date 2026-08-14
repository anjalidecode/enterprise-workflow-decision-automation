# WorkSphere AI

**Product:** WorkSphere AI — AI-Powered HR Workflow & Decision Automation  

**Repository:** `enterprise-workflow-decision-automation` (Group 1)

Intelligent HR workflows powered by specialized agents, policy-aware decisions, human approval, and auditable automation. This is **not** a chatbot and not a single LLM with tools.

The customer-facing product name is **WorkSphere AI**. The repository name is for source control only.

## Current status (Modules 1–5D)

| Module | Scope |
|--------|--------|
| **1** | Agent foundation, `WorkflowState`, leave workflow prototype |
| **2** | Tool registry / selector / executor, simulated HR adapters |
| **3** | MemoryFacade (short-term, knowledge, long-term) |
| **4A–4H** | Platform spine + eight domain workflows |
| **5A** | FastAPI REST API layer over `WorkflowEngine` |
| **5B** | JWT authentication + development RBAC |
| **5C** | PostgreSQL persistence for platform/application records |
| **5D** | WorkSphere AI professional React frontend + public registration |

**Do not treat the stack as production-ready.** Domain HR JSON stores remain simulated. Docker and cloud deployment are later phases.

## Architecture

```
Browser
    │
    ▼
React + TypeScript frontend (frontend/)
    │  JWT Bearer + REST
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
```

**Separation of concerns**

| Concern | Store / layer |
|---------|----------------|
| UI / UX | React frontend (`frontend/`) |
| AuthN / AuthZ | FastAPI JWT + RBAC |
| Live workflow coordination | `WorkflowState` / LangGraph |
| Platform records | PostgreSQL (Module 5C) |
| Domain HR simulation | JSON under `data/` |

CLI (`python run.py`) remains a **local development/testing** interface.  
FastAPI is the **authenticated application interface**.  
The frontend **never** talks to PostgreSQL or reimplements `WorkflowEngine`.

## Frontend (WorkSphere AI)

The browser application is branded **WorkSphere AI**. Internal module names and the repository name are not shown on customer-facing screens.

### Technology

- React 19 + TypeScript + Vite
- React Router
- Central API client with typed methods
- Auth context (`useAuth`) + toast notifications
- Role-aware navigation (UI only; backend remains authoritative)
- Public registration → PostgreSQL users (bcrypt) → login JWT

### Setup

```bash
# Backend (terminal 1)
source .venv/bin/activate
uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000

# Frontend (terminal 2)
cd frontend
cp .env.example .env
npm install
npm run dev
```

| Resource | URL |
|----------|-----|
| Frontend app | http://127.0.0.1:5173 |
| Base API | http://127.0.0.1:8000/api/v1 |
| Swagger UI | http://127.0.0.1:8000/docs |
| ReDoc | http://127.0.0.1:8000/redoc |

Frontend env:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Do not commit `frontend/.env`.

### Login / registration / demo accounts

Create a real organization account at `/register` (email + password + company name). The first user of a **new** organization is assigned `admin`. Later public users joining that organization receive `employee`. Role cannot be chosen in the UI.

Existing development users still work.

Password for all active demo users: `dev-password-123`

| Username | Role | Organization | Employee ID |
|----------|------|--------------|-------------|
| `employee001` | employee | `demo-org` | `E001` |
| `manager001` | manager | `demo-org` | `E100` |
| `hr001` | hr | `demo-org` | — |
| `admin001` | admin | `demo-org` | — |

### Frontend pages

| Route | Purpose |
|-------|---------|
| `/login` | Sign in |
| `/register` | Create organization account (PostgreSQL) |
| `/dashboard` | Operational dashboard from real API data |
| `/workflows` | Searchable/filterable workflow list |
| `/workflows/:id` | Agent timeline, decision, tools, memory, audit, metrics, approval |
| `/approvals` | Human approval center |
| `/analytics` | Counts and averages from visible workflow runs |
| `/requests` | Employee self-service start-workflow form |
| `/leave` `/attendance` `/recruitment` `/onboarding` `/performance` `/training` `/offboarding` `/hr-services` | Domain request forms → `POST /workflows/run` |
| `/employees` | HR activity view (no employees directory API yet) |
| `/audit` | Aggregated audit snapshots |
| `/settings` | Profile and session |

### Roles (UI visibility)

| Role | Typical navigation |
|------|--------------------|
| **employee** | Dashboard, My Workflows, My Requests, My Leave, My Attendance, My Training, HR Services, settings |
| **manager** | + Team Workflows, Approvals, Recruitment, Analytics |
| **hr** | + Employees, Offboarding, Audit, Analytics |
| **admin** | Broad platform navigation |

Frontend hiding a menu item is **not** security. Backend RBAC remains authoritative.

### Frontend tests

```bash
cd frontend
npm test
```

### Frontend limitations

- No `GET /employees` directory endpoint — Employees page uses auth identity + workflow activity
- No dedicated approvals inbox endpoint — Approvals page filters `status=awaiting_human_approval`
- Workflow list summaries do not include `user_id` / “requested by”
- JWT stored in `localStorage` for development convenience (not production hardening)
- UI notifications are toasts, not email

## PostgreSQL setup (Module 5C)

### Requirements

- PostgreSQL 14+ (16 recommended)
- Python 3.12+ virtualenv with `requirements.txt`
- Node.js 20+ for the frontend

### Environment

```bash
cp .env.example .env
```

Set at least:

```bash
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/enterprise_workflow
```

CORS includes the Vite origin:

```bash
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173
```

### Migrations and seed

```bash
source .venv/bin/activate
alembic upgrade head
python -m app.database.seed
```

## FastAPI

```bash
source .venv/bin/activate
uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

### Authentication

1. `POST /api/v1/auth/login` → JWT `access_token`
2. Call protected endpoints with `Authorization: Bearer <token>`
3. Frontend AuthContext attaches the header automatically after login

### Endpoints

| Method | Path | Auth |
|--------|------|------|
| `GET` | `/api/v1/health` | Public |
| `POST` | `/api/v1/auth/login` | Public |
| `POST` | `/api/v1/auth/register` | Public |
| `GET` | `/api/v1/auth/me` | Bearer |
| `GET` | `/api/v1/workflows/types` | Bearer |
| `POST` | `/api/v1/workflows/run` | Bearer |
| `GET` | `/api/v1/workflows` | Bearer |
| `GET` | `/api/v1/workflows/{id}` | Bearer + ownership |
| `GET` | `/api/v1/workflows/{id}/audit` | Bearer + ownership |
| `GET` | `/api/v1/workflows/{id}/metrics` | Bearer + ownership |
| `POST` | `/api/v1/workflows/{id}/approve` | Bearer + approver role |
| `POST` | `/api/v1/workflows/{id}/reject` | Bearer + approver role |

## Setup (full stack)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# create PostgreSQL database, set DATABASE_URL
alembic upgrade head
python -m app.database.seed

cd frontend
cp .env.example .env
npm install
```

Set `JWT_SECRET_KEY` for any non-development environment.

## Tests

### Backend

```bash
export DATABASE_URL="$TEST_DATABASE_URL"   # or rely on tests/conftest.py default
alembic upgrade head
python -m pytest tests -q
```

### Frontend

```bash
cd frontend && npm test
```

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
- No OAuth / SSO / Redis / Docker yet
- Demo passwords are shared and documented for local use only
- Do not commit real JWT secrets, database credentials, or `.env`

## Later phases (not started)

| Phase | Planned |
|-------|---------|
| **Post-5D** | Monitoring, deployment, deeper persistence, employee directory API |
