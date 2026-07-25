"""Auditoría estática del validador de Fase 8 sin ejecutar su flujo real."""

from __future__ import annotations

import runpy
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_phase8_end_to_end.py"


def _namespace():
    return runpy.run_path(str(SCRIPT), run_name="phase8_validator_audit")


def test_validator_is_not_collected_or_executed_and_uses_offline_environment() -> None:
    namespace = _namespace()
    assert SCRIPT.name.startswith("validate_")
    assert namespace["OFFLINE_ENV"] == {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "ANONYMIZED_TELEMETRY": "False",
    }


def test_validator_privacy_checks_keys_without_content_false_positives() -> None:
    namespace = _namespace()
    forbidden = namespace["forbidden_payload"]
    assert forbidden({"question": "privada"})
    assert forbidden({"items": [{"embedding": [0.0]}]})
    assert not forbidden(
        {
            "status": "answered",
            "answer": "Palabras context y vector usadas como lenguaje normal",
            "context_tokens": 10,
        }
    )
    assert namespace["validate_public_response"](
        {
            "status": "answered",
            "answer": "Palabras legítimas",
            "retrieved_chunks": 1,
            "context_chunks": 1,
            "context_tokens": 3,
            "requires_professional_review": True,
        }
    )
    assert not namespace["validate_public_response"](
        {
            "status": "answered",
            "answer": "x",
            "retrieved_chunks": 1,
            "context_chunks": 1,
            "context_tokens": 3,
            "requires_professional_review": True,
            "question": "prohibida",
        }
    )
    unsafe = {
        "status": "answered",
        "answer": "<script>alert(1)</script>",
        "retrieved_chunks": 1,
        "context_chunks": 1,
        "context_tokens": 3,
        "requires_professional_review": True,
    }
    assert not namespace["validate_public_response"](unsafe)


def test_validator_atomic_report_replaces_latest_without_leaking_content(tmp_path) -> None:
    namespace = _namespace()
    atomic_write = namespace["atomic_write"]
    report_type = namespace["Report"]
    destination = tmp_path / "phase8_latest.md"
    report = report_type()
    report.add("Privacidad", "PASS", "Sin contenido sensible")
    content = report.render(0)
    atomic_write(destination, content)
    assert destination.read_text(encoding="utf-8") == content
    assert not list(tmp_path.glob("*.tmp"))
    for secret in ("question", "prompt", "snippet", "chunk_id"):
        assert secret not in content


def test_validator_source_has_no_rebuild_or_migration_commands() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "/api/search/semantic/rebuild" not in source
    assert "alembic upgrade" not in source
    assert "alembic downgrade" not in source
    assert '"--workers", "1"' in source
    assert "unload_models(active_port)" in source
    assert "sqlite_counts()" in source


def test_required_rows_and_global_report_status() -> None:
    namespace = _namespace()
    report = namespace["Report"]()
    required = namespace["REQUIRED_ROWS"]
    for name in required:
        report.add(name, "PASS", "metadato seguro")
    assert report.passed
    assert "VALIDACIÓN FASE 8: APROBADA" in report.render(0)
    missing = namespace["Report"]()
    for name in required - {"Privacidad"}:
        missing.add(name, "PASS", "metadato seguro")
    assert not missing.passed
    assert "VALIDACIÓN FASE 8: FALLIDA" in missing.render(1)


def test_budget_exact_limit_and_one_token_over() -> None:
    validate = _namespace()["validate_budget"]
    common = {
        "context_size": 100,
        "context_tokens": 10,
        "max_new_tokens": 20,
        "safety_margin": 5,
        "context_chunks": 1,
    }
    assert validate(prompt_tokens=75, **common)
    assert not validate(prompt_tokens=76, **common)


def test_sqlite_counts_comparison_and_final_model_state(monkeypatch) -> None:
    namespace = _namespace()
    assert namespace["counts_equal"]((1, 2, 3, 4), (1, 2, 3, 4))
    assert not namespace["counts_equal"]((1, 2, 3, 4), (1, 2, 3, 5))
    responses = {
        "/api/models/status": (200, {"model": {"installed": True, "verified": True}}),
        "/api/models/llm/status": (200, {"state": "unloaded"}),
        "/api/models/embeddings/status": (200, {"state": "unloaded", "local_files_available": True}),
    }
    namespace["final_models_unloaded"].__globals__["request_json"] = (
        lambda _port, _method, endpoint, **_kwargs: responses[endpoint]
    )
    assert namespace["final_models_unloaded"](123)
    responses["/api/models/llm/status"] = (200, {"state": "loaded"})
    assert not namespace["final_models_unloaded"](123)


def test_pending_thread_detection_and_report_write_order(tmp_path) -> None:
    namespace = _namespace()
    assert not namespace["has_pending_threads"]()
    report = namespace["Report"]()
    report.add("Pytest", "PASS", "ok")
    target = tmp_path / "report.md"
    namespace["atomic_write"](target, report.render(1))
    assert target.is_file()
    assert target.read_text(encoding="utf-8").endswith("Código de salida: 1\n")
