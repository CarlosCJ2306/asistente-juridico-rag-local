"""Estado seguro de los modelos locales."""

from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.ai.embedding_model import EMBEDDING_MODEL_ID, EmbeddingError, get_embedding_model
from app.ai.local_llm import LocalLLMError, get_local_llm, is_local_llm_loaded
from app.ai.model_manager import DEFAULT_LLM_MODEL_ID, ModelManager
from app.core.config import settings


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


class EmbeddingModelStatus(BaseModel):
    model: str
    role: Literal["embeddings"] = "embeddings"
    state: Literal["unloaded", "loading", "loaded", "error"]
    local_files_available: bool
    device: str
    dimension: int | None


class LlmRuntimeStatus(BaseModel):
    model: str
    state: Literal["unloaded", "loaded"]
    context_size: int


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


def _embedding_status() -> EmbeddingModelStatus:
    model = get_embedding_model()
    verification = model.model_manager.verify_model(
        EMBEDDING_MODEL_ID,
        calculate_hash=False,
        configured_path=model.configured_path,
    )
    return EmbeddingModelStatus(
        model=EMBEDDING_MODEL_ID,
        state=model.state,
        local_files_available=verification.verified,
        device=model.device,
        dimension=model.dimension,
    )


def _embedding_http_error(error: EmbeddingError) -> HTTPException:
    status_code = 503 if error.code in {
        "EMBEDDING_DEPENDENCY_MISSING",
        "EMBEDDING_MODEL_NOT_FOUND",
    } else 409 if error.code == "EMBEDDING_MODEL_BUSY" else 500
    return HTTPException(status_code=status_code, detail=error.code)


@router.get("/embeddings/status", response_model=EmbeddingModelStatus)
async def embeddings_status() -> EmbeddingModelStatus:
    """Consulta estado sin importar Sentence Transformers ni cargar pesos."""

    return _embedding_status()


@router.post("/embeddings/load", response_model=EmbeddingModelStatus)
async def load_embeddings_model() -> EmbeddingModelStatus:
    """Carga explícitamente el modelo local fuera del event loop."""

    try:
        await run_in_threadpool(get_embedding_model().load)
    except EmbeddingError as exc:
        raise _embedding_http_error(exc) from exc
    return _embedding_status()


@router.post("/embeddings/unload", response_model=EmbeddingModelStatus)
async def unload_embeddings_model() -> EmbeddingModelStatus:
    """Libera el modelo local; la operación es idempotente."""

    await run_in_threadpool(get_embedding_model().unload)
    return _embedding_status()


def _llm_runtime_status() -> LlmRuntimeStatus:
    llm = get_local_llm()
    return LlmRuntimeStatus(
        model=DEFAULT_LLM_MODEL_ID,
        state="loaded" if llm.is_loaded else "unloaded",
        context_size=settings.local_llm_context_size,
    )


@router.get("/llm/status", response_model=LlmRuntimeStatus)
async def llm_runtime_status() -> LlmRuntimeStatus:
    """Consulta el ciclo de vida sin cargar el GGUF."""

    return _llm_runtime_status()


@router.post("/llm/load", response_model=LlmRuntimeStatus)
async def load_llm_model() -> LlmRuntimeStatus:
    """Carga explícitamente Qwen fuera del event loop."""

    try:
        await run_in_threadpool(get_local_llm().load)
    except LocalLLMError as exc:
        raise HTTPException(status_code=503, detail="RAG_LLM_UNAVAILABLE") from exc
    return _llm_runtime_status()


@router.post("/llm/unload", response_model=LlmRuntimeStatus)
async def unload_llm_model() -> LlmRuntimeStatus:
    """Libera Qwen; la operación es idempotente."""

    await run_in_threadpool(get_local_llm().unload)
    return _llm_runtime_status()
