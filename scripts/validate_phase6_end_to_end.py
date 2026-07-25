"""Valida de forma local y sanitizada el flujo manual de la Fase 6.

El script no usa Git ni ejecuta migraciones. Solo puede modificar ``storage/vector``
mediante el endpoint de reconstruccion semantica expresamente solicitado.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
REPORTS_DIR = PROJECT_ROOT / "local_validation_reports"
DATABASE_FILE = PROJECT_ROOT / "storage" / "database" / "asistente_juridico.db"
REPORT_TIMEOUT_SECONDS = 300
HTTP_TIMEOUT_SECONDS = 30
OFFLINE_ENVIRONMENT = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "ANONYMIZED_TELEMETRY": "False",
}
SENSITIVE_OUTPUT = re.compile(
    r"(?:[A-Za-z]:\\[^\s]+|"
    r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}|[0-9a-fA-F]{64})"
)


class ValidationFailure(RuntimeError):
    """Representa un fallo controlado, sin propagar salida sensible."""


@dataclass
class ValidationRow:
    name: str
    result: str
    detail: str
    duration_seconds: float


@dataclass
class ValidationReport:
    started_at: datetime = field(default_factory=datetime.now)
    rows: list[ValidationRow] = field(default_factory=list)

    def add(self, name: str, result: str, detail: str, started: float) -> None:
        self.rows.append(
            ValidationRow(
                name=name,
                result=result,
                detail=sanitize_detail(detail),
                duration_seconds=time.monotonic() - started,
            )
        )

    @property
    def passed(self) -> bool:
        return bool(self.rows) and all(row.result == "PASS" for row in self.rows)

    def render(self) -> str:
        outcome = "APROBADA" if self.passed else "FALLIDA"
        lines = [
            "# Validacion local sanitizada de la Fase 6",
            "",
            f"Fecha: {self.started_at.astimezone().isoformat(timespec='seconds')}",
            f"Python: {sys.version.split()[0]}",
            f"Resultado global: **{outcome}**",
            "",
            "| Validacion | Resultado | Detalle seguro | Duracion |",
            "|---|---|---|---:|",
        ]
        lines.extend(
            f"| {row.name} | {row.result} | {row.detail} | {row.duration_seconds:.2f}s |"
            for row in self.rows
        )
        lines.extend(["", f"VALIDACION FASE 6: {outcome}", ""])
        return "\n".join(lines)


def sanitize_detail(value: str) -> str:
    """Convierte errores y resultados en metadatos cortos que no revelan datos."""

    normalized = " ".join(value.replace("|", "/").split())
    normalized = SENSITIVE_OUTPUT.sub("[redactado]", normalized)
    return normalized[:220] or "Sin detalle adicional"


def offline_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(OFFLINE_ENVIRONMENT)
    return environment


def run_command(
    command: list[str], *, cwd: Path, timeout: int = REPORT_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=offline_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def command_success(command: list[str], *, cwd: Path, label: str) -> subprocess.CompletedProcess[str]:
    try:
        completed = run_command(command, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValidationFailure(f"{label}_EXECUTION_FAILED") from exc
    if completed.returncode != 0:
        raise ValidationFailure(f"{label}_FAILED")
    return completed


def require_virtual_environment() -> None:
    if Path(sys.prefix).resolve() == Path(sys.base_prefix).resolve():
        raise ValidationFailure("VIRTUAL_ENV_REQUIRED")


def require_python_module(module: str) -> None:
    completed = command_success(
        [sys.executable, "-c", f"import {module}"],
        cwd=PROJECT_ROOT,
        label=f"{module.upper().replace('-', '_')}_IMPORT",
    )
    del completed


def require_free_port(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise ValidationFailure("BACKEND_PORT_UNAVAILABLE") from exc


def database_counts() -> dict[str, int]:
    if not DATABASE_FILE.is_file() or DATABASE_FILE.stat().st_size == 0:
        raise ValidationFailure("SQLITE_DATABASE_NOT_AVAILABLE")
    database_uri = f"file:{DATABASE_FILE.as_posix()}?mode=ro"
    try:
        with sqlite3.connect(database_uri, uri=True) as connection:
            names = ("documents", "document_pages", "document_chunks", "document_chunks_fts")
            counts: dict[str, int] = {}
            for name in names:
                exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE name = ?", (name,)
                ).fetchone()
                if exists is None:
                    raise ValidationFailure("SQLITE_REQUIRED_TABLE_MISSING")
                counts[name] = int(connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
            return counts
    except sqlite3.Error as exc:
        raise ValidationFailure("SQLITE_READ_CHECK_FAILED") from exc


def require_alembic_revision() -> None:
    completed = command_success(
        [sys.executable, "-m", "alembic", "current"],
        cwd=BACKEND_ROOT,
        label="ALEMBIC_CURRENT",
    )
    if "20260724_03" not in completed.stdout:
        raise ValidationFailure("ALEMBIC_REVISION_INCOMPATIBLE")


def verify_local_embedding_model() -> None:
    command_success(
        [sys.executable, "scripts/verify_models.py", "--model", "multilingual-e5-small"],
        cwd=PROJECT_ROOT,
        label="LOCAL_EMBEDDING_MODEL_VERIFICATION",
    )


def validate_static_chroma_contract() -> None:
    source = (BACKEND_ROOT / "app" / "vector_store" / "chroma_store.py").read_text(
        encoding="utf-8"
    )
    if "HttpClient" in source or "documents=" in source:
        raise ValidationFailure("CHROMA_LOCAL_CONTENT_CONTRACT_FAILED")


class BoundedOutput:
    """Consume la salida de Uvicorn sin persistir ni exponer contenido de logs."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self.lines: deque[str] = deque(maxlen=32)
        self.thread = threading.Thread(target=self._consume, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def _consume(self) -> None:
        for line in iter(self._stream.readline, ""):
            self.lines.append(line[:512])


class UvicornProcess:
    def __init__(self, port: int) -> None:
        self.port = port
        self.process: subprocess.Popen[str] | None = None
        self._outputs: list[BoundedOutput] = []

    def start(self) -> None:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--workers",
                "1",
            ],
            cwd=BACKEND_ROOT,
            env=offline_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
        )
        for stream in (self.process.stdout, self.process.stderr):
            if stream is not None:
                output = BoundedOutput(stream)
                output.start()
                self._outputs.append(output)
        deadline = time.monotonic() + HTTP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise ValidationFailure("UVICORN_START_FAILED")
            try:
                status, _ = http_request(self.port, "GET", "/api/health")
                if status == 200:
                    return
            except (URLError, TimeoutError, ValidationFailure):
                pass
            time.sleep(0.25)
        raise ValidationFailure("UVICORN_HEALTH_TIMEOUT")

    def stop(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)


def http_request(
    port: int, method: str, path: str, payload: dict[str, Any] | None = None
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
            raw = response.read(65536)
            return int(response.status), json.loads(raw.decode("utf-8"))
    except HTTPError as error:
        raw = error.read(65536)
        try:
            payload_data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload_data = {}
        return int(error.code), payload_data if isinstance(payload_data, dict) else {}


def require_status(status: int, expected: int, error_code: str | None = None) -> None:
    if status != expected:
        raise ValidationFailure("UNEXPECTED_HTTP_STATUS")
    if error_code is not None:
        raise ValidationFailure("HTTP_ERROR_CODE_REQUIRED_OUTSIDE_RESPONSE")


def error_code(response: dict[str, Any]) -> str | None:
    detail = response.get("detail")
    return detail if isinstance(detail, str) else None


def numeric(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValidationFailure("SEMANTIC_DISTANCE_INVALID")
    return float(value)


def validate_search_response(response: dict[str, Any], top_k: int) -> int:
    forbidden = ("embedding", "vector", "query", "collection", "path", "sha", "hash")
    if any(marker in json.dumps(response).lower() for marker in forbidden):
        raise ValidationFailure("SEMANTIC_RESPONSE_PRIVACY_FAILED")
    items = response.get("items")
    returned = response.get("returned")
    if not isinstance(items, list) or not isinstance(returned, int) or returned != len(items):
        raise ValidationFailure("SEMANTIC_RESPONSE_STRUCTURE_INVALID")
    if returned > top_k:
        raise ValidationFailure("SEMANTIC_RESPONSE_TOP_K_INVALID")
    distances: list[float] = []
    required = {"chunk_id", "document_id", "document_type", "chunk_index", "start_page", "end_page", "snippet", "distance_cosine"}
    for item in items:
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValidationFailure("SEMANTIC_RESPONSE_TRACEABILITY_INVALID")
        distances.append(numeric(item["distance_cosine"]))
    if distances != sorted(distances):
        raise ValidationFailure("SEMANTIC_RESPONSE_ORDER_INVALID")
    return returned


def validate_ignore_rules() -> None:
    lines = {
        line.strip()
        for line in (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    required = {"storage/vector/", "local_validation_reports/", "models/llm/", "models/embeddings/", "*.db", "storage/documents/**/*"}
    if not required.issubset(lines):
        raise ValidationFailure("LOCAL_ARTIFACT_IGNORE_RULE_MISSING")


def run_static_validations(report: ValidationReport) -> bool:
    commands = [
        ("Dependencias pip", [sys.executable, "-m", "pip", "check"], PROJECT_ROOT, "Sin conflictos"),
        ("Pruebas", [sys.executable, "-m", "pytest"], BACKEND_ROOT, "Pruebas aprobadas"),
        ("Ruff", [sys.executable, "-m", "ruff", "check", "app", "tests"], BACKEND_ROOT, "Sin errores"),
        ("mypy", [sys.executable, "-m", "mypy", "app"], BACKEND_ROOT, "Sin errores"),
    ]
    all_passed = True
    for name, command, cwd, success_detail in commands:
        started = time.monotonic()
        try:
            completed = command_success(command, cwd=cwd, label=name.upper().replace(" ", "_"))
            detail = success_detail
            if name == "Pruebas":
                match = re.search(r"(\d+) passed", completed.stdout)
                if match:
                    detail = f"{match.group(1)} aprobadas"
            report.add(name, "PASS", detail, started)
        except ValidationFailure as exc:
            report.add(name, "FAIL", str(exc), started)
            all_passed = False
    return all_passed


def add_prerequisites(report: ValidationReport, port: int) -> tuple[bool, dict[str, int] | None]:
    checks: list[tuple[str, Any, str]] = [
        ("Entorno virtual", require_virtual_environment, "Activo"),
        ("Dependencia ChromaDB", lambda: require_python_module("chromadb"), "Disponible"),
        ("Dependencia Sentence Transformers", lambda: require_python_module("sentence_transformers"), "Disponible"),
        ("Modelo local de embeddings", verify_local_embedding_model, "Verificado localmente"),
        ("Revision Alembic", require_alembic_revision, "Revision compatible"),
        ("Puerto del backend", lambda: require_free_port(port), "Disponible"),
        ("Contrato local de Chroma", validate_static_chroma_contract, "Sin HttpClient ni textos"),
    ]
    passed = True
    for name, check, detail in checks:
        started = time.monotonic()
        try:
            check()
            report.add(name, "PASS", detail, started)
        except ValidationFailure as exc:
            report.add(name, "FAIL", str(exc), started)
            passed = False
    started = time.monotonic()
    try:
        counts = database_counts()
        report.add("SQLite inicial", "PASS", f"Conteos documentales leidos; chunks: {counts['document_chunks']}", started)
        return passed, counts
    except ValidationFailure as exc:
        report.add("SQLite inicial", "FAIL", str(exc), started)
        return False, None


def run_api_flow(report: ValidationReport, port: int, counts_before: dict[str, int]) -> bool:
    server = UvicornProcess(port)
    overall = True
    counts_checked = False
    try:
        started = time.monotonic()
        server.start()
        report.add("Backend inicial", "PASS", "Health disponible con un worker", started)

        started = time.monotonic()
        status_code, semantic_before = http_request(port, "GET", "/api/search/semantic/status")
        if status_code != 200:
            raise ValidationFailure("SEMANTIC_STATUS_INITIAL_FAILED")
        report.add("Estado semantico inicial", "PASS", f"HTTP {status_code}; chunks activos: {semantic_before.get('active_chunks', 0)}; indexados: {semantic_before.get('indexed_chunks', 0)}", started)

        started = time.monotonic()
        model_code, model_status = http_request(port, "GET", "/api/models/embeddings/status")
        if model_code != 200:
            raise ValidationFailure("EMBEDDING_STATUS_INITIAL_FAILED")
        if model_status.get("state") != "unloaded":
            unload_code, _ = http_request(port, "POST", "/api/models/embeddings/unload")
            if unload_code != 200:
                raise ValidationFailure("EMBEDDING_INITIAL_UNLOAD_FAILED")
        rebuild_code, rebuild_response = http_request(port, "POST", "/api/search/semantic/rebuild")
        if rebuild_code != 503 or error_code(rebuild_response) != "EMBEDDING_MODEL_NOT_LOADED":
            raise ValidationFailure("EMBEDDING_UNLOADED_REBUILD_CONTRACT_FAILED")
        report.add("Rebuild con modelo descargado", "PASS", "HTTP 503 controlado", started)

        started = time.monotonic()
        load_code, loaded = http_request(port, "POST", "/api/models/embeddings/load")
        dimension = loaded.get("dimension")
        if load_code != 200 or loaded.get("state") != "loaded" or loaded.get("device") != "cpu" or not isinstance(dimension, int) or dimension <= 0:
            raise ValidationFailure("EMBEDDING_LOAD_VALIDATION_FAILED")
        report.add("Modelo embeddings", "PASS", f"HTTP 200; CPU; dimension: {dimension}", started)

        started = time.monotonic()
        rebuild_code, rebuilt = http_request(port, "POST", "/api/search/semantic/rebuild")
        if rebuild_code != 200 or rebuilt.get("state") != "ready" or rebuilt.get("distance_metric") != "cosine":
            raise ValidationFailure("SEMANTIC_REBUILD_FAILED")
        indexed = rebuilt.get("indexed_chunks")
        if indexed != semantic_before.get("active_chunks") or rebuilt.get("embedding_dimension") != dimension:
            raise ValidationFailure("SEMANTIC_REBUILD_COUNTS_OR_DIMENSION_INVALID")
        report.add("Reconstruccion", "PASS", f"HTTP 200; chunks indexados: {indexed}; cosine", started)

        started = time.monotonic()
        after_code, semantic_after = http_request(port, "GET", "/api/search/semantic/status")
        if after_code != 200 or semantic_after.get("state") != "ready" or semantic_after.get("dependency_available") is not True or semantic_after.get("indexed_chunks") != semantic_after.get("active_chunks") or semantic_after.get("needs_rebuild") is not False or semantic_after.get("embedding_dimension") != dimension:
            raise ValidationFailure("SEMANTIC_STATUS_AFTER_REBUILD_INVALID")
        report.add("Estado semantico posterior", "PASS", f"HTTP 200; chunks activos: {semantic_after.get('active_chunks', 0)}; indexados: {semantic_after.get('indexed_chunks', 0)}", started)

        top_k = 3
        started = time.monotonic()
        search_code, search_response = http_request(port, "POST", "/api/search/semantic", {"query": "consulta general", "top_k": top_k})
        if search_code != 200:
            raise ValidationFailure("SEMANTIC_SEARCH_FAILED")
        returned = validate_search_response(search_response, top_k)
        report.add("Busqueda semantica", "PASS", f"HTTP 200; resultados: {returned}; top_k: {top_k}", started)

        started = time.monotonic()
        filter_code, filter_response = http_request(port, "POST", "/api/search/semantic", {"query": "consulta general", "top_k": top_k, "document_types": ["jurisprudencia"], "min_page": 1, "max_page": 1000000})
        if filter_code != 200:
            raise ValidationFailure("SEMANTIC_FILTER_SEARCH_FAILED")
        filtered = validate_search_response(filter_response, top_k)
        for item in filter_response.get("items", []):
            if item["document_type"] != "jurisprudencia" or item["start_page"] < 1 or item["end_page"] > 1000000:
                raise ValidationFailure("SEMANTIC_FILTER_CONTAINMENT_INVALID")
        empty_code, _ = http_request(port, "POST", "/api/search/semantic", {"query": "   "})
        inverted_code, _ = http_request(port, "POST", "/api/search/semantic", {"query": "consulta general", "min_page": 2, "max_page": 1})
        if empty_code != 422 or inverted_code != 422:
            raise ValidationFailure("SEMANTIC_FILTER_VALIDATION_CONTRACT_FAILED")
        report.add("Filtros y validaciones", "PASS", f"Filtro HTTP 200; resultados: {filtered}; vacia e invertida HTTP 422", started)

        started = time.monotonic()
        unload_code, unloaded = http_request(port, "POST", "/api/models/embeddings/unload")
        if unload_code != 200 or unloaded.get("state") != "unloaded" or unloaded.get("dimension") is not None or unloaded.get("local_files_available") is not True:
            raise ValidationFailure("EMBEDDING_UNLOAD_VALIDATION_FAILED")
        report.add("Modelo embeddings descargado", "PASS", "HTTP 200; estado unloaded; archivos locales disponibles", started)

        server.stop()
        started = time.monotonic()
        server = UvicornProcess(port)
        server.start()
        restarted_code, restarted = http_request(port, "GET", "/api/search/semantic/status")
        if restarted_code != 200 or restarted.get("state") != "ready" or restarted.get("indexed_chunks") != restarted.get("active_chunks") or restarted.get("needs_rebuild") is not False:
            raise ValidationFailure("SEMANTIC_RESTART_PERSISTENCE_FAILED")
        load_code, _ = http_request(port, "POST", "/api/models/embeddings/load")
        resumed_code, resumed = http_request(port, "POST", "/api/search/semantic", {"query": "consulta general", "top_k": top_k})
        if load_code != 200 or resumed_code != 200:
            raise ValidationFailure("SEMANTIC_RESTART_SEARCH_FAILED")
        resumed_count = validate_search_response(resumed, top_k)
        final_unload_code, final_unloaded = http_request(port, "POST", "/api/models/embeddings/unload")
        if final_unload_code != 200 or final_unloaded.get("state") != "unloaded":
            raise ValidationFailure("EMBEDDING_FINAL_UNLOAD_FAILED")
        report.add("Persistencia tras reinicio", "PASS", f"Estado ready; busqueda HTTP 200; resultados: {resumed_count}", started)

        for flag, name in (("--status", "Script status"), ("--validate-active", "Script indice activo")):
            started = time.monotonic()
            completed = command_success([sys.executable, "scripts/validate_semantic_index.py", flag], cwd=PROJECT_ROOT, label="SEMANTIC_VALIDATION_SCRIPT")
            output = completed.stdout + completed.stderr
            if SENSITIVE_OUTPUT.search(output) or any(word in output.lower() for word in ("collection", "vector", "consulta")):
                raise ValidationFailure("SEMANTIC_VALIDATION_SCRIPT_PRIVACY_FAILED")
            report.add(name, "PASS", "Codigo de salida 0; salida sanitizada", started)

        started = time.monotonic()
        validate_ignore_rules()
        counts_after = database_counts()
        if counts_after != counts_before:
            raise ValidationFailure("SQLITE_DOCUMENTAL_COUNTS_CHANGED")
        report.add("Privacidad y persistencia documental", "PASS", f"Reglas locales presentes; chunks sin cambios: {counts_after['document_chunks']}", started)
        counts_checked = True
    except ValidationFailure as exc:
        report.add("Flujo API", "FAIL", str(exc), time.monotonic())
        overall = False
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        report.add("Flujo API", "FAIL", f"API_VALIDATION_FAILED_{type(exc).__name__}", time.monotonic())
        overall = False
    finally:
        server.stop()
        if not counts_checked:
            started = time.monotonic()
            try:
                counts_after = database_counts()
                if counts_after != counts_before:
                    raise ValidationFailure("SQLITE_DOCUMENTAL_COUNTS_CHANGED")
                report.add(
                    "SQLite final",
                    "PASS",
                    f"Conteos documentales sin cambios; chunks: {counts_after['document_chunks']}",
                    started,
                )
            except ValidationFailure as exc:
                report.add("SQLite final", "FAIL", str(exc), started)
                overall = False
    return overall


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida manualmente la Fase 6 en modo offline")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = ValidationReport()
    prerequisites_ok, counts_before = add_prerequisites(report, arguments.port)
    if prerequisites_ok and counts_before is not None:
        if run_static_validations(report):
            run_api_flow(report, arguments.port, counts_before)
    else:
        report.rows.append(ValidationRow("Flujo API", "SKIP", "Prerequisitos obligatorios no disponibles", 0.0))
    content = report.render()
    stamp = report.started_at.strftime("%Y%m%d_%H%M%S")
    timestamped = REPORTS_DIR / f"phase6_{stamp}.md"
    write_atomic(timestamped, content)
    write_atomic(REPORTS_DIR / "phase6_latest.md", content)
    outcome = "APROBADA" if report.passed else "FALLIDA"
    print(f"Informe: local_validation_reports/{timestamped.name}")
    print(f"VALIDACION FASE 6: {outcome}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
