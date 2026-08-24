"""Ask over the directory, and the Paths picture of the answer.

This module is the one place the members board and the paths board are put side by side.
The two services are called one after the other and their results are returned in one
body, which is what an API layer is allowed to do; nothing under ``application/`` knows the
other context exists.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.core.llm import strict_json_schema
from backend.core.llm.ask import MAX_ASK_LIMIT
from backend.core.schemas.ask import AskExplainRequest, AskRequest
from backend.identity.api.deps import ActorDep, PrincipalDep
from backend.members.api.deps import AskServiceDep
from backend.members.api.schemas import (
    AskAnswerPublic,
    AskInterpretationPublic,
    AskSchemaPublic,
)
from backend.members.domain import Intent, MemberQuery, Role
from backend.paths.api.deps import PathServiceDep
from backend.paths.api.schemas import PathFlowPublic
from backend.paths.application.ports import PathFilters
from backend.paths.domain import CAREER_GROUP_NAMES, STUDY_GROUP_NAMES

router = APIRouter(prefix="/members/ask", tags=["members"])


@router.post("/", response_model=AskAnswerPublic)
async def ask(
    body: AskRequest, actor: ActorDep, service: AskServiceDep, paths: PathServiceDep
) -> AskAnswerPublic:
    answer = await service.ask(
        body.question, actor=actor, skip=body.skip, limit=body.limit, language=body.language
    )
    public = AskAnswerPublic.model_validate(answer.model_dump())
    if not answer.total:
        # No Sankey to draw for nobody, and it keeps the empty answer to one round trip.
        return public
    # The flow is drawn over every matching member, not the page that was returned, so the
    # ids come from a second pass over the same filters rather than from ``answer.members``.
    ids = await service.matching_member_ids(answer.interpretation)
    flow = await paths.flow(PathFilters(member_ids=tuple(ids)))
    return public.model_copy(update={"flow": PathFlowPublic.model_validate(flow.model_dump())})


@router.post("/explain", response_model=AskInterpretationPublic)
async def explain(
    body: AskExplainRequest, actor: ActorDep, service: AskServiceDep
) -> AskInterpretationPublic:
    """Translate without searching, for the live "this is how I read it" preview."""
    interpretation = await service.explain(body.question, actor=actor, language=body.language)
    return AskInterpretationPublic.model_validate(interpretation.model_dump())


@router.get("/schema", response_model=AskSchemaPublic)
async def ask_schema(_: PrincipalDep) -> AskSchemaPublic:
    """The filter object and its allowed values, so the UI can render editable chips."""
    return AskSchemaPublic(
        json_schema=strict_json_schema(MemberQuery),
        study_groups=list(STUDY_GROUP_NAMES),
        career_groups=list(CAREER_GROUP_NAMES),
        intents=[i.value for i in Intent],
        roles=[r.value for r in Role],
        sorts=["relevance", "name", "class"],
        max_limit=MAX_ASK_LIMIT,
    )
