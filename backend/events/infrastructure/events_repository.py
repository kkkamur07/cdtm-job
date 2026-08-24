from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.mapping import dump_for_db
from backend.core.page import PageResult
from backend.core.sql import page_with_total
from backend.events.application.commands import EventCreate, EventUpdate
from backend.events.domain import Event, EventSummary, RsvpStatus
from backend.events.infrastructure.orm_models import EventRow, EventRsvpRow
from infrastructure.repository import run_db, utc_now

#: The three counted fields are the query's own, not columns of ``events``.
_COUNTED = ("going_count", "interested_count", "my_rsvp")

#: The stored half of a calendar row, column by column. Taken from the domain summary rather
#: than written out again, so the query and the model it fills cannot drift apart.
_SUMMARY_FIELDS = tuple(f for f in EventSummary.model_fields if f not in _COUNTED)


def _counts(viewer: UUID | None) -> tuple:
    """Going, interested and this viewer's own answer, as three correlated subqueries."""
    going = (
        select(func.count())
        .where(EventRsvpRow.event_id == EventRow.id, EventRsvpRow.status == "going")
        .correlate(EventRow)
        .scalar_subquery()
    )
    interested = (
        select(func.count())
        .where(EventRsvpRow.event_id == EventRow.id, EventRsvpRow.status == "interested")
        .correlate(EventRow)
        .scalar_subquery()
    )
    mine = (
        select(EventRsvpRow.status)
        .where(EventRsvpRow.event_id == EventRow.id, EventRsvpRow.member_id == viewer)
        .correlate(EventRow)
        .scalar_subquery()
        if viewer is not None
        else func.cast(None, EventRsvpRow.status.type)
    )
    return (going.label("going"), interested.label("interested"), mine.label("mine"))


def _summary_select(viewer: UUID | None) -> Select:
    """The list query's SELECT list: a calendar row's columns, the counts, and nothing else.

    ``select(EventRow, ...)`` fetched ``description`` on every row of every page and
    validated it into a full ``Event`` the response model then dropped. A bare ``defer()``
    would not do: building the model reads the attribute, and a deferred column load is a
    lazy load, so it would cost one extra SELECT per row instead.

    A function rather than a module constant because the viewer is part of it, and so
    ``tests/unit/test_events_list_query.py`` can compile it and check what it asks for.
    """
    return select(*(getattr(EventRow, name) for name in _SUMMARY_FIELDS), *_counts(viewer))


class SqlEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    def _with_counts(self, viewer: UUID | None) -> Select:
        """The whole aggregate plus the counts. Used by every read of a single event."""
        return select(EventRow, *_counts(viewer))

    @staticmethod
    def _to_event(row: EventRow, going: int, interested: int, mine: str | None) -> Event:
        return Event(
            id=row.id,
            title=row.title,
            description=row.description,
            kind=row.kind,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            location=row.location,
            url=row.url,
            created_by_member_id=row.created_by_member_id,
            is_published=row.is_published,
            going_count=int(going or 0),
            interested_count=int(interested or 0),
            my_rsvp=RsvpStatus(mine) if mine else None,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_summary(row: tuple) -> EventSummary:
        *stored, going, interested, mine = row
        return EventSummary(
            **dict(zip(_SUMMARY_FIELDS, stored, strict=True)),
            going_count=int(going or 0),
            interested_count=int(interested or 0),
            my_rsvp=RsvpStatus(mine) if mine else None,
        )

    async def list(
        self, *, skip: int, limit: int, upcoming_only: bool, viewer_member_id: UUID | None
    ) -> PageResult[EventSummary]:
        async def go() -> PageResult[EventSummary]:
            stmt = _summary_select(viewer_member_id).where(EventRow.is_published.is_(True))
            if upcoming_only:
                stmt = stmt.where(func.coalesce(EventRow.ends_at, EventRow.starts_at) >= func.now())
            order = EventRow.starts_at.asc() if upcoming_only else EventRow.starts_at.desc()
            rows, total = await page_with_total(
                self._s, stmt.order_by(order), skip=skip, limit=limit
            )
            return PageResult(items=[self._to_summary(row) for row in rows], total=total)

        return await run_db("events.list", go, session=self._s)

    async def get(self, event_id: UUID, viewer_member_id: UUID | None) -> Event | None:
        async def go() -> Event | None:
            res = await self._s.execute(
                self._with_counts(viewer_member_id).where(EventRow.id == event_id)
            )
            row = res.first()
            return self._to_event(*row) if row else None

        return await run_db("events.get", go, session=self._s)

    async def create(self, payload: EventCreate, created_by_member_id: UUID | None) -> Event:
        async def go() -> Event:
            row = EventRow(**dump_for_db(payload), created_by_member_id=created_by_member_id)
            row.kind = payload.kind.value
            self._s.add(row)
            await self._s.commit()
            return await self.get(row.id, created_by_member_id)  # type: ignore[return-value]

        return await run_db("events.create", go, session=self._s)

    async def update(self, event_id: UUID, payload: EventUpdate) -> Event | None:
        async def go() -> Event | None:
            row = await self._s.get(EventRow, event_id)
            if row is None:
                return None
            for k, v in dump_for_db(payload, exclude_unset=True).items():
                setattr(row, k, v.value if hasattr(v, "value") else v)
            row.updated_at = utc_now()
            await self._s.commit()
            return await self.get(event_id, None)

        return await run_db("events.update", go, session=self._s)

    async def delete(self, event_id: UUID) -> bool:
        async def go() -> bool:
            res = await self._s.execute(delete(EventRow).where(EventRow.id == event_id))
            await self._s.commit()
            return bool(res.rowcount)

        return await run_db("events.delete", go, session=self._s)

    async def set_rsvp(self, event_id: UUID, member_id: UUID, status: RsvpStatus | None) -> None:
        async def go() -> None:
            row = await self._s.get(EventRsvpRow, (event_id, member_id))
            if status is None:
                if row is not None:
                    await self._s.delete(row)
            elif row is None:
                self._s.add(
                    EventRsvpRow(event_id=event_id, member_id=member_id, status=status.value)
                )
            else:
                row.status = status.value
            await self._s.commit()

        await run_db("events.rsvp", go, session=self._s)
