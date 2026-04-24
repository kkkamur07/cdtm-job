from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import companies, health, jobs, seekers
from api.settings import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Warm settings (fail fast on bad .env in dev)
    get_settings()
    yield


def create_app() -> FastAPI:
    """Build the ASGI app: middleware + mounted routers (see each router module for paths)."""
    settings = get_settings()
    app = FastAPI(title="CDTM Job Board API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ``include_router`` attaches another router's routes to this app.
    # ``prefix`` prepends a URL segment (e.g. jobs live under /api/v1/jobs/...).
    app.include_router(health.router)
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(companies.router, prefix="/api/v1")
    app.include_router(seekers.router, prefix="/api/v1")

    return app


app = create_app()
