"""Local disk adapter: ``<root>/<bucket>/<key>``. The development and test backend."""

from __future__ import annotations

from pathlib import Path

import anyio.to_thread

from backend.core.exceptions import ValidationError
from backend.media.infrastructure.images import content_type_for_key


class LocalDiskStorage:
    """Files under ``StorageSettings.local_dir``. No signing, so the API streams the bytes.

    Blocking file IO runs on a worker thread: uvicorn serves the whole app on one event loop
    and a 5 MiB write to a slow disk would stall every other request in flight.
    """

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).expanduser().resolve()

    @property
    def root(self) -> Path:
        return self._root

    def path_for(self, bucket: str, key: str) -> Path:
        """Resolve ``bucket``/``key`` under the root, refusing anything that escapes it.

        The routes already constrain both to a fixed set and a UUID pattern; this is the
        second lock, so a future caller that skips that validation cannot write to /etc.
        """
        bucket_dir = self._root / bucket
        candidate = (bucket_dir / key).resolve()
        # The store is exactly two levels deep, so the resolved parent has to be the bucket
        # directory itself. That rejects traversal in either component, including the
        # ``a/../b`` form that would otherwise land back inside the root and look harmless.
        if candidate.parent != bucket_dir or self._root not in candidate.parents:
            raise ValidationError("invalid storage path")
        return candidate

    async def put(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        path = self.path_for(bucket, key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await anyio.to_thread.run_sync(write)

    async def get(self, bucket: str, key: str) -> tuple[bytes, str] | None:
        path = self.path_for(bucket, key)

        def read() -> bytes | None:
            return path.read_bytes() if path.is_file() else None

        data = await anyio.to_thread.run_sync(read)
        if data is None:
            return None
        return data, content_type_for_key(key)

    async def signed_url(self, bucket: str, key: str, expires_s: int) -> str | None:
        # There is nothing to sign against: the files are not served by anything but the API.
        return None

    async def delete(self, bucket: str, key: str) -> None:
        path = self.path_for(bucket, key)
        await anyio.to_thread.run_sync(lambda: path.unlink(missing_ok=True))
