"""Rutas absolutas y estables del proyecto."""

from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]

MODELS_DIR = PROJECT_ROOT / "models"
EMBEDDINGS_MODELS_DIR = MODELS_DIR / "embeddings"
STORAGE_DIR = PROJECT_ROOT / "storage"
DATABASE_DIR = STORAGE_DIR / "database"
DOCUMENTS_DIR = STORAGE_DIR / "documents"
EXTRACTED_DIR = STORAGE_DIR / "extracted"
VECTOR_STORE_DIR = STORAGE_DIR / "vector_store"
TEMP_DIR = STORAGE_DIR / "temp"
UPLOADS_TEMP_DIR = TEMP_DIR / "uploads"
LOGS_DIR = STORAGE_DIR / "logs"


def resolve_database_file(value: str | Path) -> Path:
    """Resuelve un archivo de SQLite sin permitir salidas de ``storage/database``."""

    configured_path = Path(value)
    candidate = (
        configured_path.resolve()
        if configured_path.is_absolute()
        else (PROJECT_ROOT / configured_path).resolve()
    )
    allowed_directory = DATABASE_DIR.resolve()
    try:
        candidate.relative_to(allowed_directory)
    except ValueError as exc:
        raise ValueError(
            "DATABASE_FILE debe ubicarse dentro de storage/database"
        ) from exc
    return candidate


def resolve_embedding_model_directory(value: str | Path) -> Path:
    """Resuelve solo directorios de embeddings contenidos en ``models/embeddings``."""

    configured_path = Path(value)
    if configured_path.is_absolute() or ".." in configured_path.parts:
        raise ValueError("EMBEDDING_MODEL_PATH debe ubicarse dentro de models/embeddings")
    candidate = (PROJECT_ROOT / configured_path).resolve()
    try:
        candidate.relative_to(EMBEDDINGS_MODELS_DIR.resolve())
    except ValueError as exc:
        raise ValueError("EMBEDDING_MODEL_PATH debe ubicarse dentro de models/embeddings") from exc
    return candidate
