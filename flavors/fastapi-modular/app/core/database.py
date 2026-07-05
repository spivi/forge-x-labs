"""Database engine and session configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class Base(DeclarativeBase):
    """Base class for all ORM models."""


engine = (
    create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    if settings.DATABASE_URL
    else None
)

async_session_factory: async_sessionmaker[AsyncSession] | None = (
    async_sessionmaker(engine, expire_on_commit=False) if engine else None
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependency for getting an async database session."""
    if async_session_factory is None:
        msg = "DATABASE_URL not configured"
        raise RuntimeError(msg)
    async with async_session_factory() as session:
        yield session
