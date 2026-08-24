"""SQLAlchemy implementation of the account persistence port."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import NotFoundError
from backend.core.page import PageResult
from backend.identity.domain import Account, TokenClaims
from backend.identity.infrastructure.orm_models import AccountRow
from infrastructure.repository import run_db, utc_now


class SqlAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_auth_user_id(self, auth_user_id: UUID) -> Account | None:
        row = await run_db(
            "accounts.get_by_auth_user_id",
            lambda: self._s.scalar(
                select(AccountRow).where(AccountRow.auth_user_id == auth_user_id)
            ),
            session=self._s,
        )
        return Account.model_validate(row) if row else None

    async def get_by_id(self, account_id: UUID) -> Account | None:
        row = await run_db(
            "accounts.get", lambda: self._s.get(AccountRow, account_id), session=self._s
        )
        return Account.model_validate(row) if row else None

    async def list_accounts(
        self, *, skip: int, limit: int, unbound_only: bool
    ) -> PageResult[Account]:
        async def go() -> PageResult[Account]:
            stmt = select(AccountRow)
            if unbound_only:
                stmt = stmt.where(AccountRow.member_id.is_(None))
            total = await self._s.scalar(select(func.count()).select_from(stmt.subquery()))
            # Newest first: an admin binding accounts by hand is working through the people
            # who have just signed in and found nothing of their own.
            rows = (
                await self._s.scalars(
                    stmt.order_by(AccountRow.created_at.desc()).offset(skip).limit(limit)
                )
            ).all()
            return PageResult(
                items=[Account.model_validate(r) for r in rows], total=int(total or 0)
            )

        return await run_db("accounts.list", go, session=self._s)

    async def upsert_from_claims(self, claims: TokenClaims, *, is_admin: bool | None) -> Account:
        async def go() -> Account:
            row = await self._s.scalar(
                select(AccountRow).where(AccountRow.auth_user_id == claims.sub)
            )
            now = utc_now()
            if row is None:
                row = AccountRow(
                    auth_user_id=claims.sub,
                    email=claims.email,
                    full_name=claims.full_name,
                    avatar_url=claims.avatar_url,
                    is_admin=bool(is_admin),
                    last_sign_in_at=now,
                )
                self._s.add(row)
            else:
                row.email = claims.email
                if claims.full_name:
                    row.full_name = claims.full_name
                if claims.avatar_url:
                    row.avatar_url = claims.avatar_url
                if is_admin:
                    row.is_admin = True
                row.last_sign_in_at = now
                row.updated_at = now
            await self._s.commit()
            await self._s.refresh(row)
            return Account.model_validate(row)

        return await run_db("accounts.upsert", go, session=self._s)

    async def bind_member(self, account_id: UUID, member_id: UUID) -> Account:
        async def go() -> Account:
            row = await self._s.get(AccountRow, account_id)
            if row is None:
                raise NotFoundError("account not found")
            row.member_id = member_id
            row.updated_at = utc_now()
            await self._s.commit()
            await self._s.refresh(row)
            return Account.model_validate(row)

        return await run_db("accounts.bind_member", go, session=self._s)

    async def set_admin(self, account_id: UUID, is_admin: bool) -> Account:
        async def go() -> Account:
            row = await self._s.get(AccountRow, account_id)
            if row is None:
                raise NotFoundError("account not found")
            row.is_admin = is_admin
            row.updated_at = utc_now()
            await self._s.commit()
            await self._s.refresh(row)
            return Account.model_validate(row)

        return await run_db("accounts.set_admin", go, session=self._s)
