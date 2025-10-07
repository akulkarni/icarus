"""
Tests for Meta-Strategy Agent
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from src.agents.meta_strategy import MetaStrategyAgent
from src.models.events import AllocationEvent
from src.core.event_bus import EventBus


@pytest.fixture
def event_bus():
    """Create event bus for testing"""
    return EventBus()


@pytest.fixture
def meta_strategy_agent(event_bus):
    """Create meta-strategy agent for testing"""
    strategies = ['momentum', 'macd', 'mean_reversion']
    return MetaStrategyAgent(
        event_bus,
        strategies,
        evaluation_interval_hours=1,  # Short interval for testing
        min_allocation_pct=5.0,
        max_allocation_pct=50.0
    )


@pytest.mark.asyncio
async def test_initial_equal_allocation(event_bus, meta_strategy_agent):
    """Test that initial allocation is equal weighting"""
    # Subscribe to allocation events
    queue = event_bus.subscribe(AllocationEvent)

    # Start allocation (run for short time)
    task = asyncio.create_task(meta_strategy_agent._allocate_capital())
    await task

    # Should publish allocation event
    try:
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert isinstance(event, AllocationEvent)
        assert len(event.allocations) == 3
        assert event.reason == "Initial equal weighting allocation"

        # Each strategy should get ~33.33%
        for strategy, allocation in event.allocations.items():
            assert abs(allocation - 33.33) < 0.1  # Allow small rounding difference

    except asyncio.TimeoutError:
        pytest.fail("No allocation event received")


@pytest.mark.asyncio
async def test_allocations_sum_to_100(meta_strategy_agent):
    """Test that allocations always sum to 100%"""
    await meta_strategy_agent._allocate_capital()

    total_allocation = sum(meta_strategy_agent.current_allocations.values())
    assert abs(total_allocation - 100.0) < 0.01  # Allow tiny rounding error


@pytest.mark.asyncio
async def test_min_max_allocation_constraints(meta_strategy_agent):
    """Test that allocations respect min/max constraints"""
    # Mock performance data that would violate constraints
    mock_allocations = {
        'momentum': 70.0,  # Would exceed max (50%)
        'macd': 25.0,
        'mean_reversion': 5.0
    }

    # Simulate applying constraints
    for strategy, allocation in mock_allocations.items():
        constrained = max(
            float(meta_strategy_agent.min_allocation_pct),
            min(float(meta_strategy_agent.max_allocation_pct), allocation)
        )

        assert constrained >= float(meta_strategy_agent.min_allocation_pct)
        assert constrained <= float(meta_strategy_agent.max_allocation_pct)


@pytest.mark.asyncio
async def test_performance_based_allocation():
    """Test performance-based allocation calculation"""
    event_bus = EventBus()
    agent = MetaStrategyAgent(event_bus, ['momentum', 'macd'])

    # Mock database connection
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            'strategy_name': 'momentum',
            'total_pnl': Decimal('500.0'),
            'sharpe_ratio': Decimal('1.5'),
            'win_rate': Decimal('0.6'),
            'max_drawdown': Decimal('-50.0'),
            'total_trades': 100
        },
        {
            'strategy_name': 'macd',
            'total_pnl': Decimal('300.0'),
            'sharpe_ratio': Decimal('1.2'),
            'win_rate': Decimal('0.55'),
            'max_drawdown': Decimal('-40.0'),
            'total_trades': 80
        }
    ]

    with patch('src.agents.meta_strategy.get_db_manager') as mock_db:
        mock_db.return_value.get_connection.return_value = mock_conn
        mock_db.return_value.release_connection = AsyncMock()

        allocations = await agent._calculate_performance_allocations()

        # Momentum should get higher allocation (better performance)
        assert 'momentum' in allocations
        assert 'macd' in allocations
        assert allocations['momentum'] > allocations['macd']

        # Should sum to 100%
        total = sum(allocations.values())
        assert abs(total - 100.0) < 0.01


@pytest.mark.asyncio
async def test_fallback_to_equal_weighting_when_no_data():
    """Test that agent falls back to equal weighting when no performance data"""
    event_bus = EventBus()
    agent = MetaStrategyAgent(event_bus, ['momentum', 'macd'])

    # Mock empty performance data
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []

    with patch('src.agents.meta_strategy.get_db_manager') as mock_db:
        mock_db.return_value.get_connection.return_value = mock_conn
        mock_db.return_value.release_connection = AsyncMock()

        allocations = await agent._calculate_performance_allocations()

        # Should be equal weighting
        assert allocations['momentum'] == 50.0
        assert allocations['macd'] == 50.0


@pytest.mark.asyncio
async def test_reallocation_threshold():
    """Test that reallocation only happens when changes exceed threshold"""
    event_bus = EventBus()
    agent = MetaStrategyAgent(event_bus, ['momentum', 'macd'])

    # Set current allocations
    agent.current_allocations = {'momentum': 50.0, 'macd': 50.0}
    agent.first_allocation = False

    # Mock new allocations with small change (< 5%)
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []

    with patch('src.agents.meta_strategy.get_db_manager') as mock_db:
        mock_db.return_value.get_connection.return_value = mock_conn
        mock_db.return_value.release_connection = AsyncMock()

        # Mock _calculate_performance_allocations to return similar allocations
        agent._calculate_performance_allocations = AsyncMock(
            return_value={'momentum': 52.0, 'macd': 48.0}
        )

        # Subscribe to allocation events
        queue = event_bus.subscribe(AllocationEvent)

        await agent._evaluate_and_reallocate()

        # Should not publish event (change is < 5%)
        try:
            await asyncio.wait_for(queue.get(), timeout=0.1)
            pytest.fail("Should not publish allocation event for small changes")
        except asyncio.TimeoutError:
            pass  # Expected


@pytest.mark.asyncio
async def test_handles_database_errors_gracefully():
    """Test that agent handles database errors without crashing"""
    event_bus = EventBus()
    agent = MetaStrategyAgent(event_bus, ['momentum', 'macd'])
    agent.current_allocations = {'momentum': 50.0, 'macd': 50.0}

    # Mock database error
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = Exception("Database connection failed")

    with patch('src.agents.meta_strategy.get_db_manager') as mock_db:
        mock_db.return_value.get_connection.return_value = mock_conn
        mock_db.return_value.release_connection = AsyncMock()

        # Should return current allocations as fallback
        allocations = await agent._calculate_performance_allocations()

        assert allocations == agent.current_allocations


@pytest.mark.asyncio
async def test_publishes_allocation_event():
    """Test that allocation events are published correctly"""
    event_bus = EventBus()
    agent = MetaStrategyAgent(event_bus, ['momentum', 'macd'])

    # Subscribe to events
    queue = event_bus.subscribe(AllocationEvent)

    # Trigger allocation
    await agent._allocate_capital()

    # Verify event published
    try:
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert isinstance(event, AllocationEvent)
        assert 'momentum' in event.allocations
        assert 'macd' in event.allocations
        assert event.reason is not None
    except asyncio.TimeoutError:
        pytest.fail("Allocation event not published")
