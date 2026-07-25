"""Validador manual offline de la recuperación híbrida de la Fase 7.

No reconstruye índices ni modifica SQLite. Genera exclusivamente un informe
sanitizado y requiere que FTS5 y el índice semántico ya estén disponibles.
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
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402


DATABASE_FILE = PROJECT_ROOT / "storage" / "database" / "asistente_juridico.db"
REPORTS_DIR = PROJECT_ROOT / "local_validation_reports"
OFFLINE_ENV = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "ANONYMIZED_TELEMETRY": "False",
}


class ValidationFailure(RuntimeError):
    pass


@dataclass
class Row:
    name: str
    result: str
    detail: str
    duration: float


@dataclass(frozen=True)
class ValidationSnapshot:
    database_counts: dict[str, int]
    indexed_chunks: int


@dataclass
class Report:
    started: datetime = field(default_factory=datetime.now)
    rows: list[Row] = field(default_factory=list)

    def add(self, name: str, result: str, detail: str, started: float) -> None:
        safe = " ".join(detail.replace("|", "/").split())[:200]
        self.rows.append(Row(name, result, safe, time.monotonic() - started))

    @property
    def passed(self) -> bool:
        return bool(self.rows) and all(row.result == "PASS" for row in self.rows)

    def render(self) -> str:
        outcome = "APROBADA" if self.passed else "FALLIDA"
        lines = [
            "# Validación local sanitizada de la Fase 7",
            "",
            f"Fecha: {self.started.astimezone().isoformat(timespec='seconds')}",
            f"Resultado global: **{outcome}**",
            "",
            "| Validación | Resultado | Detalle seguro | Duración |",
            "|---|---|---|---:|",
        ]
        lines.extend(
            f"| {row.name} | {row.result} | {row.detail} | {row.duration:.2f}s |"
            for row in self.rows
        )
        lines.extend(["", f"VALIDACIÓN FASE 7: {outcome}", ""])
        return "\n".join(lines)


def environment() -> dict[str, str]:
    result = os.environ.copy()
    result.update(OFFLINE_ENV)
    return result


def counts() -> dict[str, int]:
    if not DATABASE_FILE.is_file():
        raise ValidationFailure("SQLITE_NOT_AVAILABLE")
    uri = f"file:{DATABASE_FILE.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        return {
            name: int(connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
            for name in (
                "documents",
                "document_pages",
                "document_chunks",
                "document_chunks_fts",
            )
        }


def request_json(
    port: int,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body else {},
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310
            return int(response.status), json.loads(response.read(65536))
    except HTTPError as error:
        try:
            data = json.loads(error.read(65536))
        except json.JSONDecodeError:
            data = {}
        return int(error.code), data


def validate_hybrid(payload: dict[str, Any], top_k: int) -> int:
    items = payload.get("items")
    if not isinstance(items, list) or payload.get("returned") != len(items):
        raise ValidationFailure("HYBRID_RESPONSE_INVALID")
    if len(items) > top_k:
        raise ValidationFailure("HYBRID_TOP_K_INVALID")
    seen: set[str] = set()
    previous = math.inf
    for item in items:
        if not isinstance(item, dict):
            raise ValidationFailure("HYBRID_ITEM_INVALID")
        chunk_id = item.get("chunk_id")
        score = item.get("hybrid_score")
        if not isinstance(chunk_id, str) or chunk_id in seen:
            raise ValidationFailure("HYBRID_DEDUPLICATION_INVALID")
        if not isinstance(score, (int, float)) or not math.isfinite(score) or score <= 0:
            raise ValidationFailure("HYBRID_SCORE_INVALID")
        expected = 0.0
        text_rank = item.get("text_rank")
        semantic_rank = item.get("semantic_rank")
        if type(text_rank) is int and text_rank > 0:
            expected += settings.hybrid_text_weight / (settings.hybrid_rrf_k + text_rank)
        elif text_rank is not None:
            raise ValidationFailure("HYBRID_RANK_INVALID")
        if type(semantic_rank) is int and semantic_rank > 0:
            expected += settings.hybrid_semantic_weight / (
                settings.hybrid_rrf_k + semantic_rank
            )
        elif semantic_rank is not None:
            raise ValidationFailure("HYBRID_RANK_INVALID")
        if (text_rank is not None) is not (item.get("appeared_in_text") is True):
            raise ValidationFailure("HYBRID_SOURCE_TRACE_INVALID")
        if (semantic_rank is not None) is not (
            item.get("appeared_in_semantic") is True
        ):
            raise ValidationFailure("HYBRID_SOURCE_TRACE_INVALID")
        if not math.isclose(score, expected, rel_tol=1e-9):
            raise ValidationFailure("HYBRID_RRF_INVALID")
        if score > previous:
            raise ValidationFailure("HYBRID_ORDER_INVALID")
        previous = float(score)
        seen.add(chunk_id)
    if _contains_forbidden_key(payload):
        raise ValidationFailure("HYBRID_PRIVACY_INVALID")
    return len(items)


def validate_text_response(payload: dict[str, Any]) -> int:
    items = payload.get("items")
    if not isinstance(items, list) or payload.get("total", 0) < len(items):
        raise ValidationFailure("TEXT_RESPONSE_INVALID")
    ranks: list[float] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValidationFailure("TEXT_ITEM_INVALID")
        chunk_id = item.get("chunk_id")
        rank = item.get("rank_bm25")
        if not isinstance(chunk_id, str) or chunk_id in seen:
            raise ValidationFailure("TEXT_DEDUPLICATION_INVALID")
        if not isinstance(rank, (int, float)) or isinstance(rank, bool) or not math.isfinite(rank):
            raise ValidationFailure("TEXT_RANK_INVALID")
        seen.add(chunk_id)
        ranks.append(float(rank))
    if ranks != sorted(ranks):
        raise ValidationFailure("TEXT_ORDER_INVALID")
    return len(items)


def validate_semantic_response(payload: dict[str, Any], top_k: int) -> int:
    items = payload.get("items")
    if not isinstance(items, list) or payload.get("returned") != len(items):
        raise ValidationFailure("SEMANTIC_RESPONSE_INVALID")
    if len(items) > top_k:
        raise ValidationFailure("SEMANTIC_TOP_K_INVALID")
    distances: list[float] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValidationFailure("SEMANTIC_ITEM_INVALID")
        chunk_id = item.get("chunk_id")
        distance = item.get("distance_cosine")
        if not isinstance(chunk_id, str) or chunk_id in seen:
            raise ValidationFailure("SEMANTIC_DEDUPLICATION_INVALID")
        if not isinstance(distance, (int, float)) or isinstance(distance, bool) or not math.isfinite(distance):
            raise ValidationFailure("SEMANTIC_DISTANCE_INVALID")
        seen.add(chunk_id)
        distances.append(float(distance))
    if distances != sorted(distances):
        raise ValidationFailure("SEMANTIC_ORDER_INVALID")
    return len(items)


def run_static_checks(report: Report) -> None:
    commands = [
        ("Pytest", [sys.executable, "-m", "pytest"]),
        ("Ruff", [sys.executable, "-m", "ruff", "check", "app", "tests"]),
        ("mypy", [sys.executable, "-m", "mypy", "app"]),
    ]
    for name, command in commands:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=BACKEND_ROOT,
                env=environment(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
                check=False,
            )
            if completed.returncode != 0:
                report.add(name, "FAIL", f"{name.upper()}_FAILED", started)
                continue
            detail = "Sin errores"
            if name == "Pytest":
                match = re.search(r"(\d+) passed", completed.stdout)
                detail = f"{match.group(1)} pruebas aprobadas" if match else "Pruebas aprobadas"
            report.add(name, "PASS", detail, started)
        except (OSError, subprocess.TimeoutExpired) as exc:
            report.add(name, "FAIL", f"{name.upper()}_{type(exc).__name__}", started)


def _contains_forbidden_key(value: object) -> bool:
    """Inspecciona nombres de campos, no contenido documental ni palabras legítimas."""

    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower()
            if (
                normalized in {"query", "match_expression", "sql", "sha256"}
                or "embedding" in normalized
                or "vector" in normalized
                or "collection" in normalized
                or normalized.endswith("path")
            ):
                return True
            if _contains_forbidden_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def run(port: int, report: Report) -> ValidationSnapshot:
    before = counts()
    started = time.monotonic()
    model_status, initial_model = request_json(
        port, "GET", "/api/models/embeddings/status"
    )
    if model_status != 200 or initial_model.get("state") != "unloaded":
        raise ValidationFailure("EMBEDDING_MODEL_NOT_UNLOADED")
    status, semantic = request_json(port, "GET", "/api/search/semantic/status")
    if (
        status != 200
        or semantic.get("state") != "ready"
        or semantic.get("needs_rebuild") is not False
        or semantic.get("dependency_available") is not True
    ):
        raise ValidationFailure("SEMANTIC_INDEX_NOT_READY")
    indexed_chunks = semantic.get("indexed_chunks")
    if not isinstance(indexed_chunks, int) or indexed_chunks < 0:
        raise ValidationFailure("SEMANTIC_INDEX_INVALID")

    query = "consulta sintética general"
    text_status, text_initial = request_json(
        port,
        "POST",
        "/api/search/text",
        {"query": query, "page": 1, "page_size": 1},
    )
    if text_status != 200:
        raise ValidationFailure("TEXT_SEARCH_INDEX_NOT_READY")
    validate_text_response(text_initial)
    report.add(
        "Índices",
        "PASS",
        "FTS5 e índice semántico disponibles; modelo inicialmente unloaded",
        started,
    )

    started = time.monotonic()
    load_status, loaded = request_json(port, "POST", "/api/models/embeddings/load")
    if load_status != 200 or loaded.get("state") != "loaded":
        raise ValidationFailure("EMBEDDING_MODEL_NOT_LOADED")
    report.add("Embeddings", "PASS", "Modelo local cargado", started)

    top_k = 5
    common = {
        "query": query,
        "document_types": ["jurisprudencia"],
        "min_page": 1,
        "max_page": 1_000_000,
    }
    started = time.monotonic()
    text_status, text_payload = request_json(
        port, "POST", "/api/search/text", {**common, "page": 1, "page_size": top_k}
    )
    semantic_status, semantic_payload = request_json(
        port, "POST", "/api/search/semantic", {**common, "top_k": top_k}
    )
    hybrid_status, hybrid_payload = request_json(
        port, "POST", "/api/search/hybrid", {**common, "top_k": top_k}
    )
    if (text_status, semantic_status, hybrid_status) != (200, 200, 200):
        raise ValidationFailure("SEARCH_SOURCE_UNAVAILABLE")
    text_count = validate_text_response(text_payload)
    semantic_count = validate_semantic_response(semantic_payload, top_k)
    returned = validate_hybrid(hybrid_payload, top_k)
    items = hybrid_payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValidationFailure("HYBRID_FILTER_VALIDATION_EMPTY")
    first_document_id = items[0].get("document_id")
    if not isinstance(first_document_id, str):
        raise ValidationFailure("HYBRID_FILTER_ID_INVALID")
    filtered_status, filtered_payload = request_json(
        port,
        "POST",
        "/api/search/hybrid",
        {**common, "document_id": first_document_id, "top_k": top_k},
    )
    if filtered_status != 200:
        raise ValidationFailure("HYBRID_FILTER_VALIDATION_FAILED")
    validate_hybrid(filtered_payload, top_k)
    filtered_items = filtered_payload.get("items")
    if not isinstance(filtered_items, list) or any(
        item.get("document_id") != first_document_id
        or item.get("document_type") != "jurisprudencia"
        or item.get("start_page", 0) < 1
        or item.get("end_page", 1_000_001) > 1_000_000
        for item in filtered_items
        if isinstance(item, dict)
    ):
        raise ValidationFailure("HYBRID_FILTER_CONTAINMENT_INVALID")
    report.add(
        "Recuperación híbrida",
        "PASS",
        f"Fuentes disponibles; textuales: {text_count}; semánticos: {semantic_count}; híbridos: {returned}; top_k: {top_k}",
        started,
    )
    del text_payload, semantic_payload

    invalid_empty, _ = request_json(port, "POST", "/api/search/hybrid", {"query": " "})
    invalid_range, _ = request_json(
        port,
        "POST",
        "/api/search/hybrid",
        {"query": query, "min_page": 2, "max_page": 1},
    )
    invalid_top_k, _ = request_json(
        port,
        "POST",
        "/api/search/hybrid",
        {"query": query, "top_k": 0},
    )
    if (invalid_empty, invalid_range, invalid_top_k) != (422, 422, 422):
        raise ValidationFailure("HYBRID_VALIDATION_STATUS_INVALID")

    started = time.monotonic()
    unload_status, unloaded = request_json(port, "POST", "/api/models/embeddings/unload")
    if unload_status != 200 or unloaded.get("state") != "unloaded":
        raise ValidationFailure("EMBEDDING_UNLOAD_FAILED")
    after = counts()
    if before != after:
        raise ValidationFailure("SQLITE_COUNTS_CHANGED")
    report.add("Integridad", "PASS", "Modelo unloaded; conteos SQLite sin cambios", started)
    return ValidationSnapshot(database_counts=before, indexed_chunks=indexed_chunks)


def validate_persistence(
    port: int,
    report: Report,
    snapshot: ValidationSnapshot,
) -> None:
    started = time.monotonic()
    status, semantic = request_json(port, "GET", "/api/search/semantic/status")
    if (
        status != 200
        or semantic.get("state") != "ready"
        or semantic.get("indexed_chunks") != snapshot.indexed_chunks
    ):
        raise ValidationFailure("SEMANTIC_PERSISTENCE_INVALID")
    model_status, model = request_json(port, "GET", "/api/models/embeddings/status")
    if model_status != 200 or model.get("state") != "unloaded":
        raise ValidationFailure("EMBEDDING_MODEL_NOT_UNLOADED")
    query = "consulta sintética general"
    text_status, _ = request_json(
        port,
        "POST",
        "/api/search/text",
        {"query": query, "page": 1, "page_size": 1},
    )
    if text_status != 200:
        raise ValidationFailure("TEXT_INDEX_PERSISTENCE_INVALID")
    load_status, _ = request_json(port, "POST", "/api/models/embeddings/load")
    hybrid_status, hybrid = request_json(
        port,
        "POST",
        "/api/search/hybrid",
        {"query": query, "top_k": 3},
    )
    unload_status, unloaded = request_json(
        port, "POST", "/api/models/embeddings/unload"
    )
    if (
        load_status != 200
        or hybrid_status != 200
        or unload_status != 200
        or unloaded.get("state") != "unloaded"
    ):
        raise ValidationFailure("HYBRID_PERSISTENCE_INVALID")
    validate_hybrid(hybrid, 3)
    if counts() != snapshot.database_counts:
        raise ValidationFailure("SQLITE_COUNTS_CHANGED")
    report.add(
        "Persistencia",
        "PASS",
        "FTS5 y semántico disponibles tras reinicio; SQLite sin cambios",
        started,
    )


def select_free_port(*, excluded: set[int] | None = None) -> int:
    excluded = excluded or set()
    for _ in range(8):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            selected = int(probe.getsockname()[1])
        if selected not in excluded:
            return selected
    raise ValidationFailure("NO_LOCAL_PORT_AVAILABLE")


def start_backend(port: int) -> subprocess.Popen[str]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", port))
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--workers",
            "1",
        ],
        cwd=BACKEND_ROOT,
        env=environment(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ValidationFailure("BACKEND_START_FAILED")
        try:
            if request_json(port, "GET", "/api/health")[0] == 200:
                return process
        except (URLError, TimeoutError):
            time.sleep(0.25)
    stop_backend(process, port=port)
    raise ValidationFailure("BACKEND_START_FAILED")


def port_accepts_connections(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def wait_port_released(port: int, *, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    delay = 0.05
    while time.monotonic() < deadline:
        if not port_accepts_connections(port):
            return
        time.sleep(delay)
        delay = min(delay * 1.5, 0.5)
    raise ValidationFailure("PORT_RELEASE_TIMEOUT")


def stop_backend(
    process: subprocess.Popen[str] | None,
    *,
    port: int | None = None,
) -> None:
    if process is None or process.poll() is not None:
        if process is not None:
            _close_process_handles(process)
        if port is not None:
            wait_port_released(port)
        return
    try:
        process.terminate()
    except OSError as exc:
        _close_process_handles(process)
        _terminate_process_tree(process)
        raise ValidationFailure("UVICORN_TERMINATE_FAILED") from exc
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired as exc:
            _terminate_process_tree(process)
            raise ValidationFailure("UVICORN_CLOSE_FAILED") from exc
    finally:
        _close_process_handles(process)
    if process.poll() is None:
        _terminate_process_tree(process)
        if process.poll() is None:
            raise ValidationFailure("UVICORN_PROCESS_STILL_RUNNING")
    if port is not None:
        wait_port_released(port)


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    """Elimina únicamente el árbol del proceso Uvicorn que este script inició."""

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    else:
        process.kill()


def _close_process_handles(process: subprocess.Popen[str]) -> None:
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is not None:
            stream.close()


def _unload_if_loaded(port: int) -> None:
    status, payload = request_json(port, "GET", "/api/models/embeddings/status")
    if status != 200:
        raise ValidationFailure("EMBEDDING_STATUS_CLOSE_FAILED")
    if payload.get("state") == "loaded":
        unload_status, unloaded = request_json(
            port, "POST", "/api/models/embeddings/unload"
        )
        if unload_status != 200 or unloaded.get("state") != "unloaded":
            raise ValidationFailure("EMBEDDING_UNLOAD_CLOSE_FAILED")


def start_backend_with_retries(
    preferred_port: int,
    *,
    excluded_ports: set[int] | None = None,
    attempts: int = 3,
) -> tuple[subprocess.Popen[str], int]:
    excluded = set(excluded_ports or set())
    candidate = preferred_port
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            process = start_backend(candidate)
            return process, candidate
        except (OSError, ValidationFailure) as exc:
            last_error = exc
            excluded.add(candidate)
            candidate = select_free_port(excluded=excluded)
    raise ValidationFailure("UVICORN_START_RETRIES_EXHAUSTED") from last_error


def require_free_port(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", port))


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida la Fase 7 sin reconstruir índices")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    report = Report()
    started = time.monotonic()
    process: subprocess.Popen[str] | None = None
    process_port: int | None = None
    first_port: int | None = None
    second_port: int | None = None
    snapshot: ValidationSnapshot | None = None
    try:
        run_static_checks(report)
        if not report.passed:
            raise ValidationFailure("STATIC_VALIDATION_FAILED")
        process, first_port = start_backend_with_retries(args.port)
        process_port = first_port
        report.add("Backend", "PASS", "Servicio local disponible", started)
        snapshot = run(first_port, report)
        stop_backend(process, port=first_port)
        process = None
        process_port = None
        second_port = select_free_port(excluded={first_port})
        process, second_port = start_backend_with_retries(
            second_port, excluded_ports={first_port}
        )
        process_port = second_port
        validate_persistence(second_port, report, snapshot)
    except (ValidationFailure, OSError, sqlite3.Error, URLError) as exc:
        report.add("Validación", "FAIL", type(exc).__name__, started)
    finally:
        if process is not None:
            try:
                if process_port is not None:
                    _unload_if_loaded(process_port)
                stop_backend(process, port=process_port)
            except (OSError, ValidationFailure) as exc:
                report.add("Cierre Uvicorn", "FAIL", type(exc).__name__, time.monotonic())
        if snapshot is None:
            try:
                final_counts = counts()
                report.add(
                    "Conteos SQLite finales",
                    "PASS",
                    f"Conteos documentales leídos; chunks: {final_counts['document_chunks']}",
                    time.monotonic(),
                )
            except (OSError, sqlite3.Error, ValidationFailure) as exc:
                report.add("Conteos SQLite finales", "FAIL", type(exc).__name__, time.monotonic())
        for port in (first_port, second_port):
            if port is None:
                continue
            port_started = time.monotonic()
            try:
                require_free_port(port)
                report.add("Puerto", "PASS", "Puerto liberado", port_started)
            except OSError:
                report.add("Puerto", "FAIL", "PORT_NOT_RELEASED", port_started)
        if snapshot is not None:
            try:
                final_counts = counts()
                result = "PASS" if final_counts == snapshot.database_counts else "FAIL"
                report.add(
                    "Conteos SQLite finales",
                    result,
                    f"Conteos documentales leídos; chunks: {final_counts['document_chunks']}",
                    time.monotonic(),
                )
            except (OSError, sqlite3.Error, ValidationFailure) as exc:
                report.add("Conteos SQLite finales", "FAIL", type(exc).__name__, time.monotonic())
    content = report.render()
    stamp = report.started.strftime("%Y%m%d_%H%M%S")
    atomic_write(REPORTS_DIR / f"phase7_{stamp}.md", content)
    atomic_write(REPORTS_DIR / "phase7_latest.md", content)
    print("VALIDACIÓN FASE 7:", "APROBADA" if report.passed else "FALLIDA")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
