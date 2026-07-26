"""Engine y sesiones asíncronas de SQLite creados únicamente bajo demanda."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.Log import log_info
from app.core.config import settings


def build_database_url(database_file: Path) -> str:
    """Construye la URL SQLite asíncrona a partir de una ruta ya validada."""

    return f"sqlite+aiosqlite:///{database_file.as_posix()}"


class DatabaseSessionManager:
    """Conserva un engine y una fábrica de sesiones sin inicializarlos al importar."""

    def __init__(self, database_file: Path | None = None) -> None:
        self.database_file = database_file or settings.database_file
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def is_initialized(self) -> bool:
        """Indica si el engine fue solicitado, sin establecer una conexión."""

        return self._engine is not None

    def get_engine(self) -> AsyncEngine:
        """Crea el engine bajo demanda, sin tablas ni migraciones implícitas."""

        if self._engine is None:
            log_info(
                "Inicializando engine SQLite asíncrono",
                operation="database_engine_initialization",
                database_name=self.database_file.name,
            )
            self._engine = create_async_engine(
                build_database_url(self.database_file),
                future=True,
            )
            event.listen(self._engine.sync_engine, "connect", self._enable_sqlite_foreign_keys)
        return self._engine

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection: object, connection_record: object) -> None:
        """Activa integridad referencial en cada conexión SQLite."""

        del connection_record
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    def get_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Obtiene la fábrica de sesiones, inicializando el engine si hace falta."""

        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.get_engine(),
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
        return self._session_factory

    async def dispose(self) -> None:
        """Libera el engine cuando fue creado explícitamente por el consumidor."""

        engine = self._engine
        self._engine = None
        self._session_factory = None
        if engine is not None:
            await engine.dispose()


database_session_manager = DatabaseSessionManager()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Dependencia FastAPI que entrega una sesión sin confirmar transacciones."""

    session_factory = database_session_manager.get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
