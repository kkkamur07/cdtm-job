from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.network.domain import IntroRequest, IntroStatus, SavedMember
from backend.network.infrastructure.orm_models import IntroRequestRow, SavedMemberRow
from infrastructure.repository import run_db, utc_now


class SqlNetworkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_saved(self, owner_member_id: UUID) -> list[SavedMember]:
        """The rows only. The cards next to them are read through ``MemberDirectory``."""

        async def go() -> list[SavedMember]:
            rows = (
                await self._s.scalars(
                    select(SavedMemberRow)
                    .where(SavedMemberRow.owner_member_id == owner_member_id)
                    .order_by(SavedMemberRow.created_at.desc())
                )
            ).all()
            return [SavedMember.model_validate(r) for r in rows]

        return await run_db("saved.list", go, session=self._s)

    async def get_saved(self, owner_member_id: UUID, saved_member_id: UUID) -> SavedMember | None:
        row = await run_db(
            "saved.get",
            lambda: self._s.get(SavedMemberRow, (owner_member_id, saved_member_id)),
            session=self._s,
        )
        return SavedMember.model_validate(row) if row else None

    async def save(
        self, owner_member_id: UUID, saved_member_id: UUID, note: str | None
    ) -> SavedMember:
        async def go() -> SavedMember:
            row = await self._s.get(SavedMemberRow, (owner_member_id, saved_member_id))
            if row is None:
                row = SavedMemberRow(
                    owner_member_id=owner_member_id, saved_member_id=saved_member_id, note=note
                )
                self._s.add(row)
            else:
                row.note = note
            await self._s.commit()
            await self._s.refresh(row)
            return SavedMember.model_validate(row)

        return await run_db("saved.save", go, session=self._s)

    async def unsave(self, owner_member_id: UUID, saved_member_id: UUID) -> bool:
        async def go() -> bool:
            res = await self._s.execute(
                delete(SavedMemberRow).where(
                    SavedMemberRow.owner_member_id == owner_member_id,
                    SavedMemberRow.saved_member_id == saved_member_id,
                )
            )
            await self._s.commit()
            return bool(res.rowcount)

        return await run_db("saved.unsave", go, session=self._s)

    async def list_intros(self, member_id: UUID) -> list[IntroRequest]:
        """Both directions: the ones this member sent and the ones they were sent."""

        async def go() -> list[IntroRequest]:
            rows = (
                await self._s.scalars(
                    select(IntroRequestRow)
                    .where(
                        or_(
                            IntroRequestRow.requester_member_id == member_id,
                            IntroRequestRow.target_member_id == member_id,
                        )
                    )
                    .order_by(IntroRequestRow.created_at.desc())
                )
            ).all()
            return [IntroRequest.model_validate(r) for r in rows]

        return await run_db("intros.list", go, session=self._s)

    async def get_intro(self, request_id: UUID) -> IntroRequest | None:
        row = await run_db(
            "intros.get", lambda: self._s.get(IntroRequestRow, request_id), session=self._s
        )
        return IntroRequest.model_validate(row) if row else None

    async def create_intro(
        self, requester_member_id: UUID, target_member_id: UUID, message: str
    ) -> IntroRequest:
        async def go() -> IntroRequest:
            row = IntroRequestRow(
                requester_member_id=requester_member_id,
                target_member_id=target_member_id,
                message=message,
            )
            self._s.add(row)
            await self._s.commit()
            await self._s.refresh(row)
            return IntroRequest.model_validate(row)

        return await run_db("intros.create", go, session=self._s)

    async def set_intro_status(self, request_id: UUID, status: IntroStatus) -> IntroRequest | None:
        """None when the request is gone, which the service turns into a 404.

        The row was read and checked a moment ago, but "a moment ago" is not a lock: the
        target can withdraw or an admin can delete between the two statements. Writing
        through the missing row raised an AttributeError nothing maps, so a race answered
        500 where it means 404.
        """

        async def go() -> IntroRequest | None:
            row = await self._s.get(IntroRequestRow, request_id)
            if row is None:
                return None
            row.status = status.value
            row.responded_at = utc_now()
            await self._s.commit()
            await self._s.refresh(row)
            return IntroRequest.model_validate(row)

        return await run_db("intros.set_status", go, session=self._s)
