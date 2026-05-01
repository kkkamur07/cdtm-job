"""FastAPI dependency callables shared across routers."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from backend.core.settings import Settings

#! Beware if you change the environment variables, you need to restart the server for the changes to take effect.
@lru_cache
def get_settings() -> Settings:
    """Return process-wide settings (env loaded once per worker)."""
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]
