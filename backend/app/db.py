"""Database access: async SQLAlchemy engine, the model base class, and the session dependency.

The engine is created on first use (not at import), so importing the app never needs a
database; DATABASE_URL comes from app.settings.
"""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.settings import get_settings


class Base(DeclarativeBase):
    """Base class for every table model; Alembic reads Base.metadata."""


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """The process's async engine, built from DATABASE_URL on first use."""
    return create_async_engine(get_settings().database_url)


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Factory for database sessions bound to the engine."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one database session per request, closed afterwards."""
    async with get_sessionmaker()() as session:
        yield session
