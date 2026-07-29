"""Adaptadores de transición sobre capacidades existentes, sin dominio Case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.cases.contracts import (
    DocumentBatchReference,
    EvidenceReference,
    ExtractionReference,
    LegacyHpnReference,
    LegacyNetworkReference,
    LegacySourceHealth,
    PublicDocumentReference,
    ScopedRetrievalQuery,
    ScopedRetrievalResult,
    TransitionWarningCode,
)
from app.cases.errors import TransitionAdapterError, TransitionErrorCode
from app.core.Log import log_warning
from app.core.exceptions import GraphError, HpnError
from app.documents import (
    DocumentBatch,
    DocumentCatalogFacade,
    DocumentExtractionError,
    DocumentExtractionFacade,
    DocumentRead,
    ExtractionSummary,
)
from app.graph import HpnGraphProjection, LegacyLegalNetworkFacade
from app.legal import HpnMatrixDetail, LegacyHpnFacade
from app.retrieval import (
    HybridSearchRequest,
    HybridSearchResponse,
    ScopedHybridRetrievalFacade,
    TextMatchMode,
)


class _DocumentCatalog(Protocol):
    async def resolve_many(self, document_ids: tuple[UUID, ...]) -> DocumentBatch: ...


class _ExtractionFacade(Protocol):
    async def status(self, document_id: UUID) -> DocumentRead | None: ...

    async def request(self, document_id: UUID) -> ExtractionSummary: ...


class _RetrievalFacade(Protocol):
    async def search(
        self,
        request: HybridSearchRequest,
        *,
        request_id: str | None = None,
    ) -> HybridSearchResponse: ...


class _HpnFacade(Protocol):
    async def detail(self, matrix_id: UUID) -> HpnMatrixDetail: ...


class _NetworkFacade(Protocol):
    async def project(
        self,
        matrix_id: UUID,
        *,
        request_id: str | None = None,
    ) -> HpnGraphProjection: ...


class DocumentAccessAdapter:
    """Convierte contratos documentales públicos a referencias de transición."""

    def __init__(self, catalog: _DocumentCatalog) -> None:
        self._catalog = catalog

    async def resolve_documents(
        self, document_ids: tuple[UUID, ...]
    ) -> DocumentBatchReference:
        try:
            batch = await self._catalog.resolve_many(document_ids)
            return DocumentBatchReference(
                items=tuple(_document_reference(item) for item in batch.items),
                missing_document_ids=batch.missing_document_ids,
            )
        except TransitionAdapterError:
            raise
        except Exception as exc:
            raise _adapter_failure(
                TransitionErrorCode.DEPENDENCY_ERROR,
                adapter="documents",
                stage="resolve",
                error=exc,
            ) from exc


class DocumentExtractionAdapter:
    """Consulta y delega la extracción sin implementar PyMuPDF nuevamente."""

    def __init__(self, facade: _ExtractionFacade) -> None:
        self._facade = facade

    async def get_status(self, document_id: UUID) -> ExtractionReference:
        try:
            document = await self._facade.status(document_id)
            if document is None:
                raise TransitionAdapterError(
                    TransitionErrorCode.DOCUMENT_NOT_FOUND,
                    adapter="extraction",
                    stage="status",
                )
            return ExtractionReference(document_id=document.id, status=document.status.value)
        except TransitionAdapterError:
            raise
        except Exception as exc:
            raise _adapter_failure(
                TransitionErrorCode.DEPENDENCY_ERROR,
                adapter="extraction",
                stage="status",
                error=exc,
            ) from exc

    async def request_extraction(self, document_id: UUID) -> ExtractionReference:
        try:
            result = await self._facade.request(document_id)
            return ExtractionReference(
                document_id=result.document_id,
                status=result.status.value,
                total_pages=result.total_pages,
                total_chunks=result.total_chunks,
                total_characters=result.total_characters,
            )
        except DocumentExtractionError as exc:
            code = (
                TransitionErrorCode.DOCUMENT_NOT_FOUND
                if exc.code == "DOCUMENT_NOT_FOUND"
                else TransitionErrorCode.EXTRACTION_REJECTED
            )
            raise _adapter_failure(
                code,
                adapter="extraction",
                stage="request",
                error=exc,
            ) from exc
        except TransitionAdapterError:
            raise
        except Exception as exc:
            raise _adapter_failure(
                TransitionErrorCode.DEPENDENCY_ERROR,
                adapter="extraction",
                stage="request",
                error=exc,
            ) from exc


class ScopedRetrievalAdapter:
    """Impone alcance documental antes de delegar en recuperación gobernada."""

    def __init__(self, facade: _RetrievalFacade) -> None:
        self._facade = facade

    async def search(
        self,
        request: ScopedRetrievalQuery,
        *,
        request_id: str | None = None,
    ) -> ScopedRetrievalResult:
        if len(request.scope.document_ids) != 1:
            raise _adapter_failure(
                TransitionErrorCode.RETRIEVAL_SCOPE_UNSUPPORTED,
                adapter="retrieval",
                stage="scope",
            )
        scoped_document_id = request.scope.document_ids[0]
        try:
            response = await self._facade.search(
                HybridSearchRequest(
                    query=request.query,
                    text_match_mode=TextMatchMode(request.text_match_mode.value),
                    top_k=request.top_k,
                    document_id=scoped_document_id,
                ),
                request_id=request_id,
            )
            if any(item.document_id != scoped_document_id for item in response.items):
                raise TransitionAdapterError(
                    TransitionErrorCode.RETRIEVAL_REJECTED,
                    adapter="retrieval",
                    stage="revalidate",
                )
            return ScopedRetrievalResult(
                items=tuple(
                    EvidenceReference(
                        document_id=item.document_id,
                        document_name=item.document_name,
                        document_type=item.document_type.value,
                        knowledge_layer=item.knowledge_layer.value,
                        chunk_index=item.chunk_index,
                        start_page=item.start_page,
                        end_page=item.end_page,
                        hybrid_score=item.hybrid_score,
                        appeared_in_text=item.appeared_in_text,
                        appeared_in_semantic=item.appeared_in_semantic,
                        text_rank=item.text_rank,
                        semantic_rank=item.semantic_rank,
                    )
                    for item in response.items
                ),
                returned=response.returned,
                top_k=response.top_k,
            )
        except TransitionAdapterError:
            raise
        except Exception as exc:
            raise _adapter_failure(
                TransitionErrorCode.RETRIEVAL_REJECTED,
                adapter="retrieval",
                stage="search",
                error=exc,
            ) from exc


class LegacyHpnAdapter:
    """Expone un resumen legacy sin atribuir la matriz a un caso."""

    def __init__(self, facade: _HpnFacade) -> None:
        self._facade = facade

    async def get_matrix(self, matrix_id: UUID) -> LegacyHpnReference:
        try:
            detail = await self._facade.detail(matrix_id)
            summary = detail.validation_summary
            warnings: list[TransitionWarningCode] = []
            if summary.stale_source_count:
                warnings.append(TransitionWarningCode.SOURCE_STALE)
            if summary.unavailable_source_count:
                warnings.append(TransitionWarningCode.SOURCE_UNAVAILABLE)
            if detail.matrix.status.value == "archived":
                warnings.append(TransitionWarningCode.MATRIX_ARCHIVED)
            if not summary.valid_for_review:
                warnings.append(TransitionWarningCode.REVIEW_REQUIRED)
            return LegacyHpnReference(
                public_matrix_id=detail.matrix.id,
                status=detail.matrix.status.value,
                fact_count=summary.fact_count,
                evidence_count=summary.evidence_count,
                norm_count=summary.norm_count,
                relation_count=summary.relation_count,
                stale_source_count=summary.stale_source_count,
                unavailable_source_count=summary.unavailable_source_count,
                read_only=detail.matrix.status.value == "archived",
                warnings=tuple(warnings),
                display_name=_safe_matrix_display_name(detail.matrix),
                source_health=_source_health(
                    stale_count=summary.stale_source_count,
                    unavailable_count=summary.unavailable_source_count,
                ),
            )
        except HpnError as exc:
            code = (
                TransitionErrorCode.HPN_NOT_FOUND
                if exc.code == "HPN_MATRIX_NOT_FOUND"
                else TransitionErrorCode.HPN_REJECTED
            )
            raise _adapter_failure(
                code,
                adapter="hpn_legacy",
                stage="detail",
                error=exc,
            ) from exc
        except TransitionAdapterError:
            raise
        except Exception as exc:
            raise _adapter_failure(
                TransitionErrorCode.DEPENDENCY_ERROR,
                adapter="hpn_legacy",
                stage="detail",
                error=exc,
            ) from exc


class LegacyLegalNetworkAdapter:
    """Resume una proyección efímera; no devuelve NetworkX ni HTML."""

    def __init__(self, facade: _NetworkFacade) -> None:
        self._facade = facade

    async def project(
        self,
        matrix_id: UUID,
        *,
        request_id: str | None = None,
    ) -> LegacyNetworkReference:
        try:
            projection = await self._facade.project(matrix_id, request_id=request_id)
            return LegacyNetworkReference(
                public_matrix_id=projection.matrix.id,
                node_count=projection.summary.node_count,
                edge_count=projection.summary.edge_count,
                disconnected_components=projection.summary.disconnected_components,
                has_directed_cycles=projection.summary.has_directed_cycles,
                warning_codes=tuple(warning.code for warning in projection.warnings),
                requires_professional_review=projection.requires_professional_review,
            )
        except GraphError as exc:
            raise _adapter_failure(
                TransitionErrorCode.NETWORK_REJECTED,
                adapter="network_legacy",
                stage="project",
                error=exc,
            ) from exc
        except TransitionAdapterError:
            raise
        except Exception as exc:
            raise _adapter_failure(
                TransitionErrorCode.DEPENDENCY_ERROR,
                adapter="network_legacy",
                stage="project",
                error=exc,
            ) from exc


@dataclass(frozen=True, slots=True)
class TransitionAdapters:
    documents: DocumentAccessAdapter
    extraction: DocumentExtractionAdapter
    retrieval: ScopedRetrievalAdapter
    hpn: LegacyHpnAdapter
    network: LegacyLegalNetworkAdapter


def build_transition_adapters(session: AsyncSession) -> TransitionAdapters:
    """Compone adaptadores sin ejecutar consultas ni registrarlos en FastAPI."""

    return TransitionAdapters(
        documents=DocumentAccessAdapter(DocumentCatalogFacade(session)),
        extraction=DocumentExtractionAdapter(DocumentExtractionFacade(session)),
        retrieval=ScopedRetrievalAdapter(ScopedHybridRetrievalFacade(session)),
        hpn=LegacyHpnAdapter(LegacyHpnFacade(session)),
        network=LegacyLegalNetworkAdapter(LegacyLegalNetworkFacade(session)),
    )


def _document_reference(document: DocumentRead) -> PublicDocumentReference:
    warnings = (
        ()
        if document.rag_eligible
        else (TransitionWarningCode.DOCUMENT_NOT_RAG_ELIGIBLE,)
    )
    return PublicDocumentReference(
        document_id=document.id,
        display_name=document.display_name,
        document_type=document.document_type.value,
        knowledge_layer=document.knowledge_layer.value,
        extraction_status=document.status.value,
        review_status=document.review_status.value,
        legal_validity_status=document.legal_validity_status.value,
        index_status=document.index_status.value,
        rag_eligible=document.rag_eligible,
        warnings=warnings,
    )


def _source_health(*, stale_count: int, unavailable_count: int) -> LegacySourceHealth:
    if unavailable_count:
        return LegacySourceHealth.UNAVAILABLE
    if stale_count:
        return LegacySourceHealth.STALE
    return LegacySourceHealth.VALID


def _safe_matrix_display_name(matrix: object) -> str:
    title = getattr(matrix, "title", None)
    return title.strip() if isinstance(title, str) and title.strip() else "Matriz HPN"


def _adapter_failure(
    code: TransitionErrorCode,
    *,
    adapter: str,
    stage: str,
    error: Exception | None = None,
) -> TransitionAdapterError:
    log_warning(
        "Adaptador de transición rechazó la operación",
        operation="case_transition_adapter",
        adapter=adapter,
        stage=stage,
        error_code=code.value,
        exception_type=type(error).__name__ if error is not None else None,
    )
    return TransitionAdapterError(code, adapter=adapter, stage=stage)
