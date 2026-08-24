"""The directory, one member's profile, and the entry and intents they maintain."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.integration.conftest import _engine, insert_member

pytestmark = pytest.mark.integration
API = "/api/v1/members"


def test_directory_search_and_profile(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    h = member_anna["headers"]
    r = client.get(f"{API}/", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 2
    r = client.get(f"{API}/", params={"q": "ben"}, headers=h)
    assert [m["slug"] for m in r.json()["items"]] == ["ben-test"]
    r = client.get(f"{API}/ben-test", headers=h)
    assert r.status_code == 200
    assert r.json()["email"] is None  # not self, not admin
    r = client.get(f"{API}/anna-test", headers=h)
    assert r.json()["email"] == "anna.test@cdtm.com"
    assert r.json()["is_claimed"] is True  # anna signed in, so her account is bound
    r = client.get(f"{API}/facets", headers=h)
    assert r.json()["members_total"] == 2


def test_member_lookup_by_ids(client: TestClient, member_anna: dict, member_ben: dict) -> None:
    """One call resolves the authors behind jobs, listings and events to cards, in order."""
    h = member_anna["headers"]
    ben, anna = str(member_ben["id"]), str(member_anna["id"])
    unknown = "00000000-0000-0000-0000-000000000000"
    r = client.get(f"{API}/lookup", params={"ids": [ben, anna, ben, unknown]}, headers=h)
    assert r.status_code == 200, r.text
    assert [m["slug"] for m in r.json()["items"]] == ["ben-test", "anna-test"]
    assert r.json()["total"] == 2
    r = client.get(f"{API}/lookup", params={"ids": ["not-a-uuid"]}, headers=h)
    assert r.status_code == 422
    assert client.get(f"{API}/lookup", params={"ids": [ben]}).status_code == 401


def test_one_member_per_company_in_one_call(client: TestClient, member_anna: dict) -> None:
    """The job board resolves a page full of companies in a single request."""
    insert_member("cara-bmw", "Cara BMW", current_company="BMW", search_text="cara bmw")
    insert_member("dan-bmw", "Dan BMW", current_company="BMW Group", search_text="dan bmw group")
    insert_member("eve-goo", "Eve Goo", current_company="Google", search_text="eve goo google")
    h = member_anna["headers"]
    r = client.get(
        f"{API}/at-company", params={"company": ["Google", "BMW", "Nobody Inc"]}, headers=h
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Order follows the question; a company nobody works at is simply absent.
    assert [c["company"] for c in body["items"]] == ["Google", "BMW"]
    assert body["total"] == 2
    by_company = {c["company"]: c for c in body["items"]}
    assert by_company["Google"]["member"]["slug"] == "eve-goo"
    assert by_company["Google"]["total"] == 1
    # "BMW" also matches "BMW Group", and the count is the whole match, not the page.
    assert by_company["BMW"]["member"]["slug"] == "cara-bmw"
    assert by_company["BMW"]["total"] == 2
    # A name full of wildcards is a name, not a pattern.
    assert (
        client.get(f"{API}/at-company", params={"company": ["%"]}, headers=h).json()["items"] == []
    )
    assert client.get(f"{API}/at-company", params={"company": ["BMW"]}).status_code == 401


def test_the_card_does_not_carry_roster_matching_metadata(
    client: TestClient, member_anna: dict, admin_headers: dict
) -> None:
    """How the loader bound a person to a mailbox is nobody's business but an admin's."""
    internal = {"roster_person_id", "matched", "match_method", "needs_review"}
    card = client.get(f"{API}/", headers=member_anna["headers"]).json()["items"][0]
    assert internal & set(card) == set()
    profile = client.get(f"{API}/anna-test", headers=member_anna["headers"]).json()
    assert internal & set(profile) == set()
    # The metadata itself lives under "review", and only an admin is given it.
    assert profile["review"] is None
    as_admin = client.get(f"{API}/anna-test", headers=admin_headers).json()
    assert as_admin["review"] == {"matched": False, "match_method": None, "needs_review": False}


def test_entry_intents_and_intent_search(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    h = member_anna["headers"]
    assert client.get(f"{API}/me/entry", headers=h).json() is None
    r = client.put(
        f"{API}/me/entry",
        json={
            "ask_me_about": "fundraising, B2B sales",
            "topics": ["fundraising"],
            "current_company": "Plato",
            "contact_preference": "email",
            "contact_email": "anna@plato.app",
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["ask_me_about"] == "fundraising, B2B sales"
    r = client.put(
        f"{API}/me/intents",
        json={"mentoring": True, "cofounding": True, "note": "pre-seed only"},
        headers=h,
    )
    assert r.status_code == 200 and r.json()["mentoring"] is True

    # entry topics are searchable, intents filter
    r = client.get(f"{API}/", params={"q": "fundraising"}, headers=member_ben["headers"])
    assert [m["slug"] for m in r.json()["items"]] == ["anna-test"]
    r = client.get(f"{API}/", params={"intent": ["mentoring"]}, headers=member_ben["headers"])
    assert r.json()["total"] == 1 and r.json()["items"][0]["intents"]["mentoring"] is True
    r = client.get(f"{API}/", params={"intent": ["hiring"]}, headers=member_ben["headers"])
    assert r.json()["total"] == 0
    # company override from entry is what the tile shows
    r = client.get(f"{API}/anna-test", headers=member_ben["headers"])
    assert r.json()["company"] == "Plato"

    # hidden entries are not shown to others
    client.put(f"{API}/me/entry", json={"visibility": "hidden"}, headers=h)
    assert client.get(f"{API}/anna-test", headers=member_ben["headers"]).json()["entry"] is None
    assert client.get(f"{API}/anna-test", headers=h).json()["entry"] is not None


def test_unbound_account_cannot_write_entry(client: TestClient) -> None:
    from tests.integration.conftest import auth

    r = client.put(f"{API}/me/entry", json={"about": "x"}, headers=auth("nobody@cdtm.com"))
    assert r.status_code == 403


def test_me_returns_the_signed_in_member(client: TestClient, member_anna: dict) -> None:
    """Was ``/community/me/member``; the profile of whoever is holding the token."""
    r = client.get(f"{API}/me", headers=member_anna["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["slug"] == "anna-test"
    # Own profile, so the e-mail is not redacted.
    assert r.json()["email"] == "anna.test@cdtm.com"


def test_ca_email_is_redacted_from_non_admin_non_self(
    client: TestClient, member_anna: dict, admin_headers: dict
) -> None:
    """A Center Assistant's inbox is a second e-mail on the same person; nulling only the
    top-level ``email`` and leaving ``ca.email`` reachable is the whole redaction defeated
    by one indirection. Attack: B (an ordinary member) opens a CA's profile."""
    ca_id = insert_member(
        "carla-ca",
        "Carla CA",
        email="carla.ca@cdtm.com",
        is_ca=True,
    )
    with _engine.begin() as conn:
        conn.execute(
            text(
                "insert into ca_details (member_id, alumni, about, responsibilities, "
                "research_fields, email) values (:id, false, 'about', '{}', '{}', :email)"
            ),
            {"id": ca_id, "email": "balowski@cdtm.com"},
        )

    r = client.get(f"{API}/carla-ca", headers=member_anna["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] is None
    assert body["ca"]["email"] is None, "CA e-mail leaked to a non-admin, non-self caller"

    # Self and admin still see it (mirrors the ordinary self/admin e-mail rule).
    r = client.get(f"{API}/carla-ca", headers=admin_headers)
    assert r.json()["ca"]["email"] == "balowski@cdtm.com"


def test_search_does_not_match_on_fields_withheld_from_the_caller(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """Attack: B searches for a token that appears only in a field never shown on the card
    or the profile (here: Anna's *hidden* entry). ``total`` must not confirm its presence."""
    h = member_anna["headers"]
    secret = "xyzzyprivatewordnotoncard"
    r = client.put(
        f"{API}/me/entry",
        json={"ask_me_about": secret, "visibility": "hidden"},
        headers=h,
    )
    assert r.status_code == 200, r.text

    r = client.get(f"{API}/", params={"q": secret}, headers=member_ben["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 0, "search leaked the presence of a withheld field (oracle)"

    # Confirm the profile itself withholds it too (10b), so this isn't just visible elsewhere.
    assert client.get(f"{API}/anna-test", headers=member_ben["headers"]).json()["entry"] is None


def test_needs_review_is_an_admin_filter(
    client: TestClient, member_anna: dict, admin_headers: dict
) -> None:
    """The flag is admin-only as a field, so it is admin-only as a filter too."""
    r = client.get(f"{API}/", params={"needs_review": "true"}, headers=member_anna["headers"])
    assert r.status_code == 403, r.text
    r = client.get(f"{API}/", params={"needs_review": "true"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    # Everyone can still list the directory; only that one filter is refused.
    assert client.get(f"{API}/", headers=member_anna["headers"]).status_code == 200
