"""Contratos públicos cerrados del núcleo Case."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.cases.domain import (
    CASE_DESCRIPTION_MAX_LENGTH,
    CASE_TITLE_MAX_LENGTH,
    CaseRetentionMode,
    normalize_case_description,
    normalize_case_title,
)


class CaseBaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseCreate(CaseBaseSchema):
    title: str = Field(min_length=1, max_length=CASE_TITLE_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=CASE_DESCRIPTION_MAX_LENGTH)
    retention_mode: CaseRetentionMode

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return normalize_case_title(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_case_description(value)


class CaseUpdate(CaseBaseSchema):
    title: str | None = Field(default=None, max_length=CASE_TITLE_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=CASE_DESCRIPTION_MAX_LENGTH)
    expected_version: int = Field(ge=1)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return None if value is None else normalize_case_title(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_case_description(value)

    @model_validator(mode="after")
    def require_change(self) -> "CaseUpdate":
        if not ({"title", "description"} & self.model_fields_set):
            raise ValueError("CASE_UPDATE_EMPTY")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("CASE_TITLE_INVALID")
        return self


class CaseActionRequest(CaseBaseSchema):
    expected_version: int = Field(ge=1)


class CasePublic(CaseBaseSchema):
    public_id: UUID
    title: str
    description: str | None
    status: str
    retention_mode: CaseRetentionMode
    expires_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    read_only: bool
    requires_professional_review: bool = True


class CaseListResponse(CaseBaseSchema):
    items: list[CasePublic]
    page: int
    page_size: int
    total: int
    total_pages: int
