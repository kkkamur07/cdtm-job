"""Job HTTP routes.

**APIRouter** groups related endpoints. ``prefix="/jobs"`` means every path here starts with
``/jobs``; the app adds ``/api/v1`` when mounting (see ``api.main``).

**Depends** wires dependencies per request (Supabase client → repository → ``JobService``).
"""

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from api.deps import get_supabase, settings_dep
from api.settings import Settings
from jobs.application.commands import CreateJobCommand, UpdateJobCommand
from jobs.application.integration_config import IntegrationConfig
from jobs.application.service import JobService
from jobs.infrastructure.repository import SupabaseJobRepository
from slack.job_publish import SlackJobPublishNotifier

router = APIRouter(prefix="/jobs", tags=["jobs"])


def get_job_service(
    client: Client = Depends(get_supabase),
    settings: Settings = Depends(settings_dep),
) -> JobService:
    """FastAPI dependency: build the application service with a real repository."""
    integrations = IntegrationConfig(
        resend_api_key=settings.resend_api_key,
        posthog_api_key=settings.posthog_api_key,
    )
    slack = SlackJobPublishNotifier(client, settings.slack_webhook_url)
    return JobService(
        SupabaseJobRepository(client),
        slack_notifier=slack,
        integrations=integrations,
    )


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_job(
    body: CreateJobCommand,
    service: JobService = Depends(get_job_service),
) -> dict[str, UUID]:
    # Parse/validate JSON into CreateJobCommand (Pydantic) already happened.
    # Run sync Supabase client off the event loop thread.
    try:
        job_id = await asyncio.to_thread(service.create_job, body)
    except ValueError as e:
        # Map domain/infra validation failures to a 400 for bad client input / constraint errors.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    # 201 Created + JSON body with new id (common REST pattern).
    return {"id": job_id}


@router.get("/published")
async def list_published_jobs(
    service: JobService = Depends(get_job_service),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, list]:
    rows = await asyncio.to_thread(lambda: service.list_published_jobs(limit=limit))

    return {"items": rows}


@router.get("/{job_id}")
async def get_job(
    job_id: UUID,
    service: JobService = Depends(get_job_service),
) -> dict:
    row = await asyncio.to_thread(service.get_job, job_id)

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return row


@router.patch("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_job(
    job_id: UUID,
    body: UpdateJobCommand,
    service: JobService = Depends(get_job_service),
) -> None:
    """HTTP PATCH: partial update; when ``locations`` is sent, it replaces all location rows."""
    try:
        await asyncio.to_thread(service.update_job, job_id, body)
    except ValueError as e:
        msg = str(e)

        if msg == "Job not found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from e

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from e


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    service: JobService = Depends(get_job_service),
) -> None:
    deleted = await asyncio.to_thread(service.delete_job, job_id)

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
