from __future__ import annotations

import asyncio
import time

import pytest

from app.ai.local_llm import LLMNotInstalledError
from app.services import llm_runtime_service as runtime_module
from app.services.llm_runtime_service import LlmRuntimeError, LlmRuntimeService


class FakeLocalLlm:
    def __init__(self, *, load_delay: float = 0.0) -> None:
        self.model_id = "synthetic-llm"
        self.is_loaded = False
        self.load_delay = load_delay
        self.load_calls = 0
        self.unload_calls = 0
        self.generation_calls = 0

    def load(self) -> None:
        self.load_calls += 1
        if self.load_delay:
            time.sleep(self.load_delay)
        self.is_loaded = True

    def unload(self) -> None:
        self.unload_calls += 1
        self.is_loaded = False

    def generate(self, delay: float = 0.0) -> str:
        self.generation_calls += 1
        if delay:
            time.sleep(delay)
        return "synthetic"


def test_concurrent_activity_loads_model_exactly_once(monkeypatch) -> None:
    async def scenario() -> None:
        model = FakeLocalLlm(load_delay=0.02)
        runtime = LlmRuntimeService(model)  # type: ignore[arg-type]
        monkeypatch.setattr(runtime_module.settings, "llm_runtime_policy", "on_demand")

        async def operation() -> None:
            async with runtime.activity():
                await asyncio.sleep(0.01)

        await asyncio.gather(operation(), operation())
        assert model.load_calls == 1
        assert runtime.load_origin == "on_demand"

    asyncio.run(scenario())


def test_loaded_model_is_reused_without_new_load(monkeypatch) -> None:
    async def scenario() -> None:
        model = FakeLocalLlm()
        model.is_loaded = True
        runtime = LlmRuntimeService(model)  # type: ignore[arg-type]
        monkeypatch.setattr(runtime_module.settings, "llm_runtime_policy", "on_demand")
        async with runtime.activity() as automatic:
            assert not automatic
        assert model.load_calls == 0

    asyncio.run(scenario())


def test_manual_policy_preserves_explicit_load_requirement(monkeypatch) -> None:
    async def scenario() -> None:
        model = FakeLocalLlm()
        runtime = LlmRuntimeService(model)  # type: ignore[arg-type]
        monkeypatch.setattr(runtime_module.settings, "llm_runtime_policy", "manual")
        with pytest.raises(LlmRuntimeError, match="RAG_LLM_NOT_LOADED"):
            async with runtime.activity():
                pass
        assert model.load_calls == 0
        await runtime.explicit_load()
        assert runtime.load_origin == "manual"

    asyncio.run(scenario())


def test_on_demand_model_unloads_only_after_real_inactivity(monkeypatch) -> None:
    async def scenario() -> None:
        model = FakeLocalLlm()
        runtime = LlmRuntimeService(model)  # type: ignore[arg-type]
        monkeypatch.setattr(runtime_module.settings, "llm_runtime_policy", "on_demand")
        monkeypatch.setattr(runtime_module.settings, "llm_idle_unload_seconds", 0.01)
        async with runtime.activity():
            await asyncio.sleep(0.03)
            assert model.is_loaded
            assert model.unload_calls == 0
            with pytest.raises(LlmRuntimeError, match="RAG_LLM_BUSY"):
                await runtime.explicit_unload()
        await asyncio.sleep(0.1)
        assert not model.is_loaded
        assert model.unload_calls == 1

    asyncio.run(scenario())


def test_load_timeout_does_not_leave_runtime_permanently_loading(monkeypatch) -> None:
    async def scenario() -> None:
        model = FakeLocalLlm(load_delay=0.04)
        runtime = LlmRuntimeService(model)  # type: ignore[arg-type]
        monkeypatch.setattr(runtime_module.settings, "llm_runtime_policy", "on_demand")
        monkeypatch.setattr(runtime_module.settings, "llm_load_timeout_seconds", 0.01)
        with pytest.raises(LlmRuntimeError, match="RAG_LLM_LOAD_TIMEOUT"):
            await runtime.ensure_loaded()
        assert runtime.operation == "error"
        await asyncio.sleep(0.06)
        assert model.is_loaded
        assert runtime.operation == "idle"
        await runtime.shutdown()
        assert not model.is_loaded

    asyncio.run(scenario())


def test_generation_timeout_keeps_model_protected_until_worker_finishes(
    monkeypatch,
) -> None:
    async def scenario() -> None:
        model = FakeLocalLlm()
        runtime = LlmRuntimeService(model)  # type: ignore[arg-type]
        monkeypatch.setattr(runtime_module.settings, "llm_runtime_policy", "on_demand")
        monkeypatch.setattr(runtime_module.settings, "llm_generation_timeout_seconds", 0.01)
        monkeypatch.setattr(runtime_module.settings, "llm_idle_unload_seconds", 0.01)
        with pytest.raises(LlmRuntimeError, match="RAG_GENERATION_TIMEOUT"):
            async with runtime.activity():
                await runtime.generate_chat(model.generate, 0.05)
        assert runtime.active_operations == 1
        assert model.unload_calls == 0
        await asyncio.sleep(0.2)
        assert runtime.active_operations == 0
        assert model.unload_calls == 1

    asyncio.run(scenario())


def test_client_cancellation_keeps_generation_protected_and_recovers(
    monkeypatch,
) -> None:
    async def scenario() -> None:
        model = FakeLocalLlm()
        runtime = LlmRuntimeService(model)  # type: ignore[arg-type]
        monkeypatch.setattr(runtime_module.settings, "llm_runtime_policy", "on_demand")
        monkeypatch.setattr(runtime_module.settings, "llm_idle_unload_seconds", 0.01)

        async def request() -> None:
            async with runtime.activity():
                await runtime.generate_chat(model.generate, 0.05)

        task = asyncio.create_task(request())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert model.unload_calls == 0
        await asyncio.sleep(0.2)
        assert runtime.active_operations == 0
        assert model.unload_calls == 1

    asyncio.run(scenario())


def test_missing_model_returns_stable_safe_error(monkeypatch) -> None:
    class MissingModel(FakeLocalLlm):
        def load(self) -> None:
            raise LLMNotInstalledError("sensitive internal detail")

    async def scenario() -> None:
        runtime = LlmRuntimeService(MissingModel())  # type: ignore[arg-type]
        monkeypatch.setattr(runtime_module.settings, "llm_runtime_policy", "on_demand")
        with pytest.raises(LlmRuntimeError) as captured:
            await runtime.ensure_loaded()
        assert captured.value.code == "RAG_LLM_NOT_INSTALLED"
        assert str(captured.value) == "RAG_LLM_NOT_INSTALLED"
        assert runtime.operation == "error"

    asyncio.run(scenario())
