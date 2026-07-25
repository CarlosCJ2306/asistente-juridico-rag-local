"""Pruebas unitarias del validador de Fase 7 sin procesos ni datos reales."""

from __future__ import annotations

import runpy
import subprocess
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_phase7_end_to_end.py"
VALIDATOR = runpy.run_path(str(SCRIPT), run_name="phase7_validator_tests")


class FakeStream:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeProcess:
    def __init__(self, *, needs_kill: bool = False) -> None:
        self.needs_kill = needs_kill
        self.terminated = False
        self.killed = False
        self.wait_calls = 0
        self.stdout = FakeStream()
        self.stderr = FakeStream()
        self.stdin = FakeStream()

    def poll(self):
        return 0 if self.killed or (self.terminated and not self.needs_kill) else None

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout=None) -> None:
        self.wait_calls += 1
        if self.needs_kill and not self.killed:
            raise subprocess.TimeoutExpired("uvicorn", timeout)


def test_stop_backend_normal_process_closes_handles_and_waits_port(monkeypatch) -> None:
    process = FakeProcess()
    released: list[int] = []
    monkeypatch.setitem(
        VALIDATOR["stop_backend"].__globals__,
        "wait_port_released",
        lambda port: released.append(port),
    )

    VALIDATOR["stop_backend"](process, port=8123)

    assert process.terminated and not process.killed
    assert process.wait_calls == 1
    assert process.stdout.closed and process.stderr.closed and process.stdin.closed
    assert released == [8123]


def test_stop_backend_forces_kill_when_terminate_times_out(monkeypatch) -> None:
    process = FakeProcess(needs_kill=True)
    monkeypatch.setitem(
        VALIDATOR["stop_backend"].__globals__, "wait_port_released", lambda _port: None
    )

    VALIDATOR["stop_backend"](process, port=8124)

    assert process.terminated and process.killed
    assert process.wait_calls == 2


def test_wait_port_released_retries_with_backoff(monkeypatch) -> None:
    states = iter([True, True, False])
    monkeypatch.setitem(
        VALIDATOR["wait_port_released"].__globals__,
        "port_accepts_connections",
        lambda _port: next(states),
    )
    monkeypatch.setattr(VALIDATOR["time"], "sleep", lambda _delay: None)

    VALIDATOR["wait_port_released"](8125, timeout=1)


def test_select_free_port_excludes_requested_port() -> None:
    selected = VALIDATOR["select_free_port"](excluded={8000})
    assert selected != 8000 and selected > 0


def test_second_start_retries_with_alternative_port(monkeypatch) -> None:
    process = FakeProcess()
    attempts = iter([OSError("occupied"), process])
    selected: list[set[int]] = []

    def fake_start(port):
        value = next(attempts)
        if isinstance(value, Exception):
            raise value
        return value

    def fake_select_free_port(*, excluded):
        selected.append(set(excluded))
        return 8126

    monkeypatch.setitem(
        VALIDATOR["start_backend_with_retries"].__globals__, "start_backend", fake_start
    )
    monkeypatch.setitem(
        VALIDATOR["start_backend_with_retries"].__globals__,
        "select_free_port",
        fake_select_free_port,
    )
    result, port = VALIDATOR["start_backend_with_retries"](8000, excluded_ports={8000})

    assert result is process and port == 8126
    assert selected == [{8000}]


def test_static_checks_run_all_commands_after_one_failure(monkeypatch) -> None:
    report = VALIDATOR["Report"]()
    results = iter(
        [
            SimpleNamespace(returncode=1, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
        ]
    )
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return next(results)

    monkeypatch.setattr(VALIDATOR["subprocess"], "run", fake_run)
    VALIDATOR["run_static_checks"](report)

    assert len(calls) == 3
    assert [row.result for row in report.rows] == ["FAIL", "PASS", "PASS"]


def test_report_atomic_write_and_outcome_are_sanitized(tmp_path: Path) -> None:
    report = VALIDATOR["Report"]()
    report.add("Prueba", "PASS", "vector legítimo | ruta absoluta", 0.0)
    target = tmp_path / "phase7.md"
    VALIDATOR["atomic_write"](target, report.render())
    content = target.read_text(encoding="utf-8")
    assert "Resultado global: **PASS**" not in content
    assert "VALIDACIÓN FASE 7: APROBADA" in content
    assert target.exists()


def test_close_process_tree_is_only_called_for_running_timeout(monkeypatch) -> None:
    process = FakeProcess(needs_kill=True)
    called: list[int] = []
    monkeypatch.setitem(
        VALIDATOR["stop_backend"].__globals__,
        "_terminate_process_tree",
        lambda value: called.append(value.pid),
    )
    monkeypatch.setattr(process, "poll", lambda: None)
    process.pid = 12345
    monkeypatch.setitem(
        VALIDATOR["stop_backend"].__globals__, "wait_port_released", lambda _port: None
    )
    # The fake reaches the kill path and then reports termination normally.
    process.poll = lambda: 0 if process.killed else None
    VALIDATOR["stop_backend"](process, port=8127)
    assert called == []
