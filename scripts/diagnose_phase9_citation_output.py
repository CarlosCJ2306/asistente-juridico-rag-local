"""Diagnóstico manual único y sanitizado de la salida citada de Fase 9.

No valida la fase completa, no reintenta recuperación o generación y no conserva
la pregunta, la respuesta, markers, citas ni metadata documental.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
REPORTS = ROOT / "local_validation_reports"
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(BACKEND))

from validate_phase8_end_to_end import (  # noqa: E402
    free_port,
    port_is_free,
    request_json,
    start_backend,
    stop_backend,
)
from validate_phase9_end_to_end import (  # noqa: E402
    CITATION_REASON_CODES,
    SAFE_APPLICATION_STAGES,
    UNKNOWN_SAFE_REASON,
    atomic_write,
    extract_safe_error,
)


OFFLINE_ENV = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "ANONYMIZED_TELEMETRY": "False",
}


@dataclass
class DiagnosticReport:
    rows: list[tuple[str, str, str, float]] = field(default_factory=list)

    def add(self, name: str, result: str, detail: str, duration: float = 0.0) -> None:
        self.rows.append((name, result, detail, duration))

    def render(
        self,
        *,
        exit_code: int,
        completed: bool,
        functional_result: str,
    ) -> str:
        lines = [
            "# Diagnóstico estructural de citas de Fase 9",
            "",
            f"Fecha: {datetime.now().astimezone().isoformat(timespec='seconds')}",
            "",
            "| Etapa | Resultado | Detalle seguro | Duración |",
            "|---|---|---|---:|",
        ]
        lines.extend(
            f"| {name} | {result} | {detail} | {duration:.2f}s |"
            for name, result, detail, duration in self.rows
        )
        lines.extend(
            [
                "",
                f"DIAGNÓSTICO COMPLETADO: {'SÍ' if completed else 'NO'}",
                f"RESULTADO FUNCIONAL {functional_result}",
                f"Código de salida: {exit_code}",
                "",
            ]
        )
        return "\n".join(lines)


@dataclass(frozen=True)
class DiagnosticOutcome:
    completed: bool
    functional_result: str
    http_status: int | None = None
    error_code: str | None = None
    reason_code: str | None = None
    stage: str | None = None
    retrieved_chunks: int | None = None
    context_chunks: int | None = None
    citation_count: int | None = None
    finish_reason: str | None = None
    generated_token_count: int | None = None
    citation_source_count: int | None = None


@dataclass(frozen=True)
class SafeOperationalMetrics:
    finish_reason: str | None = None
    generated_token_count: int | None = None
    citation_source_count: int | None = None


def generation_log_offset() -> int:
    log_file = ROOT / "storage" / "logs" / "asistente_juridico_backend.log"
    return log_file.stat().st_size if log_file.is_file() else 0


def read_safe_operational_metrics(offset: int) -> SafeOperationalMetrics:
    """Lee solo campos agregados añadidos al log después de la solicitud."""

    log_file = ROOT / "storage" / "logs" / "asistente_juridico_backend.log"
    if not log_file.is_file():
        return SafeOperationalMetrics()
    finish_reason: str | None = None
    generated_token_count: int | None = None
    citation_source_count: int | None = None
    try:
        with log_file.open("rb") as handle:
            handle.seek(max(0, offset))
            appended = handle.read().decode("utf-8", errors="replace")
        for line in appended.splitlines():
            if "| context=" not in line:
                continue
            context = json.loads(line.rsplit("| context=", 1)[1])
            if not isinstance(context, dict):
                continue
            if "Generación local completada" in line:
                candidate_reason = context.get("finish_reason")
                if candidate_reason in {"stop", "length", "unknown"}:
                    finish_reason = candidate_reason
                candidate_count = context.get("generated_count")
                if (
                    isinstance(candidate_count, int)
                    and not isinstance(candidate_count, bool)
                    and candidate_count >= 0
                ):
                    generated_token_count = candidate_count
            if context.get("operation") == "rag_chat_citations":
                candidate_sources = context.get("total_sources")
                if (
                    isinstance(candidate_sources, int)
                    and not isinstance(candidate_sources, bool)
                    and candidate_sources >= 0
                ):
                    citation_source_count = candidate_sources
    except (OSError, ValueError, json.JSONDecodeError):
        return SafeOperationalMetrics()
    return SafeOperationalMetrics(
        finish_reason,
        generated_token_count,
        citation_source_count,
    )


def fts5_index_available() -> bool:
    """Comprueba el índice sin ejecutar búsquedas ni leer contenido."""

    database = ROOT / "storage" / "database" / "asistente_juridico.db"
    if not database.is_file():
        return False
    try:
        with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as connection:
            row = connection.execute(
                "SELECT count(*) FROM sqlite_master "
                "WHERE type = 'table' AND name = 'document_chunks_fts'"
            ).fetchone()
        return row is not None and row[0] == 1
    except sqlite3.Error:
        return False


def evaluate_chat_result(
    http_status: int,
    payload: object,
    metrics: SafeOperationalMetrics | None = None,
) -> DiagnosticOutcome:
    """Clasifica únicamente estructura segura; descarta el resto del body."""

    safe_metrics = metrics or SafeOperationalMetrics()
    if http_status == 200 and isinstance(payload, dict):
        status = payload.get("status")
        if status == "answered":
            counts = (
                payload.get("retrieved_chunks"),
                payload.get("context_chunks"),
                payload.get("citation_count"),
            )
            if all(
                isinstance(value, int) and not isinstance(value, bool) and value >= 0
                for value in counts
            ):
                return DiagnosticOutcome(
                    True,
                    "ANSWERED",
                    http_status=200,
                    retrieved_chunks=counts[0],
                    context_chunks=counts[1],
                    citation_count=counts[2],
                    finish_reason=safe_metrics.finish_reason,
                    generated_token_count=safe_metrics.generated_token_count,
                    citation_source_count=safe_metrics.citation_source_count,
                )
        return DiagnosticOutcome(False, "INDETERMINADO", http_status=200)
    error_code, reason_code, stage = extract_safe_error(payload)
    if (
        error_code == "RAG_CITATION_OUTPUT_INVALID"
        and reason_code in CITATION_REASON_CODES
        and stage in SAFE_APPLICATION_STAGES
    ):
        return DiagnosticOutcome(
            True,
            "RECHAZADO",
            http_status=http_status,
            error_code=error_code,
            reason_code=reason_code,
            stage=stage,
            finish_reason=safe_metrics.finish_reason,
            generated_token_count=safe_metrics.generated_token_count,
            citation_source_count=safe_metrics.citation_source_count,
        )
    return DiagnosticOutcome(
        False,
        "INDETERMINADO",
        http_status=http_status,
        error_code=error_code,
        reason_code=reason_code or UNKNOWN_SAFE_REASON,
        stage=stage,
        finish_reason=safe_metrics.finish_reason,
        generated_token_count=safe_metrics.generated_token_count,
        citation_source_count=safe_metrics.citation_source_count,
    )


def execute_diagnostic(
    report: DiagnosticReport,
    port: int,
    *,
    requester: Callable[..., tuple[int, object]] = request_json,
    fts_checker: Callable[[], bool] = fts5_index_available,
    offset_getter: Callable[[], int] = generation_log_offset,
    metrics_reader: Callable[[int], SafeOperationalMetrics] = read_safe_operational_metrics,
) -> DiagnosticOutcome:
    """Ejecuta un solo ciclo y una sola solicitud Chat RAG."""

    embedding_code, embedding = requester(
        port, "GET", "/api/models/embeddings/status", None, timeout=30
    )
    llm_code, llm = requester(port, "GET", "/api/models/llm/status", None, timeout=30)
    initially_unloaded = (
        embedding_code == 200
        and llm_code == 200
        and isinstance(embedding, dict)
        and isinstance(llm, dict)
        and embedding.get("state") == "unloaded"
        and llm.get("state") == "unloaded"
    )
    report.add(
        "Estado inicial",
        "PASS" if initially_unloaded else "FAIL",
        "Modelos unloaded" if initially_unloaded else "Estado no compatible",
    )
    if not initially_unloaded:
        return DiagnosticOutcome(False, "INDETERMINADO")

    semantic_code, semantic = requester(
        port, "GET", "/api/search/semantic/status", None, timeout=30
    )
    indexes_ready = (
        fts_checker()
        and semantic_code == 200
        and isinstance(semantic, dict)
        and semantic.get("state") == "ready"
        and semantic.get("needs_rebuild") is False
    )
    report.add(
        "Índices",
        "PASS" if indexes_ready else "FAIL",
        "FTS5 y ChromaDB disponibles" if indexes_ready else "Índices no disponibles",
    )
    if not indexes_ready:
        return DiagnosticOutcome(False, "INDETERMINADO")

    embedding_load, embedding = requester(
        port, "POST", "/api/models/embeddings/load", None, timeout=180
    )
    llm_load, llm = requester(port, "POST", "/api/models/llm/load", None, timeout=180)
    loaded = (
        embedding_load == 200
        and llm_load == 200
        and isinstance(embedding, dict)
        and isinstance(llm, dict)
        and embedding.get("state") == "loaded"
        and llm.get("state") == "loaded"
    )
    report.add(
        "Modelos",
        "PASS" if loaded else "FAIL",
        "Carga local completada" if loaded else "Carga no disponible",
    )
    if not loaded:
        return DiagnosticOutcome(False, "INDETERMINADO")

    started = time.perf_counter()
    log_offset = offset_getter()
    http_status, response = requester(
        port,
        "POST",
        "/api/chat/rag",
        {"question": "pregunta sintetica general", "top_k": 3},
        timeout=180,
    )
    outcome = evaluate_chat_result(http_status, response, metrics_reader(log_offset))
    detail = f"HTTP {http_status}"
    if outcome.error_code is not None:
        detail += f"; {outcome.error_code}"
    if outcome.reason_code is not None:
        detail += f"; reason {outcome.reason_code}"
    if outcome.stage is not None:
        detail += f"; stage {outcome.stage}"
    if outcome.retrieved_chunks is not None:
        detail += f"; recuperados {outcome.retrieved_chunks}"
    if outcome.context_chunks is not None:
        detail += f"; contexto {outcome.context_chunks}"
    if outcome.citation_count is not None:
        detail += f"; citas {outcome.citation_count}"
    if outcome.citation_source_count is not None:
        detail += f"; fuentes {outcome.citation_source_count}"
    detail += f"; finish_reason {outcome.finish_reason or 'unavailable'}"
    detail += (
        f"; generated_token_count {outcome.generated_token_count}"
        if outcome.generated_token_count is not None
        else "; generated_token_count unavailable"
    )
    report.add(
        "Chat RAG único",
        "PASS" if outcome.completed else "FAIL",
        detail,
        time.perf_counter() - started,
    )
    del response
    return outcome


def cleanup_runtime(
    report: DiagnosticReport,
    process: object,
    port: int | None,
    *,
    requester: Callable[..., tuple[int, object]] = request_json,
    stopper: Callable[[object, int | None], bool] = stop_backend,
    port_checker: Callable[[int], bool] = port_is_free,
) -> bool:
    """Descarga ambos modelos y cierra el único backend incluso ante excepción."""

    models_ok = port is not None
    if port is not None:
        for endpoint in ("/api/models/llm/unload", "/api/models/embeddings/unload"):
            try:
                status, state = requester(port, "POST", endpoint, None, timeout=30)
                models_ok = (
                    models_ok
                    and status == 200
                    and isinstance(state, dict)
                    and state.get("state") == "unloaded"
                )
            except Exception:
                models_ok = False
    report.add(
        "Estado final de modelos",
        "PASS" if models_ok else "FAIL",
        "Modelos unloaded" if models_ok else "Limpieza de modelos incompleta",
    )
    stopped = stopper(process, port)
    ports_ok = stopped and (port is None or port_checker(port))
    report.add(
        "Puerto",
        "PASS" if ports_ok else "FAIL",
        "Liberado" if ports_ok else "No liberado",
    )
    return models_ok and ports_ok


def main() -> int:
    os.environ.update(OFFLINE_ENV)
    report = DiagnosticReport()
    process: object = None
    port: int | None = None
    outcome = DiagnosticOutcome(False, "INDETERMINADO")
    cleanup_ok = False
    try:
        port = free_port()
        process = start_backend(port)
        outcome = execute_diagnostic(report, port)
    except Exception as exc:
        report.add("Diagnóstico", "FAIL", type(exc).__name__)
    finally:
        cleanup_ok = cleanup_runtime(report, process, port)

    exit_code = 0 if outcome.completed and cleanup_ok else 1
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    content = report.render(
        exit_code=exit_code,
        completed=outcome.completed and cleanup_ok,
        functional_result=outcome.functional_result,
    )
    atomic_write(REPORTS / f"phase9_diagnostic_{timestamp}.md", content)
    print(
        "DIAGNÓSTICO FASE 9: " + ("COMPLETADO" if exit_code == 0 else "FALLIDO"),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
