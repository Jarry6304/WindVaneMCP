"""Async fixtures for in-memory SQLite testing.

PostgreSQL-specific column types (ARRAY, JSONB) are substituted with
SQLite-compatible equivalents before wind_vane models are imported.
TIMESTAMPTZ is defined in models.py as a TIMESTAMP subclass, so SQLite
handles it natively without patching.
"""

import sqlalchemy
import sqlalchemy.dialects.postgresql as _pg
import sqlalchemy.sql.sqltypes as _sqltypes
from sqlalchemy import Integer


class _TextArray(sqlalchemy.Text):
    """Stand-in for postgresql.ARRAY that compiles to TEXT in SQLite."""
    def __init__(self, item_type=None, *args, **kwargs):
        super().__init__()


# Patch PG-specific types before wind_vane.db.models is imported
_pg.ARRAY = _TextArray       # type: ignore[assignment]
_pg.JSONB = sqlalchemy.JSON  # type: ignore[assignment]

# SQLite only auto-increments INTEGER PRIMARY KEY, not BIGINT
class _SqliteSafeBigInteger(Integer):
    """BigInteger substitute that uses INTEGER affinity in SQLite for auto-increment support."""


sqlalchemy.BigInteger = _SqliteSafeBigInteger  # type: ignore[assignment]
_sqltypes.BigInteger = _SqliteSafeBigInteger   # type: ignore[assignment]

# --- fixtures ---

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from wind_vane.db.models import Base


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
