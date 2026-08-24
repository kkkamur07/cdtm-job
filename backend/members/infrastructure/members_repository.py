from __future__ import annotations

from uuid import UUID

from sqlalchemy import String, column, delete, distinct, func, or_, select, text, true, values
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer, selectinload

from backend.core.exceptions import NotFoundError
from backend.core.page import PageResult
from backend.core.sql import ilike_contains, page_with_total
from backend.members.application.commands import ClassImport, MemberImport
from backend.members.application.ports import Facets, MemberFilters
from backend.members.domain import ClassRef, Member, MemberProfile
from backend.members.infrastructure._mappers import build_search_text, to_member, to_profile
from backend.members.infrastructure._member_query import apply_member_filters
from backend.members.infrastructure.orm_models import (
    CaDetailRow,
    ClassRow,
    EducationRow,
    MemberClassRow,
    MemberEntryRow,
    MemberRow,
    PositionRow,
)
from infrastructure.repository import run_db, utc_now

#: Ceiling on ``matching_ids``. The ids travel into the Paths flow as an ``IN`` list, and a
#: statement carrying the whole roster is neither fast nor a better picture.
MAX_MATCHING_IDS = 5_000


def _order_by(f: MemberFilters) -> list:
    """Sort order for a directory page.

    "relevance" is the historical default and stays the behaviour when no sort is asked
    for: an exact-ish name hit floats to the top of a free-text search, everything else is
    alphabetical. There is no score to sort by, and inventing one would make the order
    unstable between pages.
    """
    if f.sort == "name":
        return [MemberRow.name]
    if f.sort == "class":
        return [MemberRow.class_label.desc().nullslast(), MemberRow.name]
    if f.q:
        return [MemberRow.name.ilike(ilike_contains(f.q.strip())).desc(), MemberRow.name]
    return [MemberRow.name]


#: The relationships a full profile is made of, and the search haystack with it. They are
#: ``lazy="raise"`` on the model so a list query cannot pull them by accident; every query
#: that genuinely needs them says so here.
def _profile_loads() -> list:
    return [
        selectinload(MemberRow.positions),
        selectinload(MemberRow.educations),
        selectinload(MemberRow.ca_detail),
    ]


#: A directory card never reads the haystack, and it is the widest column on the table
#: (1,186 bytes on average, 5,319 at the top). Deferring it keeps a 60-row page from
#: shipping 70 KB nobody looks at.
def _card_loads() -> list:
    return [defer(MemberRow.search_text)]


class SqlMemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ---- queries ------------------------------------------------------------------------

    async def search(
        self, *, skip: int, limit: int, filters: MemberFilters, viewer_member_id: UUID | None
    ) -> PageResult[Member]:
        async def go() -> PageResult[Member]:
            base = apply_member_filters(select(MemberRow), filters).options(*_card_loads())
            rows, total = await page_with_total(
                self._s, base.order_by(*_order_by(filters)), skip=skip, limit=limit
            )
            members = [r[0] for r in rows]
            claimed = await self._claimed_ids([m.id for m in members])
            return PageResult(
                items=[to_member(m, is_claimed=m.id in claimed) for m in members],
                total=total,
            )

        return await run_db("members.search", go, session=self._s)

    async def _claimed_ids(self, ids: list[UUID]) -> set[UUID]:
        if not ids:
            return set()
        res = await self._s.execute(
            text("select member_id from accounts where member_id = any(:ids)"), {"ids": ids}
        )
        return {r[0] for r in res}

    async def matching_ids(self, filters: MemberFilters) -> list[UUID]:
        """Every member id the filters select, unpaged, up to ``MAX_MATCHING_IDS``.

        The Paths flow is drawn over a whole cohort, not a page of it, and Paths cannot
        build a member WHERE clause of its own without importing this context. So it asks
        for the ids and narrows its own aggregate by them. The directory is a few thousand
        rows; a list of UUIDs that size is cheaper than teaching two contexts one query.

        The ceiling is there because these ids become an ``IN`` list inside the flow's
        aggregate: a question that matches everybody would otherwise bind the whole roster
        into that statement, and the picture a Sankey draws over more than five thousand
        people is not a different picture.
        """

        async def go() -> list[UUID]:
            stmt = apply_member_filters(select(MemberRow.id), filters).limit(MAX_MATCHING_IDS)
            rows = await self._s.scalars(stmt)
            return list(rows.all())

        return await run_db("members.matching_ids", go, session=self._s)

    async def viewer_context(self, member_id: UUID) -> tuple[str | None, str | None, int | None]:
        """(class label, location, latest class year) for the member asking a question.

        One statement instead of the full profile load the Ask used to do for three
        values: ``get_by_id`` is a row, three eager loads, the claimed-ids probe and a
        positions/educations fetch, all discarded here. The Entry's location wins over the
        scrape's, the same way ``to_member`` resolves it.
        """

        async def go() -> tuple[str | None, str | None, int | None]:
            year = (
                select(func.max(ClassRow.year))
                .select_from(MemberClassRow)
                .join(ClassRow, ClassRow.id == MemberClassRow.class_id)
                .where(MemberClassRow.member_id == MemberRow.id)
                .correlate(MemberRow)
                .scalar_subquery()
            )
            entry_location = (
                select(MemberEntryRow.location)
                .where(MemberEntryRow.member_id == MemberRow.id)
                .correlate(MemberRow)
                .scalar_subquery()
            )
            row = (
                await self._s.execute(
                    select(
                        MemberRow.class_label,
                        func.coalesce(func.nullif(entry_location, ""), MemberRow.location).label(
                            "location"
                        ),
                        year.label("class_year"),
                    ).where(MemberRow.id == member_id)
                )
            ).first()
            if row is None:
                return (None, None, None)
            return (row[0], row[1], int(row[2]) if row[2] is not None else None)

        return await run_db("members.viewer_context", go, session=self._s)

    async def get_by_slug(self, slug: str) -> MemberProfile | None:
        async def go() -> MemberProfile | None:
            row = await self._s.scalar(
                select(MemberRow).where(MemberRow.slug == slug).options(*_profile_loads())
            )
            if row is None:
                return None
            claimed = await self._claimed_ids([row.id])
            return to_profile(row, is_claimed=row.id in claimed)

        return await run_db("members.get_by_slug", go, session=self._s)

    async def get_by_id(self, member_id: UUID) -> MemberProfile | None:
        async def go() -> MemberProfile | None:
            # A select rather than ``Session.get``: get returns an instance the identity map
            # already holds without emitting SQL, and would hand back one whose positions a
            # directory query left unloaded.
            row = await self._s.scalar(
                select(MemberRow).where(MemberRow.id == member_id).options(*_profile_loads())
            )
            if row is None:
                return None
            claimed = await self._claimed_ids([row.id])
            return to_profile(row, is_claimed=row.id in claimed)

        return await run_db("members.get", go, session=self._s)

    async def get_many(self, ids: list[UUID]) -> list[Member]:
        """Member cards for a set of ids, in the order asked for; unknown ids are skipped."""
        if not ids:
            return []

        async def go() -> list[Member]:
            rows = (
                await self._s.scalars(
                    select(MemberRow).where(MemberRow.id.in_(ids)).options(*_card_loads())
                )
            ).all()
            claimed = await self._claimed_ids([r.id for r in rows])
            by_id = {r.id: to_member(r, is_claimed=r.id in claimed) for r in rows}
            return [by_id[i] for i in ids if i in by_id]

        return await run_db("members.get_many", go, session=self._s)

    async def one_member_per_company(self, companies: list[str]) -> list[tuple[str, UUID, int]]:
        """(company, member id, how many match) for each name that matches anybody.

        One statement for the whole list: the names go in as a VALUES table and each one
        picks its member through a LATERAL join, so a page with fifty companies on it costs
        one query instead of fifty. The predicate is the same one ``?company=`` uses, so
        the batched answer and the single-company search never disagree. ``count(*) OVER ()``
        is evaluated before LIMIT, which is how one row can still report the full tally.
        """
        if not companies:
            return []

        async def go() -> list[tuple[str, UUID, int]]:
            # Escaping happens here rather than in SQL: the pattern travels as its own
            # bound column, so a name containing % or _ stays a literal name.
            wanted = values(column("name", String), column("pattern", String), name="wanted").data(
                [(c, ilike_contains(c)) for c in companies]
            )
            pick = (
                select(MemberRow.id.label("id"), func.count().over().label("total"))
                .where(
                    or_(
                        MemberRow.current_company.ilike(wanted.c.pattern),
                        MemberRow.search_text.ilike(func.lower(wanted.c.pattern)),
                    )
                )
                .order_by(MemberRow.name)
                .limit(1)
                .lateral("pick")
            )
            stmt = select(wanted.c.name, pick.c.id, pick.c.total).select_from(
                wanted.join(pick, true())
            )
            rows = (await self._s.execute(stmt)).all()
            return [(name, member_id, total) for name, member_id, total in rows]

        return await run_db("members.one_member_per_company", go, session=self._s)

    async def find_id_by_slug(self, slug: str) -> UUID | None:
        return await run_db(
            "members.find_id_by_slug",
            lambda: self._s.scalar(select(MemberRow.id).where(MemberRow.slug == slug)),
            session=self._s,
        )

    async def slugs_for_base(self, base: str) -> list[str]:
        """``base`` and every ``base-<suffix>`` already taken, in one statement.

        The caller wants the first free name in the ``base``, ``base-2``, ``base-3`` series,
        which used to be one ``SELECT`` per candidate. The pattern is safe to build by
        concatenation because ``base`` is a slug (``_slugify`` keeps only ``a-z0-9-``), so it
        carries no ``%`` or ``_`` for LIKE to read as a wildcard. Both arms hit the unique
        index on ``members.slug``: the equality as a lookup, the prefix as a range scan.
        """
        rows = await run_db(
            "members.slugs_for_base",
            lambda: self._s.scalars(
                select(MemberRow.slug).where(
                    or_(MemberRow.slug == base, MemberRow.slug.like(f"{base}-%"))
                )
            ),
            session=self._s,
        )
        return list(rows.all())

    async def list_classes(self) -> list[ClassRef]:
        rows = await run_db(
            "classes.list",
            lambda: self._s.scalars(
                select(ClassRow).order_by(ClassRow.year.desc(), ClassRow.label)
            ),
            session=self._s,
        )
        return [ClassRef.model_validate(r) for r in rows.all()]

    async def list_majors(self) -> list[str]:
        rows = await run_db(
            "members.majors",
            lambda: self._s.scalars(
                select(MemberRow.major)
                .where(MemberRow.major.is_not(None))
                .distinct()
                .order_by(MemberRow.major)
            ),
            session=self._s,
        )
        return [m for m in rows.all() if m]

    async def count(self) -> int:
        n = await run_db(
            "members.count",
            lambda: self._s.scalar(select(func.count(MemberRow.id))),
            session=self._s,
        )
        return int(n or 0)

    async def facets(self) -> Facets:
        """The filter bar's three lists in one round trip.

        The endpoint used to await the classes, the majors and the roster size one after
        the other, which is three sequential round trips for three tiny answers (they
        cannot be gathered: one AsyncSession is one connection and is not concurrency
        safe). Each is an uncorrelated scalar subquery here, so Postgres evaluates all
        three once and returns one row.
        """

        async def go() -> Facets:
            classes = (
                select(
                    func.json_agg(
                        aggregate_order_by(
                            func.json_build_object(
                                "id",
                                ClassRow.id,
                                "label",
                                ClassRow.label,
                                "season",
                                ClassRow.season,
                                "year",
                                ClassRow.year,
                                "location",
                                ClassRow.location,
                            ),
                            ClassRow.year.desc(),
                            ClassRow.label,
                        )
                    )
                )
                .select_from(ClassRow)
                .scalar_subquery()
            )
            majors = (
                select(
                    func.array_agg(aggregate_order_by(distinct(MemberRow.major), MemberRow.major))
                )
                .where(MemberRow.major.is_not(None))
                .scalar_subquery()
            )
            total = select(func.count(MemberRow.id)).scalar_subquery()
            row = (await self._s.execute(select(classes, majors, total))).one()
            return Facets(
                classes=tuple(ClassRef.model_validate(c) for c in (row[0] or [])),
                majors=tuple(m for m in (row[1] or []) if m),
                members_total=int(row[2] or 0),
            )

        return await run_db("members.facets", go, session=self._s)

    # ---- import -------------------------------------------------------------------------

    async def _refresh_haystack(self, member_id: UUID) -> None:
        """Rebuild ``search_text`` after a write, with the rows it is built from loaded.

        ``build_search_text`` reads positions, educations and the Entry. Two of those are
        ``lazy="raise"`` so that no directory query can fetch them by accident, which means
        this write path has to ask for them by name. ``populate_existing`` makes the select
        refresh the instance already in the session, which is what ``Session.refresh`` did
        here before, so the haystack is built from what was just committed and not from
        whatever was in memory when the request started.
        """
        row = await self._s.scalar(
            select(MemberRow)
            .where(MemberRow.id == member_id)
            .options(selectinload(MemberRow.positions), selectinload(MemberRow.educations))
            .execution_options(populate_existing=True)
        )
        if row is not None:
            row.search_text = build_search_text(row)

    async def upsert_classes(self, classes: list[ClassImport]) -> int:
        if not classes:
            return 0

        async def go() -> int:
            stmt = pg_insert(ClassRow).values([c.model_dump() for c in classes])
            stmt = stmt.on_conflict_do_update(
                index_elements=[ClassRow.id],
                set_={
                    "label": stmt.excluded.label,
                    "season": stmt.excluded.season,
                    "year": stmt.excluded.year,
                    "location": stmt.excluded.location,
                },
            )
            await self._s.execute(stmt)
            await self._s.commit()
            return len(classes)

        return await run_db("classes.upsert", go, session=self._s)

    async def upsert_member(self, payload: MemberImport) -> UUID:
        async def go() -> UUID:
            row = await self._s.scalar(select(MemberRow).where(MemberRow.slug == payload.slug))
            if row is None and payload.roster_person_id is not None:
                row = await self._s.scalar(
                    select(MemberRow).where(MemberRow.roster_person_id == payload.roster_person_id)
                )
            if row is None:
                row = MemberRow(slug=payload.slug)
                self._s.add(row)

            scalar_fields = (
                "roster_person_id",
                "name",
                "first_name",
                "last_name",
                "roster_name",
                "headline",
                "summary",
                "location",
                "linkedin_url",
                "avatar_sm_url",
                "avatar_lg_url",
                "avatar_blur",
                "class_label",
                "major",
                "is_ca",
                "ca_alumni",
                "matched",
                "needs_review",
                "current_company",
                "current_title",
                "skills",
                "languages",
                "company_info",
                "linkedin_synced_at",
            )
            for f in scalar_fields:
                setattr(row, f, getattr(payload, f))
            row.slug = payload.slug
            row.roles = [r.value for r in payload.roles]
            row.match_method = payload.match_method.value if payload.match_method else None
            if payload.email:
                row.email = payload.email.lower()
            row.updated_at = utc_now()
            await self._s.flush()

            # classes (replace)
            await self._s.execute(delete(MemberClassRow).where(MemberClassRow.member_id == row.id))
            for cid in dict.fromkeys(payload.class_ids):
                self._s.add(MemberClassRow(member_id=row.id, class_id=cid))

            # positions / educations (replace: they are a snapshot of the scrape)
            await self._s.execute(
                delete(PositionRow).where(
                    PositionRow.member_id == row.id, PositionRow.source == "linkedin"
                )
            )
            for i, p in enumerate(payload.positions):
                self._s.add(
                    PositionRow(
                        member_id=row.id,
                        title=p.title,
                        company=p.company,
                        company_url=p.company_url,
                        description=p.description,
                        location=p.location,
                        start_date=p.start_date,
                        end_date=p.end_date,
                        date_range=p.date_range,
                        is_current=p.is_current,
                        sort_order=i,
                        source="linkedin",
                    )
                )
            await self._s.execute(delete(EducationRow).where(EducationRow.member_id == row.id))
            for i, e in enumerate(payload.educations):
                self._s.add(
                    EducationRow(
                        member_id=row.id,
                        school=e.school,
                        degree=e.degree,
                        date_range=e.date_range,
                        sort_order=i,
                    )
                )

            # CA detail
            await self._s.execute(delete(CaDetailRow).where(CaDetailRow.member_id == row.id))
            if payload.ca is not None:
                self._s.add(
                    CaDetailRow(
                        member_id=row.id,
                        alumni=payload.ca.alumni,
                        about=payload.ca.about,
                        responsibilities=payload.ca.responsibilities,
                        research_fields=payload.ca.research_fields,
                        email=payload.ca.email,
                    )
                )
            await self._s.flush()
            member_id = row.id
            await self._refresh_haystack(member_id)
            await self._s.commit()
            return member_id

        return await run_db("members.upsert", go, session=self._s)

    async def update_profile(
        self,
        member_id: UUID,
        *,
        name: str,
        first_name: str | None,
        last_name: str | None,
        headline: str | None,
        summary: str | None,
        location: str | None,
        linkedin_url: str | None,
        class_id: int,
        class_label: str,
        major: str | None,
        current_company: str | None,
        current_title: str | None,
    ) -> None:
        """Write the fields a member edits by hand, and nothing else.

        Unlike ``upsert_member`` (the loader's path, which replaces positions, educations
        and CA detail because it is re-importing a scrape), this touches only the scalar
        profile columns and the class membership. A member editing their headline does not
        lose their work history. The slug, avatar and e-mail are not arguments, so an edit
        can never change the URL or the identity the Google account established.
        """

        async def go() -> None:
            row = await self._s.get(MemberRow, member_id)
            if row is None:
                raise NotFoundError("member not found")
            row.name = name
            row.first_name = first_name
            row.last_name = last_name
            row.headline = headline
            row.summary = summary
            row.location = location
            row.linkedin_url = linkedin_url
            row.class_label = class_label
            row.major = major
            row.current_company = current_company
            row.current_title = current_title
            row.updated_at = utc_now()
            await self._s.flush()

            await self._s.execute(delete(MemberClassRow).where(MemberClassRow.member_id == row.id))
            self._s.add(MemberClassRow(member_id=row.id, class_id=class_id))

            await self._s.flush()
            await self._refresh_haystack(row.id)
            await self._s.commit()

        await run_db("members.update_profile", go, session=self._s)

    async def set_email(self, member_id: UUID, email: str | None) -> None:
        async def go() -> None:
            row = await self._s.get(MemberRow, member_id)
            if row is None:
                return
            row.email = email.lower() if email else None
            await self._s.commit()

        await run_db("members.set_email", go, session=self._s)

    async def refresh_search_text(self, member_id: UUID) -> None:
        async def go() -> None:
            await self._refresh_haystack(member_id)
            await self._s.commit()

        await run_db("members.refresh_search_text", go, session=self._s)
