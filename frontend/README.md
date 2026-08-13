# Enterprise Workflow HR Frontend (Module 5D)

React + TypeScript + Vite application that consumes the existing FastAPI backend.

## Setup

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open http://127.0.0.1:5173

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Local development server |
| `npm run build` | Production build |
| `npm run preview` | Preview production build |
| `npm test` | Run Vitest suite |

## Environment

`VITE_API_BASE_URL` must point at the FastAPI v1 prefix, e.g. `http://127.0.0.1:8000/api/v1`.

Do not commit `frontend/.env`.
