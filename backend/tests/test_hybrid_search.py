"""Pruebas deterministas de recuperación híbrida sin índices ni modelos reales."""

from __future__ import annotations

import asyncio
import logging
import math
import runpy
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.database.models.document import DocumentType, KnowledgeLayer, ReviewStatus
from app.database.repositories.semantic_chunk_repository import ActiveChunk
from app.database.repositories.text_search_repository import TextSearchRepositoryError
from app.database.session import DatabaseSessionManager, get_db_session
from app.main import app
from app.schemas.hybrid_search import (
    HybridSearchItem,
    HybridSearchRequest,
    HybridSearchResponse,
)
from app.schemas.semantic_search import (
    SemanticSearchItem,
    SemanticSearchResponse,
)
from app.schemas.text_search import TextSearchItem, TextSearchPage
from app.services import hybrid_search_service as hybrid_module
from app.services.hybrid_search_service import (
    HybridSearchError,
    HybridSearchService,
    _CombinedCandidate,
)
from app.services.semantic_index_service import SemanticServiceError
from app.services.document_governance_service import DocumentGovernanceSnapshot


def _active(chunk_id: UUID, *, index: int = 1, text: str = "Texto sintético") -> ActiveChunk:
    return ActiveChunk(
        chunk_id=chunk_id,
        document_id=UUID(int=index),
        document_type=DocumentType.JURISPRUDENCIA,
        chunk_index=index,
        text=text,
        start_page=index,
        end_page=index,
    )


def _text(chunk: ActiveChunk, rank: float = -1.0) -> TextSearchItem:
    return TextSearchItem(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_type=chunk.document_type,
        chunk_index=chunk.chunk_index,
        start_page=chunk.start_page,
        end_page=chunk.end_page,
        snippet="ignorado",
        rank_bm25=rank,
    )


def _semantic(chunk: ActiveChunk, distance: float = 0.2) -> SemanticSearchItem:
    return SemanticSearchItem(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_type=chunk.document_type,
        chunk_index=chunk.chunk_index,
        start_page=chunk.start_page,
        end_page=chunk.end_page,
        snippet="ignorado",
        distance_cosine=distance,
    )


class FakeTextService:
    def __init__(self, items: list[TextSearchItem]) -> None:
        self.items = items
        self.requests = []

    async def search(self, request, *, request_id=None) -> TextSearchPage:
        self.requests.append(request)
        return TextSearchPage(
            items=self.items,
            total=len(self.items),
            page=1,
            page_size=request.page_size,
        )


class FakeSemanticService:
    def __init__(self, items: list[SemanticSearchItem]) -> None:
        self.items = items
        self.requests = []

    async def search(self, request, *, request_id=None) -> SemanticSearchResponse:
        self.requests.append(request)
        return SemanticSearchResponse(
            items=self.items,
            returned=len(self.items),
            top_k=request.top_k,
        )


class FakeRepository:
    def __init__(self, chunks: list[ActiveChunk]) -> None:
        self.chunks = {chunk.chunk_id: chunk for chunk in chunks}

    async def get_active_by_ids(self, chunk_ids: list[UUID]) -> dict[UUID, ActiveChunk]:
        return {chunk_id: self.chunks[chunk_id] for chunk_id in chunk_ids if chunk_id in self.chunks}


def _run_search(
    request: HybridSearchRequest,
    text_items: list[TextSearchItem],
    semantic_items: list[SemanticSearchItem],
    chunks: list[ActiveChunk],
) -> tuple[HybridSearchResponse, FakeTextService, FakeSemanticService]:
    text_service = FakeTextService(text_items)
    semantic_service = FakeSemanticService(semantic_items)
    service = HybridSearchService(
        object(),  # type: ignore[arg-type]
        text_service=text_service,  # type: ignore[arg-type]
        semantic_service=semantic_service,  # type: ignore[arg-type]
        repository=FakeRepository(chunks),  # type: ignore[arg-type]
    )
    response = asyncio.run(service.search(request))
    return response, text_service, semantic_service


@pytest.mark.parametrize(
    "overrides",
    [
        {"hybrid_rrf_k": 0},
        {"hybrid_text_weight": 0},
        {"hybrid_text_weight": -1},
        {"hybrid_text_weight": math.nan},
        {"hybrid_semantic_weight": math.inf},
        {"hybrid_top_k_default": 51, "hybrid_top_k_max": 50},
        {"hybrid_candidate_multiplier": 0},
        {"hybrid_candidate_multiplier": 11},
        {"hybrid_rrf_k": True},
        {"hybrid_text_weight": True},
        {"hybrid_top_k_default": True},
        {"hybrid_candidate_multiplier": True},
    ],
)
def test_hybrid_settings_reject_invalid_values(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(**overrides)


def test_hybrid_settings_accept_defaults_and_request_forbids_fusion_parameters() -> None:
    configured = Settings(
        hybrid_rrf_k=20,
        hybrid_text_weight=2.0,
        hybrid_semantic_weight=0.5,
        hybrid_top_k_default=5,
        hybrid_top_k_max=20,
        hybrid_candidate_multiplier=4,
    )
    assert configured.hybrid_rrf_k == 20
    with pytest.raises(ValidationError):
        HybridSearchRequest(query="sintético", text_weight=2.0)  # type: ignore[call-arg]


def test_hybrid_request_validation_and_unicode() -> None:
    assert HybridSearchRequest(query="acción procesal").query == "acción procesal"
    for payload in (
        {"query": " "},
        {"query": "texto\x00"},
        {"query": "x", "top_k": 0},
        {"query": "x", "top_k": True},
        {"query": "x", "min_page": 2, "max_page": 1},
    ):
        with pytest.raises(ValidationError):
            HybridSearchRequest(**payload)


def test_rrf_fuses_deduplicates_and_preserves_source_traceability(monkeypatch) -> None:
    first, second, third = (_active(uuid4(), index=index) for index in (1, 2, 3))
    monkeypatch.setattr(hybrid_module.settings, "hybrid_rrf_k", 60)
    monkeypatch.setattr(hybrid_module.settings, "hybrid_text_weight", 1.0)
    monkeypatch.setattr(hybrid_module.settings, "hybrid_semantic_weight", 1.0)
    response, text_service, semantic_service = _run_search(
        HybridSearchRequest(query="sintético", top_k=3),
        [_text(first), _text(second, -2.0)],
        [_semantic(first), _semantic(third, 0.3)],
        [first, second, third],
    )
    assert [item.chunk_id for item in response.items] == [first.chunk_id, second.chunk_id, third.chunk_id]
    fused = response.items[0]
    assert fused.hybrid_score == pytest.approx(2 / 61)
    assert fused.appeared_in_text and fused.appeared_in_semantic
    assert fused.text_rank == 1 and fused.semantic_rank == 1
    assert response.items[1].appeared_in_text and not response.items[1].appeared_in_semantic
    assert response.items[2].rank_bm25 is None
    assert text_service.requests[0].page_size == 9
    assert semantic_service.requests[0].top_k == 9


def test_rrf_uses_weights_and_not_raw_scores(monkeypatch) -> None:
    chunk = _active(uuid4(), text="Contenido independiente")
    monkeypatch.setattr(hybrid_module.settings, "hybrid_rrf_k", 10)
    monkeypatch.setattr(hybrid_module.settings, "hybrid_text_weight", 2.0)
    monkeypatch.setattr(hybrid_module.settings, "hybrid_semantic_weight", 0.5)
    response, _, _ = _run_search(
        HybridSearchRequest(query="x", top_k=1),
        [_text(chunk, -999.0)],
        [_semantic(chunk, 0.999)],
        [chunk],
    )
    assert response.items[0].hybrid_score == pytest.approx(2.5 / 11)


def test_candidate_limit_is_bounded_and_both_empty() -> None:
    assert HybridSearchService._candidate_limit(1) == 3
    assert HybridSearchService._candidate_limit(50) == 50
    response, _, _ = _run_search(HybridSearchRequest(query="x"), [], [], [])
    assert response.items == [] and response.returned == 0


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_hybrid_rejects_nonfinite_source_scores(bad_value: float) -> None:
    chunk = _active(uuid4())
    text_items = [_text(chunk, bad_value)]
    semantic_items: list[SemanticSearchItem] = []
    if bad_value == -math.inf:
        text_items = []
        semantic_items = [_semantic(chunk, bad_value)]
    with pytest.raises(HybridSearchError, match="HYBRID_OUTPUT_INVALID"):
        _run_search(HybridSearchRequest(query="x"), text_items, semantic_items, [chunk])


def test_hybrid_keeps_first_duplicate_without_double_contribution() -> None:
    chunk = _active(uuid4())
    response, _, _ = _run_search(
        HybridSearchRequest(query="x"),
        [_text(chunk, -1.0), _text(chunk, -99.0)],
        [],
        [chunk],
    )
    assert response.returned == 1
    assert response.items[0].text_rank == 1
    assert response.items[0].rank_bm25 == -1.0
    assert response.items[0].hybrid_score == pytest.approx(1 / 61)


@pytest.mark.parametrize(
    ("text_rank", "semantic_rank", "rrf_k", "text_weight", "semantic_weight", "expected"),
    [
        (1, None, 60, 1.0, 1.0, 1 / 61),
        (None, 1, 60, 1.0, 1.0, 1 / 61),
        (1, 1, 60, 1.0, 1.0, 2 / 61),
        (2, 4, 60, 2.0, 0.5, 2 / 62 + 0.5 / 64),
        (3, 7, 1000, 1.0, 1.0, 1 / 1003 + 1 / 1007),
    ],
)
def test_rrf_numeric_formula_for_source_presence_weights_and_ranks(
    monkeypatch,
    text_rank,
    semantic_rank,
    rrf_k,
    text_weight,
    semantic_weight,
    expected,
) -> None:
    chunk = _active(uuid4())
    monkeypatch.setattr(hybrid_module.settings, "hybrid_rrf_k", rrf_k)
    monkeypatch.setattr(hybrid_module.settings, "hybrid_text_weight", text_weight)
    monkeypatch.setattr(hybrid_module.settings, "hybrid_semantic_weight", semantic_weight)
    text_items = [_text(_active(uuid4(), index=9)) for _ in range((text_rank or 1) - 1)]
    semantic_items = [
        _semantic(_active(uuid4(), index=10)) for _ in range((semantic_rank or 1) - 1)
    ]
    if text_rank is not None:
        text_items.append(_text(chunk, -500.0))
    if semantic_rank is not None:
        semantic_items.append(_semantic(chunk, 0.999))
    fused = HybridSearchService._fuse(text_items, semantic_items)[chunk.chunk_id]
    assert fused.text_rank == text_rank
    assert fused.semantic_rank == semantic_rank
    assert fused.hybrid_score == pytest.approx(expected, rel=1e-12)


def test_rrf_ignores_raw_score_changes_when_ranks_are_unchanged() -> None:
    chunk = _active(uuid4())
    first = HybridSearchService._fuse([_text(chunk, -1.0)], [_semantic(chunk, 0.1)])
    second = HybridSearchService._fuse([_text(chunk, -999.0)], [_semantic(chunk, 0.99)])
    assert first[chunk.chunk_id].hybrid_score == second[chunk.chunk_id].hybrid_score


def test_hybrid_source_failures_never_fallback() -> None:
    class FailingText(FakeTextService):
        async def search(self, request, *, request_id=None):
            self.requests.append(request)
            raise TextSearchRepositoryError("FTS5_NOT_AVAILABLE")

    class FailingSemantic(FakeSemanticService):
        async def search(self, request, *, request_id=None):
            self.requests.append(request)
            raise SemanticServiceError("SEMANTIC_INDEX_NOT_READY")

    semantic_would_respond = FakeSemanticService([])
    text_failure = HybridSearchService(
        object(),  # type: ignore[arg-type]
        text_service=FailingText([]),  # type: ignore[arg-type]
        semantic_service=semantic_would_respond,  # type: ignore[arg-type]
        repository=FakeRepository([]),  # type: ignore[arg-type]
    )
    with pytest.raises(TextSearchRepositoryError, match="FTS5_NOT_AVAILABLE"):
        asyncio.run(text_failure.search(HybridSearchRequest(query="x")))
    assert semantic_would_respond.requests == []

    text_responds = FakeTextService([])
    semantic_failure = HybridSearchService(
        object(),  # type: ignore[arg-type]
        text_service=text_responds,  # type: ignore[arg-type]
        semantic_service=FailingSemantic([]),  # type: ignore[arg-type]
        repository=FakeRepository([]),  # type: ignore[arg-type]
    )
    with pytest.raises(SemanticServiceError, match="SEMANTIC_INDEX_NOT_READY"):
        asyncio.run(semantic_failure.search(HybridSearchRequest(query="x")))
    assert len(text_responds.requests) == 1


def test_one_empty_successful_source_is_not_fallback() -> None:
    chunk = _active(uuid4())
    text_only, _, _ = _run_search(
        HybridSearchRequest(query="x"), [_text(chunk)], [], [chunk]
    )
    semantic_only, _, _ = _run_search(
        HybridSearchRequest(query="x"), [], [_semantic(chunk)], [chunk]
    )
    assert text_only.items[0].appeared_in_text
    assert not text_only.items[0].appeared_in_semantic
    assert semantic_only.items[0].text_rank is None
    assert semantic_only.items[0].distance_cosine is not None


def test_candidate_limit_resolves_all_internal_maxima(monkeypatch) -> None:
    monkeypatch.setattr(hybrid_module.settings, "hybrid_candidate_multiplier", 10)
    monkeypatch.setattr(hybrid_module.settings, "hybrid_top_k_max", 50)
    monkeypatch.setattr(hybrid_module.settings, "text_search_max_page_size", 17)
    monkeypatch.setattr(hybrid_module.settings, "semantic_search_top_k_max", 13)
    assert HybridSearchService._candidate_limit(1) == 10
    assert HybridSearchService._candidate_limit(10) == 13
    assert HybridSearchService._candidate_limit(50) == 13


def test_identical_filters_are_forwarded_to_both_sources() -> None:
    chunk = _active(uuid4(), index=2)
    request = HybridSearchRequest(
        query="x",
        text_match_mode="phrase",
        document_id=chunk.document_id,
        document_types=[DocumentType.JURISPRUDENCIA, DocumentType.NORMATIVA],
        min_page=2,
        max_page=3,
    )
    _, text_service, semantic_service = _run_search(request, [], [], [])
    textual = text_service.requests[0]
    semantic = semantic_service.requests[0]
    assert textual.match_mode.value == "phrase"
    for field in ("document_id", "document_types", "min_page", "max_page"):
        assert getattr(textual, field) == getattr(semantic, field) == getattr(request, field)


def test_stable_sort_uses_both_best_rank_and_identifiers() -> None:
    first = _active(UUID(int=11), index=1)
    second = _active(UUID(int=12), index=2)
    both = _CombinedCandidate(text_rank=2, semantic_rank=2, hybrid_score=0.5)
    single_better_rank = _CombinedCandidate(text_rank=1, hybrid_score=0.5)
    ordered = sorted(
        [(single_better_rank, second), (both, first)],
        key=HybridSearchService._sort_key,
    )
    assert ordered[0][1] == first

    tied_a = _CombinedCandidate(text_rank=1, hybrid_score=0.5)
    tied_b = _CombinedCandidate(semantic_rank=1, hybrid_score=0.5)
    ordered_tie = sorted(
        [(tied_b, second), (tied_a, first)],
        key=HybridSearchService._sort_key,
    )
    assert ordered_tie[0][1] == first

    document_id = uuid4()
    by_chunk_index = [
        ActiveChunk(UUID(int=31), document_id, DocumentType.OTRO, 2, "x", 1, 1),
        ActiveChunk(UUID(int=32), document_id, DocumentType.OTRO, 1, "x", 1, 1),
    ]
    same = _CombinedCandidate(text_rank=1, hybrid_score=0.5)
    ordered_index = sorted(
        [(same, chunk) for chunk in by_chunk_index],
        key=HybridSearchService._sort_key,
    )
    assert ordered_index[0][1].chunk_index == 1

    by_chunk_id = [
        ActiveChunk(UUID(int=42), document_id, DocumentType.OTRO, 1, "x", 1, 1),
        ActiveChunk(UUID(int=41), document_id, DocumentType.OTRO, 1, "x", 1, 1),
    ]
    ordered_id = sorted(
        [(same, chunk) for chunk in by_chunk_id],
        key=HybridSearchService._sort_key,
    )
    assert ordered_id[0][1].chunk_id == UUID(int=41)


def test_hybrid_numeric_response_fields_reject_booleans_and_nonfinite() -> None:
    chunk = _active(uuid4())
    base = dict(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_type=chunk.document_type,
        chunk_index=1,
        start_page=1,
        end_page=1,
        snippet="x",
        hybrid_score=0.1,
        appeared_in_text=True,
        appeared_in_semantic=False,
        text_rank=1,
        rank_bm25=-1.0,
    )
    for update in (
        {"text_rank": True},
        {"hybrid_score": True},
        {"hybrid_score": math.nan},
        {"rank_bm25": math.inf},
        {"distance_cosine": -math.inf},
    ):
        with pytest.raises(ValidationError):
            HybridSearchItem(**{**base, **update})


def test_hybrid_response_schema_rejects_invalid_identity_trace_and_counts() -> None:
    chunk = _active(uuid4())
    valid = HybridSearchItem(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_type=chunk.document_type,
        chunk_index=1,
        start_page=1,
        end_page=1,
        snippet="x",
        hybrid_score=0.1,
        appeared_in_text=True,
        appeared_in_semantic=False,
        text_rank=1,
        rank_bm25=-1.0,
    )
    with pytest.raises(ValidationError):
        HybridSearchItem(**valid.model_dump(exclude={"chunk_id"}), chunk_id="invalid")
    with pytest.raises(ValidationError, match="HYBRID_TEXT_TRACE_INVALID"):
        HybridSearchItem(**valid.model_dump(exclude={"text_rank"}), text_rank=None)
    with pytest.raises(ValidationError, match="HYBRID_RESPONSE_COUNT_INVALID"):
        HybridSearchResponse(items=[valid], returned=0, top_k=1)
    with pytest.raises(ValidationError):
        HybridSearchResponse(items=[valid], returned=1, top_k=0)


def test_phase7_validator_privacy_checks_keys_without_content_false_positives() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "validate_phase7_end_to_end.py"
    namespace = runpy.run_path(str(script), run_name="phase7_validator_audit")
    contains_forbidden = namespace["_contains_forbidden_key"]
    assert not contains_forbidden(
        {"items": [{"snippet": "texto con vector y collection como palabras"}]}
    )
    assert contains_forbidden({"items": [], "query": "prohibida"})
    assert contains_forbidden({"items": [{"embedding_vector": [0.0]}]})


def test_final_sqlite_validation_discards_stale_and_reapplies_filters() -> None:
    valid = _active(uuid4(), index=1)
    stale = _active(uuid4(), index=2)
    wrong_metadata = _text(stale).model_copy(update={"start_page": 99})
    response, _, _ = _run_search(
        HybridSearchRequest(
            query="x",
            document_types=[DocumentType.JURISPRUDENCIA],
            min_page=1,
            max_page=1,
        ),
        [_text(valid), wrong_metadata],
        [_semantic(valid)],
        [valid, stale],
    )
    assert [item.chunk_id for item in response.items] == [valid.chunk_id]


def test_hybrid_search_does_not_reintroduce_governance_excluded_chunk() -> None:
    base = _active(UUID(int=801))
    excluded = ActiveChunk(
        chunk_id=base.chunk_id,
        document_id=base.document_id,
        document_type=base.document_type,
        chunk_index=base.chunk_index,
        text=base.text,
        start_page=base.start_page,
        end_page=base.end_page,
        governance=DocumentGovernanceSnapshot(
            review_status=ReviewStatus.REJECTED,
        ),
    )
    response, _, _ = _run_search(
        HybridSearchRequest(query="consulta"),
        [_text(excluded)],
        [_semantic(excluded)],
        [excluded],
    )

    assert response.items == []
    assert response.returned == 0


def test_hybrid_layer_filter_is_deduplicated_and_forwarded() -> None:
    chunk = _active(UUID(int=802))
    request = HybridSearchRequest(
        query="consulta",
        knowledge_layers=[
            KnowledgeLayer.PRIVATE_LIBRARY,
            KnowledgeLayer.PRIVATE_LIBRARY,
        ],
    )
    response, text_service, semantic_service = _run_search(
        request,
        [_text(chunk)],
        [_semantic(chunk)],
        [chunk],
    )

    assert response.returned == 1
    assert request.knowledge_layers == [KnowledgeLayer.PRIVATE_LIBRARY]
    assert text_service.requests[0].knowledge_layers == request.knowledge_layers
    assert semantic_service.requests[0].knowledge_layers == request.knowledge_layers


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("document_id", UUID(int=99)),
        ("document_type", DocumentType.NORMATIVA),
        ("chunk_index", 99),
        ("start_page", 99),
        ("end_page", 99),
    ],
)
def test_final_sqlite_validation_discards_every_metadata_mismatch(field, value) -> None:
    chunk = _active(uuid4())
    stale = _text(chunk).model_copy(update={field: value})
    response, _, _ = _run_search(
        HybridSearchRequest(query="x"), [stale], [], [chunk]
    )
    assert response.items == []


def test_final_snippet_comes_from_sqlite_and_escapes_html() -> None:
    chunk = _active(uuid4(), text="<script>alert(1)</script> acción")
    response, _, _ = _run_search(
        HybridSearchRequest(query="x"), [_text(chunk)], [], [chunk]
    )
    assert "<script>" not in response.items[0].snippet
    assert "&lt;script&gt;" in response.items[0].snippet
    assert "acción" in response.items[0].snippet


def test_hybrid_logs_only_operational_metadata(caplog, monkeypatch) -> None:
    marker = "MARCADOR_PRIVADO_HYBRID"
    chunk = _active(uuid4(), text="SNIPPET_PRIVADO")

    def capture(message: str, **context) -> None:
        logging.getLogger("hybrid_audit").info("%s %s", message, context)

    monkeypatch.setattr(hybrid_module, "log_info", capture)
    monkeypatch.setattr(hybrid_module, "log_success", capture)
    with caplog.at_level(logging.INFO, logger="hybrid_audit"):
        _run_search(HybridSearchRequest(query=marker), [_text(chunk)], [], [chunk])
    assert marker not in caplog.text
    assert "SNIPPET_PRIVADO" not in caplog.text
    assert str(chunk.chunk_id) not in caplog.text
    assert "hybrid_score" not in caplog.text
    assert "query_length" in caplog.text


def test_hybrid_api_success_empty_validation_and_privacy(tmp_path, monkeypatch) -> None:
    manager = DatabaseSessionManager(tmp_path / "hybrid.db")
    chunk = _active(uuid4(), text="Contenido independiente")
    original_search = HybridSearchService.search

    async def override_session():
        async with manager.get_session_factory()() as session:
            yield session

    async def fake_search(_self, request, *, request_id=None):
        if request.query == "empty":
            return HybridSearchResponse(items=[], returned=0, top_k=request.top_k)
        service = HybridSearchService(
            object(),  # type: ignore[arg-type]
            text_service=FakeTextService([_text(chunk)]),  # type: ignore[arg-type]
            semantic_service=FakeSemanticService([_semantic(chunk)]),  # type: ignore[arg-type]
            repository=FakeRepository([chunk]),  # type: ignore[arg-type]
        )
        return await original_search(service, request, request_id=request_id)

    monkeypatch.setattr(HybridSearchService, "search", fake_search)
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            found = client.post("/api/search/hybrid", json={"query": "sintético"})
            empty = client.post("/api/search/hybrid", json={"query": "empty"})
            invalid = client.post("/api/search/hybrid", json={"query": " "})
        assert found.status_code == 200 and found.json()["returned"] == 1
        assert empty.status_code == 200 and empty.json()["items"] == []
        assert invalid.status_code == 422
        serialized = found.text.lower()
        for forbidden in ("sintético", "embedding", "vector", "relative_path", "collection"):
            assert forbidden not in serialized
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        asyncio.run(manager.dispose())


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (TextSearchRepositoryError("FTS5_NOT_AVAILABLE"), 503),
        (TextSearchRepositoryError("TEXT_SEARCH_INDEX_NOT_READY"), 503),
        (SemanticServiceError("CHROMA_DEPENDENCY_MISSING"), 503),
        (SemanticServiceError("SEMANTIC_INDEX_NOT_READY"), 503),
        (SemanticServiceError("SEMANTIC_INDEX_INCOMPATIBLE"), 503),
        (SemanticServiceError("SEMANTIC_INDEX_REBUILD_REQUIRED"), 503),
        (SemanticServiceError("EMBEDDING_MODEL_NOT_LOADED"), 503),
        (HybridSearchError("HYBRID_SEARCH_ERROR"), 500),
        (HybridSearchError("HYBRID_OUTPUT_INVALID"), 500),
    ],
)
def test_hybrid_api_maps_controlled_errors(tmp_path, monkeypatch, error, status) -> None:
    manager = DatabaseSessionManager(tmp_path / "errors.db")

    async def override_session():
        async with manager.get_session_factory()() as session:
            yield session

    async def fail(_self, _request, *, request_id=None):
        raise error

    monkeypatch.setattr(HybridSearchService, "search", fail)
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post("/api/search/hybrid", json={"query": "privado"})
        assert response.status_code == status
        assert response.json() == {"detail": str(error)}
        assert "privado" not in response.text
        assert "traceback" not in response.text.lower()
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        asyncio.run(manager.dispose())
