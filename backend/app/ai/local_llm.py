"""Adaptador de carga diferida para ``llama_cpp.Llama``."""

from __future__ import annotations

import gc
import os
import threading
import time
from collections.abc import Callable
from typing import Any

from app.ai.model_manager import DEFAULT_LLM_MODEL_ID, ModelManager
from app.core.Log import log_error, log_info, log_success, log_warning
from app.core.config import settings


LlamaFactory = Callable[..., Any]
SYSTEM_MESSAGE = (
    "Eres un asistente preciso. Sigue exactamente las instrucciones del usuario."
)


class LocalLLMError(RuntimeError):
    """Error base del adaptador local."""


class LLMDependencyError(LocalLLMError):
    """llama-cpp-python no está disponible."""


class LLMNotInstalledError(LocalLLMError):
    """El archivo GGUF no está instalado."""


class LLMIntegrityError(LocalLLMError):
    """El archivo GGUF no supera la verificación."""


class LLMNotLoadedError(LocalLLMError):
    """Se solicitó inferencia sin cargar primero el modelo."""


class LLMLoadError(LocalLLMError):
    """llama-cpp-python no pudo cargar el modelo."""


class LLMGenerationError(LocalLLMError):
    """Falló una generación local."""


def _default_llama_factory(**kwargs: Any) -> Any:
    """Importa llama-cpp-python únicamente cuando ``load`` lo necesita."""

    try:
        from llama_cpp import Llama
    except ImportError as exc:
        raise LLMDependencyError(
            "llama-cpp-python no está instalado; instale requirements-llm.txt"
        ) from exc
    return Llama(**kwargs)


def _reasonable_thread_count(configured_threads: int) -> int:
    if configured_threads > 0:
        return configured_threads
    available = os.cpu_count() or 2
    return max(1, min(8, available - 1))


class LocalLLM:
    """Mantiene una única instancia reutilizable y protegida por un lock."""

    def __init__(
        self,
        model_manager: ModelManager | None = None,
        *,
        model_id: str = DEFAULT_LLM_MODEL_ID,
        llama_factory: LlamaFactory | None = None,
    ) -> None:
        self._model_manager = model_manager or ModelManager()
        self._model_id = model_id
        self._llama_factory = llama_factory or _default_llama_factory
        self._llm: Any | None = None
        self._lock = threading.RLock()
        self._n_threads = _reasonable_thread_count(settings.local_llm_threads)

    @property
    def is_loaded(self) -> bool:
        """Indica si la referencia en memoria está disponible."""

        with self._lock:
            return self._llm is not None

    def load(self) -> None:
        """Verifica y carga el GGUF una sola vez, bajo demanda."""

        with self._lock:
            if self._llm is not None:
                return
            verification = self._model_manager.verify_model(self._model_id)
            if not verification.installed:
                raise LLMNotInstalledError(
                    f"El modelo '{self._model_id}' no está instalado en "
                    f"{verification.relative_path}"
                )
            if not verification.verified:
                details = "; ".join(verification.errors)
                raise LLMIntegrityError(
                    f"El modelo '{self._model_id}' no superó la verificación: {details}"
                )

            model_path = self._model_manager.resolve_model_path(self._model_id)
            started_at = time.perf_counter()
            log_info(
                "Cargando modelo generativo local",
                model_id=self._model_id,
                relative_path=verification.relative_path,
                file_size=verification.file_size,
                n_ctx=settings.local_llm_context_size,
                n_threads=self._n_threads,
                n_gpu_layers=settings.local_llm_gpu_layers,
            )
            try:
                loaded_model = self._llama_factory(
                    model_path=str(model_path),
                    n_ctx=settings.local_llm_context_size,
                    n_threads=self._n_threads,
                    n_gpu_layers=settings.local_llm_gpu_layers,
                    verbose=settings.local_llm_verbose,
                )
            except LocalLLMError:
                raise
            except Exception as exc:
                log_error(
                    "No fue posible cargar el modelo generativo local",
                    model_id=self._model_id,
                    exception_type=type(exc).__name__,
                )
                raise LLMLoadError(
                    f"llama-cpp-python no pudo cargar el modelo '{self._model_id}'"
                ) from exc
            self._llm = loaded_model
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_success(
                "Modelo generativo local cargado",
                model_id=self._model_id,
                load_duration_ms=duration_ms,
            )

    def generate(self, prompt: str) -> str:
        """Genera mediante la plantilla de chat del GGUF sin registrar contenido."""

        if not prompt.strip():
            raise ValueError("El prompt no puede estar vacío")
        with self._lock:
            if self._llm is None:
                raise LLMNotLoadedError(
                    "El modelo local no está cargado; invoque load() antes de generate()"
                )
            started_at = time.perf_counter()
            try:
                result = self._llm.create_chat_completion(
                    messages=[
                        {"role": "system", "content": SYSTEM_MESSAGE},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    max_tokens=32,
                    top_p=0.9,
                    seed=42,
                )
                generated_text = self._extract_chat_content(result)
            except LLMGenerationError as exc:
                log_error(
                    "La respuesta conversacional del modelo tiene una estructura inválida",
                    model_id=self._model_id,
                    input_length=len(prompt),
                    exception_type=type(exc).__name__,
                )
                raise
            except Exception as exc:
                log_error(
                    "Falló la generación con el modelo local",
                    model_id=self._model_id,
                    input_length=len(prompt),
                    exception_type=type(exc).__name__,
                )
                raise LLMGenerationError("La generación local no pudo completarse") from exc

            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_success(
                "Generación local completada",
                model_id=self._model_id,
                generation_duration_ms=duration_ms,
                input_length=len(prompt),
                output_length=len(generated_text),
            )
            return generated_text

    @staticmethod
    def _extract_chat_content(response: Any) -> str:
        """Extrae ``choices[0].message.content`` con validación defensiva."""

        if not isinstance(response, dict):
            raise LLMGenerationError(
                "La respuesta conversacional no es un objeto válido"
            )
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMGenerationError(
                "La respuesta conversacional no contiene choices válidos"
            )
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise LLMGenerationError(
                "La primera opción de la respuesta conversacional no es válida"
            )
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise LLMGenerationError(
                "La respuesta conversacional no contiene un message válido"
            )
        content = message.get("content")
        if not isinstance(content, str):
            raise LLMGenerationError(
                "El content de la respuesta conversacional no es texto"
            )
        if not content.strip():
            raise LLMGenerationError("La respuesta conversacional está vacía")
        return content

    def unload(self) -> None:
        """Cierra el recurso cuando es posible y libera la referencia."""

        with self._lock:
            if self._llm is None:
                return
            loaded_model = self._llm
            self._llm = None
            close_method = getattr(loaded_model, "close", None)
            if callable(close_method):
                try:
                    close_method()
                except Exception as exc:
                    log_warning(
                        "El modelo se liberó con error durante close()",
                        model_id=self._model_id,
                        exception_type=type(exc).__name__,
                    )
            del loaded_model
            gc.collect()
            log_info("Modelo generativo local descargado de memoria", model_id=self._model_id)

    def model_info(self) -> dict[str, object]:
        """Devuelve información técnica segura, sin rutas absolutas."""

        metadata = self._model_manager.safe_metadata(self._model_id)
        metadata.update(
            {
                "loaded": self.is_loaded,
                "context_size": settings.local_llm_context_size,
                "threads": self._n_threads,
                "gpu_layers": settings.local_llm_gpu_layers,
            }
        )
        return metadata


_local_llm_instance: LocalLLM | None = None
_local_llm_instance_lock = threading.Lock()


def get_local_llm() -> LocalLLM:
    """Obtiene el adaptador compartido sin cargar llama-cpp-python ni el GGUF."""

    global _local_llm_instance
    if _local_llm_instance is None:
        with _local_llm_instance_lock:
            if _local_llm_instance is None:
                _local_llm_instance = LocalLLM()
    return _local_llm_instance


def is_local_llm_loaded() -> bool:
    """Consulta el estado sin crear el adaptador compartido ni cargar el GGUF."""

    with _local_llm_instance_lock:
        instance = _local_llm_instance
    return instance.is_loaded if instance is not None else False
