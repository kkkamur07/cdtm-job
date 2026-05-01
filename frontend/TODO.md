# Frontend

## Done (MVP)

- OpenAPI client: `openapi.json` + `npm run openapi:generate` → `lib/api/generated/`
- Pages: home, `/jobs`, `/jobs/[jobId]`, `/post-job` (existing or **new** company inline), `/seekers`, `/seekers/[seekerId]`, `/seekers/new` — `/companies/new` redirects to `/post-job`
- Server Actions for job + seeker creates; listings + detail reads via FastAPI (service role on backend)
- **Routing:** All of the above live under `app/` — they are **public routes** by default (no `public/` folder involved; that directory is only for static files like `/brand/…`). Pages use **dynamic rendering** (`force-dynamic`) so builds do not require the API; for CDN caching later, consider `revalidate` / `fetch` cache once the client uses Next-aware fetching.

## Follow-ups

- **Auth / writes:** Gate `POST` flows in production (session, API key, or internal network).
- **Supabase in browser:** The `seekers` table may still lack `anon`/`authenticated` RLS policies; this UI reads seekers through **FastAPI only**. Add policies if you move reads/writes to the Supabase client.
