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


class SupabaseStorage:
    def __init__(self, *, supabase_url: str, service_role_key: str) -> None:
        self._base = supabase_url.rstrip("/") + "/storage/v1"
        self._key = service_role_key

    def _headers(self) -> dict[str, str]:
        # Storage wants both: ``apikey`` selects the project, ``Authorization`` the role.
        return {"apikey": self._key, "Authorization": f"Bearer {self._key}"}

    @staticmethod
    def _object_path(bucket: str, key: str) -> str:
        return f"{quote(bucket, safe='')}/{quote(key, safe='')}"

    async def put(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        url = f"{self._base}/object/{self._object_path(bucket, key)}"
        headers = self._headers() | {"Content-Type": content_type, "x-upsert": "true"}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                response = await client.post(url, content=data, headers=headers)
            except httpx.HTTPError as exc:
                raise RepositoryError("storage.put: storage unavailable") from exc
        if response.status_code >= 400:
            raise RepositoryError(
                f"storage.put: storage rejected the upload ({response.status_code})"
            )

    async def get(self, bucket: str, key: str) -> tuple[bytes, str] | None:
        url = f"{self._base}/object/{self._object_path(bucket, key)}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                response = await client.get(url, headers=self._headers())
            except httpx.HTTPError as exc:
                raise RepositoryError("storage.get: storage unavailable") from exc
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise RepositoryError(f"storage.get: storage error ({response.status_code})")
        return response.content, response.headers.get("content-type") or content_type_for_key(key)

    async def signed_url(self, bucket: str, key: str, expires_s: int) -> str | None:
        url = f"{self._base}/object/sign/{self._object_path(bucket, key)}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                response = await client.post(
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
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                response = await client.delete(url, headers=self._headers())
            except httpx.HTTPError as exc:
                raise RepositoryError("storage.delete: storage unavailable") from exc
        if response.status_code >= 400 and response.status_code != 404:
            raise RepositoryError(f"storage.delete: storage error ({response.status_code})")
