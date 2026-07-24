"""Descarga explícita de artefactos declarados en ``models/manifest.json``.

El módulo no realiza acciones al importarse. Al ejecutarlo desde la raíz del
proyecto usa Hugging Face únicamente como origen del archivo exacto y valida
el resultado antes de informar éxito.
"""

from __future__ import annotations

import sys
import argparse
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.model_manager import ModelManager  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.Log import (  # noqa: E402
    log_error,
    log_exception,
    log_info,
    log_success,
)


EMBEDDING_ALLOW_PATTERNS = [
    "config.json",
    "modules.json",
    "sentence_bert_config.json",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "model.safetensors",
    "1_Pooling/config.json",
]
EMBEDDING_IGNORE_PATTERNS = [
    "*.bin",
    "*.onnx",
    "*.xml",
    "*.yaml",
    "onnx/**",
    "openvino/**",
    ".eval_results/**",
    ".cache/**",
    "README*",
]


def main(argv: list[str] | None = None) -> int:
    """Descarga y verifica todos los artefactos de archivo del manifiesto."""

    parser = argparse.ArgumentParser(description="Descarga manual de modelos locales")
    parser.add_argument("--model", dest="model_id", help="Identificador del manifiesto")
    arguments = parser.parse_args(argv)

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        log_error(
            "huggingface-hub no está instalado; instale los requisitos del modelo correspondiente"
        )
        return 2

    manager = ModelManager()
    try:
        downloadable_models = list(manager.list_models())
        if arguments.model_id:
            downloadable_models = [entry for entry in downloadable_models if entry.id == arguments.model_id]
        if not downloadable_models:
            log_error("El manifiesto no contiene modelos descargables")
            return 1

        downloaded_count = 0
        skipped_count = 0
        for entry in downloadable_models:
            current_status = manager.verify_model(
                entry.id,
                configured_path=settings.embedding_model_path if entry.id == "multilingual-e5-small" else None,
            )
            if current_status.verified:
                log_info(
                    "Se omite un modelo ya verificado",
                    model_id=entry.id,
                    model_name=entry.name,
                    relative_path=entry.local_path,
                    file_size=current_status.file_size,
                )
                skipped_count += 1
                continue

            target_path = (
                manager.resolve_embedding_model_path(settings.embedding_model_path)
                if entry.id == "multilingual-e5-small"
                else manager.resolve_model_path(entry)
            )
            log_info(
                "Iniciando descarga controlada del modelo",
                model_id=entry.id,
                model_name=entry.name,
                relative_path=entry.local_path,
            )
            if entry.filename is not None:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                downloaded_path = Path(
                    hf_hub_download(
                        repo_id=entry.repository,
                        filename=entry.filename,
                        local_dir=str(target_path.parent),
                        force_download=False,
                    )
                ).resolve()
                if downloaded_path != target_path.resolve():
                    log_error("Hugging Face devolvió una ruta distinta de la declarada", model_id=entry.id)
                    return 1
            else:
                from huggingface_hub import snapshot_download

                if target_path.exists():
                    log_error(
                        "El destino de embeddings ya existe y no se sobrescribe",
                        model_id=entry.id,
                        verification_status="existing_unverified_destination",
                    )
                    return 1
                target_path.parent.mkdir(parents=True, exist_ok=True)
                temporary_path = Path(
                    tempfile.mkdtemp(prefix=f".{entry.id}.", dir=target_path.parent)
                )
                marker = temporary_path / ".incomplete"
                marker.touch()
                snapshot_download(
                    repo_id=entry.repository,
                    local_dir=str(temporary_path),
                    allow_patterns=EMBEDDING_ALLOW_PATTERNS,
                    ignore_patterns=EMBEDDING_IGNORE_PATTERNS,
                )
                temporary_path.rename(target_path)
                (target_path / ".incomplete").unlink(missing_ok=True)
            final_status = manager.verify_model(
                entry.id,
                configured_path=settings.embedding_model_path if entry.id == "multilingual-e5-small" else None,
            )
            if not final_status.verified:
                log_error(
                    "El archivo descargado no superó la verificación",
                    model_id=entry.id,
                    relative_path=entry.local_path,
                    verification_status="failed",
                )
                return 1
            log_success(
                "Modelo descargado y verificado",
                model_id=entry.id,
                model_name=entry.name,
                relative_path=entry.local_path,
                file_size=final_status.file_size,
            )
            downloaded_count += 1
        log_success(
            "Descarga controlada de modelos finalizada",
            model_count=len(downloadable_models),
            downloaded_count=downloaded_count,
            skipped_count=skipped_count,
        )
    except Exception as exc:
        log_exception(
            "La descarga de modelos terminó con error",
            exception_type=type(exc).__name__,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
