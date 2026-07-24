"""Verifica los modelos de archivo sin cargarlos ni modificarlos.

Debe ejecutarse explícitamente desde la raíz del proyecto. Reutiliza toda la
lógica de integridad de ``ModelManager`` y devuelve un código diferente de cero
si falta un modelo o cualquier comprobación falla.
"""

from __future__ import annotations

import sys
import argparse
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.model_manager import ModelManager  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.Log import log_error, log_exception, log_success  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Verifica todos los artefactos individuales declarados."""

    parser = argparse.ArgumentParser(description="Verificación manual de modelos locales")
    parser.add_argument("--model", dest="model_id", help="Identificador del manifiesto")
    arguments = parser.parse_args(argv)

    manager = ModelManager()
    try:
        file_models = list(manager.list_models())
        if arguments.model_id:
            file_models = [entry for entry in file_models if entry.id == arguments.model_id]
        if not file_models:
            log_error("El manifiesto no contiene modelos de archivo para verificar")
            return 1

        all_verified = True
        verified_count = 0
        for entry in file_models:
            result = manager.verify_model(
                entry.id,
                configured_path=settings.embedding_model_path if entry.id == "multilingual-e5-small" else None,
            )
            if result.verified:
                verified_count += 1
                log_success(
                    "Verificación final correcta",
                    model_id=entry.id,
                    model_name=entry.name,
                    relative_path=entry.local_path,
                    file_size=result.file_size,
                    verification_status="verified",
                )
            else:
                all_verified = False
                log_error(
                    "Verificación final fallida",
                    model_id=entry.id,
                    model_name=entry.name,
                    relative_path=entry.local_path,
                    verification_status="failed",
                    verification_errors=result.errors,
                )
        if all_verified:
            log_success(
                "Todos los modelos de archivo superaron la verificación",
                model_count=len(file_models),
                verified_count=verified_count,
                verification_status="verified",
            )
            return 0
        log_error(
            "Uno o más modelos de archivo no superaron la verificación",
            model_count=len(file_models),
            verified_count=verified_count,
            verification_status="failed",
        )
        return 1
    except Exception as exc:
        log_exception(
            "No fue posible completar la verificación de modelos",
            exception_type=type(exc).__name__,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
