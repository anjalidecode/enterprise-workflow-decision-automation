# Development of Enterprise Workflow Platform with Decision Automation System — Group 1

HR operations workflow automation and decision-support platform. Specialized agents collaborate through shared structured state, coordinated by a LangGraph orchestrator. This is **not** a chatbot and not a single LLM with tools.

## Current status (Modules 1–5B)

| Module | Scope |
|--------|--------|
| **1** | Agent foundation, `WorkflowState`, leave workflow prototype |
| **2** | Tool registry / selector / executor, simulated HR adapters |
| **3** | MemoryFacade (short-term, knowledge, long-term) |
| **4A–4H** | Platform spine + eight domain workflows |
| **5A** | FastAPI REST API layer over `WorkflowEngine` |
| **5B** | JWT authentication + development RBAC |

**Do not treat the API as production-ready.** The user store is in-memory for development/demo. Persistent database authentication, frontend, Docker, and cloud deployment are later phases.

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
WorkflowRouter → WorkflowRegistry → LangGraph workflows
    │
    ▼
WorkflowResult → API schemas + in-memory execution index
```

CLI (`python run.py`) remains a **local development/testing** interface with explicit org/user flags.  
FastAPI is the **authenticated application interface**.

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

### Authentication (Module 5B)

1. `POST /api/v1/auth/login` with username/password → JWT `access_token`
2. Call protected endpoints with `Authorization: Bearer <token>`
3. In Swagger: **Authorize** → paste the token (BearerAuth)

```bash
curl -s http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"hr001","password":"dev-password-123"}'
```

```bash
curl -s http://127.0.0.1:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### Demo users (temporary development store)

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

Passwords are stored only as **bcrypt hashes**. The store is process-local and will be replaced by database auth later.

### Roles and permissions (development scope)

| Role | Can | Cannot |
|------|-----|--------|
| **employee** | Run allowed self-service workflows for own `employee_id`; view own runs | Other employees' data; recruitment/offboarding; approvals; spoof identity |
| **manager** | Org workflows; approve/reject paused runs | Cross-organization access |
| **hr** | Org HR workflows; approve/reject; review employees | Cross-organization access |
| **admin** | Platform/org administration within org; approvals | Cross-organization access |

These are deterministic development rules — **not** production-grade enterprise IAM.

### Critical security rule

Authenticated JWT is the source of truth for `user_id`, `organization_id`, and `role`.  
Request body/query identity fields are **ignored** and cannot escalate privileges.

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

### Approval

```bash
curl -s -X POST \
  "http://127.0.0.1:8000/api/v1/workflows/{workflow_id}/approve" \
  -H "Authorization: Bearer $MANAGER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"Approved after review."}'
```

Approver identity comes from the JWT (`decided_by`), not from the request body.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `JWT_SECRET_KEY` for any non-development environment. Development falls back to an explicitly insecure local default when unset.

## CLI examples

```bash
python run.py "Check whether employee E001 can take 3 days of leave."
python run.py "Find candidates for the Python Backend Developer position."
```

## Tests

```bash
python -m pytest tests -q
```

## Current limitations / security notes

- Not production-ready security or IAM
- In-memory development user store (lost on restart; not a real IdP)
- In-memory workflow execution index and approval checkpoints
- No OAuth / SSO / PostgreSQL / Redis / Docker / frontend yet
- Demo passwords are shared and documented for local use only
- Do not commit real JWT secrets or credentials

## Later phases (not started)

| Phase | Planned |
|-------|---------|
| **5C+** | Durable persistence, frontend, monitoring, deployment |
