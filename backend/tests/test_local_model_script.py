"""Pruebas del script manual sin cargar ni ejecutar el modelo real."""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "test_local_model.py"


def load_test_script() -> ModuleType:
    """Importa el script bajo un nombre que pytest no trata como módulo de prueba."""

    spec = importlib.util.spec_from_file_location("manual_local_model_test", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("No fue posible cargar el script de prueba local")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeModelManager:
    def verify_model(self, _: str) -> SimpleNamespace:
        return SimpleNamespace(
            verified=True,
            relative_path="models/llm/test/model.gguf",
        )


class FakeLocalLLM:
    def __init__(self, response: str = "MODELO LOCAL FUNCIONANDO") -> None:
        self.response = response
        self.loaded = False
        self.unloaded = False
        self.received_prompt: str | None = None
        self.generation_error: Exception | None = None

    def load(self) -> None:
        self.loaded = True

    def generate(self, prompt: str) -> str:
        self.received_prompt = prompt
        if self.generation_error is not None:
            raise self.generation_error
        return self.response

    def unload(self) -> None:
        self.unloaded = True


def test_manual_script_uses_no_think_and_always_unloads(
    monkeypatch,
    capsys,
) -> None:
    script = load_test_script()
    fake_llm = FakeLocalLLM("<think>\n\n</think>\n MODELO LOCAL FUNCIONANDO \n")
    monkeypatch.setattr(script, "ModelManager", FakeModelManager)
    monkeypatch.setattr(script, "LocalLLM", lambda _: fake_llm)

    exit_code = script.main()

    assert exit_code == 0
    assert fake_llm.loaded is True
    assert fake_llm.unloaded is True
    assert fake_llm.received_prompt == (
        "/no_think\nResponde únicamente con la frase: MODELO LOCAL FUNCIONANDO"
    )
    assert "MODELO LOCAL FUNCIONANDO" in capsys.readouterr().out


def test_manual_script_unloads_when_generation_fails(monkeypatch) -> None:
    script = load_test_script()
    fake_llm = FakeLocalLLM()
    fake_llm.generation_error = RuntimeError("fallo simulado")
    monkeypatch.setattr(script, "ModelManager", FakeModelManager)
    monkeypatch.setattr(script, "LocalLLM", lambda _: fake_llm)

    exit_code = script.main()

    assert exit_code == 1
    assert fake_llm.unloaded is True


def test_controlled_response_rejects_visible_reasoning_or_extra_text() -> None:
    script = load_test_script()

    assert script.is_expected_response("  MODELO LOCAL FUNCIONANDO\n") is True
    assert (
        script.is_expected_response(
            "<think>\n</think>\nMODELO LOCAL FUNCIONANDO"
        )
        is True
    )
    assert (
        script.is_expected_response(
            "<think>razonamiento visible</think>\nMODELO LOCAL FUNCIONANDO"
        )
        is False
    )
    assert script.is_expected_response("MODELO LOCAL FUNCIONANDO extra") is False
