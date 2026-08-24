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

from backend.members.application.member_service import MemberService
from backend.members.domain import Member


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
