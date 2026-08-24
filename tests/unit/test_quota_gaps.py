"""What the question meter does when Postgres is not there to count in.

The durable meter is covered against a real database in
``tests/integration/test_core_gaps.py``; what cannot be arranged there is a metering
outage, so the fallback to the in-process bucket is pinned down here with a session that
fails the way asyncpg does.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.exc import OperationalError

from backend.core.llm.quota import SqlQuestionMeter
from backend.core.llm.rate_limit import ask_limiter


class _DeadSession:
    """A session whose statements fail the way a lost connection does."""

    def __init__(self) -> None:
        self.rolled_back = 0

    async def scalar(self, *_args: object, **_kwargs: object) -> int:
        raise OperationalError("insert into ask_quota ...", {}, Exception("connection lost"))

    async def commit(self) -> None:  # pragma: no cover - never reached
        raise AssertionError("a failed statement must not be committed")

    async def rollback(self) -> None:
        self.rolled_back += 1


class _UnrollableSession(_DeadSession):
    """The rollback fails too, which is what a dropped connection actually looks like."""

    async def rollback(self) -> None:
        self.rolled_back += 1
        raise OperationalError("rollback", {}, Exception("connection lost"))


@pytest.fixture(autouse=True)
def _fresh_buckets() -> Iterator[None]:
    # The fallback limiter is a process-wide singleton; leaving spent buckets behind would
    # charge the next test for questions it never asked.
    ask_limiter.reset()
    yield
    ask_limiter.reset()


async def test_a_metering_outage_falls_back_to_the_in_process_allowance() -> None:
    session = _DeadSession()
    meter = SqlQuestionMeter(session)

    # The allowance is still enforced, per caller, at the rate the caller was given.
    assert await meter.allow("member-1", rate_per_minute=1) is True
    assert await meter.allow("member-1", rate_per_minute=1) is False
    # A different caller has their own allowance, so one member cannot spend another's.
    assert await meter.allow("member-2", rate_per_minute=1) is True
    assert await meter.allow("member-2", rate_per_minute=1) is False


async def test_the_outage_rolls_the_session_back_so_the_request_can_carry_on() -> None:
    session = _DeadSession()
    meter = SqlQuestionMeter(session)

    assert await meter.allow("member-3", rate_per_minute=2) is True
    assert session.rolled_back >= 1


async def test_a_rollback_that_fails_too_does_not_replace_the_answer() -> None:
    session = _UnrollableSession()
    meter = SqlQuestionMeter(session)

    # The session is being abandoned anyway; the caller still gets a metering decision.
    assert await meter.allow("member-4", rate_per_minute=1) is True
    assert await meter.allow("member-4", rate_per_minute=1) is False
