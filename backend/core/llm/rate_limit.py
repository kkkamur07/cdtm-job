"""A token bucket per caller, in process memory.

Deliberately not Redis. There is one API process today, the thing being protected is a
spend ceiling rather than a correctness boundary, and an in-process bucket that is right
99% of the time costs nothing to operate. If the API is ever scaled out, the ceiling
becomes per-worker and this comment is the thing to come back to.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


@dataclass
class TokenBucketLimiter:
    """Refills at ``rate_per_minute`` tokens a minute, and holds at most a minute's worth.

    ``rate_per_minute`` is read on every call rather than captured, because it comes from
    settings and settings are re-read when the caches are reset.
    """

    _buckets: dict[str, _Bucket] = field(default_factory=dict)

    def allow(self, key: str, *, rate_per_minute: int) -> bool:
        now = time.monotonic()
        capacity = float(max(rate_per_minute, 1))
        bucket = self._buckets.get(key)
        if bucket is None:
            self._buckets[key] = _Bucket(tokens=capacity - 1.0, updated_at=now)
            return True
        refill = (now - bucket.updated_at) * (capacity / 60.0)
        bucket.tokens = min(capacity, bucket.tokens + refill)
        bucket.updated_at = now
        if bucket.tokens < 1.0:
            return False
        bucket.tokens -= 1.0
        return True

    def reset(self) -> None:
        self._buckets.clear()


#: One bucket space for every metered question, whichever board asked it. A member who
#: burns their allowance on the job board should not then get a fresh allowance on the
#: directory: the cost is the same call to the same provider.
ask_limiter = TokenBucketLimiter()
