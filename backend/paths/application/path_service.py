"""Paths: the flow between groups, the people in one of them, and recomputing them."""

from __future__ import annotations

from uuid import UUID

from backend.core.cache import TTLCache, clear_all
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

#: The flow and the group names are aggregates over ``member_paths``, which only the
#: classifier writes, and it runs offline. Holding them for a few minutes turns a page view
#: that recomputed them into one that does not; ``recompute_all`` empties every cache.
FLOW_TTL_SECONDS = 300
GROUPS_TTL_SECONDS = 600

#: Keyed on the filter combination the UI offers (a class and up to three group names), of
#: which there are a few dozen worth keeping. The Ask's flow is not cached: it is filtered
#: by a list of member ids that is different for every question.
_FLOW = TTLCache(maxsize=64, ttl=FLOW_TTL_SECONDS)
_GROUPS = TTLCache(maxsize=1, ttl=GROUPS_TTL_SECONDS)


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
        """The Sankey, cached for the filter combinations the explorer offers.

        A flow narrowed to a set of member ids (the Ask) goes straight to the repository:
        the key would be a thousand uuids and the answer is asked for once.
        """
        if filters.member_ids is not None:
            return await self._paths.flow(filters)
        key = (
            filters.class_id,
            filters.study_group,
            filters.first_step_group,
            filters.current_group,
        )
        cached = _FLOW.get(key)
        if cached is not None:
            return cached
        flow = await self._paths.flow(filters)
        _FLOW.set(key, flow)
        return flow

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
        # The page is cut where the rows are, not here: the repository returns the ids that
        # belong on this page and the size of the group, and the card loader is handed only
        # those. Two statements either way, but the second is no longer an IN list the
        # length of the whole group.
        ids, total = await self._paths.member_ids_page(
            stage=stage, group=group, filters=filters, skip=skip, limit=limit
        )
        return PageResult(items=await self._cards.cards(ids), total=total)

    async def groups(self) -> dict[str, list[str]]:
        """The group names per stage, cached: they change only when the classifier reruns."""
        cached = _GROUPS.get(())
        if cached is not None:
            # A copy, so a caller cannot edit the lists the next caller is handed.
            return {stage: list(names) for stage, names in cached.items()}
        groups = await self._paths.groups()
        _GROUPS.set((), groups)
        return {stage: list(names) for stage, names in groups.items()}

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
        # Every cached read in this process is now stale: the flow and the group names are
        # aggregates over exactly the rows this pass rewrote.
        clear_all()
        return n
