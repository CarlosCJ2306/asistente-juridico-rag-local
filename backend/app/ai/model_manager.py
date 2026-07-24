"""Lectura del manifiesto y verificación segura de modelos locales."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.Log import log_info, log_success, log_warning
from app.core.paths import MODELS_DIR, PROJECT_ROOT


DEFAULT_LLM_MODEL_ID = "qwen3-1.7b-q4-k-m"


class ModelManagerError(RuntimeError):
    """Error base de gestión local de modelos."""


class ManifestError(ModelManagerError):
    """El manifiesto no existe, no es JSON válido o incumple su contrato."""


class ModelNotFoundError(ModelManagerError):
    """El identificador solicitado no existe en el manifiesto."""


class UnsafeModelPathError(ModelManagerError):
    """La ruta declarada escapa del directorio permitido de modelos."""


class EmbeddingModelPathMismatchError(ModelManagerError):
    """La ruta configurada de embeddings no coincide con el manifiesto."""


class ModelManifestEntry(BaseModel):
    """Entrada validada del manifiesto local."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    type: str
    repository: str
    filename: str | None = None
    format: str
    quantization: str | None = None
    local_path: str
    purpose: str
    installation_status: Literal["not_installed", "installed"]
    sha256: str | None = None
    minimum_file_size_bytes: int | None = Field(default=None, gt=0)

    @field_validator(
        "id",
        "name",
        "type",
        "repository",
        "format",
        "local_path",
        "purpose",
    )
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        """Evita metadatos vacíos que producirían rutas o estados ambiguos."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("el valor no puede estar vacío")
        return normalized

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str | None) -> str | None:
        """Exige un nombre simple; la ubicación se declara en ``local_path``."""

        if value is None:
            return None
        normalized = value.strip()
        if not normalized or Path(normalized).name != normalized:
            raise ValueError("filename debe ser un nombre de archivo sin directorios")
        return normalized

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str | None) -> str | None:
        """Normaliza y valida una suma solo cuando existe una fuente confiable."""

        if value is None:
            return None
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("sha256 debe contener 64 caracteres hexadecimales")
        return normalized


class ModelManifest(BaseModel):
    """Raíz validada del manifiesto."""

    model_config = ConfigDict(extra="forbid")

    models: list[ModelManifestEntry]


class ModelVerificationResult(BaseModel):
    """Resultado serializable de una verificación física."""

    model_id: str
    installed: bool
    verified: bool
    relative_path: str
    file_size: int | None = None
    calculated_sha256: str | None = None
    errors: list[str]


class ModelManager:
    """Resuelve y verifica artefactos sin descargarlos ni cargarlos."""

    def __init__(
        self,
        *,
        project_root: Path = PROJECT_ROOT,
        models_dir: Path = MODELS_DIR,
        manifest_path: Path | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.models_dir = models_dir.resolve()
        self.manifest_path = (
            manifest_path.resolve()
            if manifest_path is not None
            else self.models_dir / "manifest.json"
        )
        self._manifest: ModelManifest | None = None

    def load_manifest(self, *, refresh: bool = False) -> ModelManifest:
        """Lee y valida el manifiesto, con caché local opcional."""

        if self._manifest is not None and not refresh:
            return self._manifest
        try:
            raw_manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            manifest = ModelManifest.model_validate(raw_manifest)
        except FileNotFoundError as exc:
            raise ManifestError(
                f"No se encontró el manifiesto de modelos: {self.manifest_path.name}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise ManifestError("El manifiesto de modelos no contiene JSON válido") from exc
        except (OSError, ValidationError) as exc:
            raise ManifestError(f"El manifiesto de modelos no es válido: {exc}") from exc

        identifiers = [entry.id for entry in manifest.models]
        if len(identifiers) != len(set(identifiers)):
            raise ManifestError("El manifiesto contiene identificadores de modelo duplicados")

        self._manifest = manifest
        log_info("Manifiesto de modelos validado", model_count=len(manifest.models))
        return manifest

    def get_model(self, model_id: str) -> ModelManifestEntry:
        """Obtiene una entrada por identificador."""

        for entry in self.load_manifest().models:
            if entry.id == model_id:
                return entry
        raise ModelNotFoundError(f"El modelo '{model_id}' no existe en el manifiesto")

    def list_models(self) -> tuple[ModelManifestEntry, ...]:
        """Devuelve las entradas validadas sin exponer estado mutable."""

        return tuple(self.load_manifest().models)

    def resolve_model_path(self, entry_or_id: ModelManifestEntry | str) -> Path:
        """Resuelve una ruta y rechaza cualquier escape de ``models/``."""

        entry = (
            self.get_model(entry_or_id)
            if isinstance(entry_or_id, str)
            else entry_or_id
        )
        declared_path = Path(entry.local_path)
        if declared_path.is_absolute():
            raise UnsafeModelPathError(
                f"La ruta del modelo '{entry.id}' debe ser relativa al proyecto"
            )
        if ".." in declared_path.parts:
            raise UnsafeModelPathError(
                f"La ruta del modelo '{entry.id}' contiene navegación no permitida"
            )
        candidate = (self.project_root / declared_path).resolve()
        try:
            candidate.relative_to(self.models_dir)
        except ValueError as exc:
            log_warning(
                "Ruta de modelo rechazada por seguridad",
                model_id=entry.id,
                relative_path=entry.local_path,
            )
            raise UnsafeModelPathError(
                f"La ruta del modelo '{entry.id}' está fuera del directorio models permitido"
            ) from exc
        return candidate

    def resolve_embedding_model_path(self, configured_path: str | Path) -> Path:
        """Resuelve la única ruta efectiva y exige coincidencia con el manifiesto."""

        entry = self.get_model("multilingual-e5-small")
        manifest_path = self.resolve_model_path(entry)
        configured = Path(configured_path)
        configured_path_resolved = (
            configured.resolve()
            if configured.is_absolute()
            else (self.project_root / configured).resolve()
        )
        allowed_directory = (self.models_dir / "embeddings").resolve()
        try:
            configured_path_resolved.relative_to(allowed_directory)
        except ValueError as exc:
            raise UnsafeModelPathError(
                "La ruta configurada de embeddings estÃ¡ fuera del directorio permitido"
            ) from exc
        if configured_path_resolved != manifest_path:
            raise EmbeddingModelPathMismatchError("EMBEDDING_MODEL_PATH_MISMATCH")
        return manifest_path

    @staticmethod
    def calculate_sha256(file_path: Path, *, chunk_size: int = 1024 * 1024) -> str:
        """Calcula SHA-256 en bloques para no cargar el archivo completo en memoria."""

        digest = hashlib.sha256()
        with file_path.open("rb") as model_file:
            for chunk in iter(lambda: model_file.read(chunk_size), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def verify_model(
        self,
        model_id: str,
        *,
        calculate_hash: bool = True,
        configured_path: str | Path | None = None,
    ) -> ModelVerificationResult:
        """Comprueba artefactos locales de archivo o directorio sin cargarlos."""

        entry = self.get_model(model_id)
        try:
            path = (
                self.resolve_embedding_model_path(configured_path)
                if entry.id == "multilingual-e5-small" and configured_path is not None
                else self.resolve_model_path(entry)
            )
            if entry.id == "multilingual-e5-small" and configured_path is None:
                raise EmbeddingModelPathMismatchError("EMBEDDING_MODEL_PATH_MISMATCH")
        except EmbeddingModelPathMismatchError as exc:
            return ModelVerificationResult(
                model_id=entry.id,
                installed=False,
                verified=False,
                relative_path=entry.local_path,
                errors=[str(exc)],
            )
        errors: list[str] = []
        file_size: int | None = None
        calculated_sha256: str | None = None

        if entry.filename and path.name != entry.filename:
            errors.append(
                f"El nombre esperado es '{entry.filename}', no '{path.name}'"
            )
        if entry.format.upper() == "GGUF" and path.suffix.lower() != ".gguf":
            errors.append("El modelo GGUF debe utilizar la extensión .gguf")

        is_sentence_transformers = entry.format.lower() == "sentence transformers"
        if not path.exists():
            errors.append("El archivo del modelo no está instalado")
        elif is_sentence_transformers and not path.is_dir():
            errors.append("La ruta del modelo de embeddings no corresponde a un directorio")
        elif is_sentence_transformers:
            required_files = ("config.json", "modules.json")
            missing_files = [name for name in required_files if not (path / name).is_file()]
            if missing_files or (path / ".incomplete").exists():
                errors.append("El directorio del modelo de embeddings está incompleto")
            file_size = sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
            if file_size == 0:
                errors.append("El directorio del modelo de embeddings está vacío")
        elif not path.is_file():
            errors.append("La ruta del modelo no corresponde a un archivo")
        else:
            file_size = path.stat().st_size
            if file_size == 0:
                errors.append("El archivo del modelo está vacío")
            if (
                entry.minimum_file_size_bytes is not None
                and file_size < entry.minimum_file_size_bytes
            ):
                errors.append(
                    "El archivo no alcanza el tamaño mínimo declarado "
                    f"({entry.minimum_file_size_bytes} bytes)"
                )
            if entry.format.upper() == "GGUF" and file_size > 0:
                with path.open("rb") as model_file:
                    if model_file.read(4) != b"GGUF":
                        errors.append("La cabecera del archivo no contiene la firma GGUF")

            if entry.sha256:
                if calculate_hash:
                    calculated_sha256 = self.calculate_sha256(path)
                    if calculated_sha256.lower() != entry.sha256.lower():
                        errors.append("La suma SHA-256 no coincide con el manifiesto")
                else:
                    errors.append("La suma SHA-256 declarada no fue comprobada")

        result = ModelVerificationResult(
            model_id=entry.id,
            installed=path.is_dir() if is_sentence_transformers else path.is_file(),
            verified=not errors,
            relative_path=entry.local_path,
            file_size=file_size,
            calculated_sha256=calculated_sha256,
            errors=errors,
        )
        log_context = {
            "model_id": entry.id,
            "model_name": entry.name,
            "relative_path": entry.local_path,
            "file_size": file_size,
            "verification_status": "verified" if result.verified else "failed",
        }
        if result.verified:
            log_success("Modelo local verificado", **log_context)
        elif result.installed:
            log_warning("La verificación del modelo local falló", **log_context)
        else:
            log_info("Modelo local no instalado", **log_context)
        return result

    def safe_metadata(self, model_id: str) -> dict[str, object]:
        """Devuelve metadatos sin rutas absolutas ni detalles sensibles."""

        entry = self.get_model(model_id)
        verification = self.verify_model(model_id, calculate_hash=False)
        return {
            "id": entry.id,
            "name": entry.name,
            "type": entry.type,
            "format": entry.format,
            "quantization": entry.quantization,
            "installed": verification.installed,
            "verified": verification.verified,
            "relative_path": entry.local_path,
            "file_size": verification.file_size,
        }
