"""Descarga explícita de artefactos declarados en ``models/manifest.json``.

El módulo no realiza acciones al importarse. Al ejecutarlo desde la raíz del
proyecto usa Hugging Face únicamente como origen del archivo exacto y valida
el resultado antes de informar éxito.
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.model_manager import ModelManager  # noqa: E402
from app.core.Log import (  # noqa: E402
    log_error,
    log_exception,
    log_info,
    log_success,
)


def main() -> int:
    """Descarga y verifica todos los artefactos de archivo del manifiesto."""

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        log_error(
            "huggingface-hub no está instalado; instale backend/requirements-llm.txt"
        )
        return 2

    manager = ModelManager()
    try:
        downloadable_models = [
            entry for entry in manager.list_models() if entry.filename is not None
        ]
        if not downloadable_models:
            log_error("El manifiesto no contiene modelos descargables")
            return 1

        downloaded_count = 0
        skipped_count = 0
        for entry in downloadable_models:
            filename = entry.filename
            if filename is None:  # Acotación defensiva para analizadores de tipos.
                continue
            current_status = manager.verify_model(entry.id)
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

            target_path = manager.resolve_model_path(entry)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            log_info(
                "Iniciando descarga controlada del modelo",
                model_id=entry.id,
                model_name=entry.name,
                relative_path=entry.local_path,
            )
            downloaded_path = Path(
                hf_hub_download(
                    repo_id=entry.repository,
                    filename=filename,
                    local_dir=str(target_path.parent),
                    force_download=target_path.exists(),
                )
            ).resolve()
            if downloaded_path != target_path.resolve():
                log_error(
                    "Hugging Face devolvió una ruta distinta de la declarada",
                    model_id=entry.id,
                    relative_path=entry.local_path,
                )
                return 1
            final_status = manager.verify_model(entry.id)
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
