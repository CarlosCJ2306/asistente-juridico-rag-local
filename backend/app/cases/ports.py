"""Ports mínimos del futuro dominio Case; no contienen implementaciones."""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from app.cases.contracts import (
    DocumentBatchReference,
    ExtractionReference,
    LegacyHpnReference,
    LegacyNetworkReference,
    ScopedRetrievalQuery,
    ScopedRetrievalResult,
)


@runtime_checkable
class DocumentAccessPort(Protocol):
    async def resolve_documents(
        self, document_ids: tuple[UUID, ...]
    ) -> DocumentBatchReference: ...


@runtime_checkable
class DocumentExtractionPort(Protocol):
    async def get_status(self, document_id: UUID) -> ExtractionReference: ...

    async def request_extraction(self, document_id: UUID) -> ExtractionReference: ...


@runtime_checkable
class ScopedRetrievalPort(Protocol):
    async def search(
        self,
        request: ScopedRetrievalQuery,
        *,
        request_id: str | None = None,
    ) -> ScopedRetrievalResult: ...


@runtime_checkable
class LegacyHpnPort(Protocol):
    async def get_matrix(self, matrix_id: UUID) -> LegacyHpnReference: ...


@runtime_checkable
class LegacyLegalNetworkPort(Protocol):
    async def project(
        self,
        matrix_id: UUID,
        *,
        request_id: str | None = None,
    ) -> LegacyNetworkReference: ...
