"""Validaciones sintéticas de configuración y contratos HPN."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.database.models.hpn import HpnNodeSource
from app.schemas.hpn import (
    HpnMatrixCreate,
    HpnMatrixUpdate,
    HpnNodeCreate,
    HpnNodeUpdate,
    HpnRelationUpdate,
    HpnSourceCreate,
)


def test_hpn_settings_defaults_and_boolean_rejection() -> None:
    configured = Settings(_env_file=None)
    assert configured.hpn_max_nodes_per_matrix == 500
    assert configured.hpn_max_relations_per_matrix == 2000
    with pytest.raises(ValidationError):
        Settings(_env_file=None, hpn_max_nodes_per_matrix=True)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, hpn_max_sources_per_node=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, hpn_matrix_title_max_length=201)


def test_hpn_schema_rejects_controls_empty_extra_and_boolean() -> None:
    with pytest.raises(ValidationError):
        HpnMatrixCreate(title="  ")
    with pytest.raises(ValidationError):
        HpnMatrixCreate(title="seguro\x00oculto")
    with pytest.raises(ValidationError):
        HpnNodeCreate(
            node_type="fact",
            title="Título",
            statement="Contenido",
            display_order=True,
        )
    with pytest.raises(ValidationError):
        HpnSourceCreate(document_id="00000000-0000-0000-0000-000000000001", chunk_index=True)
    with pytest.raises(ValidationError):
        HpnSourceCreate(
            document_id="00000000-0000-0000-0000-000000000001",
            chunk_index=1,
            chunk_id="00000000-0000-0000-0000-000000000002",
        )
    with pytest.raises(ValidationError):
        HpnMatrixCreate(title="Matriz", extra_field="rechazado")
    with pytest.raises(ValidationError):
        HpnMatrixUpdate(title=None)
    with pytest.raises(ValidationError):
        HpnNodeUpdate(statement=None)
    with pytest.raises(ValidationError):
        HpnNodeUpdate(review_status=None)
    with pytest.raises(ValidationError):
        HpnRelationUpdate(review_status=None)
    with pytest.raises(ValidationError):
        HpnMatrixUpdate(status=None)


def test_hpn_schema_preserves_unicode() -> None:
    payload = HpnNodeCreate(
        node_type="norm",
        title="Norma sobre acción y niñez",
        statement="Texto jurídico sintético con tildes y eñe.",
        display_order=1,
    )
    assert "acción" in payload.title
    assert "jurídico" in payload.statement


def test_hpn_source_snapshot_contains_only_authorized_columns() -> None:
    columns = set(HpnNodeSource.__table__.columns.keys())
    assert columns == {
        "id",
        "node_id",
        "chunk_id",
        "document_id",
        "document_name",
        "document_type",
        "chunk_index",
        "start_page",
        "end_page",
        "source_fingerprint",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert columns.isdisjoint(
        {
            "text",
            "snippet",
            "path",
            "stored_filename",
            "sha256",
            "marker",
            "score",
            "vector",
            "embedding",
            "prompt",
            "response",
        }
    )
