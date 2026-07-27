"""Políticas documentales aisladas, sin SQLite ni índices reales."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import Base
from app.database.models.document import (
    Document,
    DocumentStatus,
    DocumentType,
    IndexStatus,
    KnowledgeLayer,
    LegalValidityStatus,
    RagEligibilityReason,
    ReviewStatus,
    SourceKind,
)
from app.database.repositories.document_repository import DocumentRepository
from app.database.session import DatabaseSessionManager
from app.schemas.document import DocumentCreate, DocumentListFilters, DocumentUploadGovernance
from app.services.document_governance_service import (
    DocumentGovernanceError,
    DocumentGovernanceService,
)


NOW = datetime(2026, 7, 27, 12, tzinfo=timezone.utc)


def _document(**overrides: object) -> Document:
    identifier = uuid4()
    values: dict[str, object] = {
        "id": identifier,
        "original_filename": "synthetic.pdf",
        "display_name": "Documento sintético",
        "stored_filename": f"{identifier}.pdf",
        "relative_path": f"storage/documents/otros/{identifier}.pdf",
        "document_type": DocumentType.OTRO,
        "mime_type": "application/pdf",
        "extension": ".pdf",
        "size_bytes": 10,
        "sha256": identifier.hex * 2,
        "status": DocumentStatus.EXTRACTED,
        "knowledge_layer": KnowledgeLayer.PRIVATE_LIBRARY,
        "source_kind": SourceKind.LOCAL_UPLOAD,
        "review_status": ReviewStatus.NOT_REQUIRED,
        "legal_validity_status": LegalValidityStatus.UNKNOWN,
        "index_status": IndexStatus.INDEXED,
        "created_at": NOW - timedelta(days=2),
        "updated_at": NOW - timedelta(days=1),
        "is_deleted": False,
    }
    values.update(overrides)
    return Document(**values)


@pytest_asyncio.fixture
async def governance_session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    manager = DatabaseSessionManager(tmp_path / "governance.db")
    async with manager.get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with manager.get_session_factory()() as session:
        yield session
    await manager.dispose()


@pytest.mark.parametrize(
    ("overrides", "eligible", "expected_reasons"),
    [
        ({}, True, set()),
        (
            {
                "knowledge_layer": KnowledgeLayer.MANAGED_CORPUS,
                "review_status": ReviewStatus.PENDING,
                "legal_validity_status": LegalValidityStatus.CURRENT,
            },
            False,
            {RagEligibilityReason.REVIEW_PENDING},
        ),
        (
            {
                "knowledge_layer": KnowledgeLayer.MANAGED_CORPUS,
                "review_status": ReviewStatus.APPROVED,
                "legal_validity_status": LegalValidityStatus.CURRENT,
            },
            True,
            set(),
        ),
        (
            {
                "knowledge_layer": KnowledgeLayer.WEB_VERIFIED,
                "review_status": ReviewStatus.NOT_REQUIRED,
                "legal_validity_status": LegalValidityStatus.CURRENT,
            },
            False,
            {RagEligibilityReason.REVIEW_PENDING},
        ),
        (
            {
                "knowledge_layer": KnowledgeLayer.GLOBAL_CANDIDATE,
                "review_status": ReviewStatus.APPROVED,
            },
            False,
            {RagEligibilityReason.LAYER_NOT_RAG_ELIGIBLE},
        ),
        (
            {"is_deleted": True},
            False,
            {RagEligibilityReason.DOCUMENT_DELETED},
        ),
        (
            {"status": DocumentStatus.ARCHIVED},
            False,
            {
                RagEligibilityReason.DOCUMENT_ARCHIVED,
                RagEligibilityReason.EXTRACTION_INCOMPLETE,
            },
        ),
        (
            {"review_status": ReviewStatus.ARCHIVED},
            False,
            {RagEligibilityReason.DOCUMENT_ARCHIVED},
        ),
        (
            {"status": DocumentStatus.PENDING_EXTRACTION},
            False,
            {RagEligibilityReason.EXTRACTION_INCOMPLETE},
        ),
        (
            {"index_status": IndexStatus.PENDING},
            False,
            {RagEligibilityReason.INDEX_NOT_READY},
        ),
    ],
)
def test_rag_eligibility_by_layer_and_state(
    overrides: dict[str, object],
    eligible: bool,
    expected_reasons: set[RagEligibilityReason],
) -> None:
    result = DocumentGovernanceService().evaluate_rag_eligibility(
        _document(**overrides),
        now=NOW,
    )

    assert result.eligible is eligible
    assert expected_reasons <= set(result.reason_codes)


def test_private_library_accepts_unknown_or_current_validity() -> None:
    service = DocumentGovernanceService()

    for validity in (LegalValidityStatus.UNKNOWN, LegalValidityStatus.CURRENT):
        result = service.evaluate_rag_eligibility(
            _document(legal_validity_status=validity),
            now=NOW,
        )
        assert result.eligible is True


@pytest.mark.parametrize(
    "validity",
    [
        LegalValidityStatus.SUPERSEDED,
        LegalValidityStatus.REPEALED,
        LegalValidityStatus.EXPIRED,
    ],
)
def test_terminal_legal_validity_is_never_rag_eligible(
    validity: LegalValidityStatus,
) -> None:
    result = DocumentGovernanceService().evaluate_rag_eligibility(
        _document(legal_validity_status=validity),
        now=NOW,
    )

    assert result.eligible is False
    assert RagEligibilityReason.LEGAL_VALIDITY_NOT_ALLOWED in result.reason_codes


def test_temporary_expiration_is_timezone_aware_and_inclusive() -> None:
    service = DocumentGovernanceService()
    future = _document(
        knowledge_layer=KnowledgeLayer.TEMPORARY,
        expires_at=NOW + timedelta(seconds=1),
    )
    exact = _document(
        knowledge_layer=KnowledgeLayer.TEMPORARY,
        expires_at=NOW,
    )
    missing = _document(
        knowledge_layer=KnowledgeLayer.TEMPORARY,
        expires_at=None,
    )

    assert service.evaluate_rag_eligibility(future, now=NOW).eligible is True
    exact_result = service.evaluate_rag_eligibility(exact, now=NOW)
    assert exact_result.expired is True
    assert RagEligibilityReason.TEMPORARY_EXPIRED in exact_result.reason_codes
    missing_result = service.evaluate_rag_eligibility(missing, now=NOW)
    assert missing_result.expired is False
    assert (
        RagEligibilityReason.TEMPORARY_EXPIRATION_MISSING
        in missing_result.reason_codes
    )
    with pytest.raises(
        DocumentGovernanceError,
        match="DOCUMENT_TEMPORARY_EXPIRATION_REQUIRED",
    ):
        service.evaluate_expiration(missing, now=NOW)


def test_non_temporary_expiration_is_rejected_by_central_policy() -> None:
    service = DocumentGovernanceService()
    document = _document(expires_at=NOW + timedelta(days=1))

    result = service.evaluate_rag_eligibility(document, now=NOW)

    assert RagEligibilityReason.EXPIRATION_NOT_ALLOWED in result.reason_codes
    with pytest.raises(
        DocumentGovernanceError,
        match="DOCUMENT_EXPIRATION_NOT_ALLOWED",
    ):
        service.evaluate_expiration(document, now=NOW)


@pytest.mark.asyncio
async def test_review_transitions_are_explicit_and_invalid_jump_is_atomic(
    governance_session: AsyncSession,
) -> None:
    document = _document(review_status=ReviewStatus.NOT_REQUIRED)
    governance_session.add(document)
    await governance_session.flush()
    service = DocumentGovernanceService(governance_session)

    await service.transition_review_status(document, ReviewStatus.NOT_REQUIRED)
    await service.transition_review_status(document, ReviewStatus.PENDING)
    before_invalid = document.updated_at
    with pytest.raises(
        DocumentGovernanceError,
        match="DOCUMENT_REVIEW_TRANSITION_INVALID",
    ):
        await service.transition_review_status(document, ReviewStatus.NOT_REQUIRED)
    assert document.review_status is ReviewStatus.PENDING
    assert document.updated_at == before_invalid
    await service.transition_review_status(document, ReviewStatus.REJECTED)
    with pytest.raises(DocumentGovernanceError):
        await service.transition_review_status(document, ReviewStatus.APPROVED)
    await service.transition_review_status(document, ReviewStatus.PENDING)
    await service.transition_review_status(document, ReviewStatus.APPROVED)
    await service.transition_review_status(document, ReviewStatus.ARCHIVED)
    assert document.archived_at is not None
    with pytest.raises(DocumentGovernanceError):
        await service.transition_review_status(document, ReviewStatus.APPROVED)


@pytest.mark.asyncio
async def test_legal_validity_transitions_reject_reactivation(
    governance_session: AsyncSession,
) -> None:
    document = _document(legal_validity_status=LegalValidityStatus.UNKNOWN)
    governance_session.add(document)
    await governance_session.flush()
    service = DocumentGovernanceService(governance_session)

    await service.transition_legal_validity(document, LegalValidityStatus.CURRENT)
    await service.transition_legal_validity(document, LegalValidityStatus.REPEALED)
    with pytest.raises(
        DocumentGovernanceError,
        match="DOCUMENT_LEGAL_VALIDITY_TRANSITION_INVALID",
    ):
        await service.transition_legal_validity(document, LegalValidityStatus.CURRENT)
    assert document.legal_validity_status is LegalValidityStatus.REPEALED


@pytest.mark.asyncio
async def test_index_transitions_require_explicit_indexer_confirmation(
    governance_session: AsyncSession,
) -> None:
    document = _document(index_status=IndexStatus.NOT_REQUESTED)
    governance_session.add(document)
    await governance_session.flush()
    service = DocumentGovernanceService(governance_session)

    await service.transition_index_status(document, IndexStatus.PENDING)
    await service.transition_index_status(document, IndexStatus.INDEXING)
    with pytest.raises(
        DocumentGovernanceError,
        match="DOCUMENT_INDEX_CONFIRMATION_REQUIRED",
    ):
        await service.transition_index_status(document, IndexStatus.INDEXED)
    assert document.index_status is IndexStatus.INDEXING
    await service.confirm_indexed(document)
    assert document.index_status is IndexStatus.INDEXED
    await service.transition_index_status(document, IndexStatus.EXCLUDED)
    await service.transition_index_status(document, IndexStatus.PENDING)


def test_ordinary_layer_and_source_rules_reject_reserved_values() -> None:
    service = DocumentGovernanceService()
    document = _document()

    for layer in (
        KnowledgeLayer.MANAGED_CORPUS,
        KnowledgeLayer.WEB_VERIFIED,
        KnowledgeLayer.GLOBAL_CANDIDATE,
    ):
        with pytest.raises(
            DocumentGovernanceError,
            match="DOCUMENT_LAYER_TRANSITION_RESERVED",
        ):
            service.validate_layer_transition(document, layer)
    with pytest.raises(
        DocumentGovernanceError,
        match="DOCUMENT_SOURCE_KIND_RESERVED",
    ):
        service.validate_public_upload(
            DocumentUploadGovernance(source_kind=SourceKind.WEB_IMPORT)
        )


@pytest.mark.asyncio
async def test_version_link_rejects_self_reference_and_cycle(
    governance_session: AsyncSession,
) -> None:
    first = _document()
    second = _document()
    governance_session.add_all([first, second])
    await governance_session.flush()
    service = DocumentGovernanceService(governance_session)

    with pytest.raises(
        DocumentGovernanceError,
        match="DOCUMENT_VERSION_SELF_REFERENCE",
    ):
        await service.link_superseded_version(first, first)

    await service.link_superseded_version(second, first)
    assert second.supersedes_document_id == first.id
    with pytest.raises(
        DocumentGovernanceError,
        match="DOCUMENT_VERSION_CYCLE",
    ):
        await service.link_superseded_version(first, second)
    await service.transition_legal_validity(
        first,
        LegalValidityStatus.SUPERSEDED,
        replacement=second,
    )
    assert first.legal_validity_status is LegalValidityStatus.SUPERSEDED


@pytest.mark.asyncio
async def test_public_projection_for_list_uses_no_additional_queries(
    governance_session: AsyncSession,
) -> None:
    repository = DocumentRepository(governance_session)
    for suffix in ("one", "two"):
        await repository.create(
            DocumentCreate(
                original_filename=f"{suffix}.pdf",
                stored_filename=f"{suffix}.pdf",
                relative_path=f"storage/documents/otros/{suffix}.pdf",
                document_type=DocumentType.OTRO,
                mime_type="application/pdf",
                extension=".pdf",
                size_bytes=10,
                sha256=("a" if suffix == "one" else "b") * 64,
                status=DocumentStatus.EXTRACTED,
                index_status=IndexStatus.INDEXED,
            )
        )
    engine = governance_session.bind
    assert engine is not None
    statements = 0

    def count_statement(*_args: object) -> None:
        nonlocal statements
        statements += 1

    event.listen(engine.sync_engine, "before_cursor_execute", count_statement)
    try:
        documents = await repository.list(DocumentListFilters())
        after_list = statements
        reads = [
            DocumentGovernanceService().to_public_read(document, now=NOW)
            for document in documents
        ]
        assert statements == after_list
        assert len(reads) == 2
        assert all(read.rag_eligible for read in reads)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", count_statement)


def test_governance_logs_never_include_document_metadata(caplog: pytest.LogCaptureFixture) -> None:
    marker = "SENSITIVE_SYNTHETIC_MARKER"
    document = _document(display_name=marker, original_filename=f"{marker}.pdf")

    with caplog.at_level(logging.INFO):
        DocumentGovernanceService().evaluate_rag_eligibility(document, now=NOW)

    assert marker not in caplog.text
