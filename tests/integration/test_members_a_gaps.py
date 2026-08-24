"""Paging, batch caps and multi-intent questions, end to end against Postgres.

These cover behaviour the rest of the members and Ask suites never reach, because their
fixtures only ever insert one or two members: a page that is smaller than the match set,
and a question that names two intents at once.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.core.llm.rate_limit import ask_limiter
from tests.integration.conftest import auth, insert_member

pytestmark = pytest.mark.integration

API = "/api/v1/members"
ASK = "/api/v1/members/ask"


@pytest.fixture(autouse=True)
def _fresh_buckets():
    # The limiter is process-wide by design; tests must not inherit each other's spend.
    ask_limiter.reset()
    yield
    ask_limiter.reset()


def test_the_directory_hands_out_one_page_at_a_time(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    insert_member("cara-page", "Cara Page", "cara.page@cdtm.com")
    h = member_anna["headers"]

    first = client.get(f"{API}/", params={"limit": 1}, headers=h).json()
    second = client.get(f"{API}/", params={"limit": 1, "skip": 1}, headers=h).json()

    # The count is the whole directory; the page is the page that was asked for.
    assert first["total"] == second["total"] == 3
    assert len(first["items"]) == len(second["items"]) == 1
    assert first["items"][0]["slug"] != second["items"][0]["slug"]


def test_an_answer_is_paged_the_way_the_question_asked_for(client: TestClient) -> None:
    for i in range(3):
        insert_member(f"berliner-{i}", f"Berliner {i}", f"berliner-{i}@cdtm.com", location="Berlin")
    h = auth("berliner-0@cdtm.com")
    question = {"question": "people in Berlin", "limit": 1}

    first = client.post(f"{ASK}/", json=question, headers=h)
    assert first.status_code == 200, first.text
    second = client.post(f"{ASK}/", json={**question, "skip": 1}, headers=h)
    assert second.status_code == 200, second.text

    body, next_page = first.json(), second.json()
    assert body["total"] == next_page["total"] == 3
    assert len(body["members"]) == len(next_page["members"]) == 1
    assert body["members"][0]["slug"] != next_page["members"][0]["slug"]


def test_a_question_naming_two_intents_wants_one_person_who_does_both(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """Two intents in one question mean one person who does both, not the union."""
    assert (
        client.put(
            f"{API}/me/intents", json={"mentoring": True}, headers=member_anna["headers"]
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"{API}/me/intents",
            json={"mentoring": True, "investing": True},
            headers=member_ben["headers"],
        ).status_code
        == 200
    )

    r = client.post(
        f"{ASK}/",
        json={"question": "who is open to mentoring and investing"},
        headers=member_anna["headers"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["interpretation"]["filters"]["intents"] == ["mentoring", "investing"]
    assert [m["slug"] for m in body["members"]] == ["ben-test"]
    assert body["total"] == 1


def test_explain_reports_a_summary_language_it_cannot_write(
    client: TestClient, member_anna: dict
) -> None:
    """The preview shares the translator with ``ask``, so it shares its limits too."""
    r = client.post(
        f"{ASK}/explain",
        json={"question": "founders in Berlin", "language": "de"},
        headers=member_anna["headers"],
    )
    assert r.status_code == 200, r.text
    assert "summary language de" in r.json()["unresolved"]
    assert r.json()["filters"]["location"] == "Berlin"


def test_a_batch_longer_than_the_documented_cap_is_refused(
    client: TestClient, member_anna: dict
) -> None:
    """Both batch endpoints are a page's worth of rows, not an export."""
    h = member_anna["headers"]
    ids = [str(uuid.uuid4()) for _ in range(51)]
    assert client.get(f"{API}/lookup", params={"ids": ids}, headers=h).status_code == 422
    assert client.get(f"{API}/lookup", params={"ids": ids[:50]}, headers=h).status_code == 200

    names = [f"Company {i:02d}" for i in range(51)]
    assert client.get(f"{API}/at-company", params={"company": names}, headers=h).status_code == 422
    assert (
        client.get(f"{API}/at-company", params={"company": names[:50]}, headers=h).status_code
        == 200
    )
