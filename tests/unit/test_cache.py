"""The one in-process read cache the whole platform shares.

Four contexts hold a value in here (directory facets, the Sankey and its group names, the
companies list, the media signed URLs), and every one of them trusts the same three
promises: a value stops being served after its TTL, the cache cannot grow past ``maxsize``,
and ``clear_all`` empties every cache in the process after a loader run. None of the three
had a test, so a wrong expiry or a missing registration would have shown up as a stale page
long after the load that caused it.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from backend.core import cache as cache_module
from backend.core.cache import TTLCache, clear_all


class _Clock:
    """A monotonic clock the test moves by hand, standing in for ``time``.

    Substituted for the module's ``time``, not for ``time.monotonic`` globally: nothing else
    in the process should see a clock that jumps a minute because a test wanted an entry to
    expire.
    """

    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def _isolated_registry() -> Iterator[None]:
    """Every cache built anywhere registers itself for the life of the process.

    Without this, each cache a test constructs would stay in the registry and be cleared by
    every later test's autouse fixture: harmless, but the list would grow with the suite.
    """
    saved = list(cache_module._CACHES)
    yield
    cache_module._CACHES[:] = saved


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    fake = _Clock()
    monkeypatch.setattr(cache_module, "time", fake)
    return fake


# ---- what is stored, and for how long -----------------------------------------------------


def test_a_stored_value_comes_back() -> None:
    cache = TTLCache(maxsize=4, ttl=60)
    cache.set("k", ["a", "b"])
    assert cache.get("k") == ["a", "b"]


def test_a_key_that_was_never_stored_is_a_miss() -> None:
    assert TTLCache(maxsize=4, ttl=60).get("nothing") is None


def test_an_entry_is_still_served_a_moment_before_its_ttl_is_up(clock: _Clock) -> None:
    cache = TTLCache(maxsize=4, ttl=60)
    cache.set("k", "v")

    clock.now += 59.999

    assert cache.get("k") == "v"


def test_an_entry_is_gone_the_instant_its_ttl_is_up(clock: _Clock) -> None:
    """The boundary is ``>=``, so an entry written at t and read at t + ttl is a miss. One
    second either way does not matter to a facets list; being wrong about which side of the
    comparison it is would have made a TTL of zero mean "forever"."""
    cache = TTLCache(maxsize=4, ttl=60)
    cache.set("k", "v")

    clock.now += 60

    assert cache.get("k") is None


def test_an_expired_entry_is_dropped_rather_than_left_to_rot(clock: _Clock) -> None:
    """A cache read is the only thing that ever visits a key, so an expired entry that were
    left in place would hold its value alive until something evicted it."""
    cache = TTLCache(maxsize=4, ttl=60)
    cache.set("k", "v")
    clock.now += 61

    assert cache.get("k") is None
    assert len(cache) == 0


def test_the_ttl_is_measured_from_the_write_and_not_from_the_read(clock: _Clock) -> None:
    cache = TTLCache(maxsize=4, ttl=60)
    cache.set("k", "first")
    clock.now += 40
    assert cache.get("k") == "first"

    clock.now += 30

    assert cache.get("k") is None


def test_rewriting_a_key_restarts_its_ttl(clock: _Clock) -> None:
    cache = TTLCache(maxsize=4, ttl=60)
    cache.set("k", "first")
    clock.now += 40
    cache.set("k", "second")

    clock.now += 40

    assert cache.get("k") == "second"


def test_the_configured_ttl_is_readable() -> None:
    """The routes advertise the same number to the browser in ``Cache-Control``."""
    assert TTLCache(maxsize=4, ttl=300).ttl == 300


# ---- None is a miss, not a value ----------------------------------------------------------


def test_storing_none_is_a_no_op_so_a_miss_is_never_ambiguous() -> None:
    """``get`` answers a miss with ``None``, so a stored ``None`` could not be told apart
    from one. Callers here compute the value again on a miss, which is always safe."""
    cache = TTLCache(maxsize=4, ttl=60)

    cache.set("k", None)

    assert cache.get("k") is None
    assert len(cache) == 0


def test_storing_none_does_not_evict_the_value_that_was_there() -> None:
    cache = TTLCache(maxsize=4, ttl=60)
    cache.set("k", "v")

    cache.set("k", None)

    assert cache.get("k") == "v"


def test_a_falsy_value_that_is_not_none_is_stored() -> None:
    """An empty facets list is a real answer: a directory with no members is not a miss."""
    cache = TTLCache(maxsize=4, ttl=60)
    cache.set("k", [])
    assert cache.get("k") == []


# ---- the size ceiling ---------------------------------------------------------------------


def test_the_cache_never_grows_past_maxsize() -> None:
    cache = TTLCache(maxsize=3, ttl=60)

    for i in range(10):
        cache.set(i, f"v{i}")

    assert len(cache) == 3


def test_the_least_recently_used_entry_is_the_one_dropped() -> None:
    cache = TTLCache(maxsize=3, ttl=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)

    cache.set("d", 4)

    assert cache.get("a") is None
    assert [cache.get(k) for k in ("b", "c", "d")] == [2, 3, 4]


def test_a_read_counts_as_a_use_so_a_popular_key_survives() -> None:
    """The filter combinations a UI offers are not asked for evenly: one of them is the
    default and is asked for far more than the rest."""
    cache = TTLCache(maxsize=3, ttl=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)

    cache.get("a")
    cache.set("d", 4)

    assert cache.get("a") == 1
    assert cache.get("b") is None


def test_a_cache_of_one_holds_only_the_last_thing_written() -> None:
    """Two of the caches in the platform are keyed on nothing at all."""
    cache = TTLCache(maxsize=1, ttl=60)
    cache.set("a", 1)
    cache.set("b", 2)

    assert cache.get("a") is None
    assert cache.get("b") == 2


# ---- forgetting one entry, and all of them ------------------------------------------------


def test_pop_forgets_one_entry() -> None:
    cache = TTLCache(maxsize=4, ttl=60)
    cache.set("a", 1)
    cache.set("b", 2)

    cache.pop("a")

    assert cache.get("a") is None
    assert cache.get("b") == 2


def test_popping_a_key_that_is_not_there_is_not_an_error() -> None:
    """Deleting an image whose signature was never handed out must not be a 500."""
    cache = TTLCache(maxsize=4, ttl=60)
    cache.pop(("bucket", "never-signed"))
    assert len(cache) == 0


def test_clear_empties_one_cache() -> None:
    cache = TTLCache(maxsize=4, ttl=60)
    cache.set("a", 1)

    cache.clear()

    assert len(cache) == 0


def test_clear_all_empties_every_cache_built_in_this_process() -> None:
    """The loader calls this. Without it a community reload would be invisible for the length
    of the longest TTL, which is exactly the window somebody would file a bug in."""
    one = TTLCache(maxsize=4, ttl=60)
    two = TTLCache(maxsize=4, ttl=600)
    one.set("a", 1)
    two.set("b", 2)

    clear_all()

    assert (len(one), len(two)) == (0, 0)


def test_a_cache_registers_itself_by_being_built() -> None:
    """There is no register call to forget: constructing one is what puts it in the registry,
    which is what the media signed-URL cache was missing while it came from ``cachetools``."""
    before = len(cache_module._CACHES)

    cache = TTLCache(maxsize=4, ttl=60)

    assert cache_module._CACHES[before:] == [cache]


# ---- construction -------------------------------------------------------------------------


@pytest.mark.parametrize("maxsize", [0, -1])
def test_a_cache_that_cannot_hold_anything_is_refused(maxsize: int) -> None:
    """Silently accepted, it would evict every entry it was handed and look like a cache
    that never hits."""
    with pytest.raises(ValueError, match="maxsize"):
        TTLCache(maxsize=maxsize, ttl=60)


@pytest.mark.parametrize("ttl", [0, -1.0])
def test_a_ttl_that_is_not_positive_is_refused(ttl: float) -> None:
    with pytest.raises(ValueError, match="ttl"):
        TTLCache(maxsize=4, ttl=ttl)


def test_a_refused_cache_is_not_left_in_the_registry() -> None:
    before = len(cache_module._CACHES)

    with pytest.raises(ValueError):
        TTLCache(maxsize=0, ttl=60)

    assert len(cache_module._CACHES) == before
