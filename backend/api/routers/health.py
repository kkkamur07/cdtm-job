"""Liveness endpoint.

Industry practice:
- **Liveness** (`/health`): HTTP **200** + small JSON body means “process is up”.
  Load balancers and Kubernetes use this to restart unhealthy pods. Returning **204 No Content**
  is also valid but less common for JSON APIs.
- **Readiness** (often `/ready` or `/health/ready`): HTTP **200** only if dependencies (DB,
  queue) are usable; otherwise **503** so traffic is not routed here until ready.

This app exposes a simple liveness probe only.
"""

from fastapi import APIRouter, status

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict[str, str]:
    return {"status": "ok"}
