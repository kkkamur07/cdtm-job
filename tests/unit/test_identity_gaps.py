"""The identity seams no integration test can pin down: Actor translation, the bearer header,
the domain of an address, the dev token's expiry and display name, and the dev-login wiring.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import jwt
import pytest

from backend.core.exceptions import UnauthorizedError
from backend.core.settings import reset_settings_caches
from backend.identity.api.deps import (
    _bearer,
    get_actor,
    get_dev_login_service,
    get_member_actor,
    get_optional_actor,
)
from backend.identity.application.auth_service import _domain_of
from backend.identity.domain import Account, Principal
from backend.identity.infrastructure.dev_token_issuer import DevTokenIssuer
from backend.identity.infrastructure.jwt_verifier import SupabaseJwtVerifier

SECRET = "unit-test-secret-at-least-32-bytes-long"


def _principal(*, is_admin: bool, member_id: uuid.UUID | None) -> Principal:
    now = datetime.now(UTC)
    return Principal(
        account=Account(
            id=uuid.uuid4(),
            auth_user_id=uuid.uuid4(),
            email="person@cdtm.com",
            member_id=member_id,
            is_admin=is_admin,
            created_at=now,
            updated_at=now,
        )
    )


# ---- Principal -> Actor, the seam every other context uses --------------------------------


def test_the_actor_for_a_member_owned_write_keeps_the_admin_flag() -> None:
    """``MemberActorDep`` is what every board asks for before a member-owned write. An Actor
    built there without the caller's admin flag would quietly demote every admin on exactly
    the routes where admin is what lets them edit somebody else's row."""
    principal = _principal(is_admin=True, member_id=uuid.uuid4())

    actor = get_member_actor(principal)

    assert actor.member_id == principal.member_id
    assert actor.is_admin is True


def test_a_plain_member_actor_is_not_an_admin() -> None:
    principal = _principal(is_admin=False, member_id=uuid.uuid4())
    assert get_member_actor(principal).is_admin is False


def test_the_other_two_actor_seams_carry_the_same_two_facts() -> None:
    principal = _principal(is_admin=True, member_id=uuid.uuid4())

    for actor in (get_actor(principal), get_optional_actor(principal)):
        assert actor.member_id == principal.member_id
        assert actor.is_admin is True

    assert get_optional_actor(None) is None


# ---- the Authorization header -------------------------------------------------------------


def test_a_token_presented_under_the_wrong_scheme_is_refused() -> None:
    """The scheme has to be enforced on its own. A value that merely *looks* like a token
    after some other scheme is not a Bearer credential, and letting it through would mean the
    API accepts an ``Authorization: Basic <jwt>`` it never agreed to read."""
    with pytest.raises(UnauthorizedError):
        _bearer("Basic eyJhbGciOiJIUzI1NiJ9.e30.signature")


def test_a_bearer_header_with_no_token_is_refused() -> None:
    with pytest.raises(UnauthorizedError):
        _bearer("Bearer ")


def test_no_header_at_all_is_simply_anonymous() -> None:
    assert _bearer(None) is None


# ---- the domain the allow-list is applied to ----------------------------------------------


def test_the_domain_is_what_follows_the_last_at_sign() -> None:
    """A malformed address with more than one ``@`` must be read the way a mail system reads
    it: the domain is the part after the last one. Taking the part after the *first* ``@``
    would let ``victim@cdtm.com@attacker.example`` be judged on ``cdtm.com``."""
    assert _domain_of("victim@cdtm.com@attacker.example") == "attacker.example"
    assert _domain_of("person@CDTM.com") == "cdtm.com"
    assert _domain_of("no-at-sign") == ""


# ---- the development token ----------------------------------------------------------------


def test_a_dev_token_past_its_lifetime_is_refused() -> None:
    """The issuer has to stamp an expiry the verifier actually enforces. A token minted
    without one would be a bearer credential that never stops working, and PyJWT only checks
    an expiry that is there."""
    issuer = DevTokenIssuer(jwt_secret=SECRET, ttl_seconds=-60)
    token = issuer.issue("anna.test@cdtm.com")

    with pytest.raises(UnauthorizedError):
        SupabaseJwtVerifier(jwt_secret=SECRET, jwks_url=None).verify(token.access_token)


def test_an_anonymous_dev_login_is_named_after_the_mailbox_not_the_domain() -> None:
    """With no roster row to take a name from, the local part of the address is the display
    name. The domain would name everyone on it the same thing."""
    token = DevTokenIssuer(jwt_secret=SECRET).issue("anna.test@cdtm.com")
    claims = SupabaseJwtVerifier(jwt_secret=SECRET, jwks_url=None).verify(token.access_token)
    assert claims.full_name == "anna.test"


# ---- the dev-login wiring -----------------------------------------------------------------


class _StubAuth:
    """Stands in for AuthService: DevLoginService only mints a token and hands it over."""

    def __init__(self) -> None:
        self.tokens: list[str] = []

    def ensure_email_allowed(self, email: str) -> None:
        """Every address is allowed here; the allow-list has its own tests."""

    async def authenticate(self, token: str) -> Principal:
        self.tokens.append(token)
        return _principal(is_admin=False, member_id=None)

    async def find_member_slug(self, principal: Principal) -> str | None:
        return None


@pytest.fixture
def clean_settings():
    reset_settings_caches()
    yield
    reset_settings_caches()


async def test_the_dev_login_mints_tokens_for_the_configured_audience(
    monkeypatch: pytest.MonkeyPatch, clean_settings: None
) -> None:
    """The audience is what stops a token minted for one Supabase project being replayed at
    another. The issuer has to be given the configured one, not its own default, or a
    deployment that sets ``AUTH_JWT_AUDIENCE`` would hand out tokens its own verifier rejects
    (or worse, ones another deployment accepts)."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.setenv("AUTH_JWT_AUDIENCE", "cdtm-api")
    reset_settings_caches()

    auth = _StubAuth()
    # No database is touched: with an ``email`` and no ``member_slug`` the roster is never read.
    service = get_dev_login_service(None, auth)
    await service.login(email="anna.test@cdtm.com")

    payload = jwt.decode(auth.tokens[0], SECRET, algorithms=["HS256"], audience="cdtm-api")
    assert payload["aud"] == "cdtm-api"
