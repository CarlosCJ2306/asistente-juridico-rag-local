"""Pruebas sin red para embeddings locales mediante un doble determinista."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.ai import embedding_model as embedding_module
from app.ai.embedding_model import EmbeddingError, EmbeddingModel
from app.ai.model_manager import (
    EmbeddingModelPathMismatchError,
    ModelManager,
    UnsafeModelPathError,
)
from app.core.config import Settings
from app.database.models.document_chunk import DocumentChunk
from app.main import app
from app.services.embedding_service import EmbeddingService


DOWNLOAD_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "download_models.py"


class FakeSentenceTransformer:
    def __init__(self, *_args, **_kwargs) -> None:
        self.batches: list[list[str]] = []

    def get_sentence_embedding_dimension(self) -> int:
        return 3

    def encode(self, texts, **_kwargs):
        self.batches.append(list(texts))
        return [[3.0, 4.0, float(index + 1)] for index, _ in enumerate(texts)]


class ModernSentenceTransformer(FakeSentenceTransformer):
    def get_embedding_dimension(self) -> int:
        return 3


class InvalidDimensionTransformer(FakeSentenceTransformer):
    def get_embedding_dimension(self):
        return 0


class EmptyOutputTransformer(FakeSentenceTransformer):
    def encode(self, texts, **_kwargs):
        return []


def embedding_manager(tmp_path: Path, *, installed: bool = True) -> ModelManager:
    models_dir = tmp_path / "models"
    model_dir = models_dir / "embeddings" / "multilingual-e5-small"
    models_dir.mkdir()
    if installed:
        model_dir.mkdir(parents=True)
        (model_dir / "config.json").write_text("{}", encoding="utf-8")
        (model_dir / "modules.json").write_text("[]", encoding="utf-8")
    manifest_path = models_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "id": "multilingual-e5-small",
                        "name": "Modelo de prueba",
                        "type": "embedding",
                        "repository": "intfloat/multilingual-e5-small",
                        "format": "Sentence Transformers",
                        "local_path": "models/embeddings/multilingual-e5-small",
                        "purpose": "Prueba",
                        "installation_status": "not_installed",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return ModelManager(project_root=tmp_path, models_dir=models_dir, manifest_path=manifest_path)


def make_embedding_model(tmp_path: Path, **kwargs) -> EmbeddingModel:
    manager = embedding_manager(tmp_path)
    return EmbeddingModel(
        manager,
        configured_path=str(manager.resolve_model_path("multilingual-e5-small")),
        **kwargs,
    )


def test_embedding_settings_validate_path_batch_and_prefixes() -> None:
    valid = Settings(_env_file=None, embedding_model_path="models/embeddings/test")
    assert valid.embedding_model_path.name == "test"
    with pytest.raises(ValueError, match="models/embeddings"):
        Settings(_env_file=None, embedding_model_path="../outside")
    with pytest.raises(ValueError, match="greater than 0"):
        Settings(_env_file=None, embedding_batch_size=0)
    with pytest.raises(ValueError, match="prefijos"):
        Settings(_env_file=None, embedding_query_prefix=" ")


def test_embedding_dimension_prefers_modern_api_and_supports_legacy_fallback(tmp_path: Path) -> None:
    modern = make_embedding_model(tmp_path, loader_factory=ModernSentenceTransformer)
    modern.load()
    assert modern.dimension == 3

    legacy_tmp = tmp_path / "legacy"
    legacy_tmp.mkdir()
    legacy = make_embedding_model(legacy_tmp, loader_factory=FakeSentenceTransformer)
    legacy.load()
    assert legacy.dimension == 3


def test_embedding_dimension_rejects_non_positive_value(tmp_path: Path) -> None:
    model = make_embedding_model(tmp_path, loader_factory=InvalidDimensionTransformer)
    with pytest.raises(EmbeddingError, match="EMBEDDING_DIMENSION_INVALID"):
        model.load()


def test_embedding_manifest_and_configured_paths_share_one_effective_location(tmp_path: Path) -> None:
    manager = embedding_manager(tmp_path)
    expected = manager.resolve_model_path("multilingual-e5-small")
    assert manager.resolve_embedding_model_path("models/embeddings/./multilingual-e5-small") == expected
    with pytest.raises(EmbeddingModelPathMismatchError, match="EMBEDDING_MODEL_PATH_MISMATCH") as mismatch:
        manager.resolve_embedding_model_path("models/embeddings/other")
    assert str(expected) not in str(mismatch.value)
    with pytest.raises(UnsafeModelPathError, match="fuera del directorio permitido"):
        manager.resolve_embedding_model_path("../outside")


def test_embedding_path_symlink_escape_is_rejected(tmp_path: Path) -> None:
    manager = embedding_manager(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "models" / "embeddings" / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink no disponible en este sistema")
    with pytest.raises(UnsafeModelPathError, match="fuera del directorio permitido"):
        manager.resolve_embedding_model_path(str(link))


def test_embedding_download_patterns_are_selective_and_safe() -> None:
    source = DOWNLOAD_SCRIPT.read_text(encoding="utf-8")
    assert "local_dir_use_symlinks" not in source
    assert "allow_patterns=EMBEDDING_ALLOW_PATTERNS" in source
    assert "ignore_patterns=EMBEDDING_IGNORE_PATTERNS" in source
    for required in (
        "config.json",
        "modules.json",
        "1_Pooling/config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "sentencepiece.bpe.model",
        "model.safetensors",
    ):
        assert required in source
    assert "onnx/**" in source and "openvino/**" in source
    assert "qwen3-1.7b-q4-k-m" not in source


def test_embedding_service_prefixes_batches_normalizes_and_preserves_chunks(tmp_path: Path) -> None:
    model = make_embedding_model(tmp_path, loader_factory=FakeSentenceTransformer, batch_size=2)
    model.load()
    service = EmbeddingService(model)

    query = service.embed_query("consulta")
    passages = service.embed_passages(["uno", "dos", "tres"])
    chunk = DocumentChunk(
        id=uuid4(), document_id=uuid4(), chunk_index=1, text="fragmento",
        char_count=9, word_count=1, start_page=1, end_page=1,
    )
    embedded = service.embed_chunks([chunk])

    encoder = model._model
    assert isinstance(encoder, FakeSentenceTransformer)
    assert encoder.batches[0] == ["query: consulta"]
    assert encoder.batches[1] == ["passage: uno", "passage: dos"]
    assert encoder.batches[2] == ["passage: tres"]
    assert len(query) == model.dimension == 3
    assert len(passages) == 3
    assert embedded[0].chunk_id == chunk.id and chunk.text == "fragmento"
    assert pytest.approx(sum(value * value for value in query), rel=1e-6) == 1.0


def test_embedding_model_lifecycle_and_invalid_outputs(tmp_path: Path) -> None:
    model = make_embedding_model(tmp_path, loader_factory=FakeSentenceTransformer)
    assert model.state == "unloaded"
    model.load()
    model.load()
    assert model.state == "loaded"
    model.unload()
    model.unload()
    assert model.state == "unloaded"
    with pytest.raises(EmbeddingError, match="EMBEDDING_MODEL_NOT_LOADED"):
        model.encode(["x"])


def test_embedding_model_rejects_non_finite_output(tmp_path: Path) -> None:
    model = make_embedding_model(tmp_path, loader_factory=FakeSentenceTransformer)
    model.load()
    with pytest.raises(EmbeddingError, match="EMBEDDING_OUTPUT_INVALID"):
        model._validate_vectors([[float("nan"), 1.0, 2.0]])


def test_embedding_model_rejects_missing_output_vectors(tmp_path: Path) -> None:
    model = make_embedding_model(tmp_path, loader_factory=EmptyOutputTransformer)
    model.load()
    with pytest.raises(EmbeddingError, match="EMBEDDING_OUTPUT_INVALID"):
        model.encode(["texto"])


def test_embedding_model_missing_files_is_controlled(tmp_path: Path) -> None:
    manager = embedding_manager(tmp_path, installed=False)
    model = EmbeddingModel(
        manager,
        configured_path=str(manager.resolve_model_path("multilingual-e5-small")),
        loader_factory=FakeSentenceTransformer,
    )
    with pytest.raises(EmbeddingError, match="EMBEDDING_MODEL_NOT_FOUND"):
        model.load()
    assert model.state == "error"


def test_embedding_model_api_status_load_unload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model = make_embedding_model(tmp_path, loader_factory=FakeSentenceTransformer)
    monkeypatch.setattr(embedding_module, "_embedding_model", model)

    with TestClient(app) as client:
        status = client.get("/api/models/embeddings/status")
        loaded = client.post("/api/models/embeddings/load")
        unloaded = client.post("/api/models/embeddings/unload")

    assert status.json()["state"] == "unloaded"
    assert loaded.json()["state"] == "loaded"
    assert loaded.json()["dimension"] == 3
    assert unloaded.json()["state"] == "unloaded"
    assert str(tmp_path) not in loaded.text


def test_embedding_api_missing_model_returns_controlled_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        embedding_module,
        "_embedding_model",
        (lambda manager: EmbeddingModel(
            manager,
            configured_path=str(manager.resolve_model_path("multilingual-e5-small")),
            loader_factory=FakeSentenceTransformer,
        ))(embedding_manager(tmp_path, installed=False)),
    )
    with TestClient(app) as client:
        response = client.post("/api/models/embeddings/load")
    assert response.status_code == 503
    assert response.json()["detail"] == "EMBEDDING_MODEL_NOT_FOUND"


def test_embedding_api_busy_load_returns_409(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model = make_embedding_model(tmp_path, loader_factory=FakeSentenceTransformer)
    monkeypatch.setattr(embedding_module, "_embedding_model", model)
    assert model._lock.acquire(blocking=False)
    try:
        with TestClient(app) as client:
            response = client.post("/api/models/embeddings/load")
    finally:
        model._lock.release()
    assert response.status_code == 409
    assert response.json()["detail"] == "EMBEDDING_MODEL_BUSY"
