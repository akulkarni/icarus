"""
Fork Manager Agent

Manages database fork lifecycle.
Creates, tracks, and destroys forks on request.
"""
import asyncio
import logging
import subprocess
import json
from datetime import datetime
from typing import Dict, Optional

from src.agents.base import BaseAgent
from src.models.events import ForkRequestEvent, ForkCreatedEvent, ForkCompletedEvent
from src.core.database import get_db_manager

logger = logging.getLogger(__name__)


class ForkManagerAgent(BaseAgent):
    """
    Manages Tiger Cloud database forks.

    Uses Tiger Cloud CLI (`tsdb` command) to create/destroy forks.
    Tracks active forks and automatically cleans up expired ones.

    Fork lifecycle:
    1. Receives ForkRequestEvent
    2. Creates fork via Tiger Cloud CLI
    3. Publishes ForkCreatedEvent with connection params
    4. Tracks fork metadata
    5. Automatically destroys expired forks based on TTL
    6. Processes ForkCompletedEvent for early destruction
    """

    def __init__(
        self,
        event_bus,
        parent_service_id: str,
        max_concurrent_forks: int = 10,
        cleanup_interval_seconds: int = 1800
    ):
        """
        Initialize fork manager.

        Args:
            event_bus: Event bus for fork lifecycle events
            parent_service_id: Tiger Cloud parent service ID to fork from
            max_concurrent_forks: Maximum number of concurrent forks allowed
            cleanup_interval_seconds: How often to check for expired forks
        """
        super().__init__("fork_manager", event_bus)
        self.parent_service_id = parent_service_id
        self.max_concurrent_forks = max_concurrent_forks
        self.cleanup_interval = cleanup_interval_seconds
        self.active_forks: Dict[str, dict] = {}  # fork_id -> metadata

    async def start(self):
        """Start fork manager"""
        logger.info(f"Starting Fork Manager for parent service {self.parent_service_id}")

        # Subscribe to fork requests and completions
        request_queue = self.event_bus.subscribe(ForkRequestEvent)
        completed_queue = self.event_bus.subscribe(ForkCompletedEvent)

        # Run event loops concurrently
        await asyncio.gather(
            self._process_fork_requests(request_queue),
            self._process_fork_completions(completed_queue),
            self._cleanup_expired_forks()
        )

    async def _process_fork_requests(self, queue):
        """Process fork creation requests"""
        logger.info("Fork request processor started")

        async for request in self._consume_events(queue):
            try:
                await self._create_fork(request)
            except Exception as e:
                logger.error(f"Error processing fork request: {e}", exc_info=True)

    async def _process_fork_completions(self, queue):
        """Process fork completion events"""
        logger.info("Fork completion processor started")

        async for event in self._consume_events(queue):
            try:
                await self._handle_fork_completion(event)
            except Exception as e:
                logger.error(f"Error processing fork completion: {e}", exc_info=True)

    async def _create_fork(self, request: ForkRequestEvent):
        """
        Create database fork using Tiger Cloud CLI.

        Args:
            request: Fork request event with requester and TTL info
        """
        # Check concurrent limit
        if len(self.active_forks) >= self.max_concurrent_forks:
            logger.warning(
                f"Max concurrent forks reached ({self.max_concurrent_forks}), "
                f"queuing request from {request.requesting_agent}"
            )
            # TODO: Implement request queue for when limit is reached
            return

        logger.info(
            f"Creating fork for {request.requesting_agent} "
            f"(purpose: {request.purpose}, TTL: {request.ttl_seconds}s)"
        )

        try:
            # Call Tiger Cloud CLI to create fork
            # tsdb service fork <parent-service-id>
            result = subprocess.run(
                ['tsdb', 'service', 'fork', self.parent_service_id],
                capture_output=True,
                text=True,
                check=True,
                timeout=300  # 5 minute timeout for fork creation
            )

            # Parse CLI output to get fork service ID
            output = json.loads(result.stdout)
            fork_service_id = output['service_id']

            logger.info(f"Fork created successfully: {fork_service_id}")

            # Get connection parameters for the fork
            fork_connection = await self._get_fork_connection_params(fork_service_id)

            # Track fork metadata
            self.active_forks[fork_service_id] = {
                'requesting_agent': request.requesting_agent,
                'purpose': request.purpose,
                'created_at': datetime.now(),
                'ttl_seconds': request.ttl_seconds,
                'connection_params': fork_connection
            }

            # Persist to database
            await self._persist_fork_metadata(fork_service_id, request)

            # Publish fork created event
            await self.publish(ForkCreatedEvent(
                fork_id=fork_service_id,
                service_id=fork_service_id,
                connection_params=fork_connection,
                requesting_agent=request.requesting_agent
            ))

            logger.info(
                f"Fork {fork_service_id} created and available for "
                f"{request.requesting_agent}"
            )

        except subprocess.TimeoutExpired:
            logger.error(f"Fork creation timed out after 5 minutes")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create fork: {e.stderr}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse fork creation output: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating fork: {e}", exc_info=True)

    async def _get_fork_connection_params(self, fork_service_id: str) -> Dict[str, str]:
        """
        Get connection parameters for a fork.

        Args:
            fork_service_id: The fork service ID

        Returns:
            Dictionary with connection parameters (host, port, database, etc.)
        """
        try:
            # Get fork service details via CLI
            result = subprocess.run(
                ['tsdb', 'service', 'show', fork_service_id],
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )

            service_info = json.loads(result.stdout)

            # Extract connection parameters
            connection_params = {
                'host': service_info.get('host'),
                'port': service_info.get('port', 5432),
                'database': service_info.get('database', 'tsdb'),
                'username': service_info.get('username', 'tsdbadmin'),
                'service_id': fork_service_id
            }

            return connection_params

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get fork connection params: {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"Error getting fork connection params: {e}", exc_info=True)
            raise

    async def _persist_fork_metadata(self, fork_id: str, request: ForkRequestEvent):
        """
        Persist fork metadata to database.

        Args:
            fork_id: The fork service ID
            request: Original fork request
        """
        db = get_db_manager()
        conn = await db.get_connection()

        try:
            await conn.execute("""
                INSERT INTO fork_tracking (
                    fork_id,
                    parent_service_id,
                    requesting_agent,
                    purpose,
                    created_at,
                    ttl_seconds,
                    status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                fork_id,
                self.parent_service_id,
                request.requesting_agent,
                request.purpose,
                datetime.now(),
                request.ttl_seconds,
                'active'
            )

            logger.debug(f"Fork metadata persisted for {fork_id}")

        except Exception as e:
            logger.error(f"Failed to persist fork metadata: {e}", exc_info=True)
            # Non-fatal - fork is still usable
        finally:
            await db.release_connection(conn)

    async def _handle_fork_completion(self, event: ForkCompletedEvent):
        """
        Handle fork completion event (early destruction).

        Args:
            event: Fork completed event
        """
        fork_id = event.fork_id

        if fork_id not in self.active_forks:
            logger.warning(f"Received completion for unknown fork: {fork_id}")
            return

        logger.info(f"Fork {fork_id} completed by {event.requesting_agent}, destroying")
        await self._destroy_fork(fork_id)

    async def _destroy_fork(self, fork_id: str):
        """
        Destroy database fork.

        Args:
            fork_id: The fork service ID to destroy
        """
        if fork_id not in self.active_forks:
            logger.warning(f"Attempted to destroy unknown fork: {fork_id}")
            return

        try:
            logger.info(f"Destroying fork {fork_id}")

            # Call Tiger Cloud CLI to delete fork
            subprocess.run(
                ['tsdb', 'service', 'delete', fork_id, '--force'],
                capture_output=True,
                text=True,
                check=True,
                timeout=120
            )

            # Remove from tracking
            metadata = self.active_forks.pop(fork_id)

            # Update database
            db = get_db_manager()
            conn = await db.get_connection()
            try:
                await conn.execute("""
                    UPDATE fork_tracking
                    SET status = 'destroyed', destroyed_at = NOW()
                    WHERE fork_id = $1
                """, fork_id)
            finally:
                await db.release_connection(conn)

            logger.info(
                f"Fork {fork_id} destroyed (was used by "
                f"{metadata['requesting_agent']})"
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to destroy fork {fork_id}: {e.stderr}")
        except Exception as e:
            logger.error(f"Error destroying fork {fork_id}: {e}", exc_info=True)

    async def _cleanup_expired_forks(self):
        """Periodically cleanup expired forks based on TTL"""
        logger.info(
            f"Fork cleanup task started (interval: {self.cleanup_interval}s)"
        )

        while True:
            await asyncio.sleep(self.cleanup_interval)

            try:
                now = datetime.now()
                expired_forks = []

                # Find expired forks
                for fork_id, metadata in self.active_forks.items():
                    age_seconds = (now - metadata['created_at']).total_seconds()
                    if age_seconds > metadata['ttl_seconds']:
                        expired_forks.append(fork_id)
                        logger.info(
                            f"Fork {fork_id} expired (age: {age_seconds:.0f}s, "
                            f"TTL: {metadata['ttl_seconds']}s)"
                        )

                # Destroy expired forks
                for fork_id in expired_forks:
                    await self._destroy_fork(fork_id)

                if expired_forks:
                    logger.info(f"Cleaned up {len(expired_forks)} expired fork(s)")

            except Exception as e:
                logger.error(f"Error during fork cleanup: {e}", exc_info=True)

    def get_active_forks(self) -> Dict[str, dict]:
        """
        Get currently active forks.

        Returns:
            Dictionary of fork_id -> metadata
        """
        return self.active_forks.copy()

    def get_fork_count(self) -> int:
        """
        Get count of active forks.

        Returns:
            Number of active forks
        """
        return len(self.active_forks)

    async def stop(self):
        """Stop fork manager and cleanup all active forks"""
        logger.info(f"Stopping Fork Manager, cleaning up {len(self.active_forks)} active fork(s)")

        # Destroy all active forks
        fork_ids = list(self.active_forks.keys())
        for fork_id in fork_ids:
            try:
                await self._destroy_fork(fork_id)
            except Exception as e:
                logger.error(f"Error destroying fork {fork_id} during shutdown: {e}")

        logger.info("Fork Manager stopped")
