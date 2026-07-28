"""Persistencia de la cola local sin exponer rutas internas."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import KnowledgeLayer
from app.database.models.document_processing_job import (
    ACTIVE_PROCESSING_STATES,
    DocumentProcessingJob,
    DocumentProcessingOperation,
    DocumentProcessingState,
)


class DocumentProcessingJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_inbox_job(
        self,
        *,
        knowledge_layer: KnowledgeLayer,
        public_name: str,
        inbox_relative_path: str,
    ) -> DocumentProcessingJob | None:
        existing = await self.session.scalar(
            select(DocumentProcessingJob).where(
                DocumentProcessingJob.inbox_relative_path == inbox_relative_path,
                DocumentProcessingJob.state.in_(ACTIVE_PROCESSING_STATES),
            )
        )
        if existing is not None:
            return None
        job = DocumentProcessingJob(
            knowledge_layer=knowledge_layer,
            public_name=public_name,
            operation=DocumentProcessingOperation.INBOX_IMPORT,
            state=DocumentProcessingState.QUEUED,
            inbox_relative_path=inbox_relative_path,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def create_upload_job(
        self,
        *,
        document_id: UUID,
        knowledge_layer: KnowledgeLayer,
        public_name: str,
    ) -> DocumentProcessingJob:
        existing = await self.session.scalar(
            select(DocumentProcessingJob).where(
                DocumentProcessingJob.document_id == document_id,
                DocumentProcessingJob.state.in_(ACTIVE_PROCESSING_STATES),
            )
        )
        if existing is not None:
            return existing
        job = DocumentProcessingJob(
            document_id=document_id,
            knowledge_layer=knowledge_layer,
            public_name=public_name,
            operation=DocumentProcessingOperation.UPLOAD_PIPELINE,
            state=DocumentProcessingState.QUEUED,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get(self, job_id: UUID) -> DocumentProcessingJob | None:
        return await self.session.get(DocumentProcessingJob, job_id)

    async def next_queued(self) -> DocumentProcessingJob | None:
        return await self.session.scalar(
            select(DocumentProcessingJob)
            .where(DocumentProcessingJob.state == DocumentProcessingState.QUEUED)
            .order_by(DocumentProcessingJob.created_at, DocumentProcessingJob.id)
            .limit(1)
        )

    async def waiting_for_index(self) -> list[DocumentProcessingJob]:
        rows = await self.session.scalars(
            select(DocumentProcessingJob)
            .where(
                DocumentProcessingJob.state
                == DocumentProcessingState.WAITING_FOR_INDEX
            )
            .order_by(DocumentProcessingJob.created_at, DocumentProcessingJob.id)
        )
        return list(rows.all())

    async def recent(self, *, limit: int) -> list[DocumentProcessingJob]:
        rows = await self.session.scalars(
            select(DocumentProcessingJob)
            .order_by(DocumentProcessingJob.updated_at.desc(), DocumentProcessingJob.id)
            .limit(limit)
        )
        return list(rows.all())

    async def counts(self) -> dict[DocumentProcessingState, int]:
        rows = await self.session.execute(
            select(DocumentProcessingJob.state, func.count())
            .group_by(DocumentProcessingJob.state)
        )
        return {state: int(count) for state, count in rows}

    async def transition(
        self,
        job: DocumentProcessingJob,
        state: DocumentProcessingState,
        *,
        error_code: str | None = None,
        document_id: UUID | None = None,
        increment_attempts: bool = False,
    ) -> None:
        job.state = state
        job.error_code = error_code
        if document_id is not None:
            job.document_id = document_id
        if increment_attempts:
            job.attempts += 1
        job.updated_at = datetime.now(timezone.utc)
        job.completed_at = (
            datetime.now(timezone.utc)
            if state
            in {
                DocumentProcessingState.COMPLETED,
                DocumentProcessingState.FAILED,
                DocumentProcessingState.QUARANTINED,
            }
            else None
        )
        await self.session.flush()

    async def recover_incomplete(self) -> int:
        rows = await self.session.scalars(
            select(DocumentProcessingJob).where(
                DocumentProcessingJob.state.in_(
                    tuple(
                        state
                        for state in ACTIVE_PROCESSING_STATES
                        if state is not DocumentProcessingState.QUEUED
                    )
                )
            )
        )
        jobs = list(rows.all())
        now = datetime.now(timezone.utc)
        for job in jobs:
            job.state = DocumentProcessingState.QUEUED
            job.error_code = None
            job.updated_at = now
        await self.session.flush()
        return len(jobs)

    async def retry(self, job: DocumentProcessingJob, *, max_attempts: int) -> bool:
        if (
            job.state is not DocumentProcessingState.FAILED
            or job.attempts >= max_attempts
        ):
            return False
        await self.transition(job, DocumentProcessingState.QUEUED)
        return True
