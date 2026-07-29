"""Fachada pública mínima de la recuperación híbrida gobernada."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.hybrid_search import HybridSearchRequest, HybridSearchResponse
from app.services.hybrid_search_service import HybridSearchService


class ScopedHybridRetrievalFacade:
    """Delega una búsqueda ya validada al servicio híbrido oficial."""

    def __init__(self, session: AsyncSession) -> None:
        self._service = HybridSearchService(session)

    async def search(
        self,
        request: HybridSearchRequest,
        *,
        request_id: str | None = None,
    ) -> HybridSearchResponse:
        return await self._service.search(request, request_id=request_id)
