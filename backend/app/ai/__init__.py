"""Fachada pública de artefactos y modelos locales; no carga pesos al importar."""

from app.ai.embedding_model import EmbeddingModel, get_embedding_model
from app.ai.local_llm import LocalLLM, get_local_llm
from app.ai.model_manager import ModelManager, get_model_selection_store

__all__ = [
    "EmbeddingModel",
    "LocalLLM",
    "ModelManager",
    "get_embedding_model",
    "get_local_llm",
    "get_model_selection_store",
]
