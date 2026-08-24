"""Mint a Supabase-shaped access token locally, for development only.

There is no Supabase project yet, but the API must not grow a second way in: everything the
frontend does still travels as ``Authorization: Bearer <jwt>`` and is still checked by
:class:`~backend.identity.infrastructure.jwt_verifier.SupabaseJwtVerifier`. This issuer only
replaces the part Supabase would normally do, signing with the same HS256 secret the verifier
is configured with, so the code path under test is the production one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

#: Fixed namespace so ``uuid5(NAMESPACE, email)`` is stable across restarts. Signing in twice
#: with the same address must reach the same ``accounts`` row, exactly as a real ``sub`` would.
DEV_SUBJECT_NAMESPACE = uuid.UUID("2b0f3d5a-9e4c-5f21-9a7d-0f2e6c1b8d40")

DEV_LOGIN_ISSUER = "cdtm-dev-login"
DEV_TOKEN_TTL_SECONDS = 12 * 60 * 60


@dataclass(frozen=True, slots=True)
class DevToken:
    access_token: str
    expires_in: int
    subject: uuid.UUID


def dev_subject_for(email: str) -> uuid.UUID:
    return uuid.uuid5(DEV_SUBJECT_NAMESPACE, email.strip().lower())


class DevTokenIssuer:
    def __init__(
        self,
        *,
        jwt_secret: str,
        audience: str = "authenticated",
        ttl_seconds: int = DEV_TOKEN_TTL_SECONDS,
    ) -> None:
        self._secret = jwt_secret
        self._audience = audience
        self._ttl = ttl_seconds

    def issue(self, email: str, *, full_name: str | None = None) -> DevToken:
        email = email.strip().lower()
        subject = dev_subject_for(email)
        now = datetime.now(UTC)
        payload = {
            "sub": str(subject),
            "aud": self._audience,
            "role": "authenticated",
            "email": email,
            # Top level, where Supabase Auth writes them and where the verifier reads them.
            # The user_metadata copies below are the display fields only.
            "email_verified": True,
            "iss": DEV_LOGIN_ISSUER,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self._ttl)).timestamp()),
            # Display fields only. Nothing the verifier authorizes on is read from here,
            # because on a real Supabase project this object is writable by the end user.
            "user_metadata": {"full_name": full_name or email.split("@")[0]},
            # "dev" rather than "google": the provider is the one honest claim here, and it
            # makes a token minted locally recognisable in the accounts table and in logs.
            "app_metadata": {"provider": "dev"},
        }
        token = jwt.encode(payload, self._secret, algorithm="HS256")
        return DevToken(access_token=token, expires_in=self._ttl, subject=subject)
