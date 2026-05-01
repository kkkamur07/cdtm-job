# Supabase (CDTM job board)

Migrations and CLI config live under `supabase/` here (`--workdir` / `cd` to `infrastructure/supabase`).

## Cloud-only (no local Supabase stack)

If you **do not** run `supabase start` (no Docker local stack), you still use the CLI against **Supabase Cloud**:

```bash
cd infrastructure/supabase
supabase login
supabase link --project-ref "<YOUR_20_CHAR_PROJECT_REF>"
supabase db push
```

That applies `supabase/migrations/*.sql` to the **linked remote** database.

**`config.toml`:** Ports, Studio, Realtime, local Auth tuning, pooler, etc. matter when you run **`supabase start`**. For cloud-only day-to-day work they are effectively unused; the file stays so the CLI version you use has a valid project layout (same idea as `supabase init`). You can trim it later if your CLI version allows—when in doubt, leave it.

**Seed data:** `supabase/seed.sql` runs automatically only on **`supabase db reset`** (local). For a remote dev project, paste its contents into **Dashboard → SQL Editor** if you want dummy rows—never run destructive seeds on production.

## Optional: full local stack

Only if you want Docker Postgres + Studio matching cloud:

```bash
cd infrastructure/supabase
supabase start
supabase db reset   # migrations + seed.sql
```

## Layout

| Path | Purpose |
| ---- | ------- |
| `supabase/config.toml` | CLI / local stack settings (`supabase init` template); local sections irrelevant without `supabase start` |
| `supabase/migrations/` | Schema changes (`db push` to cloud) |
| `supabase/seed.sql` | Local reset hook or paste into SQL Editor on cloud |

Schema matches the backend domain models in `backend/*/domain/`.
