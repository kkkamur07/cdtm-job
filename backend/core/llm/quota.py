"""How many questions one caller may ask a minute, counted in Postgres.

The limit protects a spend ceiling on a shared provider account, so it has to hold across
every API instance rather than per worker. One UPSERT against ``ask_quota`` per question
does that in a single round trip: the row carries the minute it belongs to, and the
statement either adds to that minute or starts a new one.

The in-process token bucket stays as the fallback. If the database is unreachable the
question is about to fail anyway, but a metering outage must never be the thing that lets
one caller empty the account, and a bucket that is right per worker is better than none.
"""

from __future__ import annotations

import contextlib

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import RepositoryError
from backend.core.llm.rate_limit import ask_limiter
from infrastructure.repository import run_db

# date_trunc pins the row to the current minute, so a caller gets a fresh allowance on the
# minute boundary rather than a sliding window. A fixed window lets one caller ask twice the
# limit across a boundary; that is a rounding error against a spend ceiling, and it buys a
# statement with no read-modify-write race in it.
_UPSERT = text(
    """
    insert into ask_quota (member_key, window_start, asked)
    values (:key, date_trunc('minute', now()), 1)
    on conflict (member_key) do update
       set asked = case
                       when ask_quota.window_start = date_trunc('minute', now())
                       then ask_quota.asked + 1
                       else 1
                   end,
           window_start = date_trunc('minute', now())
    returning asked
    """
)


class SqlQuestionMeter:
    """Counts one question and says whether it was within the caller's allowance."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def allow(self, key: str, *, rate_per_minute: int) -> bool:
        async def go() -> int:
            asked = await self._s.scalar(_UPSERT, {"key": key})
            # The count must survive the request even when the question then fails
            # validation, or a caller could spend the allowance on questions that never
            # reach the provider. This is a meter, not part of anybody's use case, which
            # is why it commits here rather than leaving it to a service.
            await self._s.commit()
            return int(asked or 1)

        try:
            asked = await run_db("ask.meter", go, session=self._s)
        except RepositoryError:
            await self._rollback()
            return ask_limiter.allow(key, rate_per_minute=rate_per_minute)
        return asked <= max(rate_per_minute, 1)

    async def _rollback(self) -> None:
        # The session is being abandoned either way; a failed rollback has nothing left to
        # report to and must not replace the caller's error with its own.
        with contextlib.suppress(Exception):
            await self._s.rollback()
