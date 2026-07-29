"""Compuerta conservadora entre recuperación y generación jurídica."""

from __future__ import annotations

import math
import re
import unicodedata

from app.database.repositories.semantic_chunk_repository import ActiveChunk
from app.schemas.hybrid_search import HybridSearchResponse
from app.schemas.rag_chat import RagChatRequest


_COMMON_QUERY_TERMS = {
    "cual", "cuales", "como", "cuando", "donde", "sobre", "segun", "tambien",
    "eso", "esa", "ese", "esto", "esta", "aplica", "aplicable", "materia",
    "regulacion", "regimen", "norma", "normativa", "colombia", "colombiana",
    "colombiano", "documento", "evidencia", "informacion", "principal", "alcance",
    "que", "del", "los", "las", "una", "uno", "para", "por", "con", "sin",
}


def _fold(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )


def _terms(value: str) -> tuple[str, ...]:
    values = [
        term
        for term in re.findall(r"[a-z0-9]+", _fold(value))
        if len(term) >= 3 and term not in _COMMON_QUERY_TERMS
    ]
    if not values:
        values = [term for term in re.findall(r"[a-z0-9]+", _fold(value)) if len(term) >= 3]
    return tuple(dict.fromkeys(values))


class RagAnswerabilityService:
    """Exige acuerdo de fuentes y cobertura léxica antes de cargar Qwen."""

    def has_sufficient_evidence(
        self,
        *,
        retrieval_query: str,
        request: RagChatRequest,
        response: HybridSearchResponse,
        chunks: list[ActiveChunk],
    ) -> bool:
        query_terms = _terms(retrieval_query)
        if not query_terms or not chunks:
            return False
        chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        required = len(query_terms) if len(query_terms) <= 2 else math.ceil(len(query_terms) * 0.6)
        for item in response.items:
            chunk = chunks_by_id.get(item.chunk_id)
            if chunk is None:
                continue
            chunk_terms = set(re.findall(r"[a-z0-9]+", _fold(chunk.text)))
            covered = sum(term in chunk_terms for term in query_terms)
            if request.document_id is not None:
                if covered >= 1 and (
                    item.appeared_in_semantic
                    or (item.appeared_in_text and covered >= required)
                ):
                    return True
            elif (
                item.appeared_in_text
                and item.appeared_in_semantic
                and covered >= required
            ):
                return True
        return False
