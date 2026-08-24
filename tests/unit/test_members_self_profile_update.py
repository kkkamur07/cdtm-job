"""Editing your own profile writes the hand-maintained fields and nothing else.

The regression these guard against: an edit that reached ``upsert_member`` (the loader's
path) would replace positions, educations and CA detail, silently wiping a member's scraped
work history the moment they fixed a typo in their headline. ``update_self_profile`` must go
through ``update_profile`` instead, which touches only the scalar columns and the class
membership. A fake repository records the call; no database is touched here (the live,
non-destructive behaviour is exercised end-to-end against Postgres elsewhere).
"""

from __future__ import annotations

import uuid

import pytest

from backend.core.exceptions import NotFoundError
from backend.members.application.commands import SelfProfileUpdate
from backend.members.application.member_service import MemberService
from backend.members.domain import ClassRef


class RecordingMembers:
    def __init__(self) -> None:
        self.update_calls: list[dict] = []
        self.upsert_calls: int = 0

    async def list_classes(self) -> list[ClassRef]:
        return [
            ClassRef(id=85, label="Spring 2019", season="Spring", year=2019, location=None),
            ClassRef(id=109, label="Fall 2026", season="Fall", year=2026, location=None),
        ]

    async def update_profile(self, member_id, **fields) -> None:
        self.update_calls.append({"member_id": member_id, **fields})

    async def upsert_member(self, payload) -> uuid.UUID:  # pragma: no cover - must not be called
        self.upsert_calls += 1
        return uuid.uuid4()


async def test_update_goes_through_update_profile_not_upsert() -> None:
    repository = RecordingMembers()
    member_id = uuid.uuid4()

    await MemberService(repository).update_self_profile(
        member_id,
        SelfProfileUpdate(name="Ada Lovelace", class_id=85, major="Maths", headline="Analyst"),
    )

    # The scrape-replacing path was never taken.
    assert repository.upsert_calls == 0
    (call,) = repository.update_calls
    assert call["member_id"] == member_id
    # The chosen class is resolved to its label so the card and the filter agree.
    assert call["class_id"] == 85
    assert call["class_label"] == "Spring 2019"
    # The name is split for search, like the loader does.
    assert call["name"] == "Ada Lovelace"
    assert call["first_name"] == "Ada"
    assert call["last_name"] == "Lovelace"
    assert call["headline"] == "Analyst"


async def test_update_rejects_an_unknown_class() -> None:
    repository = RecordingMembers()

    with pytest.raises(NotFoundError):
        await MemberService(repository).update_self_profile(
            uuid.uuid4(),
            SelfProfileUpdate(name="Grace Hopper", class_id=999, major="CS"),
        )

    assert repository.update_calls == []
