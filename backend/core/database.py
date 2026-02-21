"""
core/database.py — PostgreSQL connection via Cloud SQL unix socket.

When --add-cloudsql-instances is set on the Cloud Run service, GCP mounts
the Cloud SQL Auth Proxy socket at /cloudsql/<INSTANCE_CONNECTION_NAME>.
We connect directly via asyncpg using that socket — no connector library needed.

Uses NullPool so each session gets its own fresh connection. This avoids the
asyncpg "another operation is in progress" error that occurs when a pooled
connection is shared across concurrent coroutines through a unix socket.
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from core.config import settings


def _build_db_url() -> str:
    """
    Build the asyncpg connection URL.

    - In Cloud Run (production): use the unix socket mounted by --add-cloudsql-instances.
    - In local dev: use DATABASE_URL env var (set via Cloud SQL Auth Proxy or direct).
    """
    database_url = os.getenv("DATABASE_URL", "")
    if database_url:
        # Normalize to asyncpg dialect
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # Strip any ?schema=public (Prisma-style) not supported by asyncpg
        if "?schema=" in database_url:
            database_url = database_url.split("?schema=")[0]
        return database_url

    # Production: unix socket mounted by --add-cloudsql-instances
    socket_dir = f"/cloudsql/{settings.cloud_sql_connection_name}"
    url = (
        f"postgresql+asyncpg://{settings.db_user}:{settings.db_pass}"
        f"@/{settings.db_name}"
        f"?host={socket_dir}"
    )
    return url


_DB_URL = _build_db_url()

# NullPool: no connection reuse — each session gets a fresh connection.
# This is required for unix socket connections with asyncpg to prevent
# "cannot perform operation: another operation is in progress" errors.
engine = create_async_engine(
    _DB_URL,
    echo=False,
    future=True,
    poolclass=NullPool,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def get_db():
    """FastAPI dependency — yields a database session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Creates all tables defined in database_models."""
    async with engine.begin() as conn:
        from models.database_models import Agent, CallLog, User, Account, Session, VerificationToken  # noqa
        await conn.run_sync(Base.metadata.create_all)
        return True
