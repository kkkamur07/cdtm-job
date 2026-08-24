"""The ``member_paths`` aggregate: the Sankey, one member's path, and recomputing it."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.paths.application.ports import PathFilters
from backend.paths.domain import (
    INTENT_GROUPS,
    NO_INTENT_GROUP,
    MemberPath,
    PathFlow,
    PathLink,
    PathNode,
)
from backend.paths.infrastructure._member_tables import member_classes, member_intents
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
            base = self._apply(select(MemberPathRow.member_id), filters)
            total = await self._s.scalar(select(func.count()).select_from(base.subquery()))
            nodes: list[PathNode] = []
            for stage, col in _STAGE_COLUMNS.items():
                res = await self._s.execute(
                    self._apply(select(col, func.count()), filters)
                    .where(col.is_not(None))
                    .group_by(col)
                    .order_by(func.count().desc())
                )
                nodes += [PathNode(stage=stage, group=g, count=int(c)) for g, c in res.all()]
            links: list[PathLink] = []
            for (s_stage, s_col), (t_stage, t_col) in _CAREER_HOPS:
                res = await self._s.execute(
                    self._apply(select(s_col, t_col, func.count()), filters)
                    .where(s_col.is_not(None), t_col.is_not(None))
                    .group_by(s_col, t_col)
                    .order_by(func.count().desc())
                )
                links += [
                    PathLink(
                        source_stage=s_stage,
                        source_group=sg,
                        target_stage=t_stage,
                        target_group=tg,
                        count=int(c),
                    )
                    for sg, tg, c in res.all()
                ]
            intent_nodes, intent_links = await self._intent_stage(filters)
            return PathFlow(
                members_counted=int(total or 0),
                nodes=nodes + intent_nodes,
                links=links + intent_links,
            )

        return await run_db("paths.flow", go, session=self._s)

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

    async def member_ids_in(self, *, stage: str, group: str, filters: PathFilters) -> list[UUID]:
        """Every member id in one box of the Sankey; the cards are read separately.

        Unpaged on purpose: the ids come from this context and the names come from the
        members context, and there is no one query that can order by a column only the
        other one has. A group is at most a few hundred people.
        """

        async def go() -> list[UUID]:
            col = _STAGE_COLUMNS[stage]
            stmt = self._apply(select(MemberPathRow.member_id), filters).where(col == group)
            rows = await self._s.scalars(stmt)
            return list(rows.all())

        return await run_db("paths.member_ids_in", go, session=self._s)

    async def groups(self) -> dict[str, list[str]]:
        async def go() -> dict[str, list[str]]:
            out: dict[str, list[str]] = {}
            for stage, col in _STAGE_COLUMNS.items():
                res = await self._s.scalars(
                    select(col).where(col.is_not(None)).distinct().order_by(col)
                )
                out[stage] = list(res.all())
            # The intent column's boxes are a fixed list, not something the data invents.
            out["intent"] = [label for _, label in INTENT_GROUPS] + [NO_INTENT_GROUP]
            return out

        return await run_db("paths.groups", go, session=self._s)
