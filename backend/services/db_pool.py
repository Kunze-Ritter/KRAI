"""
PostgreSQL Connection Pool Utility
===================================

Centralized asyncpg connection pool management for the application.
Replaces the DatabaseAdapter abstraction layer with direct asyncpg usage.
"""

import asyncio
import logging
import os

import asyncpg

logger = logging.getLogger(__name__)

# Global connection pool
_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()


async def get_pool() -> asyncpg.Pool:
    """
    Get or create the global asyncpg connection pool.

    Returns:
        asyncpg.Pool: The connection pool instance

    Raises:
        RuntimeError: If pool cannot be created
    """
    global _pool

    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                _pool = await create_pool()

    return _pool


async def create_pool() -> asyncpg.Pool:
    """
    Create a new asyncpg connection pool.

    Returns:
        asyncpg.Pool: New connection pool instance

    Raises:
        RuntimeError: If required environment variables are missing
    """
    # Get database connection parameters from environment
    postgres_url = os.getenv("POSTGRES_URL")

    if not postgres_url:
        # Fallback: construct from individual parameters
        db_host = os.getenv("POSTGRES_HOST", "localhost")
        db_port = os.getenv("POSTGRES_PORT", "5432")
        db_name = os.getenv("POSTGRES_DB", "krai")
        db_user = os.getenv("POSTGRES_USER", "postgres")
        db_password = os.getenv("POSTGRES_PASSWORD", "")

        postgres_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    try:
        pool = await asyncpg.create_pool(
            postgres_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
            server_settings={"application_name": "krai-engine"},
        )

        logger.info("✅ PostgreSQL connection pool created successfully")
        return pool

    except Exception as e:
        logger.error(f"❌ Failed to create PostgreSQL connection pool: {e}")
        raise RuntimeError(f"Failed to create database connection pool: {e}")


async def close_pool():
    """Close the global connection pool."""
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL connection pool closed")


async def test_connection() -> bool:
    """
    Test the database connection.

    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            return result == 1
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False
