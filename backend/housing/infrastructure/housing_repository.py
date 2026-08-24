from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.mapping import dump_for_db
from backend.core.page import PageResult
from backend.core.sql import ilike_contains, page_with_total
from backend.housing.application.commands import HousingCreate, HousingUpdate
from backend.housing.application.ports import HousingFilters
from backend.housing.domain import HousingListing, HousingListingSummary
from backend.housing.infrastructure.orm_models import HousingListingRow
from infrastructure.repository import run_db, utc_now

#: The board's card, column by column. Taken from the domain summary rather than written out
#: again, so the query and the model it fills cannot drift apart.
_SUMMARY_FIELDS = tuple(HousingListingSummary.model_fields)


def _summary_select() -> Select:
    """The list query's SELECT list: the card's columns and nothing else.

    ``select(HousingListingRow)`` fetched ``description`` too, on every row of every page,
    and validated it into a full ``HousingListing`` the response model then dropped. A bare
    ``defer()`` would not do: building the model reads the attribute, and a deferred column
    load is a lazy load, so it would cost one extra SELECT per row instead.

    A function rather than a module constant so the statement is fresh per call, and so
    ``tests/unit/test_housing_list_query.py`` can compile it and check what it asks for.
    """
    return select(*(getattr(HousingListingRow, name) for name in _SUMMARY_FIELDS))


#: What people write when the column is null. ``furnished`` was added after the board had
#: listings on it, so every row written before the migration answers "did not say"; those
#: rows are still matched on the words in the title and the description rather than being
#: dropped from a "furnished" search. A row that answered the question is taken at its word.
_FURNISHED_WORDS = ("furnished", "moebliert", "möbliert", "mobliert")


class SqlHousingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    def _apply(self, stmt: Select, f: HousingFilters) -> Select:
        if f.kind is not None:
            stmt = stmt.where(HousingListingRow.kind == f.kind.value)
        if f.city:
            stmt = stmt.where(HousingListingRow.city.ilike(ilike_contains(f.city)))
        if f.district:
            stmt = stmt.where(HousingListingRow.area.ilike(ilike_contains(f.district)))
        if f.status is not None:
            stmt = stmt.where(HousingListingRow.status == f.status.value)
        if f.member_id is not None:
            stmt = stmt.where(HousingListingRow.member_id == f.member_id)
        if f.min_price is not None:
            stmt = stmt.where(HousingListingRow.price_eur >= f.min_price)
        if f.max_price is not None:
            # A listing with no price is not "cheap enough", it is unknown; excluding it
            # keeps "under 900" an answer the member can trust.
            stmt = stmt.where(HousingListingRow.price_eur <= f.max_price)
        if f.available_from is not None:
            stmt = stmt.where(
                or_(
                    HousingListingRow.available_from.is_(None),
                    HousingListingRow.available_from <= f.available_from,
                )
            )
        if f.available_until is not None:
            stmt = stmt.where(
                or_(
                    HousingListingRow.available_until.is_(None),
                    HousingListingRow.available_until >= f.available_until,
                )
            )
        if f.min_rooms is not None:
            stmt = stmt.where(HousingListingRow.rooms >= f.min_rooms)
        if f.furnished is not None:
            said_so = or_(
                *[
                    or_(
                        HousingListingRow.title.ilike(ilike_contains(w)),
                        HousingListingRow.description.ilike(ilike_contains(w)),
                    )
                    for w in _FURNISHED_WORDS
                ]
            )
            unanswered = HousingListingRow.furnished.is_(None)
            stmt = stmt.where(
                or_(
                    HousingListingRow.furnished.is_(f.furnished),
                    and_(unanswered, said_so if f.furnished else ~said_so),
                )
            )
        if not f.include_expired:
            stmt = stmt.where(
                or_(
                    HousingListingRow.expires_at.is_(None),
                    HousingListingRow.expires_at > func.now(),
                )
            )
        if f.q:
            stmt = stmt.where(
                or_(
                    HousingListingRow.title.ilike(ilike_contains(f.q)),
                    HousingListingRow.description.ilike(ilike_contains(f.q)),
                    HousingListingRow.area.ilike(ilike_contains(f.q)),
                )
            )
        return stmt

    async def list(
        self, *, skip: int, limit: int, filters: HousingFilters
    ) -> PageResult[HousingListingSummary]:
        """A page of cards. ``q`` and the furnished fallback still read the description in
        the WHERE clause; the SELECT list simply never carries it back."""

        async def go() -> PageResult[HousingListingSummary]:
            stmt = self._apply(_summary_select(), filters)
            rows, total = await page_with_total(
                self._s,
                stmt.order_by(HousingListingRow.created_at.desc()),
                skip=skip,
                limit=limit,
            )
            return PageResult(
                items=[
                    HousingListingSummary(**dict(zip(_SUMMARY_FIELDS, row, strict=True)))
                    for row in rows
                ],
                total=total,
            )

        return await run_db("housing.list", go, session=self._s)

    async def get(self, listing_id: UUID) -> HousingListing | None:
        row = await run_db(
            "housing.get", lambda: self._s.get(HousingListingRow, listing_id), session=self._s
        )
        return HousingListing.model_validate(row) if row else None

    async def create(
        self, member_id: UUID, payload: HousingCreate, *, expires_at: datetime
    ) -> HousingListing:
        async def go() -> HousingListing:
            values = dump_for_db(payload)
            values["kind"] = payload.kind.value
            row = HousingListingRow(**values, member_id=member_id, expires_at=expires_at)
            self._s.add(row)
            await self._s.commit()
            await self._s.refresh(row)
            return HousingListing.model_validate(row)

        return await run_db("housing.create", go, session=self._s)

    async def update(self, listing_id: UUID, payload: HousingUpdate) -> HousingListing | None:
        async def go() -> HousingListing | None:
            row = await self._s.get(HousingListingRow, listing_id)
            if row is None:
                return None
            for k, v in dump_for_db(payload, exclude_unset=True).items():
                setattr(row, k, v.value if hasattr(v, "value") else v)
            row.updated_at = utc_now()
            await self._s.commit()
            await self._s.refresh(row)
            return HousingListing.model_validate(row)

        return await run_db("housing.update", go, session=self._s)

    async def renew(self, listing_id: UUID, *, expires_at: datetime) -> HousingListing | None:
        async def go() -> HousingListing | None:
            row = await self._s.get(HousingListingRow, listing_id)
            if row is None:
                return None
            row.expires_at = expires_at
            row.status = "open"
            row.updated_at = utc_now()
            await self._s.commit()
            await self._s.refresh(row)
            return HousingListing.model_validate(row)

        return await run_db("housing.renew", go, session=self._s)

    async def record_view(self, listing_id: UUID) -> None:
        """One UPDATE, no read-modify-write.

        A view is not part of anybody's use case and must not fail the request that caused
        it, so it commits on its own and a missing listing is simply zero rows.
        """

        async def go() -> None:
            await self._s.execute(
                update(HousingListingRow)
                .where(HousingListingRow.id == listing_id)
                .values(view_count=HousingListingRow.view_count + 1)
            )
            await self._s.commit()

        await run_db("housing.record_view", go, session=self._s)

    async def delete(self, listing_id: UUID) -> bool:
        async def go() -> bool:
            res = await self._s.execute(
                delete(HousingListingRow).where(HousingListingRow.id == listing_id)
            )
            await self._s.commit()
            return bool(res.rowcount)

        return await run_db("housing.delete", go, session=self._s)
