"""
Tests for event bus
"""
import pytest
import asyncio
from decimal import Decimal

from src.core.event_bus import EventBus, consume_events, consume_events_with_timeout
from src.models.events import (
    Event,
    MarketTickEvent,
    TradingSignalEvent,
    TradeExecutedEvent
)


@pytest.mark.asyncio
class TestEventBus:
    """Test EventBus functionality"""

    async def test_event_bus_creation(self):
        """Test creating an event bus"""
        bus = EventBus()
        assert bus is not None
        assert bus.published_count == 0

    async def test_subscribe(self):
        """Test subscribing to events"""
        bus = EventBus()
        queue = bus.subscribe(MarketTickEvent)

        assert queue is not None
        assert bus.get_subscriber_count(MarketTickEvent) == 1

    async def test_multiple_subscribers(self):
        """Test multiple subscribers to same event type"""
        bus = EventBus()

        queue1 = bus.subscribe(MarketTickEvent)
        queue2 = bus.subscribe(MarketTickEvent)

        assert bus.get_subscriber_count(MarketTickEvent) == 2

    async def test_publish_and_receive(self):
        """Test publishing and receiving events"""
        bus = EventBus()
        queue = bus.subscribe(MarketTickEvent)

        # Publish event
        event = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000.00'),
            volume=Decimal('1.0')
        )
        await bus.publish(event)

        # Receive event
        received = await asyncio.wait_for(queue.get(), timeout=1.0)

        assert received == event
        assert received.symbol == 'BTCUSDT'
        assert received.price == Decimal('50000.00')

    async def test_publish_to_multiple_subscribers(self):
        """Test that all subscribers receive events"""
        bus = EventBus()

        queue1 = bus.subscribe(MarketTickEvent)
        queue2 = bus.subscribe(MarketTickEvent)

        event = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000.00'),
            volume=Decimal('1.0')
        )
        await bus.publish(event)

        # Both queues should receive the event
        received1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
        received2 = await asyncio.wait_for(queue2.get(), timeout=1.0)

        assert received1 == event
        assert received2 == event

    async def test_type_filtering(self):
        """Test that subscribers only receive subscribed event types"""
        bus = EventBus()

        tick_queue = bus.subscribe(MarketTickEvent)
        signal_queue = bus.subscribe(TradingSignalEvent)

        # Publish different event types
        tick_event = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000.00'),
            volume=Decimal('1.0')
        )
        signal_event = TradingSignalEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            confidence=Decimal('0.75'),
            reason='Test'
        )

        await bus.publish(tick_event)
        await bus.publish(signal_event)

        # Each queue should only receive its subscribed type
        received_tick = await asyncio.wait_for(tick_queue.get(), timeout=1.0)
        received_signal = await asyncio.wait_for(signal_queue.get(), timeout=1.0)

        assert isinstance(received_tick, MarketTickEvent)
        assert isinstance(received_signal, TradingSignalEvent)

        # Queues should be empty now
        assert tick_queue.empty()
        assert signal_queue.empty()

    async def test_unsubscribe(self):
        """Test unsubscribing from events"""
        bus = EventBus()
        queue = bus.subscribe(MarketTickEvent)

        assert bus.get_subscriber_count(MarketTickEvent) == 1

        bus.unsubscribe(MarketTickEvent, queue)

        assert bus.get_subscriber_count(MarketTickEvent) == 0

    async def test_publish_with_no_subscribers(self):
        """Test publishing when no subscribers exist"""
        bus = EventBus()

        event = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000.00'),
            volume=Decimal('1.0')
        )

        # Should not raise an error
        await bus.publish(event)

        assert bus.published_count == 1

    async def test_queue_full_handling(self):
        """Test handling when subscriber queue is full"""
        bus = EventBus(max_queue_size=2)
        queue = bus.subscribe(MarketTickEvent)

        # Fill the queue
        for i in range(3):
            event = MarketTickEvent(
                symbol='BTCUSDT',
                price=Decimal(f'{50000 + i}.00'),
                volume=Decimal('1.0')
            )
            await bus.publish(event)

        # Queue should have max 2 items (3rd dropped)
        assert queue.qsize() <= 2

    async def test_publish_multiple(self):
        """Test publishing multiple events at once"""
        bus = EventBus()
        queue = bus.subscribe(MarketTickEvent)

        events = [
            MarketTickEvent(
                symbol='BTCUSDT',
                price=Decimal(f'{50000 + i}.00'),
                volume=Decimal('1.0')
            )
            for i in range(5)
        ]

        await bus.publish_multiple(events)

        # Should receive all events
        assert queue.qsize() == 5

    async def test_get_stats(self):
        """Test getting event bus statistics"""
        bus = EventBus()

        bus.subscribe(MarketTickEvent)
        bus.subscribe(TradingSignalEvent)
        bus.subscribe(MarketTickEvent)  # Second subscriber

        event = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000.00'),
            volume=Decimal('1.0')
        )
        await bus.publish(event)

        stats = bus.get_stats()

        assert stats['total_published'] == 1
        assert stats['total_subscribers'] == 3
        assert 'MarketTickEvent' in stats['event_types']
        assert stats['subscribers_by_type']['MarketTickEvent'] == 2

    async def test_close(self):
        """Test closing event bus"""
        bus = EventBus()
        queue = bus.subscribe(MarketTickEvent)

        event = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000.00'),
            volume=Decimal('1.0')
        )
        await bus.publish(event)

        await bus.close()

        assert bus.get_total_subscribers() == 0


@pytest.mark.asyncio
class TestEventConsumption:
    """Test event consumption utilities"""

    async def test_consume_events(self):
        """Test consuming events with async iterator"""
        bus = EventBus()
        queue = bus.subscribe(MarketTickEvent)

        # Publish events
        events = [
            MarketTickEvent(
                symbol='BTCUSDT',
                price=Decimal(f'{50000 + i}.00'),
                volume=Decimal('1.0')
            )
            for i in range(3)
        ]

        for event in events:
            await bus.publish(event)

        # Consume with timeout
        consumed = []
        consumer = consume_events(queue)

        # Consume 3 events then cancel
        for _ in range(3):
            event = await asyncio.wait_for(consumer.__anext__(), timeout=1.0)
            consumed.append(event)

        assert len(consumed) == 3
        assert all(isinstance(e, MarketTickEvent) for e in consumed)

    async def test_consume_events_with_timeout(self):
        """Test consuming events with timeout"""
        bus = EventBus()
        queue = bus.subscribe(MarketTickEvent)

        # Publish one event
        event = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000.00'),
            volume=Decimal('1.0')
        )
        await bus.publish(event)

        consumer = consume_events_with_timeout(queue, timeout=0.1)

        # Should get the event
        received = await consumer.__anext__()
        assert received == event

        # Should get None on timeout
        received = await consumer.__anext__()
        assert received is None


@pytest.mark.asyncio
class TestConcurrentOperations:
    """Test concurrent event bus operations"""

    async def test_concurrent_publish(self):
        """Test publishing from multiple tasks concurrently"""
        bus = EventBus()
        queue = bus.subscribe(MarketTickEvent)

        async def publish_events(count: int):
            for i in range(count):
                event = MarketTickEvent(
                    symbol='BTCUSDT',
                    price=Decimal(f'{50000 + i}.00'),
                    volume=Decimal('1.0')
                )
                await bus.publish(event)

        # Publish concurrently from 3 tasks
        await asyncio.gather(
            publish_events(10),
            publish_events(10),
            publish_events(10)
        )

        # Should have received all 30 events
        assert queue.qsize() == 30

    async def test_concurrent_subscribe_and_publish(self):
        """Test subscribing and publishing concurrently"""
        bus = EventBus()

        async def subscribe_and_consume():
            queue = bus.subscribe(MarketTickEvent)
            event = await asyncio.wait_for(queue.get(), timeout=2.0)
            return event

        async def publish_events():
            await asyncio.sleep(0.1)  # Small delay
            event = MarketTickEvent(
                symbol='BTCUSDT',
                price=Decimal('50000.00'),
                volume=Decimal('1.0')
            )
            await bus.publish(event)

        # Run both concurrently
        results = await asyncio.gather(
            subscribe_and_consume(),
            publish_events()
        )

        # First task should have received the event
        assert isinstance(results[0], MarketTickEvent)
