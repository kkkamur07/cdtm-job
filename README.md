# CDTM Job Board (monorepo)

Job board for **jobs.cdtm.com**: Supabase Postgres + FastAPI (`backend/`) + Next.js (`frontend/` when added). V1 has **no end-user auth**; writes use the **service role** from the API only.

## Environment files

| File | Purpose |
| ---- | ------- |
| [`.env.example`](./.env.example) | Pointer to backend vs frontend env layout. |
| [`backend/.env.example`](./backend/.env.example) | FastAPI / Python — **commit**; copy to `backend/.env` (gitignored). |
| [`frontend/.env.example`](./frontend/.env.example) | Next.js — copy to `frontend/.env.local` (gitignored). |

**Switching Supabase projects:** edit `backend/.env` (and deployment secrets) with the new `SUPABASE_URL` and keys. **No code changes.** Migrations in [`infrastructure/supabase/supabase/migrations/`](./infrastructure/supabase/supabase/migrations/) define schema for any empty project.

**Production:** set the same variables on the host (Fly.io, Railway, Kubernetes secrets, etc.). Use **production** `CORS_ORIGINS` (e.g. `https://jobs.cdtm.com`) and never commit `.env` files.

## Supabase: migrations vs optional seed

- **Migrations** (`infrastructure/supabase/supabase/migrations/*.sql`) apply to your **Supabase Cloud** project with **`supabase db push`** after `supabase link` from [`infrastructure/supabase`](./infrastructure/supabase) (see [infrastructure/supabase/README.md](./infrastructure/supabase/README.md)).
- **Seed** ([`infrastructure/supabase/supabase/seed.sql`](./infrastructure/supabase/supabase/seed.sql)) runs only on **local** `supabase db reset`; it is **not** run by `db push`. Do not run destructive seed SQL on production.

## Backend

See [backend/README.md](./backend/README.md).

```bash
uv sync
# copy backend/.env.example → backend/.env and fill Supabase URL + service role key
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## Supabase CLI (Supabase Cloud)

See **[infrastructure/supabase/README.md](./infrastructure/supabase/README.md)** for `login`, `link`, `db push`, and troubleshooting.

```bash
supabase login
cd infrastructure/supabase
supabase link --project-ref <ref>
supabase db push
```

Official reference: [Database migrations](https://supabase.com/docs/guides/deployment/database-migrations).

## Auth (post-v1)

See [docs/auth-vnext.md](./docs/auth-vnext.md) for the planned Google OAuth + `profiles` rollout (not implemented in v1).
