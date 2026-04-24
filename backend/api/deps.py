from typing import Annotated

from fastapi import Depends
from supabase import Client, create_client

from api.settings import Settings, get_settings


def settings_dep() -> Settings:
    return get_settings()


def get_supabase(
    settings: Annotated[Settings, Depends(settings_dep)],
) -> Client:
    """Server-only Supabase client using the **service role** key (bypasses RLS).

    Never call this from browser code or from Next.js client bundles. The anon key
    belongs in the frontend only; see `supabase/README.md` and `frontend/.env.example`.
    """
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
