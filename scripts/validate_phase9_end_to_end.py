"""Validador manual integral y sanitizado de la Fase 9.

Se prepara para una ejecución futura explícita. No descarga, migra, reconstruye
índices ni almacena preguntas, respuestas o referencias concretas.
"""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from collections.abc import Callable
from typing import Any
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
REPORTS = ROOT / "local_validation_reports"
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(BACKEND))

from validate_phase8_end_to_end import (  # noqa: E402
    counts_equal,
    final_models_unloaded,
    free_port,
    has_pending_threads,
    port_is_free,
    request_json,
    sqlite_counts,
    start_backend,
    stop_backend,
    unload_models,
)

from app.services.rag_citation_service import (  # noqa: E402
    CITATION_LIKE_PATTERN,
    CITATION_REASON_CODES,
    MARKER_PATTERN,
    RagCitationService,
)
from app.core.config import settings  # noqa: E402


OFFLINE_ENV = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "ANONYMIZED_TELEMETRY": "False",
}
PUBLIC_RESPONSE_KEYS = {
    "status",
    "answer",
    "retrieved_chunks",
    "context_chunks",
    "context_tokens",
    "requires_professional_review",
    "citation_count",
    "citations",
}
PUBLIC_CITATION_KEYS = {
    "marker",
    "document_id",
    "document_name",
    "document_type",
    "chunk_index",
    "start_page",
    "end_page",
}
FORBIDDEN_RESPONSE_KEYS = {
    "chunk_id",
    "stored_filename",
    "relative_path",
    "sha256",
    "text",
    "snippet",
    "prompt",
    "context",
    "hybrid_score",
    "rank_bm25",
    "distance_cosine",
    "embedding",
    "vector",
    "collection",
    "sql",
}
ANSWERED_STAGE_ROWS = (
    "Recuperación híbrida",
    "Chat RAG HTTP",
    "Estado answered",
    "Contrato público",
    "Presupuesto con markers",
    "Correspondencia markers-citations",
    "Metadata SQLite",
    "Cobertura",
    "Privacidad",
    "Insufficient context",
)
REQUIRED_ROWS = {
    "Pytest",
    "Ruff",
    "mypy",
    "Estado inicial",
    "FTS5",
    "ChromaDB",
    "Modelos",
    *ANSWERED_STAGE_ROWS,
    "Persistencia tras reinicio",
    "Integridad SQLite",
    "Descarga final de modelos",
    "Puertos",
    "Finalización y limpieza",
}

STABLE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,79}$")
SAFE_APPLICATION_STAGES = frozenset(
    {"citation_validation", "citation_metadata", "citation_revalidation"}
)
UNKNOWN_SAFE_REASON = "UNKNOWN_SAFE_REASON"


@dataclass(frozen=True)
class StageFailure(RuntimeError):
    """Fallo operacional sanitizado y asociado a una etapa exacta."""

    stage: str
    exception_class: str
    http_status: int | None = None
    error_code: str | None = None
    reason_code: str | None = None
    application_stage: str | None = None
    duration: float = 0.0

    def safe_detail(self) -> str:
        parts: list[str] = []
        if self.http_status is not None:
            parts.append(f"HTTP {self.http_status}")
        if self.error_code is not None:
            parts.append(self.error_code)
        if self.reason_code is not None:
            parts.append(f"reason {self.reason_code}")
        if self.application_stage is not None:
            parts.append(f"stage {self.application_stage}")
        parts.append(self.exception_class)
        return "; ".join(parts)


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
            "# Validación integral de Fase 9",
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
        lines.extend(
            ["", f"VALIDACIÓN FASE 9: {status}", f"Código de salida: {exit_code}", ""]
        )
        return "\n".join(lines)


def extract_safe_error(payload: object) -> tuple[str | None, str | None, str | None]:
    """Extrae códigos y etapa permitidos, nunca mensajes libres ni bodies."""

    if not isinstance(payload, dict):
        return None, None, None
    containers = [payload]
    detail = payload.get("detail")
    if isinstance(detail, dict):
        containers.append(detail)
    error_code: str | None = None
    reason_code: str | None = None
    application_stage: str | None = None
    for container in containers:
        candidates = (
            container.get("code"),
            container.get("error_code"),
            container.get("detail"),
        )
        if error_code is None:
            error_code = next(
                (
                    candidate
                    for candidate in candidates
                    if isinstance(candidate, str)
                    and STABLE_ERROR_CODE.fullmatch(candidate)
                ),
                None,
            )
        candidate_reason = container.get("reason_code")
        if candidate_reason in CITATION_REASON_CODES:
            reason_code = candidate_reason
        candidate_stage = container.get("stage")
        if candidate_stage in SAFE_APPLICATION_STAGES:
            application_stage = candidate_stage
    return error_code, reason_code, application_stage


def extract_stable_error_code(payload: object) -> str | None:
    """Compatibilidad para auditorías sintéticas previas."""

    return extract_safe_error(payload)[0]


def request_stage(
    requester: Callable[..., tuple[int, object]],
    port: int,
    method: str,
    endpoint: str,
    payload: dict[str, Any] | None,
    *,
    stage: str,
    timeout: float = 120,
) -> dict[str, Any]:
    """Ejecuta HTTP y conserva únicamente diagnóstico estructurado seguro."""

    started = time.perf_counter()
    try:
        status, response = requester(
            port,
            method,
            endpoint,
            payload,
            timeout=timeout,
        )
    except Exception as exc:
        raise StageFailure(
            stage=stage,
            exception_class=type(exc).__name__,
            reason_code=UNKNOWN_SAFE_REASON if stage == "Chat RAG HTTP" else None,
            duration=time.perf_counter() - started,
        ) from exc
    duration = time.perf_counter() - started
    if status != 200:
        error_code, reason_code, application_stage = extract_safe_error(response)
        if stage == "Chat RAG HTTP" and reason_code is None:
            reason_code = UNKNOWN_SAFE_REASON
        raise StageFailure(
            stage=stage,
            exception_class="HTTPError",
            http_status=status,
            error_code=error_code,
            reason_code=reason_code,
            application_stage=application_stage,
            duration=duration,
        )
    if not isinstance(response, dict):
        raise StageFailure(
            stage=stage,
            exception_class="ResponseValidationError",
            http_status=status,
            duration=duration,
        )
    return response


def require_stage(
    report: Report,
    stage: str,
    check: Callable[[], bool],
    *,
    pass_detail: str,
    error_code: str,
) -> None:
    """Registra una comprobación sin incorporar valores inspeccionados."""

    started = time.perf_counter()
    try:
        valid = check()
    except StageFailure:
        raise
    except Exception as exc:
        raise StageFailure(
            stage=stage,
            exception_class=type(exc).__name__,
            error_code=error_code,
            duration=time.perf_counter() - started,
        ) from exc
    duration = time.perf_counter() - started
    if not valid:
        raise StageFailure(
            stage=stage,
            exception_class="ResponseValidationError",
            error_code=error_code,
            duration=duration,
        )
    report.add(stage, "PASS", pass_detail, duration)


def record_stage_failure(report: Report, failure: StageFailure) -> None:
    """Hace visible la etapa causante y bloquea las posteriores no ejecutadas."""

    report.add(
        failure.stage,
        "FAIL",
        failure.safe_detail(),
        failure.duration,
    )
    failed_index = (
        ANSWERED_STAGE_ROWS.index(failure.stage)
        if failure.stage in ANSWERED_STAGE_ROWS
        else -1
    )
    for index, stage in enumerate(ANSWERED_STAGE_ROWS):
        if index > failed_index and not any(row[0] == stage for row in report.rows):
            report.add(stage, "BLOCKED", "Bloqueada por fallo previo")
    if not any(row[0] == "Persistencia tras reinicio" for row in report.rows):
        report.add(
            "Persistencia tras reinicio",
            "BLOCKED",
            "Bloqueada por fallo previo",
        )


def atomic_write(path: Path, content: str) -> None:
    """Escribe mediante temporal, flush, fsync y reemplazo atómico."""

    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".phase9_", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def run_static(report: Report) -> None:
    commands = (
        ("Pytest", [sys.executable, "-m", "pytest"]),
        ("Ruff", [sys.executable, "-m", "ruff", "check", "app", "tests"]),
        ("mypy", [sys.executable, "-m", "mypy", "app"]),
    )
    for name, command in commands:
        started = time.perf_counter()
        result = subprocess.run(
            command,
            cwd=BACKEND,
            env={**os.environ, **OFFLINE_ENV},
            capture_output=True,
            text=True,
            timeout=360,
        )
        report.add(
            name,
            "PASS" if result.returncode == 0 else "FAIL",
            "Código 0" if result.returncode == 0 else "Código distinto de cero",
            time.perf_counter() - started,
        )


def contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).casefold() in FORBIDDEN_RESPONSE_KEYS
            or contains_forbidden_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(contains_forbidden_key(item) for item in value)
    return False


def _substantive_elements(answer: str) -> list[str]:
    return RagCitationService._substantive_elements(answer)


def validate_public_contract(response: object) -> bool:
    if not isinstance(response, dict) or set(response) != PUBLIC_RESPONSE_KEYS:
        return False
    answer = response.get("answer")
    citations = response.get("citations")
    citation_count = response.get("citation_count")
    retrieved = response.get("retrieved_chunks")
    context_chunks = response.get("context_chunks")
    context_tokens = response.get("context_tokens")
    return (
        isinstance(answer, str)
        and bool(answer.strip())
        and isinstance(citations, list)
        and isinstance(citation_count, int)
        and not isinstance(citation_count, bool)
        and citation_count > 0
        and citation_count == len(citations)
        and isinstance(retrieved, int)
        and not isinstance(retrieved, bool)
        and retrieved >= 0
        and isinstance(context_chunks, int)
        and not isinstance(context_chunks, bool)
        and 0 < context_chunks <= retrieved
        and citation_count <= context_chunks
        and isinstance(context_tokens, int)
        and not isinstance(context_tokens, bool)
        and context_tokens >= 0
        and response.get("requires_professional_review") is True
        and all(
            isinstance(citation, dict) and set(citation) == PUBLIC_CITATION_KEYS
            for citation in citations
        )
    )


def validate_budget_values(
    *,
    context_size: int,
    prompt_tokens: int,
    context_tokens: int,
    max_new_tokens: int,
    safety_margin: int,
    context_chunks: int,
    source_count: int,
) -> bool:
    """Valida la fórmula exacta cuando existe diagnóstico tokenizado seguro."""

    values = (
        context_size,
        prompt_tokens,
        context_tokens,
        max_new_tokens,
        safety_margin,
        context_chunks,
        source_count,
    )
    return (
        all(isinstance(value, int) and not isinstance(value, bool) for value in values)
        and context_size > 0
        and prompt_tokens >= context_tokens >= 0
        and max_new_tokens > 0
        and safety_margin > 0
        and 0 < source_count <= context_chunks <= settings.rag_context_max_chunks
        and context_tokens <= settings.rag_context_max_tokens
        and prompt_tokens + max_new_tokens + safety_margin <= context_size
    )


def validate_budget_contract(response: dict[str, Any], llm_status: dict[str, Any]) -> bool:
    """Comprueba límites públicos sin esperar prompt_tokens en la respuesta."""

    context_size = llm_status.get("context_size")
    context_tokens = response.get("context_tokens")
    context_chunks = response.get("context_chunks")
    source_count = response.get("citation_count")
    reserved = settings.rag_max_new_tokens + settings.rag_token_safety_margin
    return (
        isinstance(context_size, int)
        and not isinstance(context_size, bool)
        and context_size > reserved
        and isinstance(context_tokens, int)
        and not isinstance(context_tokens, bool)
        and 0 <= context_tokens <= settings.rag_context_max_tokens
        and isinstance(context_chunks, int)
        and not isinstance(context_chunks, bool)
        and isinstance(source_count, int)
        and not isinstance(source_count, bool)
        and 0 < source_count <= context_chunks <= settings.rag_context_max_chunks
    )


def validate_marker_correspondence(response: dict[str, Any]) -> tuple[bool, int]:
    answer = response.get("answer")
    citations = response.get("citations")
    if not isinstance(answer, str) or not isinstance(citations, list):
        return False, 0
    markers = [
        citation.get("marker")
        for citation in citations
        if isinstance(citation, dict)
    ]
    if (
        len(markers) != len(citations)
        or len(set(markers)) != len(markers)
        or any(
            not isinstance(marker, str) or MARKER_PATTERN.fullmatch(marker) is None
            for marker in markers
        )
    ):
        return False, 0
    exact_matches = list(MARKER_PATTERN.finditer(answer))
    exact_spans = {match.span() for match in exact_matches}
    if any(
        match.span() not in exact_spans
        for match in CITATION_LIKE_PATTERN.finditer(answer)
    ):
        return False, 0
    answer_markers = [match.group(0) for match in exact_matches]
    return (
        bool(answer_markers)
        and list(dict.fromkeys(answer_markers)) == markers
        and set(answer_markers) == set(markers),
        len(answer_markers),
    )


def validate_coverage(response: dict[str, Any]) -> tuple[bool, int]:
    answer = response.get("answer")
    if not isinstance(answer, str):
        return False, 0
    elements = _substantive_elements(answer)
    covered = sum(bool(MARKER_PATTERN.search(element)) for element in elements)
    plain = RagCitationService._plain_text(MARKER_PATTERN.sub("", answer))
    return (
        bool(elements)
        and covered == len(elements)
        and any(character.isalnum() for character in plain),
        covered,
    )


def validate_response_privacy(response: dict[str, Any]) -> bool:
    answer = response.get("answer")
    return (
        isinstance(answer, str)
        and not contains_forbidden_key(response)
        and re.search(r"<\s*(?:script|iframe|object|embed|think)\b", answer, re.I)
        is None
    )


def validate_answered_response(response: Any) -> tuple[bool, int, int]:
    if not validate_public_contract(response):
        return False, 0, 0
    if response.get("status") != "answered" or not validate_response_privacy(response):
        return False, 0, 0
    correspondence, marker_uses = validate_marker_correspondence(response)
    coverage_valid, coverage = validate_coverage(response)
    if not correspondence or not coverage_valid:
        return False, 0, 0
    return True, marker_uses, coverage


def validate_insufficient_response(response: Any) -> bool:
    return (
        isinstance(response, dict)
        and set(response) == PUBLIC_RESPONSE_KEYS
        and response.get("status") == "insufficient_context"
        and response.get("citation_count") == 0
        and response.get("citations") == []
        and response.get("context_chunks") == 0
        and response.get("context_tokens") == 0
        and response.get("requires_professional_review") is True
        and not contains_forbidden_key(response)
    )


def validate_sqlite_metadata(citations: list[dict[str, Any]]) -> bool:
    database = ROOT / "storage" / "database" / "asistente_juridico.db"
    with sqlite3.connect(database) as connection:
        for citation in citations:
            try:
                document_id = UUID(str(citation["document_id"]))
            except (TypeError, ValueError):
                return False
            row = connection.execute(
                """
                SELECT d.original_filename, d.document_type, c.chunk_index,
                       c.start_page, c.end_page
                FROM document_chunks AS c
                JOIN documents AS d ON d.id = c.document_id
                WHERE d.id IN (?, ?) AND c.chunk_index = ? AND d.is_deleted = 0
                """,
                (
                    document_id.hex,
                    str(document_id),
                    citation["chunk_index"],
                ),
            ).fetchone()
            if row is None:
                return False
            expected = (
                RagCitationService.sanitize_document_name(row[0]),
                row[1],
                row[2],
                row[3],
                row[4],
            )
            actual = (
                citation["document_name"],
                citation["document_type"],
                citation["chunk_index"],
                citation["start_page"],
                citation["end_page"],
            )
            if actual != expected:
                return False
    return True


def validate_answered_stages(
    report: Report,
    port: int,
    llm_status: dict[str, Any],
    *,
    requester: Callable[..., tuple[int, object]] = request_json,
    metadata_validator: Callable[[list[dict[str, Any]]], bool] = validate_sqlite_metadata,
) -> None:
    """Ejecuta y registra por separado cada contrato obligatorio de Fase 9."""

    hybrid = request_stage(
        requester,
        port,
        "POST",
        "/api/search/hybrid",
        {"query": "termino sintetico general", "top_k": 3},
        stage="Recuperación híbrida",
    )
    require_stage(
        report,
        "Recuperación híbrida",
        lambda: isinstance(hybrid.get("items"), list),
        pass_detail="HTTP 200; respuesta estructurada",
        error_code="HYBRID_RESPONSE_INVALID",
    )

    response = request_stage(
        requester,
        port,
        "POST",
        "/api/chat/rag",
        {"question": "pregunta sintetica general", "top_k": 3},
        stage="Chat RAG HTTP",
        timeout=180,
    )
    report.add("Chat RAG HTTP", "PASS", "HTTP 200")
    require_stage(
        report,
        "Estado answered",
        lambda: response.get("status") == "answered",
        pass_detail="Estado answered",
        error_code="RAG_STATUS_INVALID",
    )
    require_stage(
        report,
        "Contrato público",
        lambda: validate_public_contract(response),
        pass_detail="Estructura aditiva válida",
        error_code="RAG_PUBLIC_CONTRACT_INVALID",
    )
    require_stage(
        report,
        "Presupuesto con markers",
        lambda: validate_budget_contract(response, llm_status),
        pass_detail="Límites públicos coherentes; fórmula aplicada internamente",
        error_code="RAG_TOKEN_BUDGET_INVALID",
    )

    require_stage(
        report,
        "Correspondencia markers-citations",
        lambda: validate_marker_correspondence(response)[0],
        pass_detail="Correspondencia exacta",
        error_code="RAG_CITATION_OUTPUT_INVALID",
    )
    citations = response.get("citations")
    require_stage(
        report,
        "Metadata SQLite",
        lambda: isinstance(citations, list) and metadata_validator(citations),
        pass_detail=f"Fuentes revalidadas: {len(citations) if isinstance(citations, list) else 0}",
        error_code="RAG_CITATION_METADATA_INVALID",
    )

    require_stage(
        report,
        "Cobertura",
        lambda: validate_coverage(response)[0],
        pass_detail="Elementos sustantivos cubiertos",
        error_code="RAG_CITATION_OUTPUT_INVALID",
    )
    require_stage(
        report,
        "Privacidad",
        lambda: validate_response_privacy(response),
        pass_detail="Contrato público sanitizado",
        error_code="RAG_PRIVACY_INVALID",
    )

    empty = request_stage(
        requester,
        port,
        "POST",
        "/api/chat/rag",
        {
            "question": "consulta sintetica general",
            "top_k": 1,
            "document_id": "00000000-0000-0000-0000-000000000001",
        },
        stage="Insufficient context",
        timeout=180,
    )
    require_stage(
        report,
        "Insufficient context",
        lambda: validate_insufficient_response(empty),
        pass_detail="HTTP 200; citas: 0",
        error_code="RAG_INSUFFICIENT_CONTEXT_INVALID",
    )


def validate_cycle(report: Report, port: int, *, after_restart: bool) -> None:
    embedding_code, embedding = request_json(
        port, "GET", "/api/models/embeddings/status"
    )
    llm_code, llm = request_json(port, "GET", "/api/models/llm/status")
    if (
        embedding_code != 200
        or llm_code != 200
        or embedding.get("state") != "unloaded"
        or llm.get("state") != "unloaded"
    ):
        raise StageFailure("Estado inicial", "RuntimeError", error_code="MODELS_NOT_INITIALLY_UNLOADED")
    report.add("Estado inicial", "PASS", "Modelos unloaded")

    semantic_code, semantic = request_json(
        port, "GET", "/api/search/semantic/status"
    )
    text_code, _ = request_json(
        port, "POST", "/api/search/text", {"query": "termino sintetico"}
    )
    if text_code != 200:
        raise StageFailure("FTS5", "RuntimeError", error_code="FTS5_NOT_READY")
    if (
        semantic_code != 200
        or semantic.get("state") != "ready"
        or semantic.get("needs_rebuild") is not False
    ):
        raise StageFailure("ChromaDB", "RuntimeError", error_code="SEMANTIC_INDEX_NOT_READY")
    report.add("FTS5", "PASS", "Índice disponible")
    report.add("ChromaDB", "PASS", "Índice ready; sin rebuild")

    embedding_load, embedding = request_json(
        port, "POST", "/api/models/embeddings/load"
    )
    llm_load, llm = request_json(port, "POST", "/api/models/llm/load")
    if (
        embedding_load != 200
        or llm_load != 200
        or embedding.get("state") != "loaded"
        or llm.get("state") != "loaded"
    ):
        raise StageFailure("Modelos", "RuntimeError", error_code="MODEL_LOAD_FAILED")
    report.add("Modelos", "PASS", "Carga local completada")
    validate_answered_stages(report, port, llm)

    llm_unload, llm_state = request_json(port, "POST", "/api/models/llm/unload")
    embedding_unload, embedding_state = request_json(
        port, "POST", "/api/models/embeddings/unload"
    )
    if (
        llm_unload != 200
        or embedding_unload != 200
        or llm_state.get("state") != "unloaded"
        or embedding_state.get("state") != "unloaded"
    ):
        raise StageFailure(
            "Descarga final de modelos",
            "RuntimeError",
            error_code="MODEL_UNLOAD_FAILED",
        )
    report.add("Descarga final de modelos", "PASS", "Modelos unloaded")
    if after_restart:
        report.add("Persistencia tras reinicio", "PASS", "Chat con citas sin rebuild")


def validate_report_privacy(content: str) -> bool:
    forbidden = (
        r"\[F\d+\]",
        r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}",
        r"(?:[A-Za-z]:\\|/Users/|/home/)",
        r"\b(?:question|answer|document_id|document_name|chunk_id|prompt|snippet|sql)\b",
    )
    return not any(re.search(pattern, content, re.IGNORECASE) for pattern in forbidden)


def main() -> int:
    report = Report()
    process = None
    active_port: int | None = None
    used_ports: list[int] = []
    initial_counts: tuple[int, int, int, int] | None = None
    exit_code = 1
    try:
        run_static(report)
        if any(
            result != "PASS"
            for name, result, _, _ in report.rows
            if name in {"Pytest", "Ruff", "mypy"}
        ):
            raise StageFailure(
                "Validaciones estáticas",
                "RuntimeError",
                error_code="STATIC_VALIDATION_FAILED",
            )
        initial_counts = sqlite_counts()
        first_port = free_port()
        used_ports.append(first_port)
        active_port = first_port
        process = start_backend(first_port)
        validate_cycle(report, first_port, after_restart=False)
        if not stop_backend(process, first_port):
            raise StageFailure(
                "Persistencia tras reinicio",
                "RuntimeError",
                error_code="FIRST_BACKEND_NOT_CLOSED",
            )
        process = None
        active_port = None

        second_port = free_port()
        while second_port in used_ports:
            second_port = free_port()
        used_ports.append(second_port)
        active_port = second_port
        process = start_backend(second_port)
        validate_cycle(report, second_port, after_restart=True)
        exit_code = 0
    except StageFailure as exc:
        record_stage_failure(report, exc)
    except Exception as exc:
        record_stage_failure(
            report,
            StageFailure("Preparación", type(exc).__name__),
        )
    finally:
        cleanup_started = time.perf_counter()
        models_ok = True
        if active_port is not None:
            models_ok = unload_models(active_port) and final_models_unloaded(active_port)
        report.add(
            "Descarga final de modelos",
            "PASS" if models_ok else "FAIL",
            "Modelos unloaded" if models_ok else "Estado final inválido",
        )
        ports_ok = stop_backend(process, active_port) and all(
            port_is_free(port) for port in used_ports
        )
        final_counts = None
        try:
            final_counts = sqlite_counts()
        except Exception as exc:
            report.add("Conteos SQLite", "FAIL", type(exc).__name__)
        integrity_ok = counts_equal(initial_counts, final_counts)
        report.add(
            "Integridad SQLite",
            "PASS" if integrity_ok else "FAIL",
            "Conteos iniciales y finales iguales" if integrity_ok else "Conteos distintos",
        )
        report.add("Puertos", "PASS" if ports_ok else "FAIL", "Liberados" if ports_ok else "Ocupados")
        cleanup_ok = models_ok and ports_ok and not has_pending_threads()
        report.add(
            "Finalización y limpieza",
            "PASS" if cleanup_ok else "FAIL",
            "Procesos y tareas propios cerrados" if cleanup_ok else "Limpieza incompleta",
            time.perf_counter() - cleanup_started,
        )
        rendered_probe = report.render(1)
        privacy_ok = validate_report_privacy(rendered_probe)
        if not privacy_ok:
            report.add("Privacidad", "FAIL", "Informe no sanitizado")
        exit_code = 0 if report.passed and cleanup_ok and integrity_ok and privacy_ok else 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rendered = report.render(exit_code)
    atomic_write(REPORTS / f"phase9_{timestamp}.md", rendered)
    atomic_write(REPORTS / "phase9_latest.md", rendered)
    print(
        f"VALIDACIÓN FASE 9: {'APROBADA' if exit_code == 0 else 'FALLIDA'}",
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
