from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response

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
from backend.paths.application.path_service import FLOW_TTL_SECONDS, GROUPS_TTL_SECONDS
from backend.paths.application.ports import PathFilters

router = APIRouter(prefix="/paths", tags=["paths"])

#: Longest group name a caller may send. The names are a fixed vocabulary (the longest is
#: "Natural Sciences & Math"), so anything longer matches nothing; the cap is what stops an
#: unbounded string reaching the query and the flow cache's key.
MAX_GROUP_NAME = 120


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
    response: Response,
    _: PrincipalDep,
    class_id: Annotated[int | None, Query()] = None,
    study_group: Annotated[str | None, Query(max_length=MAX_GROUP_NAME)] = None,
    first_step_group: Annotated[str | None, Query(max_length=MAX_GROUP_NAME)] = None,
    current_group: Annotated[str | None, Query(max_length=MAX_GROUP_NAME)] = None,
) -> PathFlowPublic:
    """Four columns: what people studied, their first step, where they are, what they offer."""
    result = await service.flow(_filters(class_id, study_group, first_step_group, current_group))
    # private, never public: the route is behind a bearer token even though the picture is
    # the same for everybody who can see it.
    response.headers["Cache-Control"] = f"private, max-age={FLOW_TTL_SECONDS}"
    # From the object, not from ``result.model_dump()``. The flow is the widest body this
    # API returns (every node and every link of the Sankey), and dumping it to primitives
    # only to validate them straight back cost a second full pass over all of it.
    return PathFlowPublic.model_validate(result, from_attributes=True)


@router.get("/groups", response_model=PathGroupsPublic)
async def groups(service: PathServiceDep, response: Response, _: PrincipalDep) -> PathGroupsPublic:
    result = await service.groups()
    response.headers["Cache-Control"] = f"private, max-age={GROUPS_TTL_SECONDS}"
    return PathGroupsPublic(**result)


@router.get("/members", response_model=PathMembersPublic)
async def members_in_group(
    service: PathServiceDep,
    page: PageParamsDep,
    _: PrincipalDep,
    stage: Annotated[str, Query(pattern="^(study|first_step|current)$")],
    group: Annotated[str, Query(max_length=MAX_GROUP_NAME)],
    class_id: Annotated[int | None, Query()] = None,
    study_group: Annotated[str | None, Query(max_length=MAX_GROUP_NAME)] = None,
    first_step_group: Annotated[str | None, Query(max_length=MAX_GROUP_NAME)] = None,
    current_group: Annotated[str | None, Query(max_length=MAX_GROUP_NAME)] = None,
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
