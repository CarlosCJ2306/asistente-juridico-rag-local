"""Ciclo de vida local y reutilizable del modelo de embeddings."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.ai.embedding_model import EmbeddingError, EmbeddingModel, get_embedding_model
from app.core.Log import log_info
from app.core.config import settings


class EmbeddingRuntimeService:
    """Protege cargas bajo demanda y descarga solo tras inactividad real."""

    def __init__(self, model: EmbeddingModel | None = None) -> None:
        self.model = model or get_embedding_model()
        self._lock = asyncio.Lock()
        self._active_operations = 0
        self._idle_task: asyncio.Task[None] | None = None
        self._automatically_loaded = False

    @property
    def automatically_loaded(self) -> bool:
        return self._automatically_loaded and self.model.is_loaded

    @property
    def active_operations(self) -> int:
        return self._active_operations

    async def explicit_load(self) -> None:
        async with self._lock:
            self._cancel_idle_task()
            await asyncio.to_thread(self.model.load)
            self._automatically_loaded = False

    async def explicit_unload(self) -> None:
        async with self._lock:
            if self._active_operations:
                raise EmbeddingError("EMBEDDING_MODEL_BUSY")
            self._cancel_idle_task()
            await asyncio.to_thread(self.model.unload)
            self._automatically_loaded = False

    async def ensure_loaded(self) -> bool:
        """Carga únicamente el modelo activo ya instalado cuando la política lo permite."""

        if self.model.is_loaded:
            return False
        if settings.embedding_runtime_policy != "on_demand":
            raise EmbeddingError("EMBEDDING_MODEL_NOT_LOADED")
        async with self._lock:
            if self.model.is_loaded:
                return False
            await asyncio.to_thread(self.model.load)
            self._automatically_loaded = True
            log_info(
                "Modelo de embeddings preparado bajo demanda",
                operation="embedding_on_demand_load",
                model_id=self.model.model_id,
            )
            return True

    @asynccontextmanager
    async def activity(self) -> AsyncIterator[bool]:
        automatic = await self.ensure_loaded()
        async with self._lock:
            self._cancel_idle_task()
            self._active_operations += 1
        try:
            yield automatic
        finally:
            async with self._lock:
                self._active_operations = max(0, self._active_operations - 1)
                if self._active_operations == 0 and self._automatically_loaded:
                    self._idle_task = asyncio.create_task(self._unload_after_idle())

    async def shutdown(self) -> None:
        async with self._lock:
            self._cancel_idle_task()
            if self._automatically_loaded and self._active_operations == 0:
                await asyncio.to_thread(self.model.unload)
                self._automatically_loaded = False

    async def _unload_after_idle(self) -> None:
        try:
            await asyncio.sleep(settings.embedding_idle_unload_seconds)
            async with self._lock:
                if self._active_operations == 0 and self._automatically_loaded:
                    await asyncio.to_thread(self.model.unload)
                    self._automatically_loaded = False
                    log_info(
                        "Modelo de embeddings liberado por inactividad",
                        operation="embedding_idle_unload",
                    )
        except asyncio.CancelledError:
            return

    def _cancel_idle_task(self) -> None:
        task = self._idle_task
        self._idle_task = None
        if task is not None and not task.done():
            task.cancel()


_embedding_runtime: EmbeddingRuntimeService | None = None


def get_embedding_runtime_service() -> EmbeddingRuntimeService:
    global _embedding_runtime
    model = get_embedding_model()
    if (
        _embedding_runtime is None
        or (
            _embedding_runtime.model is not model
            and _embedding_runtime.active_operations == 0
        )
    ):
        _embedding_runtime = EmbeddingRuntimeService(model)
    return _embedding_runtime
