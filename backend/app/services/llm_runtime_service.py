"""Ciclo de vida seguro de Qwen para generación local bajo demanda."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, Literal

from app.ai.local_llm import (
    LLMDependencyError,
    LLMGenerationBusyError,
    LLMGenerationError,
    LLMIntegrityError,
    LLMLoadError,
    LLMNotInstalledError,
    LLMNotLoadedError,
    LocalLLM,
    LocalLLMError,
    get_local_llm,
)
from app.core.Log import log_error, log_info
from app.core.config import settings


LoadOrigin = Literal["manual", "on_demand"]
RuntimeOperation = Literal["idle", "loading", "unloading", "error"]


class LlmRuntimeError(RuntimeError):
    """Error estable que no transporta rutas, prompts ni contenido."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class LlmRuntimeService:
    """Serializa cargas y protege el modelo mientras existe actividad."""

    def __init__(self, model: LocalLLM | None = None) -> None:
        self.model = model or get_local_llm()
        self._lock = asyncio.Lock()
        self._active_operations = 0
        self._idle_task: asyncio.Task[None] | None = None
        self._load_task: asyncio.Task[None] | None = None
        self._unload_task: asyncio.Task[None] | None = None
        self._generation_tasks: set[asyncio.Task[Any]] = set()
        self._load_origin: LoadOrigin | None = None
        self._operation: RuntimeOperation = "idle"
        self._shutting_down = False

    @property
    def active_operations(self) -> int:
        return self._active_operations

    @property
    def load_origin(self) -> LoadOrigin | None:
        return self._load_origin if self.model.is_loaded else None

    @property
    def operation(self) -> RuntimeOperation:
        if self._operation in {"loading", "unloading"}:
            return self._operation
        return "idle" if self.model.is_loaded or self._operation != "error" else "error"

    @property
    def busy(self) -> bool:
        return bool(
            self._active_operations
            or self._operation in {"loading", "unloading"}
            or (self._load_task is not None and not self._load_task.done())
            or (self._unload_task is not None and not self._unload_task.done())
        )

    async def explicit_load(self) -> None:
        await self._load("manual")

    async def explicit_unload(self) -> None:
        async with self._lock:
            if self._active_operations or self._generation_tasks:
                raise LlmRuntimeError("RAG_LLM_BUSY")
            if self._load_task is not None and not self._load_task.done():
                raise LlmRuntimeError("RAG_LLM_BUSY")
            self._cancel_idle_task()
            if not self.model.is_loaded:
                self._load_origin = None
                self._operation = "idle"
                return
            await self._unload_locked()

    async def ensure_loaded(self) -> bool:
        if self.model.is_loaded:
            return False
        if settings.llm_runtime_policy != "on_demand":
            raise LlmRuntimeError("RAG_LLM_NOT_LOADED")
        await self._load("on_demand")
        return True

    async def _load(self, origin: LoadOrigin) -> None:
        async with self._lock:
            if self._shutting_down:
                raise LlmRuntimeError("RAG_BACKEND_SHUTTING_DOWN")
            self._cancel_idle_task()
            if self.model.is_loaded:
                if origin == "manual":
                    self._load_origin = "manual"
                self._operation = "idle"
                return
            self._operation = "loading"
            self._load_origin = origin
            task = asyncio.create_task(asyncio.to_thread(self.model.load))
            self._load_task = task
            try:
                await asyncio.wait_for(
                    asyncio.shield(task), timeout=settings.llm_load_timeout_seconds
                )
            except TimeoutError as exc:
                self._operation = "error"
                task.add_done_callback(self._schedule_load_finalization)
                raise LlmRuntimeError("RAG_LLM_LOAD_TIMEOUT") from exc
            except asyncio.CancelledError:
                if task.done():
                    self._operation = "idle" if self.model.is_loaded else "error"
                    self._schedule_idle_unload_locked()
                else:
                    task.add_done_callback(self._schedule_load_finalization)
                raise
            except Exception as exc:
                self._operation = "error"
                self._load_origin = None
                raise self._map_load_error(exc) from exc
            finally:
                if task.done():
                    self._load_task = None
            if not self.model.is_loaded:
                self._operation = "error"
                self._load_origin = None
                raise LlmRuntimeError("RAG_LLM_LOAD_FAILED")
            self._operation = "idle"
            log_info(
                "Modelo generativo preparado",
                operation="llm_runtime_load",
                model_id=getattr(self.model, "model_id", "active-llm"),
                load_origin=origin,
            )

    @asynccontextmanager
    async def activity(self) -> AsyncIterator[bool]:
        automatic = await self.ensure_loaded()
        async with self._lock:
            if self._shutting_down:
                raise LlmRuntimeError("RAG_BACKEND_SHUTTING_DOWN")
            self._cancel_idle_task()
            self._active_operations += 1
        try:
            yield automatic
        finally:
            async with self._lock:
                self._active_operations = max(0, self._active_operations - 1)
                self._schedule_idle_unload_locked()

    async def generate_chat(
        self,
        generate: Callable[..., str],
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Ejecuta una generación bloqueante con timeout y retención segura."""

        task = asyncio.create_task(asyncio.to_thread(generate, *args, **kwargs))
        self._generation_tasks.add(task)
        try:
            return await asyncio.wait_for(
                asyncio.shield(task),
                timeout=settings.llm_generation_timeout_seconds,
            )
        except TimeoutError as exc:
            await self._retain_background_generation(task)
            raise LlmRuntimeError("RAG_GENERATION_TIMEOUT") from exc
        except asyncio.CancelledError:
            await self._retain_background_generation(task)
            raise
        except LLMGenerationBusyError as exc:
            raise LlmRuntimeError("RAG_GENERATION_BUSY") from exc
        except LLMNotLoadedError as exc:
            raise LlmRuntimeError("RAG_LLM_NOT_LOADED") from exc
        except LLMGenerationError as exc:
            raise LlmRuntimeError("RAG_GENERATION_ERROR") from exc
        except Exception as exc:
            raise LlmRuntimeError("RAG_GENERATION_ERROR") from exc
        finally:
            if task.done():
                self._generation_tasks.discard(task)

    async def shutdown(self) -> None:
        async with self._lock:
            self._shutting_down = True
            self._cancel_idle_task()
        pending = tuple(task for task in self._generation_tasks if not task.done())
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        async with self._lock:
            if self._load_origin == "on_demand" and self.model.is_loaded:
                await self._unload_locked()
            self._shutting_down = False

    async def _unload_locked(self) -> None:
        self._operation = "unloading"
        task = asyncio.create_task(asyncio.to_thread(self.model.unload))
        self._unload_task = task
        try:
            await task
        except Exception as exc:
            self._operation = "error"
            log_error(
                "No fue posible liberar el modelo generativo",
                operation="llm_runtime_unload",
                error_code="RAG_LLM_UNLOAD_FAILED",
            )
            raise LlmRuntimeError("RAG_LLM_UNLOAD_FAILED") from exc
        finally:
            self._unload_task = None
        self._load_origin = None
        self._operation = "idle"

    async def _unload_after_idle(self) -> None:
        try:
            await asyncio.sleep(settings.llm_idle_unload_seconds)
            async with self._lock:
                if (
                    self._active_operations == 0
                    and not self._generation_tasks
                    and self._load_origin == "on_demand"
                    and self.model.is_loaded
                ):
                    await self._unload_locked()
                    log_info(
                        "Modelo generativo liberado por inactividad",
                        operation="llm_idle_unload",
                    )
        except asyncio.CancelledError:
            return

    async def _retain_background_generation(self, task: asyncio.Task[Any]) -> None:
        if task.done():
            return
        async with self._lock:
            self._active_operations += 1
        task.add_done_callback(self._schedule_generation_release)

    def _schedule_generation_release(self, task: asyncio.Task[Any]) -> None:
        try:
            task.exception()
        except (asyncio.CancelledError, Exception):
            pass
        try:
            asyncio.get_running_loop().create_task(
                self._release_background_generation(task)
            )
        except RuntimeError:
            self._generation_tasks.discard(task)

    async def _release_background_generation(self, task: asyncio.Task[Any]) -> None:
        async with self._lock:
            self._generation_tasks.discard(task)
            self._active_operations = max(0, self._active_operations - 1)
            self._schedule_idle_unload_locked()

    def _schedule_load_finalization(self, task: asyncio.Task[None]) -> None:
        try:
            asyncio.get_running_loop().create_task(self._finalize_load(task))
        except RuntimeError:
            self._load_task = None

    async def _finalize_load(self, task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except Exception:
            pass
        async with self._lock:
            if self._load_task is task:
                self._load_task = None
            self._operation = "idle" if self.model.is_loaded else "error"
            if not self.model.is_loaded:
                self._load_origin = None
            self._schedule_idle_unload_locked()

    def _schedule_idle_unload_locked(self) -> None:
        if (
            self._active_operations == 0
            and not self._generation_tasks
            and self._load_origin == "on_demand"
            and self.model.is_loaded
            and not self._shutting_down
        ):
            self._cancel_idle_task()
            self._idle_task = asyncio.create_task(self._unload_after_idle())

    def _cancel_idle_task(self) -> None:
        task = self._idle_task
        self._idle_task = None
        if (
            task is not None
            and task is not asyncio.current_task()
            and not task.done()
        ):
            task.cancel()

    @staticmethod
    def _map_load_error(error: Exception) -> LlmRuntimeError:
        if isinstance(error, LLMNotInstalledError):
            return LlmRuntimeError("RAG_LLM_NOT_INSTALLED")
        if isinstance(
            error,
            (LLMDependencyError, LLMIntegrityError, LLMLoadError, LocalLLMError),
        ):
            return LlmRuntimeError("RAG_LLM_LOAD_FAILED")
        return LlmRuntimeError("RAG_LLM_LOAD_FAILED")


_llm_runtime: LlmRuntimeService | None = None


def get_llm_runtime_service() -> LlmRuntimeService:
    global _llm_runtime
    model = get_local_llm()
    if _llm_runtime is None or (
        _llm_runtime.model is not model and not _llm_runtime.busy
    ):
        _llm_runtime = LlmRuntimeService(model)
    return _llm_runtime


async def shutdown_llm_runtime_if_initialized() -> None:
    """Cierra el runtime existente sin crear el adaptador ni importar llama.cpp."""

    runtime = _llm_runtime
    if runtime is not None:
        await runtime.shutdown()
