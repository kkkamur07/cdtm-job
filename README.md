# CDTM Job Board (monorepo)

Job board for **jobs.cdtm.com**: Supabase Postgres + FastAPI (`backend/`) + Next.js (`frontend/` when added). V1 has **no end-user auth**; writes use the **service role** from the API only.

## Environment files

| File | Purpose |
| ---- | ------- |
| [`.env.example`](./.env.example) | Document every variable; **commit** this. |
| `.env` | Your real keys for local dev; **gitignored** — copy from `.env.example`. |
| `frontend/.env.example` | `NEXT_PUBLIC_*` for the browser Supabase client (when frontend exists). |

**Switching Supabase projects:** edit `.env` (and deployment secrets) with the new `SUPABASE_URL` and keys. **No code changes.** Migrations in `supabase/migrations/` define schema for any empty project.

**Production:** set the same variables on the host (Fly.io, Railway, Kubernetes secrets, etc.). Use **production** `CORS_ORIGINS` (e.g. `https://jobs.cdtm.com`) and never commit `.env`.

## Supabase: migrations vs optional seed

- **Migrations** (`supabase/migrations/*.sql`) apply to your **Supabase Cloud** project with **`supabase db push`** after `supabase link` (see [supabase/README.md](./supabase/README.md)).
- **Seed** ([`supabase/seed.sql`](./supabase/seed.sql)) is **not** run by `db push`. Use it only if you manually run it in the Dashboard **SQL Editor** (e.g. on a throwaway project). Do not run destructive seed SQL on production.

## Backend

See [backend/README.md](./backend/README.md).

```bash
cd backend
uv sync
# from repo root, fill .env with Supabase URL + service role key
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## Supabase CLI (Supabase Cloud)

See **[supabase/README.md](./supabase/README.md)** for `login`, `link`, `db push`, and troubleshooting.

```bash
supabase login
supabase link --project-ref <ref>
supabase db push
```

Official reference: [Database migrations](https://supabase.com/docs/guides/deployment/database-migrations).

## Auth (post-v1)

See [docs/auth-vnext.md](./docs/auth-vnext.md) for the planned Google OAuth + `profiles` rollout (not implemented in v1).
