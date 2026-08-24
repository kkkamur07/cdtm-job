"""The filters on the Sankey, the cards inside one of its boxes, and recomputing a path.

``test_paths.py`` draws the flow once, over two members, with no filter and with every card
field ignored. That leaves three things unverified end to end: the four query-string filters
(`class_id`, `study_group`, `first_step_group`, `current_group`), the accumulation of the
three career columns into one node list, and the whole recompute pipeline
(``CareerHistorySource`` -> classifier -> ``upsert``) that puts the rows there in the first
place, which has no route of its own and is run by ``scripts/platform/load_community.py``.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.core.settings import get_database_settings
from backend.paths.api.deps import build_path_service
from backend.paths.application.ports import PathFilters
from backend.paths.infrastructure.career_history import _BATCH
from tests.integration.conftest import _engine, insert_member

pytestmark = pytest.mark.integration
API = "/api/v1/paths"

#: Every card column with a value nothing else in a fixture shares, so a query that reads the
#: wrong column, or forgets one, cannot come back looking right.
CARD_COLUMNS = {
    "headline": "Building things at Plato",
    "avatar_sm_url": "https://cdn.example/adam-sm.webp",
    "avatar_lg_url": "https://cdn.example/adam-lg.webp",
    "avatar_blur": "data:image/webp;base64,adam-blur",
    "location": "Lisbon, Portugal",
    "class_label": "Fall 2019",
    "major": "Management & Technology",
    "current_company": "Plato",
    "current_title": "Co-Founder",
    "is_ca": True,
}


def _in_a_session(work: Any) -> Any:
    """Run ``work(session)`` on a throwaway engine of its own.

    The suite's ``client`` fixture owns a session-scoped event loop and an asyncpg pool bound
    to it, and a pool cannot be borrowed by a second loop. A test that needs to drive the
    recompute pipeline (which has no route) therefore brings its own engine and disposes of
    it again, exactly as the loader script does.
    """

    async def main():
        engine = create_async_engine(get_database_settings().async_url)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                return await work(session)
        finally:
            await engine.dispose()

    return asyncio.run(main())


def _member(
    slug: str,
    name: str,
    *,
    study: str | None = None,
    first_step: str | None = None,
    current: str | None = None,
    class_id: int | None = None,
    **columns,
) -> uuid.UUID:
    """A member, optionally with a computed path row and a class."""
    member_id = insert_member(slug, name, f"{slug}@cdtm.com", **columns)
    with _engine.begin() as conn:
        if (study, first_step, current) != (None, None, None):
            conn.execute(
                text(
                    "insert into member_paths "
                    "(member_id, study_group, first_step_group, current_group) "
                    "values (:m, :s, :f, :c)"
                ),
                {"m": member_id, "s": study, "f": first_step, "c": current},
            )
        if class_id is not None:
            conn.execute(
                text("insert into member_classes (member_id, class_id) values (:m, :c)"),
                {"m": member_id, "c": class_id},
            )
    return member_id


def _class(class_id: int, label: str, year: int, season: str) -> None:
    with _engine.begin() as conn:
        conn.execute(
            text("insert into classes (id, label, year, season) values (:i, :l, :y, :s)"),
            {"i": class_id, "l": label, "y": year, "s": season},
        )


def _position(
    member_id: uuid.UUID,
    title: str,
    company: str,
    start: date | None,
    *,
    current: bool = False,
    sort_order: int = 0,
) -> None:
    with _engine.begin() as conn:
        conn.execute(
            text(
                "insert into positions "
                "(id, member_id, title, company, start_date, is_current, sort_order) "
                "values (:i, :m, :t, :c, :d, :cur, :o)"
            ),
            {
                "i": uuid.uuid4(),
                "m": member_id,
                "t": title,
                "c": company,
                "d": start,
                "cur": current,
                "o": sort_order,
            },
        )


def _education(member_id: uuid.UUID, school: str, degree: str, sort_order: int = 0) -> None:
    with _engine.begin() as conn:
        conn.execute(
            text(
                "insert into educations (id, member_id, school, degree, sort_order) "
                "values (:i, :m, :s, :d, :o)"
            ),
            {"i": uuid.uuid4(), "m": member_id, "s": school, "d": degree, "o": sort_order},
        )


def _flow(client: TestClient, headers: dict, **params) -> dict:
    r = client.get(f"{API}/flow", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _members_in(client: TestClient, headers: dict, **params) -> dict:
    r = client.get(f"{API}/members", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _nodes(flow: dict, stage: str) -> list[tuple[str, int]]:
    return [(n["group"], n["count"]) for n in flow["nodes"] if n["stage"] == stage]


# ---- the picture ----------------------------------------------------------------------


def test_the_flow_draws_every_column_and_both_hops(client: TestClient, member_anna: dict) -> None:
    """Three career columns and two hops, accumulated: not just whichever was built last."""
    _member(
        "carl-test",
        "Carl Test",
        study="Computer Science",
        first_step="Consulting",
        current="Founder",
    )
    _member(
        "dana-test",
        "Dana Test",
        study="Computer Science",
        first_step="Consulting",
        current="Founder",
    )
    _member(
        "erik-test",
        "Erik Test",
        study="Business & Management",
        first_step="Big Tech",
        current="Consulting",
    )
    flow = _flow(client, member_anna["headers"])

    assert flow["members_counted"] == 3
    # Biggest box of each column first, and every column is drawn.
    assert _nodes(flow, "study") == [("Computer Science", 2), ("Business & Management", 1)]
    assert _nodes(flow, "first_step") == [("Consulting", 2), ("Big Tech", 1)]
    assert _nodes(flow, "current") == [("Founder", 2), ("Consulting", 1)]

    hops = [
        (link["source_stage"], link["source_group"], link["target_group"], link["count"])
        for link in flow["links"]
    ]
    assert hops[:2] == [
        ("study", "Computer Science", "Consulting", 2),
        ("study", "Business & Management", "Big Tech", 1),
    ]
    assert ("first_step", "Consulting", "Founder", 2) in hops
    assert ("first_step", "Big Tech", "Consulting", 1) in hops


def test_a_flow_over_nobody_counts_nobody(client: TestClient, member_anna: dict) -> None:
    flow = _flow(client, member_anna["headers"])
    assert flow["members_counted"] == 0
    assert flow["nodes"] == [] and flow["links"] == []


def test_the_intent_column_counts_every_intent_a_member_set(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """One member with two intents is two boxes, and the fattest flow out is drawn first."""
    ha, hb = member_anna["headers"], member_ben["headers"]
    with _engine.begin() as conn:
        conn.execute(
            text(
                "insert into member_paths (member_id, current_group) "
                "select id, 'Founder' from members where slug in ('anna-test', 'ben-test')"
            )
        )
    assert (
        client.put(
            "/api/v1/members/me/intents", json={"mentoring": True, "investing": True}, headers=ha
        ).status_code
        == 200
    )
    assert (
        client.put("/api/v1/members/me/intents", json={"investing": True}, headers=hb).status_code
        == 200
    )

    flow = _flow(client, ha)
    assert ("Investing", 2) in _nodes(flow, "intent")
    assert ("Mentoring", 1) in _nodes(flow, "intent")
    assert ("Not stated", 1) not in _nodes(flow, "intent")

    out = [
        (link["source_group"], link["target_group"], link["count"])
        for link in flow["links"]
        if link["target_stage"] == "intent"
    ]
    assert out == [("Founder", "Investing", 2), ("Founder", "Mentoring", 1)]


def test_the_group_lists_are_sorted(client: TestClient, member_anna: dict) -> None:
    """The chips are a sorted list of what the data actually contains, per column."""
    _member(
        "carl-test",
        "Carl Test",
        study="Engineering",
        first_step="Venture Capital",
        current="Founder",
    )
    _member(
        "dana-test",
        "Dana Test",
        study="Computer Science",
        first_step="Big Tech",
        current="Consulting",
    )

    groups = client.get(f"{API}/groups", headers=member_anna["headers"]).json()
    assert groups["study"] == ["Computer Science", "Engineering"]
    assert groups["first_step"] == ["Big Tech", "Venture Capital"]
    assert groups["current"] == ["Consulting", "Founder"]
    assert groups["intent"][0] == "Co-founding" and groups["intent"][-1] == "Not stated"


# ---- the four filters -----------------------------------------------------------------


@pytest.fixture
def four_paths(member_anna: dict) -> dict:
    """Three members alike and one unlike them in every one of the four filterable fields."""
    _class(1, "Fall 2019", 2019, "Fall")
    _class(2, "Fall 2021", 2021, "Fall")
    with _engine.begin() as conn:
        conn.execute(
            text(
                "insert into member_paths "
                "(member_id, study_group, first_step_group, current_group) "
                "select id, 'Computer Science', 'Consulting', 'Founder' "
                "from members where slug = 'anna-test'"
            )
        )
        conn.execute(
            text("insert into member_classes (member_id, class_id) values (:m, 1)"),
            {"m": member_anna["id"]},
        )
    _member(
        "ben-two",
        "Ben Two",
        study="Computer Science",
        first_step="Consulting",
        current="Founder",
        class_id=1,
    )
    _member(
        "carl-two",
        "Carl Two",
        study="Computer Science",
        first_step="Consulting",
        current="Founder",
        class_id=1,
    )
    dana = _member(
        "dana-two",
        "Dana Two",
        study="Business & Management",
        first_step="Big Tech",
        current="Consulting",
        class_id=2,
    )
    return {"headers": member_anna["headers"], "dana": dana}


#: (query parameter, the value three members share, the value only Dana has).
FILTERS = [
    ("class_id", 1, 2),
    ("study_group", "Computer Science", "Business & Management"),
    ("first_step_group", "Consulting", "Big Tech"),
    ("current_group", "Founder", "Consulting"),
]


def test_each_filter_narrows_the_flow(client: TestClient, four_paths: dict) -> None:
    h = four_paths["headers"]
    assert _flow(client, h)["members_counted"] == 4
    for name, many, one in FILTERS:
        assert _flow(client, h, **{name: many})["members_counted"] == 3, name
        assert _flow(client, h, **{name: one})["members_counted"] == 1, name
    # Filters compose, and a combination nobody satisfies is empty rather than ignored.
    assert _flow(client, h, class_id=2, current_group="Founder")["members_counted"] == 0
    assert _flow(client, h, class_id=1, study_group="Computer Science")["members_counted"] == 3


def test_each_filter_narrows_the_people_in_a_box(client: TestClient, four_paths: dict) -> None:
    h = four_paths["headers"]
    everyone = _members_in(client, h, stage="study", group="Computer Science")
    assert {m["slug"] for m in everyone["items"]} == {"anna-test", "ben-two", "carl-two"}

    for name, many, one in FILTERS:
        wide = _members_in(client, h, stage="study", group="Computer Science", **{name: many})
        narrow = _members_in(client, h, stage="study", group="Computer Science", **{name: one})
        assert wide["total"] == 3, name
        assert narrow["total"] == 0, name

    dana = _members_in(client, h, stage="current", group="Consulting", class_id=2)
    assert [m["slug"] for m in dana["items"]] == ["dana-two"]
    assert _members_in(client, h, stage="current", group="Consulting", class_id=1)["total"] == 0


# ---- the people in a box --------------------------------------------------------------


def test_a_box_opens_into_whole_cards_a_page_at_a_time(
    client: TestClient, member_anna: dict
) -> None:
    """Thirteen columns read by position, alphabetical, and paged."""
    _member("zoe-zeta", "Zoe Zeta", current="Founder")
    adam = _member("adam-alpha", "Adam Alpha", current="Founder", **CARD_COLUMNS)
    h = member_anna["headers"]

    first = _members_in(client, h, stage="current", group="Founder", limit=1)
    assert first["total"] == 2 and len(first["items"]) == 1
    assert first["items"][0] == {
        "id": str(adam),
        "slug": "adam-alpha",
        "name": "Adam Alpha",
        "headline": CARD_COLUMNS["headline"],
        "avatar_sm_url": CARD_COLUMNS["avatar_sm_url"],
        "avatar_lg_url": CARD_COLUMNS["avatar_lg_url"],
        "avatar_blur": CARD_COLUMNS["avatar_blur"],
        "location": CARD_COLUMNS["location"],
        "class_label": CARD_COLUMNS["class_label"],
        "major": CARD_COLUMNS["major"],
        "company": CARD_COLUMNS["current_company"],
        "title": CARD_COLUMNS["current_title"],
        "is_ca": True,
    }

    second = _members_in(client, h, stage="current", group="Founder", skip=1, limit=1)
    assert second["total"] == 2 and [m["slug"] for m in second["items"]] == ["zoe-zeta"]

    empty = _members_in(client, h, stage="current", group="Venture Capital")
    assert empty == {"items": [], "total": 0}


# ---- recompute: the pipeline that puts the rows there ---------------------------------


@pytest.fixture
def rita() -> uuid.UUID:
    """One member with the scrape rows a path is computed from.

    Two classes, so the earliest one has to be the one the first step is measured against; a
    CDTM degree ahead of the real one; a student job, an in-class job and a post-class job.
    """
    member_id = _member("rita-test", "Rita Test", major="Management & Technology")
    _class(1, "Fall 2019", 2019, "Fall")
    _class(2, "Fall 2021", 2021, "Fall")
    with _engine.begin() as conn:
        for class_id in (1, 2):
            conn.execute(
                text("insert into member_classes (member_id, class_id) values (:m, :c)"),
                {"m": member_id, "c": class_id},
            )
    _education(member_id, "CDTM", "Honours Degree in Technology Management", 0)
    _education(member_id, "TUM", "MSc Informatics", 1)
    _position(member_id, "Co-Founder", "Plato", date(2023, 8, 1), current=True, sort_order=0)
    _position(member_id, "Software Engineer", "Google", date(2021, 6, 1), sort_order=1)
    _position(member_id, "Associate", "McKinsey & Company", date(2020, 6, 1), sort_order=2)
    _position(member_id, "Working Student", "BMW", date(2019, 3, 1), sort_order=3)
    return member_id


def test_recompute_files_one_member_from_their_jobs_degrees_and_class(
    client: TestClient, member_anna: dict, rita: uuid.UUID
) -> None:
    """The whole read model, end to end: member tables -> classifier -> ``member_paths``."""

    async def work(session):
        return await build_path_service(session).recompute(rita)

    path = _in_a_session(work)
    assert path is not None
    assert path.member_id == rita
    # The roster major is read, and the CDTM honours degree everybody holds is not.
    assert path.study_group == "Business & Management"
    # Earliest class is Fall 2019, so the class ended in March 2021: BMW is a student job,
    # McKinsey started while the class was still running, Google is the first step after it.
    assert path.first_step_company == "Google"
    assert path.first_step_title == "Software Engineer"
    assert path.first_step_group == "Big Tech"
    assert path.current_company == "Plato"
    assert path.current_title == "Co-Founder"
    assert path.current_group == "Founder"

    # And it was written, not just computed: the board can read it back.
    stored = client.get(f"{API}/members/rita-test", headers=member_anna["headers"])
    assert stored.status_code == 200, stored.text
    assert stored.json()["first_step_company"] == "Google"
    assert stored.json()["current_group"] == "Founder"
    assert stored.json()["computed_at"] is not None


def test_recomputing_the_same_member_rewrites_their_one_row(
    client: TestClient, member_anna: dict, rita: uuid.UUID
) -> None:
    """A recompute is a full pass, so it has to update in place rather than pile up rows."""

    async def first(session):
        return await build_path_service(session).recompute(rita)

    _in_a_session(first)
    with _engine.begin() as conn:
        conn.execute(
            text("update members set major = 'Mechanical Engineering' where id = :i"), {"i": rita}
        )
        conn.execute(
            text("update positions set is_current = false where member_id = :i"), {"i": rita}
        )

    async def again(session):
        return await build_path_service(session).recompute(rita)

    path = _in_a_session(again)
    assert path.study_group == "Engineering"
    assert path.current_group is None and path.current_company is None

    with _engine.begin() as conn:
        rows = conn.execute(text("select count(*) from member_paths")).scalar()
    assert rows == 1
    assert (
        client.get(f"{API}/members/rita-test", headers=member_anna["headers"]).json()["study_group"]
        == "Engineering"
    )


def test_recomputing_a_member_who_is_not_there_files_nobody(client: TestClient) -> None:
    async def work(session):
        return await build_path_service(session).recompute(uuid.uuid4())

    assert _in_a_session(work) is None
    with _engine.begin() as conn:
        assert conn.execute(text("select count(*) from member_paths")).scalar() == 0


def test_recompute_all_files_everybody_including_people_with_no_scrape(
    client: TestClient, member_anna: dict, rita: uuid.UUID
) -> None:
    """The loader's full pass: everybody gets a row, even somebody with no jobs at all."""
    empty = _member("nils-test", "Nils Test")

    async def work(session):
        service = build_path_service(session)
        return await service.recompute_all()

    assert _in_a_session(work) == 3  # anna, rita, nils

    flow = _flow(client, member_anna["headers"])
    assert flow["members_counted"] == 3
    assert ("Founder", 1) in _nodes(flow, "current")

    # The batch reader has to read the roster major too, or every field of study comes out
    # of a degree instead: Rita's says Informatics, her major says Management & Technology.
    rita_row = client.get(f"{API}/members/rita-test", headers=member_anna["headers"]).json()
    assert rita_row["study_group"] == "Business & Management"

    r = client.get(f"{API}/members/nils-test", headers=member_anna["headers"])
    assert r.status_code == 200, r.text
    assert r.json() == {
        "member_id": str(empty),
        "study_group": None,
        "first_step_group": None,
        "first_step_title": None,
        "first_step_company": None,
        "current_group": None,
        "current_title": None,
        "current_company": None,
        "computed_at": r.json()["computed_at"],
    }
    assert r.json()["computed_at"] is not None


def test_the_flow_can_be_narrowed_to_a_named_set_of_members_and_the_asker_placed(
    client: TestClient, member_anna: dict
) -> None:
    """The two things the directory's Ask asks of this context, neither of which has a route.

    Ask draws the Sankey over every member its question matched (``PathFilters.member_ids``)
    and asks which box the person asking is standing in (``ViewerGroupSource``).
    """
    ben = _member("ben-two", "Ben Two", current="Consulting")
    with _engine.begin() as conn:
        conn.execute(
            text(
                "insert into member_paths (member_id, current_group) "
                "select id, 'Founder' from members where slug = 'anna-test'"
            )
        )
    anna = member_anna["id"]

    async def work(session):
        service = build_path_service(session)
        return (
            (await service.flow(PathFilters())).members_counted,
            (await service.flow(PathFilters(member_ids=()))).members_counted,
            (await service.flow(PathFilters(member_ids=(anna,)))).members_counted,
            await service.current_group_of(anna),
            await service.current_group_of(ben),
            await service.current_group_of(uuid.uuid4()),
        )

    everyone, nobody, just_anna, anna_group, ben_group, stranger = _in_a_session(work)
    assert everyone == 2
    # An empty set of ids is a real answer ("nobody matched"), not "no filter".
    assert nobody == 0
    assert just_anna == 1
    assert anna_group == "Founder"
    assert ben_group == "Consulting"
    assert stranger is None


def test_recompute_reads_a_degree_a_school_and_the_order_of_positions(
    client: TestClient, member_anna: dict
) -> None:
    """The three columns of a scraped row that a path is actually decided by.

    A degree line can carry the field of study in either half (``MSc Informatics`` at an
    unremarkable school, ``Diplom`` at a physics institute), and positions are read in the
    order the scrape put them in, which is what decides who wins between two current roles
    the classifier can name.
    """
    sara = _member("sara-test", "Sara Test")
    _education(sara, "Foo University", "MSc Informatics")
    tomas = _member("tomas-test", "Tomas Test")
    _education(tomas, "Munich Physics Institute", "Diplom")

    vera = _member("vera-test", "Vera Test")
    # Written in the opposite order to the one they are ranked in, so reading them unordered
    # gives a different answer from reading them by ``sort_order``.
    _position(vera, "Associate", "McKinsey & Company", date(2020, 1, 1), current=True, sort_order=1)
    _position(vera, "Co-Founder", "Plato", date(2022, 1, 1), current=True, sort_order=0)

    async def work(session):
        return await build_path_service(session).recompute_all()

    assert _in_a_session(work) == 4  # anna, sara, tomas, vera

    def path(slug: str) -> dict:
        r = client.get(f"{API}/members/{slug}", headers=member_anna["headers"])
        assert r.status_code == 200, r.text
        return r.json()

    assert path("sara-test")["study_group"] == "Computer Science"
    assert path("tomas-test")["study_group"] == "Natural Sciences & Math"

    v = path("vera-test")
    assert v["current_company"] == "Plato" and v["current_group"] == "Founder"
    # The first step is the earliest job by date, whatever order the scrape listed them in.
    assert v["first_step_company"] == "McKinsey & Company"
    assert v["first_step_group"] == "Consulting"


def test_recompute_all_reads_past_the_first_batch(client: TestClient) -> None:
    """``iter_all`` pages with a keyset cursor, and the directory is bigger than one page.

    A cursor that matches nothing on the second call looks perfectly healthy while the test
    fixtures hold three people, and silently files only the first two hundred in production.
    """
    total = _BATCH + 5
    with _engine.begin() as conn:
        conn.execute(
            text(
                "insert into members (id, slug, name, email, search_text, roles) "
                "select gen_random_uuid(), 'crowd-' || i, 'Crowd ' || i, "
                "'crowd' || i || '@cdtm.com', 'crowd', '{}' "
                "from generate_series(1, :n) as i"
            ),
            {"n": total},
        )

    async def work(session):
        return await build_path_service(session).recompute_all()

    assert _in_a_session(work) == total
    with _engine.begin() as conn:
        assert conn.execute(text("select count(*) from member_paths")).scalar() == total
