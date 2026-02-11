"""
PostgreSQL connection — async engine + session factory.
Stores: Users, Simulation Sessions, Scores, Task Progress.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import logger

engine = create_async_engine(
    settings.postgres_url,
    echo=settings.APP_DEBUG,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass

async def init_postgres():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL tables initialized")

async def close_postgres():
    """Dispose engine on shutdown."""
    await engine.dispose()
    logger.info("PostgreSQL connection closed")

async def get_db() -> AsyncSession:
    """FastAPI dependency — yields an async session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
