"""Entorno Alembic asíncrono; solo conecta durante un comando explícito."""

from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.models import (  # noqa: F401, E402
    Document,
    DocumentChunk,
    DocumentPage,
    HpnMatrix,
    HpnNode,
    HpnNodeSource,
    HpnRelation,
    ManagedCorpusEntry,
)
from app.database.session import build_database_url  # noqa: E402


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", build_database_url(settings.database_file))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera SQL sin conexión usando la URL derivada de la configuración real."""

    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configura migraciones SQLite compatibles con futuros cambios por lotes."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Abre una conexión asíncrona exclusivamente durante el comando Alembic."""

    connectable: AsyncEngine = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
