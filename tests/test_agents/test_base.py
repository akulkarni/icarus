"""
Tests for base agent classes
"""
import pytest
import asyncio
from decimal import Decimal

from src.core.event_bus import EventBus
from src.agents.base import BaseAgent, PeriodicAgent, EventDrivenAgent, StatefulAgent
from src.models.events import (
    Event,
    MarketTickEvent,
    TradingSignalEvent,
    AgentStartedEvent,
    AgentStoppedEvent,
    AgentHeartbeatEvent
)


# ============================================================================
# Test Agent Implementations
# ============================================================================

class TestAgent(BaseAgent):
    """Simple test agent"""

    def __init__(self, name: str, event_bus: EventBus):
        super().__init__(name, event_bus)
        self.iterations = 0

    async def start(self):
        """Run for a few iterations"""
        while self._running and self.iterations < 3:
            self.iterations += 1
            await asyncio.sleep(0.1)


class TestPeriodicAgent(PeriodicAgent):
    """Test periodic agent"""

    def __init__(self, name: str, event_bus: EventBus, interval_seconds: float = 0.1):
        super().__init__(name, event_bus, interval_seconds)
        self.iteration_count = 0

    async def iterate(self):
        self.iteration_count += 1
        if self.iteration_count >= 3:
            self._running = False


class TestEventDrivenAgent(EventDrivenAgent):
    """Test event-driven agent"""

    def __init__(self, name: str, event_bus: EventBus):
        super().__init__(name, event_bus)
        self.handled_events = []
        self.add_subscription(MarketTickEvent)

    async def handle_event(self, event: Event):
        self.handled_events.append(event)
        if len(self.handled_events) >= 3:
            self._running = False


# ============================================================================
# Tests
# ============================================================================

@pytest.mark.asyncio
class TestBaseAgent:
    """Test BaseAgent functionality"""

    async def test_agent_creation(self):
        """Test creating an agent"""
        event_bus = EventBus()
        agent = TestAgent("test_agent", event_bus)

        assert agent.name == "test_agent"
        assert agent.event_bus == event_bus
        assert not agent.is_running

    async def test_agent_start_stop(self):
        """Test starting and stopping an agent"""
        event_bus = EventBus()
        agent = TestAgent("test_agent", event_bus)

        # Start agent
        task = asyncio.create_task(agent.run())

        # Wait a bit
        await asyncio.sleep(0.2)

        # Agent should be running
        assert agent.is_running

        # Stop agent
        await agent.stop()
        await task

        # Agent should be stopped
        assert not agent.is_running

    async def test_agent_lifecycle_events(self):
        """Test that agent publishes lifecycle events"""
        event_bus = EventBus()
        agent = TestAgent("test_agent", event_bus)

        # Subscribe to lifecycle events
        started_queue = event_bus.subscribe(AgentStartedEvent)
        stopped_queue = event_bus.subscribe(AgentStoppedEvent)

        # Run agent
        task = asyncio.create_task(agent.run())

        # Should receive started event
        started = await asyncio.wait_for(started_queue.get(), timeout=1.0)
        assert isinstance(started, AgentStartedEvent)
        assert started.agent_name == "test_agent"

        # Wait for agent to complete
        await asyncio.wait_for(task, timeout=2.0)

        # Should receive stopped event
        stopped = await asyncio.wait_for(stopped_queue.get(), timeout=1.0)
        assert isinstance(stopped, AgentStoppedEvent)
        assert stopped.agent_name == "test_agent"

    async def test_agent_heartbeat(self):
        """Test that agent sends heartbeats"""
        event_bus = EventBus()
        agent = TestAgent("test_agent", event_bus)
        agent._heartbeat_interval = 0.1  # Fast heartbeat for testing

        # Subscribe to heartbeats
        heartbeat_queue = event_bus.subscribe(AgentHeartbeatEvent)

        # Start agent
        task = asyncio.create_task(agent.run())

        # Should receive at least one heartbeat
        heartbeat = await asyncio.wait_for(heartbeat_queue.get(), timeout=1.0)
        assert isinstance(heartbeat, AgentHeartbeatEvent)
        assert heartbeat.agent_name == "test_agent"
        assert heartbeat.status == 'running'

        # Cleanup
        await agent.stop()
        await task

    async def test_agent_publish(self):
        """Test agent publishing events"""
        event_bus = EventBus()
        agent = TestAgent("test_agent", event_bus)

        # Subscribe to events
        queue = event_bus.subscribe(MarketTickEvent)

        # Publish event through agent
        event = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000.00'),
            volume=Decimal('1.0')
        )
        await agent.publish(event)

        # Should receive the event
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received == event

    async def test_agent_subscribe(self):
        """Test agent subscribing to events"""
        event_bus = EventBus()
        agent = TestAgent("test_agent", event_bus)

        # Subscribe through agent
        queue = agent.subscribe(MarketTickEvent)

        # Publish event
        event = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000.00'),
            volume=Decimal('1.0')
        )
        await event_bus.publish(event)

        # Should receive the event
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received == event

    async def test_agent_status(self):
        """Test getting agent status"""
        event_bus = EventBus()
        agent = TestAgent("test_agent", event_bus)

        status = await agent.get_status()

        assert status['name'] == "test_agent"
        assert status['running'] == False
        assert 'timestamp' in status

    async def test_agent_repr(self):
        """Test agent string representation"""
        event_bus = EventBus()
        agent = TestAgent("test_agent", event_bus)

        repr_str = repr(agent)
        assert "test_agent" in repr_str
        assert "stopped" in repr_str


@pytest.mark.asyncio
class TestPeriodicAgent:
    """Test PeriodicAgent functionality"""

    async def test_periodic_iterations(self):
        """Test that periodic agent runs iterations"""
        event_bus = EventBus()
        agent = TestPeriodicAgent("periodic", event_bus, interval_seconds=0.1)

        # Run agent
        await asyncio.wait_for(agent.run(), timeout=2.0)

        # Should have run 3 iterations
        assert agent.iteration_count == 3

    async def test_periodic_interval(self):
        """Test that periodic agent respects interval"""
        event_bus = EventBus()
        agent = TestPeriodicAgent("periodic", event_bus, interval_seconds=0.2)

        start_time = asyncio.get_event_loop().time()

        # Run agent
        await asyncio.wait_for(agent.run(), timeout=3.0)

        elapsed = asyncio.get_event_loop().time() - start_time

        # Should take at least 0.6 seconds (3 iterations * 0.2s)
        assert elapsed >= 0.6


@pytest.mark.asyncio
class TestEventDrivenAgent:
    """Test EventDrivenAgent functionality"""

    async def test_event_driven_handling(self):
        """Test that event-driven agent handles events"""
        event_bus = EventBus()
        agent = TestEventDrivenAgent("event_driven", event_bus)

        # Start agent
        task = asyncio.create_task(agent.run())

        # Give agent time to subscribe
        await asyncio.sleep(0.1)

        # Publish events
        for i in range(3):
            event = MarketTickEvent(
                symbol='BTCUSDT',
                price=Decimal(f'{50000 + i}.00'),
                volume=Decimal('1.0')
            )
            await event_bus.publish(event)

        # Wait for agent to process
        await asyncio.wait_for(task, timeout=2.0)

        # Should have handled 3 events
        assert len(agent.handled_events) == 3

    async def test_multiple_subscriptions(self):
        """Test agent with multiple event subscriptions"""
        event_bus = EventBus()
        agent = TestEventDrivenAgent("event_driven", event_bus)

        # Add another subscription
        agent.add_subscription(TradingSignalEvent)

        # Start agent
        task = asyncio.create_task(agent.run())

        await asyncio.sleep(0.1)

        # Publish different event types
        tick = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000.00'),
            volume=Decimal('1.0')
        )
        signal = TradingSignalEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            confidence=Decimal('0.75'),
            reason='Test'
        )

        await event_bus.publish(tick)
        await event_bus.publish(signal)

        await asyncio.sleep(0.2)

        # Stop agent
        agent._running = False
        await task

        # Should have handled both events
        assert len(agent.handled_events) >= 2


@pytest.mark.asyncio
class TestStatefulAgent:
    """Test StatefulAgent functionality"""

    async def test_state_management(self):
        """Test agent state management"""
        event_bus = EventBus()
        agent = StatefulAgent("stateful", event_bus)

        # Set state
        agent.set_state('counter', 10)
        agent.set_state('name', 'test')

        # Get state
        assert agent.get_state('counter') == 10
        assert agent.get_state('name') == 'test'
        assert agent.get_state('missing', 'default') == 'default'

    async def test_clear_state(self):
        """Test clearing agent state"""
        event_bus = EventBus()
        agent = StatefulAgent("stateful", event_bus)

        agent.set_state('key', 'value')
        assert agent.get_state('key') == 'value'

        agent.clear_state()
        assert agent.get_state('key') is None


@pytest.mark.asyncio
class TestAgentErrorHandling:
    """Test agent error handling"""

    async def test_agent_handles_error_in_start(self):
        """Test that agent handles errors in start()"""

        class ErrorAgent(BaseAgent):
            async def start(self):
                raise ValueError("Test error")

        event_bus = EventBus()
        agent = ErrorAgent("error_agent", event_bus)

        # Should raise the error
        with pytest.raises(ValueError):
            await agent.run()

        # Agent should be stopped
        assert not agent.is_running
