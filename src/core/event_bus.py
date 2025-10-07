"""
Event Bus

Async pub/sub system for inter-agent communication.
Uses asyncio queues for message passing.
"""
import asyncio
import logging
from typing import Type, Dict, List
from collections import defaultdict
from src.models.events import BaseEvent

logger = logging.getLogger(__name__)


class EventBus:
    """
    Asynchronous event bus for publish-subscribe messaging.

    Agents can subscribe to specific event types and publish events
    that will be delivered to all subscribers.
    """

    def __init__(self):
        self._subscriptions: Dict[Type[BaseEvent], List[asyncio.Queue]] = defaultdict(list)
        self._running = True

    def subscribe(self, event_type: Type[BaseEvent]) -> asyncio.Queue:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: The event class to subscribe to

        Returns:
            Queue that will receive events of the specified type
        """
        queue = asyncio.Queue(maxsize=1000)
        self._subscriptions[event_type].append(queue)
        logger.debug(f"New subscription to {event_type.__name__}")
        return queue

    async def publish(self, event: BaseEvent):
        """
        Publish an event to all subscribers.

        Args:
            event: The event to publish
        """
        event_type = type(event)
        subscribers = self._subscriptions.get(event_type, [])

        if not subscribers:
            logger.debug(f"No subscribers for {event_type.__name__}")
            return

        logger.debug(f"Publishing {event_type.__name__} to {len(subscribers)} subscribers")

        # Put event in all subscriber queues
        for queue in subscribers:
            try:
                await queue.put(event)
            except asyncio.QueueFull:
                logger.warning(f"Queue full for {event_type.__name__}, dropping event")

    def unsubscribe(self, event_type: Type[BaseEvent], queue: asyncio.Queue):
        """
        Unsubscribe from events.

        Args:
            event_type: The event class to unsubscribe from
            queue: The queue to remove
        """
        if event_type in self._subscriptions:
            try:
                self._subscriptions[event_type].remove(queue)
                logger.debug(f"Unsubscribed from {event_type.__name__}")
            except ValueError:
                pass

    async def close(self):
        """Cleanup resources"""
        self._running = False
        # Clear all queues
        for queues in self._subscriptions.values():
            for queue in queues:
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
        self._subscriptions.clear()
        logger.info("Event bus closed")


# Global event bus instance
_event_bus = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
