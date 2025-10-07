"""
Base Agent Class

Abstract base class for all agents in the Icarus trading system.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Type, AsyncIterator
from datetime import datetime

from src.core.event_bus import EventBus, consume_events
from src.models.events import (
    Event,
    AgentStartedEvent,
    AgentStoppedEvent,
    AgentErrorEvent,
    AgentHeartbeatEvent
)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all agents

    Features:
    - Event bus integration
    - Lifecycle management (start/stop)
    - Health monitoring
    - Error handling
    - Event publishing/consuming
    """

    def __init__(self, name: str, event_bus: EventBus):
        """
        Initialize agent

        Args:
            name: Unique agent name
            event_bus: Event bus for communication
        """
        self.name = name
        self.event_bus = event_bus
        self._running = False
        self._task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._heartbeat_interval = 30  # seconds
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    async def start(self) -> None:
        """
        Start the agent

        Must be implemented by subclasses.
        This is where the agent's main logic runs.
        """
        pass

    async def run(self) -> None:
        """
        Run the agent with lifecycle management

        Handles startup, error catching, and cleanup.
        """
        try:
            self._running = True
            self.logger.info(f"Starting agent: {self.name}")

            # Publish started event
            await self.publish(AgentStartedEvent(
                agent_name=self.name,
                config=None
            ))

            # Start heartbeat
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Run agent logic
            await self.start()

        except asyncio.CancelledError:
            self.logger.info(f"Agent {self.name} cancelled")
            raise

        except Exception as e:
            self.logger.error(f"Agent {self.name} error: {e}", exc_info=True)

            # Publish error event
            await self.publish(AgentErrorEvent(
                agent_name=self.name,
                error_type=type(e).__name__,
                error_message=str(e),
                is_fatal=True
            ))

            raise

        finally:
            await self._cleanup()

    async def stop(self) -> None:
        """
        Stop the agent gracefully

        Can be overridden by subclasses for custom cleanup.
        """
        self.logger.info(f"Stopping agent: {self.name}")
        self._running = False

    async def _cleanup(self) -> None:
        """Internal cleanup logic"""
        self._running = False

        # Stop heartbeat
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Call custom cleanup
        await self.stop()

        # Publish stopped event
        await self.publish(AgentStoppedEvent(
            agent_name=self.name,
            reason="normal_shutdown"
        ))

        self.logger.info(f"Agent {self.name} stopped")

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat events"""
        while self._running:
            try:
                await self.publish(AgentHeartbeatEvent(
                    agent_name=self.name,
                    status='running'
                ))

                await asyncio.sleep(self._heartbeat_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(self._heartbeat_interval)

    # ========================================================================
    # Event Bus Helpers
    # ========================================================================

    async def publish(self, event: Event) -> None:
        """
        Publish an event to the event bus

        Args:
            event: Event to publish
        """
        try:
            await self.event_bus.publish(event)
        except Exception as e:
            self.logger.error(f"Failed to publish event: {e}")

    def subscribe(self, event_type: Type[Event]) -> asyncio.Queue:
        """
        Subscribe to events of a specific type

        Args:
            event_type: Event class to subscribe to

        Returns:
            Queue that will receive matching events
        """
        return self.event_bus.subscribe(event_type)

    async def _consume_events(self, queue: asyncio.Queue) -> AsyncIterator[Event]:
        """
        Consume events from a queue

        Args:
            queue: Queue to consume from

        Yields:
            Events from the queue
        """
        async for event in consume_events(queue):
            if not self._running:
                break
            yield event

    # ========================================================================
    # Status & Health
    # ========================================================================

    @property
    def is_running(self) -> bool:
        """Check if agent is running"""
        return self._running

    async def get_status(self) -> dict:
        """
        Get agent status

        Returns:
            Dictionary with agent status information
        """
        return {
            'name': self.name,
            'running': self._running,
            'timestamp': datetime.now().isoformat()
        }

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def __repr__(self) -> str:
        status = "running" if self._running else "stopped"
        return f"{self.__class__.__name__}(name='{self.name}', status='{status}')"


class PeriodicAgent(BaseAgent):
    """
    Base class for agents that run periodically

    Useful for agents that need to perform actions at regular intervals.
    """

    def __init__(
        self,
        name: str,
        event_bus: EventBus,
        interval_seconds: float = 60.0
    ):
        """
        Initialize periodic agent

        Args:
            name: Agent name
            event_bus: Event bus
            interval_seconds: Seconds between iterations
        """
        super().__init__(name, event_bus)
        self.interval_seconds = interval_seconds

    @abstractmethod
    async def iterate(self) -> None:
        """
        Perform one iteration of work

        Must be implemented by subclasses.
        """
        pass

    async def start(self) -> None:
        """Run periodic iterations"""
        while self._running:
            try:
                await self.iterate()
            except Exception as e:
                self.logger.error(f"Iteration error: {e}", exc_info=True)

            # Wait for next iteration
            await asyncio.sleep(self.interval_seconds)


class EventDrivenAgent(BaseAgent):
    """
    Base class for agents driven by events

    Subscribes to specific event types and processes them.
    """

    def __init__(self, name: str, event_bus: EventBus):
        super().__init__(name, event_bus)
        self._event_subscriptions: list[tuple[Type[Event], asyncio.Queue]] = []

    def add_subscription(self, event_type: Type[Event]) -> None:
        """
        Add an event subscription

        Args:
            event_type: Event class to subscribe to
        """
        queue = self.subscribe(event_type)
        self._event_subscriptions.append((event_type, queue))

    @abstractmethod
    async def handle_event(self, event: Event) -> None:
        """
        Handle an incoming event

        Must be implemented by subclasses.

        Args:
            event: Event to handle
        """
        pass

    async def start(self) -> None:
        """Start processing events from subscriptions"""
        if not self._event_subscriptions:
            self.logger.warning("No event subscriptions configured")
            return

        # Create tasks for each subscription
        tasks = [
            self._process_queue(queue)
            for _, queue in self._event_subscriptions
        ]

        # Run all tasks concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_queue(self, queue: asyncio.Queue) -> None:
        """Process events from a specific queue"""
        async for event in self._consume_events(queue):
            try:
                await self.handle_event(event)
            except Exception as e:
                self.logger.error(f"Error handling event: {e}", exc_info=True)


class StatefulAgent(BaseAgent):
    """
    Base class for agents that maintain state

    Provides state persistence and recovery.
    """

    def __init__(self, name: str, event_bus: EventBus):
        super().__init__(name, event_bus)
        self._state: dict = {}

    def get_state(self, key: str, default=None):
        """Get state value"""
        return self._state.get(key, default)

    def set_state(self, key: str, value) -> None:
        """Set state value"""
        self._state[key] = value

    def clear_state(self) -> None:
        """Clear all state"""
        self._state.clear()

    async def save_state(self) -> None:
        """
        Save state to persistent storage

        Can be overridden by subclasses for actual persistence.
        """
        pass

    async def load_state(self) -> None:
        """
        Load state from persistent storage

        Can be overridden by subclasses for actual persistence.
        """
        pass
