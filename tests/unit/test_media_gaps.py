"""The media checks the local adapter hides, and the Supabase Storage adapter itself.

Two gaps live here. The route's bucket allow-list is only ever observed through
``LocalDiskStorage``, which answers "not found" for a directory that does not exist, so the
allow-list looks enforced even when it is not; it is checked directly instead. And
``SupabaseStorage`` is the production adapter that no test ever reaches, because the suite
always configures ``STORAGE_BACKEND=local``: it is exercised here against a mock HTTP
transport, so the request it builds and the way it reads a response back are both pinned
without ever contacting Supabase.
"""

from __future__ import annotations

import httpx
import pytest

from backend.core.exceptions import NotFoundError, RepositoryError
from backend.media.api.router import _checked_location
from backend.media.infrastructure.images import (
    content_type_for_key,
    new_key,
    sniff_image_content_type,
)
from backend.media.infrastructure.supabase_storage import SupabaseStorage

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

# The shortest byte string that is a valid RIFF/WEBP header and nothing else.
MINIMAL_WEBP = b"RIFF" + (4).to_bytes(4, "little") + b"WEBP"


# ---- the route's bucket allow-list --------------------------------------------------------


def test_a_bucket_outside_the_allow_list_is_refused_however_valid_the_key_is() -> None:
    """Both halves of the check have to hold on their own. The bucket name arrives straight
    off the URL, and the production Supabase adapter does not re-check it: if only the key
    shape were enforced, any bucket in the same Supabase project would be readable through
    this API as long as the object name looked like one of ours."""
    key = new_key("image/png")

    assert _checked_location("job-images", key) == ("job-images", key)

    with pytest.raises(NotFoundError):
        _checked_location("secrets", key)
    with pytest.raises(NotFoundError):
        _checked_location("job-images", "../../etc/passwd")


# ---- image sniffing edges -----------------------------------------------------------------


def test_a_riff_header_with_no_payload_is_still_a_webp() -> None:
    """Exactly twelve bytes is a complete RIFF/WEBP header. Requiring a thirteenth would
    reject a real (if empty) file for the wrong reason."""
    assert sniff_image_content_type(MINIMAL_WEBP) == "image/webp"
    assert sniff_image_content_type(MINIMAL_WEBP[:11]) is None


def test_an_unrecognised_extension_falls_back_to_opaque_bytes() -> None:
    """Nothing that passes ``is_safe_key`` reaches this, but the adapter answers ``get()``
    with whatever comes back, and a missing type must not become ``None`` in a response
    header."""
    assert content_type_for_key("something.bin") == "application/octet-stream"
    assert content_type_for_key("no-extension") == "application/octet-stream"


# ---- the Supabase Storage adapter ---------------------------------------------------------

SERVICE_KEY = "service-role-key"


class _Recorded:
    def __init__(self, storage: SupabaseStorage, requests: list[httpx.Request]) -> None:
        self.storage = storage
        self.requests = requests

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]


@pytest.fixture
def supabase(monkeypatch: pytest.MonkeyPatch):
    """Build a ``SupabaseStorage`` whose HTTP calls are answered by ``handler``."""

    def build(handler, *, supabase_url: str = "https://project.supabase.co/") -> _Recorded:
        requests: list[httpx.Request] = []

        def record(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return handler(request)

        transport = httpx.MockTransport(record)
        real_client = httpx.AsyncClient

        class _Client(real_client):
            def __init__(self, **kwargs) -> None:
                super().__init__(transport=transport, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", _Client)
        storage = SupabaseStorage(supabase_url=supabase_url, service_role_key=SERVICE_KEY)
        return _Recorded(storage, requests)

    return build


def _ok(status: int = 200, **kwargs):
    return lambda request: httpx.Response(status, **kwargs)


def _unreachable(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("storage is unreachable")


async def test_an_upload_posts_the_bytes_to_the_object_path(supabase) -> None:
    """The URL, the credentials and the upsert header are the whole contract with Storage:
    the buckets are private, so both the project selector and the role have to travel."""
    recorded = supabase(_ok(200))
    key = new_key("image/png")

    await recorded.storage.put("job-images", key, PNG, "image/png")

    request = recorded.last
    assert request.method == "POST"
    assert str(request.url) == (f"https://project.supabase.co/storage/v1/object/job-images/{key}")
    assert request.headers["apikey"] == SERVICE_KEY
    assert request.headers["authorization"] == f"Bearer {SERVICE_KEY}"
    assert request.headers["content-type"] == "image/png"
    assert request.headers["x-upsert"] == "true"
    assert request.content == PNG


async def test_a_bucket_or_key_with_a_separator_in_it_cannot_walk_the_object_path(
    supabase,
) -> None:
    """The adapter is the last lock before the request goes out: a slash in either half is
    escaped, so it addresses one object and never a different bucket."""
    recorded = supabase(_ok(200))

    await recorded.storage.put("job-images", "a/../b.png", PNG, "image/png")
    assert str(recorded.last.url).endswith("/object/job-images/a%2F..%2Fb.png")

    await recorded.storage.put("job-images/../avatars", "a.png", PNG, "image/png")
    assert str(recorded.last.url).endswith("/object/job-images%2F..%2Favatars/a.png")


@pytest.mark.parametrize("status", [400, 403, 500])
async def test_an_upload_that_storage_rejects_is_a_storage_error(supabase, status: int) -> None:
    """Anything from 400 up is a refusal: the blob did not land, so the caller must not be
    told the URL it would have had."""
    recorded = supabase(_ok(status))
    with pytest.raises(RepositoryError):
        await recorded.storage.put("job-images", new_key("image/png"), PNG, "image/png")


async def test_an_upload_that_cannot_reach_storage_is_a_storage_error(supabase) -> None:
    recorded = supabase(_unreachable)
    with pytest.raises(RepositoryError):
        await recorded.storage.put("job-images", new_key("image/png"), PNG, "image/png")


async def test_a_read_returns_the_bytes_and_the_type_storage_reports(supabase) -> None:
    """Storage is the authority on what it is holding: the key's extension is only a guess,
    so the reported type wins when the two disagree."""
    recorded = supabase(_ok(200, content=PNG, headers={"content-type": "image/png"}))

    found = await recorded.storage.get("job-images", "a.webp")

    assert found == (PNG, "image/png")
    assert recorded.last.method == "GET"
    assert recorded.last.headers["apikey"] == SERVICE_KEY


async def test_a_read_falls_back_to_the_type_the_key_implies(supabase) -> None:
    """Storage answering without a content type must not produce a response with none."""
    recorded = supabase(lambda request: httpx.Response(200, content=PNG, headers={}))

    data, content_type = await recorded.storage.get("job-images", "a.webp")

    assert data == PNG
    assert content_type == "image/webp"


async def test_a_missing_object_reads_as_nothing_rather_than_an_error(supabase) -> None:
    """The route turns this into its own 404; a 503 here would report a storage outage for
    an image that simply is not there."""
    recorded = supabase(_ok(404))
    assert await recorded.storage.get("job-images", "a.png") is None


@pytest.mark.parametrize("status", [400, 403, 500])
async def test_a_failing_read_is_a_storage_error(supabase, status: int) -> None:
    """Only 404 means "no such image". Every other refusal is a fault, and reporting it as an
    empty bucket would turn a broken service-role key into a wall of missing pictures."""
    recorded = supabase(_ok(status))
    with pytest.raises(RepositoryError):
        await recorded.storage.get("job-images", "a.png")


async def test_a_read_that_cannot_reach_storage_is_a_storage_error(supabase) -> None:
    recorded = supabase(_unreachable)
    with pytest.raises(RepositoryError):
        await recorded.storage.get("job-images", "a.png")


async def test_a_signed_url_is_returned_absolute(supabase) -> None:
    """Storage answers with a path relative to ``/storage/v1``; the browser is redirected to
    it, so what leaves the API has to be a URL a browser can follow."""
    recorded = supabase(_ok(200, json={"signedURL": "/object/sign/job-images/a.png?token=abc"}))

    signed = await recorded.storage.signed_url("job-images", "a.png", 600)

    assert signed == (
        "https://project.supabase.co/storage/v1/object/sign/job-images/a.png?token=abc"
    )
    assert recorded.last.method == "POST"
    assert b'"expiresIn": 600' in recorded.last.content or b'"expiresIn":600' in (
        recorded.last.content
    )
    # The buckets are private, so even asking for a signature needs the service role.
    assert recorded.last.headers["apikey"] == SERVICE_KEY
    assert recorded.last.headers["authorization"] == f"Bearer {SERVICE_KEY}"


async def test_a_signed_url_without_a_leading_slash_is_still_absolute(supabase) -> None:
    recorded = supabase(_ok(200, json={"signedURL": "object/sign/job-images/a.png?token=abc"}))

    signed = await recorded.storage.signed_url("job-images", "a.png", 600)

    assert signed == (
        "https://project.supabase.co/storage/v1/object/sign/job-images/a.png?token=abc"
    )


@pytest.mark.parametrize(
    "handler",
    [_ok(400), _ok(200, json={}), _unreachable],
    ids=["refused", "no-url-in-the-answer", "unreachable"],
)
async def test_signing_that_does_not_work_out_falls_back_to_streaming(supabase, handler) -> None:
    """Signing is an optimisation. When it fails the route reads the bytes itself, so the
    adapter answers ``None`` instead of turning a servable image into an error."""
    recorded = supabase(handler)
    assert await recorded.storage.signed_url("job-images", "a.png", 600) is None


async def test_a_delete_removes_the_object(supabase) -> None:
    recorded = supabase(_ok(200))

    await recorded.storage.delete("job-images", "a.png")

    assert recorded.last.method == "DELETE"
    assert str(recorded.last.url).endswith("/storage/v1/object/job-images/a.png")
    assert recorded.last.headers["apikey"] == SERVICE_KEY
    assert recorded.last.headers["authorization"] == f"Bearer {SERVICE_KEY}"


async def test_deleting_something_that_is_already_gone_is_not_an_error(supabase) -> None:
    recorded = supabase(_ok(404))
    await recorded.storage.delete("job-images", "a.png")


@pytest.mark.parametrize("status", [400, 403, 500])
async def test_a_failing_delete_is_a_storage_error(supabase, status: int) -> None:
    """A delete that did not happen must say so; 404 is the one refusal that means the job is
    already done."""
    recorded = supabase(_ok(status))
    with pytest.raises(RepositoryError):
        await recorded.storage.delete("job-images", "a.png")


async def test_a_delete_that_cannot_reach_storage_is_a_storage_error(supabase) -> None:
    recorded = supabase(_unreachable)
    with pytest.raises(RepositoryError):
        await recorded.storage.delete("job-images", "a.png")


# ---- the connection pool and the immutability the adapter declares -------------------------


async def test_one_client_serves_every_call_instead_of_one_per_call(supabase) -> None:
    """A fresh ``AsyncClient`` per call meant a TCP connect and a TLS handshake for every
    image on every page view. The adapter holds one for its own life, built on first use so
    that constructing it (which ``create_app`` does at boot) opens no sockets."""
    recorded = supabase(_ok(200, json={"signedURL": "/object/sign/job-images/a.png?token=abc"}))
    storage = recorded.storage

    assert storage._client is None

    await storage.signed_url("job-images", "a.png", 600)
    first = storage._client
    await storage.signed_url("job-images", "b.png", 600)

    assert first is not None
    assert storage._client is first
    assert first.is_closed is False

    await storage.aclose()
    assert first.is_closed is True
    # Idempotent: the lifespan calls it on a process that may never have uploaded anything.
    await storage.aclose()


async def test_an_upload_tells_storage_the_object_will_never_change(supabase) -> None:
    """Keys are fresh UUIDs and a blob is never rewritten in place, so the object Storage
    hands back for a key is the object it will always hand back. Without this header its CDN
    re-validates every image on a default of a few seconds."""
    recorded = supabase(_ok(200))

    await recorded.storage.put("job-images", new_key("image/png"), PNG, "image/png")

    assert recorded.last.headers["cache-control"] == "max-age=31536000, immutable"
