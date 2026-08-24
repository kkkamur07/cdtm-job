from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from backend.core.api.pagination import PageParamsDep
from backend.identity.api.deps import PrincipalDep
from backend.paths.api.deps import PathServiceDep
from backend.paths.api.schemas import (
    MemberPathPublic,
    PathFlowPublic,
    PathGroupsPublic,
    PathMemberPublic,
    PathMembersPublic,
)
from backend.paths.application.ports import PathFilters

router = APIRouter(prefix="/paths", tags=["paths"])


def _filters(
    class_id: int | None,
    study_group: str | None,
    first_step_group: str | None,
    current_group: str | None,
) -> PathFilters:
    return PathFilters(
        class_id=class_id,
        study_group=study_group,
        first_step_group=first_step_group,
        current_group=current_group,
    )


@router.get("/flow", response_model=PathFlowPublic)
async def flow(
    service: PathServiceDep,
    _: PrincipalDep,
    class_id: Annotated[int | None, Query()] = None,
    study_group: Annotated[str | None, Query()] = None,
    first_step_group: Annotated[str | None, Query()] = None,
    current_group: Annotated[str | None, Query()] = None,
) -> PathFlowPublic:
    """Four columns: what people studied, their first step, where they are, what they offer."""
    result = await service.flow(_filters(class_id, study_group, first_step_group, current_group))
    return PathFlowPublic.model_validate(result.model_dump())


@router.get("/groups", response_model=PathGroupsPublic)
async def groups(service: PathServiceDep, _: PrincipalDep) -> PathGroupsPublic:
    return PathGroupsPublic(**await service.groups())


@router.get("/members", response_model=PathMembersPublic)
async def members_in_group(
    service: PathServiceDep,
    page: PageParamsDep,
    _: PrincipalDep,
    stage: Annotated[str, Query(pattern="^(study|first_step|current)$")],
    group: Annotated[str, Query(max_length=120)],
    class_id: Annotated[int | None, Query()] = None,
    study_group: Annotated[str | None, Query()] = None,
    first_step_group: Annotated[str | None, Query()] = None,
    current_group: Annotated[str | None, Query()] = None,
) -> PathMembersPublic:
    result = await service.members_in(
        stage=stage,
        group=group,
        skip=page.skip,
        limit=page.limit,
        filters=_filters(class_id, study_group, first_step_group, current_group),
    )
    return PathMembersPublic(
        items=[PathMemberPublic.model_validate(m) for m in result.items], total=result.total
    )


@router.get("/members/{slug}", response_model=MemberPathPublic)
async def member_path(slug: str, service: PathServiceDep, _: PrincipalDep) -> MemberPathPublic:
    """One member's path. Was ``/community/members/{slug}/path``."""
    return MemberPathPublic.model_validate(await service.member_path_by_slug(slug))
