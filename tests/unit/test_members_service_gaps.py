"""The caps ``MemberService`` puts on a batch before it reaches the repository.

``lookup`` and ``contacts_at`` document "duplicates collapse and the first 50 win", and the
routers in ``api/members.py`` refuse a longer query string before the service is reached
(``tests/integration/test_members_a_gaps.py`` covers that refusal). The cap itself is the
service's own promise to any caller, so it is checked here against a fake repository that
records what it was asked for. No database: nothing below this line touches one.
"""

from __future__ import annotations

import uuid
from uuid import UUID

from backend.members.application.commands import MemberImport, SelfProfileCreate
from backend.members.application.member_service import MemberService
from backend.members.domain import ClassRef, Member


class RecordingMembers:
    """The two ``MemberRepository`` batch methods, remembering their arguments."""

    def __init__(self) -> None:
        self.ids: list[list[UUID]] = []
        self.companies: list[list[str]] = []

    async def get_many(self, ids: list[UUID]) -> list[Member]:
        self.ids.append(list(ids))
        return []

    async def one_member_per_company(self, companies: list[str]) -> list[tuple[str, UUID, int]]:
        self.companies.append(list(companies))
        return []


async def test_lookup_resolves_at_most_fifty_ids_and_collapses_duplicates() -> None:
    repository = RecordingMembers()
    ids = [uuid.uuid4() for _ in range(60)]

    await MemberService(repository).lookup([*ids, *ids[:5]])

    assert repository.ids == [ids[:50]]


async def test_contacts_at_asks_about_at_most_fifty_companies() -> None:
    repository = RecordingMembers()
    names = [f"Company {i:02d}" for i in range(60)]

    # Blanks are dropped and repeats collapse before the cap is applied.
    await MemberService(repository).contacts_at([*names, "   ", "Company 00"])

    assert repository.companies == [names[:50]]


class SlugMembers:
    """Just the slug question ``_unique_slug`` asks, over a fixed set of taken names."""

    def __init__(self, taken: set[str]) -> None:
        self._taken = taken
        self.queries: list[str] = []

    async def slugs_for_base(self, base: str) -> list[str]:
        self.queries.append(base)
        return sorted(s for s in self._taken if s == base or s.startswith(f"{base}-"))

    async def list_classes(self) -> list[ClassRef]:
        return [ClassRef(id=85, label="Spring 2019", season="Spring", year=2019, location=None)]

    async def upsert_member(self, payload: MemberImport) -> UUID:
        self.written = payload
        return uuid.uuid4()


async def test_a_free_name_is_taken_as_it_is_in_one_query() -> None:
    members = SlugMembers(set())
    assert await MemberService(members)._unique_slug("ada-lovelace") == "ada-lovelace"
    assert members.queries == ["ada-lovelace"]


async def test_the_first_free_suffix_wins_after_a_run_of_collisions() -> None:
    """base, base-2 and base-3 taken: the fourth Ada is base-4, and it costs one query."""
    members = SlugMembers({"ada-lovelace", "ada-lovelace-2", "ada-lovelace-3"})

    assert await MemberService(members)._unique_slug("ada-lovelace") == "ada-lovelace-4"
    assert members.queries == ["ada-lovelace"]


async def test_a_gap_in_the_series_is_filled_rather_than_skipped() -> None:
    """base and base-3 taken, base-2 free: the free one is used."""
    members = SlugMembers({"ada-lovelace", "ada-lovelace-3"})

    assert await MemberService(members)._unique_slug("ada-lovelace") == "ada-lovelace-2"


async def test_a_longer_name_that_merely_starts_the_same_is_not_a_collision() -> None:
    """``ada-lovelace-king`` is somebody else's slug, not a numbered Ada.

    It comes back from the same prefix query, so the check has to be membership in the
    series and not "did anything match".
    """
    members = SlugMembers({"ada-lovelace-king"})

    assert await MemberService(members)._unique_slug("ada-lovelace") == "ada-lovelace"


async def test_a_claimed_profile_is_written_under_the_free_slug() -> None:
    """End to end through the use case that names a member, not just the helper."""
    members = SlugMembers({"ada-lovelace"})

    await MemberService(members).create_self_profile(
        SelfProfileCreate(name="Ada Lovelace", class_id=85, major="Maths"),
        email="ada@cdtm.com",
        avatar_url=None,
    )

    assert members.written.slug == "ada-lovelace-2"
