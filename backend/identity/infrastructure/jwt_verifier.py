"""Verify Supabase Auth access tokens.

Supabase signs tokens either with the project's shared HS256 secret (legacy, still the
default for many projects) or with asymmetric keys published at
``/auth/v1/.well-known/jwks.json`` (ES256/RS256). ``alg`` in the token header decides
which path is used.

The two paths cost very different things. HS256 is pure CPU (about 20 microseconds) and
runs inline. The asymmetric path may have to fetch the JWKS over the network, with
``urllib``, synchronously, from inside an async request; a cold or slow fetch there stalls
every other request on the event loop.

Only that fetch is worth a thread, and it happens once per ``jwks_cache_seconds``. Sending
every asymmetric verification through ``anyio.to_thread.run_sync`` charged a warm-cache
verification (a few hundred microseconds of CPU) a ~0.4 ms thread hop plus a slot on the
default 40-token anyio limiter, which Starlette also draws on for synchronous dependencies
and for every ``UploadFile`` read. So a warm key set is verified inline and only a cold or
expired one goes to a thread, through a limiter of its own so a JWKS outage cannot eat the
shared pool.

The fetch is also single-flighted. ``PyJWKClient`` has none: at each cache expiry every
concurrent request fetched the key set itself and parked a thread for up to
``JWKS_TIMEOUT_SECONDS`` doing it. One :class:`anyio.Lock` turns N of those into one.

The last hole is the ``kid``: one PyJWT does not find in the cached set makes it refetch,
inline, per token, so a stream of tokens carrying random key ids was a way to hammer the
JWKS endpoint through this API. Here the key set is looked up before PyJWT gets the token,
a ``kid`` the fresh set does not publish is refused outright, and the refusal is remembered
for :data:`UNKNOWN_KID_SECONDS` so the next token carrying it costs nothing at all.
"""

from __future__ import annotations

import time

import jwt
from anyio import CapacityLimiter, Lock, to_thread
from jwt import PyJWKClient

from backend.core.exceptions import UnauthorizedError
from backend.identity.domain import TokenClaims

#: How long to wait for the JWKS endpoint. PyJWT's own default is 30 seconds, which is a
#: request the caller has already given up on and a worker thread parked for half a minute.
JWKS_TIMEOUT_SECONDS = 5.0

#: How many worker threads may sit in a JWKS fetch at once. Its own limiter, not the default
#: anyio one: the fetch is single-flighted, so one slot is normally enough, and a handful of
#: spares (a verifier per test, a lock that has just been released) must still never be able
#: to starve the pool Starlette runs synchronous dependencies and file reads on.
JWKS_FETCH_SLOTS = 4

#: How long a ``kid`` that the freshly fetched key set does not publish stays refused without
#: another fetch. Short, because a rotated Supabase signing key arrives as exactly this shape
#: and nobody should wait long for it; non-zero, because without it every forged token with a
#: random ``kid`` bought the attacker one synchronous refetch inside PyJWT.
UNKNOWN_KID_SECONDS = 30.0

#: Ceiling on the negative cache. A flood of distinct key ids must not become a memory leak,
#: and the entries are worthless once expired anyway.
UNKNOWN_KID_MAX_ENTRIES = 256


class SupabaseJwtVerifier:
    def __init__(
        self,
        *,
        jwt_secret: str | None,
        jwks_url: str | None,
        audience: str = "authenticated",
        jwks_cache_seconds: int = 600,
        issuer: str | None = None,
    ) -> None:
        self._secret = jwt_secret
        self._audience = audience
        self._issuer = issuer
        self._jwks = (
            PyJWKClient(
                jwks_url,
                # cache_keys=True wraps the per-``kid`` lookup in an unbounded-lifetime
                # lru_cache, so once a key was seen it was held for the life of the process
                # and ``jwks_cache_seconds`` decided nothing at all. False leaves the JWK-set
                # cache, which does honour the lifespan, as the only cache: key rotation is
                # then picked up after at most that long.
                cache_keys=False,
                lifespan=jwks_cache_seconds,
                timeout=JWKS_TIMEOUT_SECONDS,
            )
            if jwks_url
            else None
        )
        # Both are safe to build outside a running event loop: anyio hands back an adapter
        # that binds to the backend on first use, and this object is built lazily by an
        # ``lru_cache`` that a synchronous dependency may reach first.
        self._jwks_refresh = Lock()
        self._jwks_fetch_slots = CapacityLimiter(JWKS_FETCH_SLOTS)
        #: ``kid`` -> monotonic time at which it may be looked up again. See the module
        #: docstring: this is what stops a forged ``kid`` from costing a JWKS fetch.
        self._unknown_kids: dict[str | None, float] = {}

    async def warm_jwks(self) -> None:
        """Fetch the key set once, off the event loop. Raises whatever the fetch raises.

        Called from the application lifespan so the first real request does not pay for a
        cold JWKS. Best effort by contract: the caller decides that a Supabase project that
        is briefly unreachable at boot is not a reason to refuse to start.

        Goes through the same single-flighted refresh as a request does, so a warm-up racing
        the first token produces one fetch and not two.
        """
        if self._jwks is None:
            return
        await self._refresh_jwks()

    async def verify_async(self, token: str) -> TokenClaims:
        """Verify from async code, paying for a thread only when there is something to wait for.

        HS256 is CPU only and stays inline; a thread hop would cost more than the work. So
        does an asymmetric token whose signing key is already in the cached key set, which is
        every one of them except the first after a cache expiry: that verification is a few
        hundred microseconds of local CPU and PyJWT touches the network only when it has to
        look the ``kid`` up in a set it does not hold.

        A cold set, an expired one, or a ``kid`` this process has not seen is the case that
        can block, and only that case goes to a worker thread, once for however many callers
        arrive together.

        There is one narrow window left: a key set that expires between the check here and
        the decode below sends PyJWT to the network inline. It costs at most
        :data:`JWKS_TIMEOUT_SECONDS` and needs a request to land inside a microsecond-wide
        gap once every ``jwks_cache_seconds``, which is not worth a lock on the hot path.
        """
        header = self._header_of(token)
        if str(header.get("alg", "")).startswith("HS"):
            return self.verify(token)
        if self._jwks is None:
            raise UnauthorizedError("asymmetric tokens are not accepted (no JWKS url)")
        kid = header.get("kid")
        if self._recently_unknown(kid):
            raise UnauthorizedError("invalid token")
        if kid not in self._published_kids():
            await self._refresh_jwks()
            if kid not in self._published_kids():
                self._remember_unknown(kid)
                raise UnauthorizedError("invalid token")
        return self.verify(token)

    # ---- the JWKS cache, seen from outside PyJWT ------------------------------------------

    def _published_kids(self) -> frozenset[str | None]:
        """The key ids of the cached JWKS, empty when the cache is cold or expired.

        Read off the raw cached document rather than through ``get_jwk_set``, which rebuilds
        every :class:`~jwt.PyJWK` (and with it every public key object) on each call. The
        filter matches the one ``PyJWKClient.get_signing_keys`` applies, so a ``kid`` counted
        here is one PyJWT will find without going back to the network.
        """
        cache = self._jwks.jwk_set_cache if self._jwks is not None else None
        document = cache.get() if cache is not None else None
        if not isinstance(document, dict):
            return frozenset()
        return frozenset(
            key["kid"]
            for key in document.get("keys", [])
            if isinstance(key, dict) and key.get("kid") and key.get("use") in ("sig", None)
        )

    async def _refresh_jwks(self) -> None:
        """Fetch the key set on a worker thread, once, however many callers want it.

        The lock is the single-flight: ``PyJWKClient`` has none of its own, so at every cache
        expiry each concurrent request fetched the JWKS itself and parked a thread for the
        length of the timeout doing it. Whoever gets the lock second finds a fresh cache and
        returns without touching the network.

        The re-check is "is the cache fresh", not "does it hold the key I wanted", and that
        is deliberate: a fresh key set is taken as the complete answer, so a ``kid`` it does
        not publish is refused rather than chased. It is the same bargain ``cache_keys=False``
        already made above, that a rotated Supabase signing key is picked up within
        ``jwks_cache_seconds`` rather than instantly, and it is what caps this endpoint's
        exposure at one fetch per lifespan no matter what tokens arrive.
        """
        if self._jwks is None:
            return
        async with self._jwks_refresh:
            if self._published_kids():
                return
            await to_thread.run_sync(self._jwks.get_jwk_set, True, limiter=self._jwks_fetch_slots)

    def _recently_unknown(self, kid: str | None) -> bool:
        expires_at = self._unknown_kids.get(kid)
        if expires_at is None:
            return False
        if time.monotonic() >= expires_at:
            del self._unknown_kids[kid]
            return False
        return True

    def _remember_unknown(self, kid: str | None) -> None:
        now = time.monotonic()
        if len(self._unknown_kids) >= UNKNOWN_KID_MAX_ENTRIES:
            # Drop what has expired first. If that frees nothing, the table is full of live
            # entries, which only a flood of distinct key ids produces, so start over: the
            # worst that costs is one JWKS fetch for whoever the reset lets through.
            self._unknown_kids = {k: v for k, v in self._unknown_kids.items() if v > now}
            if len(self._unknown_kids) >= UNKNOWN_KID_MAX_ENTRIES:
                self._unknown_kids.clear()
        self._unknown_kids[kid] = now + UNKNOWN_KID_SECONDS

    def verify(self, token: str) -> TokenClaims:
        alg = self._algorithm_of(token)
        try:
            if alg.startswith("HS"):
                if not self._secret:
                    raise UnauthorizedError("HS256 tokens are not accepted (no secret set)")
                payload = jwt.decode(token, self._secret, algorithms=[alg], audience=self._audience)
            else:
                if self._jwks is None:
                    raise UnauthorizedError("asymmetric tokens are not accepted (no JWKS url)")
                key = self._jwks.get_signing_key_from_jwt(token)
                # ``issuer`` is checked here and not on the HS256 branch: HS256 is the local
                # development login, which mints an issuer of its own (dev_token_issuer), and
                # a real Supabase project on the legacy shared secret is verified by a secret
                # only that project holds. On the asymmetric path the signing key is public,
                # so the issuer is what ties a token to *this* project.
                payload = jwt.decode(
                    token,
                    key.key,
                    algorithms=[alg],
                    audience=self._audience,
                    issuer=self._issuer,
                )
        except jwt.ExpiredSignatureError as exc:
            raise UnauthorizedError("token expired") from exc
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("invalid token") from exc
        return _claims_from_payload(payload)

    @staticmethod
    def _header_of(token: str) -> dict:
        """The unverified JOSE header. Nothing in it is trusted; it only routes the token.

        ``alg`` picks the branch and ``kid`` picks the key, and both are checked against what
        this verifier accepts before any of it decides anything: a header claiming HS256 is
        still refused unless the secret it names verifies the signature.
        """
        try:
            return jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("malformed token") from exc

    @classmethod
    def _algorithm_of(cls, token: str) -> str:
        return str(cls._header_of(token).get("alg", ""))


def _claims_from_payload(payload: dict) -> TokenClaims:
    """Read the identity from the claims Supabase Auth owns, and nowhere else.

    ``user_metadata`` is writable by the end user through Supabase's own update-user call, so
    nothing in it may decide *who* the caller is. The e-mail address is what gates the domain
    allow-list, the admin bootstrap and the binding to a roster row, which made a fallback to
    ``user_metadata.email`` a way to sign in as any Member with a mailbox this platform has
    never seen. Only the top-level ``email`` claim, which Supabase Auth writes, counts; a
    token without one is refused.

    ``email_verified`` must not be read from ``user_metadata`` for the same reason: the copy
    there is writable by the same person it is a statement about. Supabase Auth, though, does
    not put an ``email_verified`` at the top level of an OAuth access token at all - for a
    Google sign-in the flag lives only inside ``user_metadata`` - so a top-level-only read
    rejects every real Google token. The trustworthy signal is ``app_metadata.provider``:
    ``app_metadata`` is written only by the service role (GoTrue itself), never the end user,
    and it records which identity provider actually authenticated the token. Google (OIDC)
    only releases an address it has verified, so a token minted through it is proof of a
    verified e-mail. So the flag is true when Supabase set it at the top level (dev login
    does) OR when the token came through a provider that verifies e-mail itself. Any other
    provider still needs the explicit top-level claim. The display fields below stay on
    ``user_metadata`` deliberately: a name and an avatar are the user's to set, and nothing
    is authorized on them.
    """
    meta = payload.get("user_metadata") or {}
    app_meta = payload.get("app_metadata") or {}
    email = payload.get("email")
    if not payload.get("sub") or not email:
        raise UnauthorizedError("token is missing sub or email")
    return TokenClaims(
        sub=payload["sub"],
        email=str(email).lower(),
        email_verified=_email_is_verified(payload, app_meta),
        full_name=meta.get("full_name") or meta.get("name"),
        avatar_url=meta.get("avatar_url") or meta.get("picture"),
        provider=app_meta.get("provider"),
    )


#: Identity providers that verify the e-mail address before releasing it. A token minted
#: through one of these carries a verified address even when GoTrue omits the top-level
#: ``email_verified`` flag. Read from ``app_metadata`` (service-role-only), never from the
#: user-writable ``user_metadata``. Kept to the providers this platform actually allows.
_EMAIL_VERIFYING_PROVIDERS = frozenset({"google"})


def _email_is_verified(payload: dict, app_meta: dict) -> bool:
    if bool(payload.get("email_verified", False)):
        return True
    provider = app_meta.get("provider")
    providers = app_meta.get("providers")
    return provider in _EMAIL_VERIFYING_PROVIDERS or (
        isinstance(providers, list) and any(p in _EMAIL_VERIFYING_PROVIDERS for p in providers)
    )
