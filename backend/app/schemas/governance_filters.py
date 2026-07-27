"""Validación compartida de filtros públicos de gobernanza documental."""

from __future__ import annotations

from app.database.models.document import KnowledgeLayer


def normalize_knowledge_layers(
    value: list[KnowledgeLayer] | None,
) -> list[KnowledgeLayer] | None:
    """Deduplica en orden estable y limita el filtro a las capas conocidas."""

    if value is None:
        return None
    normalized = list(dict.fromkeys(value))
    if len(normalized) > len(KnowledgeLayer):
        raise ValueError("La cantidad de capas de conocimiento supera el límite")
    return normalized
