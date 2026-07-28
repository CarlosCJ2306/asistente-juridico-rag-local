"""Catálogo y selección de modelos sin tocar modelos ni storage reales."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.ai.embedding_model import EmbeddingModel
from app.ai.local_llm import LocalLLM
from app.ai.model_manager import ManifestError, ModelManager, ModelSelectionError, ModelSelectionStore
from app.api.routes import models as models_route
from app.main import app


def _catalog(tmp_path: Path, *, schema_version: int = 1) -> tuple[ModelManager, Path, Path]:
    models_dir = tmp_path / "models"
    embedding_path = models_dir / "embeddings" / "multilingual-e5-small"
    embedding_path.mkdir(parents=True, exist_ok=True)
    (embedding_path / "config.json").write_text("{}", encoding="utf-8")
    (embedding_path / "modules.json").write_text("[]", encoding="utf-8")
    llm_path = models_dir / "llm" / "qwen" / "model.gguf"
    llm_path.parent.mkdir(parents=True, exist_ok=True)
    llm_path.write_bytes(b"GGUFmodelo")
    manifest = {
        "schema_version": schema_version,
        "models": [
            {
                "id": "multilingual-e5-small", "name": "E5", "display_name": "E5 local",
                "description": "Embedding de prueba", "family": "e5", "type": "embedding",
                "repository": "intfloat/multilingual-e5-small", "format": "Sentence Transformers",
                "local_path": "models/embeddings/multilingual-e5-small", "purpose": "Prueba",
                "installation_status": "not_installed", "embedding_dimension": 384,
                "capabilities": ["query_embedding"], "enabled": True,
            },
            {
                "id": "qwen3-1.7b-q4-k-m", "name": "Qwen", "display_name": "Qwen local",
                "description": "LLM de prueba", "family": "Qwen3", "type": "llm",
                "repository": "ggml-org/Qwen", "filename": "model.gguf", "format": "GGUF",
                "quantization": "Q4_K_M", "local_path": "models/llm/qwen/model.gguf",
                "purpose": "Prueba", "installation_status": "not_installed",
                "minimum_file_size_bytes": 4, "context_length": 4096,
                "capabilities": ["chat"], "enabled": True,
            },
        ],
    }
    manifest_path = models_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return ModelManager(project_root=tmp_path, models_dir=models_dir, manifest_path=manifest_path), embedding_path, llm_path


def test_catalog_rejects_unsupported_version_duplicate_and_invalid_type(tmp_path: Path) -> None:
    manager, _, _ = _catalog(tmp_path, schema_version=2)
    with pytest.raises(ManifestError):
        manager.load_manifest()
    manager, _, _ = _catalog(tmp_path)
    raw = json.loads(manager.manifest_path.read_text(encoding="utf-8"))
    raw["models"].append(raw["models"][0])
    manager.manifest_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ManifestError, match="duplicados"):
        manager.load_manifest(refresh=True)
    raw["models"].pop()
    raw["models"][0]["type"] = "remote"
    manager.manifest_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ManifestError):
        manager.load_manifest(refresh=True)


def test_selection_is_atomic_persistent_and_corrupt_file_falls_back(tmp_path: Path) -> None:
    manager, _, _ = _catalog(tmp_path)
    selection_path = tmp_path / "storage" / "config" / "model-selection.json"
    store = ModelSelectionStore(manager, path=selection_path)
    selected = store.select("multilingual-e5-small", "embedding", currently_loaded=False)
    assert selected.active_embedding_model_id == "multilingual-e5-small"
    assert ModelSelectionStore(manager, path=selection_path).read() == selected
    assert not list(selection_path.parent.glob("*.tmp"))
    selection_path.write_text("{inválido", encoding="utf-8")
    assert store.read() == store.defaults()


def test_selection_rejects_wrong_type_missing_disabled_uninstalled_and_loaded(tmp_path: Path) -> None:
    manager, embedding_path, _ = _catalog(tmp_path)
    store = ModelSelectionStore(manager, path=tmp_path / "selection.json")
    with pytest.raises(ModelSelectionError, match="MODEL_TYPE_MISMATCH"):
        store.select("qwen3-1.7b-q4-k-m", "embedding", currently_loaded=False)
    with pytest.raises(ModelSelectionError, match="MODEL_NOT_FOUND"):
        store.select("unknown", "llm", currently_loaded=False)
    with pytest.raises(ModelSelectionError, match="MODEL_CURRENTLY_LOADED"):
        store.select("multilingual-e5-small", "embedding", currently_loaded=True)
    (embedding_path / "modules.json").unlink()
    with pytest.raises(ModelSelectionError, match="MODEL_NOT_INSTALLED"):
        store.select("multilingual-e5-small", "embedding", currently_loaded=False)
    raw = json.loads(manager.manifest_path.read_text(encoding="utf-8"))
    raw["models"][0]["enabled"] = False
    manager.manifest_path.write_text(json.dumps(raw), encoding="utf-8")
    manager.load_manifest(refresh=True)
    with pytest.raises(ModelSelectionError, match="MODEL_DISABLED"):
        store.select("multilingual-e5-small", "embedding", currently_loaded=False)


def test_embedding_fingerprint_identity_changes_only_with_embedding_model(tmp_path: Path) -> None:
    manager, embedding_path, _ = _catalog(tmp_path)
    original = EmbeddingModel(manager, configured_path=str(embedding_path))
    raw = json.loads(manager.manifest_path.read_text(encoding="utf-8"))
    alternate = dict(raw["models"][0])
    alternate.update({"id": "e5-alternate", "family": "e5-v2", "embedding_dimension": 512, "local_path": "models/embeddings/e5-alternate"})
    raw["models"].append(alternate)
    manager.manifest_path.write_text(json.dumps(raw), encoding="utf-8")
    manager.load_manifest(refresh=True)
    changed = EmbeddingModel(manager, model_id="e5-alternate")
    assert original.fingerprint_identity != changed.fingerprint_identity
    llm = LocalLLM(manager, llama_factory=Mock())
    before = original.fingerprint_identity
    llm.select_model("qwen3-1.7b-q4-k-m")
    assert original.fingerprint_identity == before


def test_future_loads_use_persisted_active_models_without_automatic_load(tmp_path: Path) -> None:
    manager, _, _ = _catalog(tmp_path)
    raw = json.loads(manager.manifest_path.read_text(encoding="utf-8"))
    alternate_embedding = dict(raw["models"][0])
    alternate_embedding.update({"id": "e5-local-alt", "local_path": "models/embeddings/e5-local-alt"})
    alternate_llm = dict(raw["models"][1])
    alternate_llm.update({"id": "qwen-local-alt", "local_path": "models/llm/qwen-alt/model.gguf"})
    raw["models"].extend([alternate_embedding, alternate_llm])
    manager.manifest_path.write_text(json.dumps(raw), encoding="utf-8")
    manager.load_manifest(refresh=True)
    alt_embedding_path = manager.resolve_model_path("e5-local-alt")
    alt_embedding_path.mkdir(parents=True)
    (alt_embedding_path / "config.json").write_text("{}", encoding="utf-8")
    (alt_embedding_path / "modules.json").write_text("[]", encoding="utf-8")
    alt_llm_path = manager.resolve_model_path("qwen-local-alt")
    alt_llm_path.parent.mkdir(parents=True)
    alt_llm_path.write_bytes(b"GGUFmodelo-alterno")
    store = ModelSelectionStore(manager, path=tmp_path / "selection.json")
    store.select("e5-local-alt", "embedding", currently_loaded=False)
    selected = store.select("qwen-local-alt", "llm", currently_loaded=False)

    class FakeEmbedding:
        def get_embedding_dimension(self) -> int:
            return 384

    embedding_factory = Mock(return_value=FakeEmbedding())
    embedding = EmbeddingModel(manager, model_id=selected.active_embedding_model_id, loader_factory=embedding_factory)
    llm_factory = Mock(return_value=Mock(close=Mock()))
    llm = LocalLLM(manager, model_id=selected.active_llm_model_id, llama_factory=llm_factory)
    assert not embedding.is_loaded and not llm.is_loaded
    embedding.load()
    llm.load()
    assert Path(embedding_factory.call_args.args[0]) == alt_embedding_path
    assert Path(llm_factory.call_args.kwargs["model_path"]) == alt_llm_path
    assert embedding_factory.call_args.kwargs["local_files_only"] is True
    assert embedding_factory.call_args.kwargs["trust_remote_code"] is False
    embedding.unload()
    llm.unload()
    assert store.read() == selected


def test_catalog_and_selection_api_are_sanitized_and_do_not_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager, embedding_path, _ = _catalog(tmp_path)
    store = ModelSelectionStore(manager, path=tmp_path / "storage" / "config" / "selection.json")
    embedding = EmbeddingModel(manager, configured_path=str(embedding_path))
    llm = LocalLLM(manager, llama_factory=Mock())
    monkeypatch.setattr(models_route, "_model_manager", manager)
    monkeypatch.setattr(models_route, "_selection_store", store)
    monkeypatch.setattr(models_route, "get_embedding_model", lambda: embedding)
    monkeypatch.setattr(models_route, "get_local_llm", lambda: llm)
    with TestClient(app) as client:
        catalog = client.get("/api/models/catalog")
        selection = client.get("/api/models/selection")
        selected_embedding = client.put("/api/models/selection/embeddings", json={"model_id": "multilingual-e5-small"})
        wrong_type = client.put("/api/models/selection/llm", json={"model_id": "multilingual-e5-small"})
    assert catalog.status_code == selection.status_code == selected_embedding.status_code == 200
    assert wrong_type.status_code == 409 and wrong_type.json()["detail"] == "MODEL_TYPE_MISMATCH"
    assert embedding.is_loaded is False and llm.is_loaded is False
    serialized = catalog.text + selection.text + selected_embedding.text
    assert str(tmp_path) not in serialized
    assert "local_path" not in serialized and "relative_path" not in serialized and "sha256" not in serialized
    assert {item["model_type"] for item in catalog.json()["models"]} == {"embedding", "llm"}
