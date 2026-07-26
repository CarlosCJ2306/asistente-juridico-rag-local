"""Orquestación manual de matrices HPN sin modelos ni índices derivados."""

from __future__ import annotations

import hashlib
import hmac
from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal, cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.Log import log_info, log_warning
from app.core.config import settings
from app.core.exceptions import HpnError
from app.core.source_sanitization import sanitize_document_name
from app.database.models.hpn import (
    HpnMatrix,
    HpnMatrixStatus,
    HpnNode,
    HpnNodeSource,
    HpnNodeType,
    HpnRelation,
    HpnRelationType,
    HpnReviewStatus,
)
from app.database.repositories.hpn_repository import HpnRepository
from app.database.repositories.semantic_chunk_repository import ActiveChunk
from app.schemas.hpn import (
    HpnMatrixCreate,
    HpnMatrixDetail,
    HpnMatrixList,
    HpnMatrixRead,
    HpnMatrixUpdate,
    HpnNodeCreate,
    HpnNodeRead,
    HpnNodeUpdate,
    HpnRelationCreate,
    HpnRelationRead,
    HpnRelationUpdate,
    HpnSourceCreate,
    HpnSourceRead,
    HpnValidationSummary,
)


RELATION_ENDPOINT_TYPES = {
    HpnRelationType.EVIDENCE_SUPPORTS_FACT: (HpnNodeType.EVIDENCE, HpnNodeType.FACT),
    HpnRelationType.EVIDENCE_CONTRADICTS_FACT: (HpnNodeType.EVIDENCE, HpnNodeType.FACT),
    HpnRelationType.NORM_APPLIES_TO_FACT: (HpnNodeType.NORM, HpnNodeType.FACT),
    HpnRelationType.NORM_LIMITS_FACT: (HpnNodeType.NORM, HpnNodeType.FACT),
}


class HpnService:
    """Mantiene HPN como datos introducidos y revisados por un profesional."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = HpnRepository(session)

    async def create_matrix(self, payload: HpnMatrixCreate) -> HpnMatrixRead:
        matrix = HpnMatrix(**payload.model_dump(), status=HpnMatrixStatus.DRAFT)
        self.session.add(matrix)
        await self._commit("HPN_CONFLICT")
        await self.session.refresh(matrix)
        self._log("hpn_matrix_create", entity="matrix", status=matrix.status.value)
        return HpnMatrixRead.model_validate(matrix)

    async def list_matrices(self, *, page: int, page_size: int) -> HpnMatrixList:
        items = await self.repository.matrices(offset=(page - 1) * page_size, limit=page_size)
        return HpnMatrixList(
            items=[HpnMatrixRead.model_validate(item) for item in items],
            total=await self.repository.matrix_count(),
            page=page,
            page_size=page_size,
        )

    async def detail(self, matrix_id: UUID) -> HpnMatrixDetail:
        matrix = await self._matrix(matrix_id)
        nodes = await self.repository.nodes(matrix_id)
        relations = await self.repository.relations(matrix_id)
        sources = await self.repository.sources([node.id for node in nodes])
        source_reads, statuses = await self._source_reads(sources)
        grouped: dict[UUID, list[HpnSourceRead]] = defaultdict(list)
        for source, source_read in zip(sources, source_reads, strict=True):
            grouped[source.node_id].append(source_read)
        summary = self._validation(matrix_id, nodes, relations, sources, statuses)
        return HpnMatrixDetail(
            matrix=HpnMatrixRead.model_validate(matrix),
            nodes=[self._node_read(node, grouped[node.id]) for node in nodes],
            relations=[HpnRelationRead.model_validate(item) for item in relations],
            validation_summary=summary,
        )

    async def update_matrix(self, matrix_id: UUID, payload: HpnMatrixUpdate) -> HpnMatrixRead:
        matrix = await self._matrix(matrix_id)
        if matrix.status == HpnMatrixStatus.ARCHIVED:
            raise HpnError("HPN_MATRIX_ARCHIVED")
        requested = payload.model_dump(exclude_unset=True)
        if not requested:
            return HpnMatrixRead.model_validate(matrix)
        requested_status = requested.pop("status", None)
        original_status = matrix.status
        requested = {
            key: value for key, value in requested.items() if getattr(matrix, key) != value
        }
        if not requested and (
            requested_status is None or requested_status == original_status
        ):
            return HpnMatrixRead.model_validate(matrix)
        if requested_status == HpnMatrixStatus.REVIEWED:
            summary = await self.validation(matrix_id)
            if not summary.valid_for_review:
                raise HpnError("HPN_REVIEW_INCOMPLETE")
            if original_status != HpnMatrixStatus.IN_REVIEW or requested:
                raise HpnError("HPN_CONFLICT")
        elif requested_status is not None:
            allowed = {
                HpnMatrixStatus.DRAFT: {
                    HpnMatrixStatus.DRAFT,
                    HpnMatrixStatus.IN_REVIEW,
                    HpnMatrixStatus.ARCHIVED,
                },
                HpnMatrixStatus.IN_REVIEW: {
                    HpnMatrixStatus.IN_REVIEW,
                    HpnMatrixStatus.ARCHIVED,
                },
                HpnMatrixStatus.REVIEWED: {
                    HpnMatrixStatus.IN_REVIEW,
                    HpnMatrixStatus.ARCHIVED,
                },
            }
            if requested_status not in allowed[original_status]:
                raise HpnError("HPN_CONFLICT")
        for key, value in requested.items():
            setattr(matrix, key, value)
        if requested and original_status == HpnMatrixStatus.REVIEWED:
            matrix.status = HpnMatrixStatus.IN_REVIEW
        if requested_status == HpnMatrixStatus.REVIEWED:
            matrix.status = HpnMatrixStatus.REVIEWED
        elif requested_status is not None:
            matrix.status = requested_status
        matrix.updated_at = datetime.now(timezone.utc)
        await self._commit("HPN_CONFLICT")
        return HpnMatrixRead.model_validate(matrix)

    async def delete_matrix(self, matrix_id: UUID) -> None:
        await self._matrix(matrix_id)
        await self.repository.soft_delete_matrix_tree(matrix_id)
        await self._commit("HPN_CONFLICT")
        self._log("hpn_matrix_delete", entity="matrix", status="deleted")

    async def create_node(self, matrix_id: UUID, payload: HpnNodeCreate) -> HpnNodeRead:
        matrix = await self._writable_matrix(matrix_id)
        if await self.repository.node_count(matrix_id) >= settings.hpn_max_nodes_per_matrix:
            raise HpnError("HPN_LIMIT_EXCEEDED")
        if payload.review_status == HpnReviewStatus.REVIEWED and payload.node_type in {
            HpnNodeType.EVIDENCE,
            HpnNodeType.NORM,
        }:
            raise HpnError("HPN_REVIEW_INCOMPLETE")
        node = HpnNode(matrix_id=matrix_id, **payload.model_dump())
        self.session.add(node)
        self._invalidate_review(matrix)
        await self._commit("HPN_CONFLICT")
        await self.session.refresh(node)
        self._log("hpn_node_create", entity="node", node_type=node.node_type.value)
        return self._node_read(node, [])

    async def update_node(
        self, matrix_id: UUID, node_id: UUID, payload: HpnNodeUpdate
    ) -> HpnNodeRead:
        matrix = await self._writable_matrix(matrix_id)
        node = await self._node(matrix_id, node_id)
        requested = payload.model_dump(exclude_unset=True)
        changes = {
            key: value for key, value in requested.items() if getattr(node, key) != value
        }
        if not changes:
            sources = await self.repository.sources([node.id])
            reads, _ = await self._source_reads(sources)
            return self._node_read(node, reads)
        if changes.get("review_status") == HpnReviewStatus.REVIEWED and node.node_type in {
            HpnNodeType.EVIDENCE,
            HpnNodeType.NORM,
        }:
            sources = await self.repository.sources([node.id])
            _, statuses = await self._source_reads(sources)
            if "valid" not in statuses:
                raise HpnError("HPN_REVIEW_INCOMPLETE")
        for key, value in changes.items():
            setattr(node, key, value)
        node.updated_at = datetime.now(timezone.utc)
        self._invalidate_review(matrix)
        await self._commit("HPN_CONFLICT")
        sources = await self.repository.sources([node.id])
        reads, _ = await self._source_reads(sources)
        return self._node_read(node, reads)

    async def delete_node(self, matrix_id: UUID, node_id: UUID) -> None:
        matrix = await self._writable_matrix(matrix_id)
        await self._node(matrix_id, node_id)
        await self.repository.soft_delete_node_tree(matrix_id, node_id)
        self._invalidate_review(matrix)
        await self._commit("HPN_CONFLICT")

    async def add_source(
        self, matrix_id: UUID, node_id: UUID, payload: HpnSourceCreate
    ) -> HpnSourceRead:
        matrix = await self._writable_matrix(matrix_id)
        node = await self._node(matrix_id, node_id)
        if await self.repository.source_count(node_id) >= settings.hpn_max_sources_per_node:
            raise HpnError("HPN_LIMIT_EXCEEDED")
        chunk = await self.repository.active_chunk_by_locator(payload.document_id, payload.chunk_index)
        if chunk is None or not chunk.text.strip():
            raise HpnError("HPN_SOURCE_INVALID")
        source = HpnNodeSource(
            node_id=node.id,
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            document_name=self._sanitize_source_name(chunk.document_name),
            document_type=chunk.document_type.value,
            chunk_index=chunk.chunk_index,
            start_page=chunk.start_page,
            end_page=chunk.end_page,
            source_fingerprint=self.source_fingerprint(chunk),
        )
        self.session.add(source)
        self._invalidate_review(matrix)
        await self._commit("HPN_DUPLICATE_SOURCE")
        await self.session.refresh(source)
        return self._source_read(source, "valid")

    async def delete_source(self, matrix_id: UUID, node_id: UUID, source_id: UUID) -> None:
        matrix = await self._writable_matrix(matrix_id)
        await self._node(matrix_id, node_id)
        source = await self.repository.source(node_id, source_id)
        if source is None:
            raise HpnError("HPN_SOURCE_NOT_FOUND")
        source.deleted_at = datetime.now(timezone.utc)
        self._invalidate_review(matrix)
        await self._commit("HPN_CONFLICT")

    async def create_relation(
        self, matrix_id: UUID, payload: HpnRelationCreate
    ) -> HpnRelationRead:
        matrix = await self._writable_matrix(matrix_id)
        if await self.repository.relation_count(matrix_id) >= settings.hpn_max_relations_per_matrix:
            raise HpnError("HPN_LIMIT_EXCEEDED")
        source = await self._node(matrix_id, payload.source_node_id)
        target = await self._node(matrix_id, payload.target_node_id)
        self._validate_relation(source, target, payload.relation_type)
        relation = HpnRelation(matrix_id=matrix_id, **payload.model_dump())
        self.session.add(relation)
        self._invalidate_review(matrix)
        await self._commit("HPN_DUPLICATE_RELATION")
        await self.session.refresh(relation)
        self._log(
            "hpn_relation_create",
            entity="relation",
            relation_type=relation.relation_type.value,
        )
        return HpnRelationRead.model_validate(relation)

    async def update_relation(
        self, matrix_id: UUID, relation_id: UUID, payload: HpnRelationUpdate
    ) -> HpnRelationRead:
        matrix = await self._writable_matrix(matrix_id)
        relation = await self.repository.relation(matrix_id, relation_id)
        if relation is None:
            raise HpnError("HPN_RELATION_NOT_FOUND")
        requested = payload.model_dump(exclude_unset=True)
        changes = {
            key: value for key, value in requested.items() if getattr(relation, key) != value
        }
        if not changes:
            return HpnRelationRead.model_validate(relation)
        for key, value in changes.items():
            setattr(relation, key, value)
        relation.updated_at = datetime.now(timezone.utc)
        self._invalidate_review(matrix)
        await self._commit("HPN_CONFLICT")
        return HpnRelationRead.model_validate(relation)

    async def delete_relation(self, matrix_id: UUID, relation_id: UUID) -> None:
        matrix = await self._writable_matrix(matrix_id)
        relation = await self.repository.relation(matrix_id, relation_id)
        if relation is None:
            raise HpnError("HPN_RELATION_NOT_FOUND")
        relation.deleted_at = datetime.now(timezone.utc)
        self._invalidate_review(matrix)
        await self._commit("HPN_CONFLICT")

    async def validation(self, matrix_id: UUID) -> HpnValidationSummary:
        await self._matrix(matrix_id)
        nodes = await self.repository.nodes(matrix_id)
        relations = await self.repository.relations(matrix_id)
        sources = await self.repository.sources([node.id for node in nodes])
        _, statuses = await self._source_reads(sources)
        return self._validation(matrix_id, nodes, relations, sources, statuses)

    @staticmethod
    def source_fingerprint(chunk: ActiveChunk) -> str:
        digest = hashlib.sha256()
        values = (
            chunk.document_id.hex,
            chunk.chunk_id.hex,
            chunk.document_type.value,
            str(chunk.chunk_index),
            str(chunk.start_page),
            str(chunk.end_page),
            chunk.document_name,
            chunk.text,
        )
        for value in values:
            encoded = value.encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
        return digest.hexdigest()

    async def _source_reads(
        self, sources: list[HpnNodeSource]
    ) -> tuple[list[HpnSourceRead], list[str]]:
        current = await self.repository.active_chunks_by_ids([source.chunk_id for source in sources])
        reads: list[HpnSourceRead] = []
        statuses: list[str] = []
        for source in sources:
            chunk = current.get(source.chunk_id)
            status = "unavailable"
            if chunk is not None and chunk.document_id == source.document_id:
                status = (
                    "valid"
                    if hmac.compare_digest(
                        self.source_fingerprint(chunk), source.source_fingerprint
                    )
                    else "stale"
                )
            statuses.append(status)
            reads.append(self._source_read(source, status))
        return reads, statuses

    @staticmethod
    def _source_read(source: HpnNodeSource, status: str) -> HpnSourceRead:
        return HpnSourceRead(
            source_id=source.id,
            document_id=source.document_id,
            document_name=source.document_name,
            document_type=source.document_type,
            chunk_index=source.chunk_index,
            start_page=source.start_page,
            end_page=source.end_page,
            source_status=cast(Literal["valid", "stale", "unavailable"], status),
            linked_at=source.created_at,
        )

    @staticmethod
    def _node_read(node: HpnNode, sources: list[HpnSourceRead]) -> HpnNodeRead:
        return HpnNodeRead(
            id=node.id,
            node_type=node.node_type,
            title=node.title,
            statement=node.statement,
            review_status=node.review_status,
            display_order=node.display_order,
            sources=sources,
            created_at=node.created_at,
            updated_at=node.updated_at,
        )

    @staticmethod
    def _validation(
        matrix_id: UUID,
        nodes: list[HpnNode],
        relations: list[HpnRelation],
        sources: list[HpnNodeSource],
        statuses: list[str],
    ) -> HpnValidationSummary:
        counts = {node_type: sum(node.node_type == node_type for node in nodes) for node_type in HpnNodeType}
        valid_nodes = {
            source.node_id for source, status in zip(sources, statuses, strict=True) if status == "valid"
        }
        evidence_without = sum(
            node.node_type == HpnNodeType.EVIDENCE and node.id not in valid_nodes for node in nodes
        )
        norm_without = sum(
            node.node_type == HpnNodeType.NORM and node.id not in valid_nodes for node in nodes
        )
        relation_types = {relation.relation_type for relation in relations}
        draft_nodes = sum(node.review_status == HpnReviewStatus.DRAFT for node in nodes)
        rejected_nodes = sum(node.review_status == HpnReviewStatus.REJECTED for node in nodes)
        draft_relations = sum(
            relation.review_status == HpnReviewStatus.DRAFT for relation in relations
        )
        all_relations_reviewed = all(
            relation.review_status == HpnReviewStatus.REVIEWED for relation in relations
        )
        stale = statuses.count("stale")
        unavailable = statuses.count("unavailable")
        has_evidence_relation = bool(
            relation_types
            & {
                HpnRelationType.EVIDENCE_SUPPORTS_FACT,
                HpnRelationType.EVIDENCE_CONTRADICTS_FACT,
            }
        )
        has_norm_relation = bool(
            relation_types
            & {HpnRelationType.NORM_APPLIES_TO_FACT, HpnRelationType.NORM_LIMITS_FACT}
        )
        valid = all(
            (
                counts[HpnNodeType.FACT] > 0,
                counts[HpnNodeType.EVIDENCE] > 0,
                counts[HpnNodeType.NORM] > 0,
                has_evidence_relation,
                has_norm_relation,
                draft_nodes == 0,
                rejected_nodes == 0,
                all_relations_reviewed,
                stale == 0,
                unavailable == 0,
                evidence_without == 0,
                norm_without == 0,
            )
        )
        return HpnValidationSummary(
            matrix_id=matrix_id,
            valid_for_review=valid,
            fact_count=counts[HpnNodeType.FACT],
            evidence_count=counts[HpnNodeType.EVIDENCE],
            norm_count=counts[HpnNodeType.NORM],
            relation_count=len(relations),
            draft_node_count=draft_nodes,
            rejected_node_count=rejected_nodes,
            draft_relation_count=draft_relations,
            stale_source_count=stale,
            unavailable_source_count=unavailable,
            evidence_without_valid_source_count=evidence_without,
            norm_without_valid_source_count=norm_without,
        )

    async def _matrix(self, matrix_id: UUID) -> HpnMatrix:
        matrix = await self.repository.matrix(matrix_id)
        if matrix is None:
            existing = await self.repository.matrix_including_deleted(matrix_id)
            raise HpnError(
                "HPN_MATRIX_DELETED" if existing is not None else "HPN_MATRIX_NOT_FOUND"
            )
        return matrix

    @staticmethod
    def _sanitize_source_name(value: str) -> str:
        return sanitize_document_name(
            value,
            max_length=settings.hpn_source_name_max_length,
        )

    async def _node(self, matrix_id: UUID, node_id: UUID) -> HpnNode:
        node = await self.repository.node(matrix_id, node_id)
        if node is None:
            raise HpnError("HPN_NODE_NOT_FOUND")
        return node

    async def _writable_matrix(self, matrix_id: UUID) -> HpnMatrix:
        matrix = await self._matrix(matrix_id)
        if matrix.status == HpnMatrixStatus.ARCHIVED:
            raise HpnError("HPN_MATRIX_ARCHIVED")
        return matrix

    @staticmethod
    def _validate_relation(
        source: HpnNode, target: HpnNode, relation_type: HpnRelationType
    ) -> None:
        if source.id == target.id or (source.node_type, target.node_type) != RELATION_ENDPOINT_TYPES[relation_type]:
            raise HpnError("HPN_RELATION_ENDPOINT_INVALID")

    @staticmethod
    def _invalidate_review(matrix: HpnMatrix) -> None:
        if matrix.status == HpnMatrixStatus.REVIEWED:
            matrix.status = HpnMatrixStatus.IN_REVIEW
            matrix.updated_at = datetime.now(timezone.utc)

    async def _commit(self, conflict_code: str) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            log_warning("Conflicto HPN", operation="hpn_write", error_code=conflict_code)
            raise HpnError(conflict_code) from exc
        except Exception:
            await self.session.rollback()
            raise

    @staticmethod
    def _log(operation: str, **safe: object) -> None:
        log_info("Operación HPN completada", operation=operation, **safe)
