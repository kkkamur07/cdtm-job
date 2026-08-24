"""The asymmetric half of the Supabase verifier, plus expiry and the display-field claims.

Supabase signs access tokens either with the project's shared HS256 secret or with the
RS256/ES256 keys it publishes at ``/auth/v1/.well-known/jwks.json``; the token header decides
which. Every other test in the suite mints HS256, so the whole JWKS path, the one the module
docstring calls the default for many real projects, had no coverage at all.

These tests serve a real JWKS over loopback rather than stubbing ``PyJWKClient``, because the
client is the part being wired: it is what fetches, caches and matches ``kid``, and a
verifier that never reaches it looks identical from the outside until a real Supabase token
arrives.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from backend.core.exceptions import UnauthorizedError
from backend.identity.infrastructure.dev_token_issuer import DEV_LOGIN_ISSUER
from backend.identity.infrastructure.jwt_verifier import (
    SupabaseJwtVerifier,
    _claims_from_payload,
)

HS_SECRET = "unit-test-secret-at-least-32-bytes-long"
SUBJECT = "11111111-1111-1111-1111-111111111111"

# Generated once: an RSA keypair costs about a tenth of a second and every test wants the
# same published keys.
RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
EC_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwk(private_key, *, alg: str, kid: str) -> dict:
    """The public half of a keypair in the shape a JWKS endpoint publishes it."""
    algorithm = (
        RSAAlgorithm(RSAAlgorithm.SHA256) if alg == "RS256" else ECAlgorithm(ECAlgorithm.SHA256)
    )
    entry = json.loads(algorithm.to_jwk(private_key.public_key()))
    entry.update({"kid": kid, "use": "sig", "alg": alg})
    return entry


JWKS_DOCUMENT = {
    "keys": [
        _jwk(RSA_KEY, alg="RS256", kid="rsa-1"),
        _jwk(EC_KEY, alg="ES256", kid="ec-1"),
    ]
}


class _Jwks:
    """A loopback JWKS endpoint that counts how often it is fetched."""

    def __init__(self) -> None:
        document = json.dumps(JWKS_DOCUMENT).encode()
        self.fetches = 0
        endpoint = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's name
                endpoint.fetches += 1
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(document)))
                self.end_headers()
                self.wfile.write(document)

            def log_message(self, *args: object) -> None:
                """Keep the test output clean."""

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}/jwks.json"

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


@pytest.fixture
def jwks() -> _Jwks:
    endpoint = _Jwks()
    yield endpoint
    endpoint.close()


def _asymmetric_token(
    key, *, alg: str, kid: str, audience: str = "authenticated", **overrides
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": SUBJECT,
        "aud": audience,
        "email": "asymmetric.person@cdtm.com",
        "email_verified": True,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "user_metadata": {"full_name": "Asymmetric Person"},
        "app_metadata": {"provider": "google"},
    }
    payload.update(overrides)
    return jwt.encode(payload, key, algorithm=alg, headers={"kid": kid})


def _verifier(jwks_url: str | None, **kwargs) -> SupabaseJwtVerifier:
    kwargs.setdefault("jwt_secret", None)
    kwargs.setdefault("audience", "authenticated")
    kwargs.setdefault("jwks_cache_seconds", 600)
    return SupabaseJwtVerifier(jwks_url=jwks_url, **kwargs)


# ---- the JWKS path ------------------------------------------------------------------------


def test_an_rs256_token_signed_by_a_published_key_is_accepted(jwks: _Jwks) -> None:
    """The production path for a Supabase project on asymmetric keys: the verifier fetches
    the JWKS, matches the token's ``kid`` and reads the same identity out of it as it does
    from an HS256 token."""
    claims = _verifier(jwks.url).verify(_asymmetric_token(RSA_KEY, alg="RS256", kid="rsa-1"))

    assert str(claims.sub) == SUBJECT
    assert claims.email == "asymmetric.person@cdtm.com"
    assert claims.email_verified is True
    assert claims.full_name == "Asymmetric Person"
    assert jwks.fetches == 1


def test_an_es256_token_signed_by_a_published_key_is_accepted(jwks: _Jwks) -> None:
    """ES256 is what a freshly created Supabase project signs with today."""
    claims = _verifier(jwks.url).verify(_asymmetric_token(EC_KEY, alg="ES256", kid="ec-1"))
    assert str(claims.sub) == SUBJECT


def test_a_token_signed_by_a_key_the_jwks_does_not_publish_is_refused(jwks: _Jwks) -> None:
    """The forgery this whole path exists to stop: the right ``kid``, the wrong private key."""
    token = _asymmetric_token(OTHER_RSA_KEY, alg="RS256", kid="rsa-1")
    with pytest.raises(UnauthorizedError):
        _verifier(jwks.url).verify(token)


def test_a_token_naming_a_key_id_the_jwks_does_not_have_is_refused(jwks: _Jwks) -> None:
    token = _asymmetric_token(RSA_KEY, alg="RS256", kid="not-a-published-key")
    with pytest.raises(UnauthorizedError):
        _verifier(jwks.url).verify(token)


def test_an_asymmetric_token_minted_for_another_audience_is_refused(jwks: _Jwks) -> None:
    """The audience is checked on this path too, not only on the HS256 one."""
    token = _asymmetric_token(RSA_KEY, alg="RS256", kid="rsa-1", audience="some-other-project")
    with pytest.raises(UnauthorizedError):
        _verifier(jwks.url).verify(token)


def test_an_asymmetric_token_is_refused_when_no_jwks_is_configured() -> None:
    """A deployment with only the HS256 secret set must refuse an RS256 token cleanly rather
    than crash on the missing JWKS client."""
    verifier = SupabaseJwtVerifier(jwt_secret=HS_SECRET, jwks_url=None)
    with pytest.raises(UnauthorizedError):
        verifier.verify(_asymmetric_token(RSA_KEY, alg="RS256", kid="rsa-1"))


def test_an_hs256_token_is_refused_when_no_secret_is_configured(jwks: _Jwks) -> None:
    """The mirror image: a project on asymmetric keys only does not accept the legacy
    shared-secret token shape."""
    token = jwt.encode(
        {"sub": SUBJECT, "aud": "authenticated", "email": "a@cdtm.com"},
        HS_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(UnauthorizedError):
        _verifier(jwks.url).verify(token)


def test_the_key_set_is_cached_so_a_stream_of_tokens_does_not_refetch_the_jwks(
    jwks: _Jwks,
) -> None:
    """Every request carries a token, so a verifier that re-fetched the key set per request
    would put the JWKS endpoint on the hot path of the whole API."""
    verifier = _verifier(jwks.url, jwks_cache_seconds=600)
    token = _asymmetric_token(RSA_KEY, alg="RS256", kid="rsa-1")

    for _ in range(5):
        verifier.verify(token)

    assert jwks.fetches == 1


def test_the_configured_lifetime_is_what_decides_when_the_keys_are_refetched(
    jwks: _Jwks,
) -> None:
    """This used to assert the opposite, that an expired key set still served from a
    per-``kid`` cache. That cache (PyJWT's ``cache_keys=True``) has no lifetime at all: a key
    seen once was held for the life of the process, so ``AUTH_JWKS_CACHE_SECONDS`` decided
    nothing and a rotated Supabase signing key would never have been picked up. With it off,
    the key set cache is the only cache, and the configured lifetime is real."""
    verifier = _verifier(jwks.url, jwks_cache_seconds=0.001)
    token = _asymmetric_token(RSA_KEY, alg="RS256", kid="rsa-1")

    verifier.verify(token)
    threading.Event().wait(0.05)
    verifier.verify(token)

    assert jwks.fetches == 2


def test_a_cache_lifetime_of_zero_is_refused_rather_than_ignored(jwks: _Jwks) -> None:
    """The configured lifetime reaches the JWKS client: a value it cannot honour is an error
    at construction, not a silent fallback to the library default."""
    with pytest.raises(jwt.PyJWKClientError):
        _verifier(jwks.url, jwks_cache_seconds=0)


# ---- expiry -------------------------------------------------------------------------------


def test_a_token_whose_exp_has_passed_is_refused() -> None:
    """Nothing else in the suite ever presents an expired token, so the branch that turns
    PyJWT's ExpiredSignatureError into a 401 was never entered."""
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": SUBJECT,
            "aud": "authenticated",
            "email": "expired.person@cdtm.com",
            "email_verified": True,
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(hours=1)).timestamp()),
        },
        HS_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(UnauthorizedError):
        SupabaseJwtVerifier(jwt_secret=HS_SECRET, jwks_url=None).verify(token)


# ---- the display fields off user_metadata -------------------------------------------------


def _payload(**overrides) -> dict:
    base = {
        "sub": SUBJECT,
        "email": "person@cdtm.com",
        "email_verified": True,
        "app_metadata": {"provider": "google"},
    }
    base.update(overrides)
    return base


def test_an_avatar_url_claim_becomes_the_account_avatar() -> None:
    """Supabase writes the Google profile picture into ``user_metadata.avatar_url``; it is
    what the frontend shows next to a name, and no fixture anywhere supplies one."""
    claims = _claims_from_payload(
        _payload(user_metadata={"avatar_url": "https://cdn.example.com/a.png"})
    )
    assert claims.avatar_url == "https://cdn.example.com/a.png"


def test_a_picture_claim_is_used_when_there_is_no_avatar_url() -> None:
    """Some providers write the OIDC ``picture`` claim instead."""
    claims = _claims_from_payload(
        _payload(user_metadata={"picture": "https://cdn.example.com/b.png"})
    )
    assert claims.avatar_url == "https://cdn.example.com/b.png"


def test_a_name_claim_is_used_when_there_is_no_full_name() -> None:
    claims = _claims_from_payload(_payload(user_metadata={"name": "Only A Name"}))
    assert claims.full_name == "Only A Name"


# ---- the issuer, and getting off the event loop --------------------------------------------


ISSUER = "https://project.supabase.co/auth/v1"


def test_an_asymmetric_token_from_another_project_is_refused(jwks: _Jwks) -> None:
    """On this path the signing key is public, so the signature alone only proves that
    *some* Supabase project minted the token. The issuer is what ties it to ours."""
    verifier = _verifier(jwks.url, issuer=ISSUER)
    token = _asymmetric_token(RSA_KEY, alg="RS256", kid="rsa-1", iss="https://other/auth/v1")

    with pytest.raises(UnauthorizedError):
        verifier.verify(token)


def test_an_asymmetric_token_from_this_project_is_accepted(jwks: _Jwks) -> None:
    verifier = _verifier(jwks.url, issuer=ISSUER)
    token = _asymmetric_token(RSA_KEY, alg="RS256", kid="rsa-1", iss=ISSUER)

    assert str(verifier.verify(token).sub) == SUBJECT


def test_an_asymmetric_token_with_no_issuer_at_all_is_refused(jwks: _Jwks) -> None:
    """Once the check is configured, a token that simply omits ``iss`` must not slip past it."""
    verifier = _verifier(jwks.url, issuer=ISSUER)

    with pytest.raises(UnauthorizedError):
        verifier.verify(_asymmetric_token(RSA_KEY, alg="RS256", kid="rsa-1"))


def test_no_configured_issuer_means_no_issuer_check(jwks: _Jwks) -> None:
    """``SUPABASE_URL`` is what the issuer is derived from, and a deployment on the legacy
    shared secret alone does not set it. Nothing may start refusing tokens for a value that
    could not be computed."""
    assert str(_verifier(jwks.url).verify(_asymmetric_token(RSA_KEY, alg="RS256", kid="rsa-1")).sub)


def test_the_development_login_issuer_still_passes_on_the_hs256_path(jwks: _Jwks) -> None:
    """The dev login mints ``iss: cdtm-dev-login``, which is not this project's issuer. The
    check belongs to the asymmetric path only, so the local sign-in keeps working even on a
    deployment that has SUPABASE_URL set."""
    verifier = _verifier(jwks.url, jwt_secret=HS_SECRET, issuer=ISSUER)
    token = jwt.encode(
        {
            "sub": SUBJECT,
            "aud": "authenticated",
            "email": "dev.person@cdtm.com",
            "email_verified": True,
            "iss": DEV_LOGIN_ISSUER,
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        },
        HS_SECRET,
        algorithm="HS256",
    )

    assert verifier.verify(token).email == "dev.person@cdtm.com"


async def test_verify_async_keeps_the_cheap_path_inline_and_threads_the_other(
    jwks: _Jwks,
) -> None:
    """HS256 is about twenty microseconds of CPU, so a thread hop would cost more than the
    work. The JWKS path can block on a network fetch inside PyJWT's synchronous urllib, on
    the one event loop that serves every request, so it goes to a worker thread."""
    verifier = _verifier(jwks.url, jwt_secret=HS_SECRET)
    hs_token = jwt.encode(
        {
            "sub": SUBJECT,
            "aud": "authenticated",
            "email": "hs.person@cdtm.com",
            "email_verified": True,
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        },
        HS_SECRET,
        algorithm="HS256",
    )
    on_the_loop = threading.get_ident()
    seen: list[int] = []
    verify = verifier.verify
    verifier.verify = lambda token: (seen.append(threading.get_ident()), verify(token))[1]

    assert (await verifier.verify_async(hs_token)).email == "hs.person@cdtm.com"
    assert seen == [on_the_loop]

    seen.clear()
    await verifier.verify_async(_asymmetric_token(RSA_KEY, alg="RS256", kid="rsa-1"))
    assert seen and seen != [on_the_loop]


async def test_warming_the_key_set_means_the_first_token_does_not_fetch_it(jwks: _Jwks) -> None:
    """The app lifespan calls this so the first request that presents an asymmetric token is
    not the one that pays for a cold JWKS fetch."""
    verifier = _verifier(jwks.url)

    await verifier.warm_jwks()
    assert jwks.fetches == 1

    verifier.verify(_asymmetric_token(RSA_KEY, alg="RS256", kid="rsa-1"))
    assert jwks.fetches == 1


async def test_warming_a_verifier_with_no_jwks_configured_does_nothing() -> None:
    await SupabaseJwtVerifier(jwt_secret=HS_SECRET, jwks_url=None).warm_jwks()
