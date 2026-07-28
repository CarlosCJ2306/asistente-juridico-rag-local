"""Contratos públicos sanitizados del procesamiento automático."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.database.models.document import KnowledgeLayer
from app.database.models.document_processing_job import (
    DocumentProcessingOperation,
    DocumentProcessingState,
)


class ProcessingJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID | None
    knowledge_layer: KnowledgeLayer
    public_name: str
    operation: DocumentProcessingOperation
    state: DocumentProcessingState
    attempts: int
    error_code: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class ProcessingQueueSummary(BaseModel):
    queued: int = Field(ge=0)
    processing: int = Field(ge=0)
    completed_recently: int = Field(ge=0)
    failed: int = Field(ge=0)
    quarantined: int = Field(ge=0)


class ProcessingJobsPage(BaseModel):
    items: list[ProcessingJobRead]
    total: int = Field(ge=0)


class ProcessingRetryResponse(BaseModel):
    job_id: UUID
    state: DocumentProcessingState
