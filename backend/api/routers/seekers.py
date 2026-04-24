import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from seekers.application.service import SeekerService

router = APIRouter(prefix="/seekers", tags=["seekers"])


def get_seeker_service() -> SeekerService:
    return SeekerService()


@router.get("/")
async def list_seekers(
    service: SeekerService = Depends(get_seeker_service),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, list | str]:
    items = await asyncio.to_thread(lambda: service.list_seekers(limit=limit))
    return {
        "items": items,
        "note": "Seeker profiles are post-v1 (Supabase Auth + Google + profiles table).",
    }


@router.get("/{seeker_id}")
async def get_seeker(
    seeker_id: UUID,
    service: SeekerService = Depends(get_seeker_service),
) -> dict:
    try:
        return await asyncio.to_thread(service.get_seeker, seeker_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e)) from e
