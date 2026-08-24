"""Image uploads and reads.

The Storage buckets are private, so the browser never talks to Supabase Storage: the API is
the only reader and writer, and the URL a caller stores in ``jobs.image_url`` or
``housing_listings.photo_urls`` points back here. That keeps the service-role key server-side
and keeps those columns stable when the storage backend changes.

``media`` is its own small bounded context (api + infrastructure, no aggregate of its own) so
that ``core`` keeps importing nothing: like every board it depends on ``core`` and on
``identity/api/deps.py`` for the ``Principal`` only.
"""

from __future__ import annotations

import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict

from backend.core.cache import TTLCache
from backend.core.exceptions import NotFoundError, PayloadTooLargeError, ValidationError
from backend.core.settings import get_app_settings, get_storage_settings
from backend.core.settings.storage import KNOWN_BUCKETS, MEDIA_BUCKETS
from backend.identity.api.deps import AdminPrincipalDep, PrincipalDep
from backend.media.infrastructure import BlobStorage, get_blob_storage
from backend.media.infrastructure.images import (
    ALLOWED_IMAGE_TYPES,
    is_safe_key,
    new_key,
    sniff_image_content_type,
)

router = APIRouter(prefix="/media", tags=["media"])

MediaKind = Literal["job-image", "housing-photo", "avatar"]

StorageDep = Annotated[BlobStorage, Depends(get_blob_storage)]

#: How long a signed URL stays valid. Expiry is not the revocation mechanism here: the key
#: is a random UUID that is only ever handed to people who can already read the row it sits
#: on, and taking an image back means deleting the blob, which invalidates every signature
#: over it at once. So the lifetime is set by what makes a page cheap - one signature reused
#: across a browsing session - rather than by how long a leaked URL stays usable.
SIGNED_URL_SECONDS = 3600

#: A signed URL is reused until this much of its life is left. The margin covers the time
#: between the browser reading the header and actually following the redirect.
SIGNED_URL_MARGIN_SECONDS = 60

#: Keys are content-addressed by a fresh UUID and blobs are never rewritten in place, so a
#: response may be cached forever.
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"

#: Signed URLs already handed out, keyed by ``(bucket, key)``.
#:
#: Every ``<img>`` on every page load used to cost a POST to the Storage sign API, and
#: because each signature is unique the browser could not reuse the redirect either, so the
#: CDN missed every time. Reusing one signature per object turns a page of twelve job cards
#: from twelve sign calls into (at most) twelve, once an hour, and lets the browser skip the
#: API entirely for the rest of the hour.
#:
#: Per process and bounded: a thousand distinct images is more than any page shows, and an
#: entry is only a URL. Nothing here is authorization state, so a second worker having its
#: own copy is not a correctness question.
#:
#: The platform's own :class:`~backend.core.cache.TTLCache`, not a second implementation from
#: a library: building one registers it, so a loader run and the test suite's reset fixture
#: empty this cache along with every other. Entries expire a minute before the signatures in
#: them do, and the least recently used is dropped once there are more than ``maxsize``.
_SIGNED_URLS: TTLCache = TTLCache(maxsize=1024, ttl=SIGNED_URL_SECONDS - SIGNED_URL_MARGIN_SECONDS)


class MediaUploadPublic(BaseModel):
    """Where the blob landed. ``url`` is what belongs in a database column."""

    model_config = ConfigDict(title="MediaUploadPublic")

    url: str
    bucket: str
    key: str
    content_type: str
    size: int


async def _cached_signed_url(storage: BlobStorage, bucket: str, key: str) -> tuple[str, int] | None:
    """A signed URL for this object and how many seconds it is still good for.

    ``None`` when the adapter cannot sign (the local disk cannot), which is what makes the
    route stream the bytes itself.
    """
    now = time.monotonic()
    cached = _SIGNED_URLS.get((bucket, key))
    if cached is not None:
        url, good_until = cached
        remaining = int(good_until - now)
        if remaining > 0:
            return url, remaining
    signed = await storage.signed_url(bucket, key, SIGNED_URL_SECONDS)
    if signed is None:
        return None
    reusable_for = SIGNED_URL_SECONDS - SIGNED_URL_MARGIN_SECONDS
    _SIGNED_URLS.set((bucket, key), (signed, now + reusable_for))
    return signed, reusable_for


def _forget_signed_url(bucket: str, key: str) -> None:
    """Drop a cached signature. Deleting the blob is how an image is taken back, and a
    redirect to a signature over an object that no longer exists is a confusing 400."""
    _SIGNED_URLS.pop((bucket, key))


def _media_url(bucket: str, key: str) -> str:
    app = get_app_settings()
    return f"{app.public_base_url.rstrip('/')}{app.api_prefix}/media/{bucket}/{key}"


def _checked_location(bucket: str, key: str) -> tuple[str, str]:
    """Reject anything that is not one of our buckets and one of our generated keys.

    A 404 rather than a 422: an unknown bucket and a missing object are the same fact to a
    caller, and enumerating which buckets exist is not information worth handing out.
    """
    if bucket not in KNOWN_BUCKETS or not is_safe_key(key):
        raise NotFoundError("image not found")
    return bucket, key


@router.post("/{kind}", response_model=MediaUploadPublic, status_code=status.HTTP_201_CREATED)
async def upload_media(
    kind: MediaKind,
    principal: PrincipalDep,
    storage: StorageDep,
    file: Annotated[UploadFile, File()],
) -> MediaUploadPublic:
    """Upload one image and get back the URL to store.

    The declared content type is ignored; the leading bytes decide, so a file that is not
    actually a JPEG, PNG or WebP cannot be parked in a bucket behind an image name.
    """
    settings = get_storage_settings()
    limit = settings.max_upload_bytes
    # Read one byte past the limit rather than the whole body: that is enough to know the
    # upload is too large without ever holding an unbounded body in memory.
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise PayloadTooLargeError(f"images must be at most {limit // 1024} KiB")
    if not data:
        raise ValidationError("the uploaded file is empty")

    content_type = sniff_image_content_type(data)
    if content_type is None or content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError(
            "unsupported image type",
            details={"allowed": sorted(ALLOWED_IMAGE_TYPES)},
        )

    bucket = MEDIA_BUCKETS[kind]
    key = new_key(content_type)
    await storage.put(bucket, key, data, content_type)
    return MediaUploadPublic(
        url=_media_url(bucket, key),
        bucket=bucket,
        key=key,
        content_type=content_type,
        size=len(data),
    )


@router.get(
    "/{bucket}/{key}", response_class=Response, responses={200: {"content": {"image/*": {}}}}
)
async def read_media(bucket: str, key: str, storage: StorageDep) -> Response:
    """Serve an uploaded image.

    Deliberately unauthenticated: these URLs sit in ``<img src=...>`` tags, and an image
    request carries no ``Authorization`` header. The access model is the key itself, a
    random UUID that is only ever handed to the caller who uploaded it and to whoever can
    already read the row it was stored on.
    """
    bucket, key = _checked_location(bucket, key)
    signed = await _cached_signed_url(storage, bucket, key)
    if signed is not None:
        url, max_age = signed
        # 307 keeps the method. ``private`` because the target carries a signature: a shared
        # cache must not hand one visitor's signed URL to the next. ``max-age`` is what is
        # left of the signature, so the browser stops reusing the redirect before the URL
        # behind it stops working.
        return RedirectResponse(
            url,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Cache-Control": f"private, max-age={max_age}"},
        )
    found = await storage.get(bucket, key)
    if found is None:
        raise NotFoundError("image not found")
    data, content_type = found
    return Response(
        content=data, media_type=content_type, headers={"Cache-Control": IMMUTABLE_CACHE}
    )


@router.delete("/{bucket}/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    bucket: str, key: str, actor: AdminPrincipalDep, storage: StorageDep
) -> None:
    """Delete an uploaded image. Admin only.

    Nothing records who uploaded a blob, so there is no owner to compare the caller against.
    Until a media table exists, admin is the only defensible answer.
    """
    bucket, key = _checked_location(bucket, key)
    await storage.delete(bucket, key)
    _forget_signed_url(bucket, key)
