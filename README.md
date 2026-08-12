# Development of Enterprise Workflow Platform with Decision Automation System — Group 1

HR Operations workflow automation and decision-support platform. Specialized agents collaborate through shared structured state, coordinated by a LangGraph orchestrator. This is not a chatbot and not a single LLM with tools.

## Current implementation (Module 1 — Agent Foundation)

Module 1 delivers the first working multi-agent HR workflow:

**Leave & Attendance** — job of checking whether an employee can take leave, using employee records, leave balances, and a deterministic HR policy.

Agents communicate only through `WorkflowState`. Each agent is a separate LangGraph node with one responsibility. After validation, the graph branches:

- valid and executable approval → Action Agent → Response Agent
- validation failure, rejection, or human approval required → Response Agent (Action Agent is skipped)

Module 1 uses deterministic Python logic in agent nodes so the workflow is testable without a Gemini API key. LLM settings are configured for later modules.

## Architecture

```
User Request
    │
    ▼
Orchestrator Agent     identify workflow type
    │
    ▼
Planner Agent          parse request and define tasks
    │
    ▼
Research Agent         load employee / leave-balance data
    │
    ▼
Policy Agent           evaluate leave policy rules
    │
    ▼
Analysis Agent         compare data, policy, and request
    │
    ▼
Decision Agent         approve / reject / pending approval
    │
    ▼
Validation Agent       verify the decision before any action
    │
    ├── validation failed or human approval required or not executable
    │     └──► Response Agent ──► END
    │
    └── valid executable approval
          └──► Action Agent (simulated HR update)
                 └──► Response Agent ──► END
```

Shared state lives in `app/orchestration/state.py`. Simulated HR data lives in `data/`. Agents do not read files directly; they use `app/services/`.

## Setup

Python 3.12 is required.

```bash
cd /home/vinay/Documents/Code/enterprise-workflow-decision-automation
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If `.venv` already exists, activate it and install requirements:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy the example environment file and add a Gemini key only if you intend to use the LLM later. Module 1 does not require it.

```bash
cp .env.example .env
```

`.env.example` placeholders:

```
GOOGLE_API_KEY=
GEMINI_MODEL=
APP_ENV=development
```

Do not commit a real API key. The default Gemini model in settings is `gemini-2.5-flash` when `GEMINI_MODEL` is left empty.

## Run the leave workflow

From the project root, with `.venv` activated:

```bash
python run.py
```

Or pass a custom request:

```bash
python run.py "Check whether employee E001 can take 3 days of leave from 2026-08-17."
python run.py "Check whether employee E002 can take 3 days of leave from 2026-08-17."
python run.py "Check whether employee E001 can take 8 days of leave from 2026-08-17."
```

Sample employees:

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
- HR systems are simulated with local JSON files.
- The Action Agent updates workflow state only; it does not persist changes to `data/`.
- There is no dashboard, REST API, PostgreSQL, RAG, tool registry, or cloud deployment yet.
- Human approval is detected and reported; there is no approval UI.

## Planned modules

- **Module 2:** Tool integration, action execution against APIs/databases, monitoring, validation and error handling.
- **Module 3:** Richer agent communication, short-term and long-term memory, shared knowledge.
- **Module 4:** Remaining HR workflows (recruitment, onboarding, policy queries, performance, offboarding), dynamic orchestration, recommendations.
- **Module 5:** REST APIs, web dashboard, monitoring, logging, deployment, and performance work.
