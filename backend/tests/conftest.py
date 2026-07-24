"""Aislamiento de configuración para las pruebas."""

import os
import json
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

os.environ["LOG_TO_FILE"] = "false"
os.environ["LOG_CONSOLE"] = "false"
os.environ["DEBUG"] = "false"


@pytest.fixture
def model_project_factory(tmp_path: Path):
    """Crea manifiestos y rutas exclusivamente dentro de un temporal."""

    from app.ai.model_manager import ModelManager

    def factory(
        *,
        local_path: str = "models/llm/test/model.gguf",
        filename: str = "model.gguf",
        model_format: str = "GGUF",
        minimum_file_size_bytes: int = 4,
        sha256: str | None = None,
    ) -> tuple[ModelManager, Path]:
        models_dir = tmp_path / "models"
        models_dir.mkdir(exist_ok=True)
        manifest_path = models_dir / "manifest.json"
        manifest = {
            "models": [
                {
                    "id": "qwen3-1.7b-q4-k-m",
                    "name": "Qwen de prueba",
                    "type": "generative",
                    "repository": "owner/repository",
                    "filename": filename,
                    "format": model_format,
                    "quantization": "Q4_K_M",
                    "local_path": local_path,
                    "purpose": "Prueba unitaria",
                    "installation_status": "not_installed",
                    "sha256": sha256,
                    "minimum_file_size_bytes": minimum_file_size_bytes,
                }
            ]
        }
        manifest_path.write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        manager = ModelManager(
            project_root=tmp_path,
            models_dir=models_dir,
            manifest_path=manifest_path,
        )
        return manager, tmp_path / local_path

    return factory
