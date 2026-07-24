"""Servicio sin persistencia para preparar embeddings de consultas y chunks."""

from __future__ import annotations

from collections.abc import Sequence

from app.ai.embedding_model import EmbeddedChunk, EmbeddingError, EmbeddingModel
from app.core.config import settings
from app.database.models.document_chunk import DocumentChunk


class EmbeddingService:
    """Aplica prefijos E5 y delega la codificación local por lotes."""

    def __init__(self, model: EmbeddingModel) -> None:
        self.model = model

    @staticmethod
    def _validate_text(text: str) -> str:
        if not text or not text.strip():
            raise EmbeddingError("EMBEDDING_INPUT_EMPTY")
        return text

    def embed_query(self, text: str) -> list[float]:
        return self.model.encode([f"{settings.embedding_query_prefix} {self._validate_text(text)}"])[0]

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        prepared = [f"{settings.embedding_passage_prefix} {self._validate_text(text)}" for text in texts]
        return self.model.encode(prepared)

    def embed_chunks(self, chunks: Sequence[DocumentChunk]) -> list[EmbeddedChunk]:
        vectors = self.embed_passages([chunk.text for chunk in chunks])
        return [
            EmbeddedChunk(
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                document_id=chunk.document_id,
                vector=vector,
                dimension=len(vector),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
