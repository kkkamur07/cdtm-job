# Supabase integration audit: performance and correctness

Repo: `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job`
Read-only audit. Versions verified from `node_modules` and `.venv`:
`@supabase/ssr 0.12.4`, `@supabase/supabase-js 2.112.3` (`@supabase/auth-js 2.112.3`),
`next 16.3.1`, `PyJWT 2.13.0`.

Changelog scan (`https://supabase.com/changelog.md`, fetched this session): no
`breaking-change` entry currently affects `@supabase/ssr`, `getClaims`, publishable keys,
asymmetric signing keys or Storage. The entries that touch this codebase are listed in
section 7.

---

## Per-request auth cost

### A. One page load, `NEXT_PUBLIC_AUTH_MODE=supabase`, visitor signed in

```
Browser ─── GET /members ───────────────────────────────► Next proxy runtime
                                                          (src/proxy.ts:9 → lib/supabase/proxy.ts:16)
   createServerClient(...)                                cheap, per request  (proxy.ts:23)
   await supabase.auth.getClaims()                        (proxy.ts:48)
     └─ getSession()   → read request cookies             0 network
        └─ refresh POST /auth/v1/token?grant_type=…       ONLY when exp-now < 90 s
                                                          (EXPIRY_MARGIN_MS = 3 × 30 s)
     ├─ (a) LEGACY HS256  header.alg startsWith "HS"
     │        → getUser(token) → GET /auth/v1/user        ★ 1 NETWORK ROUND TRIP  ~30-150 ms
     └─ (b) ASYMMETRIC ES256/RS256 (alg + kid + WebCrypto)
              → fetchJwk(kid)
                 ├─ GLOBAL_JWKS hit (< 10 min)            0 network
                 └─ miss → GET /auth/v1/.well-known/jwks.json  ★ 1 RT, then 10 min cache
              → crypto.subtle.verify                      local, ~0.2-0.5 ms
                                                                │
                                                                ▼
                                                          RSC render (separate bundle,
                                                          separate GLOBAL_JWKS)
   app/layout.tsx:48  getIdentity()                       (auth/session.ts:27, React.cache)
     └─ getServerAuth()                                   (lib/supabase/server.ts:63)
          createSupabaseServerClient()                    2nd client this request
          await supabase.auth.getClaims()                 (server.ts:69)
            └─ same branch as above  ── (a) ★ 2nd RT to /auth/v1/user
                                       ── (b) 0 network once warm
          await supabase.auth.getSession()                (server.ts:75) cookie decode #3
                                                          0 network, only to read access_token

   app/(app)/layout.tsx:16  Promise.all(loadMe, loadMyMember, loadAnnouncements)
     3 × fetch → FastAPI ─────────────────────────────────► see diagram B, ×3
   page loaders                                           ─► diagram B, ×n
                                                                │
                                                                ▼
Browser hydrate → AuthProvider effect (AuthProvider.tsx:94-116)
   dynamic import("@/lib/supabase/client")                1 extra JS chunk fetch
   supabase.auth.getSession()            (AuthProvider.tsx:108)   cookie read, 0 network
   apply(...)                                            state commit #1
   onAuthStateChange(...)                (AuthProvider.tsx:112)
     └─ _emitInitialSession → _useSession → INITIAL_SESSION
        apply(...)                                       state commit #2, same values
   autoRefreshToken tick every 30 s; POST /auth/v1/token only inside the 90 s margin
```

Totals for one document, signed in, warm caches:

| | Supabase Auth network calls before first byte |
|---|---|
| (a) legacy HS256 project secret | **2** (`GET /auth/v1/user` ×2) |
| (b) asymmetric signing keys | **0** (2 on a cold instance: one JWKS fetch per runtime, then 10 min) |

And **every `<Link>` prefetch repeats the whole thing**: the matcher does not exclude RSC
requests, so a viewport with 20 prefetched links costs 20 more proxy `getClaims` plus 20 more
`getServerAuth` `getClaims` (verified by running the matcher regex, section "Findings" row 4).

### B. One authenticated FastAPI call

```
caller ── Authorization: Bearer <jwt> ──► /api/v1/<anything>
  Depends(get_optional_principal)                      (identity/api/deps.py:88)
   └─ AuthService.authenticate(token)                  (auth_service.py:48)
        ├─ SupabaseJwtVerifier.verify()   SYNCHRONOUS, called from an async def
        │    ├─ HS256 → jwt.decode(secret)                    0 network, ~20 µs CPU
        │    └─ ES/RS → PyJWKClient.get_signing_key_from_jwt  (jwt_verifier.py:49)
        │         ├─ lru_cache(kid) hit  → 0 network          (no TTL: cached for process life)
        │         └─ miss → urllib.request.urlopen(JWKS)  ★ BLOCKS THE EVENT LOOP, timeout 30 s
        ├─ accounts.upsert_from_claims()               (account_repository.py:58)
        │    1. SELECT accounts WHERE auth_user_id = :sub          DB RT 1
        │    2. UPDATE accounts SET email, last_sign_in_at, …      DB RT 2   ← a WRITE on every GET
        │    3. COMMIT                                             DB RT 3
        │    4. session.refresh(row) → SELECT accounts             DB RT 4
        └─ if member_id is None:
             SELECT id FROM members WHERE lower(email)=…           DB RT 5 (while unbound)
  ──► handler runs, in a *new* transaction
```

**4 database round trips and one write transaction per authenticated request, before the
handler does anything.** The app shell alone (three loaders in `(app)/layout.tsx:16`) costs
12 DB round trips and 3 `UPDATE accounts` per page view.

### C. One uploaded image on the page

```
<img src="https://api…/api/v1/media/job-images/<uuid>.webp">
  Browser ── GET ──► FastAPI read_media                     (media/api/router.py:120)   RT 1
                       storage.signed_url(...)              (supabase_storage.py:59)
                         async with httpx.AsyncClient()     fresh TCP + TLS every call
                         POST /storage/v1/object/sign/…                                 RT 2
                     ◄── 307 Temporary Redirect,  NO Cache-Control  (router.py:132)
  Browser ── GET signed URL ──► Supabase Storage CDN                                    RT 3
                       token unique per request  ⇒  CDN MISS every time
```

**3 sequential round trips per image, every view, uncacheable at every hop.** Twelve job
cards = 36 round trips and 12 Storage sign-API calls per page view. The one-year
`IMMUTABLE_CACHE` constant (`router.py:45`) is only reachable on the local-disk branch
(`router.py:138`), so it never applies in production.

---

## Findings

| Severity | Location | Evidence | Doc reference | Impact | Recommended fix |
|---|---|---|---|---|---|
| **Critical** | `backend/media/api/router.py:129-132`; `backend/media/infrastructure/supabase_storage.py:59-75` | Every `GET /api/v1/media/{bucket}/{key}` mints a **brand new** signed URL (`POST /storage/v1/object/sign/...`) and returns a 307 with no `Cache-Control`. Signed URL TTL is 600 s (`router.py:41`) while keys are immutable content-addressed UUIDs (`images.py:42`). | [smart-cdn](https://supabase.com/docs/guides/storage/cdn/smart-cdn.md): "if you generate a new signed URL on every request, the cache will never be warm and every request hits the origin"; "prefer a public bucket. It results in higher cache hit rates". [cdn/fundamentals](https://supabase.com/docs/guides/storage/cdn/fundamentals.md): private buckets have lower cache efficiency because "permissions for accessing each object is checked on a per user level". | 3 RTs/image instead of 1 CDN hit; ~+100-250 ms per image, ~×12 per job board page; 0 % CDN hit rate; N sign-API calls per page view; egress billed at the non-cache-hit rate. | Move `job-images` and `housing-photos` to **public buckets** and store the public object URL, or keep them private and sign once with a long TTL persisted alongside the row. Either way stop signing per request. If the FastAPI hop must stay, cache the signed URL in-process keyed by `(bucket,key)` for TTL minus a margin, and put `Cache-Control: public, max-age=<ttl-60>` on the redirect. |
| **High** | `backend/identity/infrastructure/account_repository.py:58-88`, reached from `backend/identity/api/deps.py:88-95` on **every** `PrincipalDep`/`OptionalPrincipalDep` route | `upsert_from_claims` does SELECT → mutate → `commit()` → `refresh()` unconditionally, including writing `last_sign_in_at = now` and `updated_at = now` on a plain GET. `expire_on_commit=False` (`infrastructure/db.py:103`) so `refresh()` is a real extra SELECT. | n/a (application-side). Contradicts the repo's own rule in `AGENTS.md` ("Repositories never commit. The service owning the use case does."). | 4 DB round trips + 1 write txn per API call. Shell = 12 RTs + 3 UPDATEs/page. On the transaction pooler with `statement_cache_size=0` each statement is re-parsed. Also WAL, index churn and row bloat on `accounts` proportional to total requests, not to sign-ins. | Split read from write: `SELECT` the account by `auth_user_id`, and only write when something actually changed (email/name/avatar differ) or when `last_sign_in_at` is older than, say, 15 minutes. Drop `refresh()` (the row is already in the identity map with `expire_on_commit=False`). Add a per-process TTL cache of `sub -> Principal` (30-60 s) so repeated calls in one page load skip the DB entirely. Better still, join `accounts` + `members.slug` in one statement so `find_member_slug` does not need a second query. |
| **High** | `frontend/src/lib/supabase/proxy.ts:48` **and** `frontend/src/lib/supabase/server.ts:69` | The proxy verifies the token, then the RSC render verifies the same token again. They are separate bundles, so `GLOBAL_JWKS` (auth-js `GoTrueClient.js:50-64`) is **not** shared between them and each keeps its own 10-minute cache. `getClaims()` with no `jwt` argument calls `getSession()` first (`GoTrueClient.js:5321-5327`), then falls back to `getUser(token)` whenever `alg` starts with `HS` (`GoTrueClient.js:5339-5359`). | [signing-keys](https://supabase.com/docs/guides/auth/signing-keys.md): "If using asymmetric signing key, JWT validation is fast and does not involve Auth server"; with shared secrets, "Increased app latency as JWT validation is done by Auth server". [nextjs SSR](https://supabase.com/docs/guides/auth/server-side/nextjs.md): "It's safe to trust `getClaims()` because it validates the JWT signature against the project's published public keys every time." | **(a) HS256: 2 blocking calls to `/auth/v1/user` per document and per RSC prefetch, ~60-300 ms added to TTFB.** (b) asymmetric: ~0.6 ms CPU once warm, 2 JWKS fetches per cold serverless instance. | Move the project to **asymmetric signing keys**; that alone turns both verifications local and reduces the cost to sub-millisecond CPU, which makes the duplication harmless. See row 3 below for header propagation if you also want to remove the second verification. |
| **High** | `backend/identity/infrastructure/jwt_verifier.py:49` calling `PyJWKClient.get_signing_key_from_jwt` → `.venv/lib/python3.12/site-packages/jwt/jwks_client.py:117-120` (`urllib.request.urlopen`) | The JWKS fetch is **synchronous urllib** invoked from inside `async def get_optional_principal`. `timeout=30` by default and no timeout is passed at `jwt_verifier.py:30`. | [signing-keys](https://supabase.com/docs/guides/auth/signing-keys.md) describes the multi-level cache as keeping "the Auth server [out of] the hot path of your application". | Only on a cold process or an unknown `kid`, but when it happens the **entire uvicorn event loop stalls** for up to 30 s: every concurrent request on that worker hangs. | Pass `timeout=2.0` to `PyJWKClient`, and wrap the verify call in `anyio.to_thread.run_sync`, or pre-warm the JWKS in a FastAPI `lifespan` startup hook so the hot path never fetches. |
| **Medium** | `frontend/src/proxy.ts:13-22` | Matcher regex tested directly: `RUNS` on `/`, `/jobs`, `/api/auth/dev-session`, `/api/v1/x`, `/_next/data/x.json`, `/robots.txt`, `/manifest.webmanifest`; `skip` only on `_next/static`, `_next/image`, `assets`, `avatars`, `profiles` and literal image extensions. RSC prefetch requests reuse the page path (`/jobs?_rsc=…`) so they match. | [nextjs SSR](https://supabase.com/docs/guides/auth/server-side/nextjs.md): the middleware exists to refresh the session for *renders*, not for asset or metadata routes. | Under HS256, one extra `/auth/v1/user` per prefetch, per `robots.txt`, per Next route handler call. A page with 20 in-viewport links multiplies the auth cost by ~20. | Add `_next/data`, `api/`, `robots.txt`, `sitemap.xml`, `manifest*` and `.ico|.txt|.xml|.json|.woff2?` to the negative lookahead. Optionally skip prefetch requests: `if (request.headers.get("next-router-prefetch")) return NextResponse.next({ request })` before creating the client (a prefetch cannot deliver Set-Cookie to the browser anyway). |
| **Medium** | `backend/media/infrastructure/supabase_storage.py:36, 48, 61, 79` | Every one of `put`/`get`/`signed_url`/`delete` does `async with httpx.AsyncClient(...)`, so the client (and its connection pool) is created and destroyed per call. | n/a (httpx). Compounds the Storage-CDN issue above. | A full TCP + TLS handshake (~2 RTT, ~40-120 ms to a remote Supabase region) on every single media operation, on top of the request itself. | Hold one module-level `httpx.AsyncClient` with `limits=httpx.Limits(max_keepalive_connections=…)`, created in the app lifespan and closed on shutdown. `SupabaseStorage` is already a long-lived singleton via `get_blob_storage` (`media/infrastructure/__init__.py:18`), so it can own the client. |
| **Medium** | `backend/media/infrastructure/supabase_storage.py:35` | Upload headers are `apikey`, `Authorization`, `Content-Type`, `x-upsert`. No `cache-control` header is sent. | [smart-cdn](https://supabase.com/docs/guides/storage/cdn/smart-cdn.md): browser-side caching is managed "through the `cacheControl` option during upload" and "the default TTL is typically set to 1 hour". | Objects that are immutable by construction (UUID key, never rewritten) are re-validated by browsers every hour instead of being cached for a year. | Send `cache-control: max-age=31536000, immutable` on the upload POST (the Storage REST API reads the `cache-control` request header). |
| **Medium** | `backend/identity/infrastructure/jwt_verifier.py:30` | `PyJWKClient(..., cache_keys=True, lifespan=600)`. PyJWT's own docstring (`jwks_client.py:44-52`): the Tier-2 signing-key cache is an LRU "with **no time-based expiration**. Keys are evicted only when the cache reaches its maximum size." Since `get_signing_key` is the memoised entry point (`jwks_client.py:102-104`), a known `kid` never re-reads the Tier-1 cache, so `lifespan=600` is dead for the common path. | [jwts](https://supabase.com/docs/guides/auth/jwts.md): "Make sure that you do not cache this data for longer in your application, as it might make revocation difficult." [signing-keys](https://supabase.com/docs/guides/auth/signing-keys.md) recommends "a cache busting mechanism as part of your app's backend infrastructure". | Performance: excellent (one JWKS fetch per process). Correctness: a rotated or revoked signing key is honoured until the process restarts. `AUTH_JWKS_CACHE_SECONDS` silently does nothing. | Set `cache_keys=False` and rely on the Tier-1 `lifespan=600` JWK-set cache, which is the TTL the setting is documented to mean. Cost is one dict lookup per request, not a network call. |
| **Medium** | `frontend/src/app/layout.tsx:48` → `frontend/src/auth/session.ts:27-30` (`cookies()`) | The root layout awaits `getIdentity()`, which reads cookies on every route. | Next.js App Router: reading `cookies()` opts the whole subtree into dynamic rendering. | No route in the app can be statically rendered or served from the full-route cache, including the public `/jobs` and `/companies` pages that already opt into `revalidate` at the data layer (`api/server.ts:128-151`). Every visit pays the proxy + render auth cost. | Move `getIdentity()` out of the root layout into `(app)/layout.tsx` (which is already dynamic), and hand `initialSignedIn`/`initialEmail` to `Providers` from there. Public marketing/job pages could then be statically rendered. |
| **Low** | `frontend/src/lib/supabase/server.ts:69-75` | `getClaims()` internally calls `getSession()` (`GoTrueClient.js:5322`), then `getServerAuth` calls `getSession()` again purely to read `access_token`. That is three cookie parse + JSON decode passes per render. | [nextjs SSR](https://supabase.com/docs/guides/auth/server-side/nextjs.md): `getSession()` is fine here because it is not being trusted, only read. | No network; a few hundred microseconds and some GC pressure per render. | `const { data: { session } } = await supabase.auth.getSession(); const { data } = await supabase.auth.getClaims(session.access_token);`: one storage read instead of three, and the token is already in hand. |
| **Low** | `frontend/src/auth/AuthProvider.tsx:108-114` | `getSession()` then `onAuthStateChange(...)`; auth-js emits `INITIAL_SESSION` to every new subscriber (`GoTrueClient.js:3640-3652`) via a second `_useSession()`. Both call `apply(...)`. | n/a (library behaviour). | Two identical state commits and two `setAccessToken` calls on mount, one extra React render. No network: `__loadSession` only refreshes when `expires_at*1000 - now < 90 000 ms` (`GoTrueClient.js:2523-2551`). | Drop the explicit `getSession()` and let `INITIAL_SESSION` be the restore path; it delivers exactly the same session. |
| **Low** | `frontend/src/auth/AuthProvider.tsx:95-98` | The Supabase client is `import()`ed lazily inside the mount effect. | n/a. | A signed-in first paint does **not** wait on a network call for auth (`initialSignedIn`/`initialEmail` come from the server, `layout.tsx:59`), which is right. But `token` stays `null` until the dynamically imported chunk lands, so any React Query hook gated on `token` waits one extra chunk round trip after hydration. | Acceptable as-is; if the delay matters, add a `modulepreload` for the Supabase chunk, or `import()` it at module scope in supabase mode. |
| **Low** | `backend/identity/infrastructure/jwt_verifier.py:45, 50` | `jwt.decode(..., algorithms=[alg], audience=self._audience)`: no `issuer=` and no `options={"require": [...]}`. `alg` is taken from the attacker-supplied header. | [jwts](https://supabase.com/docs/guides/auth/jwts.md): "avoid implementing the algorithms yourself and instead rely on `supabase.auth.getClaims()`, or other high-quality JWT verification libraries". | No measurable latency cost. Correctness: any token that verifies against our secret or our JWKS is accepted regardless of `iss`. Low risk because both keys are project-scoped. | Pass `issuer=f"{supabase_url}/auth/v1"` and `options={"require": ["exp", "sub", "aud", "iss"]}`. |
| **Low** | `backend/identity/infrastructure/jwt_verifier.py:42-50`, `backend/core/settings/auth.py:24` | `alg` in the header selects HS vs JWKS. As long as `SUPABASE_JWT_SECRET` is set, an HS256 token forged with the legacy secret is accepted even after the project migrates to asymmetric keys. Intentional per ADR 0001, but the migration hazard is not recorded. | [jwts](https://supabase.com/docs/guides/auth/jwts.md): "There is almost no benefit from using a JWT signed with a shared secret" and recommends switching "to a different signing key based on public key cryptography". | None on latency. Keeps a second forging key alive indefinitely. | When the project moves to asymmetric keys, unset `SUPABASE_JWT_SECRET` in production (env is `env_ignore_empty=True`, so `SUPABASE_JWT_SECRET=` reads as unset) and keep it only where `AUTH_DEV_LOGIN_ENABLED=true`. |
| **Low** | `backend/core/settings/storage.py:37, 49-53` | `avatars_bucket` and `StorageSettings.public_url()` are referenced nowhere outside their own file (grepped across `backend/`, `scripts/`, `infrastructure/`). `frontend/README.md` states avatars "are produced by `scripts/ingest.mjs` and served as static files from `public/avatars/`"; `frontend/scripts/ingest.mjs:344` writes `/avatars/<id>.webp`. | [cdn/fundamentals](https://supabase.com/docs/guides/storage/cdn/fundamentals.md): public buckets "benefit a high CDN cache HIT ratio". | The 1,250 member avatars are served by Next from `public/`, which is fine and fast (immutable hashed static assets), but `docs/architecture.md:22` still claims `Web -->|"avatars"| Storage`. Dead config invites someone to wire it up. | Either delete `avatars_bucket`/`public_url`/`STORAGE_AVATARS_BUCKET` and correct the architecture diagram, or, if avatars do move to Storage, use a **public** bucket (the `remotePatterns` entry for `/storage/v1/object/public/**` at `frontend/next.config.ts:34-41` is already there and currently unused). |
| **Low** | `infrastructure/alembic/versions/001_initial_schema.py:1047-1069` | `_lock_down_data_api()` enables RLS on the 21 tables in `DROP_ORDER` and revokes grants, but the list is hard-coded and `ALTER DEFAULT PRIVILEGES` only binds objects created by the migrating role. Nothing in `tests/` enforces it for future tables. | Skill security checklist §5 and [securing-your-api](https://supabase.com/docs/guides/api/securing-your-api.md). | None on latency. A table added in a later migration lands in `public` with RLS off. | Add an integration assertion that every table in `Base.metadata` has `relrowsecurity = true`, next to the existing `test_migrations.py` metadata comparison. |
| **Nit** | `backend/media/api/router.py:41` | `SIGNED_URL_SECONDS = 600`, while keys are immutable UUIDs and blobs are never rewritten. | [smart-cdn](https://supabase.com/docs/guides/storage/cdn/smart-cdn.md): "token expiry and the object's response cache TTL are independent". | Guarantees churn even if the per-request signing is fixed. | If private buckets stay, sign for hours-to-days and cache the URL; deletion, not expiry, is the revocation mechanism the docs recommend anyway. |
| **Nit** | `frontend/src/components/ImageUpload.tsx:113` | `unoptimized` on the upload preview, while the render paths (`app/(app)/jobs/[slug]/page.tsx:75`, `features/community/housing/HousingCard.tsx:56`, `app/(app)/housing/[id]/page.tsx:87,257`) use the optimizer. | n/a. | The optimizer's cache absorbs most of the 3-hop media chain for rendered pages; the preview pays it in full on every render. Also means the optimizer's own TTL is driven by an upstream response that carries no `Cache-Control`. | Once the media responses carry real cache headers, this resolves itself; `unoptimized` on a 96×72 preview is otherwise fine. |

---

## Answers to the specific questions

**1. Auth network calls per page request.** Two `getClaims()` calls per document
(`lib/supabase/proxy.ts:48`, `lib/supabase/server.ts:69`), plus one `getSession()` in
`getServerAuth` (`server.ts:75`) and one plus one implicit on the client
(`AuthProvider.tsx:108` and the `INITIAL_SESSION` emit). `getSession()` never touches the
network unless the token is inside the 90 s expiry margin (`GoTrueClient.js:2523-2551`).
Under **(a) legacy HS256** both `getClaims()` calls fall through to `getUser()` and hit
`GET /auth/v1/user`: **2 blocking network calls per page**, per RSC prefetch, per matched
route handler. Under **(b) asymmetric keys** both verify locally with WebCrypto against a
JWKS cached 10 minutes in a module-global keyed by storage key (`GoTrueClient.js:50-64`,
`JWKS_TTL = 10 * 60 * 1000`): **0 network calls once warm**, one JWKS fetch per runtime per
cold instance. The matcher is **not** excluding enough: it runs on `/api/**`, `_next/data`,
`robots.txt`, `manifest`, and every RSC prefetch (regex tested directly).

**2. Does the server layer re-verify what the proxy verified?** Yes, in full, in a separate
bundle with a separate JWKS cache. There is a supported way to verify once:
`NextResponse.next({ request: { headers } })` in the proxy makes a header visible to the
render via `headers()`. If you take that route you **must** delete any inbound copy of that
header first, or you have handed the world a spoofable identity: which is exactly the
failure mode the Supabase docs warn about ("The server gets the user session from the
cookies, which can be spoofed by anyone", [nextjs SSR](https://supabase.com/docs/guides/auth/server-side/nextjs.md)).
Given that risk, the better first move is **asymmetric signing keys**: the second
verification then costs ~0.3 ms of CPU and no network, and the double work stops mattering.

**3. Client side.** Mount does one `getSession()` (`AuthProvider.tsx:108`) plus one implicit
`_useSession()` from the `INITIAL_SESSION` emit (`GoTrueClient.js:3640-3652`), so
`apply(...)` runs twice with identical values. Neither is a network call. The refresh timer
is auth-js's 30 s tick (`AUTO_REFRESH_TICK_DURATION_MS`), which only issues a refresh POST
inside the 90 s margin; `createServerClient` correctly gets `autoRefreshToken: false`
(`@supabase/ssr/dist/main/createServerClient.js:34`), so no server-side timer leaks. A
signed-in **first paint does not wait on a network call**: `initialEmail`/`initialSignedIn`
come from the server render (`app/layout.tsx:48-59`). The `token` does wait on a dynamically
imported chunk, so token-gated queries start one chunk round trip after hydration.

**4. Backend per-call cost.** Verification itself is cheap and correct in shape: one
`PyJWKClient` per process (`deps.py:33 @lru_cache(maxsize=1)`), `alg` pinned from the header
with the HS/asymmetric branch separated, `aud` checked. What is expensive is everything after
it: **every** request that carries a bearer token runs `upsert_from_claims`, which is
SELECT + UPDATE + COMMIT + refresh-SELECT (4 round trips, one of them a write), plus a fifth
SELECT on `members` while the account is unbound. It absolutely can be cached and joined: see
the High row above. The JWKS fetch is also blocking urllib on the event loop, and
`cache_keys=True` makes `AUTH_JWKS_CACHE_SECONDS` a no-op.

**5. Storage.** Reads of job and housing images go `browser → FastAPI → Storage sign API →
307 → Storage CDN`, three sequential round trips, with a fresh signed token each time so the
CDN can never warm, no `Cache-Control` on the redirect, and a new TLS connection per sign
call. The correct shape for images that are already unguessable UUID keys is a **public
bucket** and the public object URL stored directly in `jobs.image_url` /
`housing_listings.photo_urls`: one CDN-cached request, zero FastAPI involvement, zero sign
calls, and the cheaper cache-hit egress rate. `cacheControl` is not set on upload, so
Supabase's ~1 hour default applies. No image transformations are used anywhere; a public
bucket would also let `next/image` or Storage transformations size the images. Avatars are
**not** in Storage at all: they are static `public/avatars/*.webp` files from `ingest.mjs`,
which is the fastest option available and should stay.

**6. Security items that intersect with performance.** RLS is deliberately unused (ADR 0003)
because the API connects as the table owner, and the initial migration nonetheless enables
RLS on all 21 tables and revokes `anon`/`authenticated` grants
(`001_initial_schema.py:1047-1069`): that is the right belt-and-braces answer to the skill's
checklist items 4 and 5, and it costs nothing at runtime because the owner bypasses RLS. The
publishable key is `NEXT_PUBLIC_` only and both the new and legacy names are accepted
(`lib/supabase/env.ts:20-23`). The service-role key appears only in
`backend/core/settings/storage.py:36` and is never in any `NEXT_PUBLIC_` variable: verified
across both `.env.example` files. `user_metadata` is explicitly excluded from every
authorization decision (`jwt_verifier.py:58-94`), matching the checklist's first item. The two
things that are wrong: no `issuer` check, and the legacy HS256 secret remaining a valid
forging key after a migration to asymmetric keys.

**7. Changelog items that change the recommendations.**
- [Asymmetric Keys support](https://supabase.com/changelog/29289-supabase-auth-asymmetric-keys-support-in-2025): the entry that introduced `getClaims()`. Projects created after 2025-05-01 default to asymmetric keys; this is the single change that removes both per-page `/auth/v1/user` calls. Confirm which mode the project is actually on before assuming the fast path.
- [Tables not exposed to Data and GraphQL API automatically](https://supabase.com/changelog/45329-breaking-change-tables-not-exposed-to-data-and-graphql-api-automatically) (2026-04-28): from **2026-10-30 it applies to all existing projects**, but only for *new* tables: "Existing tables are not affected in your project, they keep their current grants and stay reachable." So the explicit REVOKE in the migration is still doing real work today and should not be removed.
- [3x cheaper egress for cache hits](https://supabase.com/changelog/38119-3x-cheaper-egress-for-cache-hits) (2025-08-22): makes the per-request signed URL a billing problem as well as a latency one: the current design guarantees a 0 % hit rate.
- [@supabase/ssr roadmap to v1.0.0](https://supabase.com/changelog/27037-supabase-ssr-updates-and-roadmap-towards-v1-0-0): the `getAll`/`setAll` cookie model, which this codebase already uses. In 0.12.4 `setAll` receives a second `headers` argument carrying `Cache-Control: private, no-cache, no-store, must-revalidate, max-age=0` (`@supabase/ssr/dist/main/cookies.js:499-502`); `proxy.ts:38-40` applies it and `server.ts:29-39` deliberately drops it. Cookie chunking is present (`MAX_CHUNK_SIZE = 3180`) and works correctly with the `getAll`/`setAll` pair used here.
- No `breaking-change` entry currently affects `getClaims` defaults, publishable-key rollout, or Storage behaviour. Publishable/secret keys are the forward path and [legacy JWT keys "will be deprecated by the end of 2026"](https://supabase.com/docs/guides/api/api-keys.md); `env.ts:20-23` already prefers the new name.

---

## What is already done well

- **`getClaims()` is what authorization is decided on**, and `getSession()` is used only to lift the raw token for forwarding, with the reason written down (`lib/supabase/server.ts:52-62`). That is exactly what [the Next.js SSR guide](https://supabase.com/docs/guides/auth/server-side/nextjs.md) asks for: "Never trust `supabase.auth.getSession()` inside server code such as Proxy."
- **Nothing runs between `createServerClient` and `getClaims()` in the proxy**, with the hazard spelled out at `lib/supabase/proxy.ts:45-48`. This is the single most commonly broken rule in `@supabase/ssr` integrations.
- **Cookie handling is the current `getAll`/`setAll` model** in both clients, so chunked cookies work, and the proxy propagates the library's cache headers onto the response (`proxy.ts:36-40`) so no CDN can store someone else's `Set-Cookie`.
- **No client is held at module scope on the server**, and the reason (cross-visitor session leak on a warm serverless instance) is stated at `server.ts:9-15` and `proxy.ts:21-22`. The browser client *is* a singleton with the correct reason (racing refresh timers) at `client.ts:16-18`.
- **`React.cache` on `getServerAuth` and `getIdentity`** (`server.ts:63`, `auth/session.ts:27`) means one verification per render no matter how many loaders ask, and every loader in `api/server.ts` is cached the same way, including the two that key on a joined string precisely because `React.cache` compares by identity (`api/server.ts:171-196, 209-232`).
- **The token is published to the API client synchronously in the same callback as the state**, with the child-effects-before-parent-effects reasoning written out (`AuthProvider.tsx:58-73`, `api/client.ts:13-29`). That is a real bug class avoided, not a stylistic choice.
- **Layout loaders go out in one `Promise.all`** rather than a waterfall (`app/(app)/layout.tsx:16-22`), and `api/server.ts` says so as a rule.
- **Batch endpoints instead of N+1**: `/members/lookup` and `/members/at-company` collapse per-row member resolution into one call of up to 50 (`api/server.ts:171-232`).
- **Backend JWT verification is set up correctly for the mode it is in**: one `PyJWKClient` for the process, `alg` branched explicitly rather than trusted blindly, audience checked, and `user_metadata` excluded from every identity decision with a long and correct explanation (`jwt_verifier.py:58-94`).
- **Service-role key is server-only and, per ADR 0003, only Storage needs it.** No `NEXT_PUBLIC_` variable anywhere carries a secret; both `.env.example` files say so in the first three lines.
- **The initial migration enables RLS and revokes `anon`/`authenticated` grants on `public`** even though the API bypasses RLS as owner (`001_initial_schema.py:1047-1069`): defence in depth against PostgREST, exactly as the Supabase security checklist asks.
- **Uploads sniff magic bytes rather than trusting the multipart `Content-Type`, reject SVG, and cap the read at limit+1 bytes** (`media/api/router.py:90-103`, `media/infrastructure/images.py:26-39`), and keys are validated against a strict UUID+extension regex before reaching any storage adapter (`images.py:23`).
- **First paint does not flash the signed-out state**: the server-verified summary is handed to the provider (`app/layout.tsx:48-59`, `providers.tsx:39`).
- **The dev-session route documents its own weakness honestly** (`app/api/auth/dev-session/route.ts:14-34`) instead of implying the httpOnly flag buys more than it does, and production is hard-forced to Supabase mode (`auth/mode.ts:22`).
