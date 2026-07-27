"""Adaptador perezoso para un índice ChromaDB local y reconstruible."""

from __future__ import annotations

import importlib.util
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.paths import VECTOR_DIR
from app.database.models.document import DocumentType, KnowledgeLayer


class ChromaStoreError(RuntimeError):
    """Error estable que oculta detalles internos del almacén vectorial."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class VectorCandidate:
    chunk_id: str
    metadata: dict[str, object]
    distance: float


class ChromaStore:
    """Opera exclusivamente con ``PersistentClient`` y embeddings explícitos."""

    _METADATA_KEYS = {
        "document_id",
        "document_type",
        "knowledge_layer",
        "chunk_index",
        "start_page",
        "end_page",
    }

    def __init__(
        self,
        persist_path: Path | None = None,
        *,
        enforce_authorized_path: bool = True,
    ) -> None:
        self.persist_path = persist_path or settings.chroma_persist_path
        self.enforce_authorized_path = enforce_authorized_path

    @staticmethod
    def dependency_available() -> bool:
        """Comprueba disponibilidad sin importar ChromaDB."""

        return importlib.util.find_spec("chromadb") is not None

    @staticmethod
    def _import_chroma() -> tuple[Any, Any]:
        try:
            import chromadb  # type: ignore[import-not-found]
            from chromadb.config import Settings as ChromaSettings  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ChromaStoreError("CHROMA_DEPENDENCY_MISSING") from exc
        return chromadb, ChromaSettings

    def _client(self) -> Any:
        self._validate_persist_path()
        chromadb, chroma_settings = self._import_chroma()
        return chromadb.PersistentClient(
            path=str(self.persist_path),
            settings=chroma_settings(anonymized_telemetry=False),
        )

    @staticmethod
    def _validate_collection_name(name: str) -> None:
        prefix = re.escape(settings.semantic_collection_prefix)
        if re.fullmatch(rf"{prefix}_[a-f0-9]{{32}}", name) is None:
            raise ChromaStoreError("SEMANTIC_INDEX_STATE_INVALID")

    def _validate_persist_path(self) -> None:
        if not self.enforce_authorized_path:
            return
        try:
            self.persist_path.resolve().relative_to(VECTOR_DIR.resolve())
        except ValueError as exc:
            raise ChromaStoreError("VECTOR_STORE_PATH_INVALID") from exc

    def _require_existing_store(self, *, error_code: str) -> None:
        self._validate_persist_path()
        if not self.persist_path.is_dir():
            raise ChromaStoreError(error_code)

    def create_collection(
        self,
        name: str,
        *,
        schema_version: int,
        embedding_model: str,
        embedding_dimension: int,
    ) -> None:
        self._validate_collection_name(name)
        if (
            type(schema_version) is not int
            or schema_version != settings.semantic_index_schema_version
            or embedding_model != settings.embedding_model_name
            or type(embedding_dimension) is not int
            or embedding_dimension <= 0
        ):
            raise ChromaStoreError("SEMANTIC_INDEX_INCOMPATIBLE")
        try:
            self._client().create_collection(
                name=name,
                metadata={
                    "hnsw:space": "cosine",
                    "semantic_schema_version": schema_version,
                    "embedding_model": embedding_model,
                    "embedding_dimension": embedding_dimension,
                },
                embedding_function=None,
            )
        except ChromaStoreError:
            raise
        except Exception as exc:
            raise ChromaStoreError("SEMANTIC_INDEX_BUILD_ERROR") from exc

    def add(
        self,
        collection_name: str,
        *,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[dict[str, str | int]],
    ) -> None:
        self._validate_collection_name(collection_name)
        try:
            invalid_payload = (
                not ids
                or len(ids) != len(embeddings)
                or len(ids) != len(metadatas)
                or len(set(ids)) != len(ids)
                or any(not self._valid_uuid(value) for value in ids)
                or any(not self._valid_metadata(metadata) for metadata in metadatas)
                or any(
                    not vector or not all(math.isfinite(float(value)) for value in vector)
                    for vector in embeddings
                )
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise ChromaStoreError("SEMANTIC_OUTPUT_INVALID") from exc
        if invalid_payload:
            raise ChromaStoreError("SEMANTIC_OUTPUT_INVALID")
        try:
            collection = self._client().get_collection(
                name=collection_name, embedding_function=None
            )
            collection.add(
                ids=list(ids),
                embeddings=[list(vector) for vector in embeddings],
                metadatas=list(metadatas),
            )
        except ChromaStoreError:
            raise
        except Exception as exc:
            raise ChromaStoreError("SEMANTIC_INDEX_BUILD_ERROR") from exc

    @classmethod
    def _valid_metadata(cls, metadata: dict[str, str | int]) -> bool:
        if set(metadata) != cls._METADATA_KEYS:
            return False
        document_id = metadata.get("document_id")
        document_type = metadata.get("document_type")
        knowledge_layer = metadata.get("knowledge_layer")
        chunk_index = metadata.get("chunk_index")
        start_page = metadata.get("start_page")
        end_page = metadata.get("end_page")
        return (
            isinstance(document_id, str)
            and cls._valid_uuid(document_id)
            and isinstance(document_type, str)
            and document_type in {item.value for item in DocumentType}
            and isinstance(knowledge_layer, str)
            and knowledge_layer in {item.value for item in KnowledgeLayer}
            and type(chunk_index) is int
            and chunk_index >= 1
            and type(start_page) is int
            and start_page >= 1
            and type(end_page) is int
            and end_page >= start_page
        )

    @staticmethod
    def _valid_uuid(value: str) -> bool:
        try:
            UUID(value)
        except (ValueError, TypeError, AttributeError):
            return False
        return True

    def count(self, collection_name: str) -> int:
        self._validate_collection_name(collection_name)
        self._require_existing_store(error_code="SEMANTIC_INDEX_NOT_READY")
        try:
            collection = self._client().get_collection(
                name=collection_name, embedding_function=None
            )
            return int(collection.count())
        except ChromaStoreError:
            raise
        except Exception as exc:
            raise ChromaStoreError("SEMANTIC_INDEX_NOT_READY") from exc

    def metadata(self, collection_name: str) -> dict[str, object]:
        self._validate_collection_name(collection_name)
        self._require_existing_store(error_code="SEMANTIC_INDEX_NOT_READY")
        try:
            collection = self._client().get_collection(
                name=collection_name, embedding_function=None
            )
            return dict(collection.metadata or {})
        except ChromaStoreError:
            raise
        except Exception as exc:
            raise ChromaStoreError("SEMANTIC_INDEX_NOT_READY") from exc

    def query(
        self,
        collection_name: str,
        *,
        query_embedding: Sequence[float],
        limit: int,
        where: dict[str, object] | None,
    ) -> list[VectorCandidate]:
        self._validate_collection_name(collection_name)
        self._require_existing_store(error_code="SEMANTIC_INDEX_NOT_READY")
        try:
            collection = self._client().get_collection(
                name=collection_name, embedding_function=None
            )
            result = collection.query(
                query_embeddings=[list(query_embedding)],
                n_results=limit,
                where=where,
                include=["metadatas", "distances"],
            )
            if not isinstance(result, dict):
                raise ChromaStoreError("SEMANTIC_OUTPUT_INVALID")
            ids = (result.get("ids") or [[]])[0]
            metadatas = (result.get("metadatas") or [[]])[0]
            distances = (result.get("distances") or [[]])[0]
            if (
                not isinstance(ids, list)
                or not isinstance(metadatas, list)
                or not isinstance(distances, list)
                or not (len(ids) == len(metadatas) == len(distances))
            ):
                raise ChromaStoreError("SEMANTIC_OUTPUT_INVALID")
            candidates: list[VectorCandidate] = []
            for chunk_id, metadata, distance in zip(
                ids, metadatas, distances, strict=True
            ):
                if (
                    not isinstance(chunk_id, str)
                    or not isinstance(metadata, dict)
                    or isinstance(distance, bool)
                    or not isinstance(distance, (int, float))
                ):
                    raise ChromaStoreError("SEMANTIC_OUTPUT_INVALID")
                candidates.append(
                    VectorCandidate(
                        chunk_id=chunk_id,
                        metadata=dict(metadata),
                        distance=float(distance),
                    )
                )
            return candidates
        except ChromaStoreError:
            raise
        except Exception as exc:
            raise ChromaStoreError("SEMANTIC_SEARCH_ERROR") from exc

    def delete_collection(self, name: str) -> None:
        self._validate_collection_name(name)
        self._require_existing_store(error_code="SEMANTIC_INDEX_BUILD_ERROR")
        try:
            self._client().delete_collection(name=name)
        except ChromaStoreError:
            raise
        except Exception as exc:
            raise ChromaStoreError("SEMANTIC_INDEX_BUILD_ERROR") from exc
