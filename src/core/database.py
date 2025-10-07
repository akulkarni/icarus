"""
Database Manager

Manages asyncpg connection pool for Tiger Cloud database.
"""
import asyncpg
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections using asyncpg connection pool.

    Provides connection pooling and fork connection management.
    """

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self._fork_pools = {}  # fork_id -> pool

    async def initialize(self):
        """Initialize the database connection pool"""
        # Get connection parameters from environment
        host = os.getenv('TIGER_HOST')
        port = int(os.getenv('TIGER_PORT', '5432'))
        database = os.getenv('TIGER_DATABASE', 'tsdb')
        user = os.getenv('TIGER_USER', 'tsdbadmin')
        password = os.getenv('TIGER_PASSWORD')

        if not all([host, password]):
            raise ValueError("Database credentials not configured")

        # Create connection pool
        self.pool = await asyncpg.create_pool(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            min_size=5,
            max_size=20
        )
        logger.info(f"Database pool initialized: {host}:{port}/{database}")

    async def get_connection(self) -> asyncpg.Connection:
        """Get a connection from the pool"""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        return await self.pool.acquire()

    async def release_connection(self, conn: asyncpg.Connection):
        """Release a connection back to the pool"""
        if self.pool:
            await self.pool.release(conn)

    async def get_fork_connection(self, fork_id: str, connection_params: dict) -> asyncpg.Connection:
        """Get a connection to a fork database"""
        if fork_id not in self._fork_pools:
            # Create pool for this fork
            fork_pool = await asyncpg.create_pool(
                host=connection_params['host'],
                port=connection_params['port'],
                database=connection_params['database'],
                user=connection_params['user'],
                password=connection_params['password'],
                min_size=2,
                max_size=5
            )
            self._fork_pools[fork_id] = fork_pool
            logger.info(f"Created fork pool: {fork_id}")

        return await self._fork_pools[fork_id].acquire()

    async def release_fork_connection(self, fork_id: str, conn: asyncpg.Connection):
        """Release a fork connection"""
        if fork_id in self._fork_pools:
            await self._fork_pools[fork_id].release(conn)

    async def close_fork_pool(self, fork_id: str):
        """Close a fork connection pool"""
        if fork_id in self._fork_pools:
            await self._fork_pools[fork_id].close()
            del self._fork_pools[fork_id]
            logger.info(f"Closed fork pool: {fork_id}")

    async def close(self):
        """Close all connections"""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")

        for fork_id, fork_pool in self._fork_pools.items():
            await fork_pool.close()
            logger.info(f"Fork pool closed: {fork_id}")

        self._fork_pools.clear()


# Global database manager instance
_db_manager = None


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
