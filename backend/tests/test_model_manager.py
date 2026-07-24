"""Verificación del manifiesto y de la integridad de archivos temporales."""

import hashlib
import json

import pytest

from app.ai.model_manager import ManifestError, UnsafeModelPathError


def test_reads_and_validates_manifest(model_project_factory) -> None:
    manager, _ = model_project_factory()

    manifest = manager.load_manifest()

    assert len(manifest.models) == 1
    assert manifest.models[0].id == "qwen3-1.7b-q4-k-m"


def test_resolves_path_inside_temporary_models(model_project_factory) -> None:
    manager, expected_path = model_project_factory()

    resolved_path = manager.resolve_model_path("qwen3-1.7b-q4-k-m")

    assert resolved_path == expected_path.resolve()
    assert resolved_path.is_relative_to(manager.models_dir)


def test_rejects_path_outside_models(model_project_factory) -> None:
    manager, _ = model_project_factory(local_path="outside/model.gguf")

    with pytest.raises(UnsafeModelPathError, match="fuera del directorio models"):
        manager.resolve_model_path("qwen3-1.7b-q4-k-m")


def test_rejects_path_traversal_even_when_destination_is_inside_models(
    model_project_factory,
) -> None:
    manager, _ = model_project_factory(local_path="models/llm/../test/model.gguf")

    with pytest.raises(UnsafeModelPathError, match="navegación no permitida"):
        manager.resolve_model_path("qwen3-1.7b-q4-k-m")


def test_rejects_invalid_sha256_in_manifest(model_project_factory) -> None:
    manager, _ = model_project_factory()
    manifest = json.loads(manager.manifest_path.read_text(encoding="utf-8"))
    manifest["models"][0]["sha256"] = "hash-no-valido"
    manager.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ManifestError, match="sha256"):
        manager.load_manifest(refresh=True)


def test_detects_missing_model(model_project_factory) -> None:
    manager, _ = model_project_factory()

    result = manager.verify_model("qwen3-1.7b-q4-k-m")

    assert result.installed is False
    assert result.verified is False
    assert any("no está instalado" in error for error in result.errors)


def test_detects_empty_model_file(model_project_factory) -> None:
    manager, model_path = model_project_factory()
    model_path.parent.mkdir(parents=True)
    model_path.touch()

    result = manager.verify_model("qwen3-1.7b-q4-k-m")

    assert result.installed is True
    assert result.verified is False
    assert any("vacío" in error for error in result.errors)


def test_detects_incorrect_gguf_extension(model_project_factory) -> None:
    manager, model_path = model_project_factory(
        local_path="models/llm/test/model.bin",
        filename="model.bin",
    )
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"GGUFtest")

    result = manager.verify_model("qwen3-1.7b-q4-k-m")

    assert result.verified is False
    assert any("extensión .gguf" in error for error in result.errors)


def test_detects_incorrect_filename(model_project_factory) -> None:
    manager, model_path = model_project_factory(filename="expected.gguf")
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"GGUFtest")

    result = manager.verify_model("qwen3-1.7b-q4-k-m")

    assert result.verified is False
    assert any("nombre esperado" in error for error in result.errors)


def test_detects_invalid_gguf_header(model_project_factory) -> None:
    manager, model_path = model_project_factory()
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"NOTGcontenido")

    result = manager.verify_model("qwen3-1.7b-q4-k-m")

    assert result.verified is False
    assert any("firma GGUF" in error for error in result.errors)


def test_calculates_and_validates_sha256(model_project_factory) -> None:
    content = b"GGUFcontenido-de-prueba"
    expected_hash = hashlib.sha256(content).hexdigest()
    manager, model_path = model_project_factory(
        minimum_file_size_bytes=4,
        sha256=expected_hash,
    )
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(content)

    assert manager.calculate_sha256(model_path) == expected_hash
    result = manager.verify_model("qwen3-1.7b-q4-k-m")
    assert result.verified is True
    assert result.calculated_sha256 == expected_hash


def test_manager_never_writes_to_real_models(
    model_project_factory,
) -> None:
    manager, model_path = model_project_factory()

    assert model_path.is_relative_to(manager.models_dir)
    assert "pytest" in str(model_path).lower() or "temp" in str(model_path).lower()
