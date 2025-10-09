"""
Database Manager

Manages async PostgreSQL connections with pooling and fork support.
"""
import asyncio
import logging
from typing import Any, Optional
import asyncpg
from src.core.config import get_config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Async PostgreSQL connection manager

    Features:
    - Connection pooling
    - Fork connection management
    - Automatic reconnection
    - Query helpers
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        pool_min_size: int = 5,
        pool_max_size: int = 20,
        timeout: int = 30
    ):
        """
        Initialize database manager

        Args:
            host: Database host (defaults to config)
            port: Database port (defaults to config)
            database: Database name (defaults to config)
            user: Database user (defaults to config)
            password: Database password (defaults to config)
            pool_min_size: Minimum pool size
            pool_max_size: Maximum pool size
            timeout: Connection timeout in seconds
        """
        config = get_config()

        self.host = host or config.get('database.host')
        self.port = port or config.get('database.port', 5432)
        self.database = database or config.get('database.database', 'tsdb')
        self.user = user or config.get('database.user', 'tsdbadmin')
        self.password = password or config.get('database.password')
        self.pool_min_size = pool_min_size or config.get('database.pool_min_size', 5)
        self.pool_max_size = pool_max_size or config.get('database.pool_max_size', 20)
        self.timeout = timeout or config.get('database.timeout', 30)

        self._pool: Optional[asyncpg.Pool] = None
        self._fork_pools: dict[str, asyncpg.Pool] = {}
        self._lock = asyncio.Lock()

    @property
    def is_initialized(self) -> bool:
        """Check if database pool is initialized"""
        return self._pool is not None

    async def initialize(self) -> None:
        """
        Initialize connection pool

        Must be called before using the database manager.
        """
        if self._pool is not None:
            logger.warning("Database pool already initialized")
            return

        logger.info(
            f"Initializing database pool: {self.user}@{self.host}:{self.port}/{self.database}"
        )

        try:
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=self.pool_min_size,
                max_size=self.pool_max_size,
                command_timeout=self.timeout,
                # SSL required for Tiger Cloud
                ssl='require'
            )

            logger.info("Database pool initialized successfully")

            # Test connection
            async with self._pool.acquire() as conn:
                version = await conn.fetchval('SELECT version()')
                logger.info(f"Connected to: {version}")

        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise

    async def close(self) -> None:
        """Close all database connections"""
        logger.info("Closing database connections")

        # Close fork pools
        for fork_id, pool in self._fork_pools.items():
            logger.info(f"Closing fork pool: {fork_id}")
            await pool.close()

        self._fork_pools.clear()

        # Close main pool
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("Database pool closed")

    async def get_connection(self) -> asyncpg.Connection:
        """
        Get a connection from the pool

        Returns:
            Database connection

        Note:
            Remember to release the connection with release_connection()
        """
        if self._pool is None:
            raise RuntimeError("Database pool not initialized. Call initialize() first.")

        return await self._pool.acquire()

    async def release_connection(self, conn: asyncpg.Connection) -> None:
        """
        Release a connection back to the pool

        Args:
            conn: Connection to release
        """
        if self._pool is None:
            logger.warning("Cannot release connection - pool is None")
            return

        await self._pool.release(conn)

    async def execute(self, query: str, *args) -> str:
        """
        Execute a query that doesn't return results

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            Query execution status

        Example:
            await db.execute("INSERT INTO trades (...) VALUES ($1, $2)", value1, value2)
        """
        conn = await self.get_connection()
        try:
            return await conn.execute(query, *args)
        finally:
            await self.release_connection(conn)

    async def fetch(self, query: str, *args) -> list[asyncpg.Record]:
        """
        Execute a query and fetch all results

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            List of records

        Example:
            rows = await db.fetch("SELECT * FROM trades WHERE symbol = $1", "BTCUSDT")
        """
        conn = await self.get_connection()
        try:
            return await conn.fetch(query, *args)
        finally:
            await self.release_connection(conn)

    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """
        Execute a query and fetch one result

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            Single record or None

        Example:
            row = await db.fetchrow("SELECT * FROM trades WHERE id = $1", trade_id)
        """
        conn = await self.get_connection()
        try:
            return await conn.fetchrow(query, *args)
        finally:
            await self.release_connection(conn)

    async def fetchval(self, query: str, *args) -> Any:
        """
        Execute a query and fetch a single value

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            Single value

        Example:
            count = await db.fetchval("SELECT COUNT(*) FROM trades")
        """
        conn = await self.get_connection()
        try:
            return await conn.fetchval(query, *args)
        finally:
            await self.release_connection(conn)

    async def transaction(self):
        """
        Get a transaction context manager

        Example:
            async with db.transaction() as conn:
                await conn.execute("INSERT INTO trades ...")
                await conn.execute("UPDATE portfolio ...")
        """
        conn = await self.get_connection()
        return _TransactionContext(self, conn)

    # ========================================================================
    # Fork Management
    # ========================================================================

    async def create_fork_pool(
        self,
        fork_id: str,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str
    ) -> None:
        """
        Create a connection pool for a database fork

        Args:
            fork_id: Unique identifier for the fork
            host: Fork database host
            port: Fork database port
            database: Fork database name
            user: Fork database user
            password: Fork database password
        """
        if fork_id in self._fork_pools:
            logger.warning(f"Fork pool {fork_id} already exists")
            return

        logger.info(f"Creating fork pool: {fork_id}")

        try:
            pool = await asyncpg.create_pool(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                min_size=2,  # Smaller pool for forks
                max_size=5,
                command_timeout=self.timeout,
                ssl='require'
            )

            self._fork_pools[fork_id] = pool
            logger.info(f"Fork pool created: {fork_id}")

        except Exception as e:
            logger.error(f"Failed to create fork pool {fork_id}: {e}")
            raise

    async def get_fork_connection(self, fork_id: str) -> asyncpg.Connection:
        """
        Get a connection from a fork pool

        Args:
            fork_id: Fork identifier

        Returns:
            Database connection to the fork
        """
        if fork_id not in self._fork_pools:
            raise ValueError(f"Fork pool {fork_id} not found")

        return await self._fork_pools[fork_id].acquire()

    async def release_fork_connection(
        self,
        fork_id: str,
        conn: asyncpg.Connection
    ) -> None:
        """
        Release a fork connection back to its pool

        Args:
            fork_id: Fork identifier
            conn: Connection to release
        """
        if fork_id not in self._fork_pools:
            logger.warning(f"Fork pool {fork_id} not found")
            return

        await self._fork_pools[fork_id].release(conn)

    async def close_fork_pool(self, fork_id: str) -> None:
        """
        Close a fork connection pool

        Args:
            fork_id: Fork identifier
        """
        if fork_id not in self._fork_pools:
            logger.warning(f"Fork pool {fork_id} not found")
            return

        logger.info(f"Closing fork pool: {fork_id}")

        pool = self._fork_pools.pop(fork_id)
        await pool.close()

        logger.info(f"Fork pool closed: {fork_id}")

    # ========================================================================
    # Health Checks
    # ========================================================================

    async def health_check(self) -> bool:
        """
        Check if database connection is healthy

        Returns:
            True if healthy, False otherwise
        """
        try:
            result = await self.fetchval('SELECT 1')
            return result == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def get_pool_stats(self) -> dict[str, Any]:
        """
        Get connection pool statistics

        Returns:
            Dictionary with pool stats
        """
        if self._pool is None:
            return {'status': 'not_initialized'}

        return {
            'status': 'active',
            'size': self._pool.get_size(),
            'free_size': self._pool.get_idle_size(),
            'min_size': self._pool.get_min_size(),
            'max_size': self._pool.get_max_size(),
            'fork_pools': list(self._fork_pools.keys())
        }


class _TransactionContext:
    """Context manager for database transactions"""

    def __init__(self, db_manager: DatabaseManager, conn: asyncpg.Connection):
        self.db_manager = db_manager
        self.conn = conn
        self.transaction = None

    async def __aenter__(self) -> asyncpg.Connection:
        self.transaction = self.conn.transaction()
        await self.transaction.start()
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.transaction.rollback()
        else:
            await self.transaction.commit()

        await self.db_manager.release_connection(self.conn)


# ============================================================================
# Global Database Manager Instance
# ============================================================================

_db_manager: DatabaseManager | None = None
_db_manager_lock = asyncio.Lock()


async def get_db_manager() -> DatabaseManager:
    """
    Get global database manager instance (singleton)

    Returns:
        Global DatabaseManager instance
    """
    global _db_manager

    async with _db_manager_lock:
        if _db_manager is None:
            _db_manager = DatabaseManager()
            logger.info("Global database manager created")

    return _db_manager


def get_db_manager_sync() -> DatabaseManager:
    """
    Get global database manager instance (synchronous)

    Returns:
        Global DatabaseManager instance

    Note:
        Use get_db_manager() for async code.
    """
    global _db_manager

    if _db_manager is None:
        _db_manager = DatabaseManager()
        logger.info("Global database manager created (sync)")

    return _db_manager


async def close_db_manager() -> None:
    """Close the global database manager"""
    global _db_manager

    if _db_manager is not None:
        await _db_manager.close()
        _db_manager = None
