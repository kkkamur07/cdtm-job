# CDTM Job Board — Backend

FastAPI app with light DDD: `jobs/`, `companies/`, `seekers/` (use cases in `application/`, adapters in `infrastructure/`, HTTP in `api/`).

## Setup

From **repository root** (parent of `backend/`):

```bash
cd backend
uv sync
cp ../.env.example ../.env   # copy the environment file. 
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Settings load **repo-root** ``.env`` by default, or the path in **BACKEND_ENV_FILE** if set—so you can point at any Supabase project without code changes.

## Endpoints

- `GET /health` — liveness
- `GET/POST/PATCH/DELETE` under `/api/v1/jobs` and `/api/v1/companies` — see `api/routers/`

Schema and CLI: [../supabase/README.md](../supabase/README.md).

## Layout

- `api/` — routers, settings, wiring (calls application services only)
- `jobs/application/` — `JobService.create_job`, Pydantic commands
- `jobs/infrastructure/` — Supabase repository
