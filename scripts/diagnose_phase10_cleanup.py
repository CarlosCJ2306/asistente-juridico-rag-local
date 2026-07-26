"""Diagnóstico limitado para eliminar copias residuales propias de Fase 10.

No inicia el backend, no aplica migraciones y no abre SQLite.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from validate_phase10_end_to_end import (
    DATABASE_DIR,
    REPORTS,
    SIDECAR_SUFFIXES,
    _owned_copy_path,
    atomic_write,
    probe_temporary_copy_release,
    remove_temporary_copy,
)


@dataclass
class CleanupReport:
    rows: list[tuple[str, str, str]] = field(default_factory=list)

    def add(self, name: str, result: str, detail: str) -> None:
        self.rows.append((name, result, detail))

    def render(self, exit_code: int) -> str:
        lines = [
            "# Diagnóstico de limpieza de Fase 10",
            "",
            f"Fecha: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "| Validación | Resultado | Detalle seguro |",
            "|---|---|---|",
            *(f"| {name} | {result} | {detail} |" for name, result, detail in self.rows),
            "",
            f"DIAGNÓSTICO LIMPIEZA FASE 10: {'COMPLETADO' if exit_code == 0 else 'FALLIDO'}",
            f"Código de salida: {exit_code}",
            "",
        ]
        return "\n".join(lines)


def own_process_ids() -> set[int]:
    """Localiza procesos del validador o Uvicorn sin divulgar sus PIDs."""

    if os.name != "nt":
        return set()
    command = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match '^python' -and "
        "($_.CommandLine -match 'validate_phase10_end_to_end.py' "
        "-or $_.CommandLine -match 'uvicorn app.main:app') } | "
        "Select-Object -ExpandProperty ProcessId"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return {
        int(line.strip())
        for line in completed.stdout.splitlines()
        if line.strip().isdigit() and int(line.strip()) != os.getpid()
    }


def listening_process_ids() -> set[int]:
    if os.name != "nt":
        return set()
    completed = subprocess.run(
        ["netstat", "-ano", "-p", "TCP"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    listeners: set[int] = set()
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
            try:
                listeners.add(int(parts[4]))
            except ValueError:
                continue
    return listeners


def residual_copies() -> list[Path]:
    return sorted(
        path
        for path in DATABASE_DIR.glob(".phase10_*.db")
        if _owned_copy_path(path) and not path.is_symlink()
    )


def sidecar_count(copies: list[Path]) -> int:
    return sum(
        copy.with_name(copy.name + suffix).is_file()
        for copy in copies
        for suffix in SIDECAR_SUFFIXES
    )


def main() -> int:
    report = CleanupReport()
    started = time.perf_counter()
    exit_code = 1
    copies = residual_copies()
    processes = own_process_ids()
    own_listeners = listening_process_ids() & processes
    report.add("Copias residuales", "PASS", f"Cantidad: {len(copies)}")
    report.add("Sidecars", "PASS", f"Cantidad: {sidecar_count(copies)}")
    report.add(
        "Procesos propios",
        "PASS" if not processes else "FAIL",
        "Inactivos" if not processes else "Activos",
    )
    report.add(
        "Listeners propios",
        "PASS" if not own_listeners else "FAIL",
        "Ausentes" if not own_listeners else "Presentes",
    )
    if not processes and not own_listeners:
        probes = [probe_temporary_copy_release(copy) for copy in copies]
        probes_ok = all(probe.released for probe in probes)
        report.add(
            "Rename probe",
            "PASS" if probes_ok else "FAIL",
            "Copias liberadas" if probes_ok else "Bloqueo detectado",
        )
        removals = (
            [remove_temporary_copy(copy) for copy in copies] if probes_ok else []
        )
        removed = probes_ok and all(result.removed for result in removals)
        attempts = sum(result.attempts for result in removals)
        report.add(
            "Eliminación",
            "PASS" if removed else "FAIL",
            f"Intentos: {attempts}" if removed else "Copias conservadas",
        )
        absent = not residual_copies()
        report.add(
            "Verificación final",
            "PASS" if absent else "FAIL",
            "Sin copias residuales" if absent else "Persisten copias",
        )
        exit_code = 0 if removed and absent else 1
    else:
        report.add("Rename probe", "FAIL", "Bloqueado por proceso propio")
        report.add("Eliminación", "FAIL", "No iniciada")
        report.add("Verificación final", "FAIL", "Limpieza no iniciada")
    report.add("Duración", "PASS", f"Segundos: {time.perf_counter() - started:.2f}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    atomic_write(REPORTS / f"phase10_cleanup_{timestamp}.md", report.render(exit_code))
    print(
        "DIAGNÓSTICO LIMPIEZA FASE 10: "
        f"{'COMPLETADO' if exit_code == 0 else 'FALLIDO'}"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
