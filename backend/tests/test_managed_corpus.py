"""Pruebas aisladas del corpus administrado sin fuentes ni persistencias reales."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import UploadFile
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from app.core.config import Settings
from app.database.base import Base
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
from app.database.models.managed_corpus import ManagedCorpusEntry
from app.database.session import DatabaseSessionManager
from app.main import app
from app.schemas.document import DocumentUploadGovernance
from app.schemas.managed_corpus import (
    ManagedCorpusItemStatus,
    ManagedCorpusManifest,
)
from app.services import managed_corpus_service as corpus_module
from app.services.document_service import DocumentService, DocumentStorageError
from app.services.managed_corpus_service import ManagedCorpusError, ManagedCorpusService


PDF_ONE = b"%PDF-1.7\ncontenido ficticio uno\n%%EOF"
PDF_TWO = b"%PDF-1.7\ncontenido ficticio dos\n%%EOF"


def _document_payload(
    *,
    source_key: str = "norma-uno-v1",
    filename: str = "normas/norma-uno.pdf",
    content: bytes = PDF_ONE,
    with_metadata: bool = True,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_key": source_key,
        "filename": filename,
        "display_name": "Norma sintética",
        "document_type": "normativa",
        "expected_sha256": hashlib.sha256(content).hexdigest(),
    }
    if with_metadata:
        payload.update(
            {
                "issuing_entity": "Entidad sintética",
                "jurisdiction": "Jurisdicción sintética",
                "legal_area": "Área sintética",
                "canonical_source_url": "https://example.invalid/norma",
                "published_at": "2026-07-27T00:00:00Z",
                "version_label": "v1",
                "administrative_note": "Revisión ficticia",
            }
        )
    return payload


def _manifest(*documents: dict[str, object]) -> ManagedCorpusManifest:
    return ManagedCorpusManifest.model_validate(
        {
            "schema_version": 1,
            "corpus_id": "test-corpus",
            "documents": list(documents or (_document_payload(),)),
        }
    )


@pytest_asyncio.fixture
async def corpus_environment(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncSession, ManagedCorpusService, Path, Path]]:
    database_file = tmp_path / "database" / "managed.db"
    database_file.parent.mkdir()
    manager = DatabaseSessionManager(database_file)
    async with manager.get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    staging = tmp_path / "staging"
    documents = tmp_path / "storage" / "documents"
    temporary = tmp_path / "storage" / "temp" / "uploads"
    staging.mkdir()
    async with manager.get_session_factory()() as session:
        document_service = DocumentService(
            session,
            temporary_directory=temporary,
            documents_directory=documents,
            project_root=tmp_path,
            maximum_size_bytes=4096,
            chunk_size_bytes=8,
        )
        service = ManagedCorpusService(
            session,
            staging_directory=staging,
            document_service=document_service,
        )
        yield session, service, staging, documents
    await manager.dispose()


def _write_staging(staging: Path, filename: str, content: bytes = PDF_ONE) -> Path:
    path = staging / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_manifest_is_strict_versioned_and_rejects_unsafe_values() -> None:
    assert _manifest().schema_version == 1
    invalid_payloads = [
        {"schema_version": 2, "corpus_id": "test", "documents": []},
        {
            "schema_version": 1,
            "corpus_id": "test",
            "documents": [
                _document_payload(source_key="same"),
                _document_payload(source_key="same", filename="other.pdf"),
            ],
        },
        {
            "schema_version": 1,
            "corpus_id": "test",
            "documents": [_document_payload(filename="../escape.pdf")],
        },
        {
            "schema_version": 1,
            "corpus_id": "test",
            "documents": [{**_document_payload(), "document_type": "invalid"}],
        },
        {
            "schema_version": 1,
            "corpus_id": "test",
            "documents": [{**_document_payload(), "published_at": "fecha"}],
        },
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            ManagedCorpusManifest.model_validate(payload)


def test_manifest_loader_returns_only_stable_error(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{invalid", encoding="utf-8")
    with pytest.raises(ManagedCorpusError, match="MANAGED_CORPUS_MANIFEST_INVALID"):
        ManagedCorpusService.load_manifest(manifest_path)


def test_manifest_loader_accepts_valid_json(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest().model_dump(mode="json")), encoding="utf-8"
    )
    assert ManagedCorpusService.load_manifest(manifest_path).corpus_id == "test-corpus"


def test_staging_configuration_rejects_escape() -> None:
    settings = Settings(
        _env_file=None,
        database_file="storage/database/test.db",
        managed_corpus_staging_path="storage/staging/corpus",
    )
    assert settings.managed_corpus_staging_path.name == "corpus"
    with pytest.raises(ValidationError, match="MANAGED_CORPUS_STAGING_PATH_INVALID"):
        Settings(
            _env_file=None,
            database_file="storage/database/test.db",
            managed_corpus_staging_path="../outside",
        )


@pytest.mark.asyncio
async def test_validate_is_dry_run_and_reports_missing_hash_and_invalid_pdf(
    corpus_environment,
) -> None:
    session, service, staging, documents = corpus_environment
    missing = await service.validate(_manifest())
    assert missing.failed == 1
    assert missing.results[0].safe_reason_code == "MANAGED_CORPUS_FILE_NOT_FOUND"

    _write_staging(staging, "normas/norma-uno.pdf", b"not-a-pdf")
    invalid = await service.validate(_manifest())
    assert invalid.results[0].safe_reason_code == "MANAGED_CORPUS_PDF_SIGNATURE_INVALID"

    _write_staging(staging, "normas/norma-uno.pdf")
    mismatch_manifest = _manifest(
        {**_document_payload(), "expected_sha256": "0" * 64}
    )
    mismatch = await service.validate(mismatch_manifest)
    assert mismatch.results[0].safe_reason_code == "MANAGED_CORPUS_HASH_MISMATCH"
    assert await session.scalar(select(func.count()).select_from(Document)) == 0
    assert not list(documents.rglob("*.pdf"))


@pytest.mark.asyncio
async def test_validate_accepts_safe_pdf_without_writing(corpus_environment) -> None:
    session, service, staging, documents = corpus_environment
    staged = _write_staging(staging, "normas/norma-uno.pdf")
    before = staged.read_bytes()
    result = await service.validate(_manifest())
    assert result.failed == result.conflicts == 0
    assert result.results[0].status is ManagedCorpusItemStatus.VALID
    assert staged.read_bytes() == before
    assert await session.scalar(select(func.count()).select_from(Document)) == 0
    assert not list(documents.rglob("*.pdf"))


@pytest.mark.asyncio
async def test_symlink_is_rejected_when_supported(corpus_environment) -> None:
    _, service, staging, _ = corpus_environment
    target = _write_staging(staging, "target.pdf")
    link = staging / "linked.pdf"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("El sistema no permite crear symlinks para esta prueba")
    result = await service.validate(
        _manifest(_document_payload(filename="linked.pdf"))
    )
    assert result.results[0].safe_reason_code == "MANAGED_CORPUS_STAGING_SYMLINK_REJECTED"


@pytest.mark.asyncio
async def test_import_is_pending_not_rag_eligible_and_idempotent(
    corpus_environment,
) -> None:
    session, service, staging, documents = corpus_environment
    _write_staging(staging, "normas/norma-uno.pdf")
    first = await service.import_documents(_manifest())
    second = await service.import_documents(_manifest())
    assert first.results[0].status is ManagedCorpusItemStatus.IMPORTED_PENDING
    assert second.results[0].status is ManagedCorpusItemStatus.IMPORTED_PENDING
    document = await session.scalar(select(Document))
    assert document is not None
    assert document.knowledge_layer is KnowledgeLayer.MANAGED_CORPUS
    assert document.source_kind is SourceKind.MANAGED_IMPORT
    assert document.review_status is ReviewStatus.PENDING
    assert document.legal_validity_status is LegalValidityStatus.UNKNOWN
    assert document.index_status is IndexStatus.NOT_REQUESTED
    assert document.status is DocumentStatus.PENDING_EXTRACTION
    assert service.governance.evaluate_rag_eligibility(document).eligible is False
    assert await session.scalar(select(func.count()).select_from(Document)) == 1
    assert await session.scalar(select(func.count()).select_from(ManagedCorpusEntry)) == 1
    assert len(list(documents.rglob("*.pdf"))) == 1
    serialized = first.model_dump_json()
    assert document.sha256 not in serialized
    assert document.relative_path not in serialized
    assert str(document.id) not in serialized


@pytest.mark.asyncio
async def test_imported_versions_are_distinct_and_linked_without_overwrite(
    corpus_environment,
) -> None:
    session, service, staging, documents = corpus_environment
    _write_staging(staging, "normas/norma-uno-v1.pdf", PDF_ONE)
    _write_staging(staging, "normas/norma-uno-v2.pdf", PDF_TWO)
    first = _document_payload(
        source_key="norma-uno-v1",
        filename="normas/norma-uno-v1.pdf",
        content=PDF_ONE,
    )
    second = _document_payload(
        source_key="norma-uno-v2",
        filename="normas/norma-uno-v2.pdf",
        content=PDF_TWO,
    )
    second["version_label"] = "v2"
    second["supersedes_source_key"] = "norma-uno-v1"

    manifest = _manifest(first, second)
    validation = await service.validate(manifest)
    result = await service.import_documents(manifest)

    assert validation.succeeded == 2
    assert result.succeeded == 2
    stored = list(
        (
            await session.scalars(
                select(Document).order_by(Document.created_at, Document.id)
            )
        ).all()
    )
    assert len(stored) == 2
    by_version = {document.version_label: document for document in stored}
    assert by_version["v2"].supersedes_document_id == by_version["v1"].id
    assert by_version["v1"].supersedes_document_id is None
    assert len(list(documents.rglob("*.pdf"))) == 2


def test_version_requires_preceding_source_in_manifest() -> None:
    payload = _document_payload(
        source_key="norma-uno-v2",
        filename="normas/norma-uno-v2.pdf",
        content=PDF_TWO,
    )
    payload["supersedes_source_key"] = "norma-uno-v1"

    with pytest.raises(
        ValidationError, match="MANAGED_CORPUS_PREVIOUS_VERSION_ORDER_INVALID"
    ):
        _manifest(payload)


@pytest.mark.asyncio
async def test_import_rolls_back_and_removes_files_on_storage_error(
    corpus_environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, service, staging, documents = corpus_environment
    _write_staging(staging, "normas/norma-uno.pdf")

    def fail_move(_temporary: Path, _final: Path) -> None:
        raise DocumentStorageError("synthetic")

    monkeypatch.setattr(service.document_service, "_move_to_final_path", fail_move)
    result = await service.import_documents(_manifest())
    assert result.failed == 1
    assert result.results[0].safe_reason_code == "MANAGED_CORPUS_IMPORT_ERROR"
    assert await session.scalar(select(func.count()).select_from(Document)) == 0
    assert await session.scalar(select(func.count()).select_from(ManagedCorpusEntry)) == 0
    assert not list(documents.rglob("*.pdf"))


@pytest.mark.asyncio
async def test_review_requires_metadata_confirmation_and_never_indexes(
    corpus_environment,
) -> None:
    session, service, staging, _ = corpus_environment
    _write_staging(staging, "normas/norma-uno.pdf")
    manifest = _manifest()
    await service.import_documents(manifest)
    with pytest.raises(ManagedCorpusError, match="APPROVAL_CONFIRMATION"):
        await service.review(
            manifest,
            source_key="norma-uno-v1",
            decision="approve",
            legal_validity=LegalValidityStatus.CURRENT,
            confirmed=False,
        )
    approved = await service.review(
        manifest,
        source_key="norma-uno-v1",
        decision="approve",
        legal_validity=LegalValidityStatus.CURRENT,
        confirmed=True,
    )
    assert approved.status is ManagedCorpusItemStatus.APPROVED
    document = await session.scalar(select(Document))
    assert document is not None
    assert document.review_status is ReviewStatus.APPROVED
    assert document.legal_validity_status is LegalValidityStatus.CURRENT
    assert document.index_status is IndexStatus.NOT_REQUESTED
    assert service.governance.evaluate_rag_eligibility(document).eligible is False
    pending = await service.review(
        manifest,
        source_key="norma-uno-v1",
        decision="pending",
    )
    assert pending.review_status is ReviewStatus.PENDING


@pytest.mark.asyncio
async def test_approval_rejects_missing_provenance_metadata(corpus_environment) -> None:
    _, service, staging, _ = corpus_environment
    _write_staging(staging, "normas/norma-uno.pdf")
    manifest = _manifest(_document_payload(with_metadata=False))
    await service.import_documents(manifest)
    with pytest.raises(ManagedCorpusError, match="APPROVAL_METADATA_REQUIRED"):
        await service.review(
            manifest,
            source_key="norma-uno-v1",
            decision="approve",
            legal_validity=LegalValidityStatus.CURRENT,
            confirmed=True,
        )


@pytest.mark.asyncio
async def test_review_rejects_and_invalid_transition_is_controlled(
    corpus_environment,
) -> None:
    _, service, staging, _ = corpus_environment
    _write_staging(staging, "normas/norma-uno.pdf")
    manifest = _manifest()
    await service.import_documents(manifest)
    rejected = await service.review(
        manifest,
        source_key="norma-uno-v1",
        decision="reject",
    )
    assert rejected.status is ManagedCorpusItemStatus.REJECTED
    with pytest.raises(ManagedCorpusError, match="REVIEW_TRANSITION_INVALID"):
        await service.review(
            manifest,
            source_key="norma-uno-v1",
            decision="approve",
            legal_validity=LegalValidityStatus.CURRENT,
            confirmed=True,
        )


async def _ordinary_upload(
    service: ManagedCorpusService, staging: Path, content: bytes = PDF_ONE
) -> Document:
    source = _write_staging(staging, "ordinary.pdf", content)
    upload = UploadFile(
        file=source.open("rb"),
        filename="ordinary.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )
    created = await service.document_service.upload_pdf(
        upload,
        DocumentType.NORMATIVA,
        DocumentUploadGovernance(),
    )
    document = await service.documents.get_by_id(created.id)
    assert document is not None
    return document


@pytest.mark.asyncio
async def test_duplicate_private_requires_explicit_promotion(corpus_environment) -> None:
    session, service, staging, documents = corpus_environment
    document = await _ordinary_upload(service, staging)
    _write_staging(staging, "normas/norma-uno.pdf")
    manifest = _manifest()
    validation = await service.validate(manifest)
    assert validation.conflicts == 1
    assert (
        validation.results[0].safe_reason_code
        == "MANAGED_CORPUS_DUPLICATE_REQUIRES_PROMOTION"
    )
    assert document.knowledge_layer is KnowledgeLayer.PRIVATE_LIBRARY
    with pytest.raises(ManagedCorpusError, match="PROMOTION_CONFIRMATION"):
        await service.promote(
            manifest,
            source_key="norma-uno-v1",
            document_id=document.id,
            confirmed=False,
        )
    promoted = await service.promote(
        manifest,
        source_key="norma-uno-v1",
        document_id=document.id,
        confirmed=True,
    )
    assert promoted.knowledge_layer is KnowledgeLayer.MANAGED_CORPUS
    assert promoted.review_status is ReviewStatus.PENDING
    assert promoted.legal_validity_status is LegalValidityStatus.UNKNOWN
    assert promoted.index_status is IndexStatus.EXCLUDED
    assert len(list(documents.rglob("*.pdf"))) == 1
    assert await session.scalar(select(func.count()).select_from(Document)) == 1


@pytest.mark.asyncio
async def test_promotion_rejects_hash_mismatch(corpus_environment) -> None:
    _, service, staging, _ = corpus_environment
    document = await _ordinary_upload(service, staging, PDF_ONE)
    _write_staging(staging, "normas/norma-uno.pdf", PDF_TWO)
    manifest = _manifest(_document_payload(content=PDF_TWO))
    with pytest.raises(ManagedCorpusError, match="PROMOTION_HASH_MISMATCH"):
        await service.promote(
            manifest,
            source_key="norma-uno-v1",
            document_id=document.id,
            confirmed=True,
        )
    assert document.knowledge_layer is KnowledgeLayer.PRIVATE_LIBRARY


@pytest.mark.asyncio
async def test_source_key_change_is_conflict_and_status_is_safe(corpus_environment) -> None:
    session, service, staging, _ = corpus_environment
    _write_staging(staging, "normas/norma-uno.pdf")
    manifest = _manifest()
    await service.import_documents(manifest)
    _write_staging(staging, "normas/norma-uno.pdf", PDF_TWO)
    changed = _manifest(_document_payload(content=PDF_TWO))
    validation = await service.validate(changed)
    assert validation.results[0].safe_reason_code == "MANAGED_CORPUS_SOURCE_VERSION_CONFLICT"
    status = await service.status(manifest)
    assert status.results[0].status is ManagedCorpusItemStatus.IMPORTED_PENDING
    document = await session.scalar(select(Document))
    assert document is not None
    assert document.sha256 not in status.model_dump_json()
    assert document.relative_path not in status.model_dump_json()


@pytest.mark.asyncio
async def test_logs_and_results_do_not_expose_content_paths_or_hashes(
    corpus_environment, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, service, staging, _ = corpus_environment
    marker = "PDF_PRIVATE_MARKER"
    content = f"%PDF-1.7\n{marker}\n%%EOF".encode()
    _write_staging(staging, "normas/norma-uno.pdf", content)
    manifest = _manifest(_document_payload(content=content))

    def capture(message: str, **context: object) -> None:
        logging.getLogger("managed_corpus_test").info("%s %s", message, context)

    monkeypatch.setattr(corpus_module, "log_info", capture)
    with caplog.at_level(logging.INFO, logger="managed_corpus_test"):
        result = await service.validate(manifest)
    serialized = result.model_dump_json()
    assert marker not in caplog.text
    assert str(staging) not in caplog.text
    assert hashlib.sha256(content).hexdigest() not in caplog.text
    assert str(staging) not in serialized
    assert hashlib.sha256(content).hexdigest() not in serialized


def test_no_public_administrative_endpoint_exists() -> None:
    with TestClient(app) as client:
        paths = client.get("/openapi.json").json()["paths"]
    assert all("managed-corpus" not in path and "managed_corpus" not in path for path in paths)


def test_cli_contract_has_explicit_commands_and_safe_exit_codes(capsys) -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "manage_corpus.py"
    spec = importlib.util.spec_from_file_location("manage_corpus_test_module", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parser = module.build_parser()
    for command in ("validate", "import", "status"):
        assert parser.parse_args([command]).command == command
    assert parser.parse_args(["review", "--source-key", "x", "--decision", "reject"]).command == "review"
    assert parser.parse_args(
        ["promote", "--source-key", "x", "--document-id", str(UUID(int=1))]
    ).command == "promote"

    result = corpus_module.ManagedCorpusBatchResult(
        corpus_id="test",
        operation="validate",
        results=[],
        succeeded=0,
        conflicts=0,
        failed=0,
    )
    module._print_result(result, as_json=True)
    output = capsys.readouterr().out
    assert json.loads(output)["operation"] == "validate"
    assert module._result_exit_code(result) == 0
