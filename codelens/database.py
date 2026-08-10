import asyncpg

from codelens.config import settings

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    """Create the connection pool. Call once at application startup."""
    global _pool
    if _pool is not None:
        return _pool

    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
    )
    return _pool


async def get_pool() -> asyncpg.Pool:
    """Return the existing pool, or create one if it doesn't exist yet."""
    if _pool is None:
        return await init_pool()
    return _pool


async def close_pool() -> None:
    """Gracefully close the pool. Call once at application shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
