"""Prueba manual y explícita de inferencia con el modelo local.

No descarga modelos. Verifica el GGUF, lo carga en CPU mediante ``LocalLLM``,
ejecuta un prompt controlado y libera la memoria incluso cuando ocurre un
error. Este módulo no ejecuta inferencia al importarse.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.local_llm import LocalLLM  # noqa: E402
from app.ai.model_manager import DEFAULT_LLM_MODEL_ID, ModelManager  # noqa: E402
from app.core.Log import log_error, log_exception, log_info, log_success  # noqa: E402


TEST_PROMPT = (
    "/no_think\nResponde únicamente con la frase: MODELO LOCAL FUNCIONANDO"
)
EXPECTED_TEXT = "MODELO LOCAL FUNCIONANDO"
EMPTY_THINK_PATTERN = re.compile(r"<think>\s*</think>", re.IGNORECASE)


def is_expected_response(response: str) -> bool:
    """Tolera solo espacios y bloques ``think`` sin contenido."""

    without_empty_thinking = EMPTY_THINK_PATTERN.sub("", response)
    return without_empty_thinking.strip() == EXPECTED_TEXT


def main() -> int:
    """Ejecuta la prueba y retorna cero solo si aparece la frase esperada."""

    manager = ModelManager()
    local_llm = LocalLLM(manager)
    try:
        verification = manager.verify_model(DEFAULT_LLM_MODEL_ID)
        if not verification.verified:
            log_error(
                "El modelo no está listo para la prueba local",
                model_id=DEFAULT_LLM_MODEL_ID,
                relative_path=verification.relative_path,
                verification_status="failed",
            )
            return 1

        log_info("Iniciando prueba controlada de inferencia local", model_id=DEFAULT_LLM_MODEL_ID)
        local_llm.load()
        result = local_llm.generate(TEST_PROMPT).strip()
        sys.stdout.write(f"\nResultado de inferencia:\n{result}\n")
        if not is_expected_response(result):
            log_error(
                "La inferencia terminó sin la frase esperada",
                model_id=DEFAULT_LLM_MODEL_ID,
                output_length=len(result),
            )
            return 1
        log_success(
            "Prueba controlada de inferencia completada",
            model_id=DEFAULT_LLM_MODEL_ID,
            output_length=len(result),
        )
        return 0
    except Exception as exc:
        log_exception(
            "La prueba del modelo local terminó con error",
            model_id=DEFAULT_LLM_MODEL_ID,
            exception_type=type(exc).__name__,
        )
        return 1
    finally:
        local_llm.unload()


if __name__ == "__main__":
    raise SystemExit(main())
