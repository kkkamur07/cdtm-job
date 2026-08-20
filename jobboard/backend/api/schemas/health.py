"""Health check response."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Liveness payload returned with HTTP 200 when the process is up."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
