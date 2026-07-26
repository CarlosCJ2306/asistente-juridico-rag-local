"""Pruebas sintéticas de citas y trazabilidad de la Fase 9."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import replace
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.api.routes.chat import _rag_http_error
from app.core.config import Settings
from app.database.models.document import DocumentType
from app.database.repositories.semantic_chunk_repository import ActiveChunk
from app.schemas.rag_chat import RagChatResponse, RagCitation
from app.schemas.hybrid_search import HybridSearchItem, HybridSearchResponse
from app.schemas.rag_chat import RagChatRequest
from app.services import rag_chat_service as chat_module
from app.services.rag_citation_service import (
    CITATION_REASON_CODES,
    CitationSource,
    RagCitationError,
    RagCitationService,
)
from app.services.rag_chat_service import RagChatError, RagChatService
from app.services.rag_prompt_service import RagPromptService


def _chunk(
    index: int,
    *,
    document_id: int = 10,
    name: str = "sentencia-sintetica.pdf",
    text: str = "Contenido sintético con Unicode: acción y niñez.",
) -> ActiveChunk:
    return ActiveChunk(
        chunk_id=UUID(int=100 + index),
        document_id=UUID(int=document_id),
        document_type=DocumentType.JURISPRUDENCIA,
        chunk_index=index,
        text=text,
        start_page=index,
        end_page=index + 1,
        document_name=name,
    )


class FakeRepository:
    def __init__(self, chunks: list[ActiveChunk]) -> None:
        self.chunks = {chunk.chunk_id: chunk for chunk in chunks}
        self.calls: list[list[UUID]] = []

    async def get_active_by_ids(self, chunk_ids: list[UUID]):
        self.calls.append(chunk_ids)
        return {
            chunk_id: self.chunks[chunk_id]
            for chunk_id in chunk_ids
            if chunk_id in self.chunks
        }


def _prompt(divisor: int = 10) -> RagPromptService:
    def count(text: str) -> int:
        return max(1, len(text.encode("utf-8")) // divisor)

    def count_chat(messages) -> int:
        return sum(count(message["content"]) for message in messages) + 20

    def truncate(text: str, limit: int) -> str:
        return text.encode("utf-8")[: limit * divisor].decode("utf-8", errors="ignore")

    return RagPromptService(count, count_chat, truncate)


@pytest.mark.parametrize(
    "overrides",
    [
        {"rag_citation_max_sources": 0},
        {"rag_citation_max_sources": -1},
        {"rag_citation_max_sources": True},
        {"rag_source_name_max_length": 0},
        {"rag_source_name_max_length": True},
        {"rag_citation_max_sources": 9, "rag_context_max_chunks": 8},
    ],
)
def test_citation_settings_reject_invalid_values(overrides) -> None:
    with pytest.raises(ValidationError):
        Settings(**overrides)


def test_registry_assigns_markers_in_order_and_deduplicates_chunks() -> None:
    service = RagCitationService()
    first, second, third = _chunk(1), _chunk(2), _chunk(3)
    registry = service.build_registry((first, second, first, third))
    assert [source.marker for source in registry.sources] == ["[F1]", "[F2]", "[F3]"]
    assert [source.chunk_id for source in registry.sources] == [
        first.chunk_id,
        second.chunk_id,
        third.chunk_id,
    ]
    assert service.build_registry(()).sources == ()


def test_registry_identity_does_not_depend_on_document_name() -> None:
    service = RagCitationService()
    registry = service.build_registry(
        (_chunk(1, document_id=10, name="igual.pdf"), _chunk(2, document_id=20, name="igual.pdf"))
    )
    assert len(registry.sources) == 2
    assert registry.sources[0].document_id != registry.sources[1].document_id


def test_registries_are_request_local_and_restart_at_f1() -> None:
    service = RagCitationService()
    first_request = service.build_registry((_chunk(1), _chunk(2)))
    second_request = service.build_registry((_chunk(3),))
    assert [source.marker for source in first_request.sources] == ["[F1]", "[F2]"]
    assert [source.marker for source in second_request.sources] == ["[F1]"]
    assert first_request is not second_request


def test_distinct_chunks_from_same_document_remain_separate_sources() -> None:
    registry = RagCitationService().build_registry((_chunk(1), _chunk(2)))
    assert len(registry.sources) == 2
    assert registry.sources[0].document_id == registry.sources[1].document_id
    assert registry.sources[0].chunk_id != registry.sources[1].chunk_id


@pytest.mark.parametrize(
    "invalid",
    [
        replace(_chunk(1), chunk_index=0),
        replace(_chunk(1), start_page=0),
        replace(_chunk(1), end_page=0),
        replace(_chunk(1), text=""),
    ],
)
def test_registry_rejects_invalid_internal_metadata(invalid) -> None:
    with pytest.raises(RagCitationError, match="RAG_CITATION_METADATA_INVALID"):
        RagCitationService().build_registry((invalid,))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("sentencia.pdf", "sentencia.pdf"),
        ("acción-niñez.pdf", "acción-niñez.pdf"),
        (r"C:\privado\sentencia.pdf", "sentencia.pdf"),
        ("/privado/sentencia.pdf", "sentencia.pdf"),
        ("mal\x00nombre.pdf", "malnombre.pdf"),
        ("", "documento.pdf"),
        (None, "documento.pdf"),
        ("..", "documento.pdf"),
        ("<script>.pdf", "&lt;script&gt;.pdf"),
        ("../../sentencia.pdf", "sentencia.pdf"),
        ("carpeta/subcarpeta/documento.pdf", "documento.pdf"),
        (r"..\..\documento.pdf", "documento.pdf"),
        ("solo-nombre", "solo-nombre"),
        ("[F1]-documento.pdf", "［F1］-documento.pdf"),
    ],
)
def test_document_name_is_sanitized(value, expected) -> None:
    assert RagCitationService.sanitize_document_name(value) == expected


def test_document_name_controls_and_length_are_bounded(monkeypatch) -> None:
    monkeypatch.setattr(chat_module.settings, "rag_source_name_max_length", 12)
    value = RagCitationService.sanitize_document_name("abc\n\tdefghijklmnop.pdf")
    assert len(value) <= 12
    assert "\n" not in value and "\t" not in value


def test_document_name_with_html_closing_tag_cannot_remain_executable() -> None:
    value = RagCitationService.sanitize_document_name(
        "<script>alert(1)</script>.pdf"
    )
    assert "/" not in value and "\\" not in value
    assert "<script" not in value.casefold()
    assert value.endswith(".pdf")


def test_prompt_assigns_real_markers_and_neutralizes_injected_markers() -> None:
    prompt = _prompt()
    chunk = _chunk(1, text="Dato [F1] [f 99] [Fuente 2] y acción jurídica.")
    selected = prompt.select_context("Pregunta [F9]", [chunk])
    messages = prompt.build_messages("Pregunta [F9]", selected)
    assert [message["role"] for message in messages] == ["system", "user"]
    assert messages[1]["content"].count('/no_think') == 1
    assert messages[1]["content"].count('id="[F1]"') == 1
    assert "［F1］" in messages[1]["content"]
    assert "［f 99］" in messages[1]["content"]
    assert "［Fuente 2］" in messages[1]["content"]
    assert "［F9］" in messages[1]["content"]
    assert "acción jurídica" in messages[1]["content"]
    assert str(chunk.chunk_id) not in messages[1]["content"]
    assert str(chunk.document_id) not in messages[1]["content"]
    assert "hybrid_score" not in messages[1]["content"]


@pytest.mark.parametrize(
    "injected",
    [
        "[F1]",
        "[F2]",
        "[F999]",
        "[f1]",
        "[ F1 ]",
        "[F 1]",
        "[F01]",
        "[Fuente 1]",
        "[F1",
        "[F]",
    ],
)
def test_untrusted_marker_variants_are_neutralized_without_touching_real_marker(
    injected,
) -> None:
    prompt = _prompt()
    selected = prompt.select_context(injected, [_chunk(1, text=f"Dato {injected}")])
    user = prompt.build_messages(injected, selected)[1]["content"]
    assert user.count('id="[F1]"') == 1
    question_section = user.split("MARCADORES AUTORIZADOS:", 1)[0]
    evidence_section = user.split("EVIDENCIA DOCUMENTAL NO CONFIABLE:", 1)[1].split(
        "REGLAS FINALES OBLIGATORIAS:", 1
    )[0]
    assert "［" in question_section
    assert "［" in evidence_section
    assert "［" in user


def test_ordinary_legal_brackets_are_preserved() -> None:
    block = _prompt().serialize_chunk(
        _chunk(1, text="Artículo [1], numeral [2.a] y referencia [Ley 3]."),
        1,
    )
    assert "Artículo [1], numeral [2.a] y referencia [Ley 3]." in block


def test_markers_and_metadata_are_counted_in_final_prompt(monkeypatch) -> None:
    observed: list[str] = []
    rendered_prompts: list[str] = []

    def count(text: str) -> int:
        observed.append(text)
        return len(text)

    def count_chat(messages) -> int:
        rendered = "\n".join(message["content"] for message in messages)
        rendered_prompts.append(rendered)
        return len(rendered)

    prompt = RagPromptService(count, count_chat, lambda text, limit: text[:limit])
    monkeypatch.setattr(chat_module.settings, "rag_context_max_tokens", 10_000)
    selected = prompt.select_context("Pregunta", [_chunk(1)])
    messages = prompt.build_messages("Pregunta", selected)
    assert "[F1]" in "".join(observed)
    assert "paginas=1-2" in messages[1]["content"]
    final_render = rendered_prompts[-1]
    assert "MARCADORES AUTORIZADOS" in final_render
    assert "REGLAS FINALES OBLIGATORIAS" in final_render
    assert "FORMATO VÁLIDO" in final_render


def test_marker_metadata_can_exclude_last_chunk_and_renumbers_without_gaps(
    monkeypatch,
) -> None:
    prompt = _prompt(20)
    chunks = [_chunk(1, text="uno"), _chunk(2, text="dos"), _chunk(3, text="tres")]
    first = prompt.serialize_chunk(chunks[0], 1)
    second = prompt.serialize_chunk(chunks[1], 2)
    two_block_budget = prompt.count_tokens(f"{first}\n\n{second}")
    monkeypatch.setattr(chat_module.settings, "rag_context_max_tokens", two_block_budget)
    selected = prompt.select_context("Pregunta", chunks)
    joined = "\n\n".join(selected.blocks)
    assert selected.source_chunks == tuple(chunks[:2])
    assert 'id="[F1]"' in joined and 'id="[F2]"' in joined
    assert "[F3]" not in joined


def test_token_aware_truncation_preserves_the_server_marker(monkeypatch) -> None:
    prompt = _prompt(4)
    monkeypatch.setattr(chat_module.settings, "rag_context_max_tokens", 80)
    selected = prompt.select_context("Pregunta", [_chunk(1, text="texto " * 500)])
    assert selected.truncated_first
    assert selected.chunks == 1
    assert 'id="[F1]"' in selected.blocks[0]
    assert selected.source_chunks[0].chunk_id == _chunk(1).chunk_id


@pytest.mark.parametrize(
    "answer",
    [
        "Afirmación [F99]",
        "Afirmación [F0]",
        "Afirmación [F01]",
        "Afirmación F1",
        "Afirmación (F1)",
        "Afirmación {F1}",
        "Afirmación [Fuente 1]",
        "Afirmación [F1] y [F]",
        "Afirmación [F1] y [F",
        "Afirmación sin fuente",
        "[F1] [F1]",
        "Bibliografía: ejemplo [F1]",
        "Referencia https://example.invalid [F1]",
        "Documento inventado.pdf [F1]",
        r"Ruta C:\privado\archivo [F1]",
        "Página 99 [F1]",
        "Documento: falso.pdf [F1]",
        "Identificador 00000000-0000-4000-8000-000000000010 [F1]",
    ],
)
def test_closed_parser_rejects_unknown_partial_or_invented_references(answer) -> None:
    service = RagCitationService()
    registry = service.build_registry((_chunk(1),))
    with pytest.raises(RagCitationError, match="RAG_CITATION_OUTPUT_INVALID"):
        service.validate_answer(answer, registry)


@pytest.mark.parametrize(
    ("answer", "reason_code"),
    [
        ("Afirmación sin fuente", "CITATION_NO_MARKERS"),
        ("Afirmación [F99]", "CITATION_UNKNOWN_MARKER"),
        ("Afirmación [F0]", "CITATION_INVALID_MARKER_FORMAT"),
        ("Afirmación [F]", "CITATION_AMBIGUOUS_MARKER"),
        (
            "Párrafo citado [F1].\n\nPárrafo sin cita.",
            "CITATION_UNCITED_SUBSTANTIVE_ELEMENT",
        ),
        (
            "- Elemento citado [F1]\n- Elemento sin cita",
            "CITATION_UNCITED_SUBSTANTIVE_ELEMENT",
        ),
        ("[F1]", "CITATION_ONLY_MARKERS"),
        ("# Resumen [F1]", "CITATION_NO_SUBSTANTIVE_CONTENT"),
        (
            "Bibliografía: referencia sintética [F1]",
            "CITATION_FORBIDDEN_REFERENCE_CONTENT",
        ),
        ("", "CITATION_OUTPUT_STRUCTURE_INVALID"),
    ],
)
def test_output_rejection_has_exact_safe_reason_code(answer, reason_code) -> None:
    service = RagCitationService()
    registry = service.build_registry((_chunk(1),))
    with pytest.raises(RagCitationError) as captured:
        service.validate_answer(answer, registry)
    error = captured.value
    assert error.error_code == "RAG_CITATION_OUTPUT_INVALID"
    assert error.reason_code == reason_code
    assert error.stage == "citation_validation"
    assert reason_code in CITATION_REASON_CODES
    assert str(error) == "RAG_CITATION_OUTPUT_INVALID"


def test_structural_reason_taxonomy_is_closed_and_complete() -> None:
    assert CITATION_REASON_CODES == {
        "CITATION_NO_MARKERS",
        "CITATION_UNKNOWN_MARKER",
        "CITATION_INVALID_MARKER_FORMAT",
        "CITATION_AMBIGUOUS_MARKER",
        "CITATION_UNCITED_SUBSTANTIVE_ELEMENT",
        "CITATION_NO_SUBSTANTIVE_CONTENT",
        "CITATION_ONLY_MARKERS",
        "CITATION_FORBIDDEN_REFERENCE_CONTENT",
        "CITATION_DUPLICATE_SOURCE",
        "CITATION_ORDER_MISMATCH",
        "CITATION_COVERAGE_INVALID",
        "CITATION_OUTPUT_STRUCTURE_INVALID",
    }


def test_parser_preserves_first_appearance_and_deduplicates_public_sources() -> None:
    service = RagCitationService()
    registry = service.build_registry((_chunk(1), _chunk(2)))
    used = service.validate_answer("Primero [F2].\n\nSegundo [F1] y [F2].", registry)
    assert [source.marker for source in used] == ["[F2]", "[F1]"]


@pytest.mark.parametrize(
    "answer",
    [
        "Texto [F2][F1].",
        "Texto [F2] [F1].",
        "Texto [F1], [F2].",
    ],
)
def test_parser_accepts_multiple_contiguous_valid_markers(answer) -> None:
    service = RagCitationService()
    registry = service.build_registry((_chunk(1), _chunk(2)))
    used = service.validate_answer(answer, registry)
    expected = ["[F2]", "[F1]"] if answer.index("F2") < answer.index("F1") else ["[F1]", "[F2]"]
    assert [source.marker for source in used] == expected


@pytest.mark.parametrize(
    "answer",
    [
        "Párrafo citado [F1].\n\nPárrafo sin cita.",
        "- Elemento citado [F1]\n- Elemento sin cita",
        "Encabezado:\n\nPárrafo sin cita.",
    ],
)
def test_every_substantive_element_requires_a_valid_marker(answer) -> None:
    service = RagCitationService()
    registry = service.build_registry((_chunk(1),))
    with pytest.raises(RagCitationError, match="RAG_CITATION_OUTPUT_INVALID"):
        service.validate_answer(answer, registry)


def test_structural_heading_is_allowed_when_substantive_content_is_cited() -> None:
    service = RagCitationService()
    registry = service.build_registry((_chunk(1),))
    used = service.validate_answer("# Resumen\n\nContenido sustantivo [F1].", registry)
    assert [source.marker for source in used] == ["[F1]"]


@pytest.mark.parametrize(
    "answer",
    [
        "Encabezado:\r\n\r\nAcción válida [F1].",
        "- Acción válida [F1]\n- Segunda acción [F1]",
        "1. Acción válida [F1]\r\n2. Niñez protegida [F1]",
        "Acción y jurisdicción [F1].",
        "Acción y jurisdicción [F1]",
    ],
)
def test_coverage_accepts_unicode_lists_and_windows_or_unix_newlines(answer) -> None:
    service = RagCitationService()
    registry = service.build_registry((_chunk(1),))
    assert service.validate_answer(answer, registry)


@pytest.mark.parametrize(
    "answer",
    [
        "[F1]",
        "[F1] [F2]",
        "- [F1]",
        "&lt;p&gt;&lt;/p&gt; [F1]",
        "# Afirmación sustantiva completa. [F1]\n\nOtra sin cita.",
    ],
)
def test_markers_or_empty_html_are_not_substantive_content(answer) -> None:
    service = RagCitationService()
    registry = service.build_registry((_chunk(1), _chunk(2)))
    with pytest.raises(RagCitationError, match="RAG_CITATION_OUTPUT_INVALID"):
        service.validate_answer(answer, registry)


def test_think_removal_that_leaves_only_a_marker_is_rejected() -> None:
    sanitized = RagChatService._sanitize_output("<think>interno</think>[F1]")
    service = RagCitationService()
    registry = service.build_registry((_chunk(1),))
    with pytest.raises(RagCitationError, match="RAG_CITATION_OUTPUT_INVALID"):
        service.validate_answer(sanitized, registry)


def test_revalidation_builds_public_metadata_from_current_sqlite_source() -> None:
    service = RagCitationService()
    chunk = _chunk(1, name=r"C:\interno\sentencia.pdf")
    registry = service.build_registry((chunk,))
    used = service.validate_answer("Contenido [F1].", registry)
    citations = asyncio.run(
        service.revalidate_sources(used, registry, FakeRepository([chunk]))
    )
    citation = citations[0]
    assert citation.marker == "[F1]"
    assert citation.document_id == chunk.document_id
    assert citation.document_name == "sentencia.pdf"
    assert "chunk_id" not in citation.model_dump()
    assert "stored_filename" not in citation.model_dump()


@pytest.mark.parametrize(
    "changed",
    [
        None,
        replace(_chunk(1), document_id=UUID(int=99)),
        replace(_chunk(1), document_type=DocumentType.OTRO),
        replace(_chunk(1), chunk_index=2),
        replace(_chunk(1), start_page=2),
        replace(_chunk(1), end_page=3),
        replace(_chunk(1), document_name="actualizado.pdf"),
        replace(_chunk(1), text="Texto modificado"),
    ],
)
def test_revalidation_rejects_deleted_or_changed_sources(changed) -> None:
    service = RagCitationService()
    original = _chunk(1)
    registry = service.build_registry((original,))
    used = service.validate_answer("Contenido [F1].", registry)
    repository = FakeRepository([] if changed is None else [changed])
    with pytest.raises(RagCitationError, match="RAG_CITATION_SOURCE_STALE"):
        asyncio.run(service.revalidate_sources(used, registry, repository))


def test_revalidation_rejects_source_not_in_original_context() -> None:
    service = RagCitationService()
    original = _chunk(1)
    registry = service.build_registry((original,))
    forged = CitationSource(
        marker="[F2]",
        chunk_id=UUID(int=999),
        document_id=UUID(int=10),
        document_name="documento.pdf",
        document_type=DocumentType.JURISPRUDENCIA,
        chunk_index=2,
        start_page=2,
        end_page=2,
        text_fingerprint="0" * 64,
    )
    with pytest.raises(RagCitationError, match="RAG_CITATION_SOURCE_STALE"):
        asyncio.run(
            service.revalidate_sources((forged,), registry, FakeRepository([original]))
        )


def test_one_stale_source_rejects_the_whole_response_without_partial_citations() -> None:
    service = RagCitationService()
    first, second = _chunk(1), _chunk(2)
    registry = service.build_registry((first, second))
    used = service.validate_answer("Primero [F1].\n\nSegundo [F2].", registry)
    repository = FakeRepository([first, replace(second, start_page=99, end_page=99)])
    with pytest.raises(RagCitationError, match="RAG_CITATION_SOURCE_STALE"):
        asyncio.run(service.revalidate_sources(used, registry, repository))


def test_response_contract_requires_exact_citation_count_and_empty_insufficient() -> None:
    citation = {
        "marker": "[F1]",
        "document_id": UUID(int=10),
        "document_name": "documento.pdf",
        "document_type": "jurisprudencia",
        "chunk_index": 1,
        "start_page": 1,
        "end_page": 1,
    }
    response = RagChatResponse(
        status="answered",
        answer="Contenido [F1]",
        retrieved_chunks=1,
        context_chunks=1,
        context_tokens=5,
        citation_count=1,
        citations=[citation],
    )
    assert response.citation_count == len(response.citations) == 1
    with pytest.raises(ValidationError):
        RagChatResponse(
            status="insufficient_context",
            answer="Sin contexto",
            retrieved_chunks=0,
            context_chunks=0,
            context_tokens=0,
            citation_count=1,
            citations=[citation],
        )


def test_response_schema_rejects_marker_mismatch_duplicate_source_and_extra_fields() -> None:
    base = {
        "status": "answered",
        "answer": "Contenido [F1]",
        "retrieved_chunks": 2,
        "context_chunks": 2,
        "context_tokens": 5,
        "citation_count": 1,
        "citations": [
            {
                "marker": "[F1]",
                "document_id": UUID(int=10),
                "document_name": "documento.pdf",
                "document_type": "jurisprudencia",
                "chunk_index": 1,
                "start_page": 1,
                "end_page": 1,
            }
        ],
    }
    for changed in (
        {**base, "answer": "Contenido [F2]"},
        {**base, "requires_professional_review": False},
        {**base, "campo_extra": "no permitido"},
    ):
        with pytest.raises(ValidationError):
            RagChatResponse(**changed)

    duplicate = dict(base)
    duplicate["answer"] = "Contenido [F1] [F2]"
    duplicate["citation_count"] = 2
    duplicate["citations"] = [
        base["citations"][0],
        {**base["citations"][0], "marker": "[F2]"},
    ]
    with pytest.raises(ValidationError):
        RagChatResponse(**duplicate)

    duplicate_marker = dict(base)
    duplicate_marker["answer"] = "Contenido [F1]"
    duplicate_marker["citation_count"] = 2
    duplicate_marker["citations"] = [base["citations"][0], base["citations"][0]]
    with pytest.raises(ValidationError):
        RagChatResponse(**duplicate_marker)

    wrong_count = dict(base)
    wrong_count["citation_count"] = 2
    with pytest.raises(ValidationError):
        RagChatResponse(**wrong_count)


@pytest.mark.parametrize(
    "overrides",
    [
        {"marker": ""},
        {"marker": "[F0]"},
        {"marker": "[F01]"},
        {"chunk_index": 0},
        {"start_page": -1},
        {"end_page": -1},
        {"start_page": 3, "end_page": 2},
        {"start_page": True},
        {"campo_extra": "no permitido"},
    ],
)
def test_public_citation_schema_rejects_invalid_structures(overrides) -> None:
    values = {
        "marker": "[F1]",
        "document_id": UUID(int=10),
        "document_name": "documento.pdf",
        "document_type": "jurisprudencia",
        "chunk_index": 1,
        "start_page": 1,
        "end_page": 1,
    }
    values.update(overrides)
    with pytest.raises(ValidationError):
        RagCitation(**values)


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("RAG_CITATION_OUTPUT_INVALID", 500),
        ("RAG_CITATION_METADATA_INVALID", 500),
        ("RAG_CITATION_SOURCE_STALE", 409),
    ],
)
def test_citation_errors_have_controlled_http_status(code, status) -> None:
    error = _rag_http_error(RagChatError(code))
    assert error.status_code == status
    assert error.detail == code


def test_citation_reason_is_preserved_in_safe_http_detail() -> None:
    error = _rag_http_error(
        RagChatError(
            "RAG_CITATION_OUTPUT_INVALID",
            reason_code="CITATION_UNCITED_SUBSTANTIVE_ELEMENT",
            stage="citation_validation",
        )
    )
    assert error.status_code == 500
    assert error.detail == {
        "error_code": "RAG_CITATION_OUTPUT_INVALID",
        "reason_code": "CITATION_UNCITED_SUBSTANTIVE_ELEMENT",
        "stage": "citation_validation",
    }


def test_citation_logging_contains_only_counts(caplog, monkeypatch) -> None:
    marker = "[F1]"
    private_id = str(UUID(int=10))

    def capture(message: str, **context) -> None:
        logging.getLogger("citation_audit").info("%s %s", message, context)

    monkeypatch.setattr(chat_module, "log_error", capture)
    with caplog.at_level(logging.INFO, logger="citation_audit"):
        RagChatService._log_citation_failure(
            RagCitationError(
                "RAG_CITATION_OUTPUT_INVALID",
                reason_code="CITATION_UNKNOWN_MARKER",
                stage="citation_validation",
                total_sources=2,
                substantive_elements=1,
                structural_errors=2,
            ),
            type("Request", (), {"question": "privada"})(),
            None,
            0.0,
        )
    assert marker not in caplog.text
    assert private_id not in caplog.text
    assert "privada" not in caplog.text
    assert "CITATION_UNKNOWN_MARKER" in caplog.text
    assert "citation_validation" in caplog.text
    assert "structural_errors" in caplog.text


def test_chat_closes_retrieval_session_before_generation_and_revalidates_after() -> None:
    events: list[str] = []
    chunk = _chunk(1)

    class Session:
        async def rollback(self):
            events.append("rollback")

        async def close(self):
            events.append("close")

    class Hybrid:
        async def search(self, request, *, request_id=None):
            return HybridSearchResponse(
                items=[
                    HybridSearchItem(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        document_type=chunk.document_type,
                        chunk_index=chunk.chunk_index,
                        start_page=chunk.start_page,
                        end_page=chunk.end_page,
                        snippet="no usado",
                        hybrid_score=0.1,
                        appeared_in_text=True,
                        appeared_in_semantic=False,
                        text_rank=1,
                        rank_bm25=-1.0,
                    )
                ],
                returned=1,
                top_k=request.top_k,
            )

    class Context:
        async def get_valid_chunks(self, items, request):
            return [chunk]

    class Llm:
        is_loaded = True

        @staticmethod
        def count_tokens(text, *, add_bos=False):
            return max(1, len(text) // 20)

        @staticmethod
        def count_chat_tokens(messages):
            return sum(max(1, len(message["content"]) // 20) for message in messages)

        @staticmethod
        def truncate_text_to_tokens(text, max_tokens):
            return text[: max_tokens * 20]

        @staticmethod
        def generate_chat(messages, **options):
            events.append("generate")
            return "Respuesta sintética [F1]"

    repository = FakeRepository([chunk])

    @asynccontextmanager
    async def final_session():
        events.append("new_session")
        yield object()

    class EventRepository:
        async def get_active_by_ids(self, chunk_ids):
            events.append("revalidate")
            return await repository.get_active_by_ids(chunk_ids)

    service = RagChatService(
        Session(),  # type: ignore[arg-type]
        hybrid_service=Hybrid(),  # type: ignore[arg-type]
        context_service=Context(),  # type: ignore[arg-type]
        local_llm=Llm(),  # type: ignore[arg-type]
        citation_session_factory=final_session,  # type: ignore[arg-type]
        citation_repository_factory=lambda _session: EventRepository(),  # type: ignore[arg-type]
    )
    response = asyncio.run(service.chat(RagChatRequest(question="Pregunta sintética")))
    assert response.citation_count == 1
    assert events.index("close") < events.index("generate")
    assert events.index("generate") < events.index("new_session")
    assert events.index("new_session") < events.index("revalidate")
