"""Adaptador perezoso y local de Sentence Transformers para embeddings."""

from __future__ import annotations

import gc
import math
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from numbers import Integral
from typing import Any, Literal
from uuid import UUID

from app.ai.model_manager import ModelManager
from app.core.Log import log_error, log_info, log_success
from app.core.config import settings


EMBEDDING_MODEL_ID = "multilingual-e5-small"
EmbeddingState = Literal["unloaded", "loading", "loaded", "error"]


class EmbeddingError(RuntimeError):
    """Fallo seguro de embeddings que no expone texto, vectores ni rutas."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class EmbeddedChunk:
    chunk_id: UUID
    chunk_index: int
    document_id: UUID
    vector: list[float]
    dimension: int


class EmbeddingModel:
    """Carga local única y generación normalizada sin persistir vectores."""

    def __init__(
        self,
        model_manager: ModelManager | None = None,
        *,
        loader_factory: Callable[..., Any] | None = None,
        configured_path: str | None = None,
        batch_size: int = settings.embedding_batch_size,
        device: str = settings.embedding_device,
        normalize: bool = settings.embedding_normalize,
    ) -> None:
        self.model_manager = model_manager or ModelManager()
        self._loader_factory = loader_factory
        self._configured_path = configured_path or str(settings.embedding_model_path)
        self.batch_size = batch_size
        self.device = device
        self.normalize = normalize
        self._model: Any | None = None
        self._dimension: int | None = None
        self._state: EmbeddingState = "unloaded"
        self._lock = threading.RLock()

    @property
    def state(self) -> EmbeddingState:
        return self._state

    @property
    def dimension(self) -> int | None:
        return self._dimension

    @property
    def configured_path(self) -> str:
        """Ruta configurada, solo para reutilizar la validación central."""

        return self._configured_path

    @property
    def is_loaded(self) -> bool:
        return self._state == "loaded" and self._model is not None

    def load(self) -> None:
        """Carga el modelo solo desde archivos locales y de forma idempotente."""

        if not self._lock.acquire(blocking=False):
            raise EmbeddingError("EMBEDDING_MODEL_BUSY")
        try:
            if self.is_loaded:
                return
            verification = self.model_manager.verify_model(
                EMBEDDING_MODEL_ID,
                calculate_hash=False,
                configured_path=self._configured_path,
            )
            if not verification.verified:
                self._state = "error"
                code = (
                    "EMBEDDING_MODEL_PATH_MISMATCH"
                    if "EMBEDDING_MODEL_PATH_MISMATCH" in verification.errors
                    else "EMBEDDING_MODEL_NOT_FOUND"
                )
                raise EmbeddingError(code)
            self._state = "loading"
            try:
                factory = self._loader_factory or self._import_sentence_transformer()
                path = self.model_manager.resolve_embedding_model_path(self._configured_path)
                self._model = factory(
                    str(path),
                    device=self.device,
                    local_files_only=True,
                    trust_remote_code=False,
                )
                dimension = self._embedding_dimension(self._model)
                self._dimension = dimension
                self._state = "loaded"
                log_success(
                    "Modelo local de embeddings cargado",
                    operation="embedding_model_load",
                    model_id=EMBEDDING_MODEL_ID,
                    device=self.device,
                    dimension=dimension,
                )
            except EmbeddingError:
                self._state = "error"
                raise
            except Exception as exc:
                self._model = None
                self._dimension = None
                self._state = "error"
                log_error(
                    "No fue posible cargar el modelo de embeddings",
                    operation="embedding_model_load",
                    model_id=EMBEDDING_MODEL_ID,
                    exception_type=type(exc).__name__,
                )
                raise EmbeddingError("EMBEDDING_MODEL_LOAD_ERROR") from exc
        finally:
            self._lock.release()

    @staticmethod
    def _embedding_dimension(model: Any) -> int:
        """Obtiene la dimensión usando primero la API moderna disponible."""

        modern = getattr(model, "get_embedding_dimension", None)
        if callable(modern):
            raw_dimension = modern()
        else:
            legacy = getattr(model, "get_sentence_embedding_dimension", None)
            if not callable(legacy):
                raise EmbeddingError("EMBEDDING_DIMENSION_UNAVAILABLE")
            raw_dimension = legacy()
        if isinstance(raw_dimension, bool) or not isinstance(raw_dimension, Integral):
            raise EmbeddingError("EMBEDDING_DIMENSION_INVALID")
        dimension = int(raw_dimension)
        if dimension <= 0:
            raise EmbeddingError("EMBEDDING_DIMENSION_INVALID")
        return dimension

    @staticmethod
    def _import_sentence_transformer() -> Callable[..., Any]:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError as exc:
            raise EmbeddingError("EMBEDDING_DEPENDENCY_MISSING") from exc
        return SentenceTransformer

    def unload(self) -> None:
        """Libera referencias; es seguro cuando el modelo ya estaba descargado."""

        with self._lock:
            self._model = None
            self._dimension = None
            self._state = "unloaded"
            gc.collect()
            if self.device.startswith("cuda"):
                try:
                    import torch  # type: ignore[import-not-found]

                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except ImportError:
                    pass
            log_info("Modelo de embeddings liberado", operation="embedding_model_unload", model_id=EMBEDDING_MODEL_ID)

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        """Codifica por lotes, valida salida y preserva el orden de entrada."""

        if not texts:
            return []
        if not self.is_loaded or self._model is None:
            raise EmbeddingError("EMBEDDING_MODEL_NOT_LOADED")
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start : start + self.batch_size])
            try:
                encoded = self._model.encode(
                    batch,
                    batch_size=self.batch_size,
                    convert_to_numpy=True,
                    normalize_embeddings=False,
                    show_progress_bar=False,
                )
            except Exception as exc:
                raise EmbeddingError("EMBEDDING_GENERATION_ERROR") from exc
            batch_vectors = self._validate_vectors(encoded)
            if len(batch_vectors) != len(batch):
                raise EmbeddingError("EMBEDDING_OUTPUT_INVALID")
            vectors.extend(batch_vectors)
        return vectors

    def _validate_vectors(self, encoded: Sequence[Sequence[float]]) -> list[list[float]]:
        vectors: list[list[float]] = []
        expected_dimension = self._dimension
        for vector in encoded:
            values = [float(value) for value in vector]
            if not values or not all(math.isfinite(value) for value in values):
                raise EmbeddingError("EMBEDDING_OUTPUT_INVALID")
            if expected_dimension is None:
                expected_dimension = len(values)
            if len(values) != expected_dimension:
                raise EmbeddingError("EMBEDDING_OUTPUT_INVALID")
            if self.normalize:
                norm = math.sqrt(sum(value * value for value in values))
                if not math.isfinite(norm) or norm == 0:
                    raise EmbeddingError("EMBEDDING_OUTPUT_INVALID")
                values = [value / norm for value in values]
            vectors.append(values)
        self._dimension = expected_dimension
        return vectors


_embedding_model: EmbeddingModel | None = None
_embedding_model_lock = threading.Lock()


def get_embedding_model() -> EmbeddingModel:
    """Obtiene el adaptador compartido sin cargar dependencias ni pesos."""

    global _embedding_model
    with _embedding_model_lock:
        if _embedding_model is None:
            _embedding_model = EmbeddingModel()
        return _embedding_model
