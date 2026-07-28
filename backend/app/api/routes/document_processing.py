"""Estado público y reintentos controlados del procesamiento automático."""

from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.models.document_processing_job import DocumentProcessingState
from app.database.repositories.document_processing_job_repository import (
    DocumentProcessingJobRepository,
)
from app.database.session import database_session_manager, get_db_session
from app.schemas.document_processing import (
    ProcessingJobRead,
    ProcessingJobsPage,
    ProcessingQueueSummary,
    ProcessingRetryResponse,
)
from app.services.document_automation_service import get_document_automation_service


router = APIRouter(prefix="/documents/processing", tags=["document-processing"])


@router.get("/summary", response_model=ProcessingQueueSummary)
async def processing_summary(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProcessingQueueSummary:
    repository = DocumentProcessingJobRepository(session)
    counts = await repository.counts()
    recent = await repository.recent(limit=settings.document_processing_recent_limit)
    processing_states = {
        DocumentProcessingState.DETECTING,
        DocumentProcessingState.REGISTERING,
        DocumentProcessingState.EXTRACTING,
        DocumentProcessingState.WAITING_FOR_INDEX,
        DocumentProcessingState.INDEXING,
    }
    return ProcessingQueueSummary(
        queued=counts.get(DocumentProcessingState.QUEUED, 0),
        processing=sum(counts.get(state, 0) for state in processing_states),
        completed_recently=sum(
            job.state is DocumentProcessingState.COMPLETED for job in recent
        ),
        failed=counts.get(DocumentProcessingState.FAILED, 0),
        quarantined=counts.get(DocumentProcessingState.QUARANTINED, 0),
    )


@router.get("/jobs", response_model=ProcessingJobsPage)
async def processing_jobs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProcessingJobsPage:
    jobs = await DocumentProcessingJobRepository(session).recent(limit=limit)
    return ProcessingJobsPage(
        items=[ProcessingJobRead.model_validate(job) for job in jobs],
        total=len(jobs),
    )


@router.get("/jobs/{job_id}", response_model=ProcessingJobRead)
async def processing_job(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProcessingJobRead:
    job = await DocumentProcessingJobRepository(session).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="DOCUMENT_PROCESSING_JOB_NOT_FOUND")
    return ProcessingJobRead.model_validate(job)


@router.post("/jobs/{job_id}/retry", response_model=ProcessingRetryResponse)
async def retry_processing_job(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProcessingRetryResponse:
    repository = DocumentProcessingJobRepository(session)
    job = await repository.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="DOCUMENT_PROCESSING_JOB_NOT_FOUND")
    if not await repository.retry(
        job, max_attempts=settings.document_processing_max_retries
    ):
        raise HTTPException(status_code=409, detail="DOCUMENT_PROCESSING_RETRY_NOT_ALLOWED")
    await session.commit()
    automation = get_document_automation_service(
        database_session_manager.get_session_factory()
    )
    asyncio.create_task(automation.run_once())
    return ProcessingRetryResponse(job_id=job.id, state=job.state)
