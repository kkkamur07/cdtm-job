"""The blob storage port. Two adapters implement it: local disk and Supabase Storage."""

from __future__ import annotations

from typing import Protocol


class BlobStorage(Protocol):
    """A flat bucket/key blob store.

    Keys are opaque to the store. The media routes always hand it ``<uuid4>.<ext>``, which is
    what lets :meth:`get` recover a content type without a sidecar file.
    """

    async def put(self, bucket: str, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, bucket: str, key: str) -> tuple[bytes, str] | None:
        """Return ``(data, content_type)``, or ``None`` when the key does not exist."""
        ...

    async def signed_url(self, bucket: str, key: str, expires_s: int) -> str | None:
        """A time-limited URL the browser may fetch directly, or ``None`` if the adapter
        cannot sign (the local disk cannot, so the API streams the bytes instead)."""
        ...

    async def delete(self, bucket: str, key: str) -> None:
        """Remove the blob. Deleting a key that is already gone is not an error."""
        ...

    async def aclose(self) -> None:
        """Release whatever the adapter holds open. Called once from the app lifespan.

        On the port rather than only on the adapter that needs it, so the lifespan does not
        have to ask which adapter it got.
        """
        ...
