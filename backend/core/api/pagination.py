from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query


@dataclass(frozen=True, slots=True)
class PageParams:
    skip: int
    limit: int


def page_params(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageParams:
    return PageParams(skip=skip, limit=limit)


PageParamsDep = Annotated[PageParams, Depends(page_params)]
