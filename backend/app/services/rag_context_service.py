"""Lectura y revalidación del texto vigente desde SQLite."""

from __future__ import annotations

from uuid import UUID

from app.database.repositories.semantic_chunk_repository import ActiveChunk, SemanticChunkRepository
from app.schemas.hybrid_search import HybridSearchItem
from app.schemas.rag_chat import RagChatRequest
from app.services.document_governance_service import DocumentGovernanceService


class RagContextService:
    def __init__(self, repository: SemanticChunkRepository) -> None:
        self.repository = repository
        self.governance = DocumentGovernanceService()

    async def get_valid_chunks(
        self, items: list[HybridSearchItem], request: RagChatRequest
    ) -> list[ActiveChunk]:
        ordered_ids = list(dict.fromkeys(item.chunk_id for item in items))
        active = await self.repository.get_active_by_ids(ordered_ids)
        valid: list[ActiveChunk] = []
        seen: set[UUID] = set()
        for item in items:
            chunk = active.get(item.chunk_id)
            if (
                chunk is None
                or item.chunk_id in seen
                or not chunk.text.strip()
                or not self.governance.evaluate_rag_eligibility(
                    chunk.governance
                ).eligible
            ):
                continue
            if not self._matches(item, chunk, request):
                continue
            valid.append(chunk)
            seen.add(item.chunk_id)
        return valid

    @staticmethod
    def _matches(item: HybridSearchItem, chunk: ActiveChunk, request: RagChatRequest) -> bool:
        metadata_match = (
            item.document_id == chunk.document_id
            and item.document_type == chunk.document_type
            and item.knowledge_layer == chunk.knowledge_layer
            and item.chunk_index == chunk.chunk_index
            and item.start_page == chunk.start_page
            and item.end_page == chunk.end_page
        )
        if not metadata_match:
            return False
        if request.document_id is not None and chunk.document_id != request.document_id:
            return False
        if request.document_types and chunk.document_type not in request.document_types:
            return False
        if request.knowledge_layers and chunk.knowledge_layer not in request.knowledge_layers:
            return False
        if request.min_page is not None and chunk.start_page < request.min_page:
            return False
        return not (request.max_page is not None and chunk.end_page > request.max_page)
