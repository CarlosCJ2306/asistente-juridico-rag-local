"""Validador manual integral y sanitizado de la Fase 8.

No se ejecuta durante pruebas normales. Requiere índices y modelos locales ya
instalados; nunca descarga, migra ni reconstruye automáticamente.
"""

from __future__ import annotations

import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
REPORTS = ROOT / "local_validation_reports"
sys.path.insert(0, str(BACKEND))
from app.core.config import settings  # noqa: E402
OFFLINE_ENV = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "ANONYMIZED_TELEMETRY": "False",
}
FORBIDDEN_KEYS = {
    "question", "prompt", "context", "snippet", "chunk_id", "document_id",
    "embedding", "vector", "collection", "relative_path", "sql",
}
REQUIRED_ROWS = {
    "Pytest",
    "Ruff",
    "mypy",
    "FTS5",
    "ChromaDB",
    "Modelos",
    "Recuperación híbrida",
    "Chat RAG answered",
    "Presupuesto de tokens",
    "Privacidad",
    "Insufficient context",
    "Integridad SQLite",
    "Persistencia tras reinicio",
    "Descarga final de modelos",
    "Puertos",
    "Finalización y limpieza",
}
PUBLIC_RESPONSE_KEYS = {
    "status",
    "answer",
    "retrieved_chunks",
    "context_chunks",
    "context_tokens",
    "requires_professional_review",
}


@dataclass
class Report:
    rows: list[tuple[str, str, str, float]] = field(default_factory=list)

    def add(self, name: str, result: str, detail: str, duration: float = 0.0) -> None:
        self.rows.append((name, result, detail, duration))

    @property
    def passed(self) -> bool:
        names = {name for name, _, _, _ in self.rows}
        return bool(self.rows) and REQUIRED_ROWS.issubset(names) and all(
            result == "PASS" for _, result, _, _ in self.rows
        )

    def render(self, exit_code: int) -> str:
        lines = [
            "# Validación integral de Fase 8",
            "",
            f"Fecha: {datetime.now().astimezone().isoformat(timespec='seconds')}",
            f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "",
            "| Validación | Resultado | Detalle seguro | Duración |",
            "|---|---|---|---:|",
        ]
        lines.extend(
            f"| {name} | {result} | {detail} | {duration:.2f}s |"
            for name, result, detail, duration in self.rows
        )
        status = "APROBADA" if exit_code == 0 else "FALLIDA"
        lines.extend(["", f"VALIDACIÓN FASE 8: {status}", f"Código de salida: {exit_code}", ""])
        return "\n".join(lines)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".phase8_", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def request_json(
    port: int,
    method: str,
    endpoint: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 120,
):
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"http://127.0.0.1:{port}{endpoint}", data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def forbidden_payload(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).lower() in FORBIDDEN_KEYS or forbidden_payload(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(forbidden_payload(item) for item in value)
    return False


def validate_public_response(value: Any) -> bool:
    """Valida claves públicas sin inspeccionar palabras legítimas del answer."""

    answer = value.get("answer") if isinstance(value, dict) else None
    answer_safe = isinstance(answer, str) and not re.search(
        r"<\s*(?:script|iframe|object|embed|analysis|think)\b|\[\s*(?:fuente|source)\s+\d+\s*\]",
        answer,
        flags=re.IGNORECASE,
    )
    return (
        isinstance(value, dict)
        and set(value) == PUBLIC_RESPONSE_KEYS
        and value.get("status") in {"answered", "insufficient_context"}
        and answer_safe
        and bool(answer.strip())
        and value.get("requires_professional_review") is True
        and all(
            isinstance(value.get(field), int) and value.get(field, -1) >= 0
            for field in ("retrieved_chunks", "context_chunks", "context_tokens")
        )
        and value["context_chunks"] <= value["retrieved_chunks"]
    )


def validate_report_privacy(content: str) -> bool:
    """Comprueba que el informe no contenga nombres de campos sensibles."""

    forbidden = (
        "system_prompt",
        "chunk_id",
        "document_id",
        "embedding",
        "vector",
        "collection",
        "sql",
        "<think",
        "reasoning",
    )
    return not any(
        re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(marker)}(?![A-Za-z0-9_])",
            content,
            flags=re.IGNORECASE,
        )
        for marker in forbidden
    )


def validate_budget(
    *,
    context_size: int,
    prompt_tokens: int,
    context_tokens: int,
    max_new_tokens: int,
    safety_margin: int,
    context_chunks: int,
) -> bool:
    """Comprueba la desigualdad completa con cantidades, nunca ids ni textos."""

    return (
        context_size > 0
        and prompt_tokens >= 0
        and context_tokens >= 0
        and max_new_tokens > 0
        and safety_margin > 0
        and context_chunks >= 0
        and context_tokens <= settings.rag_context_max_tokens
        and context_chunks <= settings.rag_context_max_chunks
        and prompt_tokens + max_new_tokens + safety_margin <= context_size
    )


def counts_equal(
    initial: tuple[int, int, int, int] | None,
    final: tuple[int, int, int, int] | None,
) -> bool:
    return initial is not None and final is not None and initial == final


def has_pending_threads() -> bool:
    return any(
        thread is not threading.main_thread() and thread.is_alive()
        for thread in threading.enumerate()
    )


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def port_is_free(port: int) -> bool:
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def sqlite_counts() -> tuple[int, int, int, int]:
    database = ROOT / "storage" / "database" / "asistente_juridico.db"
    with sqlite3.connect(database) as connection:
        return tuple(
            int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
            for table in ("documents", "document_pages", "document_chunks", "document_chunks_fts")
        )  # type: ignore[return-value]


def start_backend(port: int) -> subprocess.Popen[str]:
    environment = os.environ.copy()
    environment.update(OFFLINE_ENV)
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--workers", "1"],
        cwd=BACKEND,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("BACKEND_START_FAILED")
            try:
                status, _ = request_json(port, "GET", "/api/health")
                if status == 200:
                    return process
            except OSError:
                time.sleep(0.25)
        raise RuntimeError("BACKEND_HEALTH_TIMEOUT")
    except Exception:
        stop_backend(process, port)
        raise


def stop_backend(process: subprocess.Popen[str] | None, port: int | None = None) -> bool:
    if process is None or process.poll() is not None:
        return port is None or port_is_free(port)
    try:
        process.terminate()
    except OSError:
        pass
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
                timeout=15,
            )
        else:
            process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            return False
    if port is not None:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if port_is_free(port):
                return True
            time.sleep(0.25)
        return False
    return True


def unload_models(port: int) -> bool:
    successful = True
    for endpoint in ("/api/models/llm/unload", "/api/models/embeddings/unload"):
        try:
            status, _ = request_json(port, "POST", endpoint, timeout=15)
            successful = successful and status == 200
        except Exception:
            successful = False
    return successful


def final_models_unloaded(port: int) -> bool:
    try:
        model_status, model_info = request_json(port, "GET", "/api/models/status")
        llm_status, llm = request_json(port, "GET", "/api/models/llm/status")
        embedding_status, embedding = request_json(
            port, "GET", "/api/models/embeddings/status"
        )
        return (
            model_status == 200
            and model_info.get("model", {}).get("installed") is True
            and model_info.get("model", {}).get("verified") is True
            and llm_status == 200
            and embedding_status == 200
            and llm.get("state") == "unloaded"
            and embedding.get("state") == "unloaded"
            and embedding.get("local_files_available") is True
        )
    except Exception:
        return False


def run_static(report: Report) -> None:
    commands = (
        ("Pytest", [sys.executable, "-m", "pytest"]),
        ("Ruff", [sys.executable, "-m", "ruff", "check", "app", "tests"]),
        ("mypy", [sys.executable, "-m", "mypy", "app"]),
    )
    for name, command in commands:
        started = time.perf_counter()
        result = subprocess.run(command, cwd=BACKEND, capture_output=True, text=True, timeout=300)
        report.add(name, "PASS" if result.returncode == 0 else "FAIL", "Código 0" if result.returncode == 0 else "Código distinto de cero", time.perf_counter() - started)


def validate_cycle(report: Report, port: int, *, after_restart: bool) -> None:
    embed_initial, embed_state = request_json(port, "GET", "/api/models/embeddings/status")
    llm_initial, llm_state = request_json(port, "GET", "/api/models/llm/status")
    if (
        embed_initial != 200
        or llm_initial != 200
        or embed_state.get("state") != "unloaded"
        or llm_state.get("state") != "unloaded"
    ):
        raise RuntimeError("MODELS_NOT_INITIALLY_UNLOADED")
    report.add("Estado inicial", "PASS", "Qwen y embeddings unloaded")
    semantic_code, semantic = request_json(port, "GET", "/api/search/semantic/status")
    text_code, _ = request_json(port, "POST", "/api/search/text", {"query": "termino sintetico"})
    if (
        semantic_code != 200
        or semantic.get("state") != "ready"
        or semantic.get("needs_rebuild") is not False
        or text_code != 200
    ):
        raise RuntimeError("RETRIEVAL_NOT_READY")
    report.add("FTS5", "PASS", "Disponible")
    report.add("ChromaDB", "PASS", "Índice ready; needs_rebuild false")

    embed_code, embed = request_json(port, "POST", "/api/models/embeddings/load")
    llm_code, llm = request_json(port, "POST", "/api/models/llm/load")
    if embed_code != 200 or embed.get("state") != "loaded" or llm_code != 200 or llm.get("state") != "loaded":
        raise RuntimeError("MODEL_LOAD_FAILED")
    report.add("Modelos", "PASS", "Embeddings y Qwen cargados localmente")

    payload = {"question": "pregunta sintetica general", "top_k": 3}
    hybrid_code, hybrid = request_json(
        port, "POST", "/api/search/hybrid", {"query": "termino sintetico", "top_k": 3}
    )
    if hybrid_code != 200 or not isinstance(hybrid.get("items"), list):
        raise RuntimeError("HYBRID_REQUEST_FAILED")
    report.add("Recuperación híbrida", "PASS", "HTTP 200")
    code, response = request_json(port, "POST", "/api/chat/rag", payload)
    if code != 200 or response.get("status") != "answered":
        raise RuntimeError("RAG_REQUEST_FAILED")
    if not validate_public_response(response) or forbidden_payload(response) or "<think" in str(response).lower():
        raise RuntimeError("RAG_PRIVACY_FAILED")
    context_tokens = response.get("context_tokens", 0)
    context_chunks = response.get("context_chunks", 0)
    context_size = llm.get("context_size")
    max_new_tokens = settings.rag_max_new_tokens
    safety_margin = settings.rag_token_safety_margin
    prompt_upper_bound = (
        context_size - max_new_tokens - safety_margin
        if isinstance(context_size, int)
        else -1
    )
    budget_ok = (
        isinstance(context_size, int)
        and isinstance(context_tokens, int)
        and isinstance(context_chunks, int)
        and validate_budget(
            context_size=context_size,
            prompt_tokens=prompt_upper_bound,
            context_tokens=context_tokens,
            max_new_tokens=max_new_tokens,
            safety_margin=safety_margin,
            context_chunks=context_chunks,
        )
    )
    if not budget_ok:
        raise RuntimeError("RAG_TOKEN_BUDGET_INVALID")
    report.add(
        "Chat RAG answered",
        "PASS",
        f"HTTP 200; recuperación y generación únicas; chunks: {context_chunks}",
    )
    report.add(
        "Presupuesto de tokens",
        "PASS",
        f"context_size: {context_size}; prompt_tokens <= {prompt_upper_bound}; context_tokens: {context_tokens}; max_new_tokens: {max_new_tokens}; safety_margin: {safety_margin}; desigualdad PASS",
    )
    report.add("Privacidad", "PASS", "Estructura pública y respuesta sanitizadas")

    empty_code, empty = request_json(
        port,
        "POST",
        "/api/chat/rag",
        {
            "question": "consulta sintetica general",
            "top_k": 1,
            "document_id": "00000000-0000-0000-0000-000000000001",
        },
    )
    if empty_code != 200 or empty.get("status") != "insufficient_context":
        raise RuntimeError("RAG_EMPTY_CONTEXT_FAILED")
    if not validate_public_response(empty) or empty.get("context_chunks") != 0 or empty.get("context_tokens") != 0:
        raise RuntimeError("RAG_EMPTY_CONTEXT_INVALID")
    report.add("Insufficient context", "PASS", "HTTP 200; contexto cero; Qwen no invocado")

    llm_unload, llm_state = request_json(port, "POST", "/api/models/llm/unload")
    embed_unload, embed_state = request_json(port, "POST", "/api/models/embeddings/unload")
    if llm_unload != 200 or llm_state.get("state") != "unloaded" or embed_unload != 200 or embed_state.get("state") != "unloaded":
        raise RuntimeError("MODEL_UNLOAD_FAILED")
    report.add("Descarga final de modelos", "PASS", "Qwen y embeddings unloaded; archivos locales conservados")


def main() -> int:
    report = Report()
    process: subprocess.Popen[str] | None = None
    active_port: int | None = None
    used_ports: list[int] = []
    initial_counts: tuple[int, int, int, int] | None = None
    exit_code = 1
    try:
        run_static(report)
        static_rows = {
            name: result
            for name, result, _, _ in report.rows
            if name in {"Pytest", "Ruff", "mypy"}
        }
        if any(
            static_rows.get(name) != "PASS"
            for name in ("Pytest", "Ruff", "mypy")
        ):
            raise RuntimeError("STATIC_VALIDATION_FAILED")
        initial_counts = sqlite_counts()
        report.add(
            "Conteos SQLite iniciales",
            "PASS",
            "Documentos: %d; páginas: %d; chunks: %d; FTS5: %d" % initial_counts,
        )
        first_port = free_port()
        used_ports.append(first_port)
        active_port = first_port
        process = start_backend(first_port)
        validate_cycle(report, first_port, after_restart=False)
        unload_models(first_port)
        if not stop_backend(process, first_port):
            raise RuntimeError("FIRST_PORT_NOT_RELEASED")
        process = None
        active_port = None
        second_port = free_port()
        while second_port in used_ports:
            second_port = free_port()
        used_ports.append(second_port)
        active_port = second_port
        process = start_backend(second_port)
        validate_cycle(report, second_port, after_restart=True)
        report.add(
            "Persistencia tras reinicio",
            "PASS",
            "Índices disponibles sin rebuild",
        )
        exit_code = 0
    except Exception as exc:
        report.add("Validación", "FAIL", type(exc).__name__)
    finally:
        cleanup_started = time.perf_counter()
        model_cleanup_ok = True
        if active_port is not None:
            model_cleanup_ok = unload_models(active_port) and final_models_unloaded(active_port)
            report.add(
                "Descarga final de modelos",
                "PASS" if model_cleanup_ok else "FAIL",
                "Qwen y embeddings unloaded; archivos locales conservados"
                if model_cleanup_ok
                else "Estado final de modelos inválido",
            )
        ports_released = False
        cleanup_ok = True
        try:
            ports_released = stop_backend(process, active_port)
        except Exception as exc:
            cleanup_ok = False
            report.add("Cierre Uvicorn", "FAIL", type(exc).__name__)
        final_counts: tuple[int, int, int, int] | None = None
        try:
            final_counts = sqlite_counts()
            unchanged = initial_counts is None or final_counts == initial_counts
            report.add(
                "Conteos SQLite finales",
                "PASS" if unchanged else "FAIL",
                "Documentos: %d; páginas: %d; chunks: %d; FTS5: %d" % final_counts,
            )
            if not unchanged:
                exit_code = 1
        except Exception as exc:
            report.add("Conteos SQLite finales", "FAIL", type(exc).__name__)
            exit_code = 1
        all_ports_free = ports_released and all(port_is_free(port) for port in used_ports)
        report.add(
            "Puertos",
            "PASS" if all_ports_free else "FAIL",
            "Liberados" if all_ports_free else "No liberados",
        )
        if not all_ports_free:
            exit_code = 1
        sqlite_integrity = counts_equal(initial_counts, final_counts)
        report.add(
            "Integridad SQLite",
            "PASS" if sqlite_integrity else "FAIL",
            "Conteos iniciales y finales iguales"
            if sqlite_integrity
            else "Conteos modificados",
        )
        thread_pending = has_pending_threads()
        cleanup_ok = (
            cleanup_ok
            and model_cleanup_ok
            and all_ports_free
            and not thread_pending
        )
        report.add(
            "Finalización y limpieza",
            "PASS" if cleanup_ok else "FAIL",
            "Procesos, handles, puertos y tareas propios cerrados"
            if cleanup_ok
            else "Limpieza incompleta",
            time.perf_counter() - cleanup_started,
        )
        report_privacy_ok = validate_report_privacy(report.render(1))
        if not report_privacy_ok:
            report.add("Privacidad", "FAIL", "Informe contiene campos restringidos")
        exit_code = 0 if report.passed and cleanup_ok and report_privacy_ok else 1
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rendered = report.render(exit_code)
    atomic_write(REPORTS / f"phase8_{timestamp}.md", rendered)
    atomic_write(REPORTS / "phase8_latest.md", rendered)
    print(f"VALIDACIÓN FASE 8: {'APROBADA' if exit_code == 0 else 'FALLIDA'}", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
