"""Persistence and read ports for the network context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from backend.network.domain import IntroRequest, IntroStatus, MemberCard, SavedMember


@dataclass(frozen=True, slots=True)
class SavedMemberView:
    saved: SavedMember
    member: MemberCard


@dataclass(frozen=True, slots=True)
class IntroRequestView:
    request: IntroRequest
    requester: MemberCard
    target: MemberCard


class NetworkRepository(Protocol):
    async def list_saved(self, owner_member_id: UUID) -> list[SavedMember]: ...
    async def get_saved(
        self, owner_member_id: UUID, saved_member_id: UUID
    ) -> SavedMember | None: ...
    async def save(
        self, owner_member_id: UUID, saved_member_id: UUID, note: str | None
    ) -> SavedMember: ...
    async def unsave(self, owner_member_id: UUID, saved_member_id: UUID) -> bool: ...
    async def list_intros(self, member_id: UUID) -> list[IntroRequest]: ...
    async def get_intro(self, request_id: UUID) -> IntroRequest | None: ...
    async def create_intro(
        self, requester_member_id: UUID, target_member_id: UUID, message: str
    ) -> IntroRequest: ...
    async def set_intro_status(
        self, request_id: UUID, status: IntroStatus
    ) -> IntroRequest | None: ...


class MemberDirectory(Protocol):
    """Read-only view into the member tables, the way identity already reads them.

    A saved row and an intro request hold two member ids. Everything the UI puts next to
    them is a card, and this is the only thing this context is allowed to know about a
    person. Implemented with ``text()`` queries; no ORM crosses the boundary.
    """

    async def exists(self, member_id: UUID) -> bool: ...
    async def cards(self, ids: list[UUID]) -> dict[UUID, MemberCard]: ...
