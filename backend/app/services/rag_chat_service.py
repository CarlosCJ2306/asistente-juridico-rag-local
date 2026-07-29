"""Orquestación stateless de recuperación híbrida y generación local."""

from __future__ import annotations

import html
import re
import time
import unicodedata
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.local_llm import (
    LLMGenerationBusyError,
    LLMGenerationError,
    LLMNotLoadedError,
    LocalLLM,
    get_local_llm,
)
from app.core.Log import log_error, log_info, log_success
from app.core.config import settings
from app.database.repositories.semantic_chunk_repository import (
    ActiveChunk,
    SemanticChunkRepository,
)
from app.schemas.hybrid_search import HybridSearchRequest
from app.schemas.rag_chat import RagChatRequest, RagChatResponse
from app.services.hybrid_search_service import HybridSearchService
from app.services.llm_runtime_service import (
    LlmRuntimeError,
    LlmRuntimeService,
    get_llm_runtime_service,
)
from app.services.rag_answerability_service import RagAnswerabilityService
from app.services.rag_citation_service import (
    ActiveChunkReader,
    CITATION_ERROR_STAGES,
    CITATION_REASON_CODES,
    RagCitationError,
    RagCitationService,
)
from app.services.rag_context_service import RagContextService
from app.services.rag_prompt_service import (
    ConversationContextMessage,
    INSUFFICIENT_CONTEXT_ANSWER,
    RagPromptError,
    RagPromptService,
)


_FORBIDDEN_DISCLOSURE_REQUEST = re.compile(
    r"\b(?:revela|revelar|muestra|mostrar|imprime|imprimir|dime|give|show|reveal)\b"
    r".{0,100}\b(?:prompt|instrucciones?\s+del\s+sistema|system\s+prompt|"
    r"rutas?\s+(?:internas?|absolutas?)|configuraci[oó]n\s+interna|secretos?)\b",
    flags=re.IGNORECASE | re.DOTALL,
)


class RagChatError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        reason_code: str | None = None,
        stage: str | None = None,
        total_sources: int = 0,
        substantive_elements: int = 0,
        structural_errors: int = 0,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.error_code = code
        self.reason_code = (
            reason_code if reason_code in CITATION_REASON_CODES else None
        )
        self.stage = stage if stage in CITATION_ERROR_STAGES else None
        self.total_sources = max(0, total_sources)
        self.substantive_elements = max(0, substantive_elements)
        self.structural_errors = max(0, structural_errors)

    @classmethod
    def from_citation(cls, error: RagCitationError) -> "RagChatError":
        return cls(
            error.code,
            reason_code=error.reason_code,
            stage=error.stage,
            total_sources=error.total_sources,
            substantive_elements=error.substantive_elements,
            structural_errors=error.structural_errors,
        )


class RagChatService:
    """Recupera una vez, cierra la lectura y genera una vez fuera del event loop."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        hybrid_service: HybridSearchService | None = None,
        context_service: RagContextService | None = None,
        local_llm: LocalLLM | None = None,
        llm_runtime: LlmRuntimeService | None = None,
        citation_service: RagCitationService | None = None,
        citation_session_factory: (
            Callable[[], AbstractAsyncContextManager[AsyncSession]] | None
        ) = None,
        citation_repository_factory: (
            Callable[[AsyncSession], ActiveChunkReader] | None
        ) = None,
    ) -> None:
        self.session = session
        self.hybrid_service = hybrid_service or HybridSearchService(session)
        self.context_service = context_service or RagContextService(
            SemanticChunkRepository(session)
        )
        self.local_llm = local_llm or get_local_llm()
        self.llm_runtime = llm_runtime or (
            LlmRuntimeService(self.local_llm)
            if local_llm is not None
            else get_llm_runtime_service()
        )
        self.citation_service = citation_service or RagCitationService()
        self.citation_repository_factory = (
            citation_repository_factory or SemanticChunkRepository
        )
        self.citation_session_factory: (
            Callable[[], AbstractAsyncContextManager[AsyncSession]] | None
        ) = citation_session_factory
        if self.citation_session_factory is None:
            bind = getattr(session, "bind", None)
            if bind is not None:
                session_maker = async_sessionmaker(
                    bind=bind,
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autoflush=False,
                )

                def create_citation_session() -> AbstractAsyncContextManager[AsyncSession]:
                    return session_maker()

                self.citation_session_factory = create_citation_session

    async def chat(
        self,
        request: RagChatRequest,
        *,
        request_id: str | None = None,
        conversation_context: tuple[ConversationContextMessage, ...] = (),
        enforce_answerability: bool = False,
        evidence_observer: Callable[[tuple[ActiveChunk, ...]], None] | None = None,
    ) -> RagChatResponse:
        started_at = time.perf_counter()
        self._validate_question(request.question)
        retrieval_started = time.perf_counter()
        retrieval_query = self._retrieval_query(request.question, conversation_context)
        try:
            hybrid = await self.hybrid_service.search(
                HybridSearchRequest(
                    query=retrieval_query,
                    text_match_mode=request.text_match_mode,
                    top_k=request.top_k,
                    document_id=request.document_id,
                    document_types=request.document_types,
                    knowledge_layers=request.knowledge_layers,
                    min_page=request.min_page,
                    max_page=request.max_page,
                ),
                request_id=request_id,
            )
            chunks = await self.context_service.get_valid_chunks(hybrid.items, request)
            if enforce_answerability and not RagAnswerabilityService().has_sufficient_evidence(
                retrieval_query=request.question,
                request=request,
                response=hybrid,
                chunks=chunks,
            ):
                chunks = []
            await self.session.rollback()
            close_session = getattr(self.session, "close", None)
            if callable(close_session):
                await close_session()
        except RagChatError:
            raise
        except Exception:
            raise
        retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000, 2)

        if not chunks:
            response = self._insufficient(hybrid.returned)
            self._log_success(response, request, request_id, started_at, retrieval_ms, 0.0)
            return response

        try:
            async with self.llm_runtime.activity() as loaded_automatically:
                return await self._answer_with_context(
                    request=request,
                    request_id=request_id,
                    chunks=chunks,
                    retrieved_chunks=hybrid.returned,
                    started_at=started_at,
                    retrieval_ms=retrieval_ms,
                    loaded_automatically=loaded_automatically,
                    conversation_context=conversation_context,
                    evidence_observer=evidence_observer,
                )
        except LlmRuntimeError as exc:
            self.log_failure(exc.code, request, request_id, started_at)
            raise RagChatError(exc.code) from exc

    async def _answer_with_context(
        self,
        *,
        request: RagChatRequest,
        request_id: str | None,
        chunks: list[ActiveChunk],
        retrieved_chunks: int,
        started_at: float,
        retrieval_ms: float,
        loaded_automatically: bool,
        conversation_context: tuple[ConversationContextMessage, ...],
        evidence_observer: Callable[[tuple[ActiveChunk, ...]], None] | None,
    ) -> RagChatResponse:
        log_info(
            "Iniciando chat RAG local",
            operation="rag_chat",
            request_id=request_id,
            question_length=len(request.question),
            term_count=len(request.question.split()),
            top_k=request.top_k,
            filter_count=self._filter_count(request),
            model_state="loaded",
            load_origin=(
                "on_demand"
                if loaded_automatically
                else self.llm_runtime.load_origin or "manual"
            ),
        )

        prompt_service = RagPromptService(
            self.local_llm.count_tokens,
            self.local_llm.count_chat_tokens,
            self.local_llm.truncate_text_to_tokens,
        )
        try:
            selected = prompt_service.select_context(
                request.question, chunks, conversation_context
            )
            if selected.chunks == 0:
                response = self._insufficient(retrieved_chunks)
                self._log_success(
                    response, request, request_id, started_at, retrieval_ms, 0.0
                )
                return response
            registry = self.citation_service.build_registry(selected.source_chunks)
            if len(registry.sources) != selected.chunks:
                raise RagChatError("RAG_CITATION_METADATA_INVALID")
            messages = prompt_service.build_messages(
                request.question,
                selected,
                registry.markers,
                conversation_context,
            )
        except RagCitationError as exc:
            self._log_citation_failure(exc, request, request_id, started_at)
            raise RagChatError.from_citation(exc) from exc
        except RagPromptError as exc:
            if exc.code == "RAG_TOKEN_BUDGET_INVALID":
                response = self._insufficient(retrieved_chunks)
                self._log_success(
                    response, request, request_id, started_at, retrieval_ms, 0.0
                )
                return response
            raise RagChatError(exc.code) from exc
        except LLMGenerationBusyError as exc:
            raise RagChatError("RAG_GENERATION_BUSY") from exc
        except LLMNotLoadedError as exc:
            raise RagChatError("RAG_LLM_NOT_LOADED") from exc
        except LLMGenerationError as exc:
            raise RagChatError("RAG_TOKEN_BUDGET_INVALID") from exc
        generation_started = time.perf_counter()
        raw_answer = await self.llm_runtime.generate_chat(
            self.local_llm.generate_chat,
            messages,
            temperature=settings.rag_temperature,
            max_tokens=settings.rag_max_new_tokens,
            top_p=settings.rag_top_p,
            repeat_penalty=settings.rag_repeat_penalty,
        )
        generation_ms = round((time.perf_counter() - generation_started) * 1000, 2)
        answer = self._sanitize_output(
            raw_answer,
            forbidden_fragments=(messages[0]["content"], messages[1]["content"]),
        )
        try:
            used_sources = self.citation_service.validate_answer(answer, registry)
            if self.citation_session_factory is None:
                raise RagCitationError("RAG_CITATION_METADATA_INVALID")
            async with self.citation_session_factory() as citation_session:
                citations = await self.citation_service.revalidate_sources(
                    used_sources,
                    registry,
                    self.citation_repository_factory(citation_session),
                )
        except RagCitationError as exc:
            self._log_citation_failure(exc, request, request_id, started_at)
            raise RagChatError.from_citation(exc) from exc
        response = RagChatResponse(
            status="answered",
            answer=answer,
            retrieved_chunks=retrieved_chunks,
            context_chunks=selected.chunks,
            context_tokens=selected.tokens,
            requires_professional_review=True,
            citation_count=len(citations),
            citations=citations,
        )
        if evidence_observer is not None:
            evidence_observer(selected.source_chunks)
        self._log_success(
            response, request, request_id, started_at, retrieval_ms, generation_ms
        )
        return response

    @staticmethod
    def _retrieval_query(
        question: str,
        conversation_context: tuple[ConversationContextMessage, ...],
    ) -> str:
        prior_questions = [
            item.content.strip()
            for item in conversation_context
            if item.role == "user" and item.content.strip()
        ][-2:]
        parts = prior_questions + [question.strip()]
        terms: list[str] = []
        for part in parts:
            for term in part.split():
                if len(terms) >= settings.text_search_max_terms:
                    break
                terms.append(term)
        return " ".join(terms)[: settings.text_search_query_max_chars].strip()

    @staticmethod
    def _validate_question(question: str) -> None:
        """Bloquea solicitudes explícitas de secretos sin registrar su contenido."""

        if _FORBIDDEN_DISCLOSURE_REQUEST.search(question):
            raise RagChatError("RAG_REQUEST_FORBIDDEN")

    @staticmethod
    def _sanitize_output(
        value: object, *, forbidden_fragments: tuple[str, ...] = ()
    ) -> str:
        if not isinstance(value, str):
            raise RagChatError("RAG_OUTPUT_INVALID")
        without_reasoning = re.sub(
            r"<think\b[^>]*>.*?</think\s*>", "", value, flags=re.IGNORECASE | re.DOTALL
        )
        if re.search(r"</?think\b", without_reasoning, flags=re.IGNORECASE):
            raise RagChatError("RAG_OUTPUT_INVALID")
        cleaned = "".join(
            character
            for character in without_reasoning
            if character in "\n\t" or not unicodedata.category(character).startswith("C")
        ).strip()
        if not cleaned:
            raise RagChatError("RAG_OUTPUT_INVALID")
        lowered = cleaned.casefold()
        if any(fragment and fragment.casefold() in lowered for fragment in forbidden_fragments):
            raise RagChatError("RAG_OUTPUT_INVALID")
        if "<<<evidencia_no_confiable" in lowered or "<|im_start|>" in lowered:
            raise RagChatError("RAG_OUTPUT_INVALID")
        escaped = html.escape(cleaned, quote=True)
        if not escaped:
            raise RagChatError("RAG_OUTPUT_INVALID")
        return escaped[: settings.rag_answer_max_length]

    @staticmethod
    def _insufficient(retrieved: int) -> RagChatResponse:
        return RagChatResponse(
            status="insufficient_context",
            answer=INSUFFICIENT_CONTEXT_ANSWER,
            retrieved_chunks=retrieved,
            context_chunks=0,
            context_tokens=0,
            requires_professional_review=True,
            citation_count=0,
            citations=[],
        )

    @staticmethod
    def _filter_count(request: RagChatRequest) -> int:
        return sum(
            value is not None
            for value in (
                request.document_id,
                request.document_types,
                request.knowledge_layers,
                request.min_page,
                request.max_page,
            )
        )

    @staticmethod
    def _log_success(
        response: RagChatResponse,
        request: RagChatRequest,
        request_id: str | None,
        started_at: float,
        retrieval_ms: float,
        generation_ms: float,
    ) -> None:
        log_success(
            "Chat RAG local completado",
            operation="rag_chat",
            request_id=request_id,
            question_length=len(request.question),
            term_count=len(request.question.split()),
            top_k=request.top_k,
            filter_count=RagChatService._filter_count(request),
            retrieved_chunks=response.retrieved_chunks,
            context_chunks=response.context_chunks,
            context_tokens=response.context_tokens,
            citation_count=response.citation_count,
            max_new_tokens=settings.rag_max_new_tokens,
            status=response.status,
            retrieval_duration_ms=retrieval_ms,
            generation_duration_ms=generation_ms,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )

    @staticmethod
    def _log_citation_failure(
        error: RagCitationError,
        request: RagChatRequest,
        request_id: str | None,
        started_at: float,
    ) -> None:
        log_error(
            "Falló la validación de citas del chat RAG",
            operation="rag_chat_citations",
            request_id=request_id,
            error_code=error.code,
            reason_code=error.reason_code,
            stage=error.stage,
            total_sources=error.total_sources,
            substantive_elements=error.substantive_elements,
            structural_errors=error.structural_errors,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )

    @staticmethod
    def log_failure(
        code: str, request: RagChatRequest, request_id: str | None, started_at: float
    ) -> None:
        log_error(
            "Falló el chat RAG local",
            operation="rag_chat",
            request_id=request_id,
            question_length=len(request.question),
            term_count=len(request.question.split()),
            top_k=request.top_k,
            filter_count=RagChatService._filter_count(request),
            error_code=code,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
