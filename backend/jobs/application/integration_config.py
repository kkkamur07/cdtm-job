"""Optional integration keys passed into ``JobService`` without importing ``api``."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrationConfig:
    resend_api_key: str | None = None
    posthog_api_key: str | None = None
