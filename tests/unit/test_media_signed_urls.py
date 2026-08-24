"""What ``GET /media/{bucket}/{key}`` costs, and what it lets the browser cache.

An uploaded image is fetched by an ``<img>`` tag, so this route runs once per image per
page view. It used to POST to the Storage sign API every single time and answer with a 307
carrying no ``Cache-Control``, which meant three sequential round trips per image, every
view, cacheable at no hop: the signature was unique per request, so the CDN missed too.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import pytest

from backend.core.exceptions import NotFoundError
from backend.media.api import router as media_router
from backend.media.api.router import (
    SIGNED_URL_MARGIN_SECONDS,
    SIGNED_URL_SECONDS,
    read_media,
)
from backend.media.infrastructure.images import new_key

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class _Signing:
    """A storage adapter that signs, and counts how often it was asked to."""

    def __init__(self, *, signs: bool = True) -> None:
        self.calls: list[tuple[str, str, int]] = []
        self._signs = signs

    async def signed_url(self, bucket: str, key: str, expires_s: int) -> str | None:
        self.calls.append((bucket, key, expires_s))
        if not self._signs:
            return None
        return f"https://storage.example.com/{bucket}/{key}?token=sig-{len(self.calls)}"

    async def get(self, bucket: str, key: str) -> tuple[bytes, str] | None:
        return PNG, "image/png"

    async def put(self, bucket: str, key: str, data: bytes, content_type: str) -> None: ...

    async def delete(self, bucket: str, key: str) -> None: ...

    async def aclose(self) -> None: ...


@pytest.fixture(autouse=True)
def _empty_cache() -> Iterator[None]:
    """The cache is per process, so it outlives a test unless it is emptied."""
    media_router._SIGNED_URLS.clear()
    yield
    media_router._SIGNED_URLS.clear()


async def test_the_same_image_is_signed_once_and_reused() -> None:
    """Twelve job cards on a page were twelve POSTs to the Storage sign API. The key is a
    UUID and the object behind it never changes, so one signature serves all of them."""
    storage = _Signing()
    key = new_key("image/png")

    first = await read_media("job-images", key, storage)
    second = await read_media("job-images", key, storage)

    assert len(storage.calls) == 1
    assert first.headers["location"] == second.headers["location"]


async def test_each_object_gets_its_own_signature() -> None:
    """The cache is keyed on bucket and key together: a signature over one object must
    never be handed out for another, in this bucket or any other."""
    storage = _Signing()
    a, b = new_key("image/png"), new_key("image/png")

    first = await read_media("job-images", a, storage)
    second = await read_media("job-images", b, storage)
    third = await read_media("housing-photos", a, storage)

    assert len(storage.calls) == 3
    assert len({r.headers["location"] for r in (first, second, third)}) == 3


async def test_the_redirect_tells_the_browser_how_long_it_may_reuse_it() -> None:
    """Without this header the browser re-asked the API for every image on every page load,
    however long the URL it was given stayed valid."""
    storage = _Signing()

    response = await read_media("job-images", new_key("image/png"), storage)

    assert response.status_code == 307
    # ``private``: the redirect target carries a signature, so a shared cache must not hand
    # one visitor's signed URL to the next.
    assert response.headers["cache-control"] == (
        f"private, max-age={SIGNED_URL_SECONDS - SIGNED_URL_MARGIN_SECONDS}"
    )


async def test_the_advertised_lifetime_shrinks_as_the_signature_ages() -> None:
    """A cache hit must not restate the full lifetime, or the last browser to be served
    would still be reusing the URL after Storage has stopped honouring it."""
    storage = _Signing()
    key = new_key("image/png")
    await read_media("job-images", key, storage)

    # Age the cached entry by a minute without waiting one.
    url, good_until = media_router._SIGNED_URLS[("job-images", key)]
    media_router._SIGNED_URLS[("job-images", key)] = (url, good_until - 60)

    response = await read_media("job-images", key, storage)

    assert len(storage.calls) == 1
    # A whole second of slack: the remaining life is truncated to an integer, so a test that
    # spent any part of a second getting here would otherwise be a second short.
    full_life = SIGNED_URL_SECONDS - SIGNED_URL_MARGIN_SECONDS
    max_age = int(response.headers["cache-control"].removeprefix("private, max-age="))
    assert full_life - 62 <= max_age <= full_life - 60


async def test_a_signature_close_to_expiry_is_replaced_rather_than_reused() -> None:
    storage = _Signing()
    key = new_key("image/png")
    await read_media("job-images", key, storage)

    url, _ = media_router._SIGNED_URLS[("job-images", key)]
    media_router._SIGNED_URLS[("job-images", key)] = (url, time.monotonic() - 1)

    response = await read_media("job-images", key, storage)

    assert len(storage.calls) == 2
    assert response.headers["location"] != url


async def test_the_signature_is_asked_for_with_the_configured_lifetime() -> None:
    """Deletion, not expiry, is how an image is taken back here: the key is a random UUID
    only handed to people who can already read the row it sits on, and removing the blob
    invalidates every signature over it at once."""
    storage = _Signing()

    await read_media("job-images", new_key("image/png"), storage)

    assert storage.calls[0][2] == SIGNED_URL_SECONDS == 3600


async def test_an_adapter_that_cannot_sign_still_streams_the_bytes_as_immutable() -> None:
    """The local-disk backend has nothing to sign against, and its branch keeps the
    one-year immutable header it already had."""
    storage = _Signing(signs=False)

    response = await read_media("job-images", new_key("image/png"), storage)

    assert response.status_code == 200
    assert response.body == PNG
    assert response.headers["cache-control"] == media_router.IMMUTABLE_CACHE


async def test_deleting_an_image_forgets_the_signature_over_it() -> None:
    """Deletion is the revocation mechanism, so a cached redirect to a signature over an
    object that is gone would outlive the thing it points at."""
    storage = _Signing()
    key = new_key("image/png")
    await read_media("job-images", key, storage)
    assert ("job-images", key) in media_router._SIGNED_URLS

    await media_router.delete_media("job-images", key, actor=None, storage=storage)

    assert ("job-images", key) not in media_router._SIGNED_URLS


async def test_an_unknown_bucket_is_still_refused_before_anything_is_signed() -> None:
    storage = _Signing()
    with pytest.raises(NotFoundError):
        await read_media("secrets", new_key("image/png"), storage)
    assert storage.calls == []
