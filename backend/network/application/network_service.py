"""Saved people and intro requests: who may save whom, and who may answer a request.

The rows this context owns hold member ids and nothing else. The names and faces shown
next to them are read through ``MemberDirectory``, and putting the two together is this
service's job rather than the repository's: the repository owns one table, the use case
owns the answer.
"""

from __future__ import annotations

from uuid import UUID

from backend.core.actor import Actor
from backend.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from backend.core.page import PageResult
from backend.network.application.commands import IntroRequestCreate, IntroRespond, SaveMember
from backend.network.application.ports import (
    IntroRequestView,
    MemberDirectory,
    NetworkRepository,
    SavedMemberView,
)
from backend.network.domain import IntroRequest, IntroStatus, MemberCard

#: Shown in place of a card for a member who has since been removed from the directory. A
#: saved row outliving its member is rare and not worth a 500, but it must not be silently
#: dropped either: the row is still there and the member still saved somebody.
_UNKNOWN = "Unknown member"


class NetworkService:
    def __init__(self, network: NetworkRepository, members: MemberDirectory) -> None:
        self._network = network
        self._members = members

    # ---- saved --------------------------------------------------------------------------

    async def list_saved(
        self, actor: Actor, *, skip: int, limit: int
    ) -> PageResult[SavedMemberView]:
        page = await self._network.list_saved(actor.require_member(), skip=skip, limit=limit)
        cards = await self._cards([r.saved_member_id for r in page.items])
        return PageResult(
            items=[SavedMemberView(saved=r, member=cards[r.saved_member_id]) for r in page.items],
            total=page.total,
        )

    async def save(
        self, actor: Actor, saved_member_id: UUID, payload: SaveMember
    ) -> SavedMemberView:
        own = actor.require_member()
        if own == saved_member_id:
            raise ValidationError("you cannot save yourself")
        if not await self._members.exists(saved_member_id):
            raise NotFoundError("member not found")
        saved = await self._network.save(own, saved_member_id, payload.note)
        cards = await self._cards([saved_member_id])
        return SavedMemberView(saved=saved, member=cards[saved_member_id])

    async def unsave(self, actor: Actor, saved_member_id: UUID) -> None:
        if not await self._network.unsave(actor.require_member(), saved_member_id):
            raise NotFoundError("not in your saved people")

    # ---- intros -------------------------------------------------------------------------

    async def list_intros(
        self, actor: Actor, *, skip: int, limit: int
    ) -> PageResult[IntroRequestView]:
        page = await self._network.list_intros(actor.require_member(), skip=skip, limit=limit)
        rows = page.items
        ids = [r.requester_member_id for r in rows] + [r.target_member_id for r in rows]
        cards = await self._cards(ids)
        return PageResult(
            items=[
                IntroRequestView(
                    request=r,
                    requester=cards[r.requester_member_id],
                    target=cards[r.target_member_id],
                )
                for r in rows
            ],
            total=page.total,
        )

    async def request_intro(self, actor: Actor, payload: IntroRequestCreate) -> IntroRequest:
        own = actor.require_member()
        if own == payload.target_member_id:
            raise ValidationError("you cannot request an intro to yourself")
        if not await self._members.exists(payload.target_member_id):
            raise NotFoundError("member not found")
        return await self._network.create_intro(own, payload.target_member_id, payload.message)

    async def respond_intro(
        self, actor: Actor, request_id: UUID, payload: IntroRespond
    ) -> IntroRequest:
        own = actor.require_member()
        req = await self._network.get_intro(request_id)
        if req is None:
            raise NotFoundError("intro request not found")
        if req.status != IntroStatus.PENDING:
            raise ConflictError("intro request is already resolved")
        if payload.status == IntroStatus.WITHDRAWN:
            if req.requester_member_id != own and not actor.is_admin:
                raise ForbiddenError("only the requester can withdraw")
        elif payload.status in (IntroStatus.ACCEPTED, IntroStatus.DECLINED):
            if req.target_member_id != own and not actor.is_admin:
                raise ForbiddenError("only the target can respond")
        else:
            raise ValidationError("status must be accepted, declined or withdrawn")
        updated = await self._network.set_intro_status(request_id, payload.status)
        if updated is None:
            # Withdrawn or deleted between the read above and this write.
            raise NotFoundError("intro request not found")
        return updated

    # ---- internals ----------------------------------------------------------------------

    async def _cards(self, ids: list[UUID]) -> dict[UUID, MemberCard]:
        cards = await self._members.cards(ids)
        for member_id in ids:
            cards.setdefault(member_id, MemberCard(id=member_id, slug="", name=_UNKNOWN))
        return cards
