"""FastAPI dependency callables shared across routers."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from supabase import Client

from backend.companies.infrastructure.repository import SupabaseCompanyRepository
from backend.companies.services.service import CompanyService
from backend.core.settings import Settings
from backend.core.supabase_client import get_supabase_client
from backend.jobs.infrastructure.repository import SupabaseJobRepository
from backend.jobs.services.service import JobService
from backend.seekers.infrastructure.repository import SupabaseSeekerRepository
from backend.seekers.services.service import SeekerService


@lru_cache
def get_settings() -> Settings:
    """Return process-wide settings (env loaded once per worker)."""
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_supabase(settings: SettingsDep) -> Client:
    return get_supabase_client(settings)


SupabaseDep = Annotated[Client, Depends(get_supabase)]


def get_company_repository(client: SupabaseDep) -> SupabaseCompanyRepository:
    return SupabaseCompanyRepository(client)


def get_company_service(
    repo: Annotated[SupabaseCompanyRepository, Depends(get_company_repository)],
) -> CompanyService:
    return CompanyService(repo)


def get_job_repository(client: SupabaseDep) -> SupabaseJobRepository:
    return SupabaseJobRepository(client)


def get_job_service(
    repo: Annotated[SupabaseJobRepository, Depends(get_job_repository)],
) -> JobService:
    return JobService(repo)


def get_seeker_repository(client: SupabaseDep) -> SupabaseSeekerRepository:
    return SupabaseSeekerRepository(client)


def get_seeker_service(
    repo: Annotated[SupabaseSeekerRepository, Depends(get_seeker_repository)],
) -> SeekerService:
    return SeekerService(repo)


CompanyServiceDep = Annotated[CompanyService, Depends(get_company_service)]
JobServiceDep = Annotated[JobService, Depends(get_job_service)]
SeekerServiceDep = Annotated[SeekerService, Depends(get_seeker_service)]

# Persistence client — use in routes when you need raw Supabase access (most CRUD goes via *ServiceDep).
SessionDep = SupabaseDep


def current_user_optional() -> None:
    """Placeholder for future JWT/session auth."""
    return None


# Add ``current_user: CurrentUserDep`` to route handlers when you introduce auth (applications, dashboards).
CurrentUserDep = Annotated[None, Depends(current_user_optional)]
