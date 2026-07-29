"""Contratos públicos cerrados de pertenencia documental de Case."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.cases.document_domain import (
    CASE_DOCUMENT_MAX_ORDER,
    CaseDocumentAvailability,
    CaseDocumentPurpose,
    CaseDocumentWarning,
)
from app.database.models.document import (
    DocumentStatus,
    DocumentType,
    IndexStatus,
    KnowledgeLayer,
    RagEligibilityReason,
)


class CaseDocumentBaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseDocumentAttach(CaseDocumentBaseSchema):
    document_id: UUID
    purpose: CaseDocumentPurpose
    display_order: int = Field(default=0, ge=0, le=CASE_DOCUMENT_MAX_ORDER)
    expected_case_version: int = Field(ge=1)


class CaseDocumentUpdate(CaseDocumentBaseSchema):
    purpose: CaseDocumentPurpose | None = None
    display_order: int | None = Field(
        default=None, ge=0, le=CASE_DOCUMENT_MAX_ORDER
    )
    expected_case_version: int = Field(ge=1)
    expected_document_link_version: int = Field(ge=1)

    @model_validator(mode="after")
    def require_change(self) -> "CaseDocumentUpdate":
        if self.purpose is None and self.display_order is None:
            raise ValueError("CASE_DOCUMENT_UPDATE_EMPTY")
        return self


class CaseDocumentRemove(CaseDocumentBaseSchema):
    expected_case_version: int = Field(ge=1)
    expected_document_link_version: int = Field(ge=1)


class CaseDocumentPublic(CaseDocumentBaseSchema):
    association_id: UUID
    document_id: UUID
    display_name: str
    document_type: DocumentType
    knowledge_layer: KnowledgeLayer
    purpose: CaseDocumentPurpose
    display_order: int
    availability: CaseDocumentAvailability
    extraction_status: DocumentStatus
    index_status: IndexStatus
    rag_eligible: bool
    rag_ineligibility_reasons: list[RagEligibilityReason]
    warnings: list[CaseDocumentWarning]
    expires_at: datetime | None
    version: int
    case_version: int
    attached_at: datetime
    updated_at: datetime
    read_only: bool


class CaseDocumentListResponse(CaseDocumentBaseSchema):
    items: list[CaseDocumentPublic]
    page: int
    page_size: int
    total: int
    total_pages: int
    case_version: int
