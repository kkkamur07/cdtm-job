"""ORM row -> domain mapping for the members context.

These are the functions every member card, profile and directory search result is built
by, and the string the free-text search matches against. They are pure: a row in, a model
or a string out, so they are exercised here with rows built in memory rather than through
a query, and the repository tests then confirm the same fields survive a round trip
through Postgres.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.members.domain import Visibility
from backend.members.infrastructure._mappers import build_search_text, to_member, to_profile
from backend.members.infrastructure.orm_models import (
    CaDetailRow,
    ClassRow,
    EducationRow,
    MemberEntryRow,
    MemberIntentsRow,
    MemberRow,
    PositionRow,
)

SYNCED_AT = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
UPDATED_AT = datetime(2026, 4, 2, 9, 30, tzinfo=UTC)


def _entry_row(member_id, **overrides) -> MemberEntryRow:
    fields = {
        "ask_me_about": "fundraising",
        "about": "building things",
        "current_title": "Founder",
        "current_company": "Plato",
        "location": "Berlin",
        "contact_preference": "email",
        "contact_email": "ada@plato.app",
        "hobbies": ["climbing"],
        "topics": ["b2b", "sales"],
        "visibility": Visibility.MEMBERS.value,
    }
    fields.update(overrides)
    return MemberEntryRow(member_id=member_id, **fields)


def _member_row(**overrides) -> MemberRow:
    """A member with every mapped column populated, so a dropped field is visible."""
    member_id = overrides.pop("id", None) or uuid4()
    row = MemberRow(
        id=member_id,
        slug="ada-lovelace",
        roster_person_id=4711,
        name="Ada Lovelace",
        first_name="Ada",
        last_name="Lovelace",
        roster_name="Lovelace, Ada",
        email="ada.lovelace@cdtm.com",
        headline="Head of Product at Plato",
        summary="Two sentences about Ada.",
        location="Munich",
        linkedin_url="https://linkedin.com/in/ada",
        avatar_sm_url="https://cdn.test/ada-sm.webp",
        avatar_lg_url="https://cdn.test/ada.webp",
        avatar_blur="data:image/webp;base64,blurblur",
        class_label="Spring 2020",
        major="Business Administration",
        roles=["student", "ca"],
        is_ca=True,
        ca_alumni=True,
        matched=True,
        match_method="exact",
        needs_review=True,
        current_company="Plato Labs",
        current_title="Head of Product",
        skills=["Python", "SQL"],
        languages=["German", "English"],
        company_info={"name": "Plato Labs", "industry": "Software", "employee_count": 12},
        linkedin_synced_at=SYNCED_AT,
        updated_at=UPDATED_AT,
    )
    row.classes = [ClassRow(id=17, label="Spring 2020", season="spring", year=2020, location=1)]
    row.positions = [
        PositionRow(
            member_id=member_id,
            company="Old Bank",
            title="Analyst",
            sort_order=0,
            is_current=False,
            source="linkedin",
        ),
        PositionRow(
            member_id=member_id,
            company="Corner Shop",
            title="Intern",
            sort_order=1,
            is_current=False,
            source="linkedin",
        ),
    ]
    row.educations = [
        EducationRow(
            member_id=member_id, school="Stanford", degree="Computer Science", sort_order=0
        ),
        EducationRow(member_id=member_id, school="TUM", degree="Physics", sort_order=1),
    ]
    row.ca_detail = CaDetailRow(
        member_id=member_id,
        alumni=True,
        about="ran the marketing team",
        responsibilities=["marketing"],
        research_fields=["hci"],
        email="ada@cdtm.com",
    )
    row.entry = _entry_row(member_id)
    row.intents = MemberIntentsRow(
        member_id=member_id,
        cofounding=True,
        mentoring=True,
        hiring=False,
        open_to_roles=False,
        speaking=False,
        investing=False,
        note="pre-seed only",
        updated_at=UPDATED_AT,
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


# ---- the card --------------------------------------------------------------------------


def test_the_card_carries_every_field_the_directory_shows() -> None:
    row = _member_row()
    card = to_member(row, is_claimed=True)

    assert card.id == row.id
    assert card.slug == "ada-lovelace"
    assert card.name == "Ada Lovelace"
    assert card.first_name == "Ada"
    assert card.last_name == "Lovelace"
    assert card.headline == "Head of Product at Plato"
    assert card.avatar.sm == "https://cdn.test/ada-sm.webp"
    assert card.avatar.lg == "https://cdn.test/ada.webp"
    assert card.avatar.blur == "data:image/webp;base64,blurblur"
    assert card.linkedin_url == "https://linkedin.com/in/ada"
    assert [(c.id, c.label, c.season, c.year, c.location) for c in card.classes] == [
        (17, "Spring 2020", "spring", 2020, 1)
    ]
    assert card.class_label == "Spring 2020"
    assert card.major == "Business Administration"
    assert [r.value for r in card.roles] == ["student", "ca"]
    assert card.is_ca is True
    assert card.ca_alumni is True
    assert card.intents.cofounding is True
    assert card.intents.mentoring is True
    assert card.intents.hiring is False
    assert card.intents.note == "pre-seed only"
    assert card.is_claimed is True
    assert card.updated_at == UPDATED_AT
    # Roster bookkeeping never reaches a card.
    assert not hasattr(card, "review")


def test_an_entry_overrides_company_title_and_location_on_the_card() -> None:
    """What a member says about themselves wins over what the scrape found."""
    card = to_member(_member_row(), is_claimed=False)
    assert card.company == "Plato"
    assert card.title == "Founder"
    assert card.location == "Berlin"


@pytest.mark.parametrize("field", ["current_company", "current_title", "location"])
def test_an_empty_entry_field_falls_back_to_the_scraped_value(field: str) -> None:
    row = _member_row()
    row.entry = _entry_row(row.id, **{field: None})
    card = to_member(row, is_claimed=False)
    assert card.company == ("Plato Labs" if field == "current_company" else "Plato")
    assert card.title == ("Head of Product" if field == "current_title" else "Founder")
    assert card.location == ("Munich" if field == "location" else "Berlin")


def test_a_member_with_no_entry_shows_the_scraped_company_title_and_location() -> None:
    row = _member_row()
    row.entry = None
    card = to_member(row)
    assert (card.company, card.title, card.location) == ("Plato Labs", "Head of Product", "Munich")
    assert card.intents is not None
    row.intents = None
    assert to_member(row).intents is None
    # Nobody is claimed unless the repository says so.
    assert to_member(row).is_claimed is False


@pytest.mark.parametrize(
    ("sm", "lg"),
    [(None, "https://cdn.test/ada.webp"), ("https://cdn.test/ada-sm.webp", None), (None, None)],
)
def test_half_an_avatar_is_no_avatar(sm: str | None, lg: str | None) -> None:
    """Both sizes or none: a card that renders one URL and a broken image is worse."""
    row = _member_row(avatar_sm_url=sm, avatar_lg_url=lg)
    assert to_member(row, is_claimed=False).avatar is None


# ---- the profile -----------------------------------------------------------------------


def test_the_profile_carries_the_card_plus_everything_behind_it() -> None:
    row = _member_row()
    profile = to_profile(row, is_claimed=True)

    # Everything the card has, unchanged.
    assert (profile.slug, profile.name, profile.class_label) == (
        "ada-lovelace",
        "Ada Lovelace",
        "Spring 2020",
    )
    assert profile.is_claimed is True
    assert profile.company == "Plato"
    # ... and the fields only a profile has.
    assert profile.roster_name == "Lovelace, Ada"
    assert profile.email == "ada.lovelace@cdtm.com"
    assert profile.summary == "Two sentences about Ada."
    assert [(p.company, p.title) for p in profile.positions] == [
        ("Old Bank", "Analyst"),
        ("Corner Shop", "Intern"),
    ]
    assert [(e.school, e.degree) for e in profile.educations] == [
        ("Stanford", "Computer Science"),
        ("TUM", "Physics"),
    ]
    assert profile.skills == ["Python", "SQL"]
    assert profile.languages == ["German", "English"]
    assert profile.company_info.name == "Plato Labs"
    assert profile.company_info.industry == "Software"
    assert profile.company_info.employee_count == 12
    assert profile.ca.alumni is True
    assert profile.ca.about == "ran the marketing team"
    assert profile.ca.email == "ada@cdtm.com"
    assert profile.entry.ask_me_about == "fundraising"
    assert profile.entry.about == "building things"
    assert profile.entry.contact_preference.value == "email"
    assert profile.entry.contact_email == "ada@plato.app"
    assert profile.entry.hobbies == ["climbing"]
    assert profile.entry.topics == ["b2b", "sales"]
    assert profile.linkedin_synced_at == SYNCED_AT
    # Nobody is claimed unless the repository says so.
    assert to_profile(row).is_claimed is False


def test_the_card_half_of_a_profile_is_the_card_itself_field_for_field() -> None:
    """``to_profile`` carries the card over by field value rather than by serialising it.

    It used to build the card, ``model_dump()`` it down to primitives and hand those to
    ``MemberProfile``, which built the Avatar, the ClassRefs and the Intents back out of
    the dicts again: two passes over every profile read. The values move across as they
    are now, so this pins the JSON of the card half against the card's own.
    """
    row = _member_row()
    card = to_member(row, is_claimed=True)
    profile = to_profile(row, is_claimed=True)

    card_json = json.loads(card.model_dump_json())
    profile_json = json.loads(profile.model_dump_json())
    assert {key: profile_json[key] for key in card_json} == card_json
    # And the nested pieces are models, not the dicts a dump would have left behind.
    assert profile.avatar is not None and profile.avatar.sm == card.avatar.sm
    assert [c.id for c in profile.classes] == [c.id for c in card.classes]
    assert profile.intents is not None and profile.intents == card.intents


def test_the_profile_reports_how_the_loader_matched_this_person() -> None:
    """``review`` is the loader's bookkeeping; the mapper must not flatten it to defaults."""
    profile = to_profile(_member_row(), is_claimed=False)
    assert profile.review.matched is True
    assert profile.review.match_method.value == "exact"
    assert profile.review.needs_review is True

    unmatched = to_profile(
        _member_row(matched=False, match_method=None, needs_review=False), is_claimed=False
    )
    assert unmatched.review.matched is False
    assert unmatched.review.match_method is None
    assert unmatched.review.needs_review is False


def test_the_optional_blocks_of_a_profile_are_absent_rather_than_empty() -> None:
    row = _member_row()
    row.ca_detail = None
    row.entry = None
    row.company_info = None
    profile = to_profile(row, is_claimed=False)
    assert profile.ca is None
    assert profile.entry is None
    assert profile.company_info is None
    assert profile.positions and profile.educations


# ---- the search haystack ---------------------------------------------------------------


def test_the_haystack_is_every_searchable_field_lowercased_in_order() -> None:
    expected = " ".join(
        [
            "Ada Lovelace",
            "Head of Product at Plato",
            "Plato Labs",
            "Head of Product",
            "Business Administration",
            "Spring 2020",
            "Munich",
            "Python SQL",
            # the visible entry
            "fundraising",
            "Plato",
            "Founder",
            "b2b sales",
            "climbing",
            # every job, then every school and degree
            "Old Bank",
            "Analyst",
            "Corner Shop",
            "Intern",
            "Stanford",
            "Computer Science",
            "TUM",
            "Physics",
        ]
    ).lower()
    assert build_search_text(_member_row()) == expected


def test_a_hidden_entry_is_not_in_the_haystack_but_everything_else_still_is() -> None:
    """Folding a hidden entry in makes ?q= a confirmation oracle for withheld text; folding
    the rest out would silently empty the index for anyone who wrote an entry."""
    row = _member_row()
    row.entry = _entry_row(row.id, visibility=Visibility.HIDDEN.value, ask_me_about="secretword")
    haystack = build_search_text(row)

    assert "secretword" not in haystack
    assert "b2b" not in haystack and "climbing" not in haystack
    assert (
        haystack
        == " ".join(
            [
                "Ada Lovelace",
                "Head of Product at Plato",
                "Plato Labs",
                "Head of Product",
                "Business Administration",
                "Spring 2020",
                "Munich",
                "Python SQL",
                "Old Bank",
                "Analyst",
                "Corner Shop",
                "Intern",
                "Stanford",
                "Computer Science",
                "TUM",
                "Physics",
            ]
        ).lower()
    )


def test_the_haystack_of_a_member_with_nothing_but_a_name_is_just_the_name() -> None:
    row = MemberRow(id=uuid4(), slug="bare", name="Bare Member")
    assert build_search_text(row) == "bare member"


def test_a_field_the_scrape_never_filled_in_leaves_no_gap_in_the_haystack() -> None:
    """Half the directory has a job with no company or a school with no degree; a missing
    field drops out of the haystack rather than putting a hole in it."""
    member_id = uuid4()
    row = MemberRow(id=member_id, slug="holes", name="Holey Row")
    row.positions = [
        PositionRow(member_id=member_id, title="Analyst", sort_order=0, is_current=False)
    ]
    row.educations = [EducationRow(member_id=member_id, school="TUM", sort_order=0)]
    row.entry = MemberEntryRow(
        member_id=member_id,
        topics=["fundraising"],
        hobbies=[],
        contact_preference="intro",
        visibility=Visibility.MEMBERS.value,
    )
    assert build_search_text(row) == "holey row fundraising analyst tum"
