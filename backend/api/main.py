"""FastAPI application — middleware and routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.deps import get_settings
from backend.api.error_handling import register_exception_handlers
from backend.api.routers import companies, jobs, seekers
from backend.api.routers.health import router as health_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CDTM Job Board API")
    register_exception_handlers(app)

    @app.get("/", tags=["meta"])
    def root() -> dict[str, str]:
        return {"message": "Welcome to the CDTM Job Board API"}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(health_router)
    api_prefix = settings.api_route_prefix
    app.include_router(companies.router, prefix=api_prefix)
    app.include_router(jobs.router, prefix=api_prefix)
    app.include_router(seekers.router, prefix=api_prefix)
    return app


app = create_app()
