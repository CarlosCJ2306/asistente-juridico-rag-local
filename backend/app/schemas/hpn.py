"""Contratos públicos de la Matriz HPN manual."""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import settings
from app.database.models.document import DocumentType
from app.database.models.hpn import (
    HpnMatrixStatus,
    HpnNodeType,
    HpnRelationType,
    HpnReviewStatus,
)


def _clean(value: str, *, allow_empty: bool = False) -> str:
    normalized = value.strip()
    if not normalized and not allow_empty:
        raise ValueError("HPN_VALIDATION_ERROR")
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise ValueError("HPN_VALIDATION_ERROR")
    return normalized


class HpnBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class HpnMatrixCreate(HpnBaseModel):
    title: str = Field(min_length=1, max_length=settings.hpn_matrix_title_max_length)
    description: str | None = Field(
        default=None, max_length=settings.hpn_matrix_description_max_length
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _clean(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return None if value is None else _clean(value)


class HpnMatrixUpdate(HpnBaseModel):
    title: str | None = Field(default=None, max_length=settings.hpn_matrix_title_max_length)
    description: str | None = Field(
        default=None, max_length=settings.hpn_matrix_description_max_length
    )
    status: HpnMatrixStatus | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return None if value is None else _clean(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return None if value is None else _clean(value)

    @model_validator(mode="after")
    def reject_null_title(self) -> "HpnMatrixUpdate":
        for name in ("title", "status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError("HPN_VALIDATION_ERROR")
        return self


class HpnMatrixRead(HpnBaseModel):
    id: UUID
    title: str
    description: str | None
    status: HpnMatrixStatus
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_timestamps(self) -> "HpnMatrixRead":
        if self.updated_at < self.created_at:
            raise ValueError("HPN_VALIDATION_ERROR")
        return self


class HpnMatrixList(HpnBaseModel):
    items: list[HpnMatrixRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class HpnNodeCreate(HpnBaseModel):
    node_type: HpnNodeType
    title: str = Field(min_length=1, max_length=settings.hpn_node_title_max_length)
    statement: str = Field(min_length=1, max_length=settings.hpn_node_statement_max_length)
    review_status: HpnReviewStatus = HpnReviewStatus.DRAFT
    display_order: int = Field(ge=1)

    @field_validator("title", "statement")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _clean(value)

    @field_validator("display_order", mode="before")
    @classmethod
    def reject_boolean(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("HPN_VALIDATION_ERROR")
        return value


class HpnNodeUpdate(HpnBaseModel):
    title: str | None = Field(default=None, max_length=settings.hpn_node_title_max_length)
    statement: str | None = Field(
        default=None, max_length=settings.hpn_node_statement_max_length
    )
    review_status: HpnReviewStatus | None = None
    display_order: int | None = Field(default=None, ge=1)

    @field_validator("title", "statement")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return None if value is None else _clean(value)

    @field_validator("display_order", mode="before")
    @classmethod
    def reject_boolean(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("HPN_VALIDATION_ERROR")
        return value

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "HpnNodeUpdate":
        for name in ("title", "statement", "display_order", "review_status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError("HPN_VALIDATION_ERROR")
        return self


class HpnSourceCreate(HpnBaseModel):
    document_id: UUID
    chunk_index: int = Field(ge=1)

    @field_validator("chunk_index", mode="before")
    @classmethod
    def reject_boolean(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("HPN_VALIDATION_ERROR")
        return value


class HpnSourceRead(HpnBaseModel):
    source_id: UUID
    document_id: UUID
    document_name: str = Field(min_length=1, max_length=settings.hpn_source_name_max_length)
    document_type: DocumentType
    chunk_index: int = Field(ge=1)
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)
    source_status: Literal["valid", "stale", "unavailable"]
    linked_at: datetime

    @model_validator(mode="after")
    def validate_pages(self) -> "HpnSourceRead":
        if self.end_page < self.start_page:
            raise ValueError("HPN_VALIDATION_ERROR")
        return self


class HpnNodeRead(HpnBaseModel):
    id: UUID
    node_type: HpnNodeType
    title: str
    statement: str
    review_status: HpnReviewStatus
    display_order: int = Field(ge=1)
    sources: list[HpnSourceRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_timestamps(self) -> "HpnNodeRead":
        if self.updated_at < self.created_at:
            raise ValueError("HPN_VALIDATION_ERROR")
        return self


class HpnRelationCreate(HpnBaseModel):
    source_node_id: UUID
    target_node_id: UUID
    relation_type: HpnRelationType
    rationale: str | None = Field(
        default=None, max_length=settings.hpn_relation_rationale_max_length
    )
    review_status: HpnReviewStatus = HpnReviewStatus.DRAFT

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, value: str | None) -> str | None:
        return None if value is None else _clean(value)


class HpnRelationUpdate(HpnBaseModel):
    rationale: str | None = Field(
        default=None, max_length=settings.hpn_relation_rationale_max_length
    )
    review_status: HpnReviewStatus | None = None

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, value: str | None) -> str | None:
        return None if value is None else _clean(value)

    @model_validator(mode="after")
    def reject_null_review_status(self) -> "HpnRelationUpdate":
        if "review_status" in self.model_fields_set and self.review_status is None:
            raise ValueError("HPN_VALIDATION_ERROR")
        return self


class HpnRelationRead(HpnBaseModel):
    id: UUID
    source_node_id: UUID
    target_node_id: UUID
    relation_type: HpnRelationType
    rationale: str | None
    review_status: HpnReviewStatus
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_timestamps(self) -> "HpnRelationRead":
        if self.updated_at < self.created_at:
            raise ValueError("HPN_VALIDATION_ERROR")
        return self


class HpnValidationSummary(HpnBaseModel):
    matrix_id: UUID
    valid_for_review: bool
    fact_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    norm_count: int = Field(ge=0)
    relation_count: int = Field(ge=0)
    draft_node_count: int = Field(ge=0)
    rejected_node_count: int = Field(ge=0)
    draft_relation_count: int = Field(ge=0)
    stale_source_count: int = Field(ge=0)
    unavailable_source_count: int = Field(ge=0)
    evidence_without_valid_source_count: int = Field(ge=0)
    norm_without_valid_source_count: int = Field(ge=0)


class HpnMatrixDetail(HpnBaseModel):
    matrix: HpnMatrixRead
    nodes: list[HpnNodeRead]
    relations: list[HpnRelationRead]
    validation_summary: HpnValidationSummary


class HpnReviewRequest(HpnBaseModel):
    status: Literal[HpnMatrixStatus.REVIEWED]


class HpnPageParams(HpnBaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("page", "page_size", mode="before")
    @classmethod
    def reject_boolean(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("HPN_VALIDATION_ERROR")
        return value

    @model_validator(mode="after")
    def valid(self) -> "HpnPageParams":
        return self
