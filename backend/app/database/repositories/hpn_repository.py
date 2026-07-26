"""Repositorio transaccional de matrices HPN manuales."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.hpn import HpnMatrix, HpnNode, HpnNodeSource, HpnRelation
from app.database.repositories.semantic_chunk_repository import ActiveChunk


class HpnRepository:
    """Acceso a SQLite sin commits implícitos."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def matrix(self, matrix_id: UUID) -> HpnMatrix | None:
        return await self.session.scalar(
            select(HpnMatrix).where(HpnMatrix.id == matrix_id, HpnMatrix.deleted_at.is_(None))
        )

    async def matrix_including_deleted(self, matrix_id: UUID) -> HpnMatrix | None:
        return await self.session.scalar(select(HpnMatrix).where(HpnMatrix.id == matrix_id))

    async def matrices(self, *, offset: int, limit: int) -> list[HpnMatrix]:
        rows = await self.session.scalars(
            select(HpnMatrix)
            .where(HpnMatrix.deleted_at.is_(None))
            .order_by(HpnMatrix.updated_at.desc(), HpnMatrix.id)
            .offset(offset)
            .limit(limit)
        )
        return list(rows.all())

    async def matrix_count(self) -> int:
        return int(
            (await self.session.scalar(
                select(func.count()).select_from(HpnMatrix).where(HpnMatrix.deleted_at.is_(None))
            ))
            or 0
        )

    async def node(self, matrix_id: UUID, node_id: UUID) -> HpnNode | None:
        return await self.session.scalar(
            select(HpnNode).where(
                HpnNode.id == node_id,
                HpnNode.matrix_id == matrix_id,
                HpnNode.deleted_at.is_(None),
            )
        )

    async def nodes(self, matrix_id: UUID) -> list[HpnNode]:
        rows = await self.session.scalars(
            select(HpnNode)
            .where(HpnNode.matrix_id == matrix_id, HpnNode.deleted_at.is_(None))
            .order_by(HpnNode.display_order, HpnNode.id)
        )
        return list(rows.all())

    async def node_count(self, matrix_id: UUID) -> int:
        return int((await self.session.scalar(
            select(func.count()).select_from(HpnNode).where(
                HpnNode.matrix_id == matrix_id, HpnNode.deleted_at.is_(None)
            )
        )) or 0)

    async def source(self, node_id: UUID, source_id: UUID) -> HpnNodeSource | None:
        return await self.session.scalar(
            select(HpnNodeSource).where(
                HpnNodeSource.id == source_id,
                HpnNodeSource.node_id == node_id,
                HpnNodeSource.deleted_at.is_(None),
            )
        )

    async def sources(self, node_ids: list[UUID]) -> list[HpnNodeSource]:
        if not node_ids:
            return []
        rows = await self.session.scalars(
            select(HpnNodeSource)
            .where(HpnNodeSource.node_id.in_(node_ids), HpnNodeSource.deleted_at.is_(None))
            .order_by(HpnNodeSource.created_at, HpnNodeSource.id)
        )
        return list(rows.all())

    async def source_count(self, node_id: UUID) -> int:
        return int((await self.session.scalar(
            select(func.count()).select_from(HpnNodeSource).where(
                HpnNodeSource.node_id == node_id, HpnNodeSource.deleted_at.is_(None)
            )
        )) or 0)

    async def relation(self, matrix_id: UUID, relation_id: UUID) -> HpnRelation | None:
        return await self.session.scalar(
            select(HpnRelation).where(
                HpnRelation.id == relation_id,
                HpnRelation.matrix_id == matrix_id,
                HpnRelation.deleted_at.is_(None),
            )
        )

    async def relations(self, matrix_id: UUID) -> list[HpnRelation]:
        rows = await self.session.scalars(
            select(HpnRelation)
            .where(HpnRelation.matrix_id == matrix_id, HpnRelation.deleted_at.is_(None))
            .order_by(HpnRelation.created_at, HpnRelation.id)
        )
        return list(rows.all())

    async def relation_count(self, matrix_id: UUID) -> int:
        return int((await self.session.scalar(
            select(func.count()).select_from(HpnRelation).where(
                HpnRelation.matrix_id == matrix_id, HpnRelation.deleted_at.is_(None)
            )
        )) or 0)

    async def active_chunk_by_locator(self, document_id: UUID, chunk_index: int) -> ActiveChunk | None:
        row = (
            await self.session.execute(
                select(DocumentChunk, Document.document_type, Document.original_filename)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(
                    Document.id == document_id,
                    Document.is_deleted.is_(False),
                    DocumentChunk.chunk_index == chunk_index,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        chunk, document_type, name = row
        return ActiveChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_type=document_type,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            start_page=chunk.start_page,
            end_page=chunk.end_page,
            document_name=name,
        )

    async def active_chunks_by_ids(self, chunk_ids: list[UUID]) -> dict[UUID, ActiveChunk]:
        if not chunk_ids:
            return {}
        rows = (
            await self.session.execute(
                select(DocumentChunk, Document.document_type, Document.original_filename)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(DocumentChunk.id.in_(chunk_ids), Document.is_deleted.is_(False))
            )
        ).all()
        return {
            chunk.id: ActiveChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_type=document_type,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                start_page=chunk.start_page,
                end_page=chunk.end_page,
                document_name=name,
            )
            for chunk, document_type, name in rows
        }

    async def soft_delete_matrix_tree(self, matrix_id: UUID) -> None:
        now = datetime.now(timezone.utc)
        node_ids = select(HpnNode.id).where(HpnNode.matrix_id == matrix_id)
        await self.session.execute(
            update(HpnNodeSource)
            .where(HpnNodeSource.node_id.in_(node_ids), HpnNodeSource.deleted_at.is_(None))
            .values(deleted_at=now)
        )
        await self.session.execute(
            update(HpnRelation)
            .where(HpnRelation.matrix_id == matrix_id, HpnRelation.deleted_at.is_(None))
            .values(deleted_at=now)
        )
        await self.session.execute(
            update(HpnNode)
            .where(HpnNode.matrix_id == matrix_id, HpnNode.deleted_at.is_(None))
            .values(deleted_at=now)
        )
        await self.session.execute(
            update(HpnMatrix)
            .where(HpnMatrix.id == matrix_id)
            .values(deleted_at=now, updated_at=now)
        )

    async def soft_delete_node_tree(self, matrix_id: UUID, node_id: UUID) -> None:
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(HpnNodeSource)
            .where(HpnNodeSource.node_id == node_id, HpnNodeSource.deleted_at.is_(None))
            .values(deleted_at=now)
        )
        await self.session.execute(
            update(HpnRelation)
            .where(
                HpnRelation.matrix_id == matrix_id,
                HpnRelation.deleted_at.is_(None),
                or_(
                    HpnRelation.source_node_id == node_id,
                    HpnRelation.target_node_id == node_id,
                ),
            )
            .values(deleted_at=now)
        )
        await self.session.execute(
            update(HpnNode).where(HpnNode.id == node_id).values(deleted_at=now)
        )
