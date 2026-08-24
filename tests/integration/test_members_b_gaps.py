"""The member directory against real Postgres: filters, ordering, mapping and the loader.

The directory endpoint only offers a dozen of the filters ``MemberFilters`` describes; the
rest reach the same WHERE clause through Ask and through the Paths cohort. They are all one
function, so they are all exercised here against the repository that owns it, with members
put in through the same loader ``scripts/platform/load_community.py`` uses.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.core.settings import get_database_settings
from backend.members.application.commands import (
    ClassImport,
    EntryUpsert,
    IntentsUpsert,
    MemberImport,
)
from backend.members.application.import_service import ImportService
from backend.members.application.ports import MemberFilters
from backend.members.domain import CaDetail, Education, MatchMethod, Position, Role
from backend.members.infrastructure.entries_repository import SqlEntryRepository
from backend.members.infrastructure.members_repository import SqlMemberRepository
from tests.integration.conftest import _engine, insert_member

pytestmark = pytest.mark.integration
API = "/api/v1/members"

SYNCED_AT = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
async def session():
    """A session on the same local Postgres the app uses, in this test's event loop.

    The app's engine belongs to the session-scoped ``client`` fixture's loop, so a test
    that talks to a repository directly opens its own and disposes of it again.
    """
    engine = create_async_engine(get_database_settings().async_url)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with factory() as s:
            yield s
    finally:
        await engine.dispose()


@pytest.fixture
def members(session) -> SqlMemberRepository:
    return SqlMemberRepository(session)


def _member(slug: str, name: str, **overrides) -> MemberImport:
    payload = {"slug": slug, "name": name}
    payload.update(overrides)
    return MemberImport(**payload)


# ---- one imported directory, used by the filter, ordering and mapping tests --------------


@pytest.fixture
async def directory(members: SqlMemberRepository, session) -> dict[str, uuid.UUID]:
    """Three members loaded through the importer, plus an entry, intents, paths and an
    account, so every predicate in ``apply_member_filters`` has something to select on."""
    await members.upsert_classes(
        [
            ClassImport(id=17, label="Fall 2020", season="fall", year=2020, location=1),
            ClassImport(id=23, label="Spring 2023", season="spring", year=2023, location=2),
        ]
    )
    ada = await members.upsert_member(
        _member(
            "ada-mut",
            "Ada Filter",
            roster_person_id=101,
            first_name="Ada",
            last_name="Filter",
            roster_name="Filter, Ada",
            email="Ada.Filter@CDTM.com",
            headline="Head of Product at Plato Labs",
            summary="Two sentences about Ada.",
            location="Munich",
            linkedin_url="https://linkedin.com/in/ada",
            avatar_sm_url="https://cdn.test/ada-sm.webp",
            avatar_lg_url="https://cdn.test/ada.webp",
            avatar_blur="data:image/webp;base64,blur",
            class_ids=[17, 17],
            class_label="Fall 2020",
            major="Business Administration",
            roles=[Role.STUDENT],
            matched=True,
            match_method=MatchMethod.EXACT,
            current_company="Plato Labs",
            current_title="Head of Product",
            skills=["python", "sql"],
            languages=["german"],
            company_info={"name": "Plato Labs", "industry": "Software"},
            positions=[Position(company="Old Bank", title="Analyst", is_current=False)],
            educations=[Education(school="Stanford", degree="Computer Science")],
            linkedin_synced_at=SYNCED_AT,
        )
    )
    ben = await members.upsert_member(
        _member(
            "ben-mut",
            "Ben Filter",
            roster_person_id=102,
            location="Berlin",
            class_ids=[23],
            class_label="Spring 2023",
            major="Business",
            roles=[Role.CA],
            is_ca=True,
            ca_alumni=True,
            needs_review=True,
            current_company="Zeta GmbH",
            current_title="Designer",
            skills=["figma"],
            languages=["french"],
            ca=CaDetail(alumni=True, about="ran marketing", email="ben.ca@cdtm.com"),
            positions=[Position(company="New Shop", title="Intern", is_current=True)],
            educations=[Education(school="Oxford", degree="Philosophy")],
        )
    )
    cid = await members.upsert_member(_member("cid-mut", "Cid Filter"))

    entries = SqlEntryRepository(session)
    await entries.upsert(
        ada,
        EntryUpsert(
            ask_me_about="fundraising and b2b sales",
            current_company="Ariadne Ventures",
            current_title="Founder",
            location="Garching",
            topics=["fundraising"],
            hobbies=["climbing"],
            contact_preference="email",
            contact_email="ada@plato.app",
        ),
    )
    await entries.upsert_intents(ada, IntentsUpsert(cofounding=True, mentoring=True))
    await entries.upsert_intents(ben, IntentsUpsert(mentoring=True))

    with _engine.begin() as conn:
        conn.execute(
            text(
                "insert into member_paths (member_id, study_group, first_step_group, "
                "current_group) values (:id, 'Computer Science', 'Consulting', 'Founder')"
            ),
            {"id": ada},
        )
        conn.execute(
            text(
                "insert into accounts (auth_user_id, email, member_id) "
                "values (gen_random_uuid(), 'ada.account@cdtm.com', :id)"
            ),
            {"id": ada},
        )
    return {"ada-mut": ada, "ben-mut": ben, "cid-mut": cid}


#: (what is being asked for, the filters, the slugs that answer it).
FILTER_CASES: list[tuple[str, dict, set[str]]] = [
    ("free text over the haystack", {"q": "plato"}, {"ada-mut"}),
    ("free text is trimmed before matching", {"q": "   fundraising  "}, {"ada-mut"}),
    ("free text that matches nobody", {"q": "nobody-writes-this"}, set()),
    ("one class", {"class_id": 17}, {"ada-mut"}),
    ("the other class", {"class_id": 23}, {"ben-mut"}),
    ("a class label is exact", {"class_label": "Spring 2023"}, {"ben-mut"}),
    ("class years from", {"class_year_min": 2021}, {"ben-mut"}),
    ("class years to", {"class_year_max": 2021}, {"ada-mut"}),
    ("a class year range", {"class_year_min": 2020, "class_year_max": 2020}, {"ada-mut"}),
    ("a major is exact, not a substring", {"major": "Business"}, {"ben-mut"}),
    ("the longer major", {"major": "Business Administration"}, {"ada-mut"}),
    ("one role", {"role": "ca"}, {"ben-mut"}),
    ("any of several roles", {"roles": ("student", "faculty")}, {"ada-mut"}),
    ("a location, case-insensitive substring", {"location": "muni"}, {"ada-mut"}),
    ("the current company", {"company": "plato"}, {"ada-mut"}),
    ("a company only the haystack knows", {"company": "Ariadne"}, {"ada-mut"}),
    ("a company nobody works at", {"company": "Nobody Inc"}, set()),
    ("a past employer", {"past_company": "Old Bank"}, {"ada-mut"}),
    ("the other past employer", {"past_company": "shop"}, {"ben-mut"}),
    ("a current job title", {"title": "designer"}, {"ben-mut"}),
    ("a title held in a past job", {"title": "Analyst"}, {"ada-mut"}),
    ("a school", {"school": "stanford"}, {"ada-mut"}),
    ("a degree", {"degree": "philos"}, {"ben-mut"}),
    ("what they studied", {"study_group": "Computer Science"}, {"ada-mut"}),
    ("a study group nobody is in", {"study_group": "Engineering"}, set()),
    ("the first step after CDTM", {"first_step_group": "Consulting"}, {"ada-mut"}),
    ("where they are now", {"current_group": "Founder"}, {"ada-mut"}),
    ("center assistants", {"is_ca": True}, {"ben-mut"}),
    ("everybody else", {"is_ca": False}, {"ada-mut", "cid-mut"}),
    ("rows the loader was unsure about", {"needs_review": True}, {"ben-mut"}),
    ("rows the loader was sure about", {"needs_review": False}, {"ada-mut", "cid-mut"}),
    ("a skill", {"skills": ("python",)}, {"ada-mut"}),
    # A translator emits skills lowercased ("machine learning"); the stored value is often
    # title-cased ("Machine Learning"). The match must not care, or Ask silently returns zero.
    ("a skill, whatever the case", {"skills": ("PyThOn",)}, {"ada-mut"}),
    ("any of several skills", {"skills": ("figma", "python")}, {"ada-mut", "ben-mut"}),
    ("a language", {"languages": ("french",)}, {"ben-mut"}),
    ("a language, whatever the case", {"languages": ("FRENCH",)}, {"ben-mut"}),
    ("one intent", {"intents": ("mentoring",)}, {"ada-mut", "ben-mut"}),
    ("either intent", {"intents": ("cofounding", "mentoring")}, {"ada-mut", "ben-mut"}),
    (
        "both intents at once",
        {"intents": ("cofounding", "mentoring"), "intents_match": "all"},
        {"ada-mut"},
    ),
    ("an intent nobody has", {"intents": ("investing",)}, set()),
    ("a word that is not an intent filters nothing", {"intents": ("dancing",)}, None),
    ("members who wrote an entry", {"has_entry": True}, {"ada-mut"}),
    ("members who did not", {"has_entry": False}, {"ben-mut", "cid-mut"}),
    ("members who have signed in", {"claimed_only": True}, {"ada-mut"}),
    ("no filters at all", {}, None),
    (
        "filters combine, they do not compete",
        {"q": "filter", "is_ca": False, "has_entry": True},
        {"ada-mut"},
    ),
]


async def test_every_directory_filter_narrows_the_directory(
    members: SqlMemberRepository, directory: dict[str, uuid.UUID]
) -> None:
    """One member matches, the others do not: that is what a filter has to do."""
    slug_by_id = {member_id: slug for slug, member_id in directory.items()}
    everybody = set(directory)

    for label, kwargs, expected in FILTER_CASES:
        ids = await members.matching_ids(MemberFilters(**kwargs))
        got = {slug_by_id[i] for i in ids}
        assert got == (everybody if expected is None else expected), label

    # The paged search runs the same predicates as the unpaged id list.
    page = await members.search(
        skip=0, limit=50, filters=MemberFilters(is_ca=True), viewer_member_id=None
    )
    assert [m.slug for m in page.items] == ["ben-mut"]
    assert page.total == 1


async def test_a_hidden_entry_leaves_the_filters_that_do_not_read_it_alone(
    members: SqlMemberRepository, session, directory: dict[str, uuid.UUID]
) -> None:
    """Hiding an entry takes its words out of the haystack and nothing else: the member
    still has an entry, and the fields the loader scraped still match."""
    await SqlEntryRepository(session).upsert(directory["ada-mut"], EntryUpsert(visibility="hidden"))

    assert await members.matching_ids(MemberFilters(q="fundraising")) == []
    assert await members.matching_ids(MemberFilters(company="Ariadne")) == []
    assert await members.matching_ids(MemberFilters(has_entry=True)) == [directory["ada-mut"]]
    assert await members.matching_ids(MemberFilters(q="plato")) == [directory["ada-mut"]]
    assert await members.matching_ids(MemberFilters(company="plato")) == [directory["ada-mut"]]


# ---- ordering, paging and the claimed flag ----------------------------------------------


async def test_a_directory_page_is_ordered_paged_and_says_how_many_there_are(
    members: SqlMemberRepository, directory: dict[str, uuid.UUID]
) -> None:
    insert_member("dana-mut", "Dana Filter")
    order = MemberFilters(sort="name")

    first = await members.search(skip=0, limit=2, filters=order, viewer_member_id=None)
    assert [m.slug for m in first.items] == ["ada-mut", "ben-mut"]
    assert first.total == 4, "total counts everyone the filters match, not the page"

    second = await members.search(skip=2, limit=2, filters=order, viewer_member_id=None)
    assert [m.slug for m in second.items] == ["cid-mut", "dana-mut"]
    assert second.total == 4

    past_the_end = await members.search(skip=4, limit=2, filters=order, viewer_member_id=None)
    assert past_the_end.items == [] and past_the_end.total == 4


async def test_the_sort_parameter_decides_the_order(
    members: SqlMemberRepository, directory: dict[str, uuid.UUID]
) -> None:
    """ "relevance" is the default: a name that matches the words typed floats to the top.
    The other two orders are asked for by name."""
    insert_member("dana-plato", "Dana Plato", search_text="dana plato")

    async def slugs(**kwargs) -> list[str]:
        page = await members.search(
            skip=0, limit=50, filters=MemberFilters(**kwargs), viewer_member_id=None
        )
        return [m.slug for m in page.items]

    assert await slugs(sort="name") == ["ada-mut", "ben-mut", "cid-mut", "dana-plato"]
    # class_label descending, and a member with no class is last rather than first.
    assert await slugs(sort="class") == ["ben-mut", "ada-mut", "cid-mut", "dana-plato"]
    # Both members mention Plato; only one is called it.
    assert await slugs(q="plato") == ["dana-plato", "ada-mut"]
    assert await slugs(q="plato", sort="name") == ["ada-mut", "dana-plato"]
    # No sort and no free text is still alphabetical, not whatever the table returns.
    assert await slugs() == ["ada-mut", "ben-mut", "cid-mut", "dana-plato"]


async def test_every_read_path_says_whether_a_member_has_signed_in(
    members: SqlMemberRepository, directory: dict[str, uuid.UUID]
) -> None:
    """``is_claimed`` drives "invite them" vs "message them", so a card that comes back
    from a search must carry it as truthfully as a profile does."""
    ada, ben = directory["ada-mut"], directory["ben-mut"]

    page = await members.search(
        skip=0, limit=50, filters=MemberFilters(sort="name"), viewer_member_id=None
    )
    assert {m.slug: m.is_claimed for m in page.items} == {
        "ada-mut": True,
        "ben-mut": False,
        "cid-mut": False,
    }
    assert [m.is_claimed for m in await members.get_many([ada, ben])] == [True, False]
    assert (await members.get_by_id(ada)).is_claimed is True
    assert (await members.get_by_id(ben)).is_claimed is False
    assert (await members.get_by_slug("ada-mut")).is_claimed is True
    assert (await members.get_by_slug("ben-mut")).is_claimed is False


async def test_lookup_by_id_keeps_the_order_asked_for_and_drops_the_unknown(
    members: SqlMemberRepository, directory: dict[str, uuid.UUID]
) -> None:
    ada, ben = directory["ada-mut"], directory["ben-mut"]
    asked = [ben, ada, uuid.uuid4(), ben]
    assert [m.slug for m in await members.get_many(asked)] == ["ben-mut", "ada-mut", "ben-mut"]
    assert await members.get_many([uuid.uuid4()]) == []
    assert await members.get_many([]) == []
    assert await members.get_by_id(uuid.uuid4()) is None
    assert await members.get_by_slug("nobody-at-all") is None


# ---- what a row becomes once it is out of the database ----------------------------------


async def test_a_profile_read_back_carries_what_the_loader_put_in(
    members: SqlMemberRepository, directory: dict[str, uuid.UUID]
) -> None:
    profile = await members.get_by_slug("ada-mut")

    assert profile.id == directory["ada-mut"]
    assert (profile.first_name, profile.last_name) == ("Ada", "Filter")
    assert profile.headline == "Head of Product at Plato Labs"
    assert profile.avatar.sm == "https://cdn.test/ada-sm.webp"
    assert profile.avatar.lg == "https://cdn.test/ada.webp"
    assert profile.avatar.blur == "data:image/webp;base64,blur"
    assert profile.linkedin_url == "https://linkedin.com/in/ada"
    assert [(c.id, c.label, c.year) for c in profile.classes] == [(17, "Fall 2020", 2020)]
    assert profile.major == "Business Administration"
    assert [r.value for r in profile.roles] == ["student"]
    assert profile.roster_name == "Filter, Ada"
    assert profile.email == "ada.filter@cdtm.com", "the loader stores e-mail lowercased"
    assert profile.summary == "Two sentences about Ada."
    assert [(p.company, p.title, p.source) for p in profile.positions] == [
        ("Old Bank", "Analyst", "linkedin")
    ]
    assert [(e.school, e.degree) for e in profile.educations] == [("Stanford", "Computer Science")]
    assert profile.skills == ["python", "sql"]
    assert profile.languages == ["german"]
    assert profile.company_info.name == "Plato Labs"
    assert profile.company_info.industry == "Software"
    assert profile.linkedin_synced_at == SYNCED_AT
    assert profile.review.matched is True
    assert profile.review.match_method.value == "exact"
    assert profile.review.needs_review is False
    assert profile.intents.cofounding is True and profile.intents.mentoring is True
    assert profile.intents.hiring is False
    # The entry wins over the scrape for the three fields it can speak to.
    assert (profile.company, profile.title, profile.location) == (
        "Ariadne Ventures",
        "Founder",
        "Garching",
    )
    assert profile.entry.ask_me_about == "fundraising and b2b sales"
    assert profile.entry.contact_preference.value == "email"
    assert profile.entry.topics == ["fundraising"]

    ben = await members.get_by_slug("ben-mut")
    assert ben.ca.alumni is True and ben.ca.about == "ran marketing"
    assert ben.ca.email == "ben.ca@cdtm.com"
    assert ben.review.needs_review is True and ben.review.matched is False
    assert ben.review.match_method is None
    assert (ben.company, ben.title, ben.location) == ("Zeta GmbH", "Designer", "Berlin")
    assert ben.entry is None and ben.company_info is None

    cid = await members.get_by_slug("cid-mut")
    assert cid.avatar is None and cid.intents is None and cid.ca is None
    assert cid.classes == [] and cid.positions == [] and cid.educations == []


async def test_the_facets_a_directory_offers(
    members: SqlMemberRepository, directory: dict[str, uuid.UUID]
) -> None:
    """Classes newest first, majors alphabetical, and a count of everybody."""
    await members.upsert_classes(
        [ClassImport(id=24, label="Fall 2023", season="fall", year=2023, location=2)]
    )
    insert_member("pia-mut", "Pia Facet", major="Analytics")

    assert [
        (c.id, c.label, c.season, c.year, c.location) for c in await members.list_classes()
    ] == [
        # Newest year first, and two classes in the same year are ordered by label.
        (24, "Fall 2023", "fall", 2023, 2),
        (23, "Spring 2023", "spring", 2023, 2),
        (17, "Fall 2020", "fall", 2020, 1),
    ]
    assert await members.list_majors() == ["Analytics", "Business", "Business Administration"]
    assert await members.count() == 4


async def test_an_empty_directory_counts_zero(members: SqlMemberRepository) -> None:
    assert await members.count() == 0
    assert await members.list_classes() == []
    assert await members.list_majors() == []


async def test_one_member_per_company_matches_the_way_the_company_filter_does(
    members: SqlMemberRepository, directory: dict[str, uuid.UUID]
) -> None:
    """The job board's batched question and ``?company=`` must never disagree, so it uses
    the same OR: the employer on the row, or anywhere in the haystack."""
    insert_member("zoe-helios", "Zoe Helios", current_company="Helios AG", search_text="zoe helios")
    insert_member("amy-helios", "Amy Helios", search_text="amy helios helios ag consultant")

    rows = await members.one_member_per_company(["Helios", "Ariadne", "Nobody Inc"])
    by_company = {company: (member_id, total) for company, member_id, total in rows}

    assert list(by_company) == ["Helios", "Ariadne"], "order follows the question, misses drop out"
    # Two members match; the one returned is the same one every time this is asked.
    assert by_company["Helios"][1] == 2
    assert (await members.get_by_id(by_company["Helios"][0])).slug == "amy-helios"
    # Ariadne is nobody's ``current_company``: only the haystack knows it.
    assert by_company["Ariadne"] == (directory["ada-mut"], 1)
    assert await members.one_member_per_company([]) == []


# ---- the loader ------------------------------------------------------------------------


async def test_the_loader_upserts_a_member_and_then_updates_the_same_row(
    members: SqlMemberRepository, session
) -> None:
    """``scripts/platform/load_community.py`` runs this on every ingest, so importing the
    same person twice has to update one row rather than making a second."""
    service = ImportService(members)
    assert await service.import_classes([ClassImport(id=17, label="Fall 2020", year=2020)]) == 1
    assert await service.import_classes([]) == 0

    first = await service.import_member(
        _member(
            "ida-mut",
            "Ida Loader",
            roster_person_id=900,
            email="IDA.Loader@CDTM.com",
            class_ids=[17],
            major="Business",
            roles=[Role.STUDENT, Role.CA],
            match_method=MatchMethod.RANKED,
            current_company="Helios AG",
            positions=[
                Position(company="Helios AG", title="Analyst"),
                Position(company="Old Bank", title="Intern"),
            ],
            educations=[Education(school="Stanford", degree="Computer Science")],
            ca=CaDetail(alumni=False, about="first pass", email="ida.ca@cdtm.com"),
        )
    )
    profile = await members.get_by_id(first)
    assert profile.name == "Ida Loader"
    assert profile.email == "ida.loader@cdtm.com"
    assert [r.value for r in profile.roles] == ["student", "ca"]
    assert profile.review.match_method.value == "ranked"
    assert [p.title for p in profile.positions] == ["Analyst", "Intern"], "payload order is kept"
    assert profile.ca.about == "first pass"
    assert await members.matching_ids(MemberFilters(q="helios")) == [first]

    # Same person, new scrape: one row, and the snapshot lists replace rather than pile up.
    again = await service.import_member(
        _member(
            "ida-mut",
            "Ida Loader-Newname",
            roster_person_id=900,
            class_ids=[17],
            current_company="Zeta GmbH",
            positions=[Position(company="Zeta GmbH", title="Founder")],
            educations=[],
            ca=None,
        )
    )
    assert again == first, "a second import of the same slug must not create a second member"
    assert await members.count() == 1
    profile = await members.get_by_id(first)
    assert profile.name == "Ida Loader-Newname"
    assert [p.company for p in profile.positions] == ["Zeta GmbH"]
    assert profile.educations == []
    assert profile.ca is None, "a member who stopped being a CA keeps no CA detail"
    assert [c.id for c in profile.classes] == [17]
    assert await members.matching_ids(MemberFilters(q="helios")) == [], "search_text is rebuilt"
    assert await members.matching_ids(MemberFilters(company="Zeta")) == [first]


async def test_the_loader_recognises_a_member_whose_slug_changed(
    members: SqlMemberRepository,
) -> None:
    """A renamed LinkedIn profile is a new slug for the same roster person, not a new one."""
    first = await members.upsert_member(_member("jon-old", "Jon Renamed", roster_person_id=901))
    again = await members.upsert_member(_member("jon-new", "Jon Renamed", roster_person_id=901))
    assert again == first
    assert await members.count() == 1
    assert await members.find_id_by_slug("jon-new") == first
    assert await members.find_id_by_slug("jon-old") is None

    # Nothing to go on but a new slug: a different person.
    other = await members.upsert_member(_member("kim-mut", "Kim Other"))
    assert other != first
    assert await members.count() == 2
    assert await members.find_id_by_slug("nobody-here") is None


async def test_the_loader_keeps_class_positions_deduplicated_and_manual_rows_intact(
    members: SqlMemberRepository, session
) -> None:
    """The scrape is replaced on every import; a position that did not come from the
    scrape is not the scrape's to delete."""
    await members.upsert_classes(
        [
            ClassImport(id=17, label="Fall 2020", year=2020),
            ClassImport(id=23, label="Spring 2023", year=2023),
        ]
    )
    member_id = await members.upsert_member(
        _member(
            "lea-mut",
            "Lea Loader",
            class_ids=[17, 17, 23, 17],
            positions=[Position(company="Scraped GmbH", title="Analyst")],
        )
    )
    profile = await members.get_by_id(member_id)
    assert [c.id for c in profile.classes] == [23, 17], "a class listed twice is joined once"
    with _engine.begin() as conn:
        conn.execute(
            text(
                "insert into positions (member_id, company, title, sort_order, source) "
                "values (:id, 'Hand Typed AG', 'Advisor', 9, 'manual')"
            ),
            {"id": member_id},
        )
    await members.upsert_member(
        _member("lea-mut", "Lea Loader", positions=[Position(company="Fresh AG", title="Lead")])
    )

    profile = await members.get_by_id(member_id)
    assert sorted(p.company for p in profile.positions) == ["Fresh AG", "Hand Typed AG"]
    assert [c.id for c in profile.classes] == [], "classes are replaced by the new payload"


async def test_the_loader_binds_workspace_emails_by_slug(members: SqlMemberRepository) -> None:
    """``bind_emails`` runs over the Workspace export, which names people by slug and
    knows nothing about ids; a slug nobody has is skipped rather than fatal."""
    mia = await members.upsert_member(_member("mia-mut", "Mia Loader"))
    noa = await members.upsert_member(_member("noa-mut", "Noa Loader"))

    bound = await ImportService(members).bind_emails(
        {
            # A slug the export has and the roster does not: skipped, and the rest of the
            # export is still bound.
            "nobody-mut": "ghost@cdtm.com",
            "mia-mut": "Mia.Loader@CDTM.com",
            "noa-mut": "Noa.Loader@CDTM.com",
        }
    )
    assert bound == 2, "only the slugs that exist are counted, and all of them are"
    assert (await members.get_by_id(mia)).email == "mia.loader@cdtm.com"
    assert (await members.get_by_id(noa)).email == "noa.loader@cdtm.com"

    await members.set_email(mia, None)
    assert (await members.get_by_id(mia)).email is None
    await members.set_email(uuid.uuid4(), "ghost@cdtm.com")  # unknown member: a no-op


async def test_two_members_cannot_be_bound_to_one_mailbox(
    members: SqlMemberRepository,
) -> None:
    """One Workspace mailbox is one person: the e-mail is how identity binds an account to
    a member, so a second claim on it is refused and the session survives the refusal."""
    from backend.core.exceptions import ConflictError

    await members.upsert_member(_member("pam-mut", "Pam Loader"))
    twin = await members.upsert_member(_member("pat-mut", "Pat Loader"))
    await ImportService(members).bind_emails({"pam-mut": "shared@cdtm.com"})

    with pytest.raises(ConflictError):
        await members.set_email(twin, "SHARED@cdtm.com")

    assert (await members.get_by_slug("pam-mut")).email == "shared@cdtm.com"
    assert (await members.get_by_slug("pat-mut")).email is None


async def test_refreshing_the_haystack_picks_up_a_row_changed_underneath_it(
    members: SqlMemberRepository,
) -> None:
    """The loader recomputes ``search_text`` after Paths and e-mail binding have run."""
    member_id = await members.upsert_member(_member("ora-mut", "Ora Loader"))
    with _engine.begin() as conn:
        conn.execute(
            text("update members set headline = 'Quantum Cartographer' where id = :id"),
            {"id": member_id},
        )
    assert await members.matching_ids(MemberFilters(q="cartographer")) == []

    await members.refresh_search_text(member_id)
    assert await members.matching_ids(MemberFilters(q="cartographer")) == [member_id]
    await members.refresh_search_text(uuid.uuid4())  # unknown member: a no-op


async def test_importing_a_class_twice_updates_it(members: SqlMemberRepository) -> None:
    assert await members.upsert_classes([ClassImport(id=17, label="Fall 2020", year=2020)]) == 1
    assert (
        await members.upsert_classes(
            [
                ClassImport(id=17, label="Fall 2020", season="fall", year=2020, location=3),
                ClassImport(id=23, label="Spring 2023", season="spring", year=2023),
            ]
        )
        == 2
    )
    assert [(c.id, c.season, c.location) for c in await members.list_classes()] == [
        (23, "spring", None),
        (17, "fall", 3),
    ]


# ---- the entry and intents a member maintains -------------------------------------------


def test_an_entry_is_updated_field_by_field_and_read_back(
    client: TestClient, member_anna: dict
) -> None:
    """A PUT carries the fields the form changed, not the whole entry: a second save must
    not blank what the first one wrote."""
    h = member_anna["headers"]
    assert client.get(f"{API}/me/entry", headers=h).json() is None

    r = client.put(
        f"{API}/me/entry",
        json={"ask_me_about": "fundraising", "topics": ["seed"], "contact_preference": "email"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    first_saved_at = r.json()["updated_at"]

    r = client.put(f"{API}/me/entry", json={"about": "building things"}, headers=h)
    assert r.status_code == 200, r.text

    entry = client.get(f"{API}/me/entry", headers=h).json()
    assert entry["ask_me_about"] == "fundraising", "the second save wiped the first one"
    assert entry["topics"] == ["seed"]
    assert entry["about"] == "building things"
    assert entry["contact_preference"] == "email", "a stored enum comes back as its value"
    assert entry["visibility"] == "members"
    assert entry["member_id"] == str(member_anna["id"])
    assert entry["updated_at"] > first_saved_at, "every save stamps the entry"


def test_intents_are_updated_field_by_field_and_read_back(
    client: TestClient, member_anna: dict
) -> None:
    h = member_anna["headers"]
    assert client.get(f"{API}/me/intents", headers=h).json() is None

    r = client.put(f"{API}/me/intents", json={"mentoring": True, "note": "pre-seed"}, headers=h)
    assert r.status_code == 200, r.text
    first_saved_at = r.json()["updated_at"]

    r = client.put(f"{API}/me/intents", json={"hiring": True}, headers=h)
    assert r.status_code == 200, r.text

    intents = client.get(f"{API}/me/intents", headers=h).json()
    assert intents["mentoring"] is True, "saying you are hiring stopped you mentoring"
    assert intents["note"] == "pre-seed"
    assert intents["hiring"] is True
    assert intents["cofounding"] is False
    assert intents["updated_at"] > first_saved_at

    # Turning one back off leaves the others alone.
    client.put(f"{API}/me/intents", json={"mentoring": False}, headers=h)
    intents = client.get(f"{API}/me/intents", headers=h).json()
    assert (intents["mentoring"], intents["hiring"]) == (False, True)


async def test_the_wiring_gives_the_entry_service_a_member_repository(
    client: TestClient, session
) -> None:
    """``get_entry_service`` is the only place the admin override's existence check gets
    its repository; without it an admin editing somebody else's entry is a 500."""
    from backend.core.actor import Actor
    from backend.members.api.deps import get_entry_service

    members = SqlMemberRepository(session)
    ben = await members.upsert_member(_member("ben-dep", "Ben Dep"))
    admin = Actor(await members.upsert_member(_member("amy-dep", "Amy Dep")), is_admin=True)

    service = get_entry_service(session)
    entry = await service.upsert_entry(
        admin, EntryUpsert(ask_me_about="ben's topic"), member_id=ben
    )
    assert entry.member_id == ben
    assert (await service.get_entry(admin, member_id=ben)).ask_me_about == "ben's topic"
    assert await service.get_entry(admin) is None, "the admin's own entry was not touched"

    with pytest.raises(Exception):  # noqa: B017 - NotFoundError, raised through the repository
        await service.get_entry(admin, member_id=uuid.uuid4())


def test_ask_uses_the_language_model_when_one_is_configured(
    client: TestClient, member_anna: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no provider configured every install still answers with keyword rules. When a
    provider is configured the wiring must actually hand it to the translator."""
    from backend.members.api import deps

    class _Completer:
        model = "test-model"

        async def complete_json(self, *, system: str, user: str, schema: dict, schema_name: str):
            assert "Venture Capital" in system, "the career group vocabulary reached the prompt"
            assert "Computer Science" in system, "the study group vocabulary reached the prompt"
            return {
                "summary": "Members the model picked out.",
                "filters": {"school": "Stanford"},
                "confidence": 0.9,
                "unresolved": [],
            }

    monkeypatch.setattr(deps, "get_structured_completer", lambda: _Completer())
    r = client.post(
        f"{API}/ask/explain",
        json={"question": "who studied at Stanford"},
        headers=member_anna["headers"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "llm"
    assert body["summary"] == "Members the model picked out."
    assert body["filters"]["school"] == "Stanford"


async def test_a_failed_write_does_not_poison_the_rest_of_the_request(
    members: SqlMemberRepository, session
) -> None:
    """Repositories hand their session to ``run_db`` so a rejected statement is rolled
    back; without it every later query in the same request answers 503."""
    from backend.core.exceptions import AppError

    await members.upsert_classes([ClassImport(id=17, label="Fall 2020", year=2020)])
    with pytest.raises(AppError):
        # Two classes cannot share a label; the second insert violates the unique index.
        await members.upsert_classes([ClassImport(id=99, label="Fall 2020", year=2020)])

    assert [c.id for c in await members.list_classes()] == [17]
    assert await members.count() == 0
