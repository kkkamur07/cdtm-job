"""The in-process token bucket that guards the Ask spend ceiling when Postgres is the
metering store's fallback. It has no integration coverage of its own (the live tests
exercise the SQL-backed meter), so its boundary lives or dies here.
"""

from __future__ import annotations

import time

from backend.core.llm.rate_limit import TokenBucketLimiter, _Bucket


def test_a_fresh_caller_is_allowed_then_exhausts() -> None:
    limiter = TokenBucketLimiter()
    assert limiter.allow("caller", rate_per_minute=1) is True
    # The one-per-minute allowance is now spent; a second immediate call is refused.
    assert limiter.allow("caller", rate_per_minute=1) is False


def test_exactly_one_token_is_spendable_not_withheld() -> None:
    """The gate is ``tokens < 1.0`` (spend the last whole token), not ``tokens <= 1.0``
    (withhold it). With ``rate_per_minute=1`` the capacity cap pins a refilled bucket to
    exactly one token, so this pins down the boundary an off-by-one mutation would flip.
    """
    limiter = TokenBucketLimiter()
    limiter._buckets["k"] = _Bucket(tokens=1.0, updated_at=time.monotonic())
    assert limiter.allow("k", rate_per_minute=1) is True
    assert limiter.allow("k", rate_per_minute=1) is False


def test_reset_clears_every_bucket() -> None:
    limiter = TokenBucketLimiter()
    limiter.allow("a", rate_per_minute=1)
    limiter.reset()
    # After a reset the caller is fresh again.
    assert limiter.allow("a", rate_per_minute=1) is True
