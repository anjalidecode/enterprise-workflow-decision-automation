# WorkSphere AI

**Product:** WorkSphere AI — AI-Powered HR Workflow & Decision Automation  

**Repository:** `enterprise-workflow-decision-automation` (Group 1)

Intelligent HR workflows powered by specialized agents, policy-aware decisions, human approval, and auditable automation. This is **not** a chatbot and not a single LLM with tools.

The customer-facing product name is **WorkSphere AI**. The repository name is for source control only.

## Current status (Modules 1–5G)

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
| **5E** | Admin user management, invitations, and role assignment |
| **5F** | Gemini request understanding + grounded responses (optional API key) |
| **5G** | Email notification system (console + SMTP providers) |

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
LLM request understanding (Gemini or deterministic fallback)
    │  structured intent only — never executes HR actions
    ▼
WorkflowEngine.run() / resume()
    │
    ▼
WorkflowRouter → WorkflowRegistry → LangGraph + WorkflowState (live run state)
    │
    ▼
Specialized agents → ToolRegistry / ToolExecutor → MemoryFacade / KnowledgeStore
    │
    ▼
Policy + decision + validation + human approval + action
    │
    ▼
PersistenceService → PostgreSQL
```

**Separation of concerns**

| Concern | Store / layer |
|---------|----------------|
| UI / UX | React frontend (`frontend/`) |
| AuthN / AuthZ | FastAPI JWT + RBAC |
| Natural language | Gemini via `app/llm` (optional); deterministic fallback without a key |
| Live workflow coordination | `WorkflowState` / LangGraph |
| Decisions and actions | Specialized agents + tools + policy (not Gemini) |
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

Create a real organization account at `/register` (email + password + company name).

- The first user of a **new** organization is assigned `admin`.
- Later public registrations for the **same** organization receive `employee`.
- Public signup cannot choose `admin`, `hr`, or `manager`.
- Role assignment for operational staff happens in **User Management** (administrators only).

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
| `/users` | Admin user management (invite, roles, activate/deactivate) |
| `/activate` | Set a password for an invited account |
| `/audit` | Aggregated audit snapshots |
| `/settings` | Profile, session, and (admin) link to User Management |

### Roles (UI visibility)

| Role | Typical navigation |
|------|--------------------|
| **employee** | Dashboard, My Workflows, My Requests, My Leave, My Attendance, My Training, HR Services, settings |
| **manager** | + Team Workflows, Approvals, Recruitment, Analytics |
| **hr** | + Employees, Offboarding, Audit, Analytics |
| **admin** | Broad platform navigation, including User Management |

Frontend hiding a menu item is **not** security. Backend RBAC remains authoritative.

### User management and invitations

Organization administrators can open **User Management** (`/users` or Settings → User Management) to:

- List users in **their organization only**
- Invite users as Employee, Manager, or HR (not Admin)
- Change operational roles
- Deactivate / reactivate accounts

Invited users cannot sign in until they set a password at `/activate` with a one-time, expiring token. Invitation emails are sent through the notification system (console or SMTP). The invite API still returns an activation link so admins can share it if delivery fails. Tokens are stored hashed; passwords are stored as bcrypt hashes only.

An administrator cannot deactivate themselves or leave the organization with zero admins.

Inactive and invited accounts are rejected at login. Authorization uses the authenticated JWT user — the API ignores client-supplied `role`, `organization_id`, and `employee_id`.

## Email notifications (Module 5G)

WorkSphere AI sends transactional email for meaningful business events. Agents never call SMTP; they continue to use `NotificationServicePort` / `notify_*` tools. Auth and workflow layers emit typed events to `BusinessNotificationService` → `EmailProviderPort`.

```
Business event
     ↓
BusinessNotificationService (templates, recipients, idempotency)
     ↓
EmailProviderPort
     ↓
Console provider (dev)  OR  SMTP provider (real delivery)
     ↓
Recipient email
```

### Event types

| Event | When | Recipient |
|-------|------|-----------|
| `USER_REGISTERED` | First user creates a new organization | New admin |
| `USER_INVITED` | Admin invites employee/manager/hr | Invitee |
| `WORKFLOW_PENDING_APPROVAL` | Workflow enters `awaiting_human_approval` | Authorized approvers |
| `WORKFLOW_APPROVED` | Approver approves | Requester |
| `WORKFLOW_REJECTED` | Approver rejects / decision reject | Requester |
| `WORKFLOW_COMPLETED` | Meaningful auto-complete outcome | Requester |
| `WORKFLOW_BLOCKED` | Blocked outcome | Requester |

Recipients are resolved from PostgreSQL users (organization-scoped). Client-supplied `recipient_email` / `approver_email` are ignored.

### Development (console)

```bash
EMAIL_PROVIDER=console
FRONTEND_BASE_URL=http://127.0.0.1:5173
```

Console mode prints a safe email preview (event, recipient, subject, body). No SMTP credentials required. Invitation activation tokens appear only inside the rendered activation link for local testing — they are not written to ordinary structured logs as bare secrets.

### Real SMTP

```bash
EMAIL_PROVIDER=smtp
SMTP_HOST=...
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_FROM_EMAIL=...
SMTP_FROM_NAME=WorkSphere AI
SMTP_USE_TLS=true
FRONTEND_BASE_URL=https://your-app.example.com
```

Never commit real SMTP credentials. Never put SMTP settings in frontend env vars.

### Failure handling & idempotency

- Account creation and workflow decisions succeed even when email fails.
- Successful deliveries are idempotent via `notification_events` (`organization_id` + `idempotency_key`).
- Failed deliveries can be retried without duplicating a prior successful send.
- Low-cardinality metrics: `notification_sent_total`, `notification_failed_total`, `notification_latency_seconds` (labels: provider, event_type, status only).

### Local testing

1. `EMAIL_PROVIDER=console`
2. Register a new organization → welcome preview in the API console
3. Admin → User Management → Invite → invitation preview + activation link
4. Employee submits a leave request that needs approval → approver preview
5. Approver approves/rejects → requester preview

Apply the Alembic migration after pull:

```bash
alembic upgrade head
```

### Frontend tests

```bash
cd frontend
npm test
```

### Frontend limitations

- No dedicated approvals inbox endpoint — Approvals page filters `status=awaiting_human_approval`
- Workflow list summaries do not include `user_id` / “requested by”
- JWT stored in `localStorage` for development convenience (not production hardening)
- Toast UI confirms invitation/registration; outbound email uses the backend notification providers

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
| `POST` | `/api/v1/auth/activate` | Public (invitation token) |
| `GET` | `/api/v1/auth/me` | Bearer |
| `GET` | `/api/v1/users` | Bearer + admin |
| `POST` | `/api/v1/users/invite` | Bearer + admin |
| `GET` | `/api/v1/users/{id}` | Bearer + admin |
| `PATCH` | `/api/v1/users/{id}` | Bearer + admin |
| `POST` | `/api/v1/users/{id}/activate` | Bearer + admin |
| `POST` | `/api/v1/users/{id}/deactivate` | Bearer + admin |
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

## Gemini / natural-language requests (Module 5F)

Gemini improves **language understanding and communication**. It does **not** replace `WorkflowEngine`, LangGraph, tools, policy, or human approval. It never directly executes enterprise actions.

```
User request
    → LLM request understanding (structured intent)
    → WorkflowRouter (authoritative, deterministic)
    → WorkflowEngine → LangGraph → specialized agents
    → tools / memory / knowledge
    → policy → decision → validation → approval if required → action
    → optional grounded response rewrite
```

### Setup

1. Create a Google Gemini API key.
2. Add it to local `.env` (never commit `.env`, never send the key to React):

```bash
GOOGLE_API_KEY=your-key
GEMINI_MODEL=gemini-3.5-flash
```

3. Start the backend and frontend as usual.
4. On **My Requests**, leave workflow as auto-route and type a request such as:  
   `I need three days off next week. Can you check if I have enough leave?`

**Gemini is optional for local deterministic operation.** If `GOOGLE_API_KEY` is empty, WorkSphere AI uses a labeled deterministic fallback. The UI does not pretend Gemini was used.

Explicit `workflow_type` (domain forms and structured API clients) skips LLM routing.

`POST /api/v1/workflows/run` accepts `request` or `request_text`. Existing structured bodies keep working.

### Requirements traceability

| Project statement | Implementation |
|-------------------|----------------|
| Multi-agent coordination | Specialized agents + LangGraph + `WorkflowState` |
| Intelligent decision support | Analysis + decision + policy + evidence |
| Tool & system integration | `ToolRegistry` + `ToolExecutor` + service adapters |
| Shared knowledge & memory | `MemoryFacade` + `KnowledgeStore` + long-term memory |
| Workflow automation | `WorkflowEngine` + LangGraph + approvals/actions |
| Enterprise API | FastAPI + JWT + RBAC + PostgreSQL |
| LLM | Gemini request understanding + optional grounded responses |

### LLM security and observability

- Prompts receive only the request text plus role / employee_id / current date / registered workflow types
- JWTs, passwords, database URLs, and `GOOGLE_API_KEY` are never sent to the model or to the frontend
- Safe metadata (`provider`, `model`, `operation`, `status`, `duration`, token usage) is stored on the run
- Process metrics: `llm_requests_total`, `llm_failures_total`, `llm_latency_seconds` (low-cardinality labels)

Automated tests mock the provider and never call the real Gemini API.

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
| **5E** | Admin user management complete in this phase |
| **5F** | Gemini NL understanding complete in this phase |
| **5G** | Email notification system complete in this phase |
| **Later** | Monitoring, deployment, deeper persistence |
