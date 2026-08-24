"""One page and its total in one statement, which every list endpoint on the platform uses.

``page_with_total`` replaced a ``count(*)`` over the filtered subquery followed by a second
pass for the rows: ``count(*) OVER ()`` is evaluated before LIMIT, so the first row of the
page already carries the whole tally. That is only true while three things hold, and all
three are asserted here: the window column is appended and stripped back off, an empty first
page is answered without a second query at all, and a page past the end still reports the
exact total rather than the zero it can see.

Against a recording session rather than a database: what is being checked is which
statements are issued and how their rows are read, and neither needs Postgres to run. The
statements are still built and compiled, so a shape SQLAlchemy would refuse still fails.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, select

from backend.core.sql import page_with_total

_metadata = MetaData()
WIDGET = Table(
    "widget",
    _metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String),
)


def _filtered():
    """A statement in the shape the repositories hand over: filtered and ordered."""
    return (
        select(WIDGET.c.id, WIDGET.c.name).where(WIDGET.c.name.like("%a%")).order_by(WIDGET.c.name)
    )


class _Result:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[Any, ...]]:
        return self._rows


class _RecordingSession:
    """Answers with the rows it was handed and remembers every statement it was given."""

    def __init__(self, rows: list[tuple[Any, ...]], *, fallback_count: int | None = 0) -> None:
        self.rows = rows
        self.fallback_count = fallback_count
        self.executed: list[Any] = []
        self.scalars: list[Any] = []

    async def execute(self, stmt: Any) -> _Result:
        self.executed.append(stmt)
        return _Result(self.rows)

    async def scalar(self, stmt: Any) -> int | None:
        self.scalars.append(stmt)
        return self.fallback_count


def _sql(stmt: Any) -> str:
    return str(stmt)


# ---- the page and its total in one statement ----------------------------------------------


async def test_the_window_count_is_the_total_behind_the_page() -> None:
    """Not the length of the page: the point of ``count(*) OVER ()`` is that it is evaluated
    before LIMIT, so a page of two out of fifty-seven says fifty-seven."""
    session = _RecordingSession([(1, "alpha", 57), (2, "banana", 57)])

    rows, total = await page_with_total(session, _filtered(), skip=0, limit=2)

    assert total == 57
    assert rows == [(1, "alpha"), (2, "banana")]


async def test_the_total_column_is_stripped_and_the_selected_ones_keep_their_order() -> None:
    """A repository that selected extra computed columns beside its entity gets them back in
    the order it asked for, with only the appended tally removed."""
    session = _RecordingSession([(1, "alpha", "extra", 9)])

    rows, _ = await page_with_total(session, _filtered(), skip=0, limit=10)

    assert rows == [(1, "alpha", "extra")]


async def test_one_statement_carries_the_filter_the_window_and_the_page() -> None:
    session = _RecordingSession([(1, "alpha", 57)])

    await page_with_total(session, _filtered(), skip=20, limit=10)

    assert len(session.executed) == 1
    sql = _sql(session.executed[0])
    assert "count(*) OVER ()" in sql
    assert "LIMIT" in sql and "OFFSET" in sql
    # The predicate is still in the one statement, so it is evaluated once and not twice.
    assert "LIKE" in sql


async def test_a_page_with_rows_never_asks_a_second_time_for_the_total() -> None:
    """The whole saving: the second round trip and the second evaluation of the filter are
    gone. Measured on the directory with ``?q=product``: 3,929 shared buffers over two round
    trips became 1,949 over one."""
    session = _RecordingSession([(1, "alpha", 57)])

    await page_with_total(session, _filtered(), skip=0, limit=10)

    assert session.scalars == []


# ---- the two empty pages ------------------------------------------------------------------


async def test_an_empty_first_page_is_zero_without_asking() -> None:
    """No rows at offset zero is unambiguous, and a count over a filter that just matched
    nothing would be a round trip spent confirming it."""
    session = _RecordingSession([])

    rows, total = await page_with_total(session, _filtered(), skip=0, limit=10)

    assert (rows, total) == ([], 0)
    assert session.scalars == []
    assert len(session.executed) == 1


async def test_a_deep_empty_page_still_reports_the_exact_total() -> None:
    """Nothing on this page says how many rows are behind it, and answering zero would tell a
    caller who paged one step too far that the search matched nothing at all."""
    session = _RecordingSession([], fallback_count=57)

    rows, total = await page_with_total(session, _filtered(), skip=1000, limit=10)

    assert (rows, total) == ([], 57)
    assert len(session.scalars) == 1


async def test_the_fallback_counts_the_filter_without_the_ordering() -> None:
    """``ORDER BY`` inside a counted subquery is work Postgres would do and throw away, and
    some dialects refuse it outright."""
    session = _RecordingSession([], fallback_count=57)

    await page_with_total(session, _filtered(), skip=1000, limit=10)

    sql = _sql(session.scalars[0])
    assert "count(*)" in sql
    assert "LIKE" in sql
    assert "ORDER BY" not in sql
    # The count is over the filter, not over the page: no LIMIT reaches it.
    assert "LIMIT" not in sql


async def test_the_fallback_does_not_carry_the_window_column_into_the_subquery() -> None:
    """The count runs over the statement the caller passed in, not over the paged one this
    function built from it."""
    session = _RecordingSession([], fallback_count=3)

    await page_with_total(session, _filtered(), skip=1000, limit=10)

    assert "OVER ()" not in _sql(session.scalars[0])


async def test_a_fallback_that_answers_nothing_is_read_as_zero() -> None:
    """``scalar`` types as ``int | None``, and ``int(None)`` is a 500 on a list endpoint."""
    session = _RecordingSession([], fallback_count=None)

    assert await page_with_total(session, _filtered(), skip=1000, limit=10) == ([], 0)


@pytest.mark.parametrize("total", ["57", 57.0])
async def test_a_total_that_arrives_as_something_other_than_an_int_is_coerced(
    total: object,
) -> None:
    """Drivers differ on what a ``count`` comes back as, and the DTO field is an ``int``."""
    session = _RecordingSession([(1, "alpha", total)])

    assert (await page_with_total(session, _filtered(), skip=0, limit=10))[1] == 57
