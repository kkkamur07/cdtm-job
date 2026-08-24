"""Verify Supabase Auth access tokens.

Supabase signs tokens either with the project's shared HS256 secret (legacy, still the
default for many projects) or with asymmetric keys published at
``/auth/v1/.well-known/jwks.json`` (ES256/RS256). ``alg`` in the token header decides
which path is used.
"""

from __future__ import annotations

import jwt
from jwt import PyJWKClient

from backend.core.exceptions import UnauthorizedError
from backend.identity.domain import TokenClaims


class SupabaseJwtVerifier:
    def __init__(
        self,
        *,
        jwt_secret: str | None,
        jwks_url: str | None,
        audience: str = "authenticated",
        jwks_cache_seconds: int = 600,
    ) -> None:
        self._secret = jwt_secret
        self._audience = audience
        self._jwks = (
            PyJWKClient(jwks_url, cache_keys=True, lifespan=jwks_cache_seconds)
            if jwks_url
            else None
        )

    def verify(self, token: str) -> TokenClaims:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("malformed token") from exc
        alg = header.get("alg", "")
        try:
            if alg.startswith("HS"):
                if not self._secret:
                    raise UnauthorizedError("HS256 tokens are not accepted (no secret set)")
                payload = jwt.decode(token, self._secret, algorithms=[alg], audience=self._audience)
            else:
                if self._jwks is None:
                    raise UnauthorizedError("asymmetric tokens are not accepted (no JWKS url)")
                key = self._jwks.get_signing_key_from_jwt(token)
                payload = jwt.decode(token, key.key, algorithms=[alg], audience=self._audience)
        except jwt.ExpiredSignatureError as exc:
            raise UnauthorizedError("token expired") from exc
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("invalid token") from exc
        return _claims_from_payload(payload)


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
