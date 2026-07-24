"""Estado seguro de los modelos locales."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.ai.local_llm import is_local_llm_loaded
from app.ai.model_manager import DEFAULT_LLM_MODEL_ID, ModelManager


router = APIRouter(prefix="/models", tags=["models"])
_model_manager = ModelManager()


class LocalModelStatus(BaseModel):
    name: str
    type: str
    format: str
    quantization: str | None
    installed: bool
    verified: bool
    loaded: bool
    relative_path: str


class EmbeddingsStatus(BaseModel):
    installed: Literal[False] = False
    implemented: Literal[False] = False


class ModelsStatusResponse(BaseModel):
    model: LocalModelStatus
    embeddings: EmbeddingsStatus


@router.get("/status", response_model=ModelsStatusResponse)
async def models_status() -> ModelsStatusResponse:
    """Consulta metadatos físicos sin descargar, cargar ni ejecutar el LLM."""

    entry = _model_manager.get_model(DEFAULT_LLM_MODEL_ID)
    verification = _model_manager.verify_model(
        DEFAULT_LLM_MODEL_ID,
        calculate_hash=False,
    )
    return ModelsStatusResponse(
        model=LocalModelStatus(
            name=entry.name,
            type=entry.type,
            format=entry.format,
            quantization=entry.quantization,
            installed=verification.installed,
            verified=verification.verified,
            loaded=is_local_llm_loaded(),
            relative_path=entry.local_path,
        ),
        embeddings=EmbeddingsStatus(),
    )
