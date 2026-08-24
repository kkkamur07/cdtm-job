"""Wiring for the network context."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from backend.identity.api.deps import DbDep
from backend.network.application.network_service import NetworkService
from backend.network.infrastructure.member_directory import SqlMemberDirectory
from backend.network.infrastructure.network_repository import SqlNetworkRepository


def get_network_service(db: DbDep) -> NetworkService:
    return NetworkService(SqlNetworkRepository(db), SqlMemberDirectory(db))


NetworkServiceDep = Annotated[NetworkService, Depends(get_network_service)]
