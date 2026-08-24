"""Paths: the flow between groups, the people in one of them, and recomputing them."""

from __future__ import annotations

from uuid import UUID

from backend.core.exceptions import NotFoundError, ValidationError
from backend.core.page import PageResult
from backend.paths.application.ports import (
    CareerHistorySource,
    MemberCards,
    PathClassifier,
    PathFilters,
    PathRepository,
)
from backend.paths.domain import MemberCard, MemberPath, PathFlow

#: Only the three career stages have people in a box you can open. "intent" is drawn from
#: what members say they are open to, and the directory already answers "who is open to
#: mentoring" with a filter of its own.
_BROWSABLE_STAGES = ("study", "first_step", "current")


class PathService:
    def __init__(
        self,
        paths: PathRepository,
        cards: MemberCards,
        history: CareerHistorySource,
        classify: PathClassifier,
    ) -> None:
        self._paths = paths
        self._cards = cards
        self._history = history
        self._classify = classify

    async def flow(self, filters: PathFilters) -> PathFlow:
        return await self._paths.flow(filters)

    async def member_path(self, member_id: UUID) -> MemberPath:
        path = await self._paths.get(member_id)
        if path is None:
            raise NotFoundError("no path computed for this member")
        return path

    async def member_path_by_slug(self, slug: str) -> MemberPath:
        member_id = await self._cards.find_id_by_slug(slug)
        if member_id is None:
            raise NotFoundError(f"member {slug!r} not found")
        return await self.member_path(member_id)

    async def members_in(
        self, *, stage: str, group: str, skip: int, limit: int, filters: PathFilters
    ) -> PageResult[MemberCard]:
        if stage not in _BROWSABLE_STAGES:
            raise ValidationError("stage must be study, first_step or current")
        ids = await self._paths.member_ids_in(stage=stage, group=group, filters=filters)
        return await self._cards.page(ids, skip=skip, limit=limit)

    async def groups(self) -> dict[str, list[str]]:
        return await self._paths.groups()

    async def current_group_of(self, member_id: UUID) -> str | None:
        """Implements ``members.application.ports.ViewerGroupSource``."""
        return await self._paths.current_group_of(member_id)

    # ---- recompute ----------------------------------------------------------------------

    async def recompute(self, member_id: UUID) -> MemberPath | None:
        """Reclassify one member from their current positions and degrees."""
        history = await self._history.get(member_id)
        if history is None:
            return None
        path = self._classify(history)
        await self._paths.upsert(path)
        return path

    async def recompute_all(self) -> int:
        """Reclassify everyone. Run by the loader after an import; see docs/architecture.md.

        It is a full pass rather than an incremental one because the classifier's keyword
        tables change more often than the scrape does: after editing them, the only honest
        thing to do is redo every verdict.
        """
        n = 0
        async for history in self._history.iter_all():
            await self._paths.upsert(self._classify(history))
            n += 1
        return n
