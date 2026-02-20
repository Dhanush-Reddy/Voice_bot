from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from core.config import settings

# Create async engine
# For SQLite, we use aiosqlite as the driver (sqlite+aiosqlite://)
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
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
    """Dependency for providing a database session to FastAPI routes."""
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    """Initialises the database, creating all tables."""
    async with engine.begin() as conn:
        # Import models here to ensure they're registered on Base.metadata
        from models.database_models import Agent, CallLog # noqa
        await conn.run_sync(Base.metadata.create_all)
