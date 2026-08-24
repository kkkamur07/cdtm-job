from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings

from backend.core.settings._cache import settings_cache
from backend.core.settings._env import env_settings_config

#: Upload kind (what the caller asks for) to bucket (where it lands). Fixed on purpose: the
#: bucket name is part of the URL stored in ``jobs.image_url`` and ``housing_listings.photo_urls``,
#: so making it configurable would strand every row written under the previous value.
MEDIA_BUCKETS: dict[str, str] = {
    "job-image": "job-images",
    "housing-photo": "housing-photos",
    "avatar": "avatars",
}

#: The buckets the media routes will read from. A bucket name arriving in a URL is checked
#: against this set so a caller cannot address an arbitrary bucket in the Supabase project.
KNOWN_BUCKETS: frozenset[str] = frozenset(MEDIA_BUCKETS.values())


class StorageSettings(BaseSettings):
    """Where uploaded images live and how large they may be.

    Two adapters sit behind :class:`backend.media.infrastructure.ports.BlobStorage`: the local disk
    (development and tests) and Supabase Storage. The service-role key is only ever used
    server-side, because the buckets are private and the API is their only reader.
    """

    model_config = env_settings_config("STORAGE_")

    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    service_role_key: str | None = Field(default=None, alias="SUPABASE_SERVICE_ROLE_KEY")
    avatars_bucket: str = "avatars"

    backend: Literal["local", "supabase"] = "local"
    local_dir: str = ".data/media"
    # 5 MiB. Large enough for a photo out of a phone, small enough that a handful of
    # concurrent uploads cannot exhaust the API process, which buffers each body in memory.
    max_upload_bytes: int = 5 * 1024 * 1024

    @property
    def configured(self) -> bool:
        return bool(self.supabase_url and self.service_role_key)

    def public_url(self, path: str) -> str | None:
        if not self.supabase_url:
            return None
        base = self.supabase_url.rstrip("/")
        return f"{base}/storage/v1/object/public/{self.avatars_bucket}/{path.lstrip('/')}"


@settings_cache
def get_storage_settings() -> StorageSettings:
    return StorageSettings()
