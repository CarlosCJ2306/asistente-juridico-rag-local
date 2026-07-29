"""Contratos, adaptadores y límites de 12D-1 sin activar dominio Case."""

from __future__ import annotations

import ast
import dataclasses
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.cases import (
    DocumentAccessPort,
    DocumentExtractionPort,
    EvidenceScope,
    LegacyHpnPort,
    LegacyHpnReference,
    LegacyLegalNetworkPort,
    LegacyNetworkReference,
    LegacySourceHealth,
    FutureAssignmentOutcome,
    LegacyCompatibilityReasonCode,
    LegacyCompatibilityState,
    LegacyDeprecationConditions,
    LegacyDeprecationReasonCode,
    TRANSITION_MANIFEST,
    ScopedRetrievalPort,
    ScopedRetrievalQuery,
    TransitionAdapterError,
    TransitionErrorCode,
    TransitionWarningCode,
    evaluate_future_manual_assignment,
    evaluate_legacy_deprecation,
)
from app.cases import contracts as transition_contracts
from app.cases.adapters import (
    DocumentAccessAdapter,
    DocumentExtractionAdapter,
    LegacyHpnAdapter,
    LegacyLegalNetworkAdapter,
    ScopedRetrievalAdapter,
)
from app.database.models.document import (
    DocumentStatus,
    DocumentType,
    IndexStatus,
    KnowledgeLayer,
    LegalValidityStatus,
    ReviewStatus,
)
from app.database.repositories.document_repository import DocumentRepository
from app.documents import DocumentBatch, DocumentRead, ExtractionSummary
from app.schemas.hybrid_search import HybridSearchItem, HybridSearchResponse


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
APP_ROOT = BACKEND_ROOT / "app"
FRONTEND_ROOT = PROJECT_ROOT / "frontend" / "src"


def _document(document_id: UUID) -> DocumentRead:
    return DocumentRead.model_construct(
        id=document_id,
        display_name="Documento sintético",
        document_type=DocumentType.JURISPRUDENCIA,
        status=DocumentStatus.EXTRACTED,
        knowledge_layer=KnowledgeLayer.PRIVATE_LIBRARY,
        review_status=ReviewStatus.NOT_REQUIRED,
        legal_validity_status=LegalValidityStatus.UNKNOWN,
        index_status=IndexStatus.INDEXED,
        rag_eligible=True,
    )


class FakeCatalog:
    def __init__(self, batch: DocumentBatch | Exception) -> None:
        self.batch = batch
        self.calls = 0

    async def resolve_many(self, document_ids: tuple[UUID, ...]) -> DocumentBatch:
        self.calls += 1
        if isinstance(self.batch, Exception):
            raise self.batch
        return self.batch


class FakeExtraction:
    def __init__(self, document: DocumentRead | None) -> None:
        self.document = document
        self.status_calls = 0
        self.request_calls = 0

    async def status(self, document_id: UUID) -> DocumentRead | None:
        self.status_calls += 1
        return self.document

    async def request(self, document_id: UUID) -> ExtractionSummary:
        self.request_calls += 1
        return ExtractionSummary(
            document_id=document_id,
            status=DocumentStatus.EXTRACTED,
            total_pages=2,
            total_chunks=3,
            total_characters=100,
        )


class FakeRetrieval:
    def __init__(self, response: HybridSearchResponse | Exception) -> None:
        self.response = response
        self.calls = 0
        self.requests = []

    async def search(self, request, *, request_id=None) -> HybridSearchResponse:
        self.calls += 1
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeHpn:
    def __init__(self, detail: object) -> None:
        self.detail_value = detail
        self.calls = 0

    async def detail(self, matrix_id: UUID):
        self.calls += 1
        return self.detail_value


class FakeNetwork:
    def __init__(self, projection: object) -> None:
        self.projection = projection
        self.calls = 0

    async def project(self, matrix_id: UUID, *, request_id=None):
        self.calls += 1
        return self.projection


@pytest.mark.asyncio
async def test_adapters_implement_ports_and_delegate_once() -> None:
    document_id = uuid4()
    matrix_id = uuid4()
    document = _document(document_id)
    catalog = FakeCatalog(DocumentBatch((document,), ()))
    extraction = FakeExtraction(document)
    retrieval = FakeRetrieval(
        HybridSearchResponse(
            items=[
                HybridSearchItem(
                    chunk_id=uuid4(),
                    document_id=document_id,
                    document_name="Documento sintético",
                    document_type=DocumentType.JURISPRUDENCIA,
                    knowledge_layer=KnowledgeLayer.PRIVATE_LIBRARY,
                    chunk_index=1,
                    start_page=1,
                    end_page=1,
                    snippet="Contenido sintético no propagado",
                    hybrid_score=0.02,
                    appeared_in_text=True,
                    appeared_in_semantic=False,
                    text_rank=1,
                    semantic_rank=None,
                    rank_bm25=-1.0,
                    distance_cosine=None,
                )
            ],
            returned=1,
            top_k=5,
        )
    )
    summary = SimpleNamespace(
        valid_for_review=True,
        fact_count=1,
        evidence_count=1,
        norm_count=1,
        relation_count=2,
        stale_source_count=0,
        unavailable_source_count=0,
    )
    hpn = FakeHpn(
        SimpleNamespace(
            matrix=SimpleNamespace(id=matrix_id, status=SimpleNamespace(value="reviewed")),
            validation_summary=summary,
        )
    )
    network = FakeNetwork(
        SimpleNamespace(
            matrix=SimpleNamespace(id=matrix_id),
            summary=SimpleNamespace(
                node_count=3,
                edge_count=2,
                disconnected_components=1,
                has_directed_cycles=False,
            ),
            warnings=(),
            requires_professional_review=True,
        )
    )
    document_adapter = DocumentAccessAdapter(catalog)
    extraction_adapter = DocumentExtractionAdapter(extraction)
    retrieval_adapter = ScopedRetrievalAdapter(retrieval)
    hpn_adapter = LegacyHpnAdapter(hpn)
    network_adapter = LegacyLegalNetworkAdapter(network)

    assert isinstance(document_adapter, DocumentAccessPort)
    assert isinstance(extraction_adapter, DocumentExtractionPort)
    assert isinstance(retrieval_adapter, ScopedRetrievalPort)
    assert isinstance(hpn_adapter, LegacyHpnPort)
    assert isinstance(network_adapter, LegacyLegalNetworkPort)

    batch = await document_adapter.resolve_documents((document_id,))
    status = await extraction_adapter.get_status(document_id)
    extracted = await extraction_adapter.request_extraction(document_id)
    results = await retrieval_adapter.search(
        ScopedRetrievalQuery(
            query="consulta sintética",
            scope=EvidenceScope((document_id,)),
            top_k=5,
        )
    )
    matrix = await hpn_adapter.get_matrix(matrix_id)
    graph = await network_adapter.project(matrix_id)

    assert batch.items[0].document_id == document_id
    assert status.status == DocumentStatus.EXTRACTED.value
    assert extracted.total_chunks == 3
    assert results.items[0].document_id == document_id
    assert not hasattr(results.items[0], "chunk_id")
    assert matrix.matrix_id == matrix_id
    assert graph.matrix_id == matrix_id
    assert (catalog.calls, extraction.status_calls, extraction.request_calls) == (1, 1, 1)
    assert (retrieval.calls, hpn.calls, network.calls) == (1, 1, 1)
    assert retrieval.requests[0].document_id == document_id


@pytest.mark.asyncio
async def test_scoped_retrieval_rejects_batch_without_n_plus_one() -> None:
    facade = FakeRetrieval(HybridSearchResponse(items=[], returned=0, top_k=5))
    adapter = ScopedRetrievalAdapter(facade)
    with pytest.raises(TransitionAdapterError) as caught:
        await adapter.search(
            ScopedRetrievalQuery(
                query="consulta sintética",
                scope=EvidenceScope((uuid4(), uuid4())),
                top_k=5,
            )
        )
    assert caught.value.code is TransitionErrorCode.RETRIEVAL_SCOPE_UNSUPPORTED
    assert facade.calls == 0


@pytest.mark.asyncio
async def test_adapter_errors_are_closed_and_do_not_log_sensitive_detail(
    caplog: pytest.LogCaptureFixture,
) -> None:
    marker = "SENSITIVE_TRANSITION_MARKER"
    adapter = DocumentAccessAdapter(FakeCatalog(RuntimeError(marker)))
    with caplog.at_level(logging.WARNING), pytest.raises(TransitionAdapterError) as caught:
        await adapter.resolve_documents((uuid4(),))
    assert caught.value.code is TransitionErrorCode.DEPENDENCY_ERROR
    assert marker not in caplog.text
    assert "RuntimeError" in caplog.text


def test_transition_dtos_are_frozen_and_private_fields_are_absent() -> None:
    instance = EvidenceScope((uuid4(),))
    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.document_ids = ()  # type: ignore[misc]

    forbidden = {
        "case_id",
        "relative_path",
        "stored_filename",
        "sha256",
        "chunk_id",
        "text",
        "prompt",
        "embedding",
        "vector",
        "html",
        "networkx",
        "user_id",
    }
    dto_types = [
        value
        for value in vars(transition_contracts).values()
        if isinstance(value, type) and dataclasses.is_dataclass(value)
    ]
    assert dto_types
    for dto_type in dto_types:
        assert forbidden.isdisjoint(field.name for field in dataclasses.fields(dto_type))


def _legacy_hpn(
    *,
    source_health: LegacySourceHealth = LegacySourceHealth.VALID,
    status: str = "reviewed",
    warnings: tuple[TransitionWarningCode, ...] = (),
) -> LegacyHpnReference:
    return LegacyHpnReference(
        public_matrix_id=uuid4(),
        status=status,
        fact_count=1,
        evidence_count=1,
        norm_count=1,
        relation_count=1,
        stale_source_count=source_health is LegacySourceHealth.STALE,
        unavailable_source_count=source_health is LegacySourceHealth.UNAVAILABLE,
        read_only=status == "archived",
        warnings=warnings,
        display_name="Matriz sintética",
        source_health=source_health,
    )


def _legacy_network(*, available: bool = True, warning_codes: tuple[str, ...] = ()) -> LegacyNetworkReference:
    return LegacyNetworkReference(
        public_matrix_id=uuid4(),
        node_count=1,
        edge_count=0,
        disconnected_components=1,
        has_directed_cycles=False,
        warning_codes=warning_codes,
        requires_professional_review=True,
        graph_availability=available,
    )


def test_legacy_classification_manifest_and_deprecation_are_static_and_disabled() -> None:
    assert LegacyCompatibilityState.CURRENT_GLOBAL.value == "current_global"
    assert TRANSITION_MANIFEST.schema_version == 1
    assert {module.name for module in TRANSITION_MANIFEST.modules} == {
        "hpn_global",
        "legal_network_global",
    }
    assert "/matrices-hpn" in TRANSITION_MANIFEST.modules[0].current_routes
    decision = evaluate_legacy_deprecation(LegacyDeprecationConditions())
    assert not decision.deprecation_ready
    assert not decision.retirement_ready
    assert LegacyDeprecationReasonCode.TRANSITION_PHASE_NOT_READY in decision.reason_codes


def test_future_assignment_policy_is_pure_and_uses_closed_safety_codes() -> None:
    eligible = evaluate_future_manual_assignment(_legacy_hpn(), _legacy_network())
    assert eligible.outcome is FutureAssignmentOutcome.ELIGIBLE_FOR_FUTURE_MANUAL_ASSIGNMENT
    assert eligible.reason_codes == ()

    stale = evaluate_future_manual_assignment(
        _legacy_hpn(source_health=LegacySourceHealth.STALE), _legacy_network()
    )
    assert stale.outcome is FutureAssignmentOutcome.REQUIRES_REVIEW
    assert stale.reason_codes == (LegacyCompatibilityReasonCode.SOURCE_STALE,)

    unavailable = evaluate_future_manual_assignment(
        _legacy_hpn(source_health=LegacySourceHealth.UNAVAILABLE), _legacy_network()
    )
    assert unavailable.outcome is FutureAssignmentOutcome.BLOCKED
    assert unavailable.reason_codes == (LegacyCompatibilityReasonCode.SOURCE_UNAVAILABLE,)

    structural = evaluate_future_manual_assignment(
        _legacy_hpn(), _legacy_network(warning_codes=("GRAPH_RELATION_INVALID",))
    )
    assert structural.outcome is FutureAssignmentOutcome.BLOCKED
    assert LegacyCompatibilityReasonCode.STRUCTURAL_INTEGRITY_INVALID in structural.reason_codes


@pytest.mark.asyncio
async def test_document_batch_repository_uses_one_query() -> None:
    first, second = SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())
    scalar_result = MagicMock()
    scalar_result.all.return_value = [first, second]
    session = MagicMock()
    session.scalars = AsyncMock(return_value=scalar_result)

    resolved = await DocumentRepository(session).get_by_ids([first.id, second.id])

    assert resolved == {first.id: first, second.id: second}
    session.scalars.assert_awaited_once()


def test_cases_import_has_no_runtime_side_effects() -> None:
    code = """
import sys
import app.cases
for forbidden in (
    'app.main', 'app.api.router', 'app.database.session', 'chromadb',
    'sentence_transformers', 'llama_cpp',
):
    assert forbidden not in sys.modules, forbidden
"""
    env = os.environ.copy()
    env.update({"LOG_TO_FILE": "false", "LOG_CONSOLE": "false"})
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def test_backend_dependency_direction_and_inactive_package_boundaries() -> None:
    for path in APP_ROOT.rglob("*.py"):
        relative = path.relative_to(APP_ROOT)
        imports = _imports(path)
        allowed_case_consumers = {
            ("api", "routes", "cases.py"),
            ("api", "routes", "case_documents.py"),
            ("schemas", "case.py"),
            ("schemas", "case_document.py"),
        }
        if relative.parts[0] != "cases" and relative.parts not in allowed_case_consumers:
            assert not any(name == "app.cases" or name.startswith("app.cases.") for name in imports), path
        if relative.parts[:2] in {
            ("cases", "contracts.py"),
            ("cases", "ports.py"),
            ("cases", "errors.py"),
            ("cases", "legacy_compatibility.py"),
            ("cases", "transition_manifest.py"),
        }:
            assert not any(
                name.startswith(("sqlalchemy", "fastapi", "app.api", "app.database", "app.services"))
                for name in imports
            ), path
        if relative.parts[0] == "cases":
            assert not any(name.startswith("app.api") for name in imports), path


CURRENT_PUBLIC_ROUTES = {
    ("POST", "/api/cases"),
    ("GET", "/api/cases"),
    ("GET", "/api/cases/{case_id}"),
    ("PATCH", "/api/cases/{case_id}"),
    ("DELETE", "/api/cases/{case_id}"),
    ("POST", "/api/cases/{case_id}/activate"),
    ("POST", "/api/cases/{case_id}/review"),
    ("POST", "/api/cases/{case_id}/close"),
    ("POST", "/api/cases/{case_id}/archive"),
    ("POST", "/api/cases/{case_id}/restore"),
    ("POST", "/api/cases/{case_id}/documents"),
    ("GET", "/api/cases/{case_id}/documents"),
    ("GET", "/api/cases/{case_id}/documents/{association_id}"),
    ("PATCH", "/api/cases/{case_id}/documents/{association_id}"),
    ("DELETE", "/api/cases/{case_id}/documents/{association_id}"),
    ("POST", "/api/chat/rag"),
    ("GET", "/api/conversations"),
    ("POST", "/api/conversations"),
    ("GET", "/api/conversations/{conversation_id}"),
    ("PATCH", "/api/conversations/{conversation_id}"),
    ("DELETE", "/api/conversations/{conversation_id}"),
    ("POST", "/api/conversations/{conversation_id}/messages"),
    ("GET", "/api/documents"),
    ("POST", "/api/documents"),
    ("GET", "/api/documents/processing/jobs"),
    ("GET", "/api/documents/processing/jobs/{job_id}"),
    ("POST", "/api/documents/processing/jobs/{job_id}/retry"),
    ("GET", "/api/documents/processing/summary"),
    ("GET", "/api/documents/{document_id}"),
    ("DELETE", "/api/documents/{document_id}"),
    ("GET", "/api/documents/{document_id}/chunks"),
    ("POST", "/api/documents/{document_id}/extract"),
    ("GET", "/api/documents/{document_id}/pages"),
    ("GET", "/api/health"),
    ("GET", "/api/hpn/matrices"),
    ("POST", "/api/hpn/matrices"),
    ("GET", "/api/hpn/matrices/{matrix_id}"),
    ("PATCH", "/api/hpn/matrices/{matrix_id}"),
    ("DELETE", "/api/hpn/matrices/{matrix_id}"),
    ("GET", "/api/hpn/matrices/{matrix_id}/graph"),
    ("GET", "/api/hpn/matrices/{matrix_id}/graph/export"),
    ("POST", "/api/hpn/matrices/{matrix_id}/nodes"),
    ("PATCH", "/api/hpn/matrices/{matrix_id}/nodes/{node_id}"),
    ("DELETE", "/api/hpn/matrices/{matrix_id}/nodes/{node_id}"),
    ("POST", "/api/hpn/matrices/{matrix_id}/nodes/{node_id}/sources"),
    ("DELETE", "/api/hpn/matrices/{matrix_id}/nodes/{node_id}/sources/{source_id}"),
    ("POST", "/api/hpn/matrices/{matrix_id}/relations"),
    ("PATCH", "/api/hpn/matrices/{matrix_id}/relations/{relation_id}"),
    ("DELETE", "/api/hpn/matrices/{matrix_id}/relations/{relation_id}"),
    ("GET", "/api/hpn/matrices/{matrix_id}/validation"),
    ("GET", "/api/models/catalog"),
    ("POST", "/api/models/embeddings/load"),
    ("GET", "/api/models/embeddings/status"),
    ("POST", "/api/models/embeddings/unload"),
    ("POST", "/api/models/llm/load"),
    ("GET", "/api/models/llm/status"),
    ("POST", "/api/models/llm/unload"),
    ("GET", "/api/models/selection"),
    ("PUT", "/api/models/selection/embeddings"),
    ("PUT", "/api/models/selection/llm"),
    ("GET", "/api/models/status"),
    ("POST", "/api/search/hybrid"),
    ("POST", "/api/search/semantic"),
    ("POST", "/api/search/semantic/rebuild"),
    ("GET", "/api/search/semantic/status"),
    ("POST", "/api/search/text"),
}


def test_public_route_and_openapi_parity_without_case_contracts() -> None:
    from app.main import app

    schema = app.openapi()
    methods = {"get", "post", "put", "patch", "delete"}
    actual = {
        (method.upper(), path)
        for path, operations in schema["paths"].items()
        for method in methods & set(operations)
    }
    assert actual == CURRENT_PUBLIC_ROUTES
    assert {path for _, path in actual if path.startswith("/api/cases")} == {
        "/api/cases",
        "/api/cases/{case_id}",
        "/api/cases/{case_id}/activate",
        "/api/cases/{case_id}/review",
        "/api/cases/{case_id}/close",
        "/api/cases/{case_id}/archive",
        "/api/cases/{case_id}/restore",
        "/api/cases/{case_id}/documents",
        "/api/cases/{case_id}/documents/{association_id}",
    }
    case_document_schema = schema["components"]["schemas"]["CaseDocumentPublic"]
    forbidden = {
        "snapshot",
        "owner_key_hash",
        "relative_path",
        "stored_filename",
        "sha256",
        "removed_at",
    }
    assert forbidden.isdisjoint(case_document_schema["properties"])
    assert not any(name.startswith("Transition") for name in schema["components"]["schemas"])


IMPORT_PATTERN = re.compile(r"from\s+[\"']([^\"']+)[\"']")


def test_frontend_features_use_public_facades_and_routes_remain_stable() -> None:
    feature_root = FRONTEND_ROOT / "features"
    for path in feature_root.rglob("*.ts*"):
        source = path.read_text(encoding="utf-8")
        for imported in IMPORT_PATTERN.findall(source):
            if imported.startswith("../../"):
                parts = imported[6:].split("/")
                if parts[0] in {"cases", "chat", "documents", "hpn-matrices", "legal-network", "models"}:
                    assert len(parts) == 1, f"import profundo entre features: {path}: {imported}"
            assert "design-system/internal" not in imported
            assert not (".module.css" in imported and imported.startswith("../../"))

    router = (FRONTEND_ROOT / "router" / "index.tsx").read_text(encoding="utf-8")
    paths = set(re.findall(r'path:\s*"([^"]+)"', router))
    assert paths == {
        "/",
        "chat",
        "chat/:conversationId",
        "cases",
        "documents",
        "documents/search",
        "documents/:documentId",
        "matrices-hpn",
        "matrices-hpn/:matrixId",
        "legal-network",
        "legal-network/:matrixId",
        "models",
        "*",
    }
    navigation = (FRONTEND_ROOT / "app" / "navigation" / "navigation.config.ts").read_text(
        encoding="utf-8"
    )
    assert 'route: "/cases"' in navigation
    assert "Casos" in navigation
    assert 'path: "cases/:caseId"' not in router
    assert 'path: "cases/new"' not in router

    cases_root = feature_root / "cases"
    assert cases_root.is_dir()
    assert not any((cases_root / name).exists() for name in ("api", "hooks", "queries"))
    for path in cases_root.rglob("*.ts*"):
        source = path.read_text(encoding="utf-8")
        assert "fetch(" not in source
        assert "useQuery(" not in source


def test_design_system_does_not_import_features_or_domain_logic() -> None:
    design_system = FRONTEND_ROOT / "design-system"
    for path in design_system.rglob("*.ts*"):
        imports = IMPORT_PATTERN.findall(path.read_text(encoding="utf-8"))
        assert not any("features/" in imported or "/pages" in imported for imported in imports), path
