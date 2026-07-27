"""Importación local, explícita y auditable del corpus administrado."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from app.core.Log import log_error, log_info, log_success, log_warning
from app.core.config import settings
from app.database.models.document import (
    Document,
    DocumentStatus,
    IndexStatus,
    KnowledgeLayer,
    LegalValidityStatus,
    ReviewStatus,
    utc_now,
)
from app.database.repositories.document_repository import DocumentRepository
from app.database.repositories.managed_corpus_repository import ManagedCorpusRepository
from app.schemas.document import ManagedDocumentImportMetadata
from app.schemas.managed_corpus import (
    ManagedCorpusBatchResult,
    ManagedCorpusItemStatus,
    ManagedCorpusManifest,
    ManagedCorpusManifestDocument,
    ManagedCorpusOperation,
    ManagedCorpusResult,
)
from app.services.document_governance_service import (
    DocumentGovernanceError,
    DocumentGovernanceService,
)
from app.services.document_service import (
    DocumentService,
    DocumentServiceError,
)


class ManagedCorpusError(RuntimeError):
    """Error estable que no transporta rutas, hashes ni contenido."""

    def __init__(self, code: str, *, exit_code: int = 4) -> None:
        super().__init__(code)
        self.code = code
        self.exit_code = exit_code


@dataclass(frozen=True)
class ValidatedManagedFile:
    path: Path
    sha256: str
    size_bytes: int


class ManagedCorpusService:
    """Coordina manifiesto, staging y servicios documentales oficiales."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        staging_directory: Path | None = None,
        document_service: DocumentService | None = None,
    ) -> None:
        self.session = session
        self.staging_directory = (
            staging_directory or settings.managed_corpus_staging_path
        ).resolve()
        self.documents = DocumentRepository(session)
        self.registry = ManagedCorpusRepository(session)
        self.governance = DocumentGovernanceService(session)
        self.document_service = document_service or DocumentService(session)

    @staticmethod
    def load_manifest(path: Path) -> ManagedCorpusManifest:
        """Carga JSON estricto sin conservar ni registrar el contenido crudo."""

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return ManagedCorpusManifest.model_validate(raw)
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
            raise ManagedCorpusError(
                "MANAGED_CORPUS_MANIFEST_INVALID", exit_code=2
            ) from exc

    async def validate(self, manifest: ManagedCorpusManifest) -> ManagedCorpusBatchResult:
        results: list[ManagedCorpusResult] = []
        preceding_sources: set[str] = set()
        for item in manifest.documents:
            results.append(
                await self._validate_item(
                    manifest.corpus_id,
                    item,
                    declared_previous_sources=preceding_sources,
                )
            )
            preceding_sources.add(item.source_key)
        return self._batch(manifest.corpus_id, ManagedCorpusOperation.VALIDATE, results)

    async def import_documents(
        self,
        manifest: ManagedCorpusManifest,
        *,
        continue_on_error: bool = False,
    ) -> ManagedCorpusBatchResult:
        results: list[ManagedCorpusResult] = []
        for item in manifest.documents:
            validation = await self._validate_item(manifest.corpus_id, item)
            if validation.status is ManagedCorpusItemStatus.IMPORTED_PENDING or (
                validation.status
                in {
                    ManagedCorpusItemStatus.APPROVED,
                    ManagedCorpusItemStatus.PROCESSED,
                    ManagedCorpusItemStatus.INDEXED,
                    ManagedCorpusItemStatus.REJECTED,
                }
            ):
                results.append(
                    validation.model_copy(
                        update={"operation": ManagedCorpusOperation.IMPORT}
                    )
                )
                continue
            if validation.status is not ManagedCorpusItemStatus.VALID:
                results.append(
                    validation.model_copy(
                        update={"operation": ManagedCorpusOperation.IMPORT}
                    )
                )
                if not continue_on_error:
                    break
                continue
            try:
                validated = self._validate_staging_file(item)
                upload_file = validated.path.open("rb")
                upload = UploadFile(
                    file=upload_file,
                    filename=Path(item.filename).name,
                    headers=Headers({"content-type": "application/pdf"}),
                )
                previous_document = (
                    await self.registry.get_document(
                        manifest.corpus_id, item.supersedes_source_key
                    )
                    if item.supersedes_source_key is not None
                    else None
                )
                document = await self.document_service.import_managed_pdf(
                    upload,
                    item.document_type,
                    ManagedDocumentImportMetadata(
                        display_name=item.display_name,
                        issuing_entity=item.issuing_entity,
                        jurisdiction=item.jurisdiction,
                        legal_area=item.legal_area,
                        canonical_source_url=item.canonical_source_url,
                        published_at=item.published_at,
                        version_label=item.version_label,
                        supersedes_document_id=(
                            previous_document.id
                            if previous_document is not None
                            else None
                        ),
                    ),
                    corpus_id=manifest.corpus_id,
                    source_key=item.source_key,
                )
                results.append(
                    ManagedCorpusResult(
                        source_key=item.source_key,
                        operation=ManagedCorpusOperation.IMPORT,
                        status=ManagedCorpusItemStatus.IMPORTED_PENDING,
                        safe_reason_code=None,
                        document_id=self._safe_document_id(document.id),
                        knowledge_layer=document.knowledge_layer,
                        review_status=document.review_status,
                        legal_validity_status=document.legal_validity_status,
                        index_status=document.index_status,
                    )
                )
                log_success(
                    "Fuente administrada importada en revisión",
                    operation="managed_corpus_import",
                    source_key=item.source_key,
                    result="imported_pending",
                )
            except (
                DocumentServiceError,
                ManagedCorpusError,
                OSError,
                ValidationError,
            ) as exc:
                await self.session.rollback()
                log_error(
                    "Falló la importación administrada",
                    operation="managed_corpus_import",
                    source_key=item.source_key,
                    error_code="MANAGED_CORPUS_IMPORT_ERROR",
                    exception_type=type(exc).__name__,
                )
                results.append(
                    self._error_result(
                        item.source_key,
                        ManagedCorpusOperation.IMPORT,
                        "MANAGED_CORPUS_IMPORT_ERROR",
                    )
                )
                if not continue_on_error:
                    break
        return self._batch(manifest.corpus_id, ManagedCorpusOperation.IMPORT, results)

    async def status(self, manifest: ManagedCorpusManifest) -> ManagedCorpusBatchResult:
        results: list[ManagedCorpusResult] = []
        for item in manifest.documents:
            document = await self.registry.get_document(
                manifest.corpus_id, item.source_key
            )
            if document is None:
                validation = await self._validate_item(manifest.corpus_id, item)
                if validation.status is ManagedCorpusItemStatus.VALID:
                    validation = validation.model_copy(
                        update={
                            "operation": ManagedCorpusOperation.STATUS,
                            "status": ManagedCorpusItemStatus.NOT_IMPORTED,
                        }
                    )
                else:
                    validation = validation.model_copy(
                        update={"operation": ManagedCorpusOperation.STATUS}
                    )
                results.append(validation)
            else:
                results.append(
                    self._document_result(
                        item.source_key,
                        ManagedCorpusOperation.STATUS,
                        document,
                    )
                )
        return self._batch(manifest.corpus_id, ManagedCorpusOperation.STATUS, results)

    async def review(
        self,
        manifest: ManagedCorpusManifest,
        *,
        source_key: str,
        decision: str,
        legal_validity: LegalValidityStatus | None = None,
        confirmed: bool = False,
    ) -> ManagedCorpusResult:
        item = self._manifest_item(manifest, source_key)
        document = await self._require_managed_document(manifest.corpus_id, source_key)
        try:
            if decision == "approve":
                if not confirmed:
                    raise ManagedCorpusError("MANAGED_CORPUS_APPROVAL_CONFIRMATION_REQUIRED", exit_code=2)
                if document.review_status is not ReviewStatus.PENDING:
                    raise ManagedCorpusError("MANAGED_CORPUS_REVIEW_TRANSITION_INVALID", exit_code=2)
                if (
                    not item.issuing_entity
                    or not item.jurisdiction
                    or not (item.version_label or item.canonical_source_url)
                    or legal_validity is None
                    or legal_validity is LegalValidityStatus.UNKNOWN
                ):
                    raise ManagedCorpusError("MANAGED_CORPUS_APPROVAL_METADATA_REQUIRED", exit_code=2)
                if document.legal_validity_status is not legal_validity:
                    await self.governance.transition_legal_validity(
                        document, legal_validity
                    )
                await self.governance.transition_review_status(
                    document, ReviewStatus.APPROVED
                )
            elif decision == "reject":
                await self.governance.transition_review_status(
                    document, ReviewStatus.REJECTED
                )
            elif decision == "pending":
                await self.governance.transition_review_status(
                    document, ReviewStatus.PENDING
                )
            else:
                raise ManagedCorpusError("MANAGED_CORPUS_REVIEW_DECISION_INVALID", exit_code=2)
            await self.session.commit()
        except DocumentGovernanceError as exc:
            await self.session.rollback()
            raise ManagedCorpusError("MANAGED_CORPUS_REVIEW_TRANSITION_INVALID", exit_code=2) from exc
        log_info(
            "Revisión administrada aplicada",
            operation="managed_corpus_review",
            source_key=source_key,
            result=decision,
        )
        return self._document_result(source_key, ManagedCorpusOperation.REVIEW, document)

    async def promote(
        self,
        manifest: ManagedCorpusManifest,
        *,
        source_key: str,
        document_id: UUID,
        confirmed: bool,
    ) -> ManagedCorpusResult:
        if not confirmed:
            raise ManagedCorpusError("MANAGED_CORPUS_PROMOTION_CONFIRMATION_REQUIRED", exit_code=2)
        item = self._manifest_item(manifest, source_key)
        validated = self._validate_staging_file(item)
        existing_entry = await self.registry.get_entry(manifest.corpus_id, source_key)
        if existing_entry is not None:
            raise ManagedCorpusError("MANAGED_CORPUS_SOURCE_ALREADY_REGISTERED", exit_code=3)
        document = await self.documents.get_by_id(document_id, include_deleted=True)
        if document is None:
            raise ManagedCorpusError("MANAGED_CORPUS_DOCUMENT_NOT_FOUND", exit_code=2)
        if document.sha256 != validated.sha256:
            raise ManagedCorpusError("MANAGED_CORPUS_PROMOTION_HASH_MISMATCH", exit_code=3)
        if await self.registry.get_entry_by_document(document.id) is not None:
            raise ManagedCorpusError("MANAGED_CORPUS_DOCUMENT_ALREADY_REGISTERED", exit_code=3)
        if not item.issuing_entity or not item.jurisdiction or not (
            item.version_label or item.canonical_source_url
        ):
            raise ManagedCorpusError("MANAGED_CORPUS_PROMOTION_METADATA_REQUIRED", exit_code=2)
        document.display_name = item.display_name
        document.issuing_entity = item.issuing_entity
        document.jurisdiction = item.jurisdiction
        document.legal_area = item.legal_area
        document.canonical_source_url = item.canonical_source_url
        document.published_at = item.published_at
        document.source_accessed_at = (
            utc_now() if item.canonical_source_url is not None else None
        )
        document.version_label = item.version_label
        try:
            await self.governance.promote_to_managed_corpus(document)
            await self.registry.create_entry(
                corpus_id=manifest.corpus_id,
                source_key=source_key,
                document_id=document.id,
            )
            await self.session.commit()
        except DocumentGovernanceError as exc:
            await self.session.rollback()
            raise ManagedCorpusError("MANAGED_CORPUS_PROMOTION_INVALID", exit_code=2) from exc
        log_warning(
            "Documento promovido explícitamente a corpus administrado",
            operation="managed_corpus_promote",
            source_key=source_key,
            result="pending_review",
        )
        return self._document_result(source_key, ManagedCorpusOperation.PROMOTE, document)

    async def _validate_item(
        self,
        corpus_id: str,
        item: ManagedCorpusManifestDocument,
        *,
        declared_previous_sources: set[str] | None = None,
    ) -> ManagedCorpusResult:
        started_at = time.perf_counter()
        try:
            validated = self._validate_staging_file(item)
            if item.supersedes_source_key is not None:
                previous = await self.registry.get_document(
                    corpus_id, item.supersedes_source_key
                )
                if previous is None and item.supersedes_source_key not in (
                    declared_previous_sources or set()
                ):
                    return self._error_result(
                        item.source_key,
                        ManagedCorpusOperation.VALIDATE,
                        "MANAGED_CORPUS_PREVIOUS_VERSION_NOT_FOUND",
                    )
            registered = await self.registry.get_document(corpus_id, item.source_key)
            if registered is not None:
                if registered.sha256 != validated.sha256:
                    return self._conflict_result(
                        item.source_key,
                        ManagedCorpusOperation.VALIDATE,
                        "MANAGED_CORPUS_SOURCE_VERSION_CONFLICT",
                    )
                return self._document_result(
                    item.source_key, ManagedCorpusOperation.VALIDATE, registered
                )
            duplicate = await self.documents.get_by_sha256(
                validated.sha256, include_deleted=True
            )
            if duplicate is not None:
                code = (
                    "MANAGED_CORPUS_DUPLICATE_REQUIRES_PROMOTION"
                    if duplicate.knowledge_layer
                    in {KnowledgeLayer.PRIVATE_LIBRARY, KnowledgeLayer.TEMPORARY}
                    else "MANAGED_CORPUS_DUPLICATE_CONFLICT"
                )
                return self._conflict_result(
                    item.source_key, ManagedCorpusOperation.VALIDATE, code
                )
            log_info(
                "Fuente administrada validada",
                operation="managed_corpus_validate",
                source_key=item.source_key,
                result="valid",
                size_bytes=validated.size_bytes,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            )
            return ManagedCorpusResult(
                source_key=item.source_key,
                operation=ManagedCorpusOperation.VALIDATE,
                status=ManagedCorpusItemStatus.VALID,
            )
        except ManagedCorpusError as exc:
            return self._error_result(
                item.source_key, ManagedCorpusOperation.VALIDATE, exc.code
            )

    def _validate_staging_file(
        self, item: ManagedCorpusManifestDocument
    ) -> ValidatedManagedFile:
        root = self.staging_directory.resolve()
        unresolved = root / item.filename
        try:
            relative = unresolved.relative_to(root)
        except ValueError as exc:
            raise ManagedCorpusError("MANAGED_CORPUS_STAGING_PATH_INVALID", exit_code=2) from exc
        current = root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ManagedCorpusError("MANAGED_CORPUS_STAGING_SYMLINK_REJECTED", exit_code=2)
        candidate = unresolved.resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ManagedCorpusError("MANAGED_CORPUS_STAGING_PATH_INVALID", exit_code=2) from exc
        if not candidate.exists() or not candidate.is_file():
            raise ManagedCorpusError("MANAGED_CORPUS_FILE_NOT_FOUND", exit_code=2)
        if candidate.suffix.lower() != ".pdf" or mimetypes.guess_type(candidate.name)[0] != "application/pdf":
            raise ManagedCorpusError("MANAGED_CORPUS_FILE_TYPE_INVALID", exit_code=2)
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            with candidate.open("rb") as source:
                if source.read(5) != b"%PDF-":
                    raise ManagedCorpusError("MANAGED_CORPUS_PDF_SIGNATURE_INVALID", exit_code=2)
                source.seek(0)
                while block := source.read(settings.document_upload_chunk_size_bytes):
                    size_bytes += len(block)
                    if size_bytes > settings.document_max_size_bytes:
                        raise ManagedCorpusError("MANAGED_CORPUS_FILE_TOO_LARGE", exit_code=2)
                    digest.update(block)
        except OSError as exc:
            raise ManagedCorpusError("MANAGED_CORPUS_FILE_READ_ERROR", exit_code=4) from exc
        if size_bytes == 0:
            raise ManagedCorpusError("MANAGED_CORPUS_PDF_SIGNATURE_INVALID", exit_code=2)
        sha256 = digest.hexdigest()
        if item.expected_sha256 is not None and item.expected_sha256 != sha256:
            raise ManagedCorpusError("MANAGED_CORPUS_HASH_MISMATCH", exit_code=2)
        return ValidatedManagedFile(candidate, sha256, size_bytes)

    @staticmethod
    def _manifest_item(
        manifest: ManagedCorpusManifest, source_key: str
    ) -> ManagedCorpusManifestDocument:
        for item in manifest.documents:
            if item.source_key == source_key:
                return item
        raise ManagedCorpusError("MANAGED_CORPUS_SOURCE_NOT_FOUND", exit_code=2)

    async def _require_managed_document(
        self, corpus_id: str, source_key: str
    ) -> Document:
        document = await self.registry.get_document(corpus_id, source_key)
        if document is None or document.knowledge_layer is not KnowledgeLayer.MANAGED_CORPUS:
            raise ManagedCorpusError("MANAGED_CORPUS_DOCUMENT_NOT_FOUND", exit_code=2)
        return document

    @staticmethod
    def _safe_document_id(document_id: UUID) -> str:
        return f"{str(document_id)[:8]}…"

    @classmethod
    def _document_result(
        cls,
        source_key: str,
        operation: ManagedCorpusOperation,
        document: Document,
    ) -> ManagedCorpusResult:
        if document.review_status is ReviewStatus.REJECTED:
            status = ManagedCorpusItemStatus.REJECTED
        elif document.index_status is IndexStatus.INDEXED:
            status = ManagedCorpusItemStatus.INDEXED
        elif document.status is DocumentStatus.EXTRACTED:
            status = ManagedCorpusItemStatus.PROCESSED
        elif document.review_status is ReviewStatus.APPROVED:
            status = ManagedCorpusItemStatus.APPROVED
        else:
            status = ManagedCorpusItemStatus.IMPORTED_PENDING
        return ManagedCorpusResult(
            source_key=source_key,
            operation=operation,
            status=status,
            document_id=cls._safe_document_id(document.id),
            knowledge_layer=document.knowledge_layer,
            review_status=document.review_status,
            legal_validity_status=document.legal_validity_status,
            index_status=document.index_status,
        )

    @staticmethod
    def _conflict_result(
        source_key: str,
        operation: ManagedCorpusOperation,
        code: str,
    ) -> ManagedCorpusResult:
        return ManagedCorpusResult(
            source_key=source_key,
            operation=operation,
            status=ManagedCorpusItemStatus.CONFLICT,
            safe_reason_code=code,
        )

    @staticmethod
    def _error_result(
        source_key: str,
        operation: ManagedCorpusOperation,
        code: str,
    ) -> ManagedCorpusResult:
        return ManagedCorpusResult(
            source_key=source_key,
            operation=operation,
            status=ManagedCorpusItemStatus.INVALID,
            safe_reason_code=code,
        )

    @staticmethod
    def _batch(
        corpus_id: str,
        operation: ManagedCorpusOperation,
        results: list[ManagedCorpusResult],
    ) -> ManagedCorpusBatchResult:
        conflicts = sum(
            item.status is ManagedCorpusItemStatus.CONFLICT for item in results
        )
        failed = sum(
            item.status in {ManagedCorpusItemStatus.INVALID, ManagedCorpusItemStatus.ERROR}
            for item in results
        )
        return ManagedCorpusBatchResult(
            corpus_id=corpus_id,
            operation=operation,
            results=results,
            succeeded=len(results) - conflicts - failed,
            conflicts=conflicts,
            failed=failed,
        )
