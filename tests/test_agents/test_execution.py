"""
Tests for Trade Execution Agent
"""
import pytest
import asyncio
from decimal import Decimal
from src.agents.execution import TradeExecutionAgent
from src.core.event_bus import EventBus
from src.models.events import (
    TradingSignalEvent,
    TradeExecutedEvent,
    AllocationEvent,
    MarketTickEvent
)


@pytest.fixture
def event_bus():
    """Create event bus for testing"""
    return EventBus()


@pytest.fixture
def execution_agent(event_bus):
    """Create execution agent for testing"""
    return TradeExecutionAgent(event_bus, initial_capital=Decimal('10000'))


@pytest.mark.asyncio
async def test_execution_agent_initialization(event_bus):
    """Test that execution agent initializes correctly"""
    agent = TradeExecutionAgent(event_bus, initial_capital=Decimal('50000'))
    assert agent.name == "execution"
    assert agent.initial_capital == Decimal('50000')
    assert len(agent.strategy_portfolios) == 0
    assert len(agent.current_allocations) == 0


@pytest.mark.asyncio
async def test_execution_agent_receives_allocation(event_bus, execution_agent):
    """Test that execution agent processes allocation events"""
    # Start agent in background
    agent_task = asyncio.create_task(execution_agent.start())

    try:
        # Publish allocation event
        allocation = AllocationEvent(
            allocations={'momentum': 50.0, 'macd': 50.0},
            reason="Initial allocation"
        )
        await event_bus.publish(allocation)

        # Wait for processing
        await asyncio.sleep(0.1)

        # Check allocations updated
        assert execution_agent.current_allocations == {'momentum': 50.0, 'macd': 50.0}

    finally:
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_execution_agent_tracks_prices(event_bus, execution_agent):
    """Test that execution agent tracks market prices"""
    agent_task = asyncio.create_task(execution_agent.start())

    try:
        # Publish price ticks
        tick1 = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000'),
            volume=Decimal('1000')
        )
        tick2 = MarketTickEvent(
            symbol='ETHUSDT',
            price=Decimal('3000'),
            volume=Decimal('500')
        )

        await event_bus.publish(tick1)
        await event_bus.publish(tick2)

        await asyncio.sleep(0.1)

        # Check prices tracked
        assert execution_agent.current_prices['BTCUSDT'] == Decimal('50000')
        assert execution_agent.current_prices['ETHUSDT'] == Decimal('3000')

    finally:
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_execution_agent_executes_buy_signal(event_bus, execution_agent):
    """Test that execution agent executes buy signals"""
    # Subscribe to trade events
    trade_queue = event_bus.subscribe(TradeExecutedEvent)

    agent_task = asyncio.create_task(execution_agent.start())

    try:
        # Set up allocation and price
        allocation = AllocationEvent(
            allocations={'momentum': 100.0},
            reason="Test allocation"
        )
        await event_bus.publish(allocation)

        tick = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000'),
            volume=Decimal('1000')
        )
        await event_bus.publish(tick)

        await asyncio.sleep(0.1)

        # Send buy signal
        signal = TradingSignalEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            confidence=0.8,
            reason="Test buy"
        )
        await event_bus.publish(signal)

        # Wait for trade execution
        trade = await asyncio.wait_for(trade_queue.get(), timeout=2.0)

        # Verify trade
        assert isinstance(trade, TradeExecutedEvent)
        assert trade.strategy_name == 'momentum'
        assert trade.symbol == 'BTCUSDT'
        assert trade.side == 'buy'
        assert trade.quantity > 0
        assert trade.price == Decimal('50000')

        # Check portfolio updated
        portfolio = execution_agent.strategy_portfolios['momentum']
        assert 'BTCUSDT' in portfolio['positions']
        assert portfolio['positions']['BTCUSDT'] > 0
        assert portfolio['cash'] < Decimal('10000')  # Cash decreased

    finally:
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_execution_agent_executes_sell_signal(event_bus, execution_agent):
    """Test that execution agent executes sell signals"""
    trade_queue = event_bus.subscribe(TradeExecutedEvent)
    agent_task = asyncio.create_task(execution_agent.start())

    try:
        # Set up allocation and price
        allocation = AllocationEvent(
            allocations={'momentum': 100.0},
            reason="Test allocation"
        )
        await event_bus.publish(allocation)

        tick = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000'),
            volume=Decimal('1000')
        )
        await event_bus.publish(tick)

        await asyncio.sleep(0.1)

        # Execute buy first
        buy_signal = TradingSignalEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            confidence=0.8,
            reason="Test buy"
        )
        await event_bus.publish(buy_signal)

        # Wait for buy execution
        buy_trade = await asyncio.wait_for(trade_queue.get(), timeout=2.0)
        await asyncio.sleep(0.1)

        # Update price
        tick2 = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('55000'),  # Price increased
            volume=Decimal('1000')
        )
        await event_bus.publish(tick2)
        await asyncio.sleep(0.1)

        # Execute sell
        sell_signal = TradingSignalEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='sell',
            confidence=0.8,
            reason="Test sell"
        )
        await event_bus.publish(sell_signal)

        # Wait for sell execution
        sell_trade = await asyncio.wait_for(trade_queue.get(), timeout=2.0)

        # Verify sell trade
        assert sell_trade.side == 'sell'
        assert sell_trade.quantity > 0
        assert sell_trade.price == Decimal('55000')

        # Check portfolio updated
        portfolio = execution_agent.strategy_portfolios['momentum']
        # Position should be reduced (50% sold)
        assert portfolio['positions']['BTCUSDT'] < buy_trade.quantity

    finally:
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_execution_agent_ignores_signals_without_allocation(event_bus, execution_agent):
    """Test that agent ignores signals for strategies without allocation"""
    trade_queue = event_bus.subscribe(TradeExecutedEvent)
    agent_task = asyncio.create_task(execution_agent.start())

    try:
        # Set price but no allocation
        tick = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000'),
            volume=Decimal('1000')
        )
        await event_bus.publish(tick)
        await asyncio.sleep(0.1)

        # Send signal without allocation
        signal = TradingSignalEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            confidence=0.8,
            reason="Test buy"
        )
        await event_bus.publish(signal)

        # Should not execute trade
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(trade_queue.get(), timeout=0.5)

    finally:
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_execution_agent_initializes_portfolio_on_first_signal(event_bus, execution_agent):
    """Test that agent initializes portfolio on first signal"""
    agent_task = asyncio.create_task(execution_agent.start())

    try:
        # Set allocation
        allocation = AllocationEvent(
            allocations={'momentum': 60.0, 'macd': 40.0},
            reason="Test allocation"
        )
        await event_bus.publish(allocation)
        await asyncio.sleep(0.1)

        # Initially no portfolios
        assert 'momentum' not in execution_agent.strategy_portfolios

        # Set price and send signal
        tick = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000'),
            volume=Decimal('1000')
        )
        await event_bus.publish(tick)
        await asyncio.sleep(0.1)

        signal = TradingSignalEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            confidence=0.8,
            reason="Test"
        )
        await event_bus.publish(signal)
        await asyncio.sleep(0.2)

        # Portfolio should be initialized with 60% of capital
        assert 'momentum' in execution_agent.strategy_portfolios
        portfolio = execution_agent.strategy_portfolios['momentum']
        # Initial cash should be less than 6000 (60% of 10000) after buying
        assert portfolio['cash'] < Decimal('6000')

    finally:
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_get_portfolio_summary(event_bus, execution_agent):
    """Test portfolio summary generation"""
    agent_task = asyncio.create_task(execution_agent.start())

    try:
        # Set up and execute a trade
        allocation = AllocationEvent(
            allocations={'momentum': 100.0},
            reason="Test"
        )
        await event_bus.publish(allocation)

        tick = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000'),
            volume=Decimal('1000')
        )
        await event_bus.publish(tick)
        await asyncio.sleep(0.1)

        signal = TradingSignalEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            confidence=0.8,
            reason="Test"
        )
        await event_bus.publish(signal)
        await asyncio.sleep(0.2)

        # Get summary
        summary = execution_agent.get_portfolio_summary('momentum')

        assert 'cash' in summary
        assert 'positions' in summary
        assert 'position_value' in summary
        assert 'total_value' in summary
        assert summary['total_value'] > 0

    finally:
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
