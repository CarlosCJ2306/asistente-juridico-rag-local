"""Estado seguro de los modelos locales."""

from typing import Literal, cast

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict

from app.ai.embedding_model import EMBEDDING_MODEL_ID, EmbeddingError, get_embedding_model
from app.ai.local_llm import get_local_llm, is_local_llm_loaded
from app.ai.model_manager import ManifestError, ModelManager, ModelManagerError, ModelSelectionError, ModelSelectionState, get_model_selection_store
from app.core.config import settings
from app.services.embedding_runtime_service import get_embedding_runtime_service
from app.services.llm_runtime_service import (
    LlmRuntimeError,
    LlmRuntimeService,
    get_llm_runtime_service,
)


router = APIRouter(prefix="/models", tags=["models"])
_model_manager = ModelManager()
_selection_store = get_model_selection_store()


class LocalModelStatus(BaseModel):
    name: str
    type: str
    format: str
    quantization: str | None
    installed: bool
    verified: bool
    loaded: bool


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
    automatically_loaded: bool = False


class LlmRuntimeStatus(BaseModel):
    model: str
    state: Literal["unloaded", "loaded"]
    context_size: int
    runtime_operation: Literal["idle", "loading", "unloading", "error"] = "idle"
    load_origin: Literal["manual", "on_demand"] | None = None


class CatalogModelStatus(BaseModel):
    model_id: str
    model_type: Literal["embedding", "llm"]
    display_name: str
    description: str
    family: str
    format: str
    quantization: str | None
    installed: bool
    active: bool
    loaded: bool
    size_bytes: int | None
    embedding_dimension: int | None
    context_length: int | None
    capabilities: list[str]
    compatibility_status: Literal["compatible", "inactive", "not_installed", "disabled"]


class ModelCatalogResponse(BaseModel):
    schema_version: int
    models: list[CatalogModelStatus]


class ModelSelectionResponse(BaseModel):
    schema_version: int
    active_embedding_model_id: str
    active_llm_model_id: str


class ModelSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str


@router.get("/status", response_model=ModelsStatusResponse)
async def models_status() -> ModelsStatusResponse:
    """Consulta metadatos físicos sin descargar, cargar ni ejecutar el LLM."""

    selection = _selection_store.read()
    entry = _model_manager.get_model(selection.active_llm_model_id)
    verification = _model_manager.verify_model(
        selection.active_llm_model_id,
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
        ),
        embeddings=EmbeddingsStatus(),
    )


def _embedding_status() -> EmbeddingModelStatus:
    model = get_embedding_model()
    runtime = get_embedding_runtime_service()
    verification = model.model_manager.verify_model(
        model.model_id,
        calculate_hash=False,
        configured_path=model.configured_path if model.model_id == EMBEDDING_MODEL_ID else None,
    )
    return EmbeddingModelStatus(
        model=model.model_id,
        state=model.state,
        local_files_available=verification.verified,
        device=model.device,
        dimension=model.dimension,
        automatically_loaded=(
            runtime.automatically_loaded if runtime.model is model else False
        ),
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
        await get_embedding_runtime_service().explicit_load()
    except EmbeddingError as exc:
        raise _embedding_http_error(exc) from exc
    return _embedding_status()


@router.post("/embeddings/unload", response_model=EmbeddingModelStatus)
async def unload_embeddings_model() -> EmbeddingModelStatus:
    """Libera el modelo local; la operación es idempotente."""

    try:
        await get_embedding_runtime_service().explicit_unload()
    except EmbeddingError as exc:
        raise _embedding_http_error(exc) from exc
    return _embedding_status()


def _llm_lifecycle() -> LlmRuntimeService:
    llm = get_local_llm()
    runtime = get_llm_runtime_service()
    if runtime.model is not llm and not runtime.busy:
        return LlmRuntimeService(llm)
    return runtime


def _llm_runtime_status() -> LlmRuntimeStatus:
    runtime = _llm_lifecycle()
    llm = runtime.model
    return LlmRuntimeStatus(
        model=getattr(llm, "model_id", _selection_store.read().active_llm_model_id),
        state="loaded" if llm.is_loaded else "unloaded",
        context_size=settings.local_llm_context_size,
        runtime_operation=runtime.operation,
        load_origin=runtime.load_origin,
    )


@router.get("/llm/status", response_model=LlmRuntimeStatus)
async def llm_runtime_status() -> LlmRuntimeStatus:
    """Consulta el ciclo de vida sin cargar el GGUF."""

    return _llm_runtime_status()


@router.post("/llm/load", response_model=LlmRuntimeStatus)
async def load_llm_model() -> LlmRuntimeStatus:
    """Carga explícitamente Qwen fuera del event loop."""

    try:
        await _llm_lifecycle().explicit_load()
    except LlmRuntimeError as exc:
        status = 409 if exc.code == "RAG_LLM_BUSY" else 503
        raise HTTPException(status_code=status, detail=exc.code) from exc
    return _llm_runtime_status()


@router.post("/llm/unload", response_model=LlmRuntimeStatus)
async def unload_llm_model() -> LlmRuntimeStatus:
    """Libera Qwen; la operación es idempotente."""

    try:
        await _llm_lifecycle().explicit_unload()
    except LlmRuntimeError as exc:
        status = 409 if exc.code == "RAG_LLM_BUSY" else 500
        raise HTTPException(status_code=status, detail=exc.code) from exc
    return _llm_runtime_status()


def _selection_response(state: ModelSelectionState) -> ModelSelectionResponse:
    return ModelSelectionResponse(**state.model_dump())


def _selection_http_error(error: ModelSelectionError) -> HTTPException:
    if error.code == "MODEL_NOT_FOUND":
        status_code = 404
    elif error.code in {"MODEL_NOT_INSTALLED", "MODEL_DISABLED", "MODEL_TYPE_MISMATCH", "MODEL_CURRENTLY_LOADED"}:
        status_code = 409
    else:
        status_code = 500
    return HTTPException(status_code=status_code, detail=error.code)


@router.get("/catalog", response_model=ModelCatalogResponse)
async def model_catalog() -> ModelCatalogResponse:
    """Lista únicamente metadatos administrativos y disponibilidad local."""

    try:
        selection = _selection_store.read()
        embedding = get_embedding_model()
        llm = get_local_llm()
        models: list[CatalogModelStatus] = []
        for entry in _model_manager.list_models():
            verification = await run_in_threadpool(
                _model_manager.verify_model,
                entry.id,
                calculate_hash=False,
                configured_path=(embedding.configured_path if entry.id == embedding.model_id and entry.model_type == "embedding" else str(_model_manager.resolve_model_path(entry)) if entry.model_type == "embedding" else None),
            )
            active = entry.id in {selection.active_embedding_model_id, selection.active_llm_model_id}
            loaded = (entry.model_type == "embedding" and embedding.model_id == entry.id and embedding.is_loaded) or (entry.model_type == "llm" and llm.model_id == entry.id and llm.is_loaded)
            compatibility = cast(Literal["compatible", "inactive", "not_installed", "disabled"], "disabled" if not entry.enabled else "not_installed" if not verification.verified else "compatible" if active else "inactive")
            models.append(CatalogModelStatus(model_id=entry.id, model_type=entry.model_type, display_name=entry.public_name, description=entry.public_description, family=entry.public_family, format=entry.format, quantization=entry.quantization, installed=verification.verified, active=active, loaded=loaded, size_bytes=verification.file_size, embedding_dimension=entry.embedding_dimension, context_length=entry.context_length, capabilities=entry.capabilities, compatibility_status=compatibility))
        return ModelCatalogResponse(schema_version=_model_manager.load_manifest().schema_version, models=models)
    except (ManifestError, ModelManagerError, OSError) as exc:
        raise HTTPException(status_code=500, detail="MODEL_CATALOG_INVALID") from exc


@router.get("/selection", response_model=ModelSelectionResponse)
async def model_selection() -> ModelSelectionResponse:
    return _selection_response(_selection_store.read())


@router.put("/selection/embeddings", response_model=ModelSelectionResponse)
async def select_embedding_model(payload: ModelSelectionRequest) -> ModelSelectionResponse:
    runtime = get_embedding_model()
    try:
        state = await run_in_threadpool(_selection_store.select, payload.model_id, "embedding", currently_loaded=runtime.is_loaded)
        runtime.select_model(state.active_embedding_model_id)
        return _selection_response(state)
    except ModelSelectionError as exc:
        raise _selection_http_error(exc) from exc


@router.put("/selection/llm", response_model=ModelSelectionResponse)
async def select_llm_model(payload: ModelSelectionRequest) -> ModelSelectionResponse:
    runtime = get_local_llm()
    lifecycle = _llm_lifecycle()
    try:
        state = await run_in_threadpool(_selection_store.select, payload.model_id, "llm", currently_loaded=runtime.is_loaded or lifecycle.busy)
        runtime.select_model(state.active_llm_model_id)
        return _selection_response(state)
    except ModelSelectionError as exc:
        raise _selection_http_error(exc) from exc
