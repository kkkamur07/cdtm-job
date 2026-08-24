"""SQLAlchemy implementation of the account persistence port."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import NotFoundError
from backend.core.page import PageResult
from backend.core.sql import page_with_total
from backend.identity.domain import Account, TokenClaims
from backend.identity.infrastructure.orm_models import AccountRow
from infrastructure.repository import run_db, utc_now

#: Default for ``sign_in_touch_seconds``; the real value comes from ``AuthSettings``.
DEFAULT_SIGN_IN_TOUCH_SECONDS = 900


class SqlAccountRepository:
    def __init__(self, session: AsyncSession, *, sign_in_touch_seconds: int | None = None) -> None:
        self._s = session
        self._touch_after = timedelta(
            seconds=(
                DEFAULT_SIGN_IN_TOUCH_SECONDS
                if sign_in_touch_seconds is None
                else sign_in_touch_seconds
            )
        )

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
            # Newest first: an admin binding accounts by hand is working through the people
            # who have just signed in and found nothing of their own.
            rows, total = await page_with_total(
                self._s, stmt.order_by(AccountRow.created_at.desc()), skip=skip, limit=limit
            )
            return PageResult(items=[Account.model_validate(r[0]) for r in rows], total=total)

        return await run_db("accounts.list", go, session=self._s)

    async def upsert_from_claims(self, claims: TokenClaims, *, is_admin: bool | None) -> Account:
        """The sign-in prelude: read the account this token belongs to, writing only if needed.

        Every authenticated request runs this, so it is the one query the whole API pays for
        before it does anything. It used to SELECT, UPDATE, COMMIT and refresh unconditionally,
        which made every GET a write: a row lock on ``accounts``, a WAL record and three extra
        round trips per request. Now the UPDATE happens only when the token actually says
        something new, or when ``last_sign_in_at`` has gone stale enough to be worth restating.

        A duplicate e-mail still surfaces as a ConflictError, because that only arises on a
        commit, and a commit only happens on the paths that change the address.
        """

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
                await self._s.commit()
                # First sign-in only, so the extra round trip is paid once per account:
                # ``created_at`` and ``updated_at`` are server defaults, and reading an
                # unloaded attribute from an async session is an error rather than a query.
                await self._s.refresh(row)
                return Account.model_validate(row)

            changed = self._apply_claims(row, claims, is_admin=is_admin)
            stale = row.last_sign_in_at is None or (now - row.last_sign_in_at) >= self._touch_after
            if changed or stale:
                row.last_sign_in_at = now
                row.updated_at = now
                # expire_on_commit=False on the session factory, so the instance stays
                # populated after the commit and there is nothing to refresh back out of it.
                await self._s.commit()
            return Account.model_validate(row)

        return await run_db("accounts.upsert", go, session=self._s)

    @staticmethod
    def _apply_claims(row: AccountRow, claims: TokenClaims, *, is_admin: bool | None) -> bool:
        """Copy the claim-derived fields onto the row; report whether anything moved.

        Assigning an identical value would still mark the instance dirty and produce an
        UPDATE on flush, so each field is compared before it is written.
        """
        changed = False
        if row.email != claims.email:
            row.email = claims.email
            changed = True
        if claims.full_name and row.full_name != claims.full_name:
            row.full_name = claims.full_name
            changed = True
        if claims.avatar_url and row.avatar_url != claims.avatar_url:
            row.avatar_url = claims.avatar_url
            changed = True
        if is_admin and not row.is_admin:
            row.is_admin = True
            changed = True
        return changed

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
