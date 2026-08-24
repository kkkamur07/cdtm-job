from __future__ import annotations

from fastapi import APIRouter

from backend.core.llm import strict_json_schema
from backend.identity.api.deps import ActorDep, PrincipalDep
from backend.jobboard.api.deps import JobAskServiceDep
from backend.jobboard.api.schemas import (
    JobAskAnswerPublic,
    JobAskExplainRequest,
    JobAskInterpretationPublic,
    JobAskRequest,
    JobAskSchemaPublic,
)
from backend.jobboard.domain import (
    MAX_ASK_LIMIT,
    EmploymentType,
    ExperienceLevel,
    JobQuery,
    WorkArrangement,
)

router = APIRouter(prefix="/jobs/ask", tags=["jobs"])


@router.post("/", response_model=JobAskAnswerPublic)
async def ask_jobs(
    body: JobAskRequest, actor: ActorDep, service: JobAskServiceDep
) -> JobAskAnswerPublic:
    """Reading the board is public; asking is not, because a question costs money."""
    answer = await service.ask(
        body.question,
        actor=actor,
        skip=body.skip,
        limit=body.limit,
        language=body.language,
    )
    return JobAskAnswerPublic.model_validate(answer.model_dump())


@router.post("/explain", response_model=JobAskInterpretationPublic)
async def explain_jobs(
    body: JobAskExplainRequest, actor: ActorDep, service: JobAskServiceDep
) -> JobAskInterpretationPublic:
    interpretation = await service.explain(body.question, actor=actor, language=body.language)
    return JobAskInterpretationPublic.model_validate(interpretation.model_dump())


@router.get("/schema", response_model=JobAskSchemaPublic)
async def job_ask_schema(_: PrincipalDep) -> JobAskSchemaPublic:
    return JobAskSchemaPublic(
        json_schema=strict_json_schema(JobQuery),
        employment_types=[e.value for e in EmploymentType],
        work_arrangements=[w.value for w in WorkArrangement],
        experience_levels=[x.value for x in ExperienceLevel],
        sorts=["relevance", "recent", "salary"],
        max_limit=MAX_ASK_LIMIT,
    )
