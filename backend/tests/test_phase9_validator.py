"""Auditoría estática del validador de Fase 9 sin ejecutar modelos ni datos."""

from __future__ import annotations

import runpy
import sqlite3
from json import JSONDecodeError
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_phase9_end_to_end.py"


def _namespace():
    return runpy.run_path(str(SCRIPT), run_name="phase9_validator_audit")


def _answered():
    return {
        "status": "answered",
        "answer": "Afirmación sintética [F1]",
        "retrieved_chunks": 1,
        "context_chunks": 1,
        "context_tokens": 10,
        "requires_professional_review": True,
        "citation_count": 1,
        "citations": [
            {
                "marker": "[F1]",
                "document_id": "00000000-0000-0000-0000-000000000010",
                "document_name": "documento.pdf",
                "document_type": "jurisprudencia",
                "chunk_index": 1,
                "start_page": 1,
                "end_page": 1,
            }
        ],
    }


def _hybrid():
    return {"items": [], "returned": 0}


def _run_stages(namespace, responses, *, metadata_validator=lambda _items: True):
    iterator = iter(responses)

    def requester(*_args, **_kwargs):
        item = next(iterator)
        if isinstance(item, BaseException):
            raise item
        return item

    report = namespace["Report"]()
    try:
        namespace["validate_answered_stages"](
            report,
            8000,
            {"context_size": 4096},
            requester=requester,
            metadata_validator=metadata_validator,
        )
    except namespace["StageFailure"] as failure:
        namespace["record_stage_failure"](report, failure)
    return report


def test_validator_is_offline_not_collected_and_not_executed() -> None:
    namespace = _namespace()
    assert SCRIPT.name == "validate_phase9_end_to_end.py"
    assert namespace["OFFLINE_ENV"] == {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "ANONYMIZED_TELEMETRY": "False",
    }


def test_validator_has_no_rebuild_migration_or_model_download() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "/api/search/semantic/rebuild" not in source
    assert "alembic upgrade" not in source
    assert "alembic downgrade" not in source
    assert "snapshot_download" not in source
    assert "download_models" not in source
    assert "start_backend" in source and "stop_backend" in source


def test_validator_checks_additive_contract_markers_and_coverage() -> None:
    namespace = _namespace()
    valid, markers, covered = namespace["validate_answered_response"](_answered())
    assert valid and markers == covered == 1
    unknown = _answered()
    unknown["answer"] = "Afirmación sintética [F2]"
    assert not namespace["validate_answered_response"](unknown)[0]
    uncovered = _answered()
    uncovered["answer"] = "Afirmación [F1]\n\nOtra afirmación"
    assert not namespace["validate_answered_response"](uncovered)[0]


def test_validator_checks_insufficient_context_without_citations() -> None:
    namespace = _namespace()
    response = {
        "status": "insufficient_context",
        "answer": "Respuesta fija",
        "retrieved_chunks": 0,
        "context_chunks": 0,
        "context_tokens": 0,
        "requires_professional_review": True,
        "citation_count": 0,
        "citations": [],
    }
    assert namespace["validate_insufficient_response"](response)
    response["citation_count"] = 1
    assert not namespace["validate_insufficient_response"](response)


def test_validator_writes_report_atomically_and_rejects_sensitive_report(tmp_path) -> None:
    namespace = _namespace()
    report = namespace["Report"]()
    for name in namespace["REQUIRED_ROWS"]:
        report.add(name, "PASS", "Cantidad segura: 1")
    content = report.render(0)
    target = tmp_path / "phase9_latest.md"
    namespace["atomic_write"](target, content)
    assert target.read_text(encoding="utf-8") == content
    assert not list(tmp_path.glob("*.tmp"))
    assert namespace["validate_report_privacy"](content)
    assert not namespace["validate_report_privacy"]("Fuente concreta [F1]")


def test_validator_report_requires_every_mandatory_row() -> None:
    namespace = _namespace()
    report = namespace["Report"]()
    for name in namespace["REQUIRED_ROWS"]:
        report.add(name, "PASS", "metadato seguro")
    assert report.passed
    report.rows.pop()
    assert not report.passed


def test_validator_normalizes_uuid_for_sqlite_metadata_validation(tmp_path) -> None:
    namespace = _namespace()
    database_dir = tmp_path / "storage" / "database"
    database_dir.mkdir(parents=True)
    database = database_dir / "asistente_juridico.db"
    document_hex = "00000000000000000000000000000010"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE documents (id TEXT, original_filename TEXT, "
            "document_type TEXT, is_deleted INTEGER)"
        )
        connection.execute(
            "CREATE TABLE document_chunks (document_id TEXT, chunk_index INTEGER, "
            "start_page INTEGER, end_page INTEGER)"
        )
        connection.execute(
            "INSERT INTO documents VALUES (?, ?, ?, 0)",
            (document_hex, "documento.pdf", "jurisprudencia"),
        )
        connection.execute(
            "INSERT INTO document_chunks VALUES (?, 1, 2, 3)",
            (document_hex,),
        )
    namespace["validate_sqlite_metadata"].__globals__["ROOT"] = tmp_path
    assert namespace["validate_sqlite_metadata"](
        [
            {
                "document_id": "00000000-0000-0000-0000-000000000010",
                "document_name": "documento.pdf",
                "document_type": "jurisprudencia",
                "chunk_index": 1,
                "start_page": 2,
                "end_page": 3,
            }
        ]
    )


def test_validator_cleans_up_before_atomic_report_and_has_no_pipe_capture() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert source.index("cleanup_started") < source.index("timestamp =")
    assert source.index("timestamp =") < source.rindex("atomic_write(")
    namespace = _namespace()
    start_source = namespace["start_backend"].__code__.co_names
    assert "PIPE" not in start_source


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (500, "RAG_CITATION_OUTPUT_INVALID"),
        (409, "RAG_CITATION_SOURCE_STALE"),
        (500, "RAG_CITATION_METADATA_INVALID"),
        (503, "RAG_LLM_NOT_LOADED"),
        (503, "HYBRID_SEARCH_UNAVAILABLE"),
    ],
)
def test_validator_records_http_stage_and_stable_code(status, code) -> None:
    namespace = _namespace()
    report = _run_stages(
        namespace,
        [(200, _hybrid()), (status, {"detail": code})],
    )
    failure = next(row for row in report.rows if row[1] == "FAIL")
    assert failure[0] == "Chat RAG HTTP"
    assert failure[2] == (
        f"HTTP {status}; {code}; reason UNKNOWN_SAFE_REASON; HTTPError"
    )
    assert all(row[0] != "Validación" for row in report.rows)
    assert any(row[0] == "Estado answered" and row[1] == "BLOCKED" for row in report.rows)


def test_validator_handles_non_json_and_json_without_stable_code() -> None:
    namespace = _namespace()
    non_json = _run_stages(
        namespace,
        [(200, _hybrid()), JSONDecodeError("sensitive", "private body", 0)],
    )
    failure = next(row for row in non_json.rows if row[1] == "FAIL")
    assert failure[:3] == (
        "Chat RAG HTTP",
        "FAIL",
        "reason UNKNOWN_SAFE_REASON; JSONDecodeError",
    )
    assert "private body" not in non_json.render(1)

    free_detail = "contenido privado que no es un código"
    no_code = _run_stages(
        namespace,
        [(200, _hybrid()), (500, {"detail": free_detail})],
    )
    failure = next(row for row in no_code.rows if row[1] == "FAIL")
    assert failure[2] == "HTTP 500; reason UNKNOWN_SAFE_REASON; HTTPError"
    assert free_detail not in no_code.render(1)


def test_validator_preserves_safe_reason_and_application_stage() -> None:
    namespace = _namespace()
    report = _run_stages(
        namespace,
        [
            (200, _hybrid()),
            (
                500,
                {
                    "detail": {
                        "error_code": "RAG_CITATION_OUTPUT_INVALID",
                        "reason_code": "CITATION_UNCITED_SUBSTANTIVE_ELEMENT",
                        "stage": "citation_validation",
                    }
                },
            ),
        ],
    )
    failure = next(row for row in report.rows if row[1] == "FAIL")
    assert failure[:3] == (
        "Chat RAG HTTP",
        "FAIL",
        "HTTP 500; RAG_CITATION_OUTPUT_INVALID; "
        "reason CITATION_UNCITED_SUBSTANTIVE_ELEMENT; "
        "stage citation_validation; HTTPError",
    )


def test_validator_records_exception_before_http_request() -> None:
    namespace = _namespace()
    report = _run_stages(namespace, [ConnectionError("private")])
    failure = next(row for row in report.rows if row[1] == "FAIL")
    assert failure[:3] == ("Recuperación híbrida", "FAIL", "ConnectionError")
    assert "private" not in report.render(1)


def test_validator_records_exact_marker_stage_and_blocks_later(monkeypatch) -> None:
    namespace = _namespace()
    function = namespace["validate_answered_stages"]
    monkeypatch.setitem(
        function.__globals__,
        "validate_marker_correspondence",
        lambda _response: (_ for _ in ()).throw(ValueError("private answer")),
    )
    report = _run_stages(namespace, [(200, _hybrid()), (200, _answered())])
    failure = next(row for row in report.rows if row[1] == "FAIL")
    assert failure[:3] == (
        "Correspondencia markers-citations",
        "FAIL",
        "RAG_CITATION_OUTPUT_INVALID; ValueError",
    )
    assert any(row[0] == "Metadata SQLite" and row[1] == "BLOCKED" for row in report.rows)
    assert "private answer" not in report.render(1)


def test_validator_records_exact_sqlite_metadata_stage() -> None:
    namespace = _namespace()

    def fail_metadata(_citations):
        raise sqlite3.DatabaseError("private sql")

    report = _run_stages(
        namespace,
        [(200, _hybrid()), (200, _answered())],
        metadata_validator=fail_metadata,
    )
    failure = next(row for row in report.rows if row[1] == "FAIL")
    assert failure[:3] == (
        "Metadata SQLite",
        "FAIL",
        "RAG_CITATION_METADATA_INVALID; DatabaseError",
    )
    assert "private sql" not in report.render(1)


def test_validator_records_exact_coverage_stage(monkeypatch) -> None:
    namespace = _namespace()
    function = namespace["validate_coverage"]
    monkeypatch.setitem(
        function.__globals__,
        "_substantive_elements",
        lambda _answer: (_ for _ in ()).throw(RuntimeError("private text")),
    )
    report = _run_stages(namespace, [(200, _hybrid()), (200, _answered())])
    failure = next(row for row in report.rows if row[1] == "FAIL")
    assert failure[:3] == (
        "Cobertura",
        "FAIL",
        "RAG_CITATION_OUTPUT_INVALID; RuntimeError",
    )
    assert "private text" not in report.render(1)


def test_validator_budget_formula_uses_prompt_tokens_and_rejects_overflow() -> None:
    validate = _namespace()["validate_budget_values"]
    values = {
        "context_size": 100,
        "context_tokens": 20,
        "max_new_tokens": 20,
        "safety_margin": 10,
        "context_chunks": 2,
        "source_count": 2,
    }
    assert validate(prompt_tokens=70, **values)
    assert not validate(prompt_tokens=71, **values)
    assert not validate(prompt_tokens=10, **values)


def test_failed_report_is_sanitized_atomic_and_globally_failed(tmp_path) -> None:
    namespace = _namespace()
    report = _run_stages(
        namespace,
        [(200, _hybrid()), (500, {"detail": "RAG_CITATION_OUTPUT_INVALID"})],
    )
    report.add("Descarga final de modelos", "PASS", "Modelos unloaded")
    report.add("Integridad SQLite", "PASS", "Conteos iguales")
    report.add("Puertos", "PASS", "Liberados")
    report.add("Finalización y limpieza", "PASS", "Limpieza ejecutada")
    content = report.render(1)
    destination = tmp_path / "phase9_failed.md"
    namespace["atomic_write"](destination, content)
    assert not report.passed
    assert "VALIDACIÓN FASE 9: FALLIDA" in content
    assert (
        "Chat RAG HTTP | FAIL | HTTP 500; RAG_CITATION_OUTPUT_INVALID; "
        "reason UNKNOWN_SAFE_REASON" in content
    )
    assert "| Validación | FAIL |" not in content
    assert namespace["validate_report_privacy"](content)
    assert destination.read_text(encoding="utf-8") == content
    assert not list(tmp_path.glob("*.tmp"))
