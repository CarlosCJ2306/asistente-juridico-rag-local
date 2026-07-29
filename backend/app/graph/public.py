"""Proyección pública interna de Red legacy sin persistir grafos."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.hpn_graph import HpnGraphProjection
from app.services.hpn_graph_service import HpnGraphService


class LegacyLegalNetworkFacade:
    """Delega una única construcción al servicio NetworkX vigente."""

    def __init__(self, session: AsyncSession) -> None:
        self._service = HpnGraphService(session)

    async def project(
        self,
        matrix_id: UUID,
        *,
        request_id: str | None = None,
    ) -> HpnGraphProjection:
        return await self._service.project(matrix_id, request_id=request_id)
