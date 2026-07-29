"""Conversaciones RAG persistentes, aisladas y verificables."""

from __future__ import annotations

import asyncio
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.Log import log_error, log_success
from app.core.config import settings
from app.database.models.conversation import (
    Conversation,
    ConversationCitation,
    ConversationClaim,
    ConversationClaimCitation,
    ConversationCoverageStatus,
    ConversationMessage,
    ConversationMessageRole,
    ConversationMessageStatus,
    ConversationStatus,
)
from app.database.models.document import DocumentType, KnowledgeLayer
from app.database.repositories.conversation_repository import ConversationRepository
from app.database.repositories.semantic_chunk_repository import ActiveChunk
from app.database.repositories.text_search_repository import TextSearchRepositoryError
from app.schemas.conversation import (
    ConversationCitationRead,
    ConversationClaimRead,
    ConversationCreate,
    ConversationDetail,
    ConversationMessageCreate,
    ConversationMessageRead,
    ConversationPage,
    ConversationRead,
    ConversationTurnResponse,
    ConversationUpdate,
)
from app.schemas.rag_chat import RagChatResponse
from app.services.conversation_principal import ConversationPrincipal
from app.services.document_governance_service import (
    DocumentGovernanceService,
    DocumentGovernanceSnapshot,
)
from app.services.hybrid_search_service import HybridSearchError
from app.services.rag_chat_service import RagChatError, RagChatService
from app.services.rag_prompt_service import ConversationContextMessage
from app.services.semantic_index_service import SemanticServiceError


_MARKER_PATTERN = re.compile(r"\[F[1-9]\d*\]")
_CLAIM_SPLIT = re.compile(r"(?:\r?\n){2,}|\r?\n(?=\s*(?:[-*•]|\d+[.)])\s+)")
_locks: defaultdict[UUID, asyncio.Lock] = defaultdict(asyncio.Lock)


class ConversationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ConversationService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        rag_service: RagChatService | None = None,
    ) -> None:
        self.session = session
        self.repository = ConversationRepository(session)
        self._rag_session: AsyncSession | None = None
        if rag_service is None:
            bind = session.bind
            if bind is None:
                raise ConversationError("CONVERSATION_DATABASE_UNAVAILABLE")
            factory = async_sessionmaker(
                bind=bind,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
            self._rag_session = factory()
            self.rag_service = RagChatService(self._rag_session)
        else:
            self.rag_service = rag_service

    async def create(
        self, payload: ConversationCreate, principal: ConversationPrincipal
    ) -> ConversationRead:
        if principal.owner_type != "guest" or principal.guest_session_hash is None:
            raise ConversationError("CONVERSATION_PRINCIPAL_INVALID")
        now = self._now()
        conversation = await self.repository.create_guest(
            session_hash=principal.guest_session_hash,
            title=payload.title or "Nueva conversación",
            now=now,
            expires_at=self._expiry(now),
        )
        await self.session.commit()
        log_success("Conversación creada", operation="conversation_create")
        return self._conversation_read(conversation, 0)

    async def list_page(
        self,
        principal: ConversationPrincipal,
        *,
        page: int,
        page_size: int,
        status: ConversationStatus,
    ) -> ConversationPage:
        rows, total = await self.repository.list_owned(
            principal,
            now=self._now(),
            status=status,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        counts = await self.repository.message_counts([row.id for row in rows])
        return ConversationPage(
            items=[self._conversation_read(row, counts.get(row.id, 0)) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def detail(
        self, conversation_id: UUID, principal: ConversationPrincipal
    ) -> ConversationDetail:
        conversation = await self._owned(conversation_id, principal)
        messages = await self.repository.messages(conversation.id)
        rendered = await self._message_reads(messages)
        return ConversationDetail(
            **self._conversation_read(conversation, len(messages)).model_dump(),
            messages=rendered,
        )

    async def update(
        self,
        conversation_id: UUID,
        payload: ConversationUpdate,
        principal: ConversationPrincipal,
    ) -> ConversationRead:
        conversation = await self._owned(conversation_id, principal)
        if payload.title is not None:
            conversation.title = payload.title
        if payload.status is not None:
            conversation.status = ConversationStatus(payload.status)
        now = self._now()
        conversation.updated_at = now
        conversation.last_activity_at = now
        self._renew(conversation, now)
        await self.session.commit()
        count = await self.repository.message_count(conversation.id)
        return self._conversation_read(conversation, count)

    async def delete(
        self, conversation_id: UUID, principal: ConversationPrincipal
    ) -> None:
        conversation = await self._owned(conversation_id, principal)
        await self.repository.delete_conversation(conversation)
        await self.session.commit()
        log_success("Conversación eliminada", operation="conversation_delete")

    async def add_message(
        self,
        conversation_id: UUID,
        payload: ConversationMessageCreate,
        principal: ConversationPrincipal,
        *,
        idempotency_key: str | None,
        request_id: str | None,
    ) -> ConversationTurnResponse:
        async with _locks[conversation_id]:
            conversation = await self._owned(conversation_id, principal)
            if conversation.status is not ConversationStatus.ACTIVE:
                raise ConversationError("CONVERSATION_ARCHIVED")
            if idempotency_key is not None:
                prior = await self.repository.find_idempotent_user_message(
                    conversation.id, idempotency_key
                )
                if prior is not None:
                    assistant = await self.repository.assistant_after(prior)
                    if assistant is None:
                        raise ConversationError("CONVERSATION_MESSAGE_BUSY")
                    return await self._turn(conversation, prior, assistant)

            context = await self._context(conversation.id)
            now = self._now()
            sequence = await self.repository.next_sequence(conversation.id)
            user_message = await self.repository.add_message(
                ConversationMessage(
                    conversation_id=conversation.id,
                    role=ConversationMessageRole.USER,
                    content=payload.question,
                    sequence_number=sequence,
                    idempotency_key=idempotency_key,
                    created_at=now,
                )
            )
            if await self.repository.message_count(conversation.id) == 1:
                conversation.title = self._title(payload.question)
            conversation.last_activity_at = now
            conversation.updated_at = now
            self._renew(conversation, now)
            await self.session.commit()

            try:
                evidence_chunks: dict[tuple[UUID, int], str] = {}

                def observe_evidence(chunks: tuple[ActiveChunk, ...]) -> None:
                    for chunk in chunks:
                        document_id = getattr(chunk, "document_id", None)
                        chunk_index = getattr(chunk, "chunk_index", None)
                        text = getattr(chunk, "text", None)
                        if (
                            isinstance(document_id, UUID)
                            and isinstance(chunk_index, int)
                            and isinstance(text, str)
                        ):
                            evidence_chunks[(document_id, chunk_index)] = text

                try:
                    response = await self.rag_service.chat(
                        payload,
                        request_id=request_id,
                        conversation_context=context,
                        enforce_answerability=True,
                        evidence_observer=observe_evidence,
                    )
                finally:
                    if self._rag_session is not None:
                        await self._rag_session.close()
                assistant = await self._persist_assistant(
                    conversation, sequence + 1, response, evidence_chunks
                )
                await self.session.commit()
            except (
                RagChatError,
                HybridSearchError,
                TextSearchRepositoryError,
                SemanticServiceError,
            ) as exc:
                await self.session.rollback()
                conversation = await self._owned(conversation_id, principal)
                error_code = getattr(exc, "code", "RAG_GENERATION_ERROR")
                await self._persist_failure(conversation, sequence + 1, error_code)
                await self.session.commit()
                log_error(
                    "Fallo controlado en turno conversacional",
                    operation="conversation_message",
                    request_id=request_id,
                    error_code=error_code,
                )
                raise
            except Exception as exc:
                await self.session.rollback()
                conversation = await self._owned(conversation_id, principal)
                await self._persist_failure(
                    conversation, sequence + 1, "RAG_GENERATION_ERROR"
                )
                await self.session.commit()
                log_error(
                    "Fallo inesperado en turno conversacional",
                    operation="conversation_message",
                    request_id=request_id,
                    error_code="RAG_GENERATION_ERROR",
                )
                raise ConversationError("RAG_GENERATION_ERROR") from exc
            log_success(
                "Turno conversacional persistido",
                operation="conversation_message",
                request_id=request_id,
                status=response.status,
                citation_count=response.citation_count,
            )
            return await self._turn(conversation, user_message, assistant)

    async def _persist_assistant(
        self,
        conversation: Conversation,
        sequence: int,
        response: RagChatResponse,
        evidence_chunks: dict[tuple[UUID, int], str],
    ) -> ConversationMessage:
        now = self._now()
        answered = response.status == "answered"
        assistant = await self.repository.add_message(
            ConversationMessage(
                conversation_id=conversation.id,
                role=ConversationMessageRole.ASSISTANT,
                content=response.answer,
                sequence_number=sequence,
                public_status=(
                    ConversationMessageStatus.ANSWERED
                    if answered
                    else ConversationMessageStatus.INSUFFICIENT_CONTEXT
                ),
                coverage_status=(
                    ConversationCoverageStatus.FULL
                    if answered
                    else ConversationCoverageStatus.INSUFFICIENT
                ),
                model_id=(
                    getattr(getattr(self.rag_service, "local_llm", None), "model_id", None)
                    if answered
                    else None
                ),
                created_at=now,
                completed_at=now,
            )
        )
        if answered:
            citations = await self._persist_citations(
                assistant, response, evidence_chunks
            )
            await self._persist_claims(assistant, response.answer, citations)
        conversation.last_activity_at = now
        conversation.updated_at = now
        self._renew(conversation, now)
        return assistant

    async def _persist_citations(
        self,
        assistant: ConversationMessage,
        response: RagChatResponse,
        evidence_chunks: dict[tuple[UUID, int], str],
    ) -> dict[str, ConversationCitation]:
        identities = [(item.document_id, item.chunk_index) for item in response.citations]
        rows = await self.repository.current_source_rows(identities)
        if len(rows) != len(set(identities)):
            raise RagChatError("RAG_CITATION_SOURCE_STALE")
        governance = DocumentGovernanceService()
        persisted: dict[str, ConversationCitation] = {}
        for order, item in enumerate(response.citations, start=1):
            chunk, document = rows[(item.document_id, item.chunk_index)]
            source_text = evidence_chunks.get((item.document_id, item.chunk_index))
            if source_text is None or source_text != chunk.text:
                raise RagChatError("RAG_CITATION_SOURCE_STALE")
            if not governance.evaluate_rag_eligibility(
                DocumentGovernanceSnapshot.from_document(document)
            ).eligible:
                raise RagChatError("RAG_CITATION_SOURCE_STALE")
            quote, truncated = self._direct_quote(source_text)
            citation = ConversationCitation(
                assistant_message_id=assistant.id,
                marker=item.marker,
                document_id=document.id,
                display_name_snapshot=document.display_name,
                document_type_snapshot=document.document_type.value,
                knowledge_layer_snapshot=document.knowledge_layer.value,
                issuing_entity_snapshot=document.issuing_entity,
                document_date_snapshot=document.published_at,
                start_page=chunk.start_page,
                end_page=chunk.end_page,
                chunk_index=chunk.chunk_index,
                locator_label=None,
                direct_quote=quote,
                quote_truncated=truncated,
                citation_order=order,
            )
            self.session.add(citation)
            persisted[item.marker] = citation
        await self.session.flush()
        return persisted

    async def _persist_claims(
        self,
        assistant: ConversationMessage,
        answer: str,
        citations: dict[str, ConversationCitation],
    ) -> None:
        order = 0
        for element in _CLAIM_SPLIT.split(answer):
            markers = tuple(dict.fromkeys(_MARKER_PATTERN.findall(element)))
            statement = _MARKER_PATTERN.sub("", element).strip(" \t\r\n-*•")
            if not statement or not markers:
                continue
            order += 1
            claim = ConversationClaim(
                assistant_message_id=assistant.id,
                statement=statement[: settings.conversation_claim_max_chars],
                claim_order=order,
                supported=True,
            )
            self.session.add(claim)
            await self.session.flush()
            for marker in markers:
                citation = citations.get(marker)
                if citation is None:
                    raise RagChatError("RAG_CITATION_OUTPUT_INVALID")
                self.session.add(
                    ConversationClaimCitation(claim_id=claim.id, citation_id=citation.id)
                )

    async def _persist_failure(
        self, conversation: Conversation, sequence: int, error_code: str
    ) -> None:
        now = self._now()
        await self.repository.add_message(
            ConversationMessage(
                conversation_id=conversation.id,
                role=ConversationMessageRole.ASSISTANT,
                content="La operación no pudo completarse.",
                sequence_number=sequence,
                public_status=ConversationMessageStatus.FAILED,
                coverage_status=ConversationCoverageStatus.INSUFFICIENT,
                created_at=now,
                completed_at=now,
                error_code=error_code,
            )
        )
        conversation.last_activity_at = now
        conversation.updated_at = now
        self._renew(conversation, now)

    async def _context(self, conversation_id: UUID) -> tuple[ConversationContextMessage, ...]:
        rows = await self.repository.recent_messages(
            conversation_id, limit=settings.conversation_context_max_messages
        )
        remaining = settings.conversation_context_max_chars
        selected: list[ConversationContextMessage] = []
        for row in reversed(rows):
            content = row.content[:remaining]
            if not content:
                break
            selected.append(ConversationContextMessage(role=row.role.value, content=content))
            remaining -= len(content)
        return tuple(reversed(selected))

    async def _owned(
        self, conversation_id: UUID, principal: ConversationPrincipal
    ) -> Conversation:
        conversation = await self.repository.get_owned(
            conversation_id, principal, now=self._now()
        )
        if conversation is None:
            raise ConversationError("CONVERSATION_NOT_FOUND")
        return conversation

    async def _turn(
        self,
        conversation: Conversation,
        user: ConversationMessage,
        assistant: ConversationMessage,
    ) -> ConversationTurnResponse:
        messages = await self._message_reads([user, assistant])
        count = await self.repository.message_count(conversation.id)
        return ConversationTurnResponse(
            conversation=self._conversation_read(conversation, count),
            user_message=messages[0],
            assistant_message=messages[1],
        )

    async def _message_reads(
        self, messages: list[ConversationMessage]
    ) -> list[ConversationMessageRead]:
        assistant_ids = [row.id for row in messages if row.role is ConversationMessageRole.ASSISTANT]
        citations = await self.repository.citations_for_messages(assistant_ids)
        claims, links = await self.repository.claims_for_messages(assistant_ids)
        document_ids = [item.document_id for values in citations.values() for item in values]
        available = await self.repository.current_document_ids(document_ids)
        result: list[ConversationMessageRead] = []
        for row in messages:
            citation_rows = citations.get(row.id, [])
            claim_rows = claims.get(row.id, [])
            result.append(
                ConversationMessageRead(
                    id=row.id,
                    role=row.role.value,
                    content=row.content,
                    sequence_number=row.sequence_number,
                    public_status=row.public_status.value if row.public_status else None,
                    coverage_status=row.coverage_status.value if row.coverage_status else None,
                    created_at=row.created_at,
                    completed_at=row.completed_at,
                    error_code=row.error_code,
                    citations=[self._citation_read(item, item.document_id in available) for item in citation_rows],
                    claims=[
                        ConversationClaimRead(
                            id=item.id,
                            statement=item.statement,
                            claim_order=item.claim_order,
                            supported=item.supported,
                            citation_ids=links.get(item.id, []),
                        )
                        for item in claim_rows
                    ],
                    unsupported_points=[
                        item.statement for item in claim_rows if not item.supported
                    ],
                )
            )
        return result

    @staticmethod
    def _citation_read(
        item: ConversationCitation, available: bool
    ) -> ConversationCitationRead:
        return ConversationCitationRead(
            id=item.id,
            marker=item.marker,
            document_id=item.document_id,
            display_name=item.display_name_snapshot,
            document_type=DocumentType(item.document_type_snapshot),
            knowledge_layer=KnowledgeLayer(item.knowledge_layer_snapshot),
            issuing_entity=item.issuing_entity_snapshot,
            document_date=item.document_date_snapshot,
            start_page=item.start_page,
            end_page=item.end_page,
            chunk_index=item.chunk_index,
            locator_label=item.locator_label,
            direct_quote=item.direct_quote,
            quote_truncated=item.quote_truncated,
            citation_order=item.citation_order,
            document_available=available,
        )

    @staticmethod
    def _conversation_read(row: Conversation, count: int) -> ConversationRead:
        return ConversationRead(
            id=row.id,
            title=row.title,
            owner_type=row.owner_type.value,
            status=row.status.value,
            created_at=row.created_at,
            updated_at=row.updated_at,
            last_activity_at=row.last_activity_at,
            expires_at=row.expires_at,
            message_count=count,
        )

    @staticmethod
    def _direct_quote(text: str) -> tuple[str, bool]:
        limit = settings.conversation_direct_quote_max_chars
        if len(text) <= limit:
            return text, False
        candidate = text[: limit + 1]
        boundaries = [candidate.rfind(separator) for separator in (" ", "\n", "\t")]
        cut = max(boundaries)
        if cut <= 0:
            cut = limit
        return text[:cut], True

    @staticmethod
    def _title(question: str) -> str:
        cleaned = "".join(
            " " if character.isspace() else character
            for character in question
            if (
                character.isspace()
                or not unicodedata.category(character).startswith("C")
            )
            and character not in "<>"
        )
        plain = " ".join(cleaned.split())
        if not plain:
            return "Nueva conversación"
        limit = settings.conversation_title_max_length
        if len(plain) <= limit:
            return plain
        return f"{plain[: limit - 1].rstrip()}…"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _expiry(now: datetime) -> datetime:
        return now + timedelta(days=settings.conversation_guest_retention_days)

    def _renew(self, conversation: Conversation, now: datetime) -> None:
        if conversation.owner_type.value == "guest":
            conversation.expires_at = self._expiry(now)
