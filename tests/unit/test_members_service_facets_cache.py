"""The filter bar is cached, and a profile write is one of the things that invalidates it.

``facets()`` holds the classes, the majors and the roster size for five minutes, which is
right as long as nothing but the loader writes them. Claiming a profile and editing one
both do: a new member changes the count, and either can introduce a major or move somebody
to another class. Without the clear, a member who just joined was missing from their own
filter bar until the entry expired. A fake repository counts the reads; no database here.
"""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest

from backend.core.cache import clear_all
from backend.members.application.commands import (
    MemberImport,
    SelfProfileCreate,
    SelfProfileUpdate,
)
from backend.members.application.member_service import MemberService
from backend.members.application.ports import Facets
from backend.members.domain import ClassRef


@pytest.fixture(autouse=True)
def _empty_caches():
    clear_all()
    yield
    clear_all()


class CountingMembers:
    """Enough of ``MemberRepository`` for the two profile writes and ``facets``."""

    def __init__(self) -> None:
        self.facet_reads = 0

    async def facets(self) -> Facets:
        self.facet_reads += 1
        return Facets(classes=(), majors=(), members_total=self.facet_reads)

    async def list_classes(self) -> list[ClassRef]:
        return [ClassRef(id=85, label="Spring 2019", season="Spring", year=2019, location=None)]

    async def slugs_for_base(self, base: str) -> list[str]:
        return []

    async def upsert_member(self, payload: MemberImport) -> UUID:
        return uuid.uuid4()

    async def update_profile(self, member_id: UUID, **fields: object) -> None:
        return None


def _create() -> SelfProfileCreate:
    return SelfProfileCreate(name="Ada Lovelace", class_id=85, major="Mathematics")


def _update() -> SelfProfileUpdate:
    return SelfProfileUpdate(name="Ada Lovelace", class_id=85, major="Computer Science")


async def test_claiming_a_profile_drops_the_cached_facets() -> None:
    members = CountingMembers()
    service = MemberService(members)

    first = await service.facets()
    assert (await service.facets()) is first and members.facet_reads == 1

    await service.create_self_profile(_create(), email="ada@cdtm.com", avatar_url=None)

    await service.facets()
    assert members.facet_reads == 2


async def test_editing_a_profile_drops_them_too() -> None:
    members = CountingMembers()
    service = MemberService(members)

    await service.facets()
    assert members.facet_reads == 1

    await service.update_self_profile(uuid.uuid4(), _update())

    await service.facets()
    assert members.facet_reads == 2
