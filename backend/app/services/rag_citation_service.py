"""Registro efímero y validación estricta de citas del Chat RAG."""

from __future__ import annotations

import html
import hashlib
import re
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.core.config import settings
from app.core.source_sanitization import sanitize_document_name
from app.database.models.document import DocumentType, KnowledgeLayer
from app.database.repositories.semantic_chunk_repository import (
    ActiveChunk,
)
from app.schemas.rag_chat import RagCitation
from app.services.document_governance_service import DocumentGovernanceService


MARKER_PREFIX = "F"
MARKER_PATTERN = re.compile(r"\[F([1-9]\d*)\]")
CITATION_LIKE_PATTERN = re.compile(
    r"(?:\[\s*(?:f\s*-?\s*\d+|fuente\s+\d+)\s*\]?"
    r"|\[\s*(?:f|fuente)\s*\]"
    r"|\[\s*(?:f|fuente)\s*(?=$|[\r\n.,;:!?])"
    r"|\(\s*f\s*-?\s*\d+\s*\)"
    r"|\{\s*f\s*-?\s*\d+\s*\}"
    r"|\bf\s*-?\s*\d+\b)",
    flags=re.IGNORECASE,
)
AMBIGUOUS_MARKER_PATTERN = re.compile(
    r"(?:\[\s*(?:f|fuente)\s*\]?|\[\s*fuente\s+\d+\s*\]?)",
    flags=re.IGNORECASE,
)
OUTPUT_ERROR_CODE = "RAG_CITATION_OUTPUT_INVALID"
CITATION_VALIDATION_STAGE = "citation_validation"
CITATION_ERROR_STAGES = frozenset(
    {"citation_validation", "citation_metadata", "citation_revalidation"}
)
CITATION_REASON_CODES = frozenset(
    {
        "CITATION_NO_MARKERS",
        "CITATION_UNKNOWN_MARKER",
        "CITATION_INVALID_MARKER_FORMAT",
        "CITATION_AMBIGUOUS_MARKER",
        "CITATION_UNCITED_SUBSTANTIVE_ELEMENT",
        "CITATION_NO_SUBSTANTIVE_CONTENT",
        "CITATION_ONLY_MARKERS",
        "CITATION_FORBIDDEN_REFERENCE_CONTENT",
        "CITATION_DUPLICATE_SOURCE",
        "CITATION_ORDER_MISMATCH",
        "CITATION_COVERAGE_INVALID",
        "CITATION_OUTPUT_STRUCTURE_INVALID",
    }
)
FORBIDDEN_REFERENCE_PATTERN = re.compile(
    r"(?:https?://|www\."
    r"|\b[a-f0-9]{8}-[a-f0-9]{4}-[1-5a-f0-9]{4}-[89ab0-9][a-f0-9]{3}-[a-f0-9]{12}\b"
    r"|(?:[A-Za-z]:[\\/]|/(?:home|Users|var|tmp|storage|models)/)"
    r"|\b[^\s/\\<>]+\.(?:pdf|docx?)\b"
    r"|\b(?:p[aá]ginas?|chunk|documento)\s*(?:[:#]?\s*\d+|:)"
    r"|(?:^|\n)\s*(?:bibliograf[ií]a|fuentes?|referencias?)"
    r"(?:\s*:|\s*(?=\n|$)))",
    flags=re.IGNORECASE,
)


class RagCitationError(RuntimeError):
    """Error estable sin contenido documental."""

    def __init__(
        self,
        code: str,
        *,
        reason_code: str | None = None,
        stage: str | None = None,
        total_sources: int = 0,
        substantive_elements: int = 0,
        structural_errors: int = 0,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.error_code = code
        self.reason_code = (
            reason_code if reason_code in CITATION_REASON_CODES else None
        )
        self.stage = stage if stage in CITATION_ERROR_STAGES else None
        self.total_sources = self._safe_count(total_sources)
        self.substantive_elements = self._safe_count(substantive_elements)
        self.structural_errors = self._safe_count(structural_errors)

    @staticmethod
    def _safe_count(value: object) -> int:
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


class ActiveChunkReader(Protocol):
    async def get_active_by_ids(
        self, chunk_ids: list[UUID]
    ) -> dict[UUID, ActiveChunk]: ...


@dataclass(frozen=True)
class CitationSource:
    """Fuente interna efímera; nunca se serializa directamente."""

    marker: str
    chunk_id: UUID
    document_id: UUID
    document_name: str
    document_type: DocumentType
    chunk_index: int
    start_page: int
    end_page: int
    text_fingerprint: str
    knowledge_layer: KnowledgeLayer = KnowledgeLayer.PRIVATE_LIBRARY


@dataclass(frozen=True)
class CitationRegistry:
    """Registro determinista válido únicamente durante una respuesta."""

    sources: tuple[CitationSource, ...]

    @property
    def by_marker(self) -> dict[str, CitationSource]:
        return {source.marker: source for source in self.sources}

    @property
    def markers(self) -> tuple[str, ...]:
        return tuple(source.marker for source in self.sources)


class RagCitationService:
    """Asigna markers, valida la salida y revalida las fuentes en SQLite."""

    @staticmethod
    def marker(position: int) -> str:
        if isinstance(position, bool) or position < 1:
            raise RagCitationError("RAG_CITATION_METADATA_INVALID")
        return f"[{MARKER_PREFIX}{position}]"

    def build_registry(self, chunks: tuple[ActiveChunk, ...]) -> CitationRegistry:
        sources: list[CitationSource] = []
        seen: set[UUID] = set()
        for chunk in chunks:
            if chunk.chunk_id in seen:
                continue
            if len(sources) >= settings.rag_citation_max_sources:
                break
            self._validate_chunk_metadata(chunk)
            seen.add(chunk.chunk_id)
            sources.append(
                CitationSource(
                    marker=self.marker(len(sources) + 1),
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    document_name=chunk.document_name,
                    document_type=chunk.document_type,
                    knowledge_layer=chunk.knowledge_layer,
                    chunk_index=chunk.chunk_index,
                    start_page=chunk.start_page,
                    end_page=chunk.end_page,
                    text_fingerprint=hashlib.sha256(
                        chunk.text.encode("utf-8")
                    ).hexdigest(),
                )
            )
        return CitationRegistry(tuple(sources))

    def validate_answer(
        self,
        answer: str,
        registry: CitationRegistry,
    ) -> tuple[CitationSource, ...]:
        """Valida formato, pertenencia, contenido y cobertura por elemento."""

        total_sources = len(registry.sources)
        if not isinstance(answer, str) or not answer.strip():
            raise self._output_error(
                "CITATION_OUTPUT_STRUCTURE_INVALID",
                total_sources=total_sources,
            )
        if FORBIDDEN_REFERENCE_PATTERN.search(answer):
            raise self._output_error(
                "CITATION_FORBIDDEN_REFERENCE_CONTENT",
                total_sources=total_sources,
            )

        exact_matches = list(MARKER_PATTERN.finditer(answer))
        exact_spans = {match.span() for match in exact_matches}
        ambiguous = [
            match
            for match in CITATION_LIKE_PATTERN.finditer(answer)
            if match.span() not in exact_spans
        ]
        if ambiguous:
            reason_code = (
                "CITATION_AMBIGUOUS_MARKER"
                if any(AMBIGUOUS_MARKER_PATTERN.fullmatch(match.group(0)) for match in ambiguous)
                else "CITATION_INVALID_MARKER_FORMAT"
            )
            raise self._output_error(
                reason_code,
                total_sources=total_sources,
                structural_errors=len(ambiguous),
            )
        if not exact_matches:
            raise self._output_error(
                "CITATION_NO_MARKERS",
                total_sources=total_sources,
            )

        by_marker = registry.by_marker
        ordered: list[CitationSource] = []
        seen: set[str] = set()
        invalid = 0
        for match in exact_matches:
            marker = match.group(0)
            source = by_marker.get(marker)
            if source is None:
                invalid += 1
                continue
            if marker not in seen:
                ordered.append(source)
                seen.add(marker)
        if invalid:
            raise self._output_error(
                "CITATION_UNKNOWN_MARKER",
                total_sources=total_sources,
                structural_errors=invalid,
            )

        substantive = self._substantive_elements(answer)
        without_markers = self._plain_text(MARKER_PATTERN.sub("", answer))
        if not substantive:
            reason_code = (
                "CITATION_ONLY_MARKERS"
                if not any(character.isalnum() for character in without_markers)
                else "CITATION_NO_SUBSTANTIVE_CONTENT"
            )
            raise self._output_error(
                reason_code,
                total_sources=total_sources,
            )
        uncovered = sum(
            not bool(MARKER_PATTERN.search(element)) for element in substantive
        )
        if uncovered:
            raise self._output_error(
                "CITATION_UNCITED_SUBSTANTIVE_ELEMENT",
                total_sources=total_sources,
                substantive_elements=len(substantive),
                structural_errors=uncovered,
            )
        if not any(character.isalnum() for character in without_markers):
            raise self._output_error(
                "CITATION_ONLY_MARKERS",
                total_sources=total_sources,
                substantive_elements=len(substantive),
            )
        return tuple(ordered)

    @staticmethod
    def _output_error(
        reason_code: str,
        *,
        total_sources: int,
        substantive_elements: int = 0,
        structural_errors: int = 1,
    ) -> RagCitationError:
        return RagCitationError(
            OUTPUT_ERROR_CODE,
            reason_code=reason_code,
            stage=CITATION_VALIDATION_STAGE,
            total_sources=total_sources,
            substantive_elements=substantive_elements,
            structural_errors=structural_errors,
        )

    async def revalidate_sources(
        self,
        used_sources: tuple[CitationSource, ...],
        registry: CitationRegistry,
        repository: ActiveChunkReader,
    ) -> list[RagCitation]:
        """Comprueba en una lectura nueva que cada fuente citada sigue vigente."""

        registry_ids = {source.chunk_id for source in registry.sources}
        if any(source.chunk_id not in registry_ids for source in used_sources):
            raise RagCitationError("RAG_CITATION_SOURCE_STALE")
        current = await repository.get_active_by_ids(
            [source.chunk_id for source in used_sources]
        )
        citations: list[RagCitation] = []
        governance = DocumentGovernanceService()
        for source in used_sources:
            chunk = current.get(source.chunk_id)
            if (
                chunk is None
                or not governance.evaluate_rag_eligibility(
                    chunk.governance
                ).eligible
                or not self._matches(source, chunk)
            ):
                raise RagCitationError("RAG_CITATION_SOURCE_STALE")
            display_name = self.sanitize_document_name(chunk.document_name)
            citations.append(
                RagCitation(
                    marker=source.marker,
                    document_id=chunk.document_id,
                    document_name=display_name,
                    display_name=display_name,
                    document_type=chunk.document_type,
                    knowledge_layer=chunk.knowledge_layer,
                    chunk_index=chunk.chunk_index,
                    start_page=chunk.start_page,
                    end_page=chunk.end_page,
                )
            )
        return citations

    @staticmethod
    def sanitize_document_name(value: object) -> str:
        """Devuelve basename Unicode seguro sin usar el nombre almacenado."""

        return sanitize_document_name(
            value,
            max_length=settings.rag_source_name_max_length,
        )

    @staticmethod
    def _validate_chunk_metadata(chunk: ActiveChunk) -> None:
        if (
            not isinstance(chunk.chunk_id, UUID)
            or not isinstance(chunk.document_id, UUID)
            or not isinstance(chunk.document_type, DocumentType)
            or not isinstance(chunk.knowledge_layer, KnowledgeLayer)
            or isinstance(chunk.chunk_index, bool)
            or chunk.chunk_index < 1
            or isinstance(chunk.start_page, bool)
            or chunk.start_page < 1
            or isinstance(chunk.end_page, bool)
            or chunk.end_page < chunk.start_page
            or not isinstance(chunk.text, str)
            or not chunk.text.strip()
        ):
            raise RagCitationError("RAG_CITATION_METADATA_INVALID")

    @staticmethod
    def _matches(source: CitationSource, chunk: ActiveChunk) -> bool:
        return (
            source.chunk_id == chunk.chunk_id
            and source.document_id == chunk.document_id
            and source.document_type == chunk.document_type
            and source.knowledge_layer == chunk.knowledge_layer
            and source.chunk_index == chunk.chunk_index
            and source.start_page == chunk.start_page
            and source.end_page == chunk.end_page
            and source.document_name == chunk.document_name
            and source.text_fingerprint
            == hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
            and bool(chunk.text.strip())
        )

    @classmethod
    def _substantive_elements(cls, answer: str) -> list[str]:
        elements: list[str] = []
        for paragraph in re.split(r"\n\s*\n", answer):
            stripped = paragraph.strip()
            if not stripped:
                continue
            lines = [line.strip() for line in stripped.splitlines() if line.strip()]
            if any(re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)", line) for line in lines):
                candidates = lines
            else:
                candidates = [stripped]
            for candidate in candidates:
                if cls._is_structural(candidate):
                    continue
                plain = cls._plain_text(MARKER_PATTERN.sub("", candidate))
                if any(character.isalnum() for character in plain):
                    elements.append(candidate)
        return elements

    @staticmethod
    def _is_structural(value: str) -> bool:
        stripped = value.strip()
        if re.match(r"^#{1,6}\s+\S", stripped):
            heading = re.sub(r"^#{1,6}\s+", "", stripped)
            return len(heading) <= 80 and re.search(r"[.?!;]", heading) is None
        return len(stripped) <= 80 and stripped.endswith(":")

    @staticmethod
    def _plain_text(value: str) -> str:
        """Retira markup escapado para no confundir HTML vacío con contenido."""

        return re.sub(r"<[^>]*>", " ", html.unescape(value))
