"""Pruebas sintéticas del diagnóstico limitado de citas de Fase 9."""

from __future__ import annotations

import runpy
import json
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "diagnose_phase9_citation_output.py"
)


def _namespace():
    return runpy.run_path(str(SCRIPT), run_name="phase9_diagnostic_audit")


def _safe_error_payload(reason_code="CITATION_UNCITED_SUBSTANTIVE_ELEMENT"):
    return {
        "detail": {
            "error_code": "RAG_CITATION_OUTPUT_INVALID",
            "reason_code": reason_code,
            "stage": "citation_validation",
        },
        "answer": "contenido que nunca debe conservarse",
    }


def test_diagnostic_is_not_collected_and_does_not_run_full_validation() -> None:
    namespace = _namespace()
    source = SCRIPT.read_text(encoding="utf-8")
    assert SCRIPT.name == "diagnose_phase9_citation_output.py"
    assert namespace["OFFLINE_ENV"]["HF_HUB_OFFLINE"] == "1"
    assert "python -m pytest" not in source
    assert "ruff check" not in source
    assert "mypy app" not in source
    assert source.count('"/api/chat/rag"') == 1
    assert "/api/search/semantic/rebuild" not in source


def test_http_500_with_safe_reason_completes_diagnosis() -> None:
    namespace = _namespace()
    outcome = namespace["evaluate_chat_result"](
        500,
        _safe_error_payload(),
        namespace["SafeOperationalMetrics"]("stop", 12, 3),
    )
    assert outcome.completed
    assert outcome.functional_result == "RECHAZADO"
    assert outcome.error_code == "RAG_CITATION_OUTPUT_INVALID"
    assert outcome.reason_code == "CITATION_UNCITED_SUBSTANTIVE_ELEMENT"
    assert outcome.stage == "citation_validation"
    assert outcome.finish_reason == "stop"
    assert outcome.generated_token_count == 12
    assert outcome.citation_source_count == 3


def test_http_error_without_safe_reason_fails_diagnosis() -> None:
    outcome = _namespace()["evaluate_chat_result"](
        500, {"detail": "RAG_CITATION_OUTPUT_INVALID"}
    )
    assert not outcome.completed
    assert outcome.functional_result == "INDETERMINADO"
    assert outcome.reason_code == "UNKNOWN_SAFE_REASON"


def test_answered_result_keeps_only_safe_counts() -> None:
    outcome = _namespace()["evaluate_chat_result"](
        200,
        {
            "status": "answered",
            "retrieved_chunks": 3,
            "context_chunks": 2,
            "citation_count": 2,
            "answer": "contenido privado",
            "citations": ["metadata privada"],
        },
    )
    assert outcome.completed and outcome.functional_result == "ANSWERED"
    assert outcome.retrieved_chunks == 3
    assert outcome.context_chunks == outcome.citation_count == 2
    assert "contenido privado" not in repr(outcome)


def test_diagnostic_preserves_closed_finish_reasons_and_optional_token_count() -> None:
    namespace = _namespace()
    metrics_type = namespace["SafeOperationalMetrics"]
    evaluate = namespace["evaluate_chat_result"]
    for reason in ("stop", "length", "unknown"):
        outcome = evaluate(
            500,
            _safe_error_payload(),
            metrics_type(reason, 5, 2),
        )
        assert outcome.finish_reason == reason
        assert outcome.generated_token_count == 5
    unavailable = evaluate(500, _safe_error_payload(), metrics_type("stop", None, 2))
    assert unavailable.generated_token_count is None


def test_safe_log_reader_extracts_only_aggregate_metrics(tmp_path) -> None:
    namespace = _namespace()
    reader = namespace["read_safe_operational_metrics"]
    reader.__globals__["ROOT"] = tmp_path
    logs = tmp_path / "storage" / "logs"
    logs.mkdir(parents=True)
    log_file = logs / "asistente_juridico_backend.log"
    first = "línea previa\n"
    log_file.write_text(first, encoding="utf-8")
    contexts = [
        {
            "finish_reason": "length",
            "generated_count": 11,
            "answer": "contenido privado ignorado",
        },
        {
            "operation": "rag_chat_citations",
            "total_sources": 3,
            "document_id": "identificador privado ignorado",
        },
    ]
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(
            "Generación local completada | context="
            + json.dumps(contexts[0], ensure_ascii=False)
            + "\n"
        )
        handle.write(
            "Fallo estructural | context="
            + json.dumps(contexts[1], ensure_ascii=False)
            + "\n"
        )
    metrics = reader(len(first.encode("utf-8")))
    assert metrics.finish_reason == "length"
    assert metrics.generated_token_count == 11
    assert metrics.citation_source_count == 3
    assert "contenido privado" not in repr(metrics)
    assert "identificador privado" not in repr(metrics)


def test_execute_diagnostic_report_never_includes_rejected_content() -> None:
    namespace = _namespace()
    responses = iter(
        [
            (200, {"state": "unloaded"}),
            (200, {"state": "unloaded"}),
            (200, {"state": "ready", "needs_rebuild": False}),
            (200, {"state": "loaded"}),
            (200, {"state": "loaded"}),
            (500, _safe_error_payload()),
        ]
    )

    def requester(*_args, **_kwargs):
        return next(responses)

    report = namespace["DiagnosticReport"]()
    outcome = namespace["execute_diagnostic"](
        report,
        8000,
        requester=requester,
        fts_checker=lambda: True,
        offset_getter=lambda: 0,
        metrics_reader=lambda _offset: namespace["SafeOperationalMetrics"](
            "length", 14, 3
        ),
    )
    content = report.render(
        exit_code=0,
        completed=outcome.completed,
        functional_result=outcome.functional_result,
    )
    assert outcome.completed
    assert "contenido que nunca debe conservarse" not in content
    assert "CITATION_UNCITED_SUBSTANTIVE_ELEMENT" in content
    assert "finish_reason length" in content
    assert "generated_token_count 14" in content
    assert "fuentes 3" in content


def test_cleanup_unloads_models_and_releases_port() -> None:
    namespace = _namespace()
    calls: list[str] = []

    def requester(_port, _method, endpoint, _payload, **_kwargs):
        calls.append(endpoint)
        return 200, {"state": "unloaded"}

    report = namespace["DiagnosticReport"]()
    cleaned = namespace["cleanup_runtime"](
        report,
        object(),
        8000,
        requester=requester,
        stopper=lambda _process, _port: True,
        port_checker=lambda _port: True,
    )
    assert cleaned
    assert calls == ["/api/models/llm/unload", "/api/models/embeddings/unload"]
    assert any(row[:2] == ("Estado final de modelos", "PASS") for row in report.rows)
    assert any(row[:2] == ("Puerto", "PASS") for row in report.rows)


def test_main_executes_cleanup_and_atomic_report_after_exception(tmp_path, monkeypatch) -> None:
    namespace = _namespace()
    main = namespace["main"]
    globals_ = main.__globals__
    cleanup_calls: list[bool] = []
    monkeypatch.setitem(globals_, "REPORTS", tmp_path)
    monkeypatch.setitem(globals_, "free_port", lambda: 8000)
    monkeypatch.setitem(globals_, "start_backend", lambda _port: object())

    def fail_execute(*_args, **_kwargs):
        raise RuntimeError("contenido privado")

    def clean(*_args, **_kwargs):
        cleanup_calls.append(True)
        return True

    monkeypatch.setitem(globals_, "execute_diagnostic", fail_execute)
    monkeypatch.setitem(globals_, "cleanup_runtime", clean)
    assert main() == 1
    assert cleanup_calls == [True]
    reports = list(tmp_path.glob("phase9_diagnostic_*.md"))
    assert len(reports) == 1
    content = reports[0].read_text(encoding="utf-8")
    assert "DIAGNÓSTICO COMPLETADO: NO" in content
    assert "contenido privado" not in content
    assert not list(tmp_path.glob("*.tmp"))
