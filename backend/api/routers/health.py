"""Service liveness — does not verify database connectivity unless you extend it."""

from fastapi import APIRouter

from backend.api.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, status_code=200)
async def health() -> HealthResponse:
    """Return 200 with a fixed body when the API process is running."""
    return HealthResponse()
