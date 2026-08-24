# Backend performance fixes: identity, media, core/infrastructure

Repo: `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job`, branch `master`, nothing
committed. Every finding was confirmed at the cited location before it was changed; the two
that no longer held are called out below (items 7 and, partly, the ORJSON half of the audit).

---

## 1. Principal prelude write-per-request: done

Confirmed at `backend/identity/infrastructure/account_repository.py:58-88`: SELECT, then an
unconditional field assignment, `last_sign_in_at = now`, `updated_at = now`, `commit()`,
`refresh()`, on every authenticated request.

Now: SELECT, then write only when a claim-derived field actually differs (`email`,
`full_name`, `avatar_url`, the admin bootstrap) or when `last_sign_in_at` is older than
`AUTH_SIGN_IN_TOUCH_SECONDS` (new setting, default 900) or is null. `refresh()` is gone from
the update path (`expire_on_commit=False` on the session factory means the instance is still
populated after a commit); it is kept on the *insert* path only, because `id`, `created_at`
and `updated_at` are server defaults and reading an unloaded attribute from an async session
raises rather than lazily loading. The comparison is done field by field in `_apply_claims`
because assigning an identical value still marks the instance dirty and still produces an
UPDATE on flush.

ConflictError on a duplicate e-mail is preserved: it can only arise from a commit, and a
commit still happens on every path that changes the address. `auth_service.authenticate`'s
suppression around `bind_member` is untouched.

The steady state for an authenticated request is now **one SELECT and no transaction commit**
(previously SELECT + UPDATE + COMMIT + SELECT).

Files: `backend/identity/infrastructure/account_repository.py`,
`backend/core/settings/auth.py` (`sign_in_touch_seconds`),
`backend/identity/api/deps.py` (wires it in).

Tests added: `tests/unit/test_identity_sign_in_prelude.py` (10 tests, fake session counting
commits: no write when unchanged and recent; write when stale; write when null; write per
changed claim; admin bootstrap writes once and not again; a token with no display fields
does not erase them or count as a change; first sign-in still inserts and still refreshes).
`tests/integration/test_identity_gaps.py` gained
`test_a_request_with_nothing_new_to_say_leaves_the_account_row_alone` and
`test_a_sign_in_after_the_touch_window_records_the_new_time`.

Existing test adjusted: `tests/integration/test_identity_gaps.py::test_a_sign_in_records_the_name_avatar_and_time_from_the_token`
still passes unchanged (its second sign-in changes the name *and* the avatar, so it takes the
write path), but a comment was added explaining what now makes it write, and pointing at the
unchanged-case test below it.

Skill rule: fastapi-best-practices "keep layers explicit: router -> service -> repository". The threshold is a setting resolved in `api/deps.py` and passed to the repository, so the
repository still imports no settings and no FastAPI.

## 2. `sub -> Principal` TTL cache: skipped

The precondition in the brief ("only if the Principal is immutable within that window") does
not hold. Three writes mutate a live Principal:

- `AuthService.claim_member` (`auth_service.py:86`): the caller binds *their own* account to
  a Member. With a 30 s cache the very next request would still report `member_id: None`, so
  the "claim your member" flow would appear to have failed to the person who just did it.
- `bind_account_to_member` and `set_admin` (`auth_service.py:118,129`): an admin promotion or
  binding would take up to 30 s to be visible.

Invalidation is possible but needs the cache reachable from the application service, which
means either a new port or `application/` importing an infrastructure module. Against that,
item 1 already removed 3 of the 4 round trips; the cache would save the remaining SELECT.
Not worth the correctness hazard for one round trip, so it is not implemented.

Skill rule: supabase security checklist, "JWT claims are not always fresh until the user's
token is refreshed". The same staleness argument applies to caching a derived authorization
object, and here the platform can avoid the staleness entirely.

## 3. JWKS handling: done

Confirmed at `backend/identity/infrastructure/jwt_verifier.py:29-33`:
`PyJWKClient(jwks_url, cache_keys=True, lifespan=jwks_cache_seconds)`. PyJWT 2.13's
`cache_keys=True` wraps the per-`kid` lookup in an `lru_cache` with no expiry, so
`AUTH_JWKS_CACHE_SECONDS` decided nothing and a rotated Supabase signing key would never have
been picked up.

Changes:
- `cache_keys=False` (PyJWT's own default). The JWK-set cache, which does honour `lifespan`,
  becomes the only cache, so `AUTH_JWKS_CACHE_SECONDS` is now live.
- `timeout=5.0` (`JWKS_TIMEOUT_SECONDS`), down from PyJWT's default 30.
- `verify_async()` added: HS256 stays inline (about 20 microseconds of CPU, a thread hop
  costs more), the JWKS path goes through `anyio.to_thread.run_sync` so a cold or slow fetch
  cannot stall the event loop. `AuthService.authenticate` awaits it; the `TokenVerifier` port
  grew the method with a docstring saying why both exist. Sync `verify()` is unchanged as the
  whole implementation, which is what the unit tests exercise.
- `warm_jwks()` added and called from the app lifespan when a JWKS URL is configured, best
  effort: any exception is logged (`jwks_prewarm_failed`) and startup continues.
- `issuer` verification on the asymmetric path only, from
  `AuthSettings.jwt_issuer` = `{SUPABASE_URL}/auth/v1`. The HS256 path is deliberately
  exempt: `backend/identity/api/dev_router.py` -> `dev_token_issuer.py:22` mints
  `iss: "cdtm-dev-login"`, and the integration conftest mints tokens with no `iss` at all.
  On the asymmetric path the signing key is public, so the issuer is what ties a token to
  *this* project; on the HS256 path the shared secret already does that.

Files: `backend/identity/infrastructure/jwt_verifier.py`,
`backend/identity/application/ports.py`, `backend/identity/application/auth_service.py`,
`backend/identity/api/deps.py` (`get_token_verifier` now annotated as the concrete adapter,
because the lifespan pre-warms through it; `application/` still sees only the port),
`backend/core/settings/auth.py`, `backend/core/app.py`.

Tests: `tests/unit/test_jwt_verifier_gaps.py` gained 8 tests (issuer from another project
refused; issuer from this project accepted; missing `iss` refused once configured; no
configured issuer means no check; the dev-login issuer still passes on HS256; `verify_async`
runs HS256 on the loop and the JWKS path on a worker thread; warming means the first token
does not fetch; warming a verifier with no JWKS is a no-op).

Existing test deliberately changed, same file:
`test_the_signing_key_is_cached_so_a_stream_of_tokens_does_not_refetch_the_jwks` asserted
that an *expired* key set still served from the per-`kid` cache. That was the dead-TTL bug
stated as a requirement. It is now two tests: the key set is cached across a stream of tokens
(1 fetch), and the configured lifetime is what decides a refetch (2 fetches after expiry),
with a comment saying what changed and why.

Also adjusted: the fake verifier in `tests/unit/test_auth_service.py` gained `verify_async`
(3 lines). That file is outside the file list I was given, but the port changed, so it had to
follow; nothing else in it was touched.

Skill rule: supabase security checklist, "never use `user_metadata` claims in authorization
decisions". Re-read before touching `_claims_from_payload`; that logic is unchanged.

## 4. Storage HTTP client: done

Confirmed at `backend/media/infrastructure/supabase_storage.py:36,48,61,79`: an
`async with httpx.AsyncClient(...)` per call, so a fresh TCP connection and TLS handshake for
every image on every page view.

Now one `httpx.AsyncClient` per `SupabaseStorage` instance, built lazily on first use (so
constructing the adapter at boot, and in tests, opens no sockets), released by `aclose()`.
`get_blob_storage` in `backend/media/infrastructure/__init__.py` is a `settings_cache`
singleton, so that is one pool per process. The app lifespan calls `aclose()` on shutdown.
`aclose()` was added to the `BlobStorage` port and to `LocalDiskStorage` as a documented
no-op, so the lifespan does not have to ask which adapter it got.

Uploads now send `cache-control: max-age=31536000, immutable` (keys are fresh UUIDs and a
blob is never rewritten in place), which is what lets Storage's CDN keep the bytes.

Files: `backend/media/infrastructure/supabase_storage.py`,
`backend/media/infrastructure/ports.py`, `backend/media/infrastructure/local_disk.py`,
`backend/core/app.py`.

Tests: `tests/unit/test_media_gaps.py` gained
`test_one_client_serves_every_call_instead_of_one_per_call` (lazy, reused, closed, idempotent
close) and `test_an_upload_tells_storage_the_object_will_never_change`. The file's existing
`supabase` fixture monkeypatches `httpx.AsyncClient` before the adapter is built and the
client is created lazily, so all 27 pre-existing tests still exercise the mock transport
unchanged.

## 5. Media reads: done

Confirmed at `backend/media/api/router.py:120-132`: a fresh `signed_url` per request and a
307 with no `Cache-Control`.

Now:
- `SIGNED_URL_SECONDS` raised 600 -> 3600, with the reasoning in the constant's comment:
  deletion, not expiry, is the revocation mechanism here (the key is a random UUID handed
  only to people who can already read the row it sits on, and removing the blob invalidates
  every signature over it at once).
- Signed URLs cached in process in a `cachetools.TTLCache(maxsize=1024, ttl=3600-60)` keyed on
  `(bucket, key)`, storing `(url, monotonic deadline)`.
- The redirect carries `Cache-Control: private, max-age=<remaining>`, computed from the
  stored deadline so a browser served late in a signature's life is told the shorter number.
  `private` because the target carries a signature and a shared cache must not hand one
  visitor's signed URL to the next.
- `DELETE /media/{bucket}/{key}` drops the cached signature, so a redirect cannot outlive the
  object it points at.
- The local-disk branch keeps `IMMUTABLE_CACHE` exactly as it was.

`uv add cachetools` (project-scoped, `cachetools>=7.1.7` in `pyproject.toml` dependencies).

Files: `backend/media/api/router.py`, `pyproject.toml`, `uv.lock`.

Tests added: `tests/unit/test_media_signed_urls.py` (9 tests: signed once and reused; each
object gets its own signature; the redirect advertises a lifetime; the advertised lifetime
shrinks as the signature ages; a signature near expiry is replaced; the configured lifetime
is what is asked for; an adapter that cannot sign still streams with the immutable header;
deleting forgets the signature; an unknown bucket is refused before anything is signed).

## 6. Compression: done

`GZipMiddleware(minimum_size=1000)` added in `create_app`, after the request guards and
before CORS, so the order a request meets them is CORS -> gzip -> guards: the security
headers are set on the response before anything compresses it. Starlette, no new dependency.

Files: `backend/core/app.py`.

Tests added: `tests/integration/test_compression.py` (4 tests, real `TestClient` against the
real app): a 40-member list with `Accept-Encoding: gzip` comes back
`content-encoding: gzip` and shorter than the decoded document; `Accept-Encoding: identity`
gets no `content-encoding`; `/health` is under the minimum size and is left alone; a
compressed response still carries the security headers.

## 7. ORJSON: skipped, the finding no longer holds

The audit row (`backend.md:75`) is correct that `orjson` was absent, but its premise is not
true on the installed FastAPI. FastAPI **0.141.1** deprecates `ORJSONResponse`:

> ORJSONResponse is deprecated, FastAPI now serializes data directly to JSON bytes via
> Pydantic when a return type or response model is set, which is faster and doesn't need a
> custom response class.

(`.venv/lib/python3.12/site-packages/fastapi/responses.py:69-70`.) Every route in this app
declares a `response_model` or a return type, so every route already takes that path.

I implemented it, ran the suite, and FastAPI emitted the deprecation from `routing.py:144`
*during a live request*: setting `default_response_class=ORJSONResponse` had taken the
routes **off** the fast path and put them back on `jsonable_encoder` + a custom response
class. So this change is a regression on this version, not an improvement. It was reverted:
`orjson` is not in `pyproject.toml`, and `create_app` now carries a comment saying why there
is deliberately no `default_response_class`.

The error-envelope handlers were left on `JSONResponse` (they hand-build a dict of strings
plus a `jsonable_encoder`-ed details block; nothing there needs UUID or datetime handling,
and errors are not a hot path).

## 8. Pooler detection: done

Confirmed at `infrastructure/db.py:71`: `":6543/" in url or "pooler.supabase.com" in url`.
The host half is wrong for the configuration Supabase actually publishes: port 5432 on
`pooler.supabase.com` is Supavisor in **session** mode, where the connection is held for the
whole session and prepared statements are safe. The old rule gave up asyncpg's statement
cache (query-plan reuse on every statement the API issues) for a hazard that was not there.

Now `_is_transaction_pooled(url, override=...)`: the port is parsed with
`sqlalchemy.make_url` (so a password containing `:6543` or `@` cannot fool it) and only 6543
counts, plus an explicit `DATABASE_POOLER_TRANSACTION_MODE` (bool, default False) for a
deployment whose port does not give it away. A URL with no port is the default 5432, i.e. a
direct connection. An unparseable URL is not guessed at. The reasoning is in the function's
docstring and in the module docstring.

Migrator URL: `log_resolved_urls()` logs, once at boot from `create_app`, which database each
of the two engines will reach and whether the migrator URL came from `DATABASE_MIGRATOR_URL`
or fell back to `DATABASE_URL`. Passwords are stripped (`safe_url`). Behaviour is unchanged;
`infrastructure/alembic/env.py` was not touched (another agent owns it), so the log lives in
the app factory rather than in the Alembic entry point.

Skill rules: `conn-prepared-statements` ("Option 3: Use session mode pooling (port 5432 vs
6543): connection is held for entire session, prepared statements persist") and
`conn-pooling` ("Session mode: connection held for entire session (needed for prepared
statements)"). Both say the mode, not the host, is the deciding fact.

## 9. `SET LOCAL statement_timeout` under transaction pooling: done

`statement_timeout` is still sent as an asyncpg startup parameter (`server_settings`), which
is right for session mode and a direct connection. Under transaction pooling the physical
connection is shared and may predate this process, so the startup parameter may never have
been forwarded. A SQLAlchemy `after_begin` listener now issues
`SET LOCAL statement_timeout = <ms>` at the start of **every** transaction on an app session,
not just the first one in a request. Repositories commit mid-request, and a `SET LOCAL`
issued once in `get_db` would only have covered the transaction up to that commit.

`SET LOCAL` rather than `SET SESSION` deliberately: under transaction pooling the connection
belongs to somebody else once the transaction ends.

The listener is attached to `_AppSession`, a `Session` subclass used only by this app's
`AsyncSession` (`_AppAsyncSession.sync_session_class`), so Alembic's and the scripts' plain
`Session` objects never see it. It is installed only when transaction mode is on (it is an
extra statement per transaction), and `_sync_statement_timeout_listener` is idempotent in
both directions so a settings re-read cannot queue it twice or leave it behind.

Files: `infrastructure/db.py`, `backend/core/settings/database.py`, `backend/core/app.py`.

Tests added: `tests/unit/test_db_pooling.py` (13 tests: the port table including the
session-mode pooler case the old rule got wrong and a password containing `:6543@`; the
override; an unparseable URL; the statement cache is only given up on 6543, asserted by
standing in for `create_async_engine` rather than building the real cached engine; the
listener is installed only for transaction pooling and is idempotent; the statement issued is
`SET LOCAL`, not `SET SESSION`; the listener class is not `Session` itself; passwords never
reach a log line).

Note: I could not exercise the listener against a real 6543 pooler: the only such endpoint
is the production Supabase project, which is off limits. What is proven is the statement it
issues and when it is installed, not that Supavisor honours it.

## 10. Pure-ASGI middleware: done

Both `@app.middleware("http")` functions (`backend/core/app.py:240-278`) are now one
`RequestGuards` ASGI class: `_body_too_large` reads `Content-Length` off the scope and
returns the 413 response to send, and `_security_header_sender` wraps `send` to add the
headers to the `http.response.start` message. Neither needed `BaseHTTPMiddleware`'s anyio
task group and memory object stream, and the 413 now goes out through the same send wrapper
instead of updating the headers by hand. Net: one wrapper per request instead of two, and no
task group.

Behaviour is identical and the existing coverage in
`tests/unit/test_app_factory_core_gaps.py` (413 on an oversized JSON body, 413 on an
oversized upload, the media prefix's larger limit, the security headers on a normal response
and on an error response, CORS) passes unchanged.

---

## OpenAPI

My changes do not alter the OpenAPI document. Compared the generated schema against the
committed `frontend/openapi/openapi.json`: the only differences are
`/api/v1/announcements/unread-count`, `/api/v1/paths/members`, `/api/v1/paths/flow`,
`/api/v1/members/at-company`, `/api/v1/members/facets` and the `UnreadCountPublic` schema, all
from the other agent's contexts. `/api/v1/media/*` and `/api/v1/auth/*` are byte-identical
to the committed file. `uv run poe openapi` was not run.

## Verification (verbatim tails, all from the repo root)

```
$ uv run poe lint
Poe => ruff check backend infrastructure scripts tests
All checks passed!
```

```
$ uv run poe format
Poe => ruff format backend infrastructure scripts tests
308 files left unchanged
```

```
$ uv run poe test-fast
.............................................s.......................... [ 13%]
........................................................................ [ 26%]
........................................................................ [ 40%]
........................................................................ [ 53%]
........................................................................ [ 67%]
........................................................................ [ 80%]
........................................................................ [ 94%]
................................                                         [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /Users/krishuagarwal/Desktop/Programming/python/cdtm-job/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
535 passed, 1 skipped, 238 deselected, 1 warning in 26.72s
```

```
$ DATABASE_URL=postgresql://localhost:5432/cdtm_community_test_identity uv run pytest tests/integration -m integration -q
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_auth.py::test_unverified_top_level_email_is_rejected
ERROR tests/integration/test_migrations.py::test_migration_chain_matches_orm_metadata
ERROR tests/integration/test_migrations.py::test_downgrade_to_base_is_clean
1 failed, 235 passed, 1 warning, 2 errors in 312.26s (0:05:12)
```

Everything in my scope passes:

```
$ DATABASE_URL=postgresql://localhost:5432/cdtm_community_test_identity uv run pytest \
    tests/integration/test_identity_gaps.py tests/integration/test_media.py \
    tests/integration/test_media_gaps.py tests/integration/test_compression.py \
    tests/integration/test_dev_login.py tests/integration/test_health_and_errors.py \
    tests/integration/test_core_gaps.py -m integration -q
45 passed, 4 deselected, 1 warning in 19.15s
```

### The two integration failures are not mine

**`test_migrations.py` (2 errors).** Both pass on their own:

```
$ DATABASE_URL=postgresql://localhost:5432/cdtm_community_test_identity uv run pytest tests/integration/test_migrations.py -m integration -q
2 passed, 1 warning in 64.65s (0:01:04)
```

They error in the whole-suite run because the other agent is adding revisions concurrently
(`infrastructure/alembic/versions/002_hot_path_indexes.py` is untracked and appeared mid-run).
`infrastructure/alembic` is theirs and I did not touch it.

**`test_auth.py::test_unverified_top_level_email_is_rejected`, pre-existing, and worth
flagging.** `git status` shows `tests/integration/test_auth.py` unmodified, and `git diff`
shows `_email_is_verified` unmodified. Run against HEAD's file directly:

```
$ uv run python -c "... _email_is_verified({'email':'victim@cdtm.com', 'app_metadata':{'provider':'google'}}, ...)"
HEAD  _email_is_verified -> True
mine  _email_is_verified -> True
```

The test mints a token with no `email_verified` claim but with
`app_metadata: {"provider": "google"}`, and `_EMAIL_VERIFYING_PROVIDERS` treats a Google
provider as proof of a verified address. The docstring's threat model ("anyone who can get a
token minted with an arbitrary, unconfirmed `email` claim") is still closed in production,
because `app_metadata` is service-role-only and GoTrue writes it, but the test as written
contradicts the code as written, and one of the two should be updated by whoever owns that
decision. I left both alone rather than weaken a security assertion I was not asked to touch.

---

## Files touched

Source:
- `backend/identity/infrastructure/account_repository.py`
- `backend/identity/infrastructure/jwt_verifier.py`
- `backend/identity/application/ports.py`
- `backend/identity/application/auth_service.py` (one line: `await verify_async`)
- `backend/identity/api/deps.py`
- `backend/media/api/router.py`
- `backend/media/infrastructure/supabase_storage.py`
- `backend/media/infrastructure/ports.py`
- `backend/media/infrastructure/local_disk.py`
- `backend/core/app.py`
- `backend/core/settings/auth.py`
- `backend/core/settings/database.py`
- `infrastructure/db.py`
- `pyproject.toml` (+`cachetools`), `uv.lock`

Docs (small corrections made necessary by the code changes):
- `infrastructure/README.md` (the `_is_pooler_url` troubleshooting entry named a function
  that no longer exists)
- `backend/README.md` (settings table rows, media route note)
- `.env.example` (`DATABASE_POOLER_TRANSACTION_MODE`, `AUTH_SIGN_IN_TOUCH_SECONDS`)

Tests, new:
- `tests/unit/test_identity_sign_in_prelude.py` (10)
- `tests/unit/test_media_signed_urls.py` (9)
- `tests/unit/test_db_pooling.py` (13)
- `tests/integration/test_compression.py` (4)

Tests, edited:
- `tests/unit/test_jwt_verifier_gaps.py` (+8 new; one existing test split in two because the
  behaviour it pinned was the bug)
- `tests/unit/test_media_gaps.py` (+2, appended; the other agent's edits in that file left
  intact)
- `tests/integration/test_identity_gaps.py` (+2 new, +1 comment; the other agent's edits in
  that file left intact)
- `tests/unit/test_auth_service.py` (+`verify_async` on the fake verifier; outside the file
  list I was given, but the port changed)

Not touched: `backend/members`, `backend/paths`, `backend/announcements`, `backend/network`,
`backend/jobboard`, `backend/housing`, `backend/events`, `infrastructure/alembic`,
`backend/core/cache.py`. Nothing was committed, and no `git checkout`/`stash`/`reset` was run.

## Left undone / caveats

- Item 2 (Principal cache) skipped, reasoned above.
- Item 7 (ORJSON) skipped: the finding is stale on FastAPI 0.141.1 and implementing it is a
  regression. Evidence above.
- The `SET LOCAL statement_timeout` listener (item 9) is exercised for *what* it issues and
  *when* it installs, not against a live Supavisor 6543 endpoint. The only one available is the
  production project.
- `warm_jwks` now makes one HTTPS GET to `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` at
  app startup, including in the integration suite (the root `.env` sets `SUPABASE_URL`). It is
  a public read-only endpoint, not the database, with a 5 s timeout, and failure is logged and
  survived. No test or script was pointed at the remote database at any time.
- `uv add cachetools` / `uv remove orjson` re-synced the venv to the default groups and
  dropped `openpyxl`; restored with `uv sync --group data`. `pyproject.toml`'s `data` group is
  unchanged.
