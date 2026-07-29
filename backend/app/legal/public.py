"""Lectura pública interna de matrices HPN legacy, sin semántica de caso."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.hpn import HpnMatrixDetail
from app.services.hpn_service import HpnService


class LegacyHpnFacade:
    """Conserva HPN como recurso global no asociado a Case."""

    def __init__(self, session: AsyncSession) -> None:
        self._service = HpnService(session)

    async def detail(self, matrix_id: UUID) -> HpnMatrixDetail:
        return await self._service.detail(matrix_id)
