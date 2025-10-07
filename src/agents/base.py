"""
Base Agent Class

All agents inherit from this base class.
Provides common functionality for event handling and lifecycle management.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator
from src.core.event_bus import EventBus
from src.models.events import BaseEvent

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.

    Provides:
    - Event bus integration
    - Lifecycle management (start/stop)
    - Event publishing and consumption utilities
    """

    def __init__(self, name: str, event_bus: EventBus):
        """
        Initialize agent.

        Args:
            name: Unique name for this agent
            event_bus: The event bus for pub/sub communication
        """
        self.name = name
        self.event_bus = event_bus
        self._running = False
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    async def start(self):
        """
        Start the agent's main loop.

        This method should contain the agent's primary logic.
        It will be called when the agent is started.
        """
        pass

    async def stop(self):
        """Stop the agent"""
        self._running = False
        self.logger.info(f"Agent {self.name} stopped")

    async def publish(self, event: BaseEvent):
        """
        Publish an event to the event bus.

        Args:
            event: The event to publish
        """
        await self.event_bus.publish(event)
        self.logger.debug(f"Published {type(event).__name__}")

    async def _consume_events(self, queue: asyncio.Queue) -> AsyncIterator[BaseEvent]:
        """
        Consume events from a subscription queue.

        Args:
            queue: The queue to consume from

        Yields:
            Events from the queue
        """
        self._running = True
        while self._running:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error consuming event: {e}")
                continue
