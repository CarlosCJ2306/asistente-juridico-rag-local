"""Adaptador de carga diferida para ``llama_cpp.Llama``."""

from __future__ import annotations

import gc
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.ai.model_manager import DEFAULT_LLM_MODEL_ID, ModelManager, get_model_selection_store
from app.core.Log import log_error, log_info, log_success, log_warning
from app.core.config import settings


LlamaFactory = Callable[..., Any]
SYSTEM_MESSAGE = (
    "Eres un asistente preciso. Sigue exactamente las instrucciones del usuario."
)


@dataclass(frozen=True)
class LLMGenerationMetrics:
    """Metadatos agregados seguros de la última generación local."""

    finish_reason: str
    generated_token_count: int | None


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


class LLMGenerationBusyError(LocalLLMError):
    """Existe otra generación local en curso."""


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
        self._last_generation_metrics: LLMGenerationMetrics | None = None
        self._lock = threading.RLock()
        self._generation_lock = threading.Lock()
        self._n_threads = _reasonable_thread_count(settings.local_llm_threads)

    @property
    def is_loaded(self) -> bool:
        """Indica si la referencia en memoria está disponible."""

        with self._lock:
            return self._llm is not None

    @property
    def model_id(self) -> str:
        return self._model_id

    def select_model(self, model_id: str) -> None:
        """Cambia la próxima carga sin descargar ni cargar automáticamente."""

        with self._lock:
            if self._llm is not None:
                raise LocalLLMError("MODEL_CURRENTLY_LOADED")
            self._model_id = model_id

    def load(self) -> None:
        """Verifica y carga el GGUF una sola vez, bajo demanda."""

        with self._lock:
            if self._llm is not None:
                return
            verification = self._model_manager.verify_model(self._model_id)
            if not verification.installed:
                raise LLMNotInstalledError(
                    f"El modelo '{self._model_id}' no está instalado"
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
        return self.generate_chat(
            [
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=32,
            top_p=0.9,
            repeat_penalty=None,
            seed=42,
            input_length_override=len(prompt),
        )

    def count_tokens(self, text: str, *, add_bos: bool = False) -> int:
        """Cuenta tokens con el tokenizer del GGUF cargado."""

        return len(self.tokenize_text(text, add_bos=add_bos))

    def tokenize_text(self, text: str, *, add_bos: bool = False) -> list[int]:
        """Tokeniza texto con la instancia GGUF sin registrar contenido ni ids."""

        if self._generation_lock.locked():
            raise LLMGenerationBusyError("La generación local está ocupada")
        with self._lock:
            if self._llm is None:
                raise LLMNotLoadedError("El modelo local no está cargado")
            tokenize = getattr(self._llm, "tokenize", None)
            if not callable(tokenize):
                raise LLMGenerationError("El tokenizer local no está disponible")
            try:
                tokens = tokenize(text.encode("utf-8"), add_bos=add_bos)
            except Exception as exc:
                raise LLMGenerationError("No fue posible contar tokens") from exc
            if not isinstance(tokens, list):
                raise LLMGenerationError("El tokenizer devolvió una estructura inválida")
            if any(not isinstance(token, int) or isinstance(token, bool) for token in tokens):
                raise LLMGenerationError("El tokenizer devolvió ids inválidos")
            return tokens

    def truncate_text_to_tokens(self, text: str, max_tokens: int) -> str:
        """Trunca mediante tokens y decodifica sin producir Unicode inválido."""

        if isinstance(max_tokens, bool) or max_tokens <= 0:
            return ""
        tokens = self.tokenize_text(text)
        if len(tokens) <= max_tokens:
            return text
        with self._lock:
            if self._llm is None:
                raise LLMNotLoadedError("El modelo local no está cargado")
            detokenize = getattr(self._llm, "detokenize", None)
            if not callable(detokenize):
                raise LLMGenerationError("El detokenizer local no está disponible")
            selected = tokens[:max_tokens]
            while selected:
                try:
                    decoded = detokenize(selected)
                    if isinstance(decoded, bytes):
                        return decoded.decode("utf-8", errors="strict")
                    if isinstance(decoded, str):
                        return decoded
                    raise LLMGenerationError(
                        "El detokenizer devolvió una estructura inválida"
                    )
                except UnicodeDecodeError:
                    selected.pop()
                except LLMGenerationError:
                    raise
                except Exception as exc:
                    raise LLMGenerationError("No fue posible decodificar tokens") from exc
        return ""

    def count_chat_tokens(self, messages: list[dict[str, str]]) -> int:
        """Cuenta el prompt renderizado o aplica overhead conservador por mensaje."""

        if self._generation_lock.locked():
            raise LLMGenerationBusyError("La generación local está ocupada")
        with self._lock:
            if self._llm is None:
                raise LLMNotLoadedError("El modelo local no está cargado")
            renderer = getattr(self._llm, "apply_chat_template", None)
            if not callable(renderer):
                tokenizer = getattr(self._llm, "tokenizer_", None)
                renderer = getattr(tokenizer, "apply_chat_template", None)
            if callable(renderer):
                try:
                    try:
                        rendered = renderer(
                            messages,
                            tokenize=False,
                            add_generation_prompt=True,
                        )
                    except TypeError:
                        rendered = renderer(messages)
                except Exception as exc:
                    raise LLMGenerationError(
                        "No fue posible renderizar la plantilla de chat"
                    ) from exc
                if isinstance(rendered, list):
                    if all(isinstance(token, int) for token in rendered):
                        return len(rendered)
                    raise LLMGenerationError("La plantilla devolvió tokens inválidos")
                if isinstance(rendered, bytes):
                    rendered = rendered.decode("utf-8", errors="strict")
                if not isinstance(rendered, str):
                    raise LLMGenerationError("La plantilla de chat es inválida")
                return len(self.tokenize_text(rendered))
        content_tokens = sum(self.count_tokens(message["content"]) for message in messages)
        return content_tokens + (8 * len(messages)) + 4

    def generate_chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        top_p: float,
        repeat_penalty: float | None,
        seed: int | None = None,
        input_length_override: int | None = None,
    ) -> str:
        """Genera con dos mensajes controlados y la plantilla del GGUF."""

        input_length = input_length_override or sum(
            len(message.get("content", "")) for message in messages
        )
        if [message.get("role") for message in messages] != ["system", "user"]:
            raise ValueError("La generación requiere exactamente roles system y user")
        if any(not message.get("content", "").strip() for message in messages):
            raise ValueError("Los mensajes no pueden estar vacíos")
        if not self._generation_lock.acquire(blocking=False):
            raise LLMGenerationBusyError("La generación local está ocupada")
        try:
            with self._lock:
                if self._llm is None:
                    raise LLMNotLoadedError("El modelo local no está cargado")
                options: dict[str, Any] = {
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                    "stream": False,
                }
                if repeat_penalty is not None:
                    options["repeat_penalty"] = repeat_penalty
                if seed is not None:
                    options["seed"] = seed
                started_at = time.perf_counter()
                self._last_generation_metrics = None
                try:
                    result = self._llm.create_chat_completion(**options)
                    generated_text = self._extract_chat_content(result)
                    generation_metrics = self._extract_generation_metrics(result)
                    self._last_generation_metrics = generation_metrics
                except LLMGenerationError:
                    raise
                except Exception as exc:
                    raise LLMGenerationError("La generación local no pudo completarse") from exc
            log_success(
                "Generación local completada",
                model_id=self._model_id,
                generation_duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                input_length=input_length,
                output_length=len(generated_text),
                finish_reason=generation_metrics.finish_reason,
                generated_count=generation_metrics.generated_token_count,
            )
            return generated_text
        except LocalLLMError as exc:
            log_error(
                "Falló la generación con el modelo local",
                model_id=self._model_id,
                input_length=input_length,
                exception_type=type(exc).__name__,
            )
            raise
        finally:
            self._generation_lock.release()

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

    @staticmethod
    def _extract_generation_metrics(response: Any) -> LLMGenerationMetrics:
        """Normaliza finish_reason y usa solo usage.completion_tokens fiable."""

        finish_reason = "unknown"
        generated_token_count: int | None = None
        if isinstance(response, dict):
            choices = response.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                raw_reason = choices[0].get("finish_reason")
                if raw_reason in {"stop", "length"}:
                    finish_reason = raw_reason
            usage = response.get("usage")
            if isinstance(usage, dict):
                raw_count = usage.get("completion_tokens")
                if (
                    isinstance(raw_count, int)
                    and not isinstance(raw_count, bool)
                    and raw_count >= 0
                ):
                    generated_token_count = raw_count
        return LLMGenerationMetrics(finish_reason, generated_token_count)

    @property
    def last_generation_metrics(self) -> LLMGenerationMetrics | None:
        """Expone únicamente metadatos agregados; nunca texto o tokens."""

        with self._lock:
            return self._last_generation_metrics

    def unload(self) -> None:
        """Cierra el recurso cuando es posible y libera la referencia."""

        with self._lock:
            if self._llm is None:
                return
            loaded_model = self._llm
            self._llm = None
            self._last_generation_metrics = None
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
                selection = get_model_selection_store().read()
                _local_llm_instance = LocalLLM(model_id=selection.active_llm_model_id)
    return _local_llm_instance


def is_local_llm_loaded() -> bool:
    """Consulta el estado sin crear el adaptador compartido ni cargar el GGUF."""

    with _local_llm_instance_lock:
        instance = _local_llm_instance
    return instance.is_loaded if instance is not None else False
