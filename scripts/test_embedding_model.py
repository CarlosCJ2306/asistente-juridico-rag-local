"""Prueba manual explícita del modelo local de embeddings, sin descargas."""

from __future__ import annotations

import math
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.embedding_model import EmbeddingError, EmbeddingModel  # noqa: E402
from app.services.embedding_service import EmbeddingService  # noqa: E402


def main() -> int:
    """Comprueba carga, dimensión, normalización, orden y descarga."""

    model = EmbeddingModel()
    try:
        model.load()
        service = EmbeddingService(model)
        query = service.embed_query("consulta sintética")
        passages = service.embed_passages(["pasaje uno", "pasaje dos"])
        if len(passages) != 2 or any(len(vector) != len(query) for vector in passages):
            return 1
        if not all(math.isfinite(value) for vector in [query, *passages] for value in vector):
            return 1
        if not all(abs(sum(value * value for value in vector) - 1.0) < 1e-5 for vector in [query, *passages]):
            return 1
        print("Modelo local cargado")
        print(f"Dispositivo: {model.device}")
        print(f"Dimensión: {model.dimension}")
        print("Consulta: OK")
        print("Pasajes: 2 OK")
        print("Normalización: OK")
        return 0
    except EmbeddingError as exc:
        print(f"Prueba no completada: {exc.code}")
        return 1
    finally:
        model.unload()
        print("Descarga: OK")


if __name__ == "__main__":
    raise SystemExit(main())
