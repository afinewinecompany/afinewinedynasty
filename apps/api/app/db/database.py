from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from sqlalchemy import create_engine
from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# Create async engine with connection pooling
engine = create_async_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    echo=False,  # Set to True for SQL debugging
    future=True,
    pool_size=5,  # Railway default
    max_overflow=10,  # Burst capacity
    pool_pre_ping=True,  # Auto-reconnect on failure
    pool_recycle=3600,  # Recycle connections hourly
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Create sync engine for scripts (convert postgresql+asyncpg to postgresql+psycopg2)
sync_db_url = str(settings.SQLALCHEMY_DATABASE_URI).replace(
    'postgresql+asyncpg://', 'postgresql://'
)
sync_engine = create_engine(
    sync_db_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create sync session factory for scripts
SyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine
)


async def get_db() -> AsyncSession:
    """Dependency for getting database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_db_sync() -> Session:
    """Get synchronous database session for scripts."""
    return SyncSessionLocal()


async def init_db():
    """Initialize database tables (for development only)."""
    async with engine.begin() as conn:
        # Import all models to register them
        from app.db.models import (
            Prospect,
            MiLBGameLog,
            MLBStats,
            ScoutingGrade,
            MiLBAdvancedStats,
            MLFeatures,
            MLLabel,
            MLPrediction,
        )

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)