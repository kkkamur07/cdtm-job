"""Ask over the housing board, end to end.

``test_ask.py`` covers that a housing question reaches the board at all. This file covers
what the answer is allowed to contain: only listings that are on the board, only listings
that match every filter the question was read as, and only one page of them. The last two
tests are the only place in the suite where a model is configured at all, through a fake
completer standing in for the provider.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.core.exceptions import LlmUnavailableError
from backend.core.llm.ask import LLM_DOWN_NOTE
from backend.core.llm.rate_limit import ask_limiter
from backend.core.settings import reset_settings_caches
from tests.integration.conftest import _engine

pytestmark = pytest.mark.integration

HOUSING = "/api/v1/housing"
ASK = f"{HOUSING}/ask"

#: Reads as one question with every rule in it, so a filter that stops being applied shows
#: up as a listing that should not have been in the answer.
FULL_QUESTION = (
    "offering a furnished 2 room flat in Schwabing, Munich, over 500, under 900, "
    "from October, until December"
)


@pytest.fixture(autouse=True)
def _fresh_buckets():
    # The in-process limiter is the fallback meter and is process-wide by design.
    ask_limiter.reset()
    yield
    ask_limiter.reset()


def _listing(client: TestClient, headers: dict, **body) -> dict:
    payload = {"kind": "offer", "title": "Room in Schwabing", "city": "Munich"} | body
    r = client.post(f"{HOUSING}/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _ask(client: TestClient, headers: dict, question: str, **body) -> dict:
    r = client.post(f"{ASK}/", json={"question": question} | body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _ids(answer: dict) -> list[str]:
    return [listing["id"] for listing in answer["listings"]]


# ---- what an answer may contain --------------------------------------------------------------


def test_an_answer_only_ever_holds_listings_that_are_on_the_board(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """Ask goes to the repository with its own filters rather than through the board's list,
    so "open, not expired" has to be part of the question it asks, or a closed room keeps
    answering long after it went."""
    ha = member_anna["headers"]
    on_the_board = _listing(client, ha, title="Room in Schwabing", area="Schwabing")
    closed = _listing(client, ha, title="Room in Schwabing", area="Schwabing")
    client.patch(f"{HOUSING}/{closed['id']}", json={"status": "closed"}, headers=ha)
    expired = _listing(client, ha, title="Room in Schwabing", area="Schwabing")
    with _engine.begin() as conn:
        conn.execute(
            text("update housing_listings set expires_at = now() - interval '1 day' where id = :i"),
            {"i": expired["id"]},
        )

    for headers in (member_ben["headers"], ha):
        answer = _ask(client, headers, "room in Schwabing")
        assert _ids(answer) == [on_the_board["id"]]
        assert answer["total"] == 1


def test_an_answer_holds_only_what_matches_every_filter_the_question_was_read_as(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """One listing that matches the whole question, and one for every clause in it that
    matches everything except that clause."""
    ha = member_anna["headers"]
    read = client.post(f"{ASK}/explain", json={"question": FULL_QUESTION}, headers=ha).json()
    filters = read["filters"]
    free_from = date.fromisoformat(filters["available_from"])
    free_until = date.fromisoformat(filters["available_until"])
    match = {
        "kind": "offer",
        "title": "Room in Schwabing",
        "city": "Munich",
        "area": "Schwabing",
        "price_eur": 780,
        "rooms": 2,
        "furnished": True,
        # Exactly on both ends of the window the question asked for: a room free from the
        # first of the month is free "from October".
        "available_from": free_from.isoformat(),
        "available_until": free_until.isoformat(),
    }
    wanted = _listing(client, ha, **match)
    for missing in (
        {"kind": "looking"},
        {"area": "Kreuzberg"},
        {"city": "Berlin"},
        {"price_eur": 400},
        {"price_eur": 1400},
        {"rooms": 1},
        {"furnished": False},
        {"available_from": (free_from + timedelta(days=1)).isoformat()},
        {"available_until": (free_until - timedelta(days=1)).isoformat()},
    ):
        _listing(client, ha, **(match | missing))

    answer = _ask(client, member_ben["headers"], FULL_QUESTION)
    assert _ids(answer) == [wanted["id"]]
    assert answer["total"] == 1


def test_both_ends_of_a_price_range_are_included(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """ "Between 500 and 900" is an answer a member has to be able to trust at the edges."""
    ha = member_anna["headers"]
    floor = _listing(client, ha, title="Room at the floor", price_eur=500)
    ceiling = _listing(client, ha, title="Room at the ceiling", price_eur=900)
    _listing(client, ha, title="A euro too cheap", price_eur=499)
    _listing(client, ha, title="A euro too dear", price_eur=901)

    answer = _ask(client, member_ben["headers"], "flat over 500, under 900")
    assert set(_ids(answer)) == {floor["id"], ceiling["id"]}
    assert answer["total"] == 2


def test_a_room_with_exactly_the_number_of_rooms_asked_for_counts(
    client: TestClient, member_anna: dict
) -> None:
    ha = member_anna["headers"]
    exactly = _listing(client, ha, title="Two rooms", rooms=2)
    _listing(client, ha, title="One room", rooms=1)

    assert _ids(_ask(client, ha, "2 room flat")) == [exactly["id"]]


def test_a_phrase_the_board_does_not_know_becomes_a_search_of_the_whole_listing(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """ "Alte Heide" is a real corner of Munich and not one of the districts the keyword
    translator knows, so it has to reach the title, the description and the area alike."""
    ha = member_anna["headers"]
    in_title = _listing(client, ha, title="Room near Alte Heide")
    in_description = _listing(
        client, ha, title="Bright room", description="Two stops from alte heide."
    )
    in_area = _listing(client, ha, title="Quiet room", area="Alte Heide")
    _listing(client, ha, title="Room in Giesing", description="Near the river.", area="Giesing")

    answer = _ask(client, member_ben["headers"], "flat, alte heide")
    assert set(_ids(answer)) == {in_title["id"], in_description["id"], in_area["id"]}
    assert answer["total"] == 3


def test_an_answer_comes_one_page_at_a_time(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    ha = member_anna["headers"]
    for title in ("First room", "Second room", "Third room"):
        _listing(client, ha, title=title, area="Schwabing")

    seen = []
    for offset in range(3):
        page = _ask(client, member_ben["headers"], "room in Schwabing", skip=offset, limit=1)
        assert len(page["listings"]) == 1
        # The count is the whole answer, not the page of it that came back.
        assert page["total"] == 3
        seen += _ids(page)
    assert len(set(seen)) == 3


def test_explaining_a_question_reads_it_without_searching_the_board(
    client: TestClient, member_anna: dict
) -> None:
    _listing(client, member_anna["headers"], title="Room in Schwabing", area="Schwabing")
    r = client.post(
        f"{ASK}/explain",
        json={"question": "room in Schwabing under 900"},
        headers=member_anna["headers"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["filters"]["district"] == "Schwabing"
    assert body["filters"]["max_price"] == 900
    assert body["source"] == "rules"
    assert "listings" not in body

    # The preview is answered in the language the caller asked for, or says why not.
    r = client.post(
        f"{ASK}/explain",
        json={"question": "room in Schwabing", "language": "de"},
        headers=member_anna["headers"],
    )
    assert "summary language de" in r.json()["unresolved"]


def test_a_summary_language_the_keywords_cannot_write_is_reported(
    client: TestClient, member_anna: dict
) -> None:
    answer = _ask(client, member_anna["headers"], "room in Schwabing", language="de")
    assert "summary language de" in answer["interpretation"]["unresolved"]
    assert answer["interpretation"]["filters"]["district"] == "Schwabing"


def test_one_members_questions_do_not_spend_another_members_allowance(
    client: TestClient, member_anna: dict, member_ben: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The allowance is one bucket per member. If the key ever stopped naming the member,
    the first person to ask twice would rate-limit the whole community."""
    monkeypatch.setenv("LLM_MAX_QUESTIONS_PER_MINUTE", "1")
    reset_settings_caches()
    body = {"question": "room in Schwabing"}
    ha, hb = member_anna["headers"], member_ben["headers"]

    assert client.post(f"{ASK}/", json=body, headers=ha).status_code == 200
    assert client.post(f"{ASK}/", json=body, headers=ha).status_code == 429
    assert client.post(f"{ASK}/", json=body, headers=hb).status_code == 200
    assert client.post(f"{ASK}/explain", json=body, headers=hb).status_code == 429


# ---- with a model configured -------------------------------------------------------------------


class FakeCompleter:
    """Stands in for a provider. Reads the question back as a free-text filter so a test can
    tell what the model was actually asked."""

    model = "fake-model-1"

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    async def complete_json(self, *, system: str, user: str, schema: dict, schema_name: str):
        self.calls.append({"system": system, "user": user})
        if self.error is not None:
            raise self.error
        return {
            "summary": f"Reading your question as: {user}",
            "filters": {"kind": "offer", "q": user},
            "confidence": 0.77,
            "unresolved": [],
        }


def _with_completer(monkeypatch: pytest.MonkeyPatch, completer: FakeCompleter) -> FakeCompleter:
    monkeypatch.setattr(
        "backend.housing.api.deps.get_structured_completer", lambda: completer, raising=True
    )
    return completer


def test_when_a_model_is_configured_it_is_the_one_reading_the_question(
    client: TestClient, member_anna: dict, member_ben: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    completer = _with_completer(monkeypatch, FakeCompleter())
    ha = member_anna["headers"]
    wanted = _listing(client, ha, title="Room with a Bogenhausen view")
    _listing(client, ha, title="Room in Giesing")

    answer = _ask(client, member_ben["headers"], "bogenhausen view", language="pt-BR")

    interpretation = answer["interpretation"]
    assert interpretation["source"] == "llm"
    assert interpretation["summary"] == "Reading your question as: bogenhausen view"
    assert interpretation["filters"]["q"] == "bogenhausen view"
    assert interpretation["confidence"] == 0.77
    # The model read the question, and was told which language to answer in.
    assert completer.calls[0]["user"] == "bogenhausen view"
    assert "pt-BR" in completer.calls[0]["system"]
    # And its filters are what the board was actually searched with.
    assert _ids(answer) == [wanted["id"]]


def test_when_the_model_is_unreachable_the_keywords_answer_and_say_so(
    client: TestClient, member_anna: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    _with_completer(monkeypatch, FakeCompleter(LlmUnavailableError("provider unreachable")))
    ha = member_anna["headers"]
    wanted = _listing(client, ha, title="Room in Schwabing", area="Schwabing")
    _listing(client, ha, title="Room in Giesing", area="Giesing")

    answer = _ask(client, ha, "room in Schwabing", language="de")

    interpretation = answer["interpretation"]
    assert interpretation["source"] == "rules"
    assert LLM_DOWN_NOTE in interpretation["unresolved"]
    # The rest of the question was still read, in the language it was asked about.
    assert interpretation["filters"]["district"] == "Schwabing"
    assert "summary language de" in interpretation["unresolved"]
    assert _ids(answer) == [wanted["id"]]


def test_the_question_log_names_the_model_that_read_it(
    client: TestClient,
    member_anna: dict,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One line per question is how the prompt gets tuned and how a spend is accounted for,
    so it has to say which model answered even when nothing was searched."""
    _with_completer(monkeypatch, FakeCompleter())
    with caplog.at_level(logging.INFO, logger="backend.ask"):
        r = client.post(
            f"{ASK}/explain", json={"question": "room in Giesing"}, headers=member_anna["headers"]
        )
    assert r.status_code == 200, r.text
    line = next(rec.getMessage() for rec in caplog.records if rec.name == "backend.ask")
    assert "model=fake-model-1" in line
    assert "source=llm" in line
    # Explaining searched nothing, so there is no count to report.
    assert "total=-" in line
