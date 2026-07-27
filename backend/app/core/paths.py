"""Rutas absolutas y estables del proyecto."""

from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]

MODELS_DIR = PROJECT_ROOT / "models"
EMBEDDINGS_MODELS_DIR = MODELS_DIR / "embeddings"
STORAGE_DIR = PROJECT_ROOT / "storage"
STAGING_DIR = STORAGE_DIR / "staging"
MANAGED_CORPUS_STAGING_DIR = STAGING_DIR / "managed_corpus"
DATABASE_DIR = STORAGE_DIR / "database"
DOCUMENTS_DIR = STORAGE_DIR / "documents"
EXTRACTED_DIR = STORAGE_DIR / "extracted"
VECTOR_STORE_DIR = STORAGE_DIR / "vector_store"
VECTOR_DIR = STORAGE_DIR / "vector"
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


def resolve_vector_path(value: str | Path, *, expected_directory: bool) -> Path:
    """Resuelve una ruta contenida en ``storage/vector`` sin crearla."""

    configured_path = Path(value)
    if configured_path.is_absolute() or ".." in configured_path.parts:
        raise ValueError("VECTOR_STORE_PATH_INVALID")
    candidate = (PROJECT_ROOT / configured_path).resolve()
    allowed_directory = VECTOR_DIR.resolve()
    try:
        candidate.relative_to(allowed_directory)
    except ValueError as exc:
        raise ValueError("VECTOR_STORE_PATH_INVALID") from exc
    if expected_directory and candidate == allowed_directory:
        raise ValueError("VECTOR_STORE_PATH_INVALID")
    return candidate


def resolve_managed_corpus_staging_directory(value: str | Path) -> Path:
    """Resuelve staging dentro de ``storage/staging`` sin crearlo."""

    configured_path = Path(value)
    if configured_path.is_absolute() or ".." in configured_path.parts:
        raise ValueError("MANAGED_CORPUS_STAGING_PATH_INVALID")
    candidate = (PROJECT_ROOT / configured_path).resolve()
    allowed_directory = (PROJECT_ROOT / "storage" / "staging").resolve()
    try:
        candidate.relative_to(allowed_directory)
    except ValueError as exc:
        raise ValueError("MANAGED_CORPUS_STAGING_PATH_INVALID") from exc
    if candidate == allowed_directory:
        raise ValueError("MANAGED_CORPUS_STAGING_PATH_INVALID")
    return candidate
