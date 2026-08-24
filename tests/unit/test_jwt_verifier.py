"""Claim-presence rules for the Supabase token reader.

The identity a token carries decides the domain allow-list, the admin bootstrap and the
binding to a roster row, so a token that is missing either half of that identity (``sub``
or the top-level ``email``) must be refused rather than papered over. Every integration
test mints a well-formed token, so this is the only place the missing-claim paths are
exercised.
"""

from __future__ import annotations

import pytest

from backend.core.exceptions import UnauthorizedError
from backend.identity.infrastructure.jwt_verifier import _claims_from_payload


def _payload(**overrides) -> dict:
    base = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "email": "person@cdtm.com",
        "email_verified": True,
        "user_metadata": {"full_name": "A Person"},
        "app_metadata": {"provider": "google"},
    }
    base.update(overrides)
    return base


def test_both_sub_and_email_present_is_accepted() -> None:
    claims = _claims_from_payload(_payload())
    assert str(claims.sub) == "11111111-1111-1111-1111-111111111111"
    assert claims.email == "person@cdtm.com"
    assert claims.email_verified is True


def test_a_token_without_sub_is_refused() -> None:
    payload = _payload()
    del payload["sub"]
    with pytest.raises(UnauthorizedError):
        _claims_from_payload(payload)


def test_a_token_without_a_top_level_email_is_refused() -> None:
    payload = _payload()
    del payload["email"]
    with pytest.raises(UnauthorizedError):
        _claims_from_payload(payload)


def test_an_empty_email_is_refused() -> None:
    with pytest.raises(UnauthorizedError):
        _claims_from_payload(_payload(email=""))


def test_a_real_google_token_verifies_without_a_top_level_flag() -> None:
    """A live Supabase OAuth token puts ``email_verified`` inside ``user_metadata``, not at
    the top level. The provider recorded in ``app_metadata`` (service-role-only) is what makes
    the address trustworthy, so such a token is accepted as verified."""
    payload = _payload(
        user_metadata={"full_name": "A Person", "email_verified": True},
        app_metadata={"provider": "google", "providers": ["google"]},
    )
    del payload["email_verified"]
    assert _claims_from_payload(payload).email_verified is True


def test_a_non_verifying_provider_without_the_flag_is_not_verified() -> None:
    """No top-level flag and a provider that does not verify e-mail itself: the address is not
    a verified fact, so the flag stays false and the allow-list check downstream rejects it."""
    payload = _payload(
        user_metadata={"full_name": "A Person"},
        app_metadata={"provider": "email", "providers": ["email"]},
    )
    del payload["email_verified"]
    assert _claims_from_payload(payload).email_verified is False


def test_user_metadata_alone_cannot_claim_verification() -> None:
    """``user_metadata`` is end-user writable, so a verified flag placed there without a
    trusted provider must not authorize anything."""
    payload = _payload(
        user_metadata={"full_name": "A Person", "email_verified": True},
        app_metadata={"provider": "email"},
    )
    del payload["email_verified"]
    assert _claims_from_payload(payload).email_verified is False
