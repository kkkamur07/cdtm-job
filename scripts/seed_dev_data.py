#!/usr/bin/env python3
"""Idempotent dev seed for companies, published jobs, and seekers.

Requires ``backend/.env`` with ``SUPABASE_URL`` and ``SUPABASE_SERVICE_ROLE_KEY``.

Usage (from repo root)::

    uv run python scripts/seed_dev_data.py
    uv run python scripts/seed_dev_data.py --force   # allow when APP_ENV is not local
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.companies.infrastructure.repository import SupabaseCompanyRepository
from backend.companies.services.commands import CompanyCreate, CompanyUpdate
from backend.companies.services.service import CompanyService
from backend.core.errors import NotFoundError
from backend.core.settings import Settings, load_backend_dotenv_into_environ
from backend.core.supabase_client import get_supabase_client
from backend.jobs.domain.job import JobStatus
from backend.jobs.infrastructure.repository import SupabaseJobRepository
from backend.jobs.services.commands import JobCreate
from backend.jobs.services.service import JobService
from backend.seekers.infrastructure.repository import SupabaseSeekerRepository
from backend.seekers.services.commands import SeekerCreate, SeekerUpdate
from backend.seekers.services.service import SeekerService
from dev_seed_payloads import DEV_COMPANIES, DEV_JOBS, DEV_SEEKERS


def _seeker_id_by_email(client, email: str) -> UUID | None:
    res = (
        client.table("seekers")
        .select("id")
        .eq("email", email)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    return UUID(res.data[0]["id"])


def _seeker_exists(client, email: str) -> bool:
    return _seeker_id_by_email(client, email) is not None


def seed(*, force: bool = False) -> None:
    load_backend_dotenv_into_environ()
    settings = Settings()

    if settings.app_env != "local" and not force:
        print(
            f"Refusing to seed: APP_ENV={settings.app_env!r}. "
            "Use --force if you are sure this is a non-production database.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = get_supabase_client(settings)
    companies = CompanyService(SupabaseCompanyRepository(client))
    jobs = JobService(SupabaseJobRepository(client))
    seekers = SeekerService(SupabaseSeekerRepository(client))

    slug_to_id: dict[str, UUID] = {}
    created_companies = 0
    updated_logos = 0
    created_jobs = 0
    created_seekers = 0
    updated_seekers = 0

    for row in DEV_COMPANIES:
        slug = row["slug"]
        desired_logo = row.get("logo_url")
        try:
            existing = companies.get_company_by_slug(slug)
            slug_to_id[slug] = existing.id
            existing_logo = str(existing.logo_url) if existing.logo_url else None
            if desired_logo and existing_logo != str(desired_logo):
                companies.update_company(
                    existing.id,
                    CompanyUpdate(logo_url=desired_logo),
                )
                updated_logos += 1
                print(f"  company logo updated: {slug}")
            else:
                print(f"  company exists: {slug}")
        except NotFoundError:
            slug_to_id[slug] = companies.create_company(CompanyCreate(**row)).id
            created_companies += 1
            print(f"  company created: {slug}")

    job_repo = SupabaseJobRepository(client)
    for raw in DEV_JOBS:
        row = dict(raw)
        slug = row["slug"]
        if job_repo.get_by_slug(slug):
            print(f"  job exists: {slug}")
            continue
        company_slug = row.pop("company_slug")
        company_id = slug_to_id.get(company_slug)
        if company_id is None:
            print(f"  skip job {slug}: unknown company {company_slug}", file=sys.stderr)
            continue
        status = JobStatus(row.pop("status"))
        jobs.create_job(JobCreate(company_id=company_id, status=status, **row))
        created_jobs += 1
        print(f"  job created: {slug}")

    for row in DEV_SEEKERS:
        email = row.get("email")
        if email:
            seeker_id = _seeker_id_by_email(client, email)
            if seeker_id is not None:
                seekers.update_seeker(seeker_id, SeekerUpdate(**row))
                updated_seekers += 1
                print(f"  seeker updated: {email}")
                continue
        seekers.create_seeker(SeekerCreate(**row))
        created_seekers += 1
        print(f"  seeker created: {row['full_name']}")

    print(
        f"\nDone. Created {created_companies} companies, "
        f"updated {updated_logos} logos, "
        f"{created_jobs} jobs, {created_seekers} seekers, "
        f"updated {updated_seekers} seekers."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed dev data into Supabase.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even when APP_ENV is not local",
    )
    args = parser.parse_args()
    print("Seeding dev data…")
    seed(force=args.force)


if __name__ == "__main__":
    main()
