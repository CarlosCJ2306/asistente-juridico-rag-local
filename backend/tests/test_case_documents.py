"""Pruebas sintéticas de pertenencia documental, sin storage principal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.cases.document_domain import (
    CaseDocument,
    CaseDocumentAvailability,
    CaseDocumentDomainError,
    CaseDocumentPurpose,
    CaseDocumentSnapshot,
)
from app.cases.document_service import CaseDocumentService
from app.cases.errors import CaseError
from app.cases.domain import CaseStatus
from app.cases.service import CaseService
from app.database.base import Base
from app.database.models.case import CaseAuditEventRecord, CaseRecord
from app.database.models.case_document import CaseDocumentRecord
from app.database.models.document import (
    Document,
    DocumentStatus,
    DocumentType,
    IndexStatus,
    KnowledgeLayer,
    LegalValidityStatus,
    ReviewStatus,
    SourceKind,
)
from app.database.session import get_db_session
from app.main import app
from app.schemas.case import CaseActionRequest, CaseCreate
from app.schemas.case_document import (
    CaseDocumentAttach,
    CaseDocumentRemove,
    CaseDocumentUpdate,
)
from app.services.conversation_principal import ConversationPrincipal


NOW = datetime(2026, 7, 29, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def membership_database(tmp_path: Path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{(tmp_path / 'case-documents.db').as_posix()}"
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: Base.metadata.create_all(
                sync,
                tables=[
                    Document.__table__,
                    CaseRecord.__table__,
                    CaseAuditEventRecord.__table__,
                    CaseDocumentRecord.__table__,
                ],
            )
        )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield engine, factory
    await engine.dispose()


def _document(
    *,
    layer: KnowledgeLayer = KnowledgeLayer.PRIVATE_LIBRARY,
    status: DocumentStatus = DocumentStatus.EXTRACTED,
    index_status: IndexStatus = IndexStatus.INDEXED,
    expires_at: datetime | None = None,
    deleted: bool = False,
) -> Document:
    identifier = uuid4()
    return Document(
        id=identifier,
        original_filename="synthetic.pdf",
        display_name="Documento sintético",
        stored_filename=f"{identifier.hex}.pdf",
        relative_path=f"storage/documents/otros/{identifier.hex}.pdf",
        document_type=DocumentType.EXPEDIENTE,
        mime_type="application/pdf",
        extension=".pdf",
        size_bytes=64,
        sha256=uuid4().hex + uuid4().hex,
        status=status,
        knowledge_layer=layer,
        source_kind=SourceKind.LOCAL_UPLOAD,
        review_status=ReviewStatus.NOT_REQUIRED,
        legal_validity_status=LegalValidityStatus.UNKNOWN,
        index_status=index_status,
        expires_at=expires_at,
        created_at=NOW,
        updated_at=NOW,
        is_deleted=deleted,
        deleted_at=NOW if deleted else None,
    )


async def _create_case(session: AsyncSession, principal: ConversationPrincipal):
    return await CaseService(session).create_case(
        CaseCreate(title="Caso sintético", retention_mode="local_persistent"),
        principal,
    )


def test_case_document_domain_validates_order_versions_and_removal() -> None:
    snapshot = CaseDocumentSnapshot(
        display_name="Documento",
        document_type="expediente",
        knowledge_layer="private_library",
        source_kind="local_upload",
        review_status="not_required",
        legal_validity_status="unknown",
        extraction_status="extracted",
        index_status="indexed",
        expires_at=None,
        document_updated_at=NOW,
        document_version_label=None,
    )
    link = CaseDocument.create(
        case_id=uuid4(),
        document_id=uuid4(),
        purpose=CaseDocumentPurpose.PRIMARY_RECORD,
        display_order=0,
        snapshot=snapshot,
        now=NOW,
    )
    updated = link.update_link(
        purpose=CaseDocumentPurpose.EVIDENCE,
        display_order=4,
        now=NOW + timedelta(seconds=1),
    )
    removed = updated.remove(now=NOW + timedelta(seconds=2))
    assert (updated.version, updated.display_order) == (2, 4)
    assert removed.version == 3 and removed.removed_at is not None
    assert removed.snapshot == snapshot
    with pytest.raises(CaseDocumentDomainError, match="CASE_DOCUMENT_INVALID_ORDER"):
        CaseDocument.create(
            case_id=uuid4(),
            document_id=uuid4(),
            purpose=CaseDocumentPurpose.OTHER,
            display_order=-1,
            snapshot=snapshot,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_service_mutations_are_versioned_audited_and_do_not_delete_document(
    membership_database,
) -> None:
    _, factory = membership_database
    principal = ConversationPrincipal.guest("a" * 64)
    async with factory() as session:
        document = _document(
            status=DocumentStatus.PENDING_EXTRACTION,
            index_status=IndexStatus.NOT_REQUESTED,
        )
        session.add(document)
        await session.commit()
        case = await _create_case(session, principal)
        service = CaseDocumentService(session)
        attached = await service.attach_document(
            case.public_id,
            CaseDocumentAttach(
                document_id=document.id,
                purpose="primary_record",
                expected_case_version=case.version,
            ),
            principal,
        )
        assert attached.availability is CaseDocumentAvailability.PENDING_PROCESSING
        assert (attached.case_version, attached.version) == (2, 1)
        with pytest.raises(CaseError, match="CASE_DOCUMENT_DUPLICATE"):
            await service.attach_document(
                case.public_id,
                CaseDocumentAttach(
                    document_id=document.id,
                    purpose="annex",
                    expected_case_version=attached.case_version,
                ),
                principal,
            )
        updated = await service.update_document(
            case.public_id,
            attached.association_id,
            CaseDocumentUpdate(
                purpose="evidence",
                display_order=3,
                expected_case_version=attached.case_version,
                expected_document_link_version=attached.version,
            ),
            principal,
        )
        assert (updated.case_version, updated.version, updated.display_order) == (3, 2, 3)
        with pytest.raises(CaseError, match="CASE_DOCUMENT_VERSION_CONFLICT"):
            await service.update_document(
                case.public_id,
                attached.association_id,
                CaseDocumentUpdate(
                    purpose="other",
                    expected_case_version=updated.case_version,
                    expected_document_link_version=1,
                ),
                principal,
            )
        await service.remove_document(
            case.public_id,
            attached.association_id,
            CaseDocumentRemove(
                expected_case_version=updated.case_version,
                expected_document_link_version=updated.version,
            ),
            principal,
        )
        listing = await service.list_documents(
            case.public_id, principal, page=1, page_size=20
        )
        assert listing.total == 0 and listing.case_version == 4
        replacement = await service.attach_document(
            case.public_id,
            CaseDocumentAttach(
                document_id=document.id,
                purpose="annex",
                expected_case_version=listing.case_version,
            ),
            principal,
        )
        assert replacement.association_id != attached.association_id
        assert await session.get(Document, document.id) is not None
        events = list(
            (
                await session.scalars(
                    select(CaseAuditEventRecord.event_type).order_by(
                        CaseAuditEventRecord.created_at, CaseAuditEventRecord.id
                    )
                )
            ).all()
        )
        assert {
            "document_attached",
            "document_link_updated",
            "document_removed",
        } <= set(events)


@pytest.mark.asyncio
async def test_allowed_layers_rejections_and_governance_remain_unchanged(
    membership_database,
) -> None:
    _, factory = membership_database
    principal = ConversationPrincipal.guest("a" * 64)
    async with factory() as session:
        managed = _document(layer=KnowledgeLayer.MANAGED_CORPUS)
        candidate = _document(layer=KnowledgeLayer.GLOBAL_CANDIDATE)
        expired = _document(
            layer=KnowledgeLayer.TEMPORARY, expires_at=NOW - timedelta(seconds=1)
        )
        deleted = _document(deleted=True)
        private_pending = _document(
            status=DocumentStatus.REGISTERED,
            index_status=IndexStatus.NOT_REQUESTED,
        )
        temporary = _document(
            layer=KnowledgeLayer.TEMPORARY, expires_at=NOW + timedelta(days=1)
        )
        session.add_all([managed, candidate, expired, deleted, private_pending, temporary])
        await session.commit()
        before = {
            document.id: (
                document.knowledge_layer,
                document.review_status,
                document.legal_validity_status,
                document.index_status,
                document.expires_at,
            )
            for document in [managed, candidate, expired, deleted, private_pending, temporary]
        }
        case = await _create_case(session, principal)
        service = CaseDocumentService(session)
        for document in (managed, candidate):
            with pytest.raises(CaseError, match="CASE_DOCUMENT_LAYER_NOT_ALLOWED"):
                await service.attach_document(
                    case.public_id,
                    CaseDocumentAttach(
                        document_id=document.id,
                        purpose="other",
                        expected_case_version=case.version,
                    ),
                    principal,
                )
        with pytest.raises(CaseError, match="CASE_DOCUMENT_EXPIRED"):
            await service.attach_document(
                case.public_id,
                CaseDocumentAttach(
                    document_id=expired.id,
                    purpose="other",
                    expected_case_version=case.version,
                ),
                principal,
            )
        with pytest.raises(CaseError, match="CASE_DOCUMENT_UNAVAILABLE"):
            await service.attach_document(
                case.public_id,
                CaseDocumentAttach(
                    document_id=deleted.id,
                    purpose="other",
                    expected_case_version=case.version,
                ),
                principal,
            )
        first = await service.attach_document(
            case.public_id,
            CaseDocumentAttach(
                document_id=private_pending.id,
                purpose="primary_record",
                expected_case_version=case.version,
            ),
            principal,
        )
        second = await service.attach_document(
            case.public_id,
            CaseDocumentAttach(
                document_id=temporary.id,
                purpose="annex",
                expected_case_version=first.case_version,
            ),
            principal,
        )
        assert first.availability is CaseDocumentAvailability.PENDING_PROCESSING
        assert second.knowledge_layer is KnowledgeLayer.TEMPORARY
        for document_id, expected in before.items():
            current = await session.get(Document, document_id)
            assert current is not None
            assert (
                current.knowledge_layer,
                current.review_status,
                current.legal_validity_status,
                current.index_status,
                current.expires_at,
            ) == expected


@pytest.mark.asyncio
async def test_snapshot_stale_expired_and_unavailable_are_calculated_without_repair(
    membership_database,
) -> None:
    _, factory = membership_database
    principal = ConversationPrincipal.guest("a" * 64)
    async with factory() as session:
        stale_document = _document()
        expiring_document = _document(
            layer=KnowledgeLayer.TEMPORARY, expires_at=NOW + timedelta(days=1)
        )
        session.add_all([stale_document, expiring_document])
        await session.commit()
        case = await _create_case(session, principal)
        service = CaseDocumentService(session)
        stale_link = await service.attach_document(
            case.public_id,
            CaseDocumentAttach(
                document_id=stale_document.id,
                purpose="evidence",
                expected_case_version=case.version,
            ),
            principal,
        )
        expiring_link = await service.attach_document(
            case.public_id,
            CaseDocumentAttach(
                document_id=expiring_document.id,
                purpose="annex",
                expected_case_version=stale_link.case_version,
            ),
            principal,
        )
        stored_snapshot = await session.scalar(
            select(CaseDocumentRecord.snapshot_document_updated_at).where(
                CaseDocumentRecord.public_id == stale_link.association_id
            )
        )
        stale_document.review_status = ReviewStatus.APPROVED
        stale_document.updated_at = NOW + timedelta(minutes=1)
        expiring_document.expires_at = NOW - timedelta(minutes=1)
        expiring_document.updated_at = NOW + timedelta(minutes=1)
        await session.commit()
        listing = await service.list_documents(
            case.public_id, principal, page=1, page_size=20
        )
        by_document = {item.document_id: item for item in listing.items}
        assert by_document[stale_document.id].availability is CaseDocumentAvailability.STALE
        assert by_document[expiring_document.id].availability is CaseDocumentAvailability.EXPIRED
        assert await session.scalar(
            select(CaseDocumentRecord.snapshot_document_updated_at).where(
                CaseDocumentRecord.public_id == stale_link.association_id
            )
        ) == stored_snapshot
        stale_document.is_deleted = True
        stale_document.deleted_at = NOW
        stale_document.status = DocumentStatus.ARCHIVED
        await session.commit()
        detail = await service.get_document(
            case.public_id, stale_link.association_id, principal
        )
        assert detail.availability is CaseDocumentAvailability.UNAVAILABLE
        assert expiring_link.version == 1


@pytest.mark.asyncio
async def test_archived_case_is_read_only_and_idor_is_hidden(membership_database) -> None:
    _, factory = membership_database
    owner = ConversationPrincipal.guest("a" * 64)
    stranger = ConversationPrincipal.guest("b" * 64)
    async with factory() as session:
        document = _document()
        session.add(document)
        await session.commit()
        temporary_case = await CaseService(session).create_case(
            CaseCreate(title="Temporal", retention_mode="temporary"), owner
        )
        service = CaseDocumentService(session)
        attached = await service.attach_document(
            temporary_case.public_id,
            CaseDocumentAttach(
                document_id=document.id,
                purpose="primary_record",
                expected_case_version=temporary_case.version,
            ),
            owner,
        )
        with pytest.raises(CaseError, match="CASE_NOT_FOUND"):
            await service.list_documents(
                temporary_case.public_id, stranger, page=1, page_size=20
            )
        archived = await CaseService(session).transition_case(
            temporary_case.public_id,
            CaseActionRequest(expected_version=attached.case_version),
            owner,
            target=CaseStatus.ARCHIVED,
        )
        listing = await service.list_documents(
            temporary_case.public_id, owner, page=1, page_size=20
        )
        assert listing.items[0].read_only is True
        with pytest.raises(CaseError, match="CASE_ARCHIVED_READ_ONLY"):
            await service.update_document(
                temporary_case.public_id,
                attached.association_id,
                CaseDocumentUpdate(
                    purpose="annex",
                    expected_case_version=archived.version,
                    expected_document_link_version=attached.version,
                ),
                owner,
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("association_count", [1, 10, 50])
async def test_listing_uses_one_document_batch_and_bounded_queries(
    membership_database, association_count: int
) -> None:
    engine, factory = membership_database
    principal = ConversationPrincipal.guest("a" * 64)
    async with factory() as session:
        documents = [_document() for _ in range(association_count)]
        session.add_all(documents)
        await session.commit()
        case = await _create_case(session, principal)
        version = case.version
        service = CaseDocumentService(session)
        for order, document in enumerate(documents):
            attached = await service.attach_document(
                case.public_id,
                CaseDocumentAttach(
                    document_id=document.id,
                    purpose="annex",
                    display_order=order,
                    expected_case_version=version,
                ),
                principal,
            )
            version = attached.case_version

        selects = 0

        def count_selects(conn, cursor, statement, parameters, context, executemany):
            del conn, cursor, parameters, context, executemany
            nonlocal selects
            if statement.lstrip().upper().startswith("SELECT"):
                selects += 1

        event.listen(engine.sync_engine, "before_cursor_execute", count_selects)
        try:
            listing = await service.list_documents(
                case.public_id, principal, page=1, page_size=100
            )
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", count_selects)
        assert len(listing.items) == association_count
        assert [item.display_order for item in listing.items] == list(
            range(association_count)
        )
        assert selects == 4


@pytest.mark.asyncio
async def test_expired_temporary_case_blocks_access_without_renewal(
    membership_database,
) -> None:
    _, factory = membership_database
    principal = ConversationPrincipal.guest("a" * 64)
    async with factory() as session:
        case = await CaseService(session).create_case(
            CaseCreate(title="Temporal", retention_mode="temporary"), principal
        )
        record = await session.scalar(
            select(CaseRecord).where(CaseRecord.public_id == case.public_id)
        )
        assert record is not None
        expired_at = NOW - timedelta(days=1)
        record.expires_at = expired_at
        await session.commit()
        with pytest.raises(CaseError, match="CASE_EXPIRED"):
            await CaseDocumentService(session).list_documents(
                case.public_id, principal, page=1, page_size=20
            )
        await session.refresh(record)
        assert record.expires_at == expired_at


@pytest.mark.asyncio
async def test_case_document_api_contract_versions_privacy_and_isolation(
    membership_database,
) -> None:
    _, factory = membership_database
    async with factory() as session:
        private = _document()
        managed = _document(layer=KnowledgeLayer.MANAGED_CORPUS)
        session.add_all([private, managed])
        await session.commit()

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as owner, httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as stranger:
            case_response = await owner.post(
                "/api/cases",
                json={"title": "Caso API", "retention_mode": "temporary"},
            )
            case = case_response.json()
            attached_response = await owner.post(
                f"/api/cases/{case['public_id']}/documents",
                json={
                    "document_id": str(private.id),
                    "purpose": "primary_record",
                    "display_order": 0,
                    "expected_case_version": case["version"],
                },
            )
            assert attached_response.status_code == 201
            attached = attached_response.json()
            forbidden = {
                "id",
                "case_id",
                "snapshot",
                "relative_path",
                "stored_filename",
                "sha256",
                "removed_at",
                "owner_key_hash",
            }
            assert forbidden.isdisjoint(attached)
            duplicate = await owner.post(
                f"/api/cases/{case['public_id']}/documents",
                json={
                    "document_id": str(private.id),
                    "purpose": "annex",
                    "expected_case_version": attached["case_version"],
                },
            )
            assert duplicate.status_code == 409
            assert duplicate.json()["detail"] == "CASE_DOCUMENT_DUPLICATE"
            assert (
                await stranger.get(f"/api/cases/{case['public_id']}/documents")
            ).status_code == 404
            rejected = await owner.post(
                f"/api/cases/{case['public_id']}/documents",
                json={
                    "document_id": str(managed.id),
                    "purpose": "other",
                    "expected_case_version": attached["case_version"],
                },
            )
            assert rejected.status_code == 422
            updated_response = await owner.patch(
                f"/api/cases/{case['public_id']}/documents/{attached['association_id']}",
                json={
                    "purpose": "evidence",
                    "display_order": 2,
                    "expected_case_version": attached["case_version"],
                    "expected_document_link_version": attached["version"],
                },
            )
            assert updated_response.status_code == 200
            updated = updated_response.json()
            detail = await owner.get(
                f"/api/cases/{case['public_id']}/documents/{attached['association_id']}"
            )
            assert detail.status_code == 200 and detail.json()["purpose"] == "evidence"
            removed = await owner.request(
                "DELETE",
                f"/api/cases/{case['public_id']}/documents/{attached['association_id']}",
                json={
                    "expected_case_version": updated["case_version"],
                    "expected_document_link_version": updated["version"],
                },
            )
            assert removed.status_code == 204
            assert detail.json()["document_id"] == str(private.id)
            assert (
                await owner.get(
                    f"/api/cases/{case['public_id']}/documents/{attached['association_id']}"
                )
            ).status_code == 404
    finally:
        app.dependency_overrides.clear()
