"""Validación manual no destructiva del índice semántico local."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.database.session import database_session_manager  # noqa: E402
from app.services.semantic_index_service import (  # noqa: E402
    SemanticIndexService,
    SemanticServiceError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida el índice sin reconstruirlo")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--status", action="store_true")
    action.add_argument("--validate-active", action="store_true")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> int:
    async with database_session_manager.get_session_factory()() as session:
        service = SemanticIndexService(session)
        if args.status:
            status = await service.status()
            print(
                "Estado:", status.state,
                "| dependencia:", "disponible" if status.dependency_available else "ausente",
                "| chunks indexados:", status.indexed_chunks,
                "| requiere reconstrucción:", status.needs_rebuild,
            )
            return 0
        try:
            state = await service.active_state(require_model=False)
        except SemanticServiceError as exc:
            print(f"Validación fallida: {exc.code}")
            return 1
        print(
            "Índice activo válido",
            "| modelo:", state.embedding_model,
            "| dimensión:", state.embedding_dimension,
            "| chunks indexados:", state.indexed_chunks,
            "| distancia:", state.distance_metric,
        )
        return 0


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(run(args))
    finally:
        asyncio.run(database_session_manager.dispose())


if __name__ == "__main__":
    raise SystemExit(main())
