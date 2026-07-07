from __future__ import annotations

import os
from pathlib import Path

import asyncpg

_pool: asyncpg.Pool | None = None
_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=os.environ["POSTGRES_DSN"],
            min_size=1,
            max_size=10,
        )
        await _apply_schema(_pool)
    return _pool


async def _apply_schema(pool: asyncpg.Pool) -> None:
    """Bootstrap the schema on first connection. schema.sql is all
    CREATE TABLE IF NOT EXISTS / DO $$ ... EXCEPTION duplicate_object,
    so it's safe to run every time a pool is created, from every service.
    """
    if not _SCHEMA_PATH.exists():
        return
    async with pool.acquire() as conn:
        await conn.execute(_SCHEMA_PATH.read_text())


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
