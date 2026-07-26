"""Diagnóstico limitado del arranque y CRUD mínimo de Fase 10.

Opera exclusivamente sobre una copia SQLite temporal. No carga modelos, no
ejecuta el validador integral y no conserva cuerpos HTTP ni logs del backend.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from validate_phase10_end_to_end import (
    BACKEND,
    BackendHandle,
    DATABASE_DIR,
    OFFLINE_ENV,
    ORIGINAL_DB,
    REPORTS,
    StageFailure,
    atomic_write,
    backup_database,
    confirm_backend_process_active,
    database_counts,
    engine_disposition,
    free_port,
    launch_backend,
    listener_state,
    models_unloaded,
    probe_temporary_copy_release,
    remove_temporary_copy,
    report_is_private,
    request,
    required_uuid_text,
    stop_backend,
    validate_http,
    wait_for_backend_health,
    wait_for_backend_listener,
    wait_for_listener_release,
)

DIAGNOSTIC_RUNTIME_STAGES = (
    "Backend iniciado",
    "Proceso backend activo",
    "Listener backend detectado",
    "Propiedad del listener",
    "Health readiness",
    "Independencia de IA",
    "Matriz creada",
    "Matriz consultada",
)


@dataclass
class DiagnosticReport:
    rows: list[tuple[str, str, str, float]] = field(default_factory=list)

    def add(
        self,
        name: str,
        result: str,
        detail: str,
        duration: float = 0.0,
    ) -> None:
        self.rows.append((name, result, detail, duration))

    def has(self, name: str) -> bool:
        return any(row_name == name for row_name, _, _, _ in self.rows)

    def block_after_failure(self, failed_stage: str) -> None:
        try:
            failed_index = DIAGNOSTIC_RUNTIME_STAGES.index(failed_stage)
        except ValueError:
            failed_index = -1
        for stage in DIAGNOSTIC_RUNTIME_STAGES[failed_index + 1 :]:
            if not self.has(stage):
                self.add(stage, "BLOCKED", "Etapa anterior fallida")

    @property
    def passed(self) -> bool:
        return all(result == "PASS" for _, result, _, _ in self.rows)

    def render(self, exit_code: int) -> str:
        lines = [
            "# Diagnóstico de ejecución de Fase 10",
            "",
            f"Fecha: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "| Etapa | Resultado | Detalle seguro | Duración (s) |",
            "|---|---|---|---:|",
        ]
        lines.extend(
            f"| {name} | {result} | {detail} | {duration:.2f} |"
            for name, result, detail, duration in self.rows
        )
        outcome = "COMPLETADO" if exit_code == 0 else "FALLIDO"
        lines.extend(
            [
                "",
                f"DIAGNÓSTICO EJECUCIÓN FASE 10: {outcome}",
                f"Código de salida: {exit_code}",
                "",
            ]
        )
        return "\n".join(lines)


def _alembic_head(copy_path: Path, environment: dict[str, str]) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise StageFailure(
            "Migración aislada",
            "COPY_MIGRATION_FAILED",
            exception_class="SubprocessFailure",
        )
    with closing(sqlite3.connect(copy_path)) as connection:
        with closing(connection.execute("SELECT version_num FROM alembic_version")) as cursor:
            revision = cursor.fetchone()
    if revision is None or revision[0] != "20260725_04":
        raise StageFailure(
            "Alembic head",
            "ALEMBIC_HEAD_INVALID",
            exception_class="DatabaseValidationFailure",
        )


def _create_and_read_matrix(port: int, report: DiagnosticReport) -> None:
    started = time.perf_counter()
    created = validate_http(
        "Matriz creada",
        request(
            port,
            "POST",
            "/api/hpn/matrices",
            {"title": "Matriz sintética de diagnóstico"},
        ),
        201,
    )
    matrix_id = required_uuid_text(created, "id", "Matriz creada")
    report.add(
        "Matriz creada",
        "PASS",
        "HTTP 201; estructura válida",
        time.perf_counter() - started,
    )
    started = time.perf_counter()
    validate_http(
        "Matriz consultada",
        request(port, "GET", f"/api/hpn/matrices/{matrix_id}"),
        200,
    )
    report.add(
        "Matriz consultada",
        "PASS",
        "HTTP 200; estructura disponible",
        time.perf_counter() - started,
    )


def main() -> int:
    report = DiagnosticReport()
    copy_path = DATABASE_DIR / f".phase10_{uuid4().hex}.db"
    backend_handle: BackendHandle | None = None
    process_created = False
    port: int | None = None
    original_before: tuple[int, int, int, int] | None = None
    functional_ok = False
    cleanup_ok = False
    models_verified_unloaded = False
    try:
        if not ORIGINAL_DB.is_file():
            raise StageFailure(
                "Precondición SQLite",
                "ORIGINAL_DATABASE_NOT_FOUND",
                exception_class="PreconditionFailure",
            )
        original_before = database_counts(ORIGINAL_DB)
        backup_database(ORIGINAL_DB, copy_path)
        report.add("Copia temporal", "PASS", "Backup SQLite coherente")
        environment = {
            **os.environ,
            **OFFLINE_ENV,
            "DATABASE_FILE": f"storage/database/{copy_path.name}",
        }
        report.add(
            "Base aislada configurada",
            "PASS",
            "Alembic y backend usan la misma copia",
        )
        _alembic_head(copy_path, environment)
        report.add("Migración aislada", "PASS", "Código 0")
        report.add("Alembic head", "PASS", "Revisión esperada")
        if database_counts(copy_path) != original_before:
            raise StageFailure(
                "Integridad de copia",
                "COPY_DOCUMENT_INTEGRITY_FAILED",
                exception_class="DatabaseValidationFailure",
            )
        report.add("Integridad de copia", "PASS", "Conteos conservados")
        port = free_port()
        if listener_state(port, set()) != "free":
            raise StageFailure(
                "Puerto dinámico",
                "BACKEND_PORT_CONFLICT",
                exception_class="ListenerOwnershipFailure",
            )
        report.add("Puerto dinámico", "PASS", "Puerto local libre")
        backend_handle = launch_backend(
            port,
            environment,
            report,  # type: ignore[arg-type]
            stage="Backend iniciado",
        )
        process_created = True
        confirm_backend_process_active(
            backend_handle,
            report,  # type: ignore[arg-type]
            stage="Proceso backend activo",
        )
        wait_for_backend_listener(
            backend_handle,
            report,  # type: ignore[arg-type]
            detected_stage="Listener backend detectado",
            ownership_stage="Propiedad del listener",
        )
        wait_for_backend_health(
            backend_handle,
            report,  # type: ignore[arg-type]
            stage="Health readiness",
        )
        if not models_unloaded(port):
            raise StageFailure(
                "Independencia de IA",
                "MODEL_STATE_INVALID",
                exception_class="ResponseContractFailure",
            )
        report.add("Independencia de IA", "PASS", "Modelos unloaded")
        models_verified_unloaded = True
        _create_and_read_matrix(port, report)
        functional_ok = True
    except StageFailure as exc:
        report.add(exc.stage, "FAIL", exc.safe_detail())
        report.block_after_failure(exc.stage)
    except Exception as exc:
        report.add(
            "Fallo interno del diagnóstico",
            "FAIL",
            f"UNKNOWN_SAFE_ERROR; {type(exc).__name__}",
        )
    finally:
        final_models_ok = models_verified_unloaded
        final_models_checked = models_verified_unloaded
        if (
            backend_handle is not None
            and backend_handle.state == "ready"
            and backend_handle.process.poll() is None
        ):
            final_models_ok = models_unloaded(backend_handle.port)
            final_models_checked = True
        report.add(
            "Estado final de modelos",
            "PASS"
            if final_models_checked and final_models_ok
            else ("FAIL" if final_models_checked else "BLOCKED"),
            "Modelos unloaded"
            if final_models_checked and final_models_ok
            else ("Estado inválido" if final_models_checked else "Backend no ready"),
        )
        stop_result = stop_backend(
            backend_handle,
            process_was_created=process_created,
        )
        process_result = (
            "PASS"
            if stop_result.complete
            else ("BLOCKED" if not process_created else "FAIL")
        )
        report.add(
            "Procesos terminados",
            process_result,
            "Proceso, árbol y handles cerrados"
            if stop_result.complete
            else ("No se creó subprocess" if not process_created else "Cierre incompleto"),
        )
        engines_ok, engines_code = engine_disposition([stop_result])
        report.add(
            "Disposición de engines",
            "PASS" if engines_ok else "FAIL",
            engines_code,
        )
        if port is None:
            port_state = "free"
        elif backend_handle is not None:
            port_state = wait_for_listener_release(
                port,
                backend_handle.owned_pids,
            )
        else:
            port_state = listener_state(port, set())
        port_released = port_state == "free"
        port_detail = {
            "free": "Sin listener",
            "own": "Listener propio activo",
            "foreign": "Listener ajeno presente",
            "unknown": "Propietario no determinado",
        }.get(port_state, "Estado de listener inválido")
        report.add(
            "Puerto liberado",
            "PASS" if port_released else "FAIL",
            port_detail,
        )
        release = probe_temporary_copy_release(copy_path)
        removal = remove_temporary_copy(copy_path) if release.released else None
        copy_removed = removal is not None and removal.removed
        report.add(
            "Copia eliminada",
            "PASS" if copy_removed else "FAIL",
            "Copia y sidecars eliminados" if copy_removed else "Limpieza incompleta",
        )
        original_after = None
        if ORIGINAL_DB.is_file():
            try:
                original_after = database_counts(ORIGINAL_DB)
            except (OSError, sqlite3.Error):
                original_after = None
        integrity_ok = original_before is not None and original_before == original_after
        report.add(
            "Integridad original",
            "PASS" if integrity_ok else "FAIL",
            "Conteos iniciales y finales iguales" if integrity_ok else "Integridad no confirmada",
        )
        cleanup_ok = (
            (final_models_ok or not final_models_checked)
            and (stop_result.complete or not process_created)
            and engines_ok
            and port_released
            and copy_removed
            and integrity_ok
        )
        report.add(
            "Finalización y limpieza",
            "PASS" if cleanup_ok else "FAIL",
            "Proceso, puerto y copia liberados" if cleanup_ok else "Limpieza incompleta",
        )
    preliminary = 0 if functional_ok and cleanup_ok and report.passed else 1
    rendered = report.render(preliminary)
    private = report_is_private(rendered)
    if not private:
        report.add("Privacidad", "FAIL", "REPORT_PRIVACY_VALIDATION_FAILED")
    exit_code = 0 if preliminary == 0 and private else 1
    rendered = report.render(exit_code)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    atomic_write(REPORTS / f"phase10_execution_{timestamp}.md", rendered)
    print(
        "DIAGNÓSTICO EJECUCIÓN FASE 10: "
        + ("COMPLETADO" if exit_code == 0 else "FALLIDO")
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
