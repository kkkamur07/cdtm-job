# Supabase Cloud (CDTM Job Board)

This folder holds **Postgres migrations** in Git and optional **reference SQL** for demo data.  
We use **Supabase Cloud only** (no Docker / `supabase start` workflow in this repo).

Official docs: [Supabase CLI](https://supabase.com/docs/guides/cli) and [Database migrations](https://supabase.com/docs/guides/deployment/database-migrations).

## Prerequisites

1. Install the **Supabase CLI** and add it to your `PATH`.
2. A **Supabase Cloud** project (create one at [supabase.com](https://supabase.com/dashboard)).
3. Log in (needed for `link` / `db push`):

   ```bash
   supabase login
   ```

## Working directory (important)

Run **every** Supabase CLI command (`login`, `link`, `db push`, …) from the **repository root** — the folder that **contains** `supabase/`, not from inside `supabase/`.

If you `cd supabase` and run `supabase link` there, the CLI can create a **wrong nested path** `supabase/supabase/` (a second `supabase` folder inside the first). That is accidental; delete the inner `supabase/supabase` directory and run `link` again from the repo root.

After a correct `link` from the repo root, link metadata lives under **`supabase/.temp/`** (often gitignored). Migrations stay in **`supabase/migrations/`**.

## Apply migrations to your cloud project

Run from the **repository root** (the directory that contains `supabase/`).

### 1. Link this repo to the project (once per machine)

```bash
supabase link --project-ref <YOUR_PROJECT_REF>
```

- **Project ref**: Dashboard → **Project Settings** → **General** → **Reference ID**  
  (also in the URL: `https://supabase.com/dashboard/project/<ref>`).

### 2. Push migration files to the remote database

```bash
supabase db push
```

This applies any new SQL in `supabase/migrations/` that has not been applied yet. Safe to re-run.

### 3. Verify in the Dashboard

**Table Editor** should show `companies`, `jobs`, `job_locations`, and (after that migration) `notifications_log`.

### CI / automation

Use a personal access token and non-interactive patterns from Supabase docs; store `SUPABASE_ACCESS_TOKEN` and the project ref in CI secrets, then run the same `link` + `db push` steps (or use the recommended GitHub Action).

## Optional demo data on Cloud (`seed.sql`)

`seed.sql` is **not** run automatically on `db push`. To load demo rows on a **hosted** database:

1. Open **SQL Editor** in the Supabase Dashboard.
2. Paste the contents of `seed.sql` and run it **only on non-production** projects you are willing to truncate (it uses `TRUNCATE`).

For production, use real data via the API instead.

## Files in this directory

| Path | Purpose |
| ---- | ------- |
| `migrations/*.sql` | Versioned DDL (tables, RLS, indexes). Ship all schema changes here. |
| `seed.sql` | Optional demo inserts; apply manually in SQL Editor if you want sample rows on Cloud. |

## Troubleshooting

- **Nested folder `supabase/supabase/`** — You ran the CLI from inside `supabase/`. Remove the inner `supabase/` tree, `cd` to the repo root, run `supabase link` again.
- **`supabase: command not found`** — Install the CLI.
- **`db push` permission errors** — Run `supabase login` and confirm `supabase link` used the correct project ref.
- **`config.toml` missing` / not a Supabase project** — Some CLI versions expect `supabase/config.toml` even when you never run Docker. Run `supabase init --force` once from the repo root to regenerate it, then **do not** use `supabase start` unless you want local Docker. You can trim the generated file to defaults or leave it; unused local settings are ignored for `db push` only.
- **RLS / empty reads** — Browser must use the **anon** key; server uses **service role**. See **Security** below and [`.env.example`](../.env.example).

## Security: anon vs service role (required)

| Key | Where it belongs | What it can do |
| --- | ---------------- | -------------- |
| **anon** (`NEXT_PUBLIC_SUPABASE_ANON_KEY`) | **Browser only** (`frontend/.env.local`). | Whatever **RLS** allows (e.g. read published jobs). |
| **service_role** (`SUPABASE_SERVICE_ROLE_KEY`) | **Server only** (repo-root `.env` for FastAPI). Never `NEXT_PUBLIC_*`. | Bypasses RLS — never ship to the client. |

Rules:

1. Never put the service role in `frontend/.env*`.
2. Never `createClient(url, service_role)` in browser code.

See [`backend/api/deps.py`](../backend/api/deps.py), [`.env.example`](../.env.example), and [`frontend/.env.example`](../frontend/.env.example).
