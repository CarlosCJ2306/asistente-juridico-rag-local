"""Segmentación jurídica determinista, sin tokenizadores ni modelos."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CleanPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class LegalChunk:
    chunk_index: int
    text: str
    char_count: int
    word_count: int
    start_page: int
    end_page: int


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?;:])\s+")


def _safe_overlap_suffix(text: str, overlap_size: int) -> str:
    """Obtiene un sufijo que empiece en palabra completa cuando sea posible."""

    if overlap_size <= 0:
        return ""
    start = max(0, len(text) - overlap_size)
    if start == 0:
        return text
    boundary = re.search(r"\s+", text[start:])
    if boundary is None:
        # Un token mayor que el máximo ya se divide de forma dura; no se usa
        # como overlap para no iniciar otro chunk a mitad de ese token.
        return ""
    return text[start + boundary.end() :]


def _split_hard_text(text: str, maximum_size: int) -> list[str]:
    """Divide por palabra antes de aplicar un corte duro a un token aislado."""

    pieces: list[str] = []
    remaining = text
    while len(remaining) > maximum_size:
        boundary = remaining.rfind(" ", 0, maximum_size + 1)
        if boundary > 0:
            pieces.append(remaining[:boundary])
            remaining = remaining[boundary + 1 :]
        else:
            # Un único token no cabe: este es el único corte duro permitido.
            pieces.append(remaining[:maximum_size])
            remaining = remaining[maximum_size:]
    if remaining:
        pieces.append(remaining)
    return pieces


def _split_large_text(text: str, maximum_size: int) -> list[str]:
    if len(text) <= maximum_size:
        return [text]
    sentences = _SENTENCE_BOUNDARY.split(text)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > maximum_size:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_split_hard_text(sentence, maximum_size))
        elif not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= maximum_size:
            current = f"{current} {sentence}"
        else:
            pieces.append(current)
            current = sentence
    if current:
        pieces.append(current)
    return pieces


def chunk_pages(
    pages: list[CleanPage],
    *,
    target_size: int,
    maximum_size: int,
    overlap_size: int,
) -> list[LegalChunk]:
    """Genera fragmentos ordenados y trazables por página."""

    if target_size <= 0 or maximum_size <= 0 or overlap_size < 0:
        raise ValueError("Los límites de chunk deben ser válidos")
    if target_size > maximum_size or overlap_size >= target_size:
        raise ValueError("Los límites de chunk son inconsistentes")
    units: list[tuple[int, str]] = []
    for page in pages:
        for paragraph in page.text.split("\n\n"):
            stripped = paragraph.strip()
            if stripped:
                units.extend((page.page_number, piece) for piece in _split_large_text(stripped, maximum_size))
    chunks: list[LegalChunk] = []
    current: list[tuple[int, str]] = []
    current_size = 0

    def emit() -> None:
        nonlocal current, current_size
        if not current:
            return
        text = "\n\n".join(item[1] for item in current)
        chunks.append(
            LegalChunk(
                chunk_index=len(chunks) + 1,
                text=text,
                char_count=len(text),
                word_count=len(text.split()),
                start_page=current[0][0],
                end_page=current[-1][0],
            )
        )
        overlap = _safe_overlap_suffix(text, overlap_size)
        current = [(current[-1][0], overlap)] if overlap else []
        current_size = len(overlap)

    for page_number, text in units:
        separator = 2 if current else 0
        if current and (current_size + separator + len(text) > maximum_size or current_size >= target_size):
            emit()
            separator = 2 if current else 0
        if current and current_size + separator + len(text) > maximum_size:
            # El solapamiento nunca puede crear un chunk que exceda el máximo.
            current = []
            current_size = 0
        current.append((page_number, text))
        current_size += (2 if len(current) > 1 else 0) + len(text)
    emit()
    return chunks
