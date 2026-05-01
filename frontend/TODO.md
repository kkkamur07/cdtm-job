# Frontend TODO

- **Seekers + RLS:** The `seekers` table has RLS enabled but **no policies** for `anon` / `authenticated`. Without `SELECT` (and later `INSERT`/`UPDATE`) policies, the Supabase client **cannot** read or write seeker rows with the anon key or user JWT. Only the backend **service role** bypasses RLS. When the UI should load seeker profiles from Supabase directly, add the appropriate policies (or keep reads behind the FastAPI API only).
