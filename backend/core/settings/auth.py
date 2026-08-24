from __future__ import annotations

from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode

from backend.core.settings._cache import settings_cache
from backend.core.settings._env import env_settings_config


class AuthSettings(BaseSettings):
    """How the API verifies Supabase Auth JWTs and who may sign in.

    Supabase issues tokens either signed with the project's legacy HS256 secret
    (``SUPABASE_JWT_SECRET``) or with asymmetric keys published at
    ``{SUPABASE_URL}/auth/v1/.well-known/jwks.json``. Set one of ``jwt_secret`` or
    ``supabase_url``; when both are set the token's ``alg`` decides.
    """

    model_config = env_settings_config("AUTH_")

    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    jwt_secret: str | None = Field(default=None, alias="SUPABASE_JWT_SECRET")
    jwt_audience: str = "authenticated"
    jwks_cache_seconds: int = 600
    # How stale ``accounts.last_sign_in_at`` may get before a request refreshes it. Every
    # authenticated request used to UPDATE the row, so every GET took a row lock and wrote
    # WAL for a column nothing reads more precisely than "roughly when were they last here".
    # Fifteen minutes keeps the admin worklist useful and turns the prelude into one SELECT.
    sign_in_touch_seconds: int = 900
    # Only Google Workspace accounts from these domains may sign in.
    # NoDecode: env values are plain comma lists, not JSON; the validator below splits them.
    allowed_email_domains: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["cdtm.com"]
    )
    # Local sign-in without a Supabase project: /auth/dev/login mints a token with the same
    # HS256 secret the verifier checks. Off by default and refused at boot in production,
    # because anyone who can reach the endpoint can become anyone on an allowed domain.
    dev_login_enabled: bool = False
    # Bootstrap admins by email; admins can also be promoted in the accounts table.
    # NoDecode: env values are plain comma lists, not JSON; the validator below splits them.
    admin_emails: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @field_validator("allowed_email_domains", "admin_emails", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [v.strip().lower() for v in value.split(",") if v.strip()]
        if isinstance(value, list):
            return [str(v).lower() for v in value]
        return value

    @property
    def jwks_url(self) -> str | None:
        if not self.supabase_url:
            return None
        return self.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"

    @property
    def jwt_issuer(self) -> str | None:
        """The ``iss`` a Supabase-issued token carries, or ``None`` when unknown.

        GoTrue signs every access token with ``iss = {SUPABASE_URL}/auth/v1``. Checking it
        stops a token minted by *another* Supabase project whose signing key happens to be
        reachable from being accepted here. It is only knowable when the project URL is
        configured, and only applies to the asymmetric path: the HS256 path is the local
        development login, which mints its own issuer (see ``dev_token_issuer``).
        """
        if not self.supabase_url:
            return None
        return self.supabase_url.rstrip("/") + "/auth/v1"


@settings_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()
