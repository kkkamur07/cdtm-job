from __future__ import annotations

from fastapi import APIRouter

from backend.jobboard.api import ask, companies, jobs, seekers

router = APIRouter()
router.include_router(companies.router)
# Ask goes in first so /jobs/ask never has to compete with /jobs/{job_id}.
router.include_router(ask.router)
router.include_router(jobs.router)
router.include_router(seekers.router)
