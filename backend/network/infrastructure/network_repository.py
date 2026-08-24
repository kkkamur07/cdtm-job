from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.page import PageResult
from backend.core.sql import page_with_total
from backend.network.domain import IntroRequest, IntroStatus, SavedMember
from backend.network.infrastructure.orm_models import IntroRequestRow, SavedMemberRow
from infrastructure.repository import run_db, utc_now


class SqlNetworkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_saved(
        self, owner_member_id: UUID, *, skip: int, limit: int
    ) -> PageResult[SavedMember]:
        """The rows only. The cards next to them are read through ``MemberDirectory``."""

        async def go() -> PageResult[SavedMember]:
            stmt = (
                select(SavedMemberRow)
                .where(SavedMemberRow.owner_member_id == owner_member_id)
                .order_by(SavedMemberRow.created_at.desc())
            )
            rows, total = await page_with_total(self._s, stmt, skip=skip, limit=limit)
            return PageResult(items=[SavedMember.model_validate(r[0]) for r in rows], total=total)

        return await run_db("saved.list", go, session=self._s)

    async def get_saved(self, owner_member_id: UUID, saved_member_id: UUID) -> SavedMember | None:
        row = await run_db(
            "saved.get",
            lambda: self._s.get(SavedMemberRow, (owner_member_id, saved_member_id)),
            session=self._s,
        )
        return SavedMember.model_validate(row) if row else None

    async def saved_ids(self, owner_member_id: UUID) -> list[UUID]:
        """Every id in this member's shortlist, newest first, unpaged.

        The paged list is for drawing rows; this is for the Save button, which has to know
        exactly who is already saved. Inferring that from the first page said "not saved"
        about everybody past row one hundred. One column, one row per saved person, so the
        answer stays small without a skip and a limit.
        """

        async def go() -> list[UUID]:
            rows = await self._s.execute(
                select(SavedMemberRow.saved_member_id)
                .where(SavedMemberRow.owner_member_id == owner_member_id)
                .order_by(SavedMemberRow.created_at.desc())
            )
            return list(rows.scalars())

        return await run_db("saved.ids", go, session=self._s)

    async def save(
        self,
        owner_member_id: UUID,
        saved_member_id: UUID,
        note: str | None,
        *,
        replace_note: bool,
    ) -> SavedMember:
        """Insert or update the row, touching the note only when the request carried one.

        The Save button sends no note at all, because the card it sits on never had one to
        send. Treating that as ``note=None`` wiped whatever the member had written earlier,
        so an absent field now leaves the stored note where it is and only an explicit
        ``null`` clears it.
        """

        async def go() -> SavedMember:
            row = await self._s.get(SavedMemberRow, (owner_member_id, saved_member_id))
            if row is None:
                row = SavedMemberRow(
                    owner_member_id=owner_member_id, saved_member_id=saved_member_id, note=note
                )
                self._s.add(row)
            elif replace_note:
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

    async def list_intros(
        self, member_id: UUID, *, skip: int, limit: int, with_member_id: UUID | None = None
    ) -> PageResult[IntroRequest]:
        """Both directions: the ones this member sent and the ones they were sent.

        ``with_member_id`` narrows the same list to one other person, in either direction,
        so a profile page can ask "is there already a request between us" without paging
        through a history that has nothing to do with the profile being looked at.
        """

        async def go() -> PageResult[IntroRequest]:
            mine = or_(
                IntroRequestRow.requester_member_id == member_id,
                IntroRequestRow.target_member_id == member_id,
            )
            stmt = select(IntroRequestRow).where(mine)
            if with_member_id is not None:
                stmt = stmt.where(
                    or_(
                        IntroRequestRow.requester_member_id == with_member_id,
                        IntroRequestRow.target_member_id == with_member_id,
                    )
                )
            stmt = stmt.order_by(IntroRequestRow.created_at.desc())
            rows, total = await page_with_total(self._s, stmt, skip=skip, limit=limit)
            return PageResult(items=[IntroRequest.model_validate(r[0]) for r in rows], total=total)

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
