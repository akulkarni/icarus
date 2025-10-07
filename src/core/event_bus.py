"""
Event Bus

AsyncIO-based publish/subscribe event bus for inter-agent communication.
"""
import asyncio
import logging
from typing import Any, Type, AsyncIterator
from collections import defaultdict
from src.models.events import Event, get_event_type

logger = logging.getLogger(__name__)


class EventBus:
    """
    Asynchronous publish/subscribe event bus

    Features:
    - Type-based subscriptions (subscribe to specific event types)
    - Multiple subscribers per event type
    - Non-blocking publish
    - Automatic event logging
    """

    def __init__(self, max_queue_size: int = 1000):
        """
        Initialize event bus

        Args:
            max_queue_size: Maximum events in each subscriber queue
        """
        self.max_queue_size = max_queue_size
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._running = False
        self._published_count = 0
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: Type[Event]) -> asyncio.Queue:
        """
        Subscribe to events of a specific type

        Args:
            event_type: Event class to subscribe to

        Returns:
            Queue that will receive matching events

        Example:
            queue = event_bus.subscribe(MarketTickEvent)
            async for event in consume_queue(queue):
                process(event)
        """
        event_type_name = event_type.__name__
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.max_queue_size)

        self._subscribers[event_type_name].append(queue)

        logger.debug(f"Subscriber added for {event_type_name} "
                    f"(total: {len(self._subscribers[event_type_name])})")

        return queue

    def unsubscribe(self, event_type: Type[Event], queue: asyncio.Queue) -> None:
        """
        Unsubscribe a queue from an event type

        Args:
            event_type: Event class to unsubscribe from
            queue: The queue to remove
        """
        event_type_name = event_type.__name__

        if event_type_name in self._subscribers:
            try:
                self._subscribers[event_type_name].remove(queue)
                logger.debug(f"Subscriber removed for {event_type_name}")
            except ValueError:
                logger.warning(f"Queue not found in subscribers for {event_type_name}")

    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers

        Args:
            event: Event instance to publish

        Note:
            If a subscriber's queue is full, the event will be dropped
            for that subscriber (non-blocking publish)
        """
        event_type_name = get_event_type(event)

        # Get subscribers for this event type
        subscribers = self._subscribers.get(event_type_name, [])

        if not subscribers:
            logger.debug(f"No subscribers for {event_type_name}")
            return

        # Publish to all subscribers
        delivered = 0
        dropped = 0

        for queue in subscribers:
            try:
                # Non-blocking put - drop if queue is full
                queue.put_nowait(event)
                delivered += 1
            except asyncio.QueueFull:
                dropped += 1
                logger.warning(
                    f"Queue full for {event_type_name}, event dropped "
                    f"(queue size: {queue.qsize()})"
                )

        self._published_count += 1

        logger.debug(
            f"Published {event_type_name} to {delivered} subscribers "
            f"({dropped} dropped)"
        )

    async def publish_multiple(self, events: list[Event]) -> None:
        """
        Publish multiple events efficiently

        Args:
            events: List of events to publish
        """
        for event in events:
            await self.publish(event)

    def get_subscriber_count(self, event_type: Type[Event]) -> int:
        """Get number of subscribers for an event type"""
        event_type_name = event_type.__name__
        return len(self._subscribers.get(event_type_name, []))

    def get_total_subscribers(self) -> int:
        """Get total number of active subscribers across all event types"""
        return sum(len(queues) for queues in self._subscribers.values())

    @property
    def published_count(self) -> int:
        """Get total number of events published"""
        return self._published_count

    async def close(self) -> None:
        """
        Close the event bus and cleanup resources

        Clears all subscriber queues.
        """
        logger.info("Closing event bus")

        # Clear all queues
        for event_type_name, queues in self._subscribers.items():
            for queue in queues:
                # Drain queue
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

        self._subscribers.clear()
        logger.info("Event bus closed")

    def get_stats(self) -> dict[str, Any]:
        """
        Get event bus statistics

        Returns:
            Dictionary with stats about event bus usage
        """
        return {
            'total_published': self._published_count,
            'total_subscribers': self.get_total_subscribers(),
            'event_types': list(self._subscribers.keys()),
            'subscribers_by_type': {
                event_type: len(queues)
                for event_type, queues in self._subscribers.items()
            }
        }


# ============================================================================
# Global Event Bus Instance
# ============================================================================

_event_bus: EventBus | None = None
_event_bus_lock = asyncio.Lock()


async def get_event_bus() -> EventBus:
    """
    Get global event bus instance (singleton)

    Returns:
        Global EventBus instance
    """
    global _event_bus

    async with _event_bus_lock:
        if _event_bus is None:
            _event_bus = EventBus()
            logger.info("Global event bus created")

    return _event_bus


def get_event_bus_sync() -> EventBus:
    """
    Get global event bus instance (synchronous, for initialization)

    Returns:
        Global EventBus instance

    Note:
        Creates event bus if it doesn't exist. Use get_event_bus() for async code.
    """
    global _event_bus

    if _event_bus is None:
        _event_bus = EventBus()
        logger.info("Global event bus created (sync)")

    return _event_bus


async def close_event_bus() -> None:
    """Close the global event bus"""
    global _event_bus

    if _event_bus is not None:
        await _event_bus.close()
        _event_bus = None


# ============================================================================
# Utility Functions
# ============================================================================

async def consume_events(queue: asyncio.Queue) -> AsyncIterator[Event]:
    """
    Async generator to consume events from a queue

    Args:
        queue: Queue to consume from

    Yields:
        Events from the queue

    Example:
        queue = event_bus.subscribe(MarketTickEvent)
        async for event in consume_events(queue):
            print(event)
    """
    while True:
        try:
            event = await queue.get()
            yield event
        except asyncio.CancelledError:
            logger.info("Event consumer cancelled")
            break
        except Exception as e:
            logger.error(f"Error consuming event: {e}")
            break


async def consume_events_with_timeout(
    queue: asyncio.Queue,
    timeout: float = 1.0
) -> AsyncIterator[Event | None]:
    """
    Consume events with timeout between events

    Args:
        queue: Queue to consume from
        timeout: Timeout in seconds

    Yields:
        Event or None (on timeout)
    """
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=timeout)
            yield event
        except asyncio.TimeoutError:
            yield None
        except asyncio.CancelledError:
            logger.info("Event consumer cancelled")
            break
        except Exception as e:
            logger.error(f"Error consuming event: {e}")
            break
