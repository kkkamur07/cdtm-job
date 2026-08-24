"""Supabase Storage adapter: plain httpx against the Storage REST API, no SDK.

The buckets are private, so every call carries the service-role key and the browser never
talks to Storage directly. The API either streams the object or hands out a short-lived
signed URL.
"""

from __future__ import annotations

from urllib.parse import quote

import httpx

from backend.core.exceptions import RepositoryError
from backend.media.infrastructure.images import content_type_for_key

_TIMEOUT = httpx.Timeout(15.0)

#: Uploads are content-addressed by a fresh UUID and blobs are never rewritten in place, so
#: the object Storage hands back for a key is the object it will always hand back. Telling
#: Storage that at upload time is what lets its CDN keep the bytes.
_UPLOAD_CACHE_CONTROL = "max-age=31536000, immutable"


class SupabaseStorage:
    """One HTTP client per adapter instance, not one per call.

    ``get_blob_storage`` is a process-wide singleton, so this holds the connection pool for
    the life of the process: a fresh ``AsyncClient`` per call meant a new TCP connection and
    a new TLS handshake for every image on every page view. The client is built lazily so
    that constructing the adapter (which ``create_app`` does at boot, and which tests do
    freely) never opens sockets, and :meth:`aclose` is called from the app lifespan.
    """

    def __init__(self, *, supabase_url: str, service_role_key: str) -> None:
        self._base = supabase_url.rstrip("/") + "/storage/v1"
        self._key = service_role_key
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=_TIMEOUT)
        return self._client

    async def aclose(self) -> None:
        """Release the connection pool. Idempotent; the lifespan calls it once on shutdown."""
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()

    def _headers(self) -> dict[str, str]:
        # Storage wants both: ``apikey`` selects the project, ``Authorization`` the role.
        return {"apikey": self._key, "Authorization": f"Bearer {self._key}"}

    @staticmethod
    def _object_path(bucket: str, key: str) -> str:
        return f"{quote(bucket, safe='')}/{quote(key, safe='')}"

    async def put(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        url = f"{self._base}/object/{self._object_path(bucket, key)}"
        headers = self._headers() | {
            "Content-Type": content_type,
            "x-upsert": "true",
            "cache-control": _UPLOAD_CACHE_CONTROL,
        }
        try:
            response = await self._http().post(url, content=data, headers=headers)
        except httpx.HTTPError as exc:
            raise RepositoryError("storage.put: storage unavailable") from exc
        if response.status_code >= 400:
            raise RepositoryError(
                f"storage.put: storage rejected the upload ({response.status_code})"
            )

    async def get(self, bucket: str, key: str) -> tuple[bytes, str] | None:
        url = f"{self._base}/object/{self._object_path(bucket, key)}"
        try:
            response = await self._http().get(url, headers=self._headers())
        except httpx.HTTPError as exc:
            raise RepositoryError("storage.get: storage unavailable") from exc
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise RepositoryError(f"storage.get: storage error ({response.status_code})")
        return response.content, response.headers.get("content-type") or content_type_for_key(key)

    async def signed_url(self, bucket: str, key: str, expires_s: int) -> str | None:
        url = f"{self._base}/object/sign/{self._object_path(bucket, key)}"
        try:
            response = await self._http().post(
                url, json={"expiresIn": expires_s}, headers=self._headers()
            )
        except httpx.HTTPError:
            # Signing is an optimisation; the caller falls back to streaming the bytes.
            return None
        if response.status_code >= 400:
            return None
        signed = response.json().get("signedURL")
        if not signed:
            return None
        # Storage returns a path relative to /storage/v1, e.g. "/object/sign/bucket/key?token=".
        return self._base + signed if signed.startswith("/") else f"{self._base}/{signed}"

    async def delete(self, bucket: str, key: str) -> None:
        url = f"{self._base}/object/{self._object_path(bucket, key)}"
        try:
            response = await self._http().delete(url, headers=self._headers())
        except httpx.HTTPError as exc:
            raise RepositoryError("storage.delete: storage unavailable") from exc
        if response.status_code >= 400 and response.status_code != 404:
            raise RepositoryError(f"storage.delete: storage error ({response.status_code})")
