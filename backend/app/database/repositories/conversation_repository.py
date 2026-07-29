"""Persistencia aislada de conversaciones y snapshots de evidencia."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.conversation import (
    Conversation,
    ConversationCitation,
    ConversationClaim,
    ConversationClaimCitation,
    ConversationMessage,
    ConversationMessageRole,
    ConversationOwnerType,
    ConversationStatus,
)
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.services.conversation_principal import ConversationPrincipal


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _owned(principal: ConversationPrincipal, now: datetime):
        statement = select(Conversation).where(Conversation.deleted_at.is_(None))
        if principal.owner_type == "guest":
            return statement.where(
                Conversation.owner_type == ConversationOwnerType.GUEST,
                Conversation.guest_session_hash == principal.guest_session_hash,
                Conversation.expires_at > now,
            )
        return statement.where(
            Conversation.owner_type == ConversationOwnerType.ACCOUNT,
            Conversation.user_id == principal.user_id,
        )

    async def create_guest(
        self,
        *,
        session_hash: str,
        title: str,
        now: datetime,
        expires_at: datetime,
    ) -> Conversation:
        conversation = Conversation(
            title=title,
            owner_type=ConversationOwnerType.GUEST,
            guest_session_hash=session_hash,
            status=ConversationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            last_activity_at=now,
            expires_at=expires_at,
            schema_version=1,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get_owned(
        self,
        conversation_id: UUID,
        principal: ConversationPrincipal,
        *,
        now: datetime,
    ) -> Conversation | None:
        return await self.session.scalar(
            self._owned(principal, now).where(Conversation.id == conversation_id)
        )

    async def list_owned(
        self,
        principal: ConversationPrincipal,
        *,
        now: datetime,
        status: ConversationStatus,
        offset: int,
        limit: int,
    ) -> tuple[list[Conversation], int]:
        owned = self._owned(principal, now).where(Conversation.status == status)
        count_statement = select(func.count()).select_from(owned.subquery())
        total = int((await self.session.scalar(count_statement)) or 0)
        rows = await self.session.scalars(
            owned.order_by(Conversation.last_activity_at.desc(), Conversation.id)
            .offset(offset)
            .limit(limit)
        )
        return list(rows.all()), total

    async def messages(self, conversation_id: UUID) -> list[ConversationMessage]:
        rows = await self.session.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.sequence_number, ConversationMessage.id)
        )
        return list(rows.all())

    async def recent_messages(
        self, conversation_id: UUID, *, limit: int
    ) -> list[ConversationMessage]:
        rows = await self.session.scalars(
            select(ConversationMessage)
            .where(
                ConversationMessage.conversation_id == conversation_id,
                or_(
                    ConversationMessage.role == ConversationMessageRole.USER,
                    ConversationMessage.public_status != "failed",
                ),
            )
            .order_by(ConversationMessage.sequence_number.desc())
            .limit(limit)
        )
        return list(reversed(rows.all()))

    async def message_count(self, conversation_id: UUID) -> int:
        return int(
            (await self.session.scalar(
                select(func.count())
                .select_from(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
            ))
            or 0
        )

    async def message_counts(self, conversation_ids: list[UUID]) -> dict[UUID, int]:
        if not conversation_ids:
            return {}
        rows = await self.session.execute(
            select(ConversationMessage.conversation_id, func.count())
            .where(ConversationMessage.conversation_id.in_(conversation_ids))
            .group_by(ConversationMessage.conversation_id)
        )
        return {conversation_id: int(count) for conversation_id, count in rows}

    async def next_sequence(self, conversation_id: UUID) -> int:
        current = await self.session.scalar(
            select(func.max(ConversationMessage.sequence_number)).where(
                ConversationMessage.conversation_id == conversation_id
            )
        )
        return int(current or 0) + 1

    async def add_message(self, message: ConversationMessage) -> ConversationMessage:
        self.session.add(message)
        await self.session.flush()
        return message

    async def find_idempotent_user_message(
        self, conversation_id: UUID, key: str
    ) -> ConversationMessage | None:
        return await self.session.scalar(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.idempotency_key == key,
                ConversationMessage.role == ConversationMessageRole.USER,
            )
        )

    async def assistant_after(
        self, user_message: ConversationMessage
    ) -> ConversationMessage | None:
        return await self.session.scalar(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == user_message.conversation_id,
                ConversationMessage.sequence_number == user_message.sequence_number + 1,
                ConversationMessage.role == ConversationMessageRole.ASSISTANT,
            )
        )

    async def citations_for_messages(
        self, message_ids: list[UUID]
    ) -> dict[UUID, list[ConversationCitation]]:
        if not message_ids:
            return {}
        rows = await self.session.scalars(
            select(ConversationCitation)
            .where(ConversationCitation.assistant_message_id.in_(message_ids))
            .order_by(
                ConversationCitation.assistant_message_id,
                ConversationCitation.citation_order,
            )
        )
        result: dict[UUID, list[ConversationCitation]] = {}
        for citation in rows.all():
            result.setdefault(citation.assistant_message_id, []).append(citation)
        return result

    async def claims_for_messages(
        self, message_ids: list[UUID]
    ) -> tuple[dict[UUID, list[ConversationClaim]], dict[UUID, list[UUID]]]:
        if not message_ids:
            return {}, {}
        claims = list((await self.session.scalars(
            select(ConversationClaim)
            .where(ConversationClaim.assistant_message_id.in_(message_ids))
            .order_by(ConversationClaim.assistant_message_id, ConversationClaim.claim_order)
        )).all())
        by_message: dict[UUID, list[ConversationClaim]] = {}
        for claim in claims:
            by_message.setdefault(claim.assistant_message_id, []).append(claim)
        links: dict[UUID, list[UUID]] = {}
        if claims:
            rows = await self.session.execute(
                select(
                    ConversationClaimCitation.claim_id,
                    ConversationClaimCitation.citation_id,
                ).where(
                    ConversationClaimCitation.claim_id.in_([claim.id for claim in claims])
                )
            )
            for claim_id, citation_id in rows:
                links.setdefault(claim_id, []).append(citation_id)
        return by_message, links

    async def current_source_rows(
        self, identities: list[tuple[UUID, int]]
    ) -> dict[tuple[UUID, int], tuple[DocumentChunk, Document]]:
        if not identities:
            return {}
        document_ids = list({document_id for document_id, _ in identities})
        rows = await self.session.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.document_id.in_(document_ids))
        )
        requested = set(identities)
        return {
            (chunk.document_id, chunk.chunk_index): (chunk, document)
            for chunk, document in rows
            if (chunk.document_id, chunk.chunk_index) in requested
        }

    async def current_document_ids(self, document_ids: list[UUID]) -> set[UUID]:
        if not document_ids:
            return set()
        rows = await self.session.scalars(
            select(Document.id).where(
                Document.id.in_(document_ids), Document.is_deleted.is_(False)
            )
        )
        return set(rows.all())

    async def delete_conversation(self, conversation: Conversation) -> None:
        await self.session.delete(conversation)

    async def hard_delete_expired_guests(self, *, now: datetime) -> int:
        result = await self.session.execute(
            delete(Conversation).where(
                Conversation.owner_type == ConversationOwnerType.GUEST,
                Conversation.expires_at <= now,
            )
        )
        return int(getattr(result, "rowcount", 0) or 0)
