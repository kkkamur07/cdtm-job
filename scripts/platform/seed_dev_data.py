#!/usr/bin/env python3
"""Seed a development database with content around the loaded Members.

    uv run poe seed

Members come from ``load_community.py``; this script only adds what Members would normally
create themselves: intents, entries, jobs (with companies), events, announcements and
housing listings. It is idempotent: every row is keyed by slug or title and re-used, and
intents and entries are only written for Members who have none yet.

Which Members get intents and entries is deterministic (a hash of the slug), so the same
database always looks the same and the "open to co-founding, like you" rows on the home
page have something to show. Logos, covers and photos point at public placeholder hosts
(logo.clearbit.com, picsum.photos); none of it is CDTM data.
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
from datetime import UTC, date, datetime, timedelta

from _bootstrap import ensure_repo_on_path

ensure_repo_on_path()

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from backend.announcements.infrastructure.orm_models import AnnouncementRow  # noqa: E402
from backend.events.infrastructure.orm_models import EventRow  # noqa: E402
from backend.housing.infrastructure.orm_models import HousingListingRow  # noqa: E402
from backend.jobboard.infrastructure.orm_models import CompanyRow, JobRow  # noqa: E402
from backend.members.infrastructure._mappers import build_search_text  # noqa: E402
from backend.members.infrastructure.orm_models import (  # noqa: E402
    MemberEntryRow,
    MemberIntentsRow,
    MemberRow,
)
from infrastructure.db import get_session_factory  # noqa: E402


def _logo(domain: str) -> str:
    return f"https://logo.clearbit.com/{domain}"


def _photo(seed: str, w: int = 1200, h: int = 800) -> str:
    return f"https://picsum.photos/seed/{seed}/{w}/{h}"


COMPANIES = [
    dict(
        name="Plato",
        slug="plato",
        industry="Software",
        is_cdtm_startup=True,
        hq_city="Berlin",
        hq_country="DE",
        company_size_band="startup",
        website_url="https://www.plato.io",
        logo_url=_logo("plato.io"),
        short_description="AI workflow software for distributors.",
    ),
    dict(
        name="Celonis",
        slug="celonis",
        industry="Software",
        is_cdtm_startup=True,
        hq_city="Munich",
        hq_country="DE",
        company_size_band="enterprise",
        website_url="https://www.celonis.com",
        logo_url=_logo("celonis.com"),
        short_description="Process mining.",
    ),
    dict(
        name="Tacto",
        slug="tacto",
        industry="Procurement",
        is_cdtm_startup=True,
        hq_city="Munich",
        hq_country="DE",
        company_size_band="startup",
        website_url="https://www.tacto.ai",
        logo_url=_logo("tacto.ai"),
        short_description="Supply-chain software for the Mittelstand.",
    ),
    dict(
        name="Personio",
        slug="personio",
        industry="HR Software",
        is_cdtm_startup=False,
        hq_city="Munich",
        hq_country="DE",
        company_size_band="enterprise",
        website_url="https://www.personio.com",
        logo_url=_logo("personio.com"),
        short_description="HR operating system for small and mid-sized companies.",
    ),
    dict(
        name="Helsing",
        slug="helsing",
        industry="Defence AI",
        is_cdtm_startup=False,
        hq_city="Munich",
        hq_country="DE",
        company_size_band="mid",
        website_url="https://helsing.ai",
        logo_url=_logo("helsing.ai"),
        short_description="Software-first defence company.",
    ),
    dict(
        name="Isar Aerospace",
        slug="isar-aerospace",
        industry="Space",
        is_cdtm_startup=False,
        hq_city="Munich",
        hq_country="DE",
        company_size_band="mid",
        website_url="https://www.isaraerospace.com",
        logo_url=_logo("isaraerospace.com"),
        short_description="Launch vehicles for small and medium satellites.",
    ),
    dict(
        name="Google",
        slug="google",
        industry="Technology",
        is_cdtm_startup=False,
        hq_city="Zurich",
        hq_country="CH",
        company_size_band="enterprise",
        website_url="https://www.google.com",
        logo_url=_logo("google.com"),
        short_description="Search, cloud, Android.",
    ),
]

JOBS = [
    dict(
        company="plato",
        slug="plato-founding-engineer",
        title="Founding Engineer",
        summary="Build the core product with the founders, own whole features end to end.",
        employment_type="full_time",
        work_arrangement="hybrid",
        experience_level="mid",
        city="Berlin",
        country="DE",
        location_display="Berlin, hybrid",
        salary_min=75000,
        salary_max=95000,
        salary_currency="EUR",
        salary_period="yearly",
        compensation_disclosure="public",
        status="published",
        image_url=_photo("plato-cover", 1600, 600),
        application_url="https://www.plato.io/careers",
        description=(
            "We are three CDTM alumni building AI workflow software for industrial "
            "distributors. You will be engineer number four, working directly with the "
            "founders on the product, the data pipeline and the first enterprise rollouts.\n\n"
            "What you will do\n"
            "- Ship features across the stack (TypeScript, Postgres, a bit of Python)\n"
            "- Talk to customers and turn what you hear into product\n"
            "- Set up the engineering practices we will keep for years\n\n"
            "What we look for\n"
            "- Three or more years building production software\n"
            "- Comfortable owning things that are not yet defined"
        ),
        must_have_skills=["TypeScript", "Postgres", "React"],
        nice_to_have_skills=["Python", "LLM tooling"],
        days_ago=2,
    ),
    dict(
        company="celonis",
        slug="celonis-product-manager-intern",
        title="Product Manager Intern",
        summary="Six months in the core platform team, starting October.",
        employment_type="internship",
        work_arrangement="onsite",
        experience_level="intern",
        city="Munich",
        country="DE",
        location_display="Munich",
        salary_min=2400,
        salary_max=2400,
        salary_currency="EUR",
        salary_period="monthly",
        compensation_disclosure="public",
        status="published",
        image_url=_photo("celonis-cover", 1600, 600),
        application_url="https://www.celonis.com/careers",
        description=(
            "Join the core platform team for six months. You will run discovery with "
            "enterprise customers, write specs with the engineers and ship two features "
            "before you leave."
        ),
        days_ago=5,
    ),
    dict(
        company="tacto",
        slug="tacto-working-student-data",
        title="Working Student Data",
        summary="Help the data team with pipelines and dashboards, 16 to 20 hours a week.",
        employment_type="working_student",
        work_arrangement="hybrid",
        experience_level="entry",
        city="Munich",
        country="DE",
        location_display="Munich, hybrid",
        compensation_disclosure="undisclosed",
        status="published",
        application_email="jobs@example.com",
        description=(
            "You will maintain our ingestion pipelines, build dashboards for the customer "
            "success team and help us clean supplier data. Python and SQL needed."
        ),
        must_have_skills=["Python", "SQL"],
        nice_to_have_skills=["dbt"],
        days_ago=9,
    ),
    dict(
        company="personio",
        slug="personio-senior-backend-engineer",
        title="Senior Backend Engineer, Payroll",
        summary="Own the payroll calculation service that pays a million people a month.",
        employment_type="full_time",
        work_arrangement="hybrid",
        experience_level="senior",
        city="Munich",
        country="DE",
        location_display="Munich, hybrid",
        salary_min=85000,
        salary_max=110000,
        salary_currency="EUR",
        salary_period="yearly",
        compensation_disclosure="public",
        status="published",
        image_url=_photo("personio-cover", 1600, 600),
        application_url="https://www.personio.com/careers",
        description=(
            "Payroll is the part of Personio that must never be wrong. You will lead the "
            "design of the calculation engine, mentor two engineers and work with the "
            "compliance team on country rollouts."
        ),
        must_have_skills=["Kotlin", "Postgres", "Distributed systems"],
        visa_sponsorship=True,
        relocation_assistance=True,
        days_ago=1,
    ),
    dict(
        company="helsing",
        slug="helsing-ml-engineer",
        title="Machine Learning Engineer",
        summary="Perception models for airborne sensors.",
        employment_type="full_time",
        work_arrangement="onsite",
        experience_level="mid",
        city="Munich",
        country="DE",
        location_display="Munich",
        compensation_disclosure="confidential",
        status="published",
        application_url="https://helsing.ai/careers",
        description=(
            "You will train and deploy perception models on edge hardware, working closely "
            "with the flight test team. Strong PyTorch and a security clearance path required."
        ),
        must_have_skills=["PyTorch", "C++"],
        days_ago=12,
    ),
    dict(
        company="isar-aerospace",
        slug="isar-aerospace-propulsion-intern",
        title="Propulsion Engineering Intern",
        summary="Test campaign support for the Aquila engine.",
        employment_type="internship",
        work_arrangement="onsite",
        experience_level="intern",
        city="Munich",
        country="DE",
        location_display="Ottobrunn",
        compensation_disclosure="undisclosed",
        status="published",
        application_url="https://www.isaraerospace.com/careers",
        description=(
            "Support the propulsion team during the next test campaign: instrumentation, "
            "data reduction, test reports. Mechanical or aerospace engineering background."
        ),
        days_ago=20,
    ),
    dict(
        company="google",
        slug="google-product-manager-remote",
        title="Product Manager, Developer Tools",
        summary="Remote within the EU, Cloud developer experience team.",
        employment_type="full_time",
        work_arrangement="remote",
        experience_level="mid",
        city="Zurich",
        country="CH",
        location_display="Remote (EU)",
        compensation_disclosure="confidential",
        status="published",
        image_url=_photo("google-cover", 1600, 600),
        application_url="https://careers.google.com",
        description=(
            "Own the roadmap for a developer tooling product used by Cloud customers. "
            "You will work with engineering leads in Zurich and Munich."
        ),
        must_have_skills=["Product management", "Developer tools"],
        days_ago=4,
    ),
    dict(
        company="plato",
        slug="plato-growth-marketing-lead",
        title="Growth Marketing Lead",
        summary="First marketing hire. B2B, industrial customers, long sales cycles.",
        employment_type="full_time",
        work_arrangement="remote",
        experience_level="lead",
        city="Berlin",
        country="DE",
        location_display="Remote (DE)",
        salary_min=70000,
        salary_max=90000,
        salary_currency="EUR",
        salary_period="yearly",
        compensation_disclosure="public",
        status="published",
        application_url="https://www.plato.io/careers",
        description=(
            "You will build the marketing function from zero: positioning, content, events, "
            "and the first campaigns into the Mittelstand."
        ),
        days_ago=7,
    ),
]

EVENTS = [
    dict(
        title="Alumni Stammtisch Munich",
        kind="community",
        days=9,
        location="Augustiner Klosterwirt, Munich",
        description="Monthly get-together. Bring a +1 from your class.",
    ),
    dict(
        title="CDTM Demo Day",
        kind="cdtm",
        days=23,
        location="CDTM, Marsstrasse 20, Munich",
        url="https://www.cdtm.com",
        description="The current class presents the Managing Product Development projects.",
    ),
    dict(
        title="Founders Breakfast Berlin",
        kind="community",
        days=16,
        location="Factory Berlin, Goerlitzer Park",
        description="For alumni building companies in Berlin. Coffee, croissants, no pitches.",
    ),
    dict(
        title="Bits & Pretzels",
        kind="external",
        days=40,
        location="Messe Munich",
        url="https://www.bitsandpretzels.com",
        description="A few alumni go every year. Say so on the RSVP and we will coordinate.",
    ),
]

ANNOUNCEMENTS = [
    dict(
        title="Welcome to the new Community Tool",
        is_pinned=True,
        days_ago=3,
        body=(
            "Sign in with your cdtm.com Google account, claim your entry and tell the network "
            "what you are open to. Intents drive the home page and the Ask box."
        ),
    ),
    dict(
        title="Call for mentors: Class of Fall 2026",
        is_pinned=False,
        days_ago=1,
        body=(
            "The new class starts in October. If you are open to mentoring, set the intent on "
            "your entry and we will match you with two students in your field."
        ),
    ),
    dict(
        title="Housing board is live",
        is_pinned=False,
        days_ago=6,
        body=(
            "Offering a room or looking for one? Post it on the housing board so it reaches "
            "alumni before it reaches the open market."
        ),
    ),
]

LISTINGS = [
    dict(
        kind="offer",
        title="Room in Maxvorstadt WG",
        city="Munich",
        area="Maxvorstadt",
        price_eur=780,
        rooms=1,
        available_from=date.today() + timedelta(days=40),
        description=(
            "18 sqm in a three-person flat share, five minutes from TUM. Balcony, washing "
            "machine, fast wifi. We are two alumni and a med student."
        ),
        photos=["room-maxvorstadt-1", "room-maxvorstadt-2", "room-maxvorstadt-3"],
    ),
    dict(
        kind="offer",
        title="Sublet: 2-room flat in Prenzlauer Berg",
        city="Berlin",
        area="Prenzlauer Berg",
        price_eur=1350,
        rooms=2,
        available_from=date.today() + timedelta(days=20),
        available_until=date.today() + timedelta(days=200),
        description=(
            "Furnished two-room flat, six-month sublet while I am in Singapore. Altbau, "
            "fourth floor, no lift, great light."
        ),
        photos=["flat-pberg-1", "flat-pberg-2", "flat-pberg-3", "flat-pberg-4"],
    ),
    dict(
        kind="looking",
        title="Looking: room in Zurich from September",
        city="Zurich",
        price_eur=1400,
        rooms=1,
        available_from=date.today() + timedelta(days=30),
        description=(
            "Starting at Google in September, looking for a room or small flat near the "
            "Europaallee office. Budget up to 1,400 CHF."
        ),
        photos=[],
    ),
    dict(
        kind="offer",
        title="Studio in Schwabing, furnished",
        city="Munich",
        area="Schwabing",
        price_eur=1150,
        rooms=1,
        available_from=date.today() + timedelta(days=10),
        description="32 sqm studio, furnished, Muenchner Freiheit in four minutes on foot.",
        photos=["studio-schwabing-1", "studio-schwabing-2"],
    ),
    dict(
        kind="looking",
        title="Couple looking for 2 to 3 rooms in Munich",
        city="Munich",
        price_eur=2000,
        rooms=2.5,
        available_from=date.today() + timedelta(days=60),
        description="Both working, no pets, quiet. Anything between Sendling and Haidhausen.",
        photos=[],
    ),
    dict(
        kind="offer",
        title="Room in Kreuzberg WG, short term",
        city="Berlin",
        area="Kreuzberg",
        price_eur=650,
        rooms=1,
        available_from=date.today() + timedelta(days=5),
        available_until=date.today() + timedelta(days=95),
        description="Three months while our flatmate is on exchange. Furnished, bike cellar.",
        photos=["room-kreuzberg-1", "room-kreuzberg-2"],
    ),
]

# Deterministic intent assignment: the bucket decides which flags a Member gets, so roughly
# one in five Members has at least one intent and every intent has a few dozen people.
INTENT_BUCKETS = {
    0: dict(cofounding=True),
    1: dict(mentoring=True),
    2: dict(cofounding=True, hiring=True),
    3: dict(open_to_roles=True),
    4: dict(speaking=True, mentoring=True),
    5: dict(investing=True),
}
INTENT_NOTES = {
    0: "Looking for a technical co-founder for a B2B idea.",
    1: "Happy to do 30-minute calls with current students.",
    2: "Hiring engineers and a first PM.",
    3: "Open to product roles from next spring.",
    4: "Talks on go-to-market and early hiring.",
    5: "Angel cheques up to 25k in pre-seed.",
}
ENTRY_TOPICS = [
    ["go-to-market", "B2B sales", "pricing"],
    ["machine learning", "MLOps", "data platforms"],
    ["fundraising", "pre-seed", "angel investing"],
    ["product management", "discovery", "roadmaps"],
    ["climate tech", "energy", "hardware"],
    ["consulting exit", "career change", "MBA"],
]
ENTRY_HOBBIES = [
    ["bouldering", "coffee"],
    ["trail running", "sourdough"],
    ["sailing", "chess"],
    ["cycling", "photography"],
    ["skiing", "cooking"],
    ["tennis", "reading"],
]
ENTRY_ASK = [
    "Selling to the Mittelstand, pricing B2B software, hiring the first AE.",
    "Shipping ML in production, team topologies for data teams.",
    "Raising a pre-seed in Germany, term sheets, angel syndicates.",
    "Product discovery, writing PRDs people read, stakeholder management.",
    "Hardware startups, climate tech funding, working with utilities.",
    "Leaving consulting, MBA or not, first operating role.",
]


def _bucket(slug: str, modulo: int) -> int:
    return int(hashlib.sha1(slug.encode(), usedforsecurity=False).hexdigest(), 16) % modulo


async def run() -> int:
    now = datetime.now(UTC)
    async with get_session_factory()() as s:
        members = (
            await s.scalars(
                select(MemberRow)
                .options(
                    selectinload(MemberRow.entry),
                    selectinload(MemberRow.intents),
                    selectinload(MemberRow.positions),
                )
                .order_by(MemberRow.name)
            )
        ).all()
        member_id = members[0].id if members else None

        # Intents and entries for a deterministic slice of Members.
        intents_added = entries_added = 0
        for m in members:
            b = _bucket(m.slug, 30)
            if b >= 6:
                continue
            if m.intents is None:
                s.add(MemberIntentsRow(member_id=m.id, note=INTENT_NOTES[b], **INTENT_BUCKETS[b]))
                intents_added += 1
            if m.entry is None:
                m.entry = MemberEntryRow(
                    member_id=m.id,
                    ask_me_about=ENTRY_ASK[b],
                    about=(
                        f"{m.headline or 'CDTM alumni'}. Always up for a coffee with people "
                        "from the network."
                    ),
                    current_title=m.current_title,
                    current_company=m.current_company,
                    location=m.location,
                    contact_preference="intro",
                    topics=ENTRY_TOPICS[b],
                    hobbies=ENTRY_HOBBIES[b],
                )
                m.search_text = build_search_text(m)
                entries_added += 1

        # Spread authorship over a few Members so "posted by" is not always the same person.
        def author(i: int):
            return members[i % len(members)].id if members else None

        by_slug: dict[str, CompanyRow] = {}
        for c in COMPANIES:
            row = await s.scalar(select(CompanyRow).where(CompanyRow.slug == c["slug"]))
            if row is None:
                row = CompanyRow(**c)
                s.add(row)
                await s.flush()
            by_slug[c["slug"]] = row

        for i, j in enumerate(JOBS):
            j = dict(j)
            company = by_slug[j.pop("company")]
            days_ago = j.pop("days_ago", 0)
            exists = await s.scalar(
                select(JobRow).where(JobRow.company_id == company.id, JobRow.title == j["title"])
            )
            if exists is None:
                posted = now - timedelta(days=days_ago)
                s.add(
                    JobRow(
                        company_id=company.id,
                        posted_by_member_id=author(i * 7),
                        published_at=posted,
                        created_at=posted,
                        valid_through=(posted + timedelta(days=60)).date(),
                        **j,
                    )
                )

        for i, e in enumerate(EVENTS):
            if await s.scalar(select(EventRow).where(EventRow.title == e["title"])) is None:
                e = dict(e)
                starts = now.replace(hour=18, minute=30, second=0, microsecond=0) + timedelta(
                    days=e.pop("days")
                )
                s.add(
                    EventRow(
                        starts_at=starts,
                        ends_at=starts + timedelta(hours=3),
                        created_by_member_id=author(i * 11),
                        **e,
                    )
                )

        for i, a in enumerate(ANNOUNCEMENTS):
            if (
                await s.scalar(select(AnnouncementRow).where(AnnouncementRow.title == a["title"]))
                is None
            ):
                a = dict(a)
                s.add(
                    AnnouncementRow(
                        published_at=now - timedelta(days=a.pop("days_ago")),
                        author_member_id=author(i * 13),
                        **a,
                    )
                )

        if member_id is not None:
            for i, h in enumerate(LISTINGS):
                if (
                    await s.scalar(
                        select(HousingListingRow).where(HousingListingRow.title == h["title"])
                    )
                    is None
                ):
                    h = dict(h)
                    photos = h.pop("photos")
                    s.add(
                        HousingListingRow(
                            member_id=member_id if i == 0 else author(i * 17),
                            photo_urls=[_photo(p) for p in photos],
                            expires_at=now + timedelta(days=60 - 7 * i),
                            **h,
                        )
                    )

        await s.commit()
        n_members = await s.scalar(select(func.count()).select_from(MemberRow))
    print(
        f"seeded: {n_members} members, +{intents_added} intents, +{entries_added} entries, "
        f"{len(COMPANIES)} companies, {len(JOBS)} jobs, {len(EVENTS)} events, "
        f"{len(ANNOUNCEMENTS)} announcements, {len(LISTINGS)} listings"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
