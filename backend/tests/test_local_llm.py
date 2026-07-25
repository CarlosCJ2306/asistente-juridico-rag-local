"""Pruebas del adaptador llama-cpp sin cargar una biblioteca o modelo real."""

import importlib
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from app.ai import local_llm as local_llm_module


class FakeLlama:
    def __init__(self, response: object | None = None) -> None:
        self.closed = False
        self.chat_calls: list[dict[str, object]] = []
        self.response = (
            response
            if response is not None
            else {
                "choices": [
                    {"message": {"content": "MODELO LOCAL FUNCIONANDO"}}
                ]
            }
        )

    def __call__(self, *_: object, **__: object) -> object:
        raise AssertionError("No debe utilizarse completado de texto crudo")

    def create_chat_completion(self, **kwargs: object) -> object:
        self.chat_calls.append(kwargs)
        return self.response

    def tokenize(self, content: bytes, *, add_bos: bool = False) -> list[int]:
        del add_bos
        return list(content)

    def detokenize(self, tokens: list[int]) -> bytes:
        return bytes(tokens)

    def close(self) -> None:
        self.closed = True


def test_import_does_not_create_or_load_llm() -> None:
    reloaded_module = importlib.reload(local_llm_module)

    assert reloaded_module._local_llm_instance is None


def test_missing_model_raises_clear_error(model_project_factory) -> None:
    manager, _ = model_project_factory()
    factory = Mock()
    local_llm = local_llm_module.LocalLLM(manager, llama_factory=factory)

    with pytest.raises(local_llm_module.LLMNotInstalledError, match="no está instalado"):
        local_llm.load()

    factory.assert_not_called()
    assert local_llm.is_loaded is False


def test_load_generate_and_unload_use_mock_only(model_project_factory) -> None:
    manager, model_path = model_project_factory()
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"GGUFcontenido-valido")
    fake_llama = FakeLlama()
    factory = Mock(return_value=fake_llama)
    local_llm = local_llm_module.LocalLLM(manager, llama_factory=factory)

    local_llm.load()
    result = local_llm.generate("Prompt controlado")

    assert local_llm.is_loaded is True
    assert local_llm.count_tokens("á") == len("á".encode("utf-8"))
    assert result == "MODELO LOCAL FUNCIONANDO"
    assert len(fake_llama.chat_calls) == 1
    chat_options = fake_llama.chat_calls[0]
    assert chat_options["messages"] == [
        {
            "role": "system",
            "content": (
                "Eres un asistente preciso. "
                "Sigue exactamente las instrucciones del usuario."
            ),
        },
        {"role": "user", "content": "Prompt controlado"},
    ]
    assert chat_options["temperature"] == 0.0
    assert chat_options["max_tokens"] == 32
    assert chat_options["top_p"] == 0.9
    assert chat_options["seed"] == 42
    factory.assert_called_once()
    call_options = factory.call_args.kwargs
    assert call_options["n_ctx"] == 4096
    assert call_options["n_gpu_layers"] == 0
    assert call_options["verbose"] is False
    assert call_options["n_threads"] >= 1

    local_llm.unload()
    assert local_llm.is_loaded is False
    assert fake_llama.closed is True


def test_concurrent_load_reuses_a_single_instance(model_project_factory) -> None:
    manager, model_path = model_project_factory()
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"GGUFcontenido-valido")
    fake_llama = FakeLlama()
    factory = Mock(return_value=fake_llama)
    local_llm = local_llm_module.LocalLLM(manager, llama_factory=factory)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: local_llm.load(), range(4)))

    factory.assert_called_once()
    assert local_llm.is_loaded is True
    local_llm.unload()


@pytest.mark.parametrize(
    ("response", "expected_error"),
    [
        ({}, "choices válidos"),
        ({"choices": []}, "choices válidos"),
        ({"choices": [{}]}, "message válido"),
        ({"choices": [{"message": {}}]}, "no es texto"),
        ({"choices": [{"message": {"content": None}}]}, "no es texto"),
        ({"choices": [{"message": {"content": "   \n"}}]}, "está vacía"),
    ],
)
def test_malformed_chat_response_raises_clear_error(
    model_project_factory,
    response: object,
    expected_error: str,
) -> None:
    manager, model_path = model_project_factory()
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"GGUFcontenido-valido")
    fake_llama = FakeLlama(response)
    local_llm = local_llm_module.LocalLLM(
        manager,
        llama_factory=Mock(return_value=fake_llama),
    )
    local_llm.load()

    with pytest.raises(local_llm_module.LLMGenerationError, match=expected_error):
        local_llm.generate("Prompt controlado")

    local_llm.unload()


def test_generation_logs_only_safe_metadata(
    model_project_factory,
    monkeypatch,
) -> None:
    manager, model_path = model_project_factory()
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"GGUFcontenido-valido")
    secret_response = "RESPUESTA_COMPLETA_NO_REGISTRAR"
    fake_llama = FakeLlama(
        {"choices": [{"message": {"content": secret_response}}]}
    )
    local_llm = local_llm_module.LocalLLM(
        manager,
        llama_factory=Mock(return_value=fake_llama),
    )
    local_llm.load()
    success_log = Mock()
    error_log = Mock()
    monkeypatch.setattr(local_llm_module, "log_success", success_log)
    monkeypatch.setattr(local_llm_module, "log_error", error_log)
    secret_prompt = "PROMPT_COMPLETO_NO_REGISTRAR"

    result = local_llm.generate(secret_prompt)

    assert result == secret_response
    logged_data = repr(success_log.call_args_list) + repr(error_log.call_args_list)
    assert secret_prompt not in logged_data
    assert secret_response not in logged_data
    assert success_log.call_args.kwargs["model_id"] == "qwen3-1.7b-q4-k-m"
    assert success_log.call_args.kwargs["input_length"] == len(secret_prompt)
    assert success_log.call_args.kwargs["output_length"] == len(secret_response)
    assert "generation_duration_ms" in success_log.call_args.kwargs
    local_llm.unload()


def test_qwen_tokenizer_counts_truncates_and_preserves_unicode(model_project_factory) -> None:
    manager, model_path = model_project_factory()
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"GGUFcontenido-valido")
    local_llm = local_llm_module.LocalLLM(
        manager, llama_factory=Mock(return_value=FakeLlama())
    )
    with pytest.raises(local_llm_module.LLMNotLoadedError):
        local_llm.count_tokens("acción")
    local_llm.load()
    assert local_llm.count_tokens("acción") == len("acción".encode())
    assert local_llm.truncate_text_to_tokens("acción", 4) == "acci"
    local_llm.unload()


def test_chat_token_count_uses_loaded_gguf_template(model_project_factory) -> None:
    class TemplatedLlama(FakeLlama):
        def apply_chat_template(self, messages, **kwargs):
            del messages, kwargs
            return "plantilla-real"

    manager, model_path = model_project_factory()
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"GGUFcontenido-valido")
    local_llm = local_llm_module.LocalLLM(
        manager, llama_factory=Mock(return_value=TemplatedLlama())
    )
    local_llm.load()
    count = local_llm.count_chat_tokens(
        [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    )
    assert count == len("plantilla-real".encode())
    local_llm.unload()


def test_generation_lock_is_nonblocking_and_released_after_error(model_project_factory) -> None:
    manager, model_path = model_project_factory()
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"GGUFcontenido-valido")
    local_llm = local_llm_module.LocalLLM(
        manager, llama_factory=Mock(return_value=FakeLlama(response={})),
    )
    local_llm.load()
    local_llm._generation_lock.acquire()
    try:
        with pytest.raises(local_llm_module.LLMGenerationBusyError):
            local_llm.count_tokens("x")
    finally:
        local_llm._generation_lock.release()
    with pytest.raises(local_llm_module.LLMGenerationError):
        local_llm.generate("x")
    assert local_llm._generation_lock.acquire(blocking=False)
    local_llm._generation_lock.release()
    local_llm.unload()
