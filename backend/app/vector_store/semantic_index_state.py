"""Estado mínimo y atómico del índice semántico activo."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.core.paths import VECTOR_DIR


class SemanticStateError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class SemanticIndexState:
    schema_version: int
    active_collection: str
    embedding_model: str
    embedding_dimension: int
    distance_metric: str
    indexed_chunks: int
    created_at: str
    source_fingerprint: str


class SemanticStateStore:
    """Lee y reemplaza el puntero activo sin almacenar contenido documental."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        collection_prefix: str = settings.semantic_collection_prefix,
        enforce_authorized_path: bool | None = None,
    ) -> None:
        self.path = path or settings.semantic_index_state_file
        self.collection_prefix = collection_prefix
        self.enforce_authorized_path = (
            self.path == settings.semantic_index_state_file
            if enforce_authorized_path is None
            else enforce_authorized_path
        )

    def read(self) -> SemanticIndexState | None:
        self._validate_path()
        if not self.path.exists():
            return None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            state = SemanticIndexState(**raw)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
            raise SemanticStateError("SEMANTIC_INDEX_STATE_INVALID") from exc
        self._validate(state)
        return state

    def write_atomic(self, state: SemanticIndexState) -> None:
        self._validate_path()
        self._validate(state)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as state_file:
                json.dump(asdict(state), state_file, ensure_ascii=False, sort_keys=True)
                state_file.flush()
                os.fsync(state_file.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            raise SemanticStateError("SEMANTIC_INDEX_BUILD_ERROR") from exc
        finally:
            temporary.unlink(missing_ok=True)

    def clear(self) -> None:
        """Retira únicamente el puntero derivado cuando no existía estado previo."""

        self._validate_path()
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            raise SemanticStateError("SEMANTIC_INDEX_BUILD_ERROR") from exc

    def _validate(self, state: SemanticIndexState) -> None:
        if (
            isinstance(state.schema_version, bool)
            or not isinstance(state.schema_version, int)
            or isinstance(state.embedding_dimension, bool)
            or not isinstance(state.embedding_dimension, int)
            or isinstance(state.indexed_chunks, bool)
            or not isinstance(state.indexed_chunks, int)
            or not isinstance(state.active_collection, str)
            or not isinstance(state.embedding_model, str)
            or not isinstance(state.distance_metric, str)
            or not isinstance(state.created_at, str)
            or not isinstance(state.source_fingerprint, str)
        ):
            raise SemanticStateError("SEMANTIC_INDEX_STATE_INVALID")
        prefix = re.escape(self.collection_prefix)
        if re.fullmatch(rf"{prefix}_[a-f0-9]{{32}}", state.active_collection) is None:
            raise SemanticStateError("SEMANTIC_INDEX_STATE_INVALID")
        if state.schema_version <= 0:
            raise SemanticStateError("SEMANTIC_INDEX_STATE_INVALID")
        if not state.embedding_model.strip() or state.embedding_dimension <= 0:
            raise SemanticStateError("SEMANTIC_INDEX_STATE_INVALID")
        if state.distance_metric != "cosine" or state.indexed_chunks < 0:
            raise SemanticStateError("SEMANTIC_INDEX_STATE_INVALID")
        if re.fullmatch(r"[0-9a-f]{64}", state.source_fingerprint) is None:
            raise SemanticStateError("SEMANTIC_INDEX_STATE_INVALID")
        try:
            created_at = datetime.fromisoformat(state.created_at)
        except ValueError as exc:
            raise SemanticStateError("SEMANTIC_INDEX_STATE_INVALID") from exc
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise SemanticStateError("SEMANTIC_INDEX_STATE_INVALID")

    def _validate_path(self) -> None:
        if not self.enforce_authorized_path:
            return
        try:
            self.path.resolve().relative_to(VECTOR_DIR.resolve())
        except ValueError as exc:
            raise SemanticStateError("VECTOR_STORE_PATH_INVALID") from exc
