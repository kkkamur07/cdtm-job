"""Persistence and read ports for the paths context."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from backend.paths.domain import CareerHistory, MemberCard, MemberPath, PathFlow


@dataclass(frozen=True, slots=True)
class PathFilters:
    class_id: int | None = None
    study_group: str | None = None
    first_step_group: str | None = None
    current_group: str | None = None
    #: Narrow the flow to a named set of members. The directory's Ask fills this with every
    #: member its question matched, not the page it showed, so the Sankey is drawn over the
    #: whole answer. Ids rather than a directory filter: the filter is the members context's
    #: language, and this context does not speak it.
    member_ids: tuple[UUID, ...] | None = None


class PathRepository(Protocol):
    async def flow(self, filters: PathFilters) -> PathFlow: ...
    async def get(self, member_id: UUID) -> MemberPath | None: ...
    async def upsert(self, path: MemberPath) -> None: ...
    async def member_ids_page(
        self, *, stage: str, group: str, filters: PathFilters, skip: int, limit: int
    ) -> tuple[list[UUID], int]:
        """One page of the ids in a box of the Sankey, in card order, and how many there are.

        The page is cut in SQL rather than in Python: this used to hand every id in the
        group to the card loader, so opening a box of four hundred people shipped four
        hundred uuids back only to look up twenty of them, and put the other three hundred
        and eighty into an ``IN`` list. The order is the order the cards are drawn in
        (member name), because a page cut in one order and drawn in another is not a page.
        """
        ...

    async def current_group_of(self, member_id: UUID) -> str | None: ...
    async def groups(self) -> dict[str, list[str]]: ...


class CareerHistorySource(Protocol):
    """The jobs, degrees and class the classifier reads, out of the member tables.

    Implemented over read-only table handles so this context never imports the members
    ORM (``infrastructure/_member_tables.py``), the way ``identity`` reads ``members.email``
    with a ``text()`` query. Paths is a read model: it takes what happened to a person and
    files them under a group, and nothing in members knows the classifier exists.
    """

    async def get(self, member_id: UUID) -> CareerHistory | None: ...
    def iter_all(self) -> AsyncIterator[CareerHistory]: ...


class PathClassifier(Protocol):
    """Turns one career history into a path.

    A port rather than an import so the application layer keeps pointing one way. The
    implementation is ``infrastructure/paths_classifier.py``, which is where it belongs:
    the rules encode how our LinkedIn scrape looks, not what a career is.
    """

    def __call__(self, history: CareerHistory) -> MemberPath: ...


class MemberCards(Protocol):
    """Names and faces for the ids in a group, so a box of the Sankey opens into people."""

    async def find_id_by_slug(self, slug: str) -> UUID | None: ...
    async def cards(self, ids: list[UUID]) -> list[MemberCard]:
        """The cards for exactly these ids, in the order a page of them is drawn.

        No paging here any more: the repository above already cut the page, so this is
        handed the twenty ids that are going to be shown and nothing else.
        """
        ...
