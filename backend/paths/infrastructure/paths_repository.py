"""The ``member_paths`` aggregate: the Sankey, one member's path, and recomputing it."""

from __future__ import annotations

from enum import IntEnum
from uuid import UUID

from sqlalchemy import Select, func, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.sql import page_with_total
from backend.paths.application.ports import PathFilters
from backend.paths.domain import (
    INTENT_GROUPS,
    NO_INTENT_GROUP,
    MemberPath,
    PathFlow,
    PathLink,
    PathNode,
)
from backend.paths.infrastructure._member_tables import member_classes, member_intents, members
from backend.paths.infrastructure.orm_models import MemberPathRow
from infrastructure.repository import run_db, utc_now

_STAGE_COLUMNS = {
    "study": MemberPathRow.study_group,
    "first_step": MemberPathRow.first_step_group,
    "current": MemberPathRow.current_group,
}

#: The two history-to-history hops of the Sankey. The fourth stage is not a career step and
#: is built separately, because it fans out: one member can be open to six things at once.
_CAREER_HOPS = (
    (("study", MemberPathRow.study_group), ("first_step", MemberPathRow.first_step_group)),
    (("first_step", MemberPathRow.first_step_group), ("current", MemberPathRow.current_group)),
)


class _GroupingSet(IntEnum):
    """Which grouping set a row of the flow aggregate came from.

    Postgres' ``GROUPING(study, first_step, current)`` sets one bit per column that was
    *not* grouped by, most significant first, so each of the six sets has its own number.
    """

    STUDY_TO_FIRST_STEP = 0b001
    STUDY = 0b011
    FIRST_STEP_TO_CURRENT = 0b100
    FIRST_STEP = 0b101
    CURRENT = 0b110
    TOTAL = 0b111


class SqlPathRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    def _apply(self, stmt: Select, f: PathFilters) -> Select:
        if f.class_id is not None:
            stmt = stmt.where(
                select(member_classes.c.member_id)
                .where(
                    member_classes.c.member_id == MemberPathRow.member_id,
                    member_classes.c.class_id == f.class_id,
                )
                .exists()
            )
        if f.study_group:
            stmt = stmt.where(MemberPathRow.study_group == f.study_group)
        if f.first_step_group:
            stmt = stmt.where(MemberPathRow.first_step_group == f.first_step_group)
        if f.current_group:
            stmt = stmt.where(MemberPathRow.current_group == f.current_group)
        if f.member_ids is not None:
            # Ask fills this with every member its question matched, not the page it
            # showed. An empty tuple is a real answer ("nobody"), so it must narrow to
            # nothing rather than be treated as "no filter".
            stmt = stmt.where(MemberPathRow.member_id.in_(list(f.member_ids)))
        return stmt

    async def flow(self, filters: PathFilters) -> PathFlow:
        async def go() -> PathFlow:
            counted, nodes, links = await self._career_stages(filters)
            intent_nodes, intent_links = await self._intent_stage(filters)
            return PathFlow(
                members_counted=counted,
                nodes=nodes + intent_nodes,
                links=links + intent_links,
            )

        return await run_db("paths.flow", go, session=self._s)

    async def _career_stages(
        self, filters: PathFilters
    ) -> tuple[int, list[PathNode], list[PathLink]]:
        """The three history columns, their two hops and the members counted: one statement.

        This used to be six: a ``count(*)``, one ``GROUP BY`` per stage and one per hop, so
        the same table was scanned six times per request for six aggregates over the same
        rows. ``GROUPING SETS`` asks for all six in one pass.

        ``GROUPING(a, b, c)`` comes back as a bitmask saying which columns were *not* in
        the grouping set that produced the row, which is what tells the six sets apart when
        they arrive interleaved. Rows whose group is null are dropped here rather than by a
        WHERE clause, because a grouping-sets query cannot filter one set and not another,
        and a null group has never been drawn.
        """
        study, first_step, current = (
            _STAGE_COLUMNS["study"],
            _STAGE_COLUMNS["first_step"],
            _STAGE_COLUMNS["current"],
        )
        n = func.count().label("n")
        stmt = (
            self._apply(
                select(
                    study,
                    first_step,
                    current,
                    func.grouping(study, first_step, current).label("gset"),
                    n,
                ),
                filters,
            )
            .group_by(
                func.grouping_sets(
                    *[tuple_(col) for col in _STAGE_COLUMNS.values()],
                    *[tuple_(s_col, t_col) for (_, s_col), (_, t_col) in _CAREER_HOPS],
                    # The empty set is the grand total, which is members_counted.
                    text("()"),
                )
            )
            # Biggest box first, then by name. The old six statements ordered on the count
            # alone, so two groups of equal size could swap places between two requests and
            # the drawing would jump; the tie-break costs nothing and stops that.
            .order_by(n.desc(), study, first_step, current)
        )
        rows = (await self._s.execute(stmt)).all()

        counted = 0
        by_stage: dict[str, list[PathNode]] = {stage: [] for stage in _STAGE_COLUMNS}
        by_hop: dict[str, list[PathLink]] = {"study": [], "first_step": []}
        for s_group, f_group, c_group, gset, count in rows:
            bits = _GroupingSet(int(gset))
            if bits is _GroupingSet.TOTAL:
                counted = int(count)
            elif bits is _GroupingSet.STUDY and s_group is not None:
                by_stage["study"].append(PathNode(stage="study", group=s_group, count=int(count)))
            elif bits is _GroupingSet.FIRST_STEP and f_group is not None:
                by_stage["first_step"].append(
                    PathNode(stage="first_step", group=f_group, count=int(count))
                )
            elif bits is _GroupingSet.CURRENT and c_group is not None:
                by_stage["current"].append(
                    PathNode(stage="current", group=c_group, count=int(count))
                )
            elif bits is _GroupingSet.STUDY_TO_FIRST_STEP and None not in (s_group, f_group):
                by_hop["study"].append(
                    PathLink(
                        source_stage="study",
                        source_group=s_group,
                        target_stage="first_step",
                        target_group=f_group,
                        count=int(count),
                    )
                )
            elif bits is _GroupingSet.FIRST_STEP_TO_CURRENT and None not in (f_group, c_group):
                by_hop["first_step"].append(
                    PathLink(
                        source_stage="first_step",
                        source_group=f_group,
                        target_stage="current",
                        target_group=c_group,
                        count=int(count),
                    )
                )
        # Stage order, then hop order, each already sorted by count because the statement is.
        nodes = [node for stage in _STAGE_COLUMNS for node in by_stage[stage]]
        links = by_hop["study"] + by_hop["first_step"]
        return counted, nodes, links

    async def _intent_stage(self, filters: PathFilters) -> tuple[list[PathNode], list[PathLink]]:
        """The "open to" column, and the flow into it from where people are now.

        A member with three intents contributes three links, so these counts do not add up
        to the number of people the way the career stages do. That is what the column is
        for: it answers "of the people who ended up in VC, how many will take a call",
        which is a different question from "where did they go".
        """
        intent_columns = [member_intents.c[field] for field, _ in INTENT_GROUPS]
        joined = self._apply(
            select(MemberPathRow.current_group, *intent_columns)
            .select_from(MemberPathRow)
            .outerjoin(member_intents, member_intents.c.member_id == MemberPathRow.member_id),
            filters,
        )
        # One row per member rather than six grouped counts: a member fans out into every
        # intent they set, and the fan-out has to be counted per member to be able to say
        # "and the ones who set nothing". Three thousand narrow rows is not worth a UNION.
        rows = (await self._s.execute(joined)).mappings().all()

        counts: dict[str, int] = {}
        pair_counts: dict[tuple[str, str], int] = {}
        for row in rows:
            labels = [label for field, label in INTENT_GROUPS if row.get(field)]
            if not labels:
                labels = [NO_INTENT_GROUP]
            current = row["current_group"]
            for label in labels:
                counts[label] = counts.get(label, 0) + 1
                if current:
                    key = (current, label)
                    pair_counts[key] = pair_counts.get(key, 0) + 1

        order = [label for _, label in INTENT_GROUPS] + [NO_INTENT_GROUP]
        nodes = [
            PathNode(stage="intent", group=label, count=counts[label])
            for label in order
            if label in counts
        ]
        links = [
            PathLink(
                source_stage="current",
                source_group=source,
                target_stage="intent",
                target_group=target,
                count=count,
            )
            for (source, target), count in sorted(
                pair_counts.items(), key=lambda kv: kv[1], reverse=True
            )
        ]
        return nodes, links

    async def get(self, member_id: UUID) -> MemberPath | None:
        row = await run_db(
            "paths.get", lambda: self._s.get(MemberPathRow, member_id), session=self._s
        )
        return MemberPath.model_validate(row) if row else None

    async def current_group_of(self, member_id: UUID) -> str | None:
        """What the asker does now, for the directory's Ask. See ``ViewerGroupSource``."""
        return await run_db(
            "paths.current_group_of",
            lambda: self._s.scalar(
                select(MemberPathRow.current_group).where(MemberPathRow.member_id == member_id)
            ),
            session=self._s,
        )

    async def upsert(self, path: MemberPath) -> None:
        async def go() -> None:
            values = path.model_dump(exclude={"computed_at"})
            values["computed_at"] = utc_now()
            stmt = pg_insert(MemberPathRow).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[MemberPathRow.member_id],
                set_={k: getattr(stmt.excluded, k) for k in values if k != "member_id"},
            )
            await self._s.execute(stmt)
            await self._s.commit()

        await run_db("paths.upsert", go, session=self._s)

    async def member_ids_page(
        self, *, stage: str, group: str, filters: PathFilters, skip: int, limit: int
    ) -> tuple[list[UUID], int]:
        """One page of the ids in a box of the Sankey, in card order, with the group's size.

        This used to return every id in the group unpaged, on the grounds that "the ids come
        from this context and the names come from the members context, so no one query can
        order by a column only the other one has". That is not true: ``members`` is already
        one of the metadata-free table handles this context reads (``_member_tables.py``,
        the same seam ``member_classes`` comes through), so the page can be cut in the same
        order the cards are drawn in. Opening a group of four hundred used to ship four
        hundred uuids back to page twenty of them in the loader's ``IN`` list; now twenty
        come back and twenty go into it.

        ``name`` then ``id``: names repeat here (two people called Anna is normal), and an
        ordering that is not total lets Postgres put the same person on two pages.
        """

        async def go() -> tuple[list[UUID], int]:
            col = _STAGE_COLUMNS[stage]
            stmt = (
                self._apply(select(MemberPathRow.member_id), filters)
                .where(col == group)
                .join(members, members.c.id == MemberPathRow.member_id)
                .order_by(members.c.name, members.c.id)
            )
            rows, total = await page_with_total(self._s, stmt, skip=skip, limit=limit)
            return [row[0] for row in rows], total

        return await run_db("paths.member_ids_page", go, session=self._s)

    async def groups(self) -> dict[str, list[str]]:
        """The group names each stage actually has people in.

        One statement rather than a ``SELECT DISTINCT`` per stage: the same grouping-sets
        trick as the flow, which is one scan of ``member_paths`` for all three columns.
        """

        async def go() -> dict[str, list[str]]:
            study, first_step, current = (
                _STAGE_COLUMNS["study"],
                _STAGE_COLUMNS["first_step"],
                _STAGE_COLUMNS["current"],
            )
            stmt = select(
                study, first_step, current, func.grouping(study, first_step, current).label("gset")
            ).group_by(func.grouping_sets(*[tuple_(col) for col in _STAGE_COLUMNS.values()]))
            out: dict[str, list[str]] = {stage: [] for stage in _STAGE_COLUMNS}
            for s_group, f_group, c_group, gset in (await self._s.execute(stmt)).all():
                bits = _GroupingSet(int(gset))
                if bits is _GroupingSet.STUDY and s_group is not None:
                    out["study"].append(s_group)
                elif bits is _GroupingSet.FIRST_STEP and f_group is not None:
                    out["first_step"].append(f_group)
                elif bits is _GroupingSet.CURRENT and c_group is not None:
                    out["current"].append(c_group)
            for names in out.values():
                names.sort()
            # The intent column's boxes are a fixed list, not something the data invents.
            out["intent"] = [label for _, label in INTENT_GROUPS] + [NO_INTENT_GROUP]
            return out

        return await run_db("paths.groups", go, session=self._s)
