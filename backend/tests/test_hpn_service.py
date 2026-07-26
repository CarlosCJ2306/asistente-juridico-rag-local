"""Pruebas HPN sobre SQLite temporal, sin modelos ni índices reales."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.exceptions import HpnError
from app.database.base import Base
from app.database.models.document import Document, DocumentStatus, DocumentType
from app.database.models.document_chunk import DocumentChunk
from app.database.models.hpn import (
    HpnMatrix,
    HpnMatrixStatus,
    HpnNode,
    HpnNodeSource,
    HpnRelation,
)
from app.schemas.hpn import (
    HpnMatrixCreate,
    HpnMatrixUpdate,
    HpnNodeCreate,
    HpnNodeUpdate,
    HpnRelationCreate,
    HpnSourceCreate,
)
from app.services.hpn_service import HpnService
from app.database.repositories.semantic_chunk_repository import ActiveChunk


@pytest_asyncio.fixture
async def hpn_session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'hpn.db').as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _document_chunk(
    session: AsyncSession, suffix: str = "hpn"
) -> tuple[Document, DocumentChunk]:
    document = Document(
        original_filename=rf"C:\entrada\fuente-{suffix}.html.pdf",
        stored_filename=f"interno-{suffix}.pdf",
        relative_path=f"storage/documents/otros/interno-{suffix}.pdf",
        document_type=DocumentType.JURISPRUDENCIA,
        mime_type="application/pdf",
        extension=".pdf",
        size_bytes=10,
        sha256=hashlib.sha256(suffix.encode()).hexdigest(),
        status=DocumentStatus.EXTRACTED,
    )
    session.add(document)
    await session.flush()
    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=1,
        text=f"Contenido documental sintético {suffix}.",
        char_count=31,
        word_count=3,
        start_page=1,
        end_page=2,
    )
    session.add(chunk)
    await session.commit()
    return document, chunk


async def _matrix_nodes(service: HpnService):
    matrix = await service.create_matrix(HpnMatrixCreate(title="Matriz sintética"))
    fact = await service.create_node(
        matrix.id,
        HpnNodeCreate(
            node_type="fact",
            title="Hecho",
            statement="Enunciado manual",
            review_status="reviewed",
            display_order=1,
        ),
    )
    evidence = await service.create_node(
        matrix.id,
        HpnNodeCreate(
            node_type="evidence", title="Prueba", statement="Elemento manual", display_order=2
        ),
    )
    norm = await service.create_node(
        matrix.id,
        HpnNodeCreate(
            node_type="norm", title="Norma", statement="Referencia manual", display_order=3
        ),
    )
    return matrix, fact, evidence, norm


@pytest.mark.asyncio
async def test_hpn_full_review_and_edit_returns_to_in_review(hpn_session: AsyncSession) -> None:
    document, _ = await _document_chunk(hpn_session)
    service = HpnService(hpn_session)
    matrix, fact, evidence, norm = await _matrix_nodes(service)
    for node in (evidence, norm):
        source = await service.add_source(
            matrix.id, node.id, HpnSourceCreate(document_id=document.id, chunk_index=1)
        )
        assert source.source_status == "valid"
        assert "chunk_id" not in source.model_dump()
        assert "source_fingerprint" not in source.model_dump()
        await service.update_node(
            matrix.id, node.id, HpnNodeUpdate(review_status="reviewed")
        )
    for source_id, target_id, relation_type in (
        (evidence.id, fact.id, "evidence_supports_fact"),
        (norm.id, fact.id, "norm_applies_to_fact"),
    ):
        await service.create_relation(
            matrix.id,
            HpnRelationCreate(
                source_node_id=source_id,
                target_node_id=target_id,
                relation_type=relation_type,
                review_status="reviewed",
            ),
        )
    summary = await service.validation(matrix.id)
    assert summary.valid_for_review is True
    with pytest.raises(HpnError, match="HPN_CONFLICT"):
        await service.update_matrix(
            matrix.id, HpnMatrixUpdate(status=HpnMatrixStatus.REVIEWED)
        )
    assert (await service.detail(matrix.id)).matrix.status == HpnMatrixStatus.DRAFT
    reviewed = await service.update_matrix(
        matrix.id, HpnMatrixUpdate(status=HpnMatrixStatus.IN_REVIEW)
    )
    assert reviewed.status == HpnMatrixStatus.IN_REVIEW
    reviewed = await service.update_matrix(
        matrix.id, HpnMatrixUpdate(status=HpnMatrixStatus.REVIEWED)
    )
    assert reviewed.status == HpnMatrixStatus.REVIEWED
    changed = await service.update_matrix(
        matrix.id, HpnMatrixUpdate(description="Cambio administrativo")
    )
    assert changed.status == HpnMatrixStatus.IN_REVIEW
    reviewed = await service.update_matrix(
        matrix.id, HpnMatrixUpdate(status=HpnMatrixStatus.REVIEWED)
    )
    assert reviewed.status == HpnMatrixStatus.REVIEWED
    await service.update_node(matrix.id, fact.id, HpnNodeUpdate(statement="Cambio manual"))
    detail = await service.detail(matrix.id)
    assert detail.matrix.status == HpnMatrixStatus.IN_REVIEW


@pytest.mark.asyncio
async def test_hpn_sources_report_stale_and_unavailable_without_rewriting_snapshot(
    hpn_session: AsyncSession,
) -> None:
    document, chunk = await _document_chunk(hpn_session)
    service = HpnService(hpn_session)
    matrix, _, evidence, _ = await _matrix_nodes(service)
    linked = await service.add_source(
        matrix.id, evidence.id, HpnSourceCreate(document_id=document.id, chunk_index=1)
    )
    chunk.text = "Contenido cambiado"
    await hpn_session.commit()
    detail = await service.detail(matrix.id)
    assert detail.nodes[1].sources[0].source_status == "stale"
    assert detail.nodes[1].sources[0].document_name == linked.document_name
    document.is_deleted = True
    await hpn_session.commit()
    detail = await service.detail(matrix.id)
    assert detail.nodes[1].sources[0].source_status == "unavailable"


@pytest.mark.asyncio
async def test_hpn_rejects_invalid_relations_duplicates_and_incomplete_review(
    hpn_session: AsyncSession,
) -> None:
    service = HpnService(hpn_session)
    matrix, fact, evidence, norm = await _matrix_nodes(service)
    with pytest.raises(HpnError, match="HPN_RELATION_ENDPOINT_INVALID"):
        await service.create_relation(
            matrix.id,
            HpnRelationCreate(
                source_node_id=fact.id,
                target_node_id=evidence.id,
                relation_type="evidence_supports_fact",
            ),
        )
    await service.create_relation(
        matrix.id,
        HpnRelationCreate(
            source_node_id=evidence.id,
            target_node_id=fact.id,
            relation_type="evidence_supports_fact",
        ),
    )
    with pytest.raises(HpnError, match="HPN_DUPLICATE_RELATION"):
        await service.create_relation(
            matrix.id,
            HpnRelationCreate(
                source_node_id=evidence.id,
                target_node_id=fact.id,
                relation_type="evidence_supports_fact",
            ),
        )
    with pytest.raises(HpnError, match="HPN_REVIEW_INCOMPLETE"):
        await service.update_matrix(matrix.id, HpnMatrixUpdate(status="reviewed"))


@pytest.mark.asyncio
async def test_hpn_soft_delete_preserves_document_and_chunk(hpn_session: AsyncSession) -> None:
    document, chunk = await _document_chunk(hpn_session)
    service = HpnService(hpn_session)
    matrix, fact, evidence, norm = await _matrix_nodes(service)
    source = await service.add_source(
        matrix.id, evidence.id, HpnSourceCreate(document_id=document.id, chunk_index=1)
    )
    relation = await service.create_relation(
        matrix.id,
        HpnRelationCreate(
            source_node_id=evidence.id,
            target_node_id=fact.id,
            relation_type="evidence_supports_fact",
        ),
    )
    await service.delete_matrix(matrix.id)
    with pytest.raises(HpnError, match="HPN_MATRIX_DELETED"):
        await service.detail(matrix.id)
    with pytest.raises(HpnError, match="HPN_MATRIX_DELETED"):
        await service.delete_matrix(matrix.id)
    persisted_matrix = await hpn_session.get(HpnMatrix, matrix.id)
    persisted_nodes = [
        await hpn_session.get(HpnNode, node_id)
        for node_id in (fact.id, evidence.id, norm.id)
    ]
    persisted_source = await hpn_session.get(HpnNodeSource, source.source_id)
    persisted_relation = await hpn_session.get(HpnRelation, relation.id)
    assert persisted_matrix is not None and persisted_matrix.deleted_at is not None
    assert all(node is not None and node.deleted_at is not None for node in persisted_nodes)
    assert persisted_source is not None and persisted_source.deleted_at is not None
    assert persisted_relation is not None and persisted_relation.deleted_at is not None
    assert await hpn_session.get(Document, document.id) is not None
    assert await hpn_session.get(DocumentChunk, chunk.id) is not None


@pytest.mark.asyncio
async def test_hpn_logging_contains_only_operational_metadata(
    hpn_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[object] = []
    monkeypatch.setattr(
        "app.services.hpn_service.log_info",
        lambda message, **context: captured.extend((message, context)),
    )
    monkeypatch.setattr(
        "app.services.hpn_service.log_warning",
        lambda message, **context: captured.extend((message, context)),
    )
    secrets = {
        "title": "SECRET_HPN_TITLE_DO_NOT_LOG",
        "description": "SECRET_HPN_DESCRIPTION_DO_NOT_LOG",
        "statement": "SECRET_HPN_STATEMENT_DO_NOT_LOG",
        "rationale": "SECRET_HPN_RATIONALE_DO_NOT_LOG",
        "document_name": "SECRET_HPN_DOCUMENT_NAME_DO_NOT_LOG",
    }
    document, chunk = await _document_chunk(hpn_session, secrets["document_name"])
    service = HpnService(hpn_session)
    matrix = await service.create_matrix(
        HpnMatrixCreate(title=secrets["title"], description=secrets["description"])
    )
    fact = await service.create_node(
        matrix.id,
        HpnNodeCreate(
            node_type="fact", title="Fact", statement=secrets["statement"], display_order=1
        ),
    )
    evidence = await service.create_node(
        matrix.id,
        HpnNodeCreate(
            node_type="evidence", title="Evidence", statement="Manual", display_order=2
        ),
    )
    await service.add_source(
        matrix.id,
        evidence.id,
        HpnSourceCreate(document_id=document.id, chunk_index=chunk.chunk_index),
    )
    await service.create_relation(
        matrix.id,
        HpnRelationCreate(
            source_node_id=evidence.id,
            target_node_id=fact.id,
            relation_type="evidence_supports_fact",
            rationale=secrets["rationale"],
        ),
    )
    rendered = repr(captured)
    for secret in (*secrets.values(), str(matrix.id), str(fact.id), str(evidence.id)):
        assert secret not in rendered
    assert HpnService.source_fingerprint(
        ActiveChunk(
            chunk_id=chunk.id,
            document_id=document.id,
            document_type=document.document_type,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            start_page=chunk.start_page,
            end_page=chunk.end_page,
            document_name=document.original_filename,
        )
    ) not in rendered


@pytest.mark.parametrize(
    "change",
    [
        {"text": "otro"},
        {"document_type": DocumentType.NORMATIVA},
        {"start_page": 2, "end_page": 2},
        {"document_name": "otro.pdf"},
        {"chunk_index": 2},
    ],
)
def test_hpn_fingerprint_detects_each_relevant_change(change: dict[str, object]) -> None:
    chunk = ActiveChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_type=DocumentType.JURISPRUDENCIA,
        chunk_index=1,
        text="texto",
        start_page=1,
        end_page=1,
        document_name="fuente.pdf",
    )
    assert HpnService.source_fingerprint(chunk) != HpnService.source_fingerprint(
        replace(chunk, **change)
    )


def test_hpn_fingerprint_is_deterministic_unicode_and_unambiguous() -> None:
    chunk = ActiveChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_type=DocumentType.NORMATIVA,
        chunk_index=12,
        text="acción\nniñez",
        start_page=1,
        end_page=2,
        document_name="norma-á.pdf",
    )
    assert HpnService.source_fingerprint(chunk) == HpnService.source_fingerprint(chunk)
    ambiguous = replace(chunk, chunk_index=1, start_page=22)
    assert HpnService.source_fingerprint(chunk) != HpnService.source_fingerprint(ambiguous)
    assert HpnService.source_fingerprint(chunk) != HpnService.source_fingerprint(
        replace(chunk, document_id=uuid4())
    )
    assert HpnService.source_fingerprint(chunk) != HpnService.source_fingerprint(
        replace(chunk, chunk_id=uuid4())
    )


@pytest.mark.asyncio
async def test_hpn_active_uniqueness_allows_relink_after_soft_delete(
    hpn_session: AsyncSession,
) -> None:
    document, _ = await _document_chunk(hpn_session, "unique")
    document_id = document.id
    service = HpnService(hpn_session)
    matrix, fact, evidence, _ = await _matrix_nodes(service)
    matrix_id, fact_id, evidence_id = matrix.id, fact.id, evidence.id
    first = await service.add_source(
        matrix_id, evidence_id, HpnSourceCreate(document_id=document_id, chunk_index=1)
    )
    first_source_id = first.source_id
    with pytest.raises(HpnError, match="HPN_DUPLICATE_SOURCE"):
        await service.add_source(
            matrix_id, evidence_id, HpnSourceCreate(document_id=document_id, chunk_index=1)
        )
    await service.delete_source(matrix_id, evidence_id, first_source_id)
    second = await service.add_source(
        matrix_id, evidence_id, HpnSourceCreate(document_id=document_id, chunk_index=1)
    )
    assert second.source_id != first_source_id

    relation = await service.create_relation(
        matrix_id,
        HpnRelationCreate(
            source_node_id=evidence_id,
            target_node_id=fact_id,
            relation_type="evidence_supports_fact",
        ),
    )
    await service.delete_relation(matrix_id, relation.id)
    recreated = await service.create_relation(
        matrix_id,
        HpnRelationCreate(
            source_node_id=evidence_id,
            target_node_id=fact_id,
            relation_type="evidence_supports_fact",
        ),
    )
    assert recreated.id != relation.id


@pytest.mark.asyncio
async def test_hpn_mixed_source_states_are_returned_without_snapshot_repair(
    hpn_session: AsyncSession,
) -> None:
    documents = [await _document_chunk(hpn_session, suffix) for suffix in ("valid", "stale", "gone")]
    service = HpnService(hpn_session)
    matrix, _, evidence, _ = await _matrix_nodes(service)
    for document, _ in documents:
        await service.add_source(
            matrix.id, evidence.id, HpnSourceCreate(document_id=document.id, chunk_index=1)
        )
    documents[1][1].text = "cambio posterior"
    documents[2][0].is_deleted = True
    await hpn_session.commit()
    detail = await service.detail(matrix.id)
    statuses = {source.source_status for source in detail.nodes[1].sources}
    assert statuses == {"valid", "stale", "unavailable"}
    assert detail.validation_summary.valid_for_review is False
    assert detail.validation_summary.stale_source_count == 1
    assert detail.validation_summary.unavailable_source_count == 1


@pytest.mark.asyncio
async def test_hpn_archived_matrix_is_readable_but_not_editable(
    hpn_session: AsyncSession,
) -> None:
    service = HpnService(hpn_session)
    matrix = await service.create_matrix(HpnMatrixCreate(title="Archivo"))
    archived = await service.update_matrix(
        matrix.id, HpnMatrixUpdate(status=HpnMatrixStatus.ARCHIVED)
    )
    assert archived.status == HpnMatrixStatus.ARCHIVED
    assert (await service.detail(matrix.id)).matrix.status == HpnMatrixStatus.ARCHIVED
    assert (await service.list_matrices(page=1, page_size=20)).total == 1
    with pytest.raises(HpnError, match="HPN_MATRIX_ARCHIVED"):
        await service.create_node(
            matrix.id,
            HpnNodeCreate(
                node_type="fact", title="No", statement="No", display_order=1
            ),
        )
    with pytest.raises(HpnError, match="HPN_MATRIX_ARCHIVED"):
        await service.update_matrix(matrix.id, HpnMatrixUpdate(title="Cambio"))


@pytest.mark.asyncio
async def test_hpn_invalid_transition_does_not_mutate_matrix(
    hpn_session: AsyncSession,
) -> None:
    service = HpnService(hpn_session)
    matrix = await service.create_matrix(HpnMatrixCreate(title="Original"))
    with pytest.raises(HpnError, match="HPN_REVIEW_INCOMPLETE"):
        await service.update_matrix(
            matrix.id, HpnMatrixUpdate(title="No persistir", status="reviewed")
        )
    current = await service.detail(matrix.id)
    assert current.matrix.title == "Original"
    assert current.matrix.status == HpnMatrixStatus.DRAFT


@pytest.mark.asyncio
async def test_hpn_accepts_exactly_the_four_directed_relation_combinations(
    hpn_session: AsyncSession,
) -> None:
    service = HpnService(hpn_session)
    matrix, fact, evidence, norm = await _matrix_nodes(service)
    relation_types = (
        (evidence.id, "evidence_supports_fact"),
        (evidence.id, "evidence_contradicts_fact"),
        (norm.id, "norm_applies_to_fact"),
        (norm.id, "norm_limits_fact"),
    )
    created = []
    for source_id, relation_type in relation_types:
        created.append(
            await service.create_relation(
                matrix.id,
                HpnRelationCreate(
                    source_node_id=source_id,
                    target_node_id=fact.id,
                    relation_type=relation_type,
                ),
            )
        )
    assert {relation.relation_type.value for relation in created} == {
        relation_type for _, relation_type in relation_types
    }


@pytest.mark.asyncio
async def test_hpn_rejects_cross_matrix_deleted_and_self_relation_endpoints(
    hpn_session: AsyncSession,
) -> None:
    document, _ = await _document_chunk(hpn_session, "node-cascade")
    service = HpnService(hpn_session)
    first, fact, evidence, _ = await _matrix_nodes(service)
    second, second_fact, _, _ = await _matrix_nodes(service)
    with pytest.raises(HpnError, match="HPN_NODE_NOT_FOUND"):
        await service.create_relation(
            first.id,
            HpnRelationCreate(
                source_node_id=evidence.id,
                target_node_id=second_fact.id,
                relation_type="evidence_supports_fact",
            ),
        )
    with pytest.raises(HpnError, match="HPN_RELATION_ENDPOINT_INVALID"):
        await service.create_relation(
            first.id,
            HpnRelationCreate(
                source_node_id=evidence.id,
                target_node_id=evidence.id,
                relation_type="evidence_supports_fact",
            ),
        )
    source = await service.add_source(
        first.id,
        evidence.id,
        HpnSourceCreate(document_id=document.id, chunk_index=1),
    )
    relation = await service.create_relation(
        first.id,
        HpnRelationCreate(
            source_node_id=evidence.id,
            target_node_id=fact.id,
            relation_type="evidence_supports_fact",
        ),
    )
    await service.delete_node(first.id, evidence.id)
    persisted_source = await hpn_session.get(HpnNodeSource, source.source_id)
    persisted_relation = await hpn_session.get(HpnRelation, relation.id)
    assert persisted_source is not None and persisted_source.deleted_at is not None
    assert persisted_relation is not None and persisted_relation.deleted_at is not None
    with pytest.raises(HpnError, match="HPN_NODE_NOT_FOUND"):
        await service.create_relation(
            first.id,
            HpnRelationCreate(
                source_node_id=evidence.id,
                target_node_id=fact.id,
                relation_type="evidence_supports_fact",
            ),
        )
    assert (await service.detail(second.id)).matrix.id == second.id


@pytest.mark.asyncio
async def test_hpn_document_chunk_mismatch_is_unavailable(
    hpn_session: AsyncSession,
) -> None:
    from app.database.models.hpn import HpnNodeSource

    first_document, _ = await _document_chunk(hpn_session, "first-owner")
    second_document, _ = await _document_chunk(hpn_session, "second-owner")
    service = HpnService(hpn_session)
    matrix, _, evidence, _ = await _matrix_nodes(service)
    public = await service.add_source(
        matrix.id,
        evidence.id,
        HpnSourceCreate(document_id=first_document.id, chunk_index=1),
    )
    stored = await hpn_session.get(HpnNodeSource, public.source_id)
    assert stored is not None
    stored.document_id = second_document.id
    await hpn_session.commit()
    detail = await service.detail(matrix.id)
    assert detail.nodes[1].sources[0].source_status == "unavailable"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (r"C:\carpeta\fuente.pdf", "fuente.pdf"),
        ("/tmp/fuente.pdf", "fuente.pdf"),
        ("<script>alert(1)</script>.pdf", "script&gt;.pdf"),
        ("\x00", "documento.pdf"),
        (".", "documento.pdf"),
        ("..", "documento.pdf"),
        ("/tmp/acción-niñez.pdf", "acción-niñez.pdf"),
    ],
)
def test_hpn_source_name_is_safe(value: str, expected: str) -> None:
    sanitized = HpnService._sanitize_source_name(value)
    assert sanitized == expected
    assert "<" not in sanitized
