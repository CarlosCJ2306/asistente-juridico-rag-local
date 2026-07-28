"""El estado de modelos debe ser seguro y no provocar carga del LLM."""

from fastapi.testclient import TestClient

from app.ai import local_llm as local_llm_module
from app.api.routes import models as models_routes
from app.main import app


def test_models_status_is_safe_and_does_not_load(
    model_project_factory,
    monkeypatch,
) -> None:
    manager, _ = model_project_factory()
    monkeypatch.setattr(models_routes, "_model_manager", manager)
    monkeypatch.setattr(local_llm_module, "_local_llm_instance", None)
    monkeypatch.setattr(
        models_routes,
        "is_local_llm_loaded",
        local_llm_module.is_local_llm_loaded,
    )

    with TestClient(app) as client:
        response = client.get("/api/models/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == {
        "name": "Qwen de prueba",
        "type": "generative",
        "format": "GGUF",
        "quantization": "Q4_K_M",
        "installed": False,
        "verified": False,
        "loaded": False,
    }
    assert payload["embeddings"] == {"installed": False, "implemented": False}
    assert local_llm_module._local_llm_instance is None
    assert str(manager.project_root) not in response.text
    assert response.headers.get("X-Request-ID")
