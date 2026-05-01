# CDTM Job Board (monorepo)

Job board for **jobs.cdtm.com**: Supabase Postgres + FastAPI (`backend/`) + Next.js (`frontend/`). V1 has **no end-user auth**; writes use the **service role** from the API only.

## Run the project locally

From the **repository root** (where `pyproject.toml` lives):

1. **Backend** — install deps and run the API (needs `backend/.env`; copy from [`backend/.env.example`](./backend/.env.example)):

   ```bash
   uv sync
   uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Or use the FastAPI CLI (good for production-like multi-worker runs):

   ```bash
   uv run fastapi run backend/main.py --workers 4 
   fastapi run backend/main.py --workers 4
   ```

2. **Frontend** — in another terminal:

   ```bash
   cd frontend
   cp .env.example .env.local   # set NEXT_PUBLIC_API_URL=http://localhost:8000
   npm install
   npm run dev
   ```

   Open [http://localhost:3000](http://localhost:3000). Ensure backend `CORS_ORIGINS` includes `http://localhost:3000` (see [`backend/core/settings.py`](./backend/core/settings.py)).

More detail: [backend/README.md](./backend/README.md), [frontend/README.md](./frontend/README.md).

## Supabase

Everything you want with supabase is configured in `infrastructure/supabase`

Sequence of commands : 

```bash
supabase login
supabase link --project-ref <YOUR-PROJECT-REF>
supabase db push # For the migrations to take effect
```

## Environment files

| File | Purpose |
| ---- | ------- |
| [`.env.example`](./.env.example) | Pointer to backend vs frontend env layout. |
| [`backend/.env.example`](./backend/.env.example) | FastAPI / Python — **commit**; copy to `backend/.env` (gitignored). |
| [`frontend/.env.example`](./frontend/.env.example) | Next.js — copy to `frontend/.env.local` (gitignored). |


## How are the APIs designed?

Routers expose **REST** endpoints with explicit **response models**, optional **pagination** (`skip` / `limit`), and **errors** surfaced as HTTP exceptions. The sketch below matches the style used in [`backend/api/routers/`](./backend/api/routers/) (names abbreviated):

```python
@router.get("/", response_model=ItemsPublic)
def list_things(
    service: ThingServiceDep,
    skip: int = 0,
    limit: int = 50,  # pagination
) -> ItemsPublic:
    try:
        ...
    except DomainError as e:
        raise HTTPException(status_code=404, detail="...")

# Typical verbs on a resource:
@router.post("/", response_model=ThingPublic, status_code=201)
def create_thing(...): ...

@router.put("/{id}", response_model=ThingPublic)
def replace_thing(...): ...

@router.patch("/{id}", response_model=ThingPublic)
def update_thing(...): ...

@router.delete("/{id}", status_code=204)
def delete_thing(...) -> None: ...   # or a small JSON message if you standardise on one style
```

**Conventions:**

1. **Response models** — Public DTOs (e.g. `JobPublic`, `CompaniesPublic`) live under [`backend/api/schemas/`](./backend/api/schemas/) so **OpenAPI** stays stable and generated clients see clear shapes.
2. **Pagination** — List endpoints return a page object (`items` + `total`) with `skip` / `limit` query params where applicable.
3. **Errors** — Failures are mapped to **`HTTPException`** (and shared helpers in [`backend/api/route_errors.py`](./backend/api/route_errors.py) / [`backend/api/error_handling.py`](./backend/api/error_handling.py)).

The backend follows a **domain-oriented layout**: domain models per bounded context (`jobs/`, `companies/`, `seekers/`), application **services** + **commands**, infrastructure **repositories** (Supabase), and **public** schemas at the API boundary so you can evolve internals without breaking clients.

## Backend package layout

Intended shape (see repo for full filenames):

```txt
backend/
  __init__.py
  main.py                    # ASGI entry: exports app from backend.api.main
  core/
    __init__.py
    settings.py              # pydantic-settings / env
    ...
  api/
    __init__.py
    main.py                  # FastAPI app, CORS, router includes
    deps.py                  # Depends(get_settings), service deps
    error_handling.py
    route_errors.py
    schemas/                  # public DTOs for OpenAPI (jobs_public, companies_public, …)
    routers/
      health.py
      jobs.py
      companies.py
      seekers.py
  jobs/
    domain/
      job.py                  # aggregates + enums
    services/
      commands.py             # JobCreate / JobUpdate
      service.py              # application service
      ports.py
    infrastructure/
      repository.py
  companies/
    ...
  seekers/
    ...
```

## Integration tests

Focus right now: **call Supabase through the API** — POST payloads, assert responses, then **read back** or verify persistence.

Pattern:

```python
# dummy payload → POST → assert status/body → GET or DB check
```

Run from the **repo root** so imports resolve (`backend` package):

```bash
python -m pytest tests/integration
```

Or with **uv** (recommended):

```bash
uv run pytest tests/integration
```

Using `python -m pytest` or `uv run pytest` avoids stray **`ModuleNotFoundError: backend`** when the working directory / `PYTHONPATH` is wrong.

>[!Major]
> After API changes (repo root), refresh the frontend OpenAPI client:

```bash
uv run python -c "import json, pathlib; from backend.api.main import app; pathlib.Path('frontend/openapi.json').write_text(json.dumps(app.openapi()))" && cd frontend && npm run openapi:generate
```

See [frontend/README.md](./frontend/README.md) for dev/build.
