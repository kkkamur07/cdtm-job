"""Supabase client factory (service role — server only)."""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from backend.core.settings import Settings


@lru_cache
def _client_cache(url: str, service_role_key: str) -> Client:
    return create_client(url, service_role_key)


def get_supabase_client(settings: Settings) -> Client:
    """Return a cached Supabase client for this process."""
    return _client_cache(
        str(settings.supabase_url),
        settings.supabase_service_role_key.get_secret_value(),
    )
