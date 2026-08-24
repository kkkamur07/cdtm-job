"""What a list route ships, and what only a detail route ships.

Three boards return rows built out of an aggregate whose longest field is free text: a job
description, a housing description, an event description. ``MAX_RICH_TEXT`` is 20,000
characters, the page size is 100, and nothing in any list UI draws any of it, so the list
routes answer with a summary and the by-id, by-slug, create and update routes answer with
the whole aggregate. These tests hold that line from the outside: a summary that quietly
grew the description back, or a detail route that quietly lost it, fails here.

``tests/unit/test_list_summary_dtos.py`` is the other half: it pins the summary's field
set against the aggregate's, so a new field cannot slip past unnoticed either way.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.core.llm.rate_limit import ask_limiter

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _fresh_buckets():
    # The Ask limiter is process-wide by design; tests must not inherit each other's spend.
    ask_limiter.reset()
    yield
    ask_limiter.reset()


LONG = "A paragraph nothing in a list ever draws. " * 20

#: What ``GET /jobs/`` must not carry. The description is the expensive one; the three
#: keyword lists are only read on the detail page next to it.
JOB_OMITS = ("description", "must_have_skills", "nice_to_have_skills", "languages")


def _published_job(client: TestClient, headers: dict) -> dict:
    company = client.post(
        "/api/v1/companies/", json={"name": "ACME", "slug": "summary-acme"}, headers=headers
    )
    assert company.status_code == 201, company.text
    created = client.post(
        "/api/v1/jobs/",
        json={
            "company_id": company.json()["id"],
            "title": "Founding Engineer",
            "slug": "summary-founding-engineer",
            "description": LONG,
            "employment_type": "full_time",
            "work_arrangement": "remote",
            "experience_level": "mid",
            "status": "published",
            "must_have_skills": ["Python"],
            "nice_to_have_skills": ["SQLAlchemy"],
            "languages": ["en"],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_the_jobs_list_leaves_out_the_description_and_the_keyword_lists(
    client: TestClient, member_anna: dict
) -> None:
    job = _published_job(client, member_anna["headers"])

    row = client.get("/api/v1/jobs/", params={"status": "published"}).json()["items"][0]
    assert row["id"] == job["id"]
    for field in JOB_OMITS:
        assert field not in row
    # The row is still a row: everything the board draws is on it.
    assert row["title"] == "Founding Engineer"
    assert (row["employment_type"], row["work_arrangement"]) == ("full_time", "remote")
    assert row["published_at"] is not None


def test_a_job_read_on_its_own_still_carries_everything(
    client: TestClient, member_anna: dict
) -> None:
    job = _published_job(client, member_anna["headers"])

    for path in (f"/api/v1/jobs/{job['id']}", "/api/v1/jobs/slug/summary-founding-engineer"):
        body = client.get(path).json()
        assert body["description"] == LONG, path
        assert body["must_have_skills"] == ["Python"], path
        assert body["nice_to_have_skills"] == ["SQLAlchemy"], path
        assert body["languages"] == ["en"], path

    # Create and update answer with the aggregate too, so a form reads back what it sent.
    assert job["description"] == LONG
    patched = client.patch(
        f"/api/v1/jobs/{job['id']}", json={"title": "Renamed"}, headers=member_anna["headers"]
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["description"] == LONG


def test_the_jobs_ask_answer_ships_rows_rather_than_whole_postings(
    client: TestClient, member_anna: dict
) -> None:
    """The browser intersects the answer with the board by id, so rows are all it needs."""
    _published_job(client, member_anna["headers"])
    r = client.post(
        "/api/v1/jobs/ask/",
        json={"question": "founding engineer roles that are remote"},
        headers=member_anna["headers"],
    )
    assert r.status_code == 200, r.text
    for job in r.json()["jobs"]:
        for field in JOB_OMITS:
            assert field not in job


def test_the_housing_board_leaves_out_the_description_and_the_listing_keeps_it(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    created = client.post(
        "/api/v1/housing/",
        json={
            "kind": "offer",
            "title": "Room in Maxvorstadt",
            "city": "Munich",
            "description": LONG,
            "photo_urls": ["housing/one.webp"],
        },
        headers=member_anna["headers"],
    )
    assert created.status_code == 201, created.text
    listing = created.json()
    assert listing["description"] == LONG

    row = client.get("/api/v1/housing/", headers=member_ben["headers"]).json()["items"][0]
    assert "description" not in row
    # The card draws the photo, the city and the kind, and those are all still there.
    assert row["photo_urls"] == ["housing/one.webp"]
    assert (row["city"], row["kind"]) == ("Munich", "offer")

    opened = client.get(f"/api/v1/housing/{listing['id']}", headers=member_ben["headers"]).json()
    assert opened["description"] == LONG


def test_the_housing_ask_answer_ships_cards_rather_than_whole_listings(
    client: TestClient, member_anna: dict
) -> None:
    client.post(
        "/api/v1/housing/",
        json={"kind": "offer", "title": "Room in Munich", "city": "Munich", "description": LONG},
        headers=member_anna["headers"],
    )
    r = client.post(
        "/api/v1/housing/ask/",
        json={"question": "a room in Munich"},
        headers=member_anna["headers"],
    )
    assert r.status_code == 200, r.text
    for card in r.json()["listings"]:
        assert "description" not in card


def test_the_events_list_leaves_out_the_description_and_the_event_keeps_it(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    starts = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    created = client.post(
        "/api/v1/events/",
        json={
            "title": "Stammtisch",
            "starts_at": starts,
            "location": "Munich",
            "description": LONG,
        },
        headers=member_anna["headers"],
    )
    assert created.status_code == 201, created.text
    event = created.json()
    assert event["description"] == LONG

    row = client.get("/api/v1/events/", headers=member_ben["headers"]).json()["items"][0]
    assert "description" not in row
    assert (row["title"], row["location"]) == ("Stammtisch", "Munich")
    assert row["going_count"] == 0

    opened = client.get(f"/api/v1/events/{event['id']}", headers=member_ben["headers"]).json()
    assert opened["description"] == LONG
    # An RSVP answers with the whole event, because the browser writes it into its cache.
    rsvp = client.put(
        f"/api/v1/events/{event['id']}/rsvp",
        json={"status": "going"},
        headers=member_ben["headers"],
    )
    assert rsvp.status_code == 200, rsvp.text
    assert rsvp.json()["description"] == LONG


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/v1/jobs/", {"status": "published"}),
        ("/api/v1/housing/", {}),
        ("/api/v1/events/", {}),
    ],
)
def test_every_board_still_answers_with_an_items_and_total_envelope(
    client: TestClient, member_anna: dict, path: str, params: dict
) -> None:
    body = client.get(path, params=params, headers=member_anna["headers"]).json()
    assert set(body) == {"items", "total"}
    assert body["total"] == 0 and body["items"] == []
