"""The development token has to be a token the production verifier accepts."""

from __future__ import annotations

import pytest

from backend.core.exceptions import UnauthorizedError
from backend.identity.infrastructure.dev_token_issuer import (
    DEV_LOGIN_ISSUER,
    DevTokenIssuer,
    dev_subject_for,
)
from backend.identity.infrastructure.jwt_verifier import SupabaseJwtVerifier

SECRET = "unit-test-secret-at-least-32-bytes-long"


def _verifier(secret: str = SECRET, audience: str = "authenticated") -> SupabaseJwtVerifier:
    return SupabaseJwtVerifier(jwt_secret=secret, jwks_url=None, audience=audience)


def test_issued_token_verifies_and_carries_the_claims() -> None:
    issuer = DevTokenIssuer(jwt_secret=SECRET)
    token = issuer.issue("Anna.Test@cdtm.com", full_name="Anna Test")

    claims = _verifier().verify(token.access_token)

    assert claims.email == "anna.test@cdtm.com"
    assert claims.full_name == "Anna Test"
    assert claims.provider == "dev"
    assert claims.sub == token.subject
    assert token.expires_in == 12 * 60 * 60


def test_subject_is_stable_per_email() -> None:
    issuer = DevTokenIssuer(jwt_secret=SECRET)
    first = issuer.issue("ben.test@cdtm.com")
    second = issuer.issue("  BEN.TEST@cdtm.com ")
    assert first.subject == second.subject == dev_subject_for("ben.test@cdtm.com")


def test_issuer_claim_marks_the_token_as_locally_minted() -> None:
    import jwt

    token = DevTokenIssuer(jwt_secret=SECRET).issue("anna.test@cdtm.com")
    payload = jwt.decode(token.access_token, SECRET, algorithms=["HS256"], audience="authenticated")
    assert payload["iss"] == DEV_LOGIN_ISSUER


def test_another_secret_does_not_verify() -> None:
    token = DevTokenIssuer(jwt_secret=SECRET).issue("anna.test@cdtm.com")
    with pytest.raises(UnauthorizedError):
        _verifier(secret="a-different-secret-entirely-32-bytes").verify(token.access_token)


def test_audience_must_match() -> None:
    token = DevTokenIssuer(jwt_secret=SECRET, audience="something-else").issue("a@cdtm.com")
    with pytest.raises(UnauthorizedError):
        _verifier().verify(token.access_token)
