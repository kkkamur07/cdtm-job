"""What the Sankey cache is keyed on, and what empties it.

``flow()`` holds an answer for five minutes because it is an aggregate over rows only the
classifier writes. Two things follow from that and neither is obvious from the happy path:
the key has to name every filter the answer depends on, and a write to ``member_paths``
has to drop what was held. Fakes throughout; nothing below reaches a database.
"""

from __future__ import annotations

import uuid

import pytest

from backend.core.cache import clear_all
from backend.paths.application.path_service import PathService
from backend.paths.application.ports import PathFilters
from backend.paths.domain import CareerHistory, MemberPath, PathFlow


@pytest.fixture(autouse=True)
def _empty_caches():
    clear_all()
    yield
    clear_all()


class CountingPaths:
    """``flow`` and ``upsert``, counting how often each was reached."""

    def __init__(self) -> None:
        self.flows = 0
        self.upserts: list[MemberPath] = []

    async def flow(self, filters: PathFilters) -> PathFlow:
        self.flows += 1
        return PathFlow(members_counted=self.flows)

    async def upsert(self, path: MemberPath) -> None:
        self.upserts.append(path)

    async def groups(self) -> dict[str, list[str]]:
        return {"study": ["Business"]}


class OneHistory:
    def __init__(self, member_id: uuid.UUID | None) -> None:
        self._member_id = member_id

    async def get(self, member_id: uuid.UUID) -> CareerHistory | None:
        if member_id != self._member_id:
            return None
        return CareerHistory(member_id=member_id)


def _classify(history: CareerHistory) -> MemberPath:
    return MemberPath(member_id=history.member_id, current_group="Venture Capital")


def _service(paths: CountingPaths, *, history_for: uuid.UUID | None = None) -> PathService:
    return PathService(paths, cards=None, history=OneHistory(history_for), classify=_classify)


async def test_the_same_filters_are_answered_once() -> None:
    paths = CountingPaths()
    service = _service(paths)

    first = await service.flow(PathFilters(class_id=85))
    second = await service.flow(PathFilters(class_id=85))

    assert paths.flows == 1 and second is first
    # A different combination is a different key.
    await service.flow(PathFilters(class_id=86))
    assert paths.flows == 2


async def test_a_flow_narrowed_to_member_ids_is_never_cached() -> None:
    """The Ask's flow is asked for once, over a list of ids that is new every question."""
    paths = CountingPaths()
    service = _service(paths)
    ids = (uuid.uuid4(), uuid.uuid4())

    await service.flow(PathFilters(member_ids=ids))
    await service.flow(PathFilters(member_ids=ids))

    assert paths.flows == 2


async def test_member_ids_are_part_of_the_key_even_though_the_guard_comes_first() -> None:
    """Belt and braces: an id-narrowed flow must not be able to collide with a public one.

    The early return means this can only happen if the guard is ever removed. Naming the
    field in the key makes that a cache miss rather than one member's Ask answered with
    the whole directory's Sankey, or the other way round.
    """
    from backend.paths.application import path_service

    public = PathFilters(class_id=85)
    narrowed = PathFilters(class_id=85, member_ids=(uuid.uuid4(),))
    paths = CountingPaths()
    service = _service(paths)

    await service.flow(public)
    assert len(path_service._FLOW) == 1
    # The one key that was stored belongs to the unnarrowed filters.
    assert path_service._FLOW.get((85, None, None, None, None)) is not None
    assert path_service._FLOW.get((85, None, None, None, narrowed.member_ids)) is None


async def test_recomputing_one_member_empties_the_caches() -> None:
    """One reclassified row moves a line of the Sankey and can rename a group."""
    member_id = uuid.uuid4()
    paths = CountingPaths()
    service = _service(paths, history_for=member_id)

    await service.flow(PathFilters(class_id=85))
    await service.groups()
    assert paths.flows == 1

    path = await service.recompute(member_id)
    assert path is not None and paths.upserts == [path]

    await service.flow(PathFilters(class_id=85))
    assert paths.flows == 2


async def test_a_member_with_no_history_writes_nothing() -> None:
    """No row to reclassify, so no upsert, and the caches keep what was still true."""
    paths = CountingPaths()
    service = _service(paths, history_for=uuid.uuid4())

    await service.flow(PathFilters(class_id=85))
    assert await service.recompute(uuid.uuid4()) is None

    await service.flow(PathFilters(class_id=85))
    assert paths.flows == 1 and paths.upserts == []
