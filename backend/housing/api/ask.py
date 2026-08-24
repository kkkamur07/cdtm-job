from __future__ import annotations

from fastapi import APIRouter

from backend.core.llm import strict_json_schema
from backend.core.llm.ask import MAX_ASK_LIMIT
from backend.core.llm.phrases import CITIES
from backend.core.schemas.ask import AskExplainRequest, AskRequest
from backend.housing.api.deps import HousingAskServiceDep
from backend.housing.api.schemas import (
    HousingAskAnswerPublic,
    HousingAskInterpretationPublic,
    HousingAskSchemaPublic,
)
from backend.housing.domain import HousingKind, HousingQuery
from backend.housing.infrastructure.housing_ask_translator_rules import DISTRICTS
from backend.identity.api.deps import ActorDep, PrincipalDep

router = APIRouter(prefix="/housing/ask", tags=["housing"])


@router.post("/", response_model=HousingAskAnswerPublic)
async def ask_housing(
    body: AskRequest, actor: ActorDep, service: HousingAskServiceDep
) -> HousingAskAnswerPublic:
    answer = await service.ask(
        body.question, actor=actor, skip=body.skip, limit=body.limit, language=body.language
    )
    # From the object, not from ``answer.model_dump()``: the dump serialised every field
    # and every nested model only for the validator to build them all again.
    return HousingAskAnswerPublic.model_validate(answer)


@router.post("/explain", response_model=HousingAskInterpretationPublic)
async def explain_housing(
    body: AskExplainRequest, actor: ActorDep, service: HousingAskServiceDep
) -> HousingAskInterpretationPublic:
    interpretation = await service.explain(body.question, actor=actor, language=body.language)
    return HousingAskInterpretationPublic.model_validate(interpretation)


@router.get("/schema", response_model=HousingAskSchemaPublic)
async def housing_ask_schema(_: PrincipalDep) -> HousingAskSchemaPublic:
    return HousingAskSchemaPublic(
        json_schema=strict_json_schema(HousingQuery),
        kinds=[k.value for k in HousingKind],
        # The words the keyword translator recognises without help. They are suggestions
        # for the UI, not a closed list: any other city or district still reaches the
        # filter through the model or through free text.
        districts=sorted(set(DISTRICTS.values())),
        cities=sorted(set(CITIES.values())),
        max_limit=MAX_ASK_LIMIT,
    )
