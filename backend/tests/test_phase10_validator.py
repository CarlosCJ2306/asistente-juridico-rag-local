"""Pruebas sintÃ©ticas del validador HPN sin ejecutarlo."""

import asyncio
import importlib.util
import io
import sqlite3
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_phase10_end_to_end.py"
DIAGNOSTIC = SCRIPT.with_name("diagnose_phase10_cleanup.py")
EXECUTION_DIAGNOSTIC = SCRIPT.with_name("diagnose_phase10_execution.py")


def _validator_module():
    spec = importlib.util.spec_from_file_location("phase10_validator_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _diagnostic_module():
    scripts_dir = str(SCRIPT.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("phase10_cleanup_diagnostic_under_test", DIAGNOSTIC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _execution_diagnostic_module():
    scripts_dir = str(SCRIPT.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(
        "phase10_execution_diagnostic_under_test", EXECUTION_DIAGNOSTIC
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeProcess:
    stdin = None
    stdout = None
    stderr = None

    def __init__(self, pid: int = 321, *, returncode: int | None = None) -> None:
        self.pid = pid
        self.returncode = returncode
        self.waited = False

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float) -> int:
        del timeout
        self.waited = True
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def send_signal(self, signal_value: int) -> None:
        del signal_value
        self.returncode = 0

    def terminate(self) -> None:
        self.returncode = 0

    def kill(self) -> None:
        self.returncode = 1


def test_phase10_validator_name_and_guard() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert SCRIPT.name == "validate_phase10_end_to_end.py"
    assert 'if __name__ == "__main__":' in source
    assert "alembic\", \"upgrade\", \"head" in source
    assert "backup_database(ORIGINAL_DB, copy_path)" in source
    assert "source_connection.backup(destination_connection)" in source
    assert "SIDECAR_SUFFIXES" in source
    assert "remove_temporary_copy(copy_path)" in source
    assert source.rfind("remove_temporary_copy(copy_path)") < source.rfind("atomic_write(REPORTS")
    assert "and final_cleanup" in source
    assert "await database_session_manager.dispose()" in (
        (SCRIPT.parents[1] / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    )
    assert source.rfind("stop_backend(backend)") < source.rfind(
        "remove_temporary_copy(copy_path)"
    )


def test_phase10_validator_keeps_models_unloaded_and_uses_offline_environment() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_DATASETS_OFFLINE",
        "ANONYMIZED_TELEMETRY",
    ):
        assert key in source
    assert "/api/models/embeddings/status" in source
    assert "/api/models/llm/status" in source
    assert "/load" not in source


def test_phase10_validator_report_is_sanitized_and_atomic() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "os.fsync" in source
    assert "os.replace" in source
    assert "local_validation_reports" in source
    assert "phase10_latest.md" in source
    assert "response.text" not in source
    assert "traceback" not in source.lower()
    for row in (
        "Copia temporal",
        "Migración aislada",
        "Alembic head",
        "Integridad documental en copia",
        "Base aislada configurada",
        "Backend aislado iniciado",
        "Proceso backend activo",
        "Listener backend detectado",
        "Propiedad del listener",
        "Health readiness",
        "Matriz creada",
        "Nodo fact creado",
        "Nodo evidence creado",
        "Nodo norm creado",
        "Fuentes vinculadas",
        "Relaciones creadas",
        "Validación incompleta",
        "Revisión completa",
        "reviewed a in_review",
        "Fuente stale",
        "Cierre previo al reinicio",
        "Reinicio",
        "Proceso backend reiniciado",
        "Listener tras reinicio",
        "Propiedad tras reinicio",
        "Health tras reinicio",
        "Persistencia comprobada",
        "Borrado lógico",
        "Cascada lógica",
        "Cierre de clientes y conexiones",
        "Disposición de engines",
        "Cierre de Uvicorn",
        "Liberación de puertos",
        "Eliminación de sidecars",
        "Eliminación de copia temporal",
        "Integridad original",
        "Modelos unloaded",
        "Eliminación de copia",
        "Finalización y limpieza",
        "Procesos propios terminados",
        "Archivo temporal liberado",
    ):
        assert row in source
    assert "SUM(deleted_at IS NOT NULL)" in source
    assert 'report.add("Ejecución"' not in source
    assert 'report.add("EjecuciÃ³n"' not in source
    assert "engine_disposition(stop_results)" in source
    assert "_drain_shutdown_output(handle)" in source
    assert "DATABASE_ENGINES_DISPOSED" in source
    assert "and engine_ok" in source


def test_phase10_sqlite_connections_and_cursors_are_closed_before_rename(
    tmp_path: Path,
) -> None:
    module = _validator_module()
    database = tmp_path / "synthetic.db"
    connection = sqlite3.connect(database)
    try:
        for table in (
            "documents",
            "document_pages",
            "document_chunks",
            "document_chunks_fts",
        ):
            cursor = connection.execute(f"CREATE TABLE {table} (id INTEGER)")
            cursor.close()
        connection.commit()
    finally:
        connection.close()
    assert module.database_counts(database) == (0, 0, 0, 0)
    renamed = database.with_suffix(".renamed")
    database.replace(renamed)
    renamed.replace(database)
    source = SCRIPT.read_text(encoding="utf-8")
    assert "with sqlite3.connect" not in source
    assert "closing(sqlite3.connect" in source
    assert "closing(connection.execute" in source
    assert "closing(connection.cursor())" in source


def test_phase10_backup_closes_source_and_destination(tmp_path: Path) -> None:
    module = _validator_module()
    source = tmp_path / "source.db"
    destination = tmp_path / "destination.db"
    connection = sqlite3.connect(source)
    try:
        connection.execute("CREATE TABLE synthetic (id INTEGER)").close()
        connection.commit()
    finally:
        connection.close()
    module.backup_database(source, destination)
    source_renamed = source.with_suffix(".source-renamed")
    destination_renamed = destination.with_suffix(".destination-renamed")
    source.replace(source_renamed)
    destination.replace(destination_renamed)
    assert source_renamed.is_file() and destination_renamed.is_file()


def test_phase10_parent_has_no_application_engine_and_alembic_disposes() -> None:
    validator = SCRIPT.read_text(encoding="utf-8")
    alembic = (SCRIPT.parents[1] / "backend" / "alembic" / "env.py").read_text(
        encoding="utf-8"
    )
    assert "create_async_engine" not in validator
    assert "from app." not in validator
    assert "finally:" in alembic
    assert "await connectable.dispose()" in alembic


def test_phase10_uvicorn_is_isolated_and_gracefully_waited() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"--workers"' in source
    assert '"--no-access-log"' in source
    assert "--reload" not in source
    assert "CREATE_NEW_PROCESS_GROUP" in source
    assert "CTRL_C_EVENT" in source
    assert "process.wait(timeout=" in source
    assert '["taskkill", "/PID", str(process.pid), "/T", "/F"]' in source


def test_phase10_listener_classification_ignores_time_wait_and_foreign_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _validator_module()
    output = "\n".join(
        (
            "TCP 127.0.0.1:41000 0.0.0.0:0 LISTENING 123",
            "TCP 127.0.0.1:41001 127.0.0.1:50000 TIME_WAIT 123",
        )
    )
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=output, returncode=0),
    )
    assert module.listening_pids(41000) == {123}
    assert module.listener_state(41000, {123}) == "own"
    assert module.listener_state(41000, {999}) == "foreign"
    assert module.listener_state(41001, {123}) == "free"
    port = module.free_port()
    assert 1 <= port <= 65535


def test_phase10_copy_path_is_closed_and_traversal_safe(tmp_path: Path) -> None:
    module = _validator_module()
    database_dir = tmp_path / "storage" / "database"
    database_dir.mkdir(parents=True)
    module.DATABASE_DIR = database_dir
    valid = database_dir / f".phase10_{'a' * 32}.db"
    assert module._owned_copy_path(valid)
    assert not module._owned_copy_path(database_dir / ".." / "database" / valid.name)
    assert not module._owned_copy_path(database_dir / "unrelated.db")
    assert not module._owned_copy_path(database_dir / "asistente_juridico.db")
    symlink = database_dir / f".phase10_{'b' * 32}.db"
    try:
        symlink.symlink_to(valid)
    except (OSError, NotImplementedError):
        pytest.skip("El sistema no permite crear symlinks en esta prueba")
    assert not module._owned_copy_path(symlink)


def test_phase10_copy_removal_retries_permission_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _validator_module()
    database_dir = tmp_path / "storage" / "database"
    database_dir.mkdir(parents=True)
    module.DATABASE_DIR = database_dir
    target = database_dir / f".phase10_{'c' * 32}.db"
    target.write_text("synthetic", encoding="utf-8")
    for suffix in module.SIDECAR_SUFFIXES:
        target.with_name(target.name + suffix).write_text("sidecar", encoding="utf-8")
    original_unlink = Path.unlink
    calls = 0

    def flaky_unlink(path: Path, *, missing_ok: bool = False) -> None:
        nonlocal calls
        if path == target and calls == 0:
            calls += 1
            raise PermissionError("synthetic lock")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    result = module.remove_temporary_copy(target, attempts=3)
    assert result.removed is True
    assert result.sidecars_removed is True
    assert result.attempts >= 2
    assert not target.exists()
    assert all(not target.with_name(target.name + suffix).exists() for suffix in module.SIDECAR_SUFFIXES)


def test_phase10_copy_removal_reports_persistent_lock_without_deleting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _validator_module()
    database_dir = tmp_path / "storage" / "database"
    database_dir.mkdir(parents=True)
    module.DATABASE_DIR = database_dir
    target = database_dir / f".phase10_{'d' * 32}.db"
    target.write_text("synthetic", encoding="utf-8")

    def locked_unlink(path: Path, *, missing_ok: bool = False) -> None:
        del missing_ok
        if path == target:
            raise PermissionError("synthetic lock")
        Path.unlink(path, missing_ok=True)

    monkeypatch.setattr(Path, "unlink", locked_unlink)
    result = module.remove_temporary_copy(target, attempts=2)
    assert result.removed is False
    assert result.failure_type == "PermissionError"
    assert target.exists()


def test_phase10_rename_probe_restores_name_and_detects_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _validator_module()
    database_dir = tmp_path / "storage" / "database"
    database_dir.mkdir(parents=True)
    module.DATABASE_DIR = database_dir
    target = database_dir / f".phase10_{'e' * 32}.db"
    target.write_text("synthetic", encoding="utf-8")
    result = module.probe_temporary_copy_release(target)
    assert result.released is True
    assert target.is_file()
    original_replace = Path.replace

    def locked_replace(path: Path, target_path: Path) -> Path:
        if path == target:
            raise PermissionError("synthetic lock")
        return original_replace(path, target_path)

    monkeypatch.setattr(Path, "replace", locked_replace)
    blocked = module.probe_temporary_copy_release(target)
    assert blocked.released is False
    assert blocked.failure_type == "PermissionError"
    assert target.is_file()


def test_phase10_cleanup_diagnostic_success_writes_sanitized_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _diagnostic_module()
    report_dir = tmp_path / "reports"
    residual = tmp_path / ".phase10_synthetic.db"
    calls = iter(([residual], []))
    monkeypatch.setattr(module, "REPORTS", report_dir)
    monkeypatch.setattr(module, "residual_copies", lambda: next(calls))
    monkeypatch.setattr(module, "sidecar_count", lambda copies: 0)
    monkeypatch.setattr(module, "own_process_ids", set)
    monkeypatch.setattr(module, "listening_process_ids", set)
    monkeypatch.setattr(
        module,
        "probe_temporary_copy_release",
        lambda path: SimpleNamespace(released=True),
    )
    monkeypatch.setattr(
        module,
        "remove_temporary_copy",
        lambda path: SimpleNamespace(removed=True, attempts=1),
    )
    assert module.main() == 0
    reports = list(report_dir.glob("phase10_cleanup_*.md"))
    assert len(reports) == 1
    content = reports[0].read_text(encoding="utf-8")
    assert "DIAGNÓSTICO LIMPIEZA FASE 10: COMPLETADO" in content
    assert "synthetic.db" not in content


def test_phase10_cleanup_diagnostic_blocked_returns_failure_without_deleting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _diagnostic_module()
    report_dir = tmp_path / "reports"
    monkeypatch.setattr(module, "REPORTS", report_dir)
    monkeypatch.setattr(module, "residual_copies", lambda: [tmp_path / "residual.db"])
    monkeypatch.setattr(module, "sidecar_count", lambda copies: 1)
    monkeypatch.setattr(module, "own_process_ids", lambda: {10})
    monkeypatch.setattr(module, "listening_process_ids", lambda: {10})

    def unexpected_delete(path: Path) -> None:
        raise AssertionError("La eliminación no debe ejecutarse")

    monkeypatch.setattr(module, "remove_temporary_copy", unexpected_delete)
    assert module.main() == 1
    reports = list(report_dir.glob("phase10_cleanup_*.md"))
    assert len(reports) == 1
    content = reports[0].read_text(encoding="utf-8")
    assert "DIAGNÓSTICO LIMPIEZA FASE 10: FALLIDO" in content
    assert "Código de salida: 1" in content


def test_phase10_stage_failure_and_blocked_rows_are_safe() -> None:
    module = _validator_module()
    report = module.Report()
    failure = module.StageFailure(
        "Health readiness",
        "BACKEND_HEALTH_TIMEOUT",
        http_status=503,
        exception_class="ReadinessTimeout",
    )
    report.add(failure.stage, "FAIL", failure.safe_detail())
    report.block_missing_execution_stages()
    rows = {name: (result, detail) for name, result, detail, _ in report.rows}
    assert rows["Health readiness"] == (
        "FAIL",
        "HTTP 503; BACKEND_HEALTH_TIMEOUT; ReadinessTimeout",
    )
    assert rows["Independencia de IA"][0] == "BLOCKED"
    assert not any(name.startswith("Ejec") for name in rows)


def test_phase10_http_response_contract_handles_empty_and_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _validator_module()

    class Response:
        def __init__(self, status: int, body: bytes) -> None:
            self.status = status
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int) -> bytes:
            assert limit == 65_536
            return self.body

    responses = iter((Response(204, b""), Response(200, b"not-json")))
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda *args, **kwargs: next(responses),
    )
    empty = module.request(8000, "DELETE", "/synthetic")
    invalid = module.request(8000, "GET", "/synthetic")
    assert (empty.status, empty.data, empty.json_valid) == (204, {}, True)
    assert invalid.status == 200
    assert invalid.error_code == "INVALID_JSON_RESPONSE"
    assert invalid.data == {}
    assert invalid.json_valid is False


def test_phase10_http_error_code_is_stable_and_body_is_not_propagated() -> None:
    module = _validator_module()
    assert (
        module._safe_error_code(
            {"detail": {"error_code": "HPN_MATRIX_NOT_FOUND", "unsafe": "secret"}},
            default="UNKNOWN_SAFE_ERROR",
        )
        == "HPN_MATRIX_NOT_FOUND"
    )
    with pytest.raises(module.StageFailure) as captured:
        module.validate_http(
            "Matriz creada",
            module.HttpResult(
                500,
                {"unsafe": "synthetic-sensitive-marker"},
                "UNKNOWN_SAFE_ERROR",
                True,
            ),
            201,
        )
    assert captured.value.safe_detail() == (
        "HTTP 500; UNKNOWN_SAFE_ERROR; HttpValidationFailure"
    )
    assert "synthetic-sensitive-marker" not in captured.value.safe_detail()


def test_phase10_backend_early_exit_is_classified_and_log_handle_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _validator_module()
    process = _FakeProcess(returncode=1)
    monkeypatch.setattr(
        module.subprocess,
        "Popen",
        lambda *args, **kwargs: process,
    )
    report = module.Report()
    backend = module.launch_backend(49100, {}, report)
    assert backend.process is process
    assert backend.owned_pids == {process.pid}
    with pytest.raises(module.StageFailure) as captured:
        module.confirm_backend_process_active(backend, report)
    assert captured.value.stage == "Proceso backend activo"
    assert captured.value.error_code == "BACKEND_PROCESS_EXITED"
    result = module.stop_backend(backend)
    assert result.complete is True
    assert backend.stdout_handle.closed and backend.stderr_handle.closed


def test_phase10_backend_subprocess_start_failure_is_specific(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _validator_module()
    monkeypatch.setattr(
        module.subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            FileNotFoundError("synthetic")
        ),
    )
    with pytest.raises(module.StageFailure) as captured:
        module.launch_backend(49103, {}, module.Report())
    assert captured.value.stage == "Backend aislado iniciado"
    assert captured.value.error_code == "BACKEND_SUBPROCESS_START_ERROR"
    assert captured.value.exception_class == "FileNotFoundError"


def test_phase10_backend_startup_failure_and_health_timeout_are_specific(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _validator_module()
    process = _FakeProcess(pid=322)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: process)
    backend = module.launch_backend(49105, {}, module.Report())
    assert backend.process is process
    backend.state = "listener_owned"
    monotonic = iter((0.0, 31.0))
    monkeypatch.setattr(module.time, "monotonic", lambda: next(monotonic))
    with pytest.raises(module.StageFailure) as timeout_failure:
        module.wait_for_backend_health(backend, module.Report())
    assert timeout_failure.value.stage == "Health readiness"
    assert timeout_failure.value.error_code == "BACKEND_HEALTH_TIMEOUT"
    assert backend.process is process
    assert not backend.stdout_handle.closed
    assert module.stop_backend(backend).complete is True


def test_phase10_foreign_listener_is_rejected_before_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _validator_module()
    process = _FakeProcess(pid=323)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: process)
    backend = module.launch_backend(49106, {}, module.Report())
    monkeypatch.setattr(
        module,
        "observe_backend_listener",
        lambda handle: module.ListenerObservation("BACKEND_LISTENER_FOREIGN"),
    )
    report = module.Report()
    with pytest.raises(module.StageFailure) as captured:
        module.wait_for_backend_listener(backend, report)
    assert captured.value.error_code == "BACKEND_LISTENER_FOREIGN"
    assert captured.value.stage == "Propiedad del listener"
    report.add(captured.value.stage, "FAIL", captured.value.safe_detail())
    report.block_missing_execution_stages()
    rows = {name: result for name, result, _, _ in report.rows}
    assert rows["Health readiness"] == "BLOCKED"
    assert backend.process is process
    assert module.stop_backend(backend).complete is True


def test_phase10_health_is_requested_only_after_expected_listener_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _validator_module()

    process = _FakeProcess(pid=324)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: process)
    backend = module.launch_backend(49109, {}, module.Report())
    observations = iter(
        (
            module.ListenerObservation("BACKEND_LISTENER_NOT_READY"),
            module.ListenerObservation(
                "BACKEND_LISTENER_OWNED", frozenset({process.pid})
            ),
        )
    )
    monkeypatch.setattr(
        module,
        "observe_backend_listener",
        lambda handle: next(observations),
    )
    calls: list[int] = []

    def fake_request(port, method, path, payload=None):
        calls.append(port)
        return module.HttpResult(200, {}, "NONE", True)

    monkeypatch.setattr(module, "request", fake_request)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    report = module.Report()
    module.wait_for_backend_listener(backend, report)
    assert calls == []
    module.wait_for_backend_health(backend, report)
    assert calls == [49109]
    assert module.stop_backend(backend).complete is True


def test_phase10_http_client_uses_the_selected_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _validator_module()
    seen: list[str] = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int) -> bytes:
            return b"{}"

    def fake_urlopen(call, timeout):
        seen.append(call.full_url)
        return Response()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    assert module.request(49107, "GET", "/api/health").status == 200
    assert seen == ["http://127.0.0.1:49107/api/health"]


def test_phase10_launch_is_direct_and_preserves_process_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _validator_module()
    process = _FakeProcess(pid=400)
    captured: dict[str, object] = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return process

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    backend = module.launch_backend(49110, {"DATABASE_FILE": "safe.db"}, module.Report())
    command = captured["command"]
    assert command[:4] == [sys.executable, "-m", "uvicorn", "app.main:app"]
    assert "--workers" in command and "1" in command
    assert "--reload" not in command
    assert captured["shell"] is False
    assert captured["cwd"] == module.BACKEND
    assert captured["stdout"] is not captured["stderr"]
    assert backend.process is process
    assert backend.owned_pids == {process.pid}
    assert backend.command_category == "UVICORN_DIRECT"
    stop_result = module.stop_backend(backend)
    assert stop_result.complete is True
    assert stop_result.waited is True
    assert stop_result.returncode_available is True
    assert process.waited is True
    assert backend.stdout_handle.closed and backend.stderr_handle.closed


@pytest.mark.parametrize(
    ("owners", "parents", "expected"),
    (
        ({410}, None, "BACKEND_LISTENER_OWNED"),
        ({411}, {411: 410}, "BACKEND_LISTENER_OWNED"),
        ({999}, {999: 998}, "BACKEND_LISTENER_FOREIGN"),
        ({411}, None, "BACKEND_LISTENER_OWNER_UNKNOWN"),
    ),
)
def test_phase10_listener_ownership_classification(
    owners: set[int],
    parents: dict[int, int] | None,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _validator_module()
    process = _FakeProcess(pid=410)
    backend = module.BackendHandle(
        process=process,
        port=49111,
        main_pid=process.pid,
        command_category="UVICORN_DIRECT",
        stdout_handle=io.StringIO(),
        stderr_handle=io.StringIO(),
        owned_pids={process.pid},
    )
    monkeypatch.setattr(
        module,
        "listener_owner_query",
        lambda port: (True, owners),
    )
    monkeypatch.setattr(module, "process_parent_map", lambda: parents)
    observation = module.observe_backend_listener(backend)
    assert observation.code == expected
    if expected == "BACKEND_LISTENER_OWNED":
        assert owners.issubset(backend.owned_pids)


def test_phase10_process_exit_before_listener_preserves_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _validator_module()
    process = _FakeProcess(pid=420, returncode=1)
    backend = module.BackendHandle(
        process=process,
        port=49112,
        main_pid=process.pid,
        command_category="UVICORN_DIRECT",
        stdout_handle=io.StringIO(),
        stderr_handle=io.StringIO(),
        owned_pids={process.pid},
    )
    with pytest.raises(module.StageFailure) as captured:
        module.wait_for_backend_listener(backend, module.Report())
    assert captured.value.error_code == "BACKEND_PROCESS_EXITED"
    assert backend.process is process


def test_phase10_cleanup_does_not_treat_lost_or_unknown_process_as_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _validator_module()
    lost = module.stop_backend(None, process_was_created=True)
    assert lost.complete is False
    assert lost.process_present is False
    monkeypatch.setattr(
        module,
        "listener_owner_query",
        lambda port: (True, {999}),
    )
    assert module.listener_state(49113, set()) == "foreign"
    monkeypatch.setattr(
        module,
        "listener_owner_query",
        lambda port: (True, None),
    )
    assert module.listener_state(49113, set()) == "unknown"


def test_fastapi_lifespan_disposes_only_at_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main as app_main

    disposed: list[bool] = []

    class Manager:
        async def dispose(self) -> None:
            disposed.append(True)

    monkeypatch.setattr(app_main, "database_session_manager", Manager())

    async def exercise() -> None:
        async with app_main.lifespan(app_main.app):
            assert disposed == []
        assert disposed == [True]

    asyncio.run(exercise())


def test_fastapi_lifespan_disposes_without_stdout_ipc(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from app import main as app_main

    disposed: list[bool] = []

    class Manager:
        async def dispose(self) -> None:
            disposed.append(True)

    monkeypatch.setattr(app_main, "database_session_manager", Manager())
    monkeypatch.delenv("PHASE10_DISPOSE_SENTINEL", raising=False)

    async def exercise() -> None:
        async with app_main.lifespan(app_main.app):
            pass

    asyncio.run(exercise())
    captured = capsys.readouterr()
    assert disposed == [True]
    assert "DATABASE_ENGINES_DISPOSED" not in captured.out
    assert "DATABASE_ENGINES_DISPOSE_FAILED" not in captured.out


def _phase10_main_layout(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    app_dir = project / "backend" / "app"
    database_dir = project / "storage" / "database"
    app_dir.mkdir(parents=True)
    database_dir.mkdir(parents=True)
    main_file = app_dir / "main.py"
    main_file.write_text("", encoding="utf-8")
    return main_file, database_dir


def test_phase10_dispose_sentinel_absent_in_production_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app import main as app_main

    main_file, database_dir = _phase10_main_layout(tmp_path)
    monkeypatch.setattr(app_main, "__file__", str(main_file))
    monkeypatch.delenv("PHASE10_DISPOSE_SENTINEL", raising=False)
    app_main._write_phase10_dispose_sentinel()
    assert list(database_dir.iterdir()) == []


def test_phase10_dispose_sentinel_is_atomic_and_exact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app import main as app_main

    main_file, database_dir = _phase10_main_layout(tmp_path)
    monkeypatch.setattr(app_main, "__file__", str(main_file))
    sentinel = database_dir / (".phase10_dispose_" + "b" * 32 + ".ok")
    monkeypatch.setenv("PHASE10_DISPOSE_SENTINEL", str(sentinel))
    app_main._write_phase10_dispose_sentinel()
    assert sentinel.read_text(encoding="ascii") == "DISPOSED"
    assert not list(database_dir.glob(".*.tmp"))


def test_phase10_dispose_sentinel_rejects_traversal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app import main as app_main

    main_file, database_dir = _phase10_main_layout(tmp_path)
    monkeypatch.setattr(app_main, "__file__", str(main_file))
    outside = database_dir.parent / (".phase10_dispose_" + "c" * 32 + ".ok")
    monkeypatch.setenv("PHASE10_DISPOSE_SENTINEL", str(outside))
    with pytest.raises(RuntimeError, match="PHASE10_DISPOSE_SENTINEL_INVALID"):
        app_main._write_phase10_dispose_sentinel()
    assert not outside.exists()


def test_phase10_invalid_or_residual_sentinel_fails_safely(tmp_path: Path) -> None:
    module = _validator_module()
    module.DATABASE_DIR = tmp_path
    invalid = tmp_path / (".phase10_dispose_" + "e" * 32 + ".ok")
    invalid.write_text("WRONG", encoding="ascii")
    valid, removed, code = module._validate_and_remove_dispose_sentinel(invalid)
    assert (valid, removed, code) == (
        False,
        False,
        "DATABASE_DISPOSE_SENTINEL_INVALID",
    )
    assert invalid.exists()
    residual = tmp_path / ".phase10_dispose_f.tmp"
    residual.write_text("", encoding="ascii")
    assert module.dispose_sentinel_residuals() is True


def test_phase10_dispose_failure_does_not_create_sentinel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app import main as app_main

    main_file, database_dir = _phase10_main_layout(tmp_path)
    monkeypatch.setattr(app_main, "__file__", str(main_file))
    sentinel = database_dir / (".phase10_dispose_" + "d" * 32 + ".ok")
    monkeypatch.setenv("PHASE10_DISPOSE_SENTINEL", str(sentinel))

    class Manager:
        async def dispose(self) -> None:
            raise RuntimeError("sensitive")

    monkeypatch.setattr(app_main, "database_session_manager", Manager())
    async def exercise() -> None:
        async with app_main.lifespan(app_main.app):
            pass

    with pytest.raises(RuntimeError, match="DATABASE_ENGINES_DISPOSE_FAILED"):
        asyncio.run(exercise())
    assert not sentinel.exists()


def test_database_session_dispose_is_idempotent_and_detaches_before_await() -> None:
    from app.database.session import DatabaseSessionManager

    class Engine:
        def __init__(self, *, fail: bool = False) -> None:
            self.calls = 0
            self.fail = fail

        async def dispose(self) -> None:
            self.calls += 1
            if self.fail:
                raise RuntimeError("engine failure")

    async def exercise() -> None:
        manager = DatabaseSessionManager(Path("synthetic.db"))
        engine = Engine()
        manager._engine = engine  # type: ignore[assignment]
        manager._session_factory = object()  # type: ignore[assignment]
        await manager.dispose()
        await manager.dispose()
        assert engine.calls == 1
        assert manager._engine is None
        assert manager._session_factory is None

        failing = DatabaseSessionManager(Path("synthetic.db"))
        failed_engine = Engine(fail=True)
        failing._engine = failed_engine  # type: ignore[assignment]
        failing._session_factory = object()  # type: ignore[assignment]
        with pytest.raises(RuntimeError, match="engine failure"):
            await failing.dispose()
        assert failing._engine is None
        assert failing._session_factory is None

    asyncio.run(exercise())


def test_sentinel_write_failure_is_not_engine_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main as app_main

    disposed: list[bool] = []

    class Manager:
        async def dispose(self) -> None:
            disposed.append(True)

    monkeypatch.setattr(app_main, "database_session_manager", Manager())
    monkeypatch.setattr(
        app_main,
        "_write_phase10_dispose_sentinel",
        lambda: (_ for _ in ()).throw(RuntimeError("sentinel")),
    )

    async def exercise() -> None:
        async with app_main.lifespan(app_main.app):
            pass

    asyncio.run(exercise())
    assert disposed == [True]
    module = _validator_module()
    result = module.ProcessStopResult(
        True,
        True,
        True,
        waited=True,
        returncode_available=True,
        tree_stopped=True,
        shutdown_confirmation="DATABASE_ENGINES_DISPOSED",
        sentinel_confirmation="DATABASE_DISPOSE_SENTINEL_WRITE_FAILED",
    )
    assert module.engine_disposition([result]) == (True, "DATABASE_ENGINES_DISPOSED")
    assert module.sentinel_disposition([result]) == (
        False,
        "DATABASE_DISPOSE_SENTINEL_WRITE_FAILED",
    )


def test_missing_sentinel_is_warning_and_does_not_fail_report() -> None:
    module = _validator_module()
    report = module.Report()
    report.add("Confirmación de disposición", "WARN", "DATABASE_DISPOSE_SENTINEL_MISSING")
    report.add("Limpieza objetiva", "PASS", "Recursos liberados")
    assert report.passed is True


def test_generic_nonzero_returncode_does_not_prove_engine_failure() -> None:
    module = _validator_module()
    result = module.ProcessStopResult(
        True,
        False,
        True,
        waited=True,
        returncode_available=True,
        tree_stopped=True,
        shutdown_confirmation="DATABASE_ENGINES_DISPOSED",
    )
    assert module.engine_disposition([result]) == (True, "DATABASE_ENGINES_DISPOSED")


def test_phase10_stop_validates_and_removes_sentinel_after_draining_handles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _validator_module()
    monkeypatch.setattr(module, "DATABASE_DIR", tmp_path)
    sentinel = tmp_path / (".phase10_dispose_" + "a" * 32 + ".ok")
    sentinel.write_text("DISPOSED", encoding="ascii")
    process = _FakeProcess(pid=430)
    stdout = io.StringIO("normal output")
    stderr = io.StringIO("DATABASE_ENGINES_DISPOSE_FAILED\n")
    backend = module.BackendHandle(
        process=process,
        port=49114,
        main_pid=process.pid,
        command_category="UVICORN_DIRECT",
        stdout_handle=stdout,
        stderr_handle=stderr,
        owned_pids={process.pid},
        dispose_sentinel=sentinel,
    )
    result = module.stop_backend(backend)
    assert result.shutdown_confirmation == "DATABASE_ENGINES_DISPOSED"
    assert result.sentinel_valid is True
    assert result.sentinel_removed is True
    assert result.stdout_drained is True
    assert result.stderr_drained is True
    assert stdout.closed and stderr.closed
    assert result.complete is True


def test_phase10_shutdown_marker_categories_and_engine_row_semantics() -> None:
    module = _validator_module()
    success = module.ProcessStopResult(
        True,
        True,
        True,
        waited=True,
        returncode_available=True,
        tree_stopped=True,
        shutdown_confirmation="DATABASE_ENGINES_DISPOSED",
        sentinel_valid=True,
        sentinel_removed=True,
    )
    failure = module.ProcessStopResult(
        True,
        True,
        True,
        waited=True,
        returncode_available=True,
        tree_stopped=True,
        shutdown_confirmation="DATABASE_ENGINES_DISPOSE_FAILED",
        sentinel_valid=False,
        sentinel_removed=False,
    )
    missing = module.ProcessStopResult(
        True,
        True,
        True,
        waited=True,
        returncode_available=True,
        tree_stopped=True,
        sentinel_valid=False,
        sentinel_removed=False,
    )
    assert module.engine_disposition([success]) == (
        True,
        "DATABASE_ENGINES_DISPOSED",
    )
    assert module.engine_disposition([failure]) == (
        False,
        "DATABASE_ENGINES_DISPOSE_FAILED",
    )
    assert module.engine_disposition([missing]) == (
        False,
        "BACKEND_SHUTDOWN_SENTINEL_MISSING",
    )
    assert module.engine_disposition([success, missing])[0] is False


def test_fastapi_lifespan_dispose_failure_emits_only_safe_category(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from app import main as app_main

    class Manager:
        async def dispose(self) -> None:
            raise RuntimeError("sensitive database path")

    monkeypatch.setattr(app_main, "database_session_manager", Manager())
    monkeypatch.delenv("PHASE10_DISPOSE_SENTINEL", raising=False)

    async def exercise() -> None:
        async with app_main.lifespan(app_main.app):
            pass

    with pytest.raises(RuntimeError):
        asyncio.run(exercise())
    captured = capsys.readouterr()
    assert "DATABASE_ENGINES_DISPOSE_FAILED" not in captured.out
    assert "sensitive database path" not in captured.out


def test_phase10_validator_uses_one_database_setting_for_migration_and_backend() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"DATABASE_FILE": f"storage/database/{copy_path.name}"' in source
    assert "active_backend = launch_backend(port, environment, report)" in source
    assert "cwd=BACKEND" in source
    assert "env=environment" in source
    assert "PYTHONPATH" in source
    assert "shell=False" in source
    assert "cmd /c" not in source.lower()
    assert "activate.bat" not in source.lower()


def test_phase10_execution_diagnostic_success_is_minimal_and_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _execution_diagnostic_module()
    report_dir = tmp_path / "reports"
    database_dir = tmp_path / "database"
    database_dir.mkdir()
    original = database_dir / "original.db"
    original.write_bytes(b"synthetic")
    process = _FakeProcess(pid=123)
    backend_handle = module.BackendHandle(
        process=process,
        port=49101,
        main_pid=process.pid,
        command_category="UVICORN_DIRECT",
        stdout_handle=io.StringIO(),
        stderr_handle=io.StringIO(),
        owned_pids={process.pid},
    )

    monkeypatch.setattr(module, "REPORTS", report_dir)
    monkeypatch.setattr(module, "DATABASE_DIR", database_dir)
    monkeypatch.setattr(module, "ORIGINAL_DB", original)
    monkeypatch.setattr(module, "database_counts", lambda path: (1, 2, 3, 3))
    monkeypatch.setattr(
        module,
        "backup_database",
        lambda source, target: target.write_bytes(b"copy"),
    )
    monkeypatch.setattr(module, "_alembic_head", lambda path, environment: None)
    monkeypatch.setattr(module, "free_port", lambda: 49101)
    monkeypatch.setattr(module, "listener_state", lambda port, owners: "free")

    def fake_launch(port, environment, report, *, stage):
        report.add(stage, "PASS", "UVICORN_DIRECT")
        return backend_handle

    monkeypatch.setattr(module, "launch_backend", fake_launch)
    monkeypatch.setattr(
        module,
        "confirm_backend_process_active",
        lambda backend, report, *, stage: report.add(stage, "PASS", "Activo"),
    )

    def fake_listener(backend, report, *, detected_stage, ownership_stage):
        report.add(detected_stage, "PASS", "Detectado")
        report.add(ownership_stage, "PASS", "BACKEND_LISTENER_OWNED")
        backend.state = "listener_owned"

    monkeypatch.setattr(module, "wait_for_backend_listener", fake_listener)

    def fake_health(backend, report, *, stage):
        backend.state = "ready"
        report.add(stage, "PASS", "HTTP 200")

    monkeypatch.setattr(module, "wait_for_backend_health", fake_health)
    monkeypatch.setattr(module, "models_unloaded", lambda port: True)
    monkeypatch.setattr(
        module,
        "_create_and_read_matrix",
        lambda port, report: report.add("CRUD mínimo", "PASS", "HTTP 201/200"),
    )
    monkeypatch.setattr(
        module,
        "stop_backend",
        lambda backend, **kwargs: SimpleNamespace(
            complete=True,
            shutdown_confirmation="DATABASE_ENGINES_DISPOSED",
            sentinel_valid=True,
            sentinel_removed=True,
        ),
    )
    monkeypatch.setattr(module, "wait_for_listener_release", lambda *args: "free")
    monkeypatch.setattr(
        module,
        "probe_temporary_copy_release",
        lambda path: SimpleNamespace(released=True),
    )
    monkeypatch.setattr(
        module,
        "remove_temporary_copy",
        lambda path: SimpleNamespace(removed=True),
    )
    monkeypatch.setattr(module, "report_is_private", lambda content: True)
    assert module.main() == 0
    reports = list(report_dir.glob("phase10_execution_*.md"))
    assert len(reports) == 1
    content = reports[0].read_text(encoding="utf-8")
    assert "COMPLETADO" in content
    assert "synthetic" not in content
    assert "UUID" not in content


def test_phase10_execution_diagnostic_accepts_matrix_201_and_immediate_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _execution_diagnostic_module()
    validator = _validator_module()
    responses = iter(
        (
            validator.HttpResult(
                201,
                {"id": "00000000-0000-0000-0000-000000000001"},
                "NONE",
                True,
            ),
            validator.HttpResult(200, {"matrix": {}}, "NONE", True),
        )
    )
    monkeypatch.setattr(module, "request", lambda *args, **kwargs: next(responses))
    report = module.DiagnosticReport()
    module._create_and_read_matrix(49108, report)
    assert [(name, result) for name, result, _, _ in report.rows] == [
        ("Matriz creada", "PASS"),
        ("Matriz consultada", "PASS"),
    ]


def test_phase10_execution_diagnostic_reports_startup_failure_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _execution_diagnostic_module()
    report_dir = tmp_path / "reports"
    database_dir = tmp_path / "database"
    database_dir.mkdir()
    original = database_dir / "original.db"
    original.write_bytes(b"synthetic")
    removed: list[Path] = []
    process = _FakeProcess(pid=124)
    backend_handle = module.BackendHandle(
        process=process,
        port=49102,
        main_pid=process.pid,
        command_category="UVICORN_DIRECT",
        stdout_handle=io.StringIO(),
        stderr_handle=io.StringIO(),
        owned_pids={process.pid},
    )
    stopped: list[object] = []

    monkeypatch.setattr(module, "REPORTS", report_dir)
    monkeypatch.setattr(module, "DATABASE_DIR", database_dir)
    monkeypatch.setattr(module, "ORIGINAL_DB", original)
    monkeypatch.setattr(module, "database_counts", lambda path: (1, 2, 3, 3))
    monkeypatch.setattr(
        module,
        "backup_database",
        lambda source, target: target.write_bytes(b"copy"),
    )
    monkeypatch.setattr(module, "_alembic_head", lambda path, environment: None)
    monkeypatch.setattr(module, "free_port", lambda: 49102)
    monkeypatch.setattr(module, "listener_state", lambda port, owners: "free")
    monkeypatch.setattr(
        module,
        "launch_backend",
        lambda port, environment, report, *, stage: backend_handle,
    )
    monkeypatch.setattr(
        module,
        "confirm_backend_process_active",
        lambda backend, report, *, stage: report.add(stage, "PASS", "Activo"),
    )
    monkeypatch.setattr(
        module,
        "wait_for_backend_listener",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            module.StageFailure(
                "Propiedad del listener",
                "BACKEND_LISTENER_FOREIGN",
                exception_class="ListenerOwnershipFailure",
            )
        ),
    )

    def fake_stop(backend, **kwargs):
        stopped.append(backend)
        return SimpleNamespace(
            complete=True,
            shutdown_confirmation="DATABASE_ENGINES_DISPOSED",
            sentinel_valid=True,
            sentinel_removed=True,
        )

    monkeypatch.setattr(
        module,
        "stop_backend",
        fake_stop,
    )
    monkeypatch.setattr(module, "wait_for_listener_release", lambda *args: "free")
    monkeypatch.setattr(
        module,
        "probe_temporary_copy_release",
        lambda path: SimpleNamespace(released=True),
    )

    def fake_remove(path: Path):
        removed.append(path)
        return SimpleNamespace(removed=True)

    monkeypatch.setattr(module, "remove_temporary_copy", fake_remove)
    monkeypatch.setattr(module, "report_is_private", lambda content: True)
    assert module.main() == 1
    assert len(removed) == 1
    assert stopped == [backend_handle]
    content = next(report_dir.glob("phase10_execution_*.md")).read_text(
        encoding="utf-8"
    )
    assert "Propiedad del listener | FAIL" in content
    assert "BACKEND_LISTENER_FOREIGN" in content
    assert "Health readiness | BLOCKED" in content
    assert "RuntimeError" not in content


def test_hpn_service_has_no_ai_or_index_dependencies() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "app" / "services" / "hpn_service.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "ModelManager",
        "LocalLLM",
        "EmbeddingService",
        "HybridSearchService",
        "RagCitationService",
        "Chroma",
        "FTS5",
    ):
        assert forbidden not in source
