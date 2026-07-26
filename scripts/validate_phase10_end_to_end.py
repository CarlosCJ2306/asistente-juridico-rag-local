"""Validador manual de Fase 10 sobre una copia SQLite aislada.

No carga modelos, no reconstruye índices y nunca escribe en la base original.
Debe ejecutarse explícitamente desde la raíz del proyecto.
"""

from __future__ import annotations

import json
import csv
import os
import re
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, IO
from uuid import UUID, uuid4


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
ORIGINAL_DB = ROOT / "storage" / "database" / "asistente_juridico.db"
REPORTS = ROOT / "local_validation_reports"
DATABASE_DIR = ROOT / "storage" / "database"
COPY_NAME_PATTERN = re.compile(
    r"\.phase10_[0-9a-f]{32}\.db(?:-(?:wal|shm|journal))?\Z"
)
SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")
OFFLINE_ENV = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "ANONYMIZED_TELEMETRY": "False",
    "LOG_TO_FILE": "false",
    "LOG_CONSOLE": "false",
}

EXECUTION_STAGES = (
    "Base aislada configurada",
    "Backend aislado iniciado",
    "Proceso backend activo",
    "Listener backend detectado",
    "Propiedad del listener",
    "Health readiness",
    "Independencia de IA",
    "Matriz creada",
    "Nodo fact creado",
    "Nodo evidence creado",
    "Nodo norm creado",
    "Fuentes vinculadas",
    "Validación incompleta",
    "Relaciones creadas",
    "Revisión completa",
    "CRUD matriz",
    "reviewed a in_review",
    "Fuente stale",
    "Persistencia preparada",
    "Cierre previo al reinicio",
    "Reinicio",
    "Proceso backend reiniciado",
    "Listener tras reinicio",
    "Propiedad tras reinicio",
    "Health tras reinicio",
    "Persistencia comprobada",
    "Borrado lógico",
    "Cascada lógica",
)
SAFE_ERROR_PATTERN = re.compile(r"[A-Z][A-Z0-9_]{2,63}\Z")


@dataclass
class Report:
    rows: list[tuple[str, str, str, float]] = field(default_factory=list)

    def add(self, name: str, result: str, detail: str, duration: float = 0.0) -> None:
        self.rows.append((name, result, detail, duration))

    def has(self, name: str) -> bool:
        return any(row_name == name for row_name, _, _, _ in self.rows)

    def block_missing_execution_stages(self) -> None:
        for stage in EXECUTION_STAGES:
            if not self.has(stage):
                self.add(stage, "BLOCKED", "Etapa anterior fallida")

    @property
    def passed(self) -> bool:
        return all(result in {"PASS", "WARN"} for _, result, _, _ in self.rows)

    def render(self, exit_code: int) -> str:
        lines = [
            "# Validación local de Fase 10",
            "",
            f"Fecha: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "| Validación | Resultado | Detalle seguro | Duración (s) |",
            "|---|---|---|---:|",
        ]
        lines.extend(
            f"| {name} | {result} | {detail} | {duration:.2f} |"
            for name, result, detail, duration in self.rows
        )
        result = "APROBADA" if exit_code == 0 else "FALLIDA"
        lines.extend(["", f"VALIDACIÓN FASE 10: {result}", f"Código de salida: {exit_code}", ""])
        return "\n".join(lines)


@dataclass(frozen=True)
class CleanupResult:
    removed: bool
    sidecars_removed: bool
    attempts: int
    failure_type: str | None = None


@dataclass(frozen=True)
class ReleaseProbeResult:
    released: bool
    failure_type: str | None = None


@dataclass(frozen=True)
class ProcessStopResult:
    stopped: bool
    graceful: bool
    handles_closed: bool
    waited: bool = False
    returncode_available: bool = False
    tree_stopped: bool = False
    process_present: bool = True
    shutdown_confirmation: str = "BACKEND_SHUTDOWN_SENTINEL_MISSING"
    stdout_drained: bool = False
    stderr_drained: bool = False
    sentinel_valid: bool = False
    sentinel_removed: bool = False
    sentinel_confirmation: str = "DATABASE_DISPOSE_SENTINEL_MISSING"

    @property
    def complete(self) -> bool:
        return (
            self.process_present
            and self.stopped
            and self.handles_closed
            and self.waited
            and self.returncode_available
            and self.tree_stopped
        )


@dataclass
class BackendHandle:
    process: subprocess.Popen[str]
    port: int
    main_pid: int
    command_category: str
    stdout_handle: IO[str]
    stderr_handle: IO[str]
    owned_pids: set[int]
    dispose_sentinel: Path = field(default_factory=Path)
    state: str = "launched"


@dataclass(frozen=True)
class ListenerObservation:
    code: str
    owner_pids: frozenset[int] = frozenset()


@dataclass(frozen=True)
class HttpResult:
    status: int
    data: dict[str, Any]
    error_code: str
    json_valid: bool

    def __iter__(self):
        yield self.status
        yield self.data

    def __getitem__(self, index: int):
        return (self.status, self.data)[index]


class StageFailure(Exception):
    def __init__(
        self,
        stage: str,
        error_code: str,
        *,
        http_status: int | None = None,
        exception_class: str = "ValidationFailure",
    ) -> None:
        super().__init__(error_code)
        self.stage = stage
        self.error_code = (
            error_code if SAFE_ERROR_PATTERN.fullmatch(error_code) else "UNKNOWN_SAFE_ERROR"
        )
        self.http_status = http_status
        self.exception_class = exception_class

    def safe_detail(self) -> str:
        parts = []
        if self.http_status is not None:
            parts.append(f"HTTP {self.http_status}")
        parts.extend((self.error_code, self.exception_class))
        return "; ".join(parts)


def _owned_copy_path(path: Path) -> bool:
    """Acepta solo copias HPN generadas directamente bajo storage/database."""

    try:
        if ".." in path.parts or path.is_symlink() or path.resolve().parent != DATABASE_DIR.resolve():
            return False
    except OSError:
        return False
    return COPY_NAME_PATTERN.fullmatch(path.name) is not None


def _remove_with_retry(path: Path, *, attempts: int) -> tuple[bool, int, str | None]:
    used = 0
    for number in range(1, attempts + 1):
        used = number
        try:
            if path.is_symlink():
                return False, used, "UnsafePath"
            if not path.exists():
                return True, used, None
            path.unlink()
            return True, used, None
        except PermissionError:
            if number < attempts:
                time.sleep(0.05 * number)
                continue
            return False, used, "PermissionError"
        except OSError as exc:
            return False, used, type(exc).__name__
    return False, used, "RemovalFailed"


def probe_temporary_copy_release(path: Path) -> ReleaseProbeResult:
    """Comprueba acceso exclusivo renombrando y restaurando dentro del directorio."""

    if not _owned_copy_path(path):
        return ReleaseProbeResult(False, "UnsafePath")
    if not path.exists():
        return ReleaseProbeResult(True)
    probe = path.with_suffix(".probe")
    if probe.exists() or probe.is_symlink():
        return ReleaseProbeResult(False, "ProbeExists")
    moved = False
    try:
        path.replace(probe)
        moved = True
        probe.replace(path)
        return ReleaseProbeResult(True)
    except PermissionError:
        failure = "PermissionError"
    except OSError as exc:
        failure = type(exc).__name__
    if moved and probe.exists() and not path.exists():
        try:
            probe.replace(path)
        except OSError:
            return ReleaseProbeResult(False, "RestoreFailed")
    return ReleaseProbeResult(False, failure)


def remove_temporary_copy(path: Path, *, attempts: int = 3) -> CleanupResult:
    """Elimina una copia propia y sus sidecars con reintentos limitados."""

    if attempts < 1 or not _owned_copy_path(path):
        return CleanupResult(False, False, 0, "UnsafePath")
    sidecars_ok = True
    total_attempts = 0
    failure: str | None = None
    for suffix in SIDECAR_SUFFIXES:
        removed, used, error = _remove_with_retry(path.with_name(path.name + suffix), attempts=attempts)
        total_attempts += used
        sidecars_ok = sidecars_ok and removed
        if error is not None and failure is None:
            failure = error
    database_ok, used, error = _remove_with_retry(path, attempts=attempts)
    total_attempts += used
    if error is not None and failure is None:
        failure = error
    return CleanupResult(database_ok and sidecars_ok, sidecars_ok, total_attempts, failure)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".phase10_", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def database_counts(path: Path) -> tuple[int, int, int, int]:
    uri = f"file:{path.as_posix()}?mode=ro"
    counts: list[int] = []
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        for table in ("documents", "document_pages", "document_chunks", "document_chunks_fts"):
            with closing(connection.execute(f"SELECT COUNT(*) FROM {table}")) as cursor:
                counts.append(int(cursor.fetchone()[0]))
    return tuple(counts)  # type: ignore[return-value]


def backup_database(source: Path, destination: Path) -> None:
    """Crea una copia coherente mediante la API de backup de SQLite."""

    uri = f"file:{source.as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as source_connection:
        with closing(sqlite3.connect(destination)) as destination_connection:
            source_connection.backup(destination_connection)


def run_static(report: Report) -> None:
    commands = (
        ("Pytest", [sys.executable, "-m", "pytest"]),
        ("Ruff", [sys.executable, "-m", "ruff", "check", "app", "tests"]),
        ("mypy", [sys.executable, "-m", "mypy", "app"]),
    )
    for name, command in commands:
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            cwd=BACKEND,
            env={**os.environ, **OFFLINE_ENV},
            capture_output=True,
            text=True,
            timeout=420,
        )
        report.add(name, "PASS" if completed.returncode == 0 else "FAIL", "Código 0" if completed.returncode == 0 else "Código distinto de cero", time.perf_counter() - started)
        if completed.returncode != 0:
            raise StageFailure(
                name,
                "STATIC_VALIDATION_FAILED",
                exception_class="SubprocessFailure",
            )


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _tcp_listener_present(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def listener_owner_query(port: int) -> tuple[bool, set[int] | None]:
    """Distingue ausencia de listener de propietario no determinable."""

    if not 1 <= port <= 65535:
        return False, None
    if os.name != "nt":
        present = _tcp_listener_present(port)
        return present, None if present else set()
    try:
        completed = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        present = _tcp_listener_present(port)
        return present, None if present else set()
    if completed.returncode != 0:
        present = _tcp_listener_present(port)
        return present, None if present else set()
    owners: set[int] = set()
    for line in completed.stdout.splitlines():
        parts = line.split()
        if (
            len(parts) < 5
            or parts[0].upper() != "TCP"
            or parts[3].upper() != "LISTENING"
        ):
            continue
        try:
            local_port = int(parts[1].rsplit(":", 1)[1])
            owner = int(parts[4])
        except (IndexError, ValueError):
            continue
        if local_port == port:
            owners.add(owner)
    return bool(owners), owners


def listening_pids(port: int) -> set[int]:
    """Compatibilidad: devuelve propietarios conocidos del listener."""

    _, owners = listener_owner_query(port)
    return set() if owners is None else owners


def process_parent_map() -> dict[int, int] | None:
    """Obtiene únicamente la relación PID-padre sin líneas de comando."""

    if os.name != "nt":
        return None
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-CimInstance Win32_Process | "
                "Select-Object ProcessId,ParentProcessId | ConvertTo-Csv -NoTypeInformation",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    parents: dict[int, int] = {}
    try:
        output = completed.stdout.lstrip("\ufeff")
        for row in csv.DictReader(output.splitlines()):
            process_id = int(row["ProcessId"])
            parent_id = int(row["ParentProcessId"])
            parents[process_id] = parent_id
    except (KeyError, TypeError, ValueError):
        return None
    return parents


def descendant_pids(root_pid: int, parents: dict[int, int]) -> set[int]:
    descendants = {root_pid}
    changed = True
    while changed:
        changed = False
        for process_id, parent_id in parents.items():
            if parent_id in descendants and process_id not in descendants:
                descendants.add(process_id)
                changed = True
    return descendants


def observe_backend_listener(handle: BackendHandle) -> ListenerObservation:
    present, owners = listener_owner_query(handle.port)
    if not present:
        return ListenerObservation("BACKEND_LISTENER_NOT_READY")
    if owners is None or not owners:
        return ListenerObservation("BACKEND_LISTENER_OWNER_UNKNOWN")
    if owners.issubset(handle.owned_pids):
        return ListenerObservation("BACKEND_LISTENER_OWNED", frozenset(owners))
    parents = process_parent_map()
    if parents is None:
        return ListenerObservation(
            "BACKEND_LISTENER_OWNER_UNKNOWN", frozenset(owners)
        )
    legitimate = descendant_pids(handle.main_pid, parents)
    if owners.issubset(legitimate):
        handle.owned_pids.update(legitimate)
        return ListenerObservation("BACKEND_LISTENER_OWNED", frozenset(owners))
    return ListenerObservation("BACKEND_LISTENER_FOREIGN", frozenset(owners))


def listener_state(port: int, owned_pids: set[int]) -> str:
    present, owners = listener_owner_query(port)
    if not present:
        return "free"
    if owners is None:
        return "unknown"
    if owners and owners.issubset(owned_pids):
        return "own"
    return "foreign"


def wait_for_listener_release(
    port: int, owned_pids: set[int], *, timeout: float = 5.0
) -> str:
    deadline = time.monotonic() + timeout
    state = listener_state(port, owned_pids)
    while state == "own" and time.monotonic() < deadline:
        time.sleep(0.05)
        state = listener_state(port, owned_pids)
    return state


def _safe_error_code(data: object, *, default: str) -> str:
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, str) and SAFE_ERROR_PATTERN.fullmatch(detail):
            return detail
        if isinstance(detail, dict):
            nested_code = detail.get("error_code")
            if isinstance(nested_code, str) and SAFE_ERROR_PATTERN.fullmatch(
                nested_code
            ):
                return nested_code
        code = data.get("error_code")
        if isinstance(code, str) and SAFE_ERROR_PATTERN.fullmatch(code):
            return code
    return default


def request(
    port: int, method: str, path: str, payload: dict[str, Any] | None = None
) -> HttpResult:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    call = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(call, timeout=30) as response:
            raw = response.read(65_536)
            if not raw:
                return HttpResult(response.status, {}, "NONE", True)
            try:
                decoded = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return HttpResult(response.status, {}, "INVALID_JSON_RESPONSE", False)
            if not isinstance(decoded, dict):
                return HttpResult(response.status, {}, "INVALID_JSON_RESPONSE", False)
            return HttpResult(
                response.status,
                decoded,
                _safe_error_code(decoded, default="NONE"),
                True,
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read(65_536)
        try:
            decoded = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return HttpResult(exc.code, {}, "UNKNOWN_SAFE_ERROR", False)
        data = decoded if isinstance(decoded, dict) else {}
        return HttpResult(
            exc.code,
            data,
            _safe_error_code(data, default="UNKNOWN_SAFE_ERROR"),
            isinstance(decoded, dict),
        )
    except (urllib.error.URLError, TimeoutError, OSError):
        return HttpResult(0, {}, "HTTP_CONNECTION_ERROR", False)


def validate_http(
    stage: str,
    result: HttpResult,
    expected_status: int,
) -> dict[str, Any]:
    if result.status != expected_status or not result.json_valid:
        raise StageFailure(
            stage,
            result.error_code,
            http_status=result.status,
            exception_class="HttpValidationFailure",
        )
    return result.data


def require_http(
    report: Report,
    stage: str,
    result: HttpResult,
    expected_status: int,
    *,
    started: float,
) -> dict[str, Any]:
    data = validate_http(stage, result, expected_status)
    report.add(stage, "PASS", f"HTTP {result.status}", time.perf_counter() - started)
    return data


def required_uuid_text(data: dict[str, Any], key: str, stage: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise StageFailure(
            stage,
            "HTTP_RESPONSE_STRUCTURE_INVALID",
            exception_class="MissingField",
        )
    try:
        UUID(value)
    except ValueError:
        raise StageFailure(
            stage,
            "HTTP_RESPONSE_STRUCTURE_INVALID",
            exception_class="InvalidUuidField",
        ) from None
    return value


def _backend_log_category(backend: BackendHandle) -> str:
    contents: list[str] = []
    for handle in (backend.stdout_handle, backend.stderr_handle):
        if handle.closed:
            continue
        try:
            handle.flush()
            handle.seek(0)
            contents.append(handle.read(32_768).lower())
        except (OSError, ValueError):
            continue
    if not contents:
        return "BACKEND_LOG_UNAVAILABLE"
    content = "\n".join(contents)
    categories = (
        ("address already in use", "BACKEND_PORT_CONFLICT"),
        ("error loading asgi app", "BACKEND_IMPORT_ERROR"),
        ("could not import module", "BACKEND_IMPORT_ERROR"),
        ("modulenotfounderror", "BACKEND_IMPORT_ERROR"),
        ("validation error for settings", "BACKEND_CONFIGURATION_ERROR"),
        ("database_file debe", "BACKEND_DATABASE_CONFIGURATION_ERROR"),
        ("application startup failed", "BACKEND_STARTUP_ERROR"),
        ("unable to open database", "BACKEND_DATABASE_ERROR"),
        ("no such table", "BACKEND_DATABASE_SCHEMA_ERROR"),
    )
    return next((code for marker, code in categories if marker in content), "UNKNOWN_SAFE_ERROR")


def launch_backend(
    port: int,
    environment: dict[str, str],
    report: Report,
    *,
    stage: str = "Backend aislado iniciado",
) -> BackendHandle:
    """Lanza Uvicorn directamente y devuelve el handle antes de readiness."""

    started = time.perf_counter()
    child_environment = dict(environment)
    current_pythonpath = child_environment.get("PYTHONPATH", "")
    child_environment["PYTHONPATH"] = str(BACKEND) + (
        os.pathsep + current_pythonpath if current_pythonpath else ""
    )
    dispose_sentinel = DATABASE_DIR / f".phase10_dispose_{uuid4().hex}.ok"
    if (
        DATABASE_DIR.is_symlink()
        or dispose_sentinel.parent.is_symlink()
        or dispose_sentinel.exists()
        or dispose_sentinel.is_symlink()
        or dispose_sentinel.parent.resolve() != DATABASE_DIR.resolve()
    ):
        raise StageFailure(stage, "PHASE10_SENTINEL_PATH_INVALID")
    child_environment["PHASE10_DISPOSE_SENTINEL"] = str(dispose_sentinel)
    stdout_handle: IO[str] = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    stderr_handle: IO[str] = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    command = [
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
        "--no-access-log",
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=BACKEND,
            env=child_environment,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            shell=False,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
    except OSError as exc:
        stdout_handle.close()
        stderr_handle.close()
        raise StageFailure(
            stage,
            "BACKEND_SUBPROCESS_START_ERROR",
            exception_class=type(exc).__name__,
        ) from None
    backend = BackendHandle(
        process=process,
        port=port,
        main_pid=process.pid,
        command_category="UVICORN_DIRECT",
        stdout_handle=stdout_handle,
        stderr_handle=stderr_handle,
        owned_pids={process.pid},
        dispose_sentinel=dispose_sentinel,
    )
    report.add(stage, "PASS", "UVICORN_DIRECT", time.perf_counter() - started)
    return backend


def confirm_backend_process_active(
    backend: BackendHandle,
    report: Report,
    *,
    stage: str = "Proceso backend activo",
) -> None:
    if backend.process.poll() is not None:
        raise StageFailure(
            stage,
            "BACKEND_PROCESS_EXITED",
            exception_class="ProcessExited",
        )
    backend.state = "active"
    report.add(stage, "PASS", "BACKEND_PROCESS_ACTIVE")


def wait_for_backend_listener(
    backend: BackendHandle,
    report: Report,
    *,
    detected_stage: str = "Listener backend detectado",
    ownership_stage: str = "Propiedad del listener",
    timeout: float = 30.0,
) -> None:
    started = time.perf_counter()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if backend.process.poll() is not None:
            raise StageFailure(
                detected_stage,
                "BACKEND_PROCESS_EXITED",
                exception_class="ProcessExited",
            )
        observation = observe_backend_listener(backend)
        if observation.code == "BACKEND_LISTENER_NOT_READY":
            time.sleep(0.2)
            continue
        report.add(
            detected_stage,
            "PASS",
            "BACKEND_LISTENER_DETECTED",
            time.perf_counter() - started,
        )
        if observation.code == "BACKEND_LISTENER_FOREIGN":
            raise StageFailure(
                ownership_stage,
                "BACKEND_LISTENER_FOREIGN",
                exception_class="ListenerOwnershipFailure",
            )
        if observation.code == "BACKEND_LISTENER_OWNER_UNKNOWN":
            raise StageFailure(
                ownership_stage,
                "BACKEND_LISTENER_OWNER_UNKNOWN",
                exception_class="ListenerOwnershipUnknown",
            )
        backend.state = "listener_owned"
        report.add(
            ownership_stage,
            "PASS",
            "BACKEND_LISTENER_OWNED",
            time.perf_counter() - started,
        )
        return
    raise StageFailure(
        detected_stage,
        "BACKEND_LISTENER_NOT_READY",
        exception_class="ListenerTimeout",
    )


def wait_for_backend_health(
    backend: BackendHandle,
    report: Report,
    *,
    stage: str = "Health readiness",
    timeout: float = 30.0,
) -> None:
    started = time.perf_counter()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if backend.process.poll() is not None:
            raise StageFailure(
                stage,
                "BACKEND_PROCESS_EXITED",
                exception_class="ProcessExited",
            )
        health = request(backend.port, "GET", "/api/health")
        if health.status == 200 and health.json_valid:
            backend.state = "ready"
            report.add(
                stage,
                "PASS",
                "HTTP 200",
                time.perf_counter() - started,
            )
            return
        if health.status not in {0, 503}:
            raise StageFailure(
                stage,
                health.error_code,
                http_status=health.status,
                exception_class="HealthResponseFailure",
            )
        time.sleep(0.2)
    raise StageFailure(
        stage,
        "BACKEND_HEALTH_TIMEOUT",
        exception_class="ReadinessTimeout",
    )


def _drain_handle(handle: IO[str], *, limit: int = 65_536) -> tuple[str, bool]:
    if handle.closed:
        return "", False
    try:
        handle.flush()
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - limit), os.SEEK_SET)
        return handle.read(limit), True
    except (OSError, ValueError):
        return "", False


def _drain_shutdown_output(backend: BackendHandle) -> tuple[str, bool, bool, str | None]:
    stdout, stdout_ok = _drain_handle(backend.stdout_handle)
    stderr, stderr_ok = _drain_handle(backend.stderr_handle)
    combined = f"{stdout}\n{stderr}"
    # El contenido de logs se conserva únicamente para diagnóstico; nunca
    # determina la disposición de engines.
    if "DATABASE_DISPOSE_SENTINEL_WRITE_FAILED" in combined:
        log_code = "DATABASE_DISPOSE_SENTINEL_WRITE_FAILED"
    elif "DATABASE_ENGINES_DISPOSE_FAILED" in combined:
        log_code = "DATABASE_ENGINES_DISPOSE_FAILED"
    else:
        log_code = None
    return "BACKEND_SHUTDOWN_LOG_CAPTURED", stdout_ok, stderr_ok, log_code


def _validate_and_remove_dispose_sentinel(path: Path) -> tuple[bool, bool, str]:
    """Valida el centinela y lo elimina; no acepta rutas fuera del directorio."""

    if (
        ".." in path.parts
        or path.is_symlink()
        or path.parent.is_symlink()
        or path.parent.resolve() != DATABASE_DIR.resolve()
        or not re.fullmatch(r"\.phase10_dispose_[0-9a-f]{32}\.ok", path.name)
    ):
        return False, False, "DATABASE_DISPOSE_SENTINEL_INVALID"
    try:
        if not path.is_file():
            return False, False, "DATABASE_DISPOSE_SENTINEL_MISSING"
        if path.read_text(encoding="ascii") != "DISPOSED":
            return False, False, "DATABASE_DISPOSE_SENTINEL_INVALID"
        path.unlink()
        if path.exists() or path.is_symlink():
            return True, False, "DATABASE_DISPOSE_SENTINEL_WRITE_FAILED"
        return True, True, "DATABASE_ENGINES_DISPOSED"
    except (OSError, UnicodeError):
        return False, False, "DATABASE_DISPOSE_SENTINEL_INVALID"


def stop_backend(
    backend: BackendHandle | subprocess.Popen[str] | None,
    *,
    process_was_created: bool = False,
) -> ProcessStopResult:
    if backend is None:
        return ProcessStopResult(
            stopped=not process_was_created,
            graceful=not process_was_created,
            handles_closed=not process_was_created,
            waited=False,
            returncode_available=False,
            tree_stopped=not process_was_created,
            process_present=False,
        )
    handle = backend if isinstance(backend, BackendHandle) else None
    process = backend.process if handle is not None else backend
    graceful = process.poll() is not None
    waited = False
    try:
        if process.poll() is None:
            if os.name == "nt":
                process.send_signal(signal.CTRL_C_EVENT)
            else:
                process.terminate()
            try:
                process.wait(timeout=15)
                waited = True
                graceful = True
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                        timeout=10,
                    )
                process.kill()
                try:
                    process.wait(timeout=5)
                    waited = True
                except subprocess.TimeoutExpired:
                    graceful = False
        else:
            process.wait(timeout=0)
            waited = True
    except OSError:
        graceful = False
    shutdown_confirmation = "BACKEND_SHUTDOWN_SENTINEL_MISSING"
    sentinel_confirmation = "DATABASE_DISPOSE_SENTINEL_MISSING"
    stdout_drained = False
    stderr_drained = False
    sentinel_valid = False
    sentinel_removed = False
    log_code: str | None = None
    if handle is not None and waited:
        (
            _,
            stdout_drained,
            stderr_drained,
            log_code,
        ) = _drain_shutdown_output(handle)
    handles_ok = True
    streams: list[IO[str]] = []
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is not None:
            streams.append(stream)
    if handle is not None:
        streams.extend((handle.stdout_handle, handle.stderr_handle))
    closed_ids: set[int] = set()
    for stream in streams:
        if id(stream) in closed_ids:
            continue
        closed_ids.add(id(stream))
        if not stream.closed:
            try:
                stream.close()
            except OSError:
                handles_ok = False
    if handle is not None and waited and handles_ok:
        (
            sentinel_valid,
            sentinel_removed,
            shutdown_confirmation,
        ) = _validate_and_remove_dispose_sentinel(handle.dispose_sentinel)
        sentinel_confirmation = shutdown_confirmation
        if log_code == "DATABASE_DISPOSE_SENTINEL_WRITE_FAILED":
            sentinel_confirmation = log_code
        if log_code == "DATABASE_ENGINES_DISPOSE_FAILED" and process.returncode not in (0, None):
            shutdown_confirmation = "DATABASE_ENGINES_DISPOSE_FAILED"
        else:
            shutdown_confirmation = "DATABASE_ENGINES_DISPOSED"
    stopped = process.poll() is not None
    returncode_available = getattr(process, "returncode", None) is not None
    tree_stopped = stopped
    if handle is not None and len(handle.owned_pids) > 1:
        parents = process_parent_map()
        descendant_ids = handle.owned_pids - {handle.main_pid}
        running_owned = (
            set() if parents is None else descendant_ids.intersection(parents.keys())
        )
        if running_owned and os.name == "nt":
            for process_id in sorted(running_owned):
                subprocess.run(
                    ["taskkill", "/PID", str(process_id), "/T", "/F"],
                    capture_output=True,
                    check=False,
                    timeout=10,
                )
            parents = process_parent_map()
            running_owned = (
                set()
                if parents is None
                else descendant_ids.intersection(parents.keys())
            )
        tree_stopped = parents is not None and not running_owned
    return ProcessStopResult(
        stopped=stopped,
        graceful=graceful,
        handles_closed=handles_ok,
        waited=waited,
        returncode_available=returncode_available,
        tree_stopped=tree_stopped,
        process_present=True,
        shutdown_confirmation=shutdown_confirmation,
        stdout_drained=stdout_drained,
        stderr_drained=stderr_drained,
        sentinel_valid=sentinel_valid,
        sentinel_removed=sentinel_removed,
        sentinel_confirmation=sentinel_confirmation,
    )


def models_unloaded(port: int) -> bool:
    for endpoint in ("/api/models/embeddings/status", "/api/models/llm/status"):
        code, state = request(port, "GET", endpoint)
        if code != 200 or state.get("state") != "unloaded":
            return False
    return True


def engine_disposition(results: list[ProcessStopResult]) -> tuple[bool, str]:
    """Decide engines únicamente mediante la confirmación de shutdown."""

    if not results:
        return False, "BACKEND_SHUTDOWN_SENTINEL_MISSING"
    if any(result.shutdown_confirmation == "DATABASE_ENGINES_DISPOSE_FAILED" for result in results):
        return False, "DATABASE_ENGINES_DISPOSE_FAILED"
    if all(result.shutdown_confirmation == "DATABASE_ENGINES_DISPOSED" for result in results):
        return True, "DATABASE_ENGINES_DISPOSED"
    if any(result.shutdown_confirmation == "PHASE10_SENTINEL_PATH_INVALID" for result in results):
        return False, "PHASE10_SENTINEL_PATH_INVALID"
    if any(result.shutdown_confirmation == "BACKEND_SHUTDOWN_SENTINEL_INVALID" for result in results):
        return False, "BACKEND_SHUTDOWN_SENTINEL_INVALID"
    if any(result.shutdown_confirmation == "PHASE10_SENTINEL_REMOVE_FAILED" for result in results):
        return False, "PHASE10_SENTINEL_REMOVE_FAILED"
    return False, "BACKEND_SHUTDOWN_SENTINEL_MISSING"


def sentinel_disposition(results: list[ProcessStopResult]) -> tuple[bool, str]:
    """Evalúa exclusivamente la confirmación del archivo centinela."""

    if not results:
        return False, "DATABASE_DISPOSE_SENTINEL_MISSING"
    if all(
        getattr(result, "sentinel_valid", False)
        and getattr(result, "sentinel_removed", False)
        for result in results
    ):
        return True, "DATABASE_ENGINES_DISPOSED"
    codes = {getattr(result, "sentinel_confirmation", "DATABASE_DISPOSE_SENTINEL_MISSING") for result in results}
    if "DATABASE_DISPOSE_SENTINEL_INVALID" in codes:
        return False, "DATABASE_DISPOSE_SENTINEL_INVALID"
    if "DATABASE_DISPOSE_SENTINEL_WRITE_FAILED" in codes:
        return False, "DATABASE_DISPOSE_SENTINEL_WRITE_FAILED"
    return False, "DATABASE_DISPOSE_SENTINEL_MISSING"


def dispose_sentinel_residuals() -> bool:
    """Devuelve si quedó algún centinela de esta validación en el directorio."""

    if not DATABASE_DIR.is_dir() or DATABASE_DIR.is_symlink():
        return True
    try:
        return any(
            path.name.startswith(".phase10_dispose_")
            and (path.name.endswith(".ok") or ".ok." in path.name)
            for path in DATABASE_DIR.iterdir()
        )
    except OSError:
        return True


def report_is_private(content: str) -> bool:
    forbidden = (
        r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}",
        r"(?:[A-Za-z]:\\|/Users/|/home/)",
        r"\b(?:document_id|chunk_id|fingerprint|statement|rationale|sql)\b",
    )
    return not any(re.search(pattern, content, re.IGNORECASE) for pattern in forbidden)


def first_two_sources(copy_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    with closing(sqlite3.connect(copy_path)) as connection:
        with closing(
            connection.execute(
                "SELECT d.id, c.chunk_index FROM document_chunks c JOIN documents d ON d.id=c.document_id WHERE d.is_deleted=0 ORDER BY c.id LIMIT 2"
            )
        ) as cursor:
            rows = cursor.fetchall()
    if not rows:
        raise StageFailure(
            "Fuentes vinculadas",
            "NO_ACTIVE_SOURCE",
            exception_class="SourceLookupFailure",
        )
    while len(rows) < 2:
        rows.append(rows[0])
    return (
        {"document_id": rows[0][0], "chunk_index": rows[0][1]},
        {"document_id": rows[1][0], "chunk_index": rows[1][1]},
    )


def phase10_flow(report: Report, port: int, copy_path: Path) -> str:
    started = time.perf_counter()
    matrix = validate_http(
        "Matriz creada",
        request(port, "POST", "/api/hpn/matrices", {"title": "Matriz sintética temporal"}),
        201,
    )
    matrix_id = required_uuid_text(matrix, "id", "Matriz creada")
    report.add("Matriz creada", "PASS", "HTTP 201", time.perf_counter() - started)
    nodes: dict[str, dict[str, Any]] = {}
    for order, node_type in enumerate(("fact", "evidence", "norm"), start=1):
        stage = f"Nodo {node_type} creado"
        started = time.perf_counter()
        node = validate_http(
            stage,
            request(
                port,
                "POST",
                f"/api/hpn/matrices/{matrix_id}/nodes",
                {"node_type": node_type, "title": "Elemento sintético", "statement": "Contenido manual temporal", "review_status": "reviewed" if node_type == "fact" else "draft", "display_order": order},
            ),
            201,
        )
        required_uuid_text(node, "id", stage)
        nodes[node_type] = node
        report.add(stage, "PASS", "HTTP 201", time.perf_counter() - started)
    source_a, source_b = first_two_sources(copy_path)
    started = time.perf_counter()
    for node_type, source in (("evidence", source_a), ("norm", source_b)):
        validate_http(
            "Fuentes vinculadas",
            request(port, "POST", f"/api/hpn/matrices/{matrix_id}/nodes/{nodes[node_type]['id']}/sources", source),
            201,
        )
    report.add("Fuentes vinculadas", "PASS", "HTTP 201; fuentes resueltas desde SQLite", time.perf_counter() - started)
    started = time.perf_counter()
    incomplete = validate_http(
        "Validación incompleta",
        request(port, "GET", f"/api/hpn/matrices/{matrix_id}/validation"),
        200,
    )
    if incomplete.get("valid_for_review") is not False:
        raise StageFailure("Validación incompleta", "HPN_VALIDATION_STATE_INVALID", exception_class="ResponseContractFailure")
    report.add("Validación incompleta", "PASS", "HTTP 200; revisión final bloqueada", time.perf_counter() - started)
    started = time.perf_counter()
    for node_type in ("evidence", "norm"):
        validate_http(
            "Relaciones creadas",
            request(port, "PATCH", f"/api/hpn/matrices/{matrix_id}/nodes/{nodes[node_type]['id']}", {"review_status": "reviewed"}),
            200,
        )
    for node_type, relation_type in (("evidence", "evidence_supports_fact"), ("norm", "norm_applies_to_fact")):
        validate_http(
            "Relaciones creadas",
            request(
                port,
                "POST",
                f"/api/hpn/matrices/{matrix_id}/relations",
                {"source_node_id": nodes[node_type]["id"], "target_node_id": nodes["fact"]["id"], "relation_type": relation_type, "review_status": "reviewed"},
            ),
            201,
        )
    report.add("Relaciones creadas", "PASS", "HTTP 200/201; relaciones dirigidas creadas", time.perf_counter() - started)
    started = time.perf_counter()
    validation = validate_http(
        "Revisión completa",
        request(port, "GET", f"/api/hpn/matrices/{matrix_id}/validation"),
        200,
    )
    if validation.get("valid_for_review") is not True:
        raise StageFailure("Revisión completa", "HPN_VALIDATION_STATE_INVALID", exception_class="ResponseContractFailure")
    for status in ("in_review", "reviewed"):
        validate_http(
            "Revisión completa",
            request(port, "PATCH", f"/api/hpn/matrices/{matrix_id}", {"status": status}),
            200,
        )
    report.add("Revisión completa", "PASS", "HTTP 200; revisión humana habilitada", time.perf_counter() - started)
    started = time.perf_counter()
    node_update = validate_http(
        "CRUD matriz",
        request(port, "PATCH", f"/api/hpn/matrices/{matrix_id}/nodes/{nodes['fact']['id']}", {"statement": "Cambio manual temporal"}),
        200,
    )
    if node_update.get("review_status") != "reviewed":
        raise StageFailure("CRUD matriz", "HPN_NODE_UPDATE_INVALID", exception_class="ResponseContractFailure")
    report.add("CRUD matriz", "PASS", "HTTP 200; lectura y actualización validadas", time.perf_counter() - started)
    started = time.perf_counter()
    detail = validate_http(
        "reviewed a in_review",
        request(port, "GET", f"/api/hpn/matrices/{matrix_id}"),
        200,
    )
    matrix_detail = detail.get("matrix")
    if not isinstance(matrix_detail, dict) or matrix_detail.get("status") != "in_review":
        raise StageFailure("reviewed a in_review", "HPN_REVIEW_INVALIDATION_FAILED", exception_class="ResponseContractFailure")
    report.add("reviewed a in_review", "PASS", "HTTP 200; invalidación estructural comprobada", time.perf_counter() - started)
    started = time.perf_counter()
    with closing(sqlite3.connect(copy_path)) as connection:
        with closing(connection.cursor()) as cursor:
            cursor.execute("UPDATE document_chunks SET text=text || ' cambio temporal' WHERE document_id IN (?, ?)", (source_a["document_id"], str(source_a["document_id"])))
        connection.commit()
    detail = validate_http(
        "Fuente stale",
        request(port, "GET", f"/api/hpn/matrices/{matrix_id}"),
        200,
    )
    statuses = [source["source_status"] for node in detail.get("nodes", []) for source in node.get("sources", [])]
    if "stale" not in statuses:
        raise StageFailure("Fuente stale", "HPN_STALE_SOURCE_NOT_DETECTED", exception_class="ResponseContractFailure")
    report.add("Fuente stale", "PASS", "HTTP 200; cambio detectado sin reparar snapshot", time.perf_counter() - started)
    report.add("Persistencia preparada", "PASS", "Matriz disponible en copia aislada")
    return str(matrix_id)


def main() -> int:
    report = Report()
    copy_path = ROOT / "storage" / "database" / f".phase10_{uuid4().hex}.db"
    active_backend: BackendHandle | None = None
    launched_backends: list[BackendHandle] = []
    used_ports: list[int] = []
    original_before: tuple[int, int, int, int] | None = None
    exit_code = 1
    models_verified_unloaded = False
    completed_stops: dict[int, ProcessStopResult] = {}
    try:
        run_static(report)
        if not ORIGINAL_DB.is_file():
            raise StageFailure(
                "Precondición SQLite",
                "ORIGINAL_DATABASE_NOT_FOUND",
                exception_class="PreconditionFailure",
            )
        original_before = database_counts(ORIGINAL_DB)
        backup_database(ORIGINAL_DB, copy_path)
        report.add("Copia temporal", "PASS", "Backup SQLite coherente creado")
        environment = {
            **os.environ,
            **OFFLINE_ENV,
            "DATABASE_FILE": f"storage/database/{copy_path.name}",
        }
        configured_database = environment.get("DATABASE_FILE")
        if (
            configured_database != f"storage/database/{copy_path.name}"
            or not _owned_copy_path(copy_path)
        ):
            raise StageFailure(
                "Base aislada configurada",
                "ISOLATED_DATABASE_CONFIGURATION_INVALID",
                exception_class="ConfigurationFailure",
            )
        report.add(
            "Base aislada configurada",
            "PASS",
            "Alembic y backend usan la misma copia",
        )
        migration = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if migration.returncode != 0:
            raise StageFailure(
                "Migración aislada",
                "COPY_MIGRATION_FAILED",
                exception_class="SubprocessFailure",
            )
        report.add("Migración aislada", "PASS", "Copia temporal en head")
        with closing(sqlite3.connect(copy_path)) as connection:
            with closing(
                connection.execute("SELECT version_num FROM alembic_version")
            ) as cursor:
                current = cursor.fetchone()
        if current is None or current[0] != "20260725_04":
            raise StageFailure(
                "Alembic head",
                "ALEMBIC_HEAD_INVALID",
                exception_class="DatabaseValidationFailure",
            )
        report.add("Alembic head", "PASS", "Revisión 20260725_04")
        if database_counts(copy_path) != original_before:
            raise StageFailure(
                "Integridad documental en copia",
                "COPY_DOCUMENT_INTEGRITY_FAILED",
                exception_class="DatabaseValidationFailure",
            )
        report.add("Integridad documental en copia", "PASS", "Conteos conservados")
        port = free_port()
        used_ports.append(port)
        active_backend = launch_backend(port, environment, report)
        launched_backends.append(active_backend)
        confirm_backend_process_active(active_backend, report)
        wait_for_backend_listener(active_backend, report)
        wait_for_backend_health(active_backend, report)
        if not models_unloaded(port):
            raise StageFailure(
                "Independencia de IA",
                "MODEL_STATE_INVALID",
                exception_class="ResponseContractFailure",
            )
        report.add("Independencia de IA", "PASS", "Modelos permanecen unloaded")
        models_verified_unloaded = True
        matrix_id = phase10_flow(report, port, copy_path)
        if not models_unloaded(port):
            raise StageFailure(
                "Independencia de IA",
                "MODEL_STATE_CHANGED",
                exception_class="ResponseContractFailure",
            )
        first_stop = stop_backend(active_backend)
        if first_stop.complete:
            completed_stops[id(active_backend)] = first_stop
        if not first_stop.complete:
            raise StageFailure(
                "Cierre previo al reinicio",
                "BACKEND_STOP_FAILED",
                exception_class="ProcessCleanupFailure",
            )
        report.add(
            "Cierre previo al reinicio",
            "PASS",
            "Proceso y handles cerrados",
        )
        active_backend = None
        restart_port = free_port()
        while restart_port in used_ports:
            restart_port = free_port()
        used_ports.append(restart_port)
        active_backend = launch_backend(
            restart_port,
            environment,
            report,
            stage="Reinicio",
        )
        launched_backends.append(active_backend)
        confirm_backend_process_active(
            active_backend,
            report,
            stage="Proceso backend reiniciado",
        )
        wait_for_backend_listener(
            active_backend,
            report,
            detected_stage="Listener tras reinicio",
            ownership_stage="Propiedad tras reinicio",
        )
        wait_for_backend_health(
            active_backend,
            report,
            stage="Health tras reinicio",
        )
        started = time.perf_counter()
        validate_http(
            "Persistencia comprobada",
            request(restart_port, "GET", f"/api/hpn/matrices/{matrix_id}"),
            200,
        )
        report.add(
            "Persistencia comprobada",
            "PASS",
            "HTTP 200 tras reinicio",
            time.perf_counter() - started,
        )
        started = time.perf_counter()
        validate_http(
            "Borrado lógico",
            request(restart_port, "DELETE", f"/api/hpn/matrices/{matrix_id}"),
            204,
        )
        report.add(
            "Borrado lógico",
            "PASS",
            "HTTP 204",
            time.perf_counter() - started,
        )
        validate_http(
            "Cascada lógica",
            request(restart_port, "GET", f"/api/hpn/matrices/{matrix_id}"),
            409,
        )
        matrix_hex = UUID(matrix_id).hex
        with closing(sqlite3.connect(copy_path)) as connection:
            parameters = (matrix_id, matrix_hex)
            with closing(
                connection.execute(
                    "SELECT deleted_at IS NOT NULL FROM hpn_matrices WHERE id IN (?, ?)",
                    parameters,
                )
            ) as cursor:
                matrix_deleted = cursor.fetchone()
            with closing(
                connection.execute(
                    "SELECT COUNT(*), SUM(deleted_at IS NOT NULL) FROM hpn_nodes "
                    "WHERE matrix_id IN (?, ?)",
                    parameters,
                )
            ) as cursor:
                node_state = cursor.fetchone()
            with closing(
                connection.execute(
                    "SELECT COUNT(*), SUM(deleted_at IS NOT NULL) FROM hpn_relations "
                    "WHERE matrix_id IN (?, ?)",
                    parameters,
                )
            ) as cursor:
                relation_state = cursor.fetchone()
            with closing(
                connection.execute(
                    "SELECT COUNT(*), SUM(s.deleted_at IS NOT NULL) "
                    "FROM hpn_node_sources s JOIN hpn_nodes n ON n.id=s.node_id "
                    "WHERE n.matrix_id IN (?, ?)",
                    parameters,
                )
            ) as cursor:
                source_state = cursor.fetchone()
        states = (node_state, relation_state, source_state)
        if (
            matrix_deleted is None
            or matrix_deleted[0] != 1
            or any(
                state is None or state[0] < 1 or state[0] != state[1]
                for state in states
            )
        ):
            raise StageFailure(
                "Cascada lógica",
                "HPN_SOFT_DELETE_CASCADE_INVALID",
                exception_class="DatabaseValidationFailure",
            )
        report.add("Cascada lógica", "PASS", "Matriz y dependencias ocultas")
        if not models_unloaded(restart_port):
            raise StageFailure(
                "Independencia de IA",
                "FINAL_MODEL_STATE_INVALID",
                exception_class="ResponseContractFailure",
            )
        exit_code = 0
    except StageFailure as exc:
        report.add(exc.stage, "FAIL", exc.safe_detail())
        report.block_missing_execution_stages()
    except Exception as exc:
        report.add(
            "Fallo interno del validador",
            "FAIL",
            f"UNKNOWN_SAFE_ERROR; {type(exc).__name__}",
        )
        report.block_missing_execution_stages()
    finally:
        models_ok = models_verified_unloaded
        models_checked = models_verified_unloaded
        if (
            active_backend is not None
            and active_backend.state == "ready"
            and active_backend.process.poll() is None
        ):
            try:
                models_ok = models_unloaded(active_backend.port)
                models_checked = True
            except (OSError, ValueError, KeyError):
                models_ok = False
                models_checked = True
        report.add(
            "Modelos unloaded",
            "PASS"
            if models_checked and models_ok
            else ("FAIL" if models_checked else "BLOCKED"),
            "Qwen y embeddings no fueron cargados"
            if models_checked and models_ok
            else ("Estado inválido" if models_checked else "Backend no ready"),
        )
        report.add(
            "Cierre de clientes y conexiones",
            "PASS",
            "Clientes HTTP y conexiones SQLite usan contextos cerrados",
        )
        stop_results: list[ProcessStopResult] = []
        for backend in reversed(launched_backends):
            if id(backend) in completed_stops:
                stop_results.append(completed_stops[id(backend)])
                continue
            try:
                result = stop_backend(backend)
                completed_stops[id(backend)] = result
                stop_results.append(result)
            except (OSError, subprocess.SubprocessError):
                stop_results.append(
                    ProcessStopResult(
                        False,
                        False,
                        False,
                        process_present=True,
                    )
                )
        process_created = bool(launched_backends)
        processes_complete = process_created and all(
            result.complete for result in stop_results
        )
        listener_states = {
            backend.port: wait_for_listener_release(
                backend.port,
                backend.owned_pids,
            )
            for backend in launched_backends
        }
        for used_port in used_ports:
            if used_port not in listener_states:
                listener_states[used_port] = listener_state(used_port, set())
        own_listener = any(state == "own" for state in listener_states.values())
        foreign_listener = any(
            state == "foreign" for state in listener_states.values()
        )
        unknown_listener = any(
            state == "unknown" for state in listener_states.values()
        )
        cleanup_ok = processes_complete and not (
            own_listener or foreign_listener or unknown_listener
        )
        sentinels_residual = dispose_sentinel_residuals()
        report.add(
            "Centinelas de dispose",
            "FAIL" if sentinels_residual else "PASS",
            "Centinela residual detectado" if sentinels_residual else "Sin centinelas residuales",
        )
        cleanup_ok = cleanup_ok and not sentinels_residual
        process_row_result = (
            "PASS" if processes_complete else ("BLOCKED" if not process_created else "FAIL")
        )
        process_row_detail = (
            "Proceso esperado, árbol y handles cerrados"
            if processes_complete
            else ("No se creó subprocess" if not process_created else "Proceso no cerrado")
        )
        report.add("Cierre de Uvicorn", process_row_result, process_row_detail)
        process_released = not process_created or processes_complete
        report.add(
            "Procesos propios terminados",
            process_row_result,
            "No queda proceso del validador"
            if processes_complete
            else ("No se creó subprocess" if not process_created else "Proceso activo"),
        )
        ports_ok = not (own_listener or foreign_listener or unknown_listener)
        if own_listener:
            port_detail = "Listener propio activo"
        elif foreign_listener:
            port_detail = "Listener ajeno presente"
        elif unknown_listener:
            port_detail = "Propietario no determinado"
        else:
            port_detail = "Sin listener"
        report.add(
            "Liberación de puertos",
            "PASS" if ports_ok else "FAIL",
            port_detail,
        )
        release_probe = (
            probe_temporary_copy_release(copy_path)
            if process_released and ports_ok
            else ReleaseProbeResult(False, "ResourcesOpen")
        )
        report.add(
            "Archivo temporal liberado",
            "PASS" if release_probe.released else "FAIL",
            "Rename probe correcto" if release_probe.released else (release_probe.failure_type or "Bloqueado"),
        )
        removal = (
            remove_temporary_copy(copy_path)
            if release_probe.released
            else CleanupResult(False, False, 0, release_probe.failure_type)
        )
        engines_ok, engines_code = engine_disposition(stop_results)
        sentinel_ok, sentinel_code = sentinel_disposition(stop_results)
        engine_ok = engines_ok
        sentinel_result = (
            "PASS"
            if sentinel_ok
            else ("WARN" if sentinel_code == "DATABASE_DISPOSE_SENTINEL_MISSING" else "FAIL")
        )
        report.add("Confirmaci\u00f3n de disposici\u00f3n", sentinel_result, sentinel_code)
        report.add(
            "Disposición de engines",
            "PASS" if engine_ok else "FAIL",
            engines_code,
        )
        report.add(
            "Eliminación de sidecars",
            "PASS" if removal.sidecars_removed else "FAIL",
            f"Intentos: {removal.attempts}" if removal.sidecars_removed else (removal.failure_type or "Fallo seguro"),
        )
        report.add(
            "Eliminación de copia temporal",
            "PASS" if removal.removed else "FAIL",
            f"Intentos: {removal.attempts}" if removal.removed else (removal.failure_type or "Copia conservada"),
        )
        original_after = None
        if ORIGINAL_DB.is_file():
            try:
                original_after = database_counts(ORIGINAL_DB)
            except (OSError, sqlite3.Error):
                original_after = None
        integrity = original_before is not None and original_before == original_after
        report.add("Integridad original", "PASS" if integrity else "FAIL", "Conteos iniciales y finales iguales" if integrity else "Integridad no confirmada")
        copy_removed = removal.removed and not any(
            path.exists() or path.is_symlink()
            for path in (
                copy_path,
                *(copy_path.with_name(copy_path.name + suffix) for suffix in SIDECAR_SUFFIXES),
            )
        )
        report.add(
            "Eliminación de copia",
            "PASS" if copy_removed else "FAIL",
            "Copia temporal eliminada" if copy_removed else "Copia temporal presente",
        )
        final_cleanup = (
            cleanup_ok
            and process_released
            and engine_ok
            and ports_ok
            and release_probe.released
            and removal.sidecars_removed
            and copy_removed
        )
        report.add(
            "Finalización y limpieza",
            "PASS" if final_cleanup else "FAIL",
            "Procesos, handles, puertos y copia liberados"
            if final_cleanup
            else "Limpieza incompleta",
        )
        privacy_ok = report_is_private(report.render(1))
        report.add(
            "Privacidad del informe",
            "PASS" if privacy_ok else "FAIL",
            "Informe sanitizado" if privacy_ok else "Contenido no permitido",
        )
        exit_code = (
            0
            if exit_code == 0
            and report.passed
            and final_cleanup
            and models_ok
            and models_checked
            and privacy_ok
            else 1
        )
    rendered = report.render(exit_code)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    atomic_write(REPORTS / f"phase10_{timestamp}.md", rendered)
    atomic_write(REPORTS / "phase10_latest.md", rendered)
    print(f"VALIDACIÓN FASE 10: {'APROBADA' if exit_code == 0 else 'FALLIDA'}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
