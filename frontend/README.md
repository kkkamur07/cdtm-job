# CDTM Community, frontend

Next.js 16 (App Router), React 19, TypeScript, Tailwind v4. It talks to the
FastAPI backend in `../backend` over `/api/v1` and holds no database connection
of its own.

## Run it

```bash
npm install
cp .env.example .env.local     # defaults point at http://localhost:8000
npm run dev                    # http://localhost:3000
```

With the backend running on port 8000 (`uv run uvicorn backend.main:app --reload
--port 8000` from the repo root) and `AUTH_DEV_LOGIN_ENABLED=true` in its
environment, `/login` will sign you in with any `@cdtm.com` address. CORS on the
backend already allows `http://localhost:3000`.

## Scripts

| Script                 | What it does                                                        |
| ---------------------- | ------------------------------------------------------------------- |
| `npm run dev`          | Dev server on :3000                                                  |
| `npm run build`        | Production build                                                     |
| `npm start`            | Serve the production build                                           |
| `npm run lint`         | ESLint (flat config, `eslint-config-next`)                           |
| `npm run typecheck`    | `tsc --noEmit`                                                       |
| `npm run generate:api` | Regenerate `src/api/schema.d.ts` from `openapi/openapi.json`         |
| `npm run check:api`    | Fail if the committed schema is stale (for CI)                       |
| `npm run ingest`       | Rebuild the member index, profiles and avatars under `public/`       |

`openapi/openapi.json` is produced by the backend. After any backend API change,
copy the new file in and run `npm run generate:api`; the generated
`src/api/schema.d.ts` is committed and never hand-edited.

## Environment

Every variable is `NEXT_PUBLIC_`, which means it is shipped to the browser.
**Never put a secret here.** The Supabase service-role key in particular must
never leave the backend.

| Variable                               | Required               | Meaning                                             |
| -------------------------------------- | ---------------------- | --------------------------------------------------- |
| `NEXT_PUBLIC_API_URL`                  | no (`localhost:8000`)  | FastAPI base URL. Also serves uploaded images.       |
| `NEXT_PUBLIC_AUTH_MODE`                | no                     | `dev` or `supabase`. See below.                      |
| `NEXT_PUBLIC_SUPABASE_URL`             | supabase mode          | Project URL.                                         |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | supabase mode          | Publishable key (`sb_publishable_…`).                |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY`        | fallback               | Accepted for projects created before the key rename. |

`NEXT_PUBLIC_API_URL` is read by `next.config.ts` at build time to allow that
host in `images.remotePatterns`, so changing it needs a rebuild, not just a
restart.

## Auth

Two modes, one interface. Every page and every request reads the same
`accessToken`; only where it comes from differs.

```
src/auth/
  mode.ts           AUTH_MODE, isDevAuth, isSupabaseAuth, cookie name
  contract.ts       dev sign-in shapes, aliased from the generated schema
  session.ts        server-only: getIdentity(), getAccessToken()
  AuthProvider.tsx  client: restores the session, exposes token + sign in / out
src/app/api/auth/dev-session/route.ts   GET / POST / DELETE the httpOnly cookie
src/lib/supabase/    client.ts, server.ts, proxy.ts, env.ts  (supabase mode only)
src/proxy.ts         Next 16 proxy (formerly middleware): refreshes the session
```

**dev mode** (default when `NEXT_PUBLIC_SUPABASE_URL` is unset). `/login` posts
to `POST /api/v1/auth/dev/login` with `{ email, member_slug }` and gets back
`{ access_token, token_type, expires_in, me }`. The token is handed to
`POST /api/auth/dev-session`, a Next route handler that parks it in an httpOnly
cookie. `GET /api/v1/auth/dev/members?q=` backs the optional "sign in as a roster
member" picker and needs no token.

**supabase mode**. `@supabase/ssr` with cookie-backed sessions: Google OAuth with
`queryParams: { hd: "cdtm.com" }`, `/auth/callback` exchanges the code,
`src/proxy.ts` refreshes the session on every request, and `getClaims()` (not
`getSession()`) is what authorization is decided on.

**How a page gets the token.**

- Server components and route handlers: `await getAccessToken()` from
  `@/auth/session`. In dev mode it decodes the httpOnly cookie; in supabase mode
  it verifies the JWT with `getClaims()` and then reads the raw token from the
  session. It is wrapped in `React.cache`, so one render verifies once.
  `src/api/server.ts` calls it for you: every `load*` loader attaches the bearer.
- Client components: `useSession().token`, and the `openapi-fetch` client picks
  it up automatically through `setAccessTokenReader`, so hooks never pass it by
  hand.

To switch a deployment to Supabase: create the project, enable the Google
provider, add `<origin>/auth/callback` to the redirect allow list, set
`NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, and set
`NEXT_PUBLIC_AUTH_MODE=supabase`. Nothing else in the app changes.

## Images

Storage buckets are private, so the browser never touches storage. Uploads go to
the API:

```
POST   /api/v1/media/{kind}          multipart, field "file"  (jpeg/png/webp, 5 MB)
GET    /api/v1/media/{bucket}/{key}  public, cache-immutable
DELETE /api/v1/media/{bucket}/{key}
```

`kind` is `job-image`, `housing-photo` or `avatar`. The returned `url` is what
goes into `jobs.image_url` and `housing_listings.photo_urls`.
`src/components/ImageUpload.tsx` is the shared picker (drag and drop, preview,
progress, per-file errors, remove) and is used by the job and housing forms.
`src/api/media.ts` holds the upload call and `mediaUrl()`, which absolutises a
relative API path.

Member avatars are different: they are produced by `scripts/ingest.mjs` and
served as static files from `public/avatars/`.

## Layout

Conventions, commands and domain language for the whole repository live in
[`../AGENTS.md`](../AGENTS.md); [`AGENTS.md`](AGENTS.md) in this directory adds
the Next.js version notes.

```
src/
  api/        config, client (openapi-fetch), server (RSC loaders), hooks, types
  auth/       mode, contract, session (server), AuthProvider (client)
  app/        (app)/… the shell and every page, login/, api/auth/, auth/callback
  components/ shell, gate, states, avatars, image upload, primitives
  features/   community/…, jobboard/…    one slice per backend bounded context
  lib/        format, forms, url state, intents, supabase/
```

`features/` groups the community screens together and keeps the job board
separate, which is how the backend used to be split. The backend has since been
broken up further, into `backend/members/`, `network/`, `paths/`, `events/`,
`announcements/`, `housing/`, `jobboard/`, `identity/` and `media/`, so a change
that starts in one of those lands in one of the folders below:

```
features/
  community/          members, entries, intents, network, events, announcements,
    ask/              housing, paths. The Ask hooks and the interpretation box
    announcements/    are shared by every screen that has a question bar.
    events/
    home/
    housing/
    me/
    members/
    paths/
  jobboard/           companies, jobs, and the row shapes the board renders
```

A slice owns its components, its client hooks and the flattening it needs
(`jobboard/jobData.ts` turns a `Job` plus its company and poster into the row
the list actually draws). Anything two slices both need is a primitive and
lives in `components/`; anything two slices both fetch is a loader in
`api/server.ts`. The two slices do not import each other, which is the same
rule the backend keeps between `community` and `jobboard`.

Server components are the default. `src/api/server.ts` holds the read side:
every loader is wrapped in `React.cache`, nothing lives at module scope, and
pages fetch independent things with one `Promise.all` rather than a chain of
awaits. Writes and anything interactive live in small client islands that use
React Query through `src/api/hooks/*`.

## Ingest

Unchanged from the standalone directory tool, except that its inputs now live
at the repo root: the roster CSVs in `../data/roster/` and the scraped LinkedIn
JSON in `../data/linkedin/<month>/`. See `../data/README.md`. Run
`npm run ingest`; it writes `public/data/index.json`, `public/profiles/*.json`
and `public/avatars/*.webp`. The `data/` tree is gitignored.

What ingest writes is read by the pages that serve `public/`, not by a hand
written mirror of the shape: the API's own schema in `src/api/schema.d.ts` is
the single description of what a member looks like.
