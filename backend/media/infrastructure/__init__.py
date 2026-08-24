"""Blob storage: one port, two adapters, one cached factory."""

from __future__ import annotations

from pathlib import Path

from backend.core.exceptions import AppError
from backend.core.settings._cache import settings_cache
from backend.core.settings.storage import get_storage_settings
from backend.media.infrastructure.local_disk import LocalDiskStorage
from backend.media.infrastructure.ports import BlobStorage
from backend.media.infrastructure.supabase_storage import SupabaseStorage

__all__ = ["BlobStorage", "LocalDiskStorage", "SupabaseStorage", "get_blob_storage"]


@settings_cache
def get_blob_storage() -> BlobStorage:
    """The adapter ``STORAGE_BACKEND`` selects.

    Registered with ``settings_cache`` rather than a bare ``lru_cache`` so that
    ``reset_settings_caches()`` drops the adapter too; a test that repoints
    ``STORAGE_LOCAL_DIR`` would otherwise keep writing into the previous directory.
    """
    s = get_storage_settings()
    if s.backend == "supabase":
        if not s.configured:
            raise AppError("STORAGE_BACKEND=supabase needs SUPABASE_URL and a service-role key")
        return SupabaseStorage(
            supabase_url=str(s.supabase_url), service_role_key=str(s.service_role_key)
        )
    return LocalDiskStorage(Path(s.local_dir))
