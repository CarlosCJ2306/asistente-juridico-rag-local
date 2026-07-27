"""Política central y transiciones de gobernanza documental."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.Log import log_info, log_warning
from app.database.models.document import (
    Document,
    DocumentStatus,
    IndexStatus,
    KnowledgeLayer,
    LegalValidityStatus,
    RagEligibilityReason,
    ReviewStatus,
    SourceKind,
    utc_now,
)
from app.schemas.document import DocumentRead, DocumentUploadGovernance


class DocumentGovernanceError(RuntimeError):
    """Error de dominio estable que no transporta metadatos documentales."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class DocumentEligibility:
    """Resultado calculado e inmutable de la política RAG documental."""

    eligible: bool
    reason_codes: tuple[RagEligibilityReason, ...]
    expired: bool
    requires_review: bool
    requires_indexing: bool


class GovernedDocument(Protocol):
    """Campos mínimos que permiten evaluar una fuente cargada desde SQLite."""

    @property
    def status(self) -> DocumentStatus: ...

    @property
    def knowledge_layer(self) -> KnowledgeLayer: ...

    @property
    def review_status(self) -> ReviewStatus: ...

    @property
    def legal_validity_status(self) -> LegalValidityStatus: ...

    @property
    def index_status(self) -> IndexStatus: ...

    @property
    def expires_at(self) -> datetime | None: ...

    @property
    def archived_at(self) -> datetime | None: ...

    @property
    def is_deleted(self) -> bool: ...


@dataclass(frozen=True)
class DocumentGovernanceSnapshot:
    """Instantánea inmutable para revalidar chunks sin consultas adicionales."""

    status: DocumentStatus = DocumentStatus.EXTRACTED
    knowledge_layer: KnowledgeLayer = KnowledgeLayer.PRIVATE_LIBRARY
    review_status: ReviewStatus = ReviewStatus.NOT_REQUIRED
    legal_validity_status: LegalValidityStatus = LegalValidityStatus.UNKNOWN
    index_status: IndexStatus = IndexStatus.INDEXED
    expires_at: datetime | None = None
    archived_at: datetime | None = None
    is_deleted: bool = False

    @classmethod
    def from_document(cls, document: GovernedDocument) -> "DocumentGovernanceSnapshot":
        return cls(
            status=document.status,
            knowledge_layer=document.knowledge_layer,
            review_status=document.review_status,
            legal_validity_status=document.legal_validity_status,
            index_status=document.index_status,
            expires_at=document.expires_at,
            archived_at=document.archived_at,
            is_deleted=document.is_deleted,
        )


class DocumentGovernanceService:
    """Evalúa y modifica gobernanza sin persistir elegibilidad ni hacer commit."""

    REVIEW_TRANSITIONS: ClassVar[
        dict[ReviewStatus, frozenset[ReviewStatus]]
    ] = {
        ReviewStatus.NOT_REQUIRED: frozenset(
            {ReviewStatus.NOT_REQUIRED, ReviewStatus.PENDING}
        ),
        ReviewStatus.PENDING: frozenset(
            {ReviewStatus.APPROVED, ReviewStatus.REJECTED}
        ),
        ReviewStatus.APPROVED: frozenset(
            {ReviewStatus.PENDING, ReviewStatus.ARCHIVED}
        ),
        ReviewStatus.REJECTED: frozenset(
            {ReviewStatus.PENDING, ReviewStatus.ARCHIVED}
        ),
        ReviewStatus.ARCHIVED: frozenset(),
    }
    LEGAL_VALIDITY_TRANSITIONS: ClassVar[
        dict[LegalValidityStatus, frozenset[LegalValidityStatus]]
    ] = {
        LegalValidityStatus.UNKNOWN: frozenset(
            {
                LegalValidityStatus.CURRENT,
                LegalValidityStatus.EXPIRED,
                LegalValidityStatus.SUPERSEDED,
                LegalValidityStatus.REPEALED,
            }
        ),
        LegalValidityStatus.CURRENT: frozenset(
            {
                LegalValidityStatus.SUPERSEDED,
                LegalValidityStatus.REPEALED,
                LegalValidityStatus.EXPIRED,
            }
        ),
        LegalValidityStatus.SUPERSEDED: frozenset(),
        LegalValidityStatus.REPEALED: frozenset(),
        LegalValidityStatus.EXPIRED: frozenset(),
    }
    INDEX_TRANSITIONS: ClassVar[dict[IndexStatus, frozenset[IndexStatus]]] = {
        IndexStatus.NOT_REQUESTED: frozenset(
            {IndexStatus.PENDING, IndexStatus.EXCLUDED}
        ),
        IndexStatus.PENDING: frozenset(
            {IndexStatus.INDEXING, IndexStatus.FAILED, IndexStatus.EXCLUDED}
        ),
        IndexStatus.INDEXING: frozenset(
            {IndexStatus.INDEXED, IndexStatus.FAILED}
        ),
        IndexStatus.INDEXED: frozenset(
            {IndexStatus.PENDING, IndexStatus.EXCLUDED}
        ),
        IndexStatus.FAILED: frozenset(
            {IndexStatus.PENDING, IndexStatus.EXCLUDED}
        ),
        IndexStatus.EXCLUDED: frozenset({IndexStatus.PENDING}),
    }
    _REVIEW_REQUIRED_LAYERS: ClassVar[frozenset[KnowledgeLayer]] = frozenset(
        {
            KnowledgeLayer.MANAGED_CORPUS,
            KnowledgeLayer.WEB_VERIFIED,
            KnowledgeLayer.GLOBAL_CANDIDATE,
        }
    )
    _ORDINARY_LAYERS: ClassVar[frozenset[KnowledgeLayer]] = frozenset(
        {KnowledgeLayer.PRIVATE_LIBRARY, KnowledgeLayer.TEMPORARY}
    )
    _INDEXING_REQUIRED_STATES: ClassVar[frozenset[IndexStatus]] = frozenset(
        {
            IndexStatus.NOT_REQUESTED,
            IndexStatus.PENDING,
            IndexStatus.INDEXING,
            IndexStatus.FAILED,
        }
    )

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    def evaluate_rag_eligibility(
        self,
        document: GovernedDocument,
        *,
        now: datetime | None = None,
    ) -> DocumentEligibility:
        """Aplica todas las reglas sobre campos ya cargados, sin consultas adicionales."""

        effective_now = self._aware_utc(now or datetime.now(timezone.utc))
        reasons: list[RagEligibilityReason] = []

        if document.is_deleted:
            reasons.append(RagEligibilityReason.DOCUMENT_DELETED)
        if (
            document.status is DocumentStatus.ARCHIVED
            or document.review_status is ReviewStatus.ARCHIVED
            or document.archived_at is not None
        ):
            reasons.append(RagEligibilityReason.DOCUMENT_ARCHIVED)
        if document.status is not DocumentStatus.EXTRACTED:
            reasons.append(RagEligibilityReason.EXTRACTION_INCOMPLETE)

        if document.review_status is ReviewStatus.REJECTED:
            reasons.append(RagEligibilityReason.REVIEW_REJECTED)
        elif document.review_status is ReviewStatus.PENDING:
            reasons.append(RagEligibilityReason.REVIEW_PENDING)
        elif (
            document.knowledge_layer in self._REVIEW_REQUIRED_LAYERS
            and document.review_status is not ReviewStatus.APPROVED
        ):
            reasons.append(RagEligibilityReason.REVIEW_PENDING)

        expired, expiration_reason = self._expiration_state(
            document,
            now=effective_now,
        )
        if expiration_reason is not None:
            reasons.append(expiration_reason)

        if document.knowledge_layer is KnowledgeLayer.GLOBAL_CANDIDATE:
            reasons.append(RagEligibilityReason.LAYER_NOT_RAG_ELIGIBLE)

        if not self._validity_allowed(document):
            reasons.append(RagEligibilityReason.LEGAL_VALIDITY_NOT_ALLOWED)

        if document.index_status is not IndexStatus.INDEXED:
            reasons.append(RagEligibilityReason.INDEX_NOT_READY)

        ordered_reasons = tuple(dict.fromkeys(reasons))
        requires_review = (
            document.review_status is ReviewStatus.PENDING
            or (
                document.knowledge_layer in self._REVIEW_REQUIRED_LAYERS
                and document.review_status is not ReviewStatus.APPROVED
            )
        )
        return DocumentEligibility(
            eligible=not ordered_reasons,
            reason_codes=ordered_reasons,
            expired=expired,
            requires_review=requires_review,
            requires_indexing=document.index_status
            in self._INDEXING_REQUIRED_STATES,
        )

    def evaluate_indexing_eligibility(
        self,
        document: GovernedDocument,
        *,
        now: datetime | None = None,
    ) -> DocumentEligibility:
        """Evalúa la fuente ignorando solo que aún no esté indexada."""

        result = self.evaluate_rag_eligibility(document, now=now)
        reasons = tuple(
            reason
            for reason in result.reason_codes
            if reason is not RagEligibilityReason.INDEX_NOT_READY
            or document.index_status is IndexStatus.EXCLUDED
        )
        return DocumentEligibility(
            eligible=not reasons,
            reason_codes=reasons,
            expired=result.expired,
            requires_review=result.requires_review,
            requires_indexing=result.requires_indexing,
        )

    def evaluate_expiration(
        self,
        document: Document,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Devuelve expiración y rechaza configuraciones incoherentes."""

        expired, reason = self._expiration_state(
            document,
            now=self._aware_utc(now or datetime.now(timezone.utc)),
        )
        if reason is RagEligibilityReason.TEMPORARY_EXPIRATION_MISSING:
            raise DocumentGovernanceError("DOCUMENT_TEMPORARY_EXPIRATION_REQUIRED")
        if reason is RagEligibilityReason.EXPIRATION_NOT_ALLOWED:
            raise DocumentGovernanceError("DOCUMENT_EXPIRATION_NOT_ALLOWED")
        return expired

    def validate_public_upload(self, governance: DocumentUploadGovernance) -> None:
        """Limita la carga ordinaria a capas y procedencia locales."""

        if governance.knowledge_layer not in self._ORDINARY_LAYERS:
            raise DocumentGovernanceError("DOCUMENT_LAYER_RESERVED")
        if governance.source_kind is not SourceKind.LOCAL_UPLOAD:
            raise DocumentGovernanceError("DOCUMENT_SOURCE_KIND_RESERVED")
        self._validate_expiration_values(
            governance.knowledge_layer,
            governance.expires_at,
        )

    def validate_layer_transition(
        self,
        document: Document,
        target: KnowledgeLayer,
    ) -> None:
        """Valida únicamente transiciones ordinarias; no promueve capas reservadas."""

        if target is document.knowledge_layer:
            return
        if (
            target not in self._ORDINARY_LAYERS
            or document.knowledge_layer not in self._ORDINARY_LAYERS
        ):
            raise DocumentGovernanceError("DOCUMENT_LAYER_TRANSITION_RESERVED")
        self._validate_expiration_values(target, document.expires_at)

    async def transition_review_status(
        self,
        document: Document,
        target: ReviewStatus,
    ) -> None:
        allowed = self.REVIEW_TRANSITIONS[document.review_status]
        if target not in allowed:
            self._reject_transition("DOCUMENT_REVIEW_TRANSITION_INVALID")
        previous = document.review_status
        archived_at = utc_now() if target is ReviewStatus.ARCHIVED else document.archived_at
        await self._apply(
            document,
            review_status=target,
            archived_at=archived_at,
        )
        self._log_transition("review", previous.value, target.value)

    async def transition_legal_validity(
        self,
        document: Document,
        target: LegalValidityStatus,
        *,
        replacement: Document | None = None,
    ) -> None:
        allowed = self.LEGAL_VALIDITY_TRANSITIONS[document.legal_validity_status]
        if target not in allowed:
            self._reject_transition("DOCUMENT_LEGAL_VALIDITY_TRANSITION_INVALID")
        if target is LegalValidityStatus.SUPERSEDED and replacement is not None:
            self._validate_replacement(document, replacement)
        previous = document.legal_validity_status
        await self._apply(document, legal_validity_status=target)
        self._log_transition("legal_validity", previous.value, target.value)

    async def transition_index_status(
        self,
        document: Document,
        target: IndexStatus,
    ) -> None:
        """Aplica transiciones ordinarias; `indexed` exige confirmación separada."""

        if target is IndexStatus.INDEXED:
            self._reject_transition("DOCUMENT_INDEX_CONFIRMATION_REQUIRED")
        if target not in self.INDEX_TRANSITIONS[document.index_status]:
            self._reject_transition("DOCUMENT_INDEX_TRANSITION_INVALID")
        if document.index_status is IndexStatus.EXCLUDED and target is IndexStatus.PENDING:
            eligibility = self.evaluate_rag_eligibility(document)
            blocking = tuple(
                reason
                for reason in eligibility.reason_codes
                if reason is not RagEligibilityReason.INDEX_NOT_READY
            )
            if blocking:
                self._reject_transition("DOCUMENT_INDEX_TRANSITION_INVALID")
        previous = document.index_status
        await self._apply(document, index_status=target)
        self._log_transition("index", previous.value, target.value)

    async def confirm_indexed(self, document: Document) -> None:
        """Punto explícito reservado para confirmación futura del indexador real."""

        if document.index_status is not IndexStatus.INDEXING:
            self._reject_transition("DOCUMENT_INDEX_TRANSITION_INVALID")
        previous = document.index_status
        await self._apply(document, index_status=IndexStatus.INDEXED)
        self._log_transition("index_confirmation", previous.value, IndexStatus.INDEXED.value)

    async def link_superseded_version(
        self,
        document: Document,
        previous_document: Document,
    ) -> None:
        """Enlaza versiones sin cambiar automáticamente la vigencia de ninguna."""

        if document.id == previous_document.id:
            self._reject_transition("DOCUMENT_VERSION_SELF_REFERENCE")
        await self._ensure_no_version_cycle(document, previous_document)
        await self._apply(
            document,
            supersedes_document_id=previous_document.id,
        )
        self._log_transition("version_link", "unlinked", "linked")

    async def promote_to_managed_corpus(self, document: Document) -> None:
        """Promueve explícitamente una fuente local e invalida su índice derivado."""

        if (
            document.is_deleted
            or document.knowledge_layer not in self._ORDINARY_LAYERS
            or document.status is DocumentStatus.ARCHIVED
            or document.review_status is ReviewStatus.ARCHIVED
        ):
            self._reject_transition("DOCUMENT_MANAGED_PROMOTION_INVALID")
        await self._apply(
            document,
            knowledge_layer=KnowledgeLayer.MANAGED_CORPUS,
            source_kind=SourceKind.MANAGED_IMPORT,
            review_status=ReviewStatus.PENDING,
            legal_validity_status=LegalValidityStatus.UNKNOWN,
            index_status=IndexStatus.EXCLUDED,
            expires_at=None,
            archived_at=None,
        )
        self._log_transition("managed_promotion", "ordinary", "pending_review")

    def to_public_read(
        self,
        document: Document,
        *,
        now: datetime | None = None,
    ) -> DocumentRead:
        """Construye el contrato público con elegibilidad calculada en memoria."""

        eligibility = self.evaluate_rag_eligibility(document, now=now)
        return DocumentRead(
            id=document.id,
            display_name=document.display_name,
            original_filename=document.original_filename,
            document_type=document.document_type,
            mime_type=document.mime_type,
            extension=document.extension,
            size_bytes=document.size_bytes,
            status=document.status,
            knowledge_layer=document.knowledge_layer,
            source_kind=document.source_kind,
            review_status=document.review_status,
            legal_validity_status=document.legal_validity_status,
            index_status=document.index_status,
            issuing_entity=document.issuing_entity,
            jurisdiction=document.jurisdiction,
            legal_area=document.legal_area,
            canonical_source_url=document.canonical_source_url,
            published_at=document.published_at,
            source_accessed_at=document.source_accessed_at,
            version_label=document.version_label,
            expires_at=document.expires_at,
            archived_at=document.archived_at,
            supersedes_document_id=document.supersedes_document_id,
            created_at=document.created_at,
            updated_at=document.updated_at,
            rag_eligible=eligibility.eligible,
            rag_eligibility_reasons=list(eligibility.reason_codes),
            is_expired=eligibility.expired,
        )

    @staticmethod
    def _validity_allowed(document: GovernedDocument) -> bool:
        if document.legal_validity_status in {
            LegalValidityStatus.SUPERSEDED,
            LegalValidityStatus.REPEALED,
            LegalValidityStatus.EXPIRED,
        }:
            return False
        if document.knowledge_layer in {
            KnowledgeLayer.MANAGED_CORPUS,
            KnowledgeLayer.WEB_VERIFIED,
        }:
            return document.legal_validity_status is LegalValidityStatus.CURRENT
        return document.legal_validity_status in {
            LegalValidityStatus.UNKNOWN,
            LegalValidityStatus.CURRENT,
        }

    @classmethod
    def _expiration_state(
        cls,
        document: GovernedDocument,
        *,
        now: datetime,
    ) -> tuple[bool, RagEligibilityReason | None]:
        if document.knowledge_layer is KnowledgeLayer.TEMPORARY:
            if document.expires_at is None:
                return False, RagEligibilityReason.TEMPORARY_EXPIRATION_MISSING
            try:
                expires_at = cls._aware_utc(document.expires_at)
            except DocumentGovernanceError:
                return False, RagEligibilityReason.TEMPORARY_EXPIRATION_MISSING
            expired = expires_at <= now
            return (
                expired,
                RagEligibilityReason.TEMPORARY_EXPIRED if expired else None,
            )
        if document.expires_at is not None:
            return False, RagEligibilityReason.EXPIRATION_NOT_ALLOWED
        return False, None

    @classmethod
    def _validate_expiration_values(
        cls,
        layer: KnowledgeLayer,
        expires_at: datetime | None,
    ) -> None:
        if layer is KnowledgeLayer.TEMPORARY:
            if expires_at is None:
                raise DocumentGovernanceError("DOCUMENT_TEMPORARY_EXPIRATION_REQUIRED")
            cls._aware_utc(expires_at)
        elif expires_at is not None:
            raise DocumentGovernanceError("DOCUMENT_EXPIRATION_NOT_ALLOWED")

    @staticmethod
    def _validate_replacement(document: Document, replacement: Document) -> None:
        if replacement.id == document.id:
            raise DocumentGovernanceError("DOCUMENT_VERSION_SELF_REFERENCE")
        if replacement.supersedes_document_id != document.id:
            raise DocumentGovernanceError("DOCUMENT_VERSION_LINK_INVALID")
        if document.supersedes_document_id == replacement.id:
            raise DocumentGovernanceError("DOCUMENT_VERSION_CYCLE")

    async def _ensure_no_version_cycle(
        self,
        document: Document,
        previous_document: Document,
    ) -> None:
        session = self._require_session()
        target_id = document.id
        current: Document | None = previous_document
        visited: set[object] = set()
        while current is not None:
            if current.id == target_id:
                self._reject_transition("DOCUMENT_VERSION_CYCLE")
            if current.id in visited or current.supersedes_document_id is None:
                return
            visited.add(current.id)
            current = await session.get(Document, current.supersedes_document_id)

    async def _apply(self, document: Document, **changes: object) -> None:
        session = self._require_session()
        async with session.begin_nested():
            for field, value in changes.items():
                setattr(document, field, value)
            document.updated_at = utc_now()
            await session.flush()

    def _require_session(self) -> AsyncSession:
        if self.session is None:
            raise DocumentGovernanceError("DOCUMENT_GOVERNANCE_SESSION_REQUIRED")
        return self.session

    @staticmethod
    def _aware_utc(value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise DocumentGovernanceError("DOCUMENT_GOVERNANCE_DATETIME_INVALID")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _reject_transition(code: str) -> None:
        log_warning(
            "Transición documental rechazada",
            operation="document_governance_transition",
            error_code=code,
        )
        raise DocumentGovernanceError(code)

    @staticmethod
    def _log_transition(dimension: str, previous: str, target: str) -> None:
        log_info(
            "Transición documental aplicada",
            operation="document_governance_transition",
            dimension=dimension,
            previous_status=previous,
            target_status=target,
        )
