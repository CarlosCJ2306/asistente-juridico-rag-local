"""Retención automática de conversaciones invitadas expiradas."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.Log import log_error, log_info, log_success
from app.core.config import settings
from app.database.repositories.conversation_repository import ConversationRepository


class ConversationCleanupService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        await self.run_once()
        self._task = asyncio.create_task(self._run(), name="conversation-cleanup")

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        self._task = None
        if task is not None:
            await task

    async def run_once(self) -> int:
        try:
            async with self.session_factory() as session:
                deleted = await ConversationRepository(session).hard_delete_expired_guests(
                    now=datetime.now(timezone.utc)
                )
                await session.commit()
        except SQLAlchemyError:
            log_error(
                "Limpieza de conversaciones no disponible",
                operation="conversation_cleanup",
                error_code="CONVERSATION_SCHEMA_NOT_READY",
            )
            return 0
        log_success(
            "Retención de conversaciones aplicada",
            operation="conversation_cleanup",
            deleted_count=deleted,
        )
        return deleted

    async def _run(self) -> None:
        log_info("Limpieza de conversaciones iniciada", operation="conversation_cleanup")
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=settings.conversation_cleanup_interval_seconds,
                )
            except TimeoutError:
                await self.run_once()


def get_conversation_cleanup_service(
    session_factory: async_sessionmaker[AsyncSession],
) -> ConversationCleanupService:
    return ConversationCleanupService(session_factory)
