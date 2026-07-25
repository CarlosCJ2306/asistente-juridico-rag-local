"""Pruebas aisladas de índice y búsqueda semántica sin modelos ni datos reales."""

from __future__ import annotations

import asyncio
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core import paths
from app.core.config import Settings
from app.database.base import Base
from app.database.models.document import Document, DocumentStatus, DocumentType
from app.database.models.document_chunk import DocumentChunk
from app.database.repositories.semantic_chunk_repository import ActiveChunk
from app.database.session import DatabaseSessionManager, get_db_session
from app.main import app
from app.schemas.semantic_search import (
    SemanticRebuildResponse,
    SemanticSearchItem,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticStatusResponse,
)
from app.services import semantic_index_service as index_module
from app.services import semantic_search_service as search_module
from app.services.semantic_index_service import SemanticIndexService, SemanticServiceError
from app.services.semantic_search_service import SemanticSearchService
from app.vector_store.chroma_store import ChromaStore, ChromaStoreError, VectorCandidate
from app.vector_store import semantic_index_state as state_module
from app.vector_store.semantic_index_state import (
    SemanticIndexState,
    SemanticStateError,
    SemanticStateStore,
)


class FakeEmbeddingModel:
    def __init__(self, *, loaded: bool = True, dimension: int = 3) -> None:
        self.is_loaded = loaded
        self.dimension = dimension if loaded else None
        self.encoded: list[list[str]] = []

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.encoded.append(list(texts))
        vectors = []
        for text in texts:
            lowered = text.lower()
            if "segundo" in lowered:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([1.0, 0.0, 0.0])
        return vectors


class FakeChromaStore:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.collections: dict[str, dict[str, object]] = {}
        self.fail_create_after_write = False
        self.fail_add_on_call: int | None = None
        self.add_calls = 0
        self.count_delta = 0
        self.fail_delete_names: set[str] = set()
        self.fail_all_deletes = False
        self.delete_attempts: list[str] = []
        self.last_query: dict[str, object] | None = None
        self.extra_candidates: list[VectorCandidate] = []

    def dependency_available(self) -> bool:
        return self.available

    def create_collection(
        self,
        name: str,
        *,
        schema_version: int,
        embedding_model: str,
        embedding_dimension: int,
    ) -> None:
        self.collections[name] = {
            "metadata": {
                "hnsw:space": "cosine",
                "semantic_schema_version": schema_version,
                "embedding_model": embedding_model,
                "embedding_dimension": embedding_dimension,
            },
            "rows": {},
        }
        if self.fail_create_after_write:
            raise ChromaStoreError("SEMANTIC_INDEX_BUILD_ERROR")

    def add(self, name: str, *, ids, embeddings, metadatas) -> None:
        self.add_calls += 1
        if self.fail_add_on_call == self.add_calls:
            raise ChromaStoreError("SEMANTIC_INDEX_BUILD_ERROR")
        rows = self.collections[name]["rows"]
        assert isinstance(rows, dict)
        for chunk_id, vector, metadata in zip(ids, embeddings, metadatas, strict=True):
            rows[chunk_id] = (list(vector), dict(metadata))

    def count(self, name: str) -> int:
        try:
            rows = self.collections[name]["rows"]
        except KeyError as exc:
            raise ChromaStoreError("SEMANTIC_INDEX_NOT_READY") from exc
        assert isinstance(rows, dict)
        return len(rows) + self.count_delta

    def metadata(self, name: str) -> dict[str, object]:
        try:
            metadata = self.collections[name]["metadata"]
        except KeyError as exc:
            raise ChromaStoreError("SEMANTIC_INDEX_NOT_READY") from exc
        assert isinstance(metadata, dict)
        return dict(metadata)

    def query(
        self,
        name: str,
        *,
        query_embedding,
        limit: int,
        where: dict[str, object] | None,
    ) -> list[VectorCandidate]:
        self.last_query = {
            "query_embedding": list(query_embedding),
            "limit": limit,
            "where": where,
        }
        rows = self.collections[name]["rows"]
        assert isinstance(rows, dict)
        candidates = []
        for chunk_id, (vector, metadata) in rows.items():
            if not self._matches(metadata, where):
                continue
            dot = sum(a * b for a, b in zip(query_embedding, vector, strict=True))
            candidates.append(
                VectorCandidate(
                    chunk_id=chunk_id,
                    metadata=dict(metadata),
                    distance=1.0 - dot,
                )
            )
        candidates.extend(self.extra_candidates)
        return sorted(candidates, key=lambda item: item.distance)[:limit]

    def delete_collection(self, name: str) -> None:
        self.delete_attempts.append(name)
        if self.fail_all_deletes or name in self.fail_delete_names:
            raise ChromaStoreError("SEMANTIC_INDEX_BUILD_ERROR")
        self.collections.pop(name, None)

    @classmethod
    def _matches(cls, metadata: dict[str, object], where: dict[str, object] | None) -> bool:
        if where is None:
            return True
        if "$and" in where:
            clauses = where["$and"]
            assert isinstance(clauses, list)
            return all(cls._matches(metadata, clause) for clause in clauses)
        for key, expected in where.items():
            current = metadata.get(key)
            if isinstance(expected, dict):
                if "$in" in expected and current not in expected["$in"]:
                    return False
                if "$gte" in expected and (not isinstance(current, int) or current < expected["$gte"]):
                    return False
                if "$lte" in expected and (not isinstance(current, int) or current > expected["$lte"]):
                    return False
            elif current != expected:
                return False
        return True


class FailingStateStore(SemanticStateStore):
    def write_atomic(self, state: SemanticIndexState) -> None:
        del state
        raise SemanticStateError("SEMANTIC_INDEX_BUILD_ERROR")


def _document(document_type: DocumentType, *, deleted: bool = False) -> Document:
    identifier = uuid4()
    return Document(
        id=identifier,
        original_filename="synthetic.pdf",
        stored_filename=f"{identifier}.pdf",
        relative_path=f"storage/documents/otro/{identifier}.pdf",
        document_type=document_type,
        mime_type="application/pdf",
        extension=".pdf",
        size_bytes=10,
        sha256=identifier.hex * 2,
        status=DocumentStatus.EXTRACTED,
        is_deleted=deleted,
    )


async def _semantic_database(tmp_path: Path):
    manager = DatabaseSessionManager(tmp_path / "semantic.db")
    async with manager.get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with manager.get_session_factory()() as session:
        first = _document(DocumentType.JURISPRUDENCIA)
        second = _document(DocumentType.NORMATIVA)
        deleted = _document(DocumentType.OTRO, deleted=True)
        session.add_all([first, second, deleted])
        await session.flush()
        chunks = [
            DocumentChunk(
                document_id=first.id,
                chunk_index=1,
                text="Primero <script>alert(1)</script> acción con Unicode " + "x" * 600,
                char_count=650,
                word_count=7,
                start_page=1,
                end_page=2,
            ),
            DocumentChunk(
                document_id=second.id,
                chunk_index=1,
                text="Segundo fragmento sintético",
                char_count=27,
                word_count=3,
                start_page=3,
                end_page=4,
            ),
            DocumentChunk(
                document_id=deleted.id,
                chunk_index=1,
                text="Contenido excluido",
                char_count=18,
                word_count=2,
                start_page=1,
                end_page=1,
            ),
        ]
        session.add_all(chunks)
        await session.commit()
        identifiers = (first.id, second.id, chunks[0].id, chunks[1].id)
    return manager, identifiers


def _run(coroutine):
    return asyncio.run(coroutine)


def test_semantic_settings_paths_limits_and_no_import_side_effect(tmp_path: Path, monkeypatch) -> None:
    expected = paths.STORAGE_DIR / "vector" / "chroma"
    assert Settings(_env_file=None).chroma_persist_path == expected.resolve()
    assert not (tmp_path / "vector").exists()
    for invalid in ("../outside", str(tmp_path.resolve())):
        with pytest.raises(ValueError, match="VECTOR_STORE_PATH_INVALID"):
            Settings(_env_file=None, chroma_persist_path=invalid)
    with pytest.raises(ValueError):
        Settings(_env_file=None, semantic_index_batch_size=0)
    with pytest.raises(ValueError, match="SEMANTIC_COLLECTION_PREFIX_INVALID"):
        Settings(_env_file=None, semantic_collection_prefix="índice")
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            semantic_search_top_k_default=20,
            semantic_search_top_k_max=10,
        )

    allowed = tmp_path / "storage" / "vector"
    outside = tmp_path / "outside"
    allowed.mkdir(parents=True)
    outside.mkdir()
    link = allowed / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        return
    monkeypatch.setattr(paths, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(paths, "VECTOR_DIR", allowed)
    with pytest.raises(ValueError, match="VECTOR_STORE_PATH_INVALID"):
        paths.resolve_vector_path("storage/vector/escape/chroma", expected_directory=True)


def test_application_import_and_status_do_not_create_vector_storage(
    tmp_path: Path, monkeypatch
) -> None:
    vector_root = tmp_path / "storage" / "vector"
    script = (
        "from pathlib import Path\n"
        "import app.core.paths as paths\n"
        f"root = Path({str(tmp_path)!r})\n"
        "paths.PROJECT_ROOT = root\n"
        "paths.EMBEDDINGS_MODELS_DIR = root / 'models' / 'embeddings'\n"
        "paths.VECTOR_DIR = root / 'storage' / 'vector'\n"
        "from app.main import app\n"
        "assert app is not None\n"
        "assert not paths.VECTOR_DIR.exists()\n"
    )
    environment = os.environ.copy()
    environment.update({"LOG_TO_FILE": "false", "LOG_CONSOLE": "false"})
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert not vector_root.exists()

    manager = _run(_semantic_database(tmp_path))[0]

    async def override_session():
        async with manager.get_session_factory()() as session:
            yield session

    monkeypatch.setattr(index_module.settings, "chroma_persist_path", vector_root / "chroma")
    monkeypatch.setattr(
        index_module.settings,
        "semantic_index_state_file",
        vector_root / "semantic_index_state.json",
    )
    monkeypatch.setattr(ChromaStore, "dependency_available", staticmethod(lambda: False))
    monkeypatch.setattr(
        sys.modules["app.vector_store.semantic_index_state"], "VECTOR_DIR", vector_root
    )
    monkeypatch.setattr(sys.modules["app.vector_store.chroma_store"], "VECTOR_DIR", vector_root)
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.get("/api/search/semantic/status")
        assert response.status_code == 200
        assert response.json()["state"] == "unavailable"
        assert not vector_root.exists()
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        _run(manager.dispose())


def test_chroma_import_is_lazy_and_adapter_has_no_remote_or_documents() -> None:
    source = (Path(__file__).parents[1] / "app" / "vector_store" / "chroma_store.py").read_text(
        encoding="utf-8"
    )
    assert "chromadb" not in sys.modules
    assert "PersistentClient" in source
    assert "anonymized_telemetry=False" in source
    assert "HttpClient" not in source
    assert "documents=" not in source
    assert "embedding_function=None" in source
    with pytest.raises(ChromaStoreError, match="VECTOR_STORE_PATH_INVALID"):
        ChromaStore(Path.cwd())._validate_persist_path()
    with pytest.raises(ChromaStoreError, match="SEMANTIC_INDEX_STATE_INVALID"):
        ChromaStore().delete_collection("foreign_collection")


def test_chroma_adapter_rejects_invalid_insert_and_misaligned_query_arrays(
    tmp_path: Path, monkeypatch
) -> None:
    store = ChromaStore(tmp_path, enforce_authorized_path=False)
    name = f"legal_chunks_{uuid4().hex}"
    allowed_metadata: dict[str, str | int] = {
        "document_id": str(uuid4()),
        "document_type": "jurisprudencia",
        "chunk_index": 1,
        "start_page": 1,
        "end_page": 2,
    }
    assert store._valid_metadata(allowed_metadata)
    assert not store._valid_metadata({**allowed_metadata, "text": "forbidden"})
    assert not store._valid_metadata({**allowed_metadata, "end_page": 0})
    for ids, embeddings, metadatas in (
        ([], [], []),
        (["a", "a"], [[1.0], [1.0]], [{}, {}]),
        (["a"], [[]], [{}]),
        (["a"], [[float("nan")]], [{}]),
        (["a"], [[1.0]], []),
    ):
        with pytest.raises(ChromaStoreError, match="SEMANTIC_OUTPUT_INVALID"):
            store.add(name, ids=ids, embeddings=embeddings, metadatas=metadatas)

    class FakeCollection:
        def query(self, **_kwargs):
            return {
                "ids": [[str(uuid4())]],
                "metadatas": [[]],
                "distances": [[0.1]],
            }

    class FakeClient:
        def get_collection(self, **_kwargs):
            return FakeCollection()

    monkeypatch.setattr(store, "_require_existing_store", lambda **_kwargs: None)
    monkeypatch.setattr(store, "_client", lambda: FakeClient())
    with pytest.raises(ChromaStoreError, match="SEMANTIC_OUTPUT_INVALID"):
        store.query(name, query_embedding=[1.0], limit=1, where=None)

    for vectors, expected_count in (([], 1), ([[]], 1), ([[1.0, 2.0]], 1), ([[1.0]], 2)):
        with pytest.raises(SemanticServiceError, match="SEMANTIC_OUTPUT_INVALID"):
            SemanticIndexService._validate_vectors(
                vectors, dimension=1, expected_count=expected_count
            )


def test_semantic_state_is_atomic_minimal_and_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "vector" / "state.json"
    store = SemanticStateStore(path)
    assert store.read() is None and not path.parent.exists()
    state = SemanticIndexState(
        schema_version=1,
        active_collection=f"legal_chunks_{uuid4().hex}",
        embedding_model="intfloat/multilingual-e5-small",
        embedding_dimension=384,
        distance_metric="cosine",
        indexed_chunks=2,
        created_at="2026-07-24T00:00:00+00:00",
        source_fingerprint="0" * 64,
    )
    store.write_atomic(state)
    assert store.read() == state
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert set(raw) == {
        "schema_version", "active_collection", "embedding_model",
        "embedding_dimension", "distance_metric", "indexed_chunks", "created_at",
        "source_fingerprint",
    }
    assert not list(path.parent.glob("*.tmp"))
    path.write_text("{", encoding="utf-8")
    with pytest.raises(SemanticStateError, match="SEMANTIC_INDEX_STATE_INVALID"):
        store.read()


def test_semantic_state_rejects_unknown_collection_and_incompatible_values(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "active_collection": "unknown_collection",
                "embedding_model": "intfloat/multilingual-e5-small",
                "embedding_dimension": 3,
                "distance_metric": "cosine",
                "indexed_chunks": 0,
                "created_at": "now",
                "source_fingerprint": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SemanticStateError, match="SEMANTIC_INDEX_STATE_INVALID"):
        SemanticStateStore(path).read()
    with pytest.raises(SemanticStateError, match="VECTOR_STORE_PATH_INVALID"):
        SemanticStateStore(path, enforce_authorized_path=True).read()


@pytest.mark.parametrize(
    ("change", "value"),
    [
        ("missing", "embedding_model"),
        ("extra", "document_text"),
        ("schema_version", 0),
        ("embedding_model", ""),
        ("embedding_dimension", 0),
        ("embedding_dimension", "3"),
        ("distance_metric", "l2"),
        ("indexed_chunks", -1),
        ("indexed_chunks", True),
        ("created_at", "2026-07-24"),
        ("created_at", "not-a-timestamp"),
        ("source_fingerprint", "invalid"),
    ],
)
def test_semantic_state_rejects_missing_extra_and_invalid_fields(
    tmp_path: Path, change: str, value: object
) -> None:
    raw: dict[str, object] = {
        "schema_version": 1,
        "active_collection": f"legal_chunks_{uuid4().hex}",
        "embedding_model": "intfloat/multilingual-e5-small",
        "embedding_dimension": 3,
        "distance_metric": "cosine",
        "indexed_chunks": 2,
        "created_at": "2026-07-24T00:00:00+00:00",
        "source_fingerprint": "0" * 64,
    }
    if change == "missing":
        raw.pop(str(value))
    elif change == "extra":
        raw[str(value)] = "forbidden"
    else:
        raw[change] = value
    path = tmp_path / f"{change}.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SemanticStateError, match="SEMANTIC_INDEX_STATE_INVALID"):
        SemanticStateStore(path).read()


def test_semantic_state_rejects_empty_partial_and_atomic_replace_failure(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "state.json"
    store = SemanticStateStore(path)
    for content in ("", "{", "[]"):
        path.write_text(content, encoding="utf-8")
        with pytest.raises(SemanticStateError, match="SEMANTIC_INDEX_STATE_INVALID"):
            store.read()

    original = "original-state"
    path.write_text(original, encoding="utf-8")
    state = SemanticIndexState(
        schema_version=1,
        active_collection=f"legal_chunks_{uuid4().hex}",
        embedding_model="intfloat/multilingual-e5-small",
        embedding_dimension=3,
        distance_metric="cosine",
        indexed_chunks=0,
        created_at="2026-07-24T00:00:00+00:00",
        source_fingerprint="0" * 64,
    )

    def fail_replace(_source, _target) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(state_module.os, "replace", fail_replace)
    with pytest.raises(SemanticStateError, match="SEMANTIC_INDEX_BUILD_ERROR"):
        store.write_atomic(state)
    assert path.read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob("*.tmp"))


def test_semantic_rebuild_batches_excludes_deleted_and_activates_atomically(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(index_module.settings, "semantic_index_batch_size", 1)
    async def scenario() -> None:
        manager, identifiers = await _semantic_database(tmp_path)
        state_store = SemanticStateStore(tmp_path / "vector" / "state.json")
        store = FakeChromaStore()
        model = FakeEmbeddingModel()
        try:
            async with manager.get_session_factory()() as session:
                service = SemanticIndexService(
                    session, embedding_model=model, store=store, state_store=state_store
                )
                response = await service.rebuild()
                assert response.indexed_chunks == 2
                state = state_store.read()
                assert state is not None and store.count(state.active_collection) == 2
                rows = store.collections[state.active_collection]["rows"]
                assert isinstance(rows, dict)
                assert set(rows) == {str(identifiers[2]), str(identifiers[3])}
                assert all(
                    set(metadata) == {
                        "document_id",
                        "document_type",
                        "chunk_index",
                        "start_page",
                        "end_page",
                    }
                    for _, metadata in rows.values()
                )
                assert len(model.encoded) == 2 and all(
                    text.startswith("passage: ") for batch in model.encoded for text in batch
                )
                status = await service.status()
                assert status.state == "ready" and not status.needs_rebuild
        finally:
            await manager.dispose()

    _run(scenario())


@pytest.mark.parametrize(
    ("mutation", "needs_rebuild"),
    [
        ("none", False),
        ("text", True),
        ("pages", True),
        ("document_type", True),
        ("replace", True),
        ("delete_and_add", True),
    ],
)
def test_semantic_status_uses_source_fingerprint_with_unchanged_count(
    tmp_path: Path, mutation: str, needs_rebuild: bool
) -> None:
    async def scenario() -> None:
        manager, identifiers = await _semantic_database(tmp_path)
        store = FakeChromaStore()
        state_store = SemanticStateStore(tmp_path / "vector" / "state.json")
        try:
            async with manager.get_session_factory()() as session:
                service = SemanticIndexService(
                    session,
                    embedding_model=FakeEmbeddingModel(),
                    store=store,
                    state_store=state_store,
                )
                await service.rebuild()
                if mutation != "none":
                    chunk = await session.get(DocumentChunk, identifiers[2])
                    assert chunk is not None
                    if mutation == "text":
                        chunk.text = "Texto sintético reemplazado"
                    elif mutation == "pages":
                        chunk.start_page = 2
                        chunk.end_page = 3
                    elif mutation == "document_type":
                        document = await session.get(Document, identifiers[0])
                        assert document is not None
                        document.document_type = DocumentType.OTRO
                    elif mutation == "replace":
                        await session.delete(chunk)
                        await session.flush()
                        session.add(
                            DocumentChunk(
                                document_id=identifiers[0],
                                chunk_index=1,
                                text="Chunk sustituto",
                                char_count=16,
                                word_count=2,
                                start_page=1,
                                end_page=2,
                            )
                        )
                    elif mutation == "delete_and_add":
                        document = await session.get(Document, identifiers[0])
                        assert document is not None
                        document.is_deleted = True
                        replacement = _document(DocumentType.JURISPRUDENCIA)
                        session.add(replacement)
                        await session.flush()
                        session.add(
                            DocumentChunk(
                                document_id=replacement.id,
                                chunk_index=1,
                                text="Chunk compensatorio",
                                char_count=19,
                                word_count=2,
                                start_page=1,
                                end_page=2,
                            )
                        )
                    await session.commit()
                status = await service.status()
                assert status.active_chunks == 2
                assert status.needs_rebuild is needs_rebuild
        finally:
            await manager.dispose()

    _run(scenario())


def test_semantic_rebuild_failure_preserves_previous_index_and_removes_temporary(tmp_path: Path) -> None:
    async def scenario() -> None:
        manager, _ = await _semantic_database(tmp_path)
        state_store = SemanticStateStore(tmp_path / "vector" / "state.json")
        store = FakeChromaStore()
        old_name = f"legal_chunks_{uuid4().hex}"
        store.create_collection(
            old_name,
            schema_version=1,
            embedding_model="intfloat/multilingual-e5-small",
            embedding_dimension=3,
        )
        old_state = SemanticIndexState(
            schema_version=1,
            active_collection=old_name,
            embedding_model="intfloat/multilingual-e5-small",
            embedding_dimension=3,
            distance_metric="cosine",
            indexed_chunks=0,
            created_at="2026-07-24T00:00:00+00:00",
            source_fingerprint="0" * 64,
        )
        state_store.write_atomic(old_state)
        store.fail_add_on_call = 1
        try:
            async with manager.get_session_factory()() as session:
                service = SemanticIndexService(
                    session,
                    embedding_model=FakeEmbeddingModel(),
                    store=store,
                    state_store=state_store,
                )
                with pytest.raises(SemanticServiceError, match="SEMANTIC_INDEX_BUILD_ERROR"):
                    await service.rebuild()
                assert state_store.read() == old_state
                assert set(store.collections) == {old_name}
        finally:
            await manager.dispose()

    _run(scenario())


@pytest.mark.parametrize("failure", ["create", "second_batch", "count", "state_write"])
def test_semantic_rebuild_partial_failures_remove_only_temporary_and_release_lock(
    tmp_path: Path, monkeypatch, failure: str
) -> None:
    monkeypatch.setattr(index_module.settings, "semantic_index_batch_size", 1)

    async def scenario() -> None:
        manager, _ = await _semantic_database(tmp_path)
        path = tmp_path / "vector" / "state.json"
        store = FakeChromaStore()
        state_store: SemanticStateStore = SemanticStateStore(path)
        if failure == "create":
            store.fail_create_after_write = True
        elif failure == "second_batch":
            store.fail_add_on_call = 2
        elif failure == "count":
            store.count_delta = 1
        else:
            state_store = FailingStateStore(path)
        try:
            async with manager.get_session_factory()() as session:
                service = SemanticIndexService(
                    session,
                    embedding_model=FakeEmbeddingModel(),
                    store=store,
                    state_store=state_store,
                )
                with pytest.raises(SemanticServiceError):
                    await service.rebuild()
                assert not store.collections
                assert not path.exists()
                assert SemanticIndexService._rebuild_lock.acquire(blocking=False)
                SemanticIndexService._rebuild_lock.release()
        finally:
            await manager.dispose()

    _run(scenario())


def test_semantic_rebuild_cleanup_failures_preserve_safe_active_state(
    tmp_path: Path, monkeypatch
) -> None:
    warnings: list[dict[str, object]] = []

    def capture_warning(_message: str, **context: object) -> None:
        warnings.append(context)

    monkeypatch.setattr(index_module, "log_warning", capture_warning)
    async def scenario() -> None:
        manager, _ = await _semantic_database(tmp_path)
        path = tmp_path / "vector" / "state.json"
        base_state_store = SemanticStateStore(path)
        old_name = f"legal_chunks_{uuid4().hex}"
        old_state = SemanticIndexState(
            schema_version=1,
            active_collection=old_name,
            embedding_model="intfloat/multilingual-e5-small",
            embedding_dimension=3,
            distance_metric="cosine",
            indexed_chunks=0,
            created_at="2026-07-24T00:00:00+00:00",
            source_fingerprint="0" * 64,
        )
        base_state_store.write_atomic(old_state)
        try:
            async with manager.get_session_factory()() as session:
                failed_store = FakeChromaStore()
                failed_store.create_collection(
                    old_name,
                    schema_version=1,
                    embedding_model="intfloat/multilingual-e5-small",
                    embedding_dimension=3,
                )
                failed_store.fail_add_on_call = 1
                failed_store.fail_all_deletes = True
                failed_service = SemanticIndexService(
                    session,
                    embedding_model=FakeEmbeddingModel(),
                    store=failed_store,
                    state_store=base_state_store,
                )
                with pytest.raises(SemanticServiceError):
                    await failed_service.rebuild()
                assert base_state_store.read() == old_state
                assert old_name in failed_store.collections
                assert len(failed_store.collections) == 2

                successful_store = FakeChromaStore()
                successful_store.create_collection(
                    old_name,
                    schema_version=1,
                    embedding_model="intfloat/multilingual-e5-small",
                    embedding_dimension=3,
                )
                successful_store.fail_delete_names.add(old_name)
                successful_service = SemanticIndexService(
                    session,
                    embedding_model=FakeEmbeddingModel(),
                    store=successful_store,
                    state_store=base_state_store,
                )
                response = await successful_service.rebuild()
                new_state = base_state_store.read()
                assert response.state == "ready"
                assert new_state is not None
                assert new_state.active_collection != old_name
                assert old_name in successful_store.collections
                assert new_state.active_collection in successful_store.collections
        finally:
            await manager.dispose()

    _run(scenario())
    assert {item["error_code"] for item in warnings} == {
        "SEMANTIC_INDEX_TEMP_CLEANUP_ERROR",
        "SEMANTIC_INDEX_CLEANUP_ERROR",
    }


def test_semantic_rebuild_requires_dependency_model_and_rejects_concurrency(tmp_path: Path) -> None:
    async def scenario() -> None:
        manager, _ = await _semantic_database(tmp_path)
        try:
            async with manager.get_session_factory()() as session:
                missing = SemanticIndexService(
                    session,
                    embedding_model=FakeEmbeddingModel(),
                    store=FakeChromaStore(available=False),
                    state_store=SemanticStateStore(tmp_path / "missing.json"),
                )
                with pytest.raises(SemanticServiceError, match="CHROMA_DEPENDENCY_MISSING"):
                    await missing.rebuild()
                unloaded = SemanticIndexService(
                    session,
                    embedding_model=FakeEmbeddingModel(loaded=False),
                    store=FakeChromaStore(),
                    state_store=SemanticStateStore(tmp_path / "unloaded.json"),
                )
                with pytest.raises(SemanticServiceError, match="EMBEDDING_MODEL_NOT_LOADED"):
                    await unloaded.rebuild()
                assert SemanticIndexService._rebuild_lock.acquire(blocking=False)
                try:
                    with pytest.raises(SemanticServiceError, match="SEMANTIC_INDEX_BUSY"):
                        await missing.__class__(
                            session,
                            embedding_model=FakeEmbeddingModel(),
                            store=FakeChromaStore(),
                            state_store=SemanticStateStore(tmp_path / "busy.json"),
                        ).rebuild()
                finally:
                    SemanticIndexService._rebuild_lock.release()
        finally:
            await manager.dispose()

    _run(scenario())


def test_semantic_search_uses_previous_active_index_while_building(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        manager, _ = await _semantic_database(tmp_path)
        store = FakeChromaStore()
        state_store = SemanticStateStore(tmp_path / "vector" / "state.json")
        try:
            async with manager.get_session_factory()() as session:
                service = SemanticIndexService(
                    session,
                    embedding_model=FakeEmbeddingModel(),
                    store=store,
                    state_store=state_store,
                )
                await service.rebuild()
                type(service)._building = True
                try:
                    status = await service.status()
                    result = await SemanticSearchService(service).search(
                        SemanticSearchRequest(query="consulta sintética")
                    )
                    assert status.state == "building"
                    assert result.returned == 2

                    no_state = SemanticIndexService(
                        session,
                        embedding_model=FakeEmbeddingModel(),
                        store=FakeChromaStore(),
                        state_store=SemanticStateStore(tmp_path / "missing-state.json"),
                    )
                    with pytest.raises(
                        SemanticServiceError, match="SEMANTIC_INDEX_NOT_READY"
                    ):
                        await no_state.active_state(require_model=True)
                    assert (await no_state.status()).state == "building"
                finally:
                    type(service)._building = False
        finally:
            await manager.dispose()

    _run(scenario())


def test_semantic_rebuild_activates_explicit_empty_index_for_zero_active_chunks(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        manager = DatabaseSessionManager(tmp_path / "empty.db")
        async with manager.get_engine().begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        state_store = SemanticStateStore(tmp_path / "vector" / "state.json")
        store = FakeChromaStore()
        old_name = f"legal_chunks_{uuid4().hex}"
        store.create_collection(
            old_name,
            schema_version=1,
            embedding_model="intfloat/multilingual-e5-small",
            embedding_dimension=3,
        )
        state_store.write_atomic(
            SemanticIndexState(
                schema_version=1,
                active_collection=old_name,
                embedding_model="intfloat/multilingual-e5-small",
                embedding_dimension=3,
                distance_metric="cosine",
                indexed_chunks=0,
                created_at="2026-07-24T00:00:00+00:00",
                source_fingerprint="0" * 64,
            )
        )
        try:
            async with manager.get_session_factory()() as session:
                service = SemanticIndexService(
                    session,
                    embedding_model=FakeEmbeddingModel(),
                    store=store,
                    state_store=state_store,
                )
                rebuilt = await service.rebuild()
                state = state_store.read()
                assert rebuilt.indexed_chunks == 0
                assert state is not None and state.indexed_chunks == 0
                assert state.source_fingerprint == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                assert set(store.collections) == {state.active_collection}
                status = await service.status()
                assert status.state == "ready" and not status.needs_rebuild
                result = await SemanticSearchService(service).search(
                    SemanticSearchRequest(query="consulta sintética")
                )
                assert result.items == [] and result.returned == 0
        finally:
            await manager.dispose()

    _run(scenario())


def test_semantic_search_uses_query_embedding_filters_sqlite_and_safe_snippet(tmp_path: Path) -> None:
    async def scenario() -> None:
        manager, identifiers = await _semantic_database(tmp_path)
        store = FakeChromaStore()
        model = FakeEmbeddingModel()
        state_store = SemanticStateStore(tmp_path / "vector" / "state.json")
        try:
            async with manager.get_session_factory()() as session:
                index = SemanticIndexService(
                    session, embedding_model=model, store=store, state_store=state_store
                )
                await index.rebuild()
                model.encoded.clear()
                result = await SemanticSearchService(index).search(
                    SemanticSearchRequest(
                        query="acción sintética",
                        document_id=identifiers[0],
                        document_types=[DocumentType.JURISPRUDENCIA],
                        min_page=1,
                        max_page=2,
                        top_k=1,
                    )
                )
                assert result.returned == 1 and result.items[0].chunk_id == identifiers[2]
                assert model.encoded == [["query: acción sintética"]]
                assert store.last_query is not None and store.last_query["limit"] == 3
                assert store.last_query["where"] == {
                    "$and": [
                        {"document_id": str(identifiers[0])},
                        {"document_type": {"$in": ["jurisprudencia"]}},
                        {"start_page": {"$gte": 1}},
                        {"end_page": {"$lte": 2}},
                    ]
                }
                assert "query:" not in result.model_dump_json()
                assert "&lt;script&gt;" in result.items[0].snippet
                assert "<script>" not in result.items[0].snippet
                assert len(result.items[0].snippet) <= 500
                assert "acción" in result.items[0].snippet
        finally:
            await manager.dispose()

    _run(scenario())


def test_semantic_search_discards_stale_duplicate_and_mismatched_candidates(tmp_path: Path) -> None:
    async def scenario() -> None:
        manager, identifiers = await _semantic_database(tmp_path)
        store = FakeChromaStore()
        model = FakeEmbeddingModel()
        state_store = SemanticStateStore(tmp_path / "vector" / "state.json")
        try:
            async with manager.get_session_factory()() as session:
                index = SemanticIndexService(
                    session, embedding_model=model, store=store, state_store=state_store
                )
                await index.rebuild()
                state = state_store.read()
                assert state is not None
                rows = store.collections[state.active_collection]["rows"]
                assert isinstance(rows, dict)
                vector, metadata = rows[str(identifiers[2])]
                metadata["start_page"] = 99
                store.extra_candidates = [
                    VectorCandidate(
                        chunk_id=str(uuid4()),
                        metadata=dict(metadata),
                        distance=0.0,
                    ),
                    VectorCandidate(
                        chunk_id=str(identifiers[3]),
                        metadata=dict(rows[str(identifiers[3])][1]),
                        distance=1.0,
                    ),
                ]
                result = await SemanticSearchService(index).search(
                    SemanticSearchRequest(query="primero", top_k=5)
                )
                assert all(item.chunk_id != identifiers[2] for item in result.items)
                assert result.returned == 1
        finally:
            await manager.dispose()

    _run(scenario())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("document_id", None),
        ("document_id", "00000000-0000-0000-0000-000000000000"),
        ("document_type", None),
        ("document_type", "normativa"),
        ("chunk_index", True),
        ("chunk_index", 2),
        ("start_page", "1"),
        ("start_page", 2),
        ("end_page", None),
        ("end_page", 3),
    ],
)
def test_semantic_metadata_validation_rejects_missing_wrong_types_and_mismatches(
    field: str, value: object
) -> None:
    chunk = ActiveChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_type=DocumentType.JURISPRUDENCIA,
        chunk_index=1,
        text="Sintético",
        start_page=1,
        end_page=2,
    )
    metadata: dict[str, object] = {
        "document_id": str(chunk.document_id),
        "document_type": chunk.document_type.value,
        "chunk_index": chunk.chunk_index,
        "start_page": chunk.start_page,
        "end_page": chunk.end_page,
    }
    assert SemanticSearchService._metadata_matches(metadata, chunk)
    if value is None:
        metadata.pop(field)
    else:
        metadata[field] = value
    assert not SemanticSearchService._metadata_matches(metadata, chunk)


def test_semantic_search_rejects_invalid_output_and_request_limits(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        SemanticSearchRequest(query="   ")
    with pytest.raises(ValidationError):
        SemanticSearchRequest(query="x", min_page=3, max_page=2)
    with pytest.raises(ValidationError):
        SemanticSearchRequest(query="x", top_k=999)
    with pytest.raises(SemanticServiceError, match="SEMANTIC_QUERY_INVALID"):
        SemanticSearchService._normalize_query("texto\x00privado")
    assert math.isfinite(0.1)


def test_semantic_search_rejects_non_finite_distance_and_incompatible_index(tmp_path: Path) -> None:
    async def scenario() -> None:
        manager, identifiers = await _semantic_database(tmp_path)
        store = FakeChromaStore()
        model = FakeEmbeddingModel()
        state_store = SemanticStateStore(tmp_path / "vector" / "state.json")
        try:
            async with manager.get_session_factory()() as session:
                index = SemanticIndexService(
                    session, embedding_model=model, store=store, state_store=state_store
                )
                await index.rebuild()
                state = state_store.read()
                assert state is not None
                rows = store.collections[state.active_collection]["rows"]
                assert isinstance(rows, dict)
                metadata = dict(rows[str(identifiers[2])][1])
                for invalid_distance in (float("nan"), float("inf"), float("-inf")):
                    store.extra_candidates = [
                        VectorCandidate(str(identifiers[2]), metadata, invalid_distance)
                    ]
                    with pytest.raises(
                        SemanticServiceError, match="SEMANTIC_OUTPUT_INVALID"
                    ):
                        await SemanticSearchService(index).search(
                            SemanticSearchRequest(query="sintético")
                        )
                store.extra_candidates = []
                object.__setattr__(model, "dimension", 4)
                with pytest.raises(SemanticServiceError, match="SEMANTIC_INDEX_INCOMPATIBLE"):
                    await index.active_state(require_model=True)
        finally:
            await manager.dispose()

    _run(scenario())


def test_semantic_api_status_and_controlled_errors_without_chroma(tmp_path: Path, monkeypatch) -> None:
    manager = _run(_semantic_database(tmp_path))[0]

    async def override_session():
        async with manager.get_session_factory()() as session:
            yield session

    monkeypatch.setattr(ChromaStore, "dependency_available", staticmethod(lambda: False))
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            status = client.get("/api/search/semantic/status")
            rebuild = client.post("/api/search/semantic/rebuild")
            search = client.post("/api/search/semantic", json={"query": "MARCADOR_PRIVADO"})
            invalid = client.post("/api/search/semantic", json={"query": "   "})
            invalid_top = client.post(
                "/api/search/semantic", json={"query": "x", "top_k": 999}
            )
            invalid_range = client.post(
                "/api/search/semantic",
                json={"query": "x", "min_page": 3, "max_page": 2},
            )
        assert status.status_code == 200 and status.json()["state"] == "unavailable"
        assert rebuild.status_code == 503
        assert search.status_code == 503 and "MARCADOR_PRIVADO" not in search.text
        assert invalid.status_code == 422
        assert invalid_top.status_code == 422
        assert invalid_range.status_code == 422
        for response in (status, rebuild, search):
            serialized = response.text.lower()
            for forbidden in (str(tmp_path).lower(), "active_collection", "traceback", "vector"):
                assert forbidden not in serialized
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        _run(manager.dispose())


def test_semantic_status_handles_missing_corrupt_incompatible_and_unloaded_model(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        manager, _ = await _semantic_database(tmp_path)
        path = tmp_path / "vector" / "state.json"
        store = FakeChromaStore()
        model = FakeEmbeddingModel()
        try:
            async with manager.get_session_factory()() as session:
                service = SemanticIndexService(
                    session,
                    embedding_model=model,
                    store=store,
                    state_store=SemanticStateStore(path),
                )
                type(service)._last_error_code = None
                assert (await service.status()).state == "not_ready"
                path.parent.mkdir(parents=True)
                path.write_text("{", encoding="utf-8")
                corrupt = await service.status()
                assert corrupt.state == "error"
                assert corrupt.error_code == "SEMANTIC_INDEX_STATE_INVALID"
                path.unlink()
                await service.rebuild()
                state = SemanticStateStore(path).read()
                assert state is not None
                collection_metadata = store.collections[state.active_collection]["metadata"]
                assert isinstance(collection_metadata, dict)
                collection_metadata["hnsw:space"] = "l2"
                with pytest.raises(
                    SemanticServiceError, match="SEMANTIC_INDEX_INCOMPATIBLE"
                ):
                    await service.active_state(require_model=True)
                collection_metadata["hnsw:space"] = "cosine"
                model.is_loaded = False
                model.dimension = None
                unloaded = await service.status()
                assert unloaded.state == "ready"
                assert unloaded.embedding_dimension == 3

                incompatible = {
                    **state.__dict__,
                    "schema_version": state.schema_version + 1,
                }
                path.write_text(json.dumps(incompatible), encoding="utf-8")
                result = await service.status()
                assert result.state == "error"
                assert result.error_code == "SEMANTIC_INDEX_INCOMPATIBLE"
        finally:
            await manager.dispose()

    _run(scenario())


def test_semantic_api_maps_busy_and_success_without_exposing_internal_data(
    tmp_path: Path, monkeypatch
) -> None:
    manager = _run(_semantic_database(tmp_path))[0]

    async def override_session():
        async with manager.get_session_factory()() as session:
            yield session

    async def busy(self, **_kwargs):
        raise SemanticServiceError("SEMANTIC_INDEX_BUSY")

    monkeypatch.setattr(SemanticIndexService, "rebuild", busy)
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.post("/api/search/semantic/rebuild")
        assert response.status_code == 409
        assert response.json() == {"detail": "SEMANTIC_INDEX_BUSY"}
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        _run(manager.dispose())


@pytest.mark.parametrize(
    ("operation", "code", "status_code"),
    [
        ("rebuild", "EMBEDDING_MODEL_NOT_LOADED", 503),
        ("rebuild", "SEMANTIC_INDEX_BUILD_ERROR", 500),
        ("search", "SEMANTIC_INDEX_NOT_READY", 503),
        ("search", "SEMANTIC_INDEX_INCOMPATIBLE", 503),
        ("search", "EMBEDDING_MODEL_NOT_LOADED", 503),
        ("search", "SEMANTIC_SEARCH_ERROR", 500),
    ],
)
def test_semantic_api_maps_controlled_service_errors_without_internal_details(
    tmp_path: Path, monkeypatch, operation: str, code: str, status_code: int
) -> None:
    manager = _run(_semantic_database(tmp_path))[0]

    async def override_session():
        async with manager.get_session_factory()() as session:
            yield session

    async def fail(*_args, **_kwargs):
        raise SemanticServiceError(code)

    if operation == "rebuild":
        monkeypatch.setattr(SemanticIndexService, "rebuild", fail)
        endpoint = "/api/search/semantic/rebuild"
        payload = None
    else:
        monkeypatch.setattr(SemanticSearchService, "search", fail)
        endpoint = "/api/search/semantic"
        payload = {"query": "MARCADOR_PRIVADO"}
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.post(endpoint, json=payload)
        assert response.status_code == status_code
        assert response.json() == {"detail": code}
        assert "MARCADOR_PRIVADO" not in response.text
        assert "traceback" not in response.text.lower()
        assert str(tmp_path).lower() not in response.text.lower()
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        _run(manager.dispose())


def test_semantic_api_returns_typed_ready_rebuild_search_and_empty(
    tmp_path: Path, monkeypatch
) -> None:
    manager, identifiers = _run(_semantic_database(tmp_path))
    empty = False

    async def override_session():
        async with manager.get_session_factory()() as session:
            yield session

    async def ready(self):
        return SemanticStatusResponse(
            state="ready",
            dependency_available=True,
            embedding_model="multilingual-e5-small",
            embedding_dimension=3,
            indexed_chunks=2,
            active_chunks=2,
            needs_rebuild=False,
        )

    async def rebuilt(self, **_kwargs):
        return SemanticRebuildResponse(indexed_chunks=2, embedding_dimension=3)

    async def searched(self, request, **_kwargs):
        if empty:
            return SemanticSearchResponse(items=[], returned=0, top_k=request.top_k)
        item = SemanticSearchItem(
            chunk_id=identifiers[2],
            document_id=identifiers[0],
            document_type=DocumentType.JURISPRUDENCIA,
            chunk_index=1,
            start_page=1,
            end_page=2,
            snippet="Sintético",
            distance_cosine=0.1,
        )
        return SemanticSearchResponse(items=[item], returned=1, top_k=request.top_k)

    monkeypatch.setattr(SemanticIndexService, "status", ready)
    monkeypatch.setattr(SemanticIndexService, "rebuild", rebuilt)
    monkeypatch.setattr(SemanticSearchService, "search", searched)
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            status = client.get("/api/search/semantic/status")
            rebuild = client.post("/api/search/semantic/rebuild")
            found = client.post(
                "/api/search/semantic", json={"query": "MARCADOR_PRIVADO", "top_k": 2}
            )
            empty = True
            no_results = client.post(
                "/api/search/semantic", json={"query": "MARCADOR_PRIVADO", "top_k": 2}
            )
        assert status.status_code == 200 and status.json()["state"] == "ready"
        assert rebuild.status_code == 200 and rebuild.json()["indexed_chunks"] == 2
        assert found.status_code == 200 and found.json()["returned"] == 1
        assert no_results.status_code == 200 and no_results.json()["items"] == []
        for response in (status, rebuild, found, no_results):
            assert "MARCADOR_PRIVADO" not in response.text
            assert "active_collection" not in response.text
            assert "embedding" not in found.json().get("items", [{}])[0]
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        _run(manager.dispose())


def test_semantic_logging_never_contains_query_text(tmp_path: Path, monkeypatch, caplog) -> None:
    captured: list[tuple[str, dict[str, object]]] = []

    def capture(message: str, **context) -> None:
        captured.append((message, context))

    monkeypatch.setattr(search_module, "log_info", capture)
    monkeypatch.setattr(search_module, "log_success", capture)
    monkeypatch.setattr(search_module, "log_error", capture)

    async def scenario() -> None:
        manager, _ = await _semantic_database(tmp_path)
        store = FakeChromaStore()
        state_store = SemanticStateStore(tmp_path / "vector" / "state.json")
        try:
            async with manager.get_session_factory()() as session:
                index = SemanticIndexService(
                    session,
                    embedding_model=FakeEmbeddingModel(),
                    store=store,
                    state_store=state_store,
                )
                await index.rebuild()
                await SemanticSearchService(index).search(
                    SemanticSearchRequest(query="MARCADOR_PRIVADO")
                )
        finally:
            await manager.dispose()

    _run(scenario())
    serialized = repr(captured)
    assert "MARCADOR_PRIVADO" not in serialized
    assert "active_collection" not in serialized
    assert "query_length" in serialized


def test_manual_semantic_script_is_non_destructive_and_not_pytest_collectable() -> None:
    script_path = Path(__file__).parents[2] / "scripts" / "validate_semantic_index.py"
    source = script_path.read_text(encoding="utf-8")
    assert script_path.name.startswith("validate_")
    assert not script_path.name.startswith("test_")
    assert ".rebuild(" not in source
    assert "active_collection" not in source
    assert "query_embedding" not in source
    assert "Qwen" not in source
    assert "http://" not in source and "https://" not in source


def test_optional_real_chroma_persists_synthetic_vectors(tmp_path: Path) -> None:
    pytest.importorskip("chromadb")
    store = ChromaStore(tmp_path / "chroma", enforce_authorized_path=False)
    name = f"legal_chunks_{uuid4().hex}"
    store.create_collection(
        name,
        schema_version=1,
        embedding_model="intfloat/multilingual-e5-small",
        embedding_dimension=2,
    )
    identifier = str(uuid4())
    store.add(
        name,
        ids=[identifier],
        embeddings=[[1.0, 0.0]],
        metadatas=[{
            "document_id": str(uuid4()),
            "document_type": "otro",
            "chunk_index": 1,
            "start_page": 1,
            "end_page": 1,
        }],
    )
    recreated = ChromaStore(tmp_path / "chroma", enforce_authorized_path=False)
    result = recreated.query(
        name, query_embedding=[1.0, 0.0], limit=1, where=None
    )
    assert result[0].chunk_id == identifier
    assert recreated.count(name) == 1
    collection = recreated._client().get_collection(
        name=name, embedding_function=None
    )
    payload = collection.get(ids=[identifier], include=["documents", "metadatas"])
    documents = payload.get("documents")
    assert documents is None or all(document is None for document in documents)
    assert payload["metadatas"] == [{
        "document_id": result[0].metadata["document_id"],
        "document_type": "otro",
        "chunk_index": 1,
        "start_page": 1,
        "end_page": 1,
    }]
