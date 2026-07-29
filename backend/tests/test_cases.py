"""Pruebas sintéticas del núcleo Case sin persistencias principales."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes.cases import router as cases_router
from app.cases.domain import Case, CaseDomainError, CaseRetentionMode, CaseStatus
from app.cases.errors import CaseError
from app.cases.service import CaseService
from app.database.base import Base
from app.database.models.case import CaseAuditEventRecord, CaseRecord
from app.database.session import get_db_session
from app.main import app
from app.schemas.case import CaseActionRequest, CaseCreate, CaseUpdate
from app.services.conversation_principal import ConversationPrincipal


NOW = datetime(2026, 7, 28, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def case_factory(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'cases.db').as_posix()}")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: Base.metadata.create_all(
                sync,
                tables=[CaseRecord.__table__, CaseAuditEventRecord.__table__],
            )
        )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


def test_case_domain_retention_transitions_restore_and_read_only() -> None:
    temporary = Case.create(
        title="  Caso   sintético ",
        description=" Descripción   neutral ",
        retention_mode=CaseRetentionMode.TEMPORARY,
        owner_key_hash="a" * 64,
        now=NOW,
        retention_days=7,
    )
    assert temporary.title == "Caso sintético"
    assert temporary.expires_at == NOW + timedelta(days=7)
    active = temporary.transition(target=CaseStatus.ACTIVE, now=NOW, retention_days=7)
    closed = active.transition(target=CaseStatus.CLOSED, now=NOW, retention_days=7)
    archived = closed.transition(target=CaseStatus.ARCHIVED, now=NOW, retention_days=7)
    assert archived.read_only
    assert archived.restore(now=NOW, retention_days=7).status is CaseStatus.CLOSED
    with pytest.raises(CaseDomainError, match="CASE_ARCHIVED_READ_ONLY"):
        archived.update_content(
            title="Otro",
            description=None,
            description_supplied=False,
            now=NOW,
            retention_days=7,
        )
    with pytest.raises(CaseDomainError, match="CASE_INVALID_TRANSITION"):
        temporary.transition(target=CaseStatus.CLOSED, now=NOW, retention_days=7)

    persistent = Case.create(
        title="Persistente",
        description=None,
        retention_mode=CaseRetentionMode.LOCAL_PERSISTENT,
        owner_key_hash=None,
        now=NOW,
        retention_days=7,
    )
    assert persistent.expires_at is None
    with pytest.raises(CaseDomainError, match="CASE_RETENTION_INVALID"):
        Case.create(
            title="Inválido",
            description=None,
            retention_mode=CaseRetentionMode.TEMPORARY,
            owner_key_hash=None,
            now=NOW,
            retention_days=7,
        )


@pytest.mark.asyncio
async def test_case_service_isolates_guests_audits_and_locks(case_factory) -> None:
    owner = ConversationPrincipal.guest("a" * 64)
    stranger = ConversationPrincipal.guest("b" * 64)
    async with case_factory() as session:
        service = CaseService(session)
        created = await service.create_case(
            CaseCreate(title="Temporal", retention_mode="temporary"), owner
        )
        with pytest.raises(CaseError, match="CASE_NOT_FOUND"):
            await service.get_case(created.public_id, stranger)
        updated = await service.update_case(
            created.public_id,
            CaseUpdate(title="Temporal actualizado", expected_version=created.version),
            owner,
        )
        with pytest.raises(CaseError, match="CASE_VERSION_CONFLICT"):
            await service.update_case(
                created.public_id,
                CaseUpdate(title="Obsoleto", expected_version=created.version),
                owner,
            )
        archived = await service.transition_case(
            created.public_id,
            CaseActionRequest(expected_version=updated.version),
            owner,
            target=CaseStatus.ARCHIVED,
        )
        restored = await service.restore_case(
            created.public_id,
            CaseActionRequest(expected_version=archived.version),
            owner,
        )
        await service.delete_case(created.public_id, restored.version, owner)
        assert await session.scalar(select(func.count()).select_from(CaseRecord)) == 1
        assert await session.scalar(select(func.count()).select_from(CaseAuditEventRecord)) == 5
        assert (await service.list_cases(owner, page=1, page_size=20)).model_dump() == {
            "items": [], "page": 1, "page_size": 20, "total": 0, "total_pages": 0
        }


@pytest.mark.asyncio
async def test_cases_api_cookie_isolation_public_contract_and_local_visibility(case_factory) -> None:
    async def override_session():
        async with case_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as first, httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as second:
            temporary = await first.post(
                "/api/cases",
                json={"title": "Temporal API", "description": None, "retention_mode": "temporary"},
            )
            assert temporary.status_code == 201
            assert temporary.headers["set-cookie"].count("HttpOnly") == 1
            assert "Path=/api" in temporary.headers["set-cookie"]
            body = temporary.json()
            forbidden = {"id", "owner_type", "owner_key_hash", "deleted_at"}
            assert forbidden.isdisjoint(body)
            assert (await second.get(f"/api/cases/{body['public_id']}")).status_code == 404

            persistent = await first.post(
                "/api/cases",
                json={"title": "Persistente API", "retention_mode": "local_persistent"},
            )
            assert persistent.status_code == 201
            second_list = await second.get("/api/cases")
            assert second_list.status_code == 200
            assert [item["title"] for item in second_list.json()["items"]] == [
                "Persistente API"
            ]
    finally:
        app.dependency_overrides.clear()


def test_case_router_is_registered_only_under_api_cases() -> None:
    routes = {
        (method, route.path)
        for route in cases_router.routes
        for method in getattr(route, "methods", set())
    }
    assert ("POST", "/cases") in routes
    assert ("GET", "/cases/{case_id}") in routes
    assert not any("documents" in path or "hpn" in path for _, path in routes if path.startswith("/cases"))
