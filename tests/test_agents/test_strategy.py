"""
Tests for Strategy Agents
"""
import pytest
import asyncio
from datetime import datetime
from decimal import Decimal
from src.agents.strategies.momentum import MomentumStrategy
from src.agents.strategies.macd import MACDStrategy
from src.core.event_bus import EventBus
from src.models.events import MarketTickEvent, TradingSignalEvent


@pytest.fixture
def event_bus():
    """Create event bus for testing"""
    return EventBus()


@pytest.fixture
def momentum_strategy(event_bus):
    """Create momentum strategy for testing"""
    return MomentumStrategy(event_bus, 'BTCUSDT')


@pytest.fixture
def macd_strategy(event_bus):
    """Create MACD strategy for testing"""
    return MACDStrategy(event_bus, 'BTCUSDT')


@pytest.mark.asyncio
async def test_momentum_strategy_initialization(event_bus):
    """Test momentum strategy initializes correctly"""
    strategy = MomentumStrategy(event_bus, 'ETHUSDT')
    assert strategy.name == 'momentum'
    assert strategy.symbol == 'ETHUSDT'
    assert strategy.params['ma_short'] == 20
    assert strategy.params['ma_long'] == 50
    assert len(strategy.price_history) == 0


@pytest.mark.asyncio
async def test_macd_strategy_initialization(event_bus):
    """Test MACD strategy initializes correctly"""
    strategy = MACDStrategy(event_bus, 'ETHUSDT')
    assert strategy.name == 'macd'
    assert strategy.symbol == 'ETHUSDT'
    assert strategy.params['fast_period'] == 12
    assert strategy.params['slow_period'] == 26
    assert strategy.params['signal_period'] == 9


@pytest.mark.asyncio
async def test_strategy_accumulates_price_history(event_bus, momentum_strategy):
    """Test that strategy accumulates price history"""
    # Subscribe to signals
    signal_queue = event_bus.subscribe(TradingSignalEvent)

    # Start strategy in background
    strategy_task = asyncio.create_task(momentum_strategy.start())

    # Publish some price ticks
    for i in range(10):
        tick = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal(f'{50000 + i * 100}'),
            volume=Decimal('1000')
        )
        await event_bus.publish(tick)
        await asyncio.sleep(0.01)

    # Give strategy time to process
    await asyncio.sleep(0.1)

    # Check price history accumulated
    assert len(momentum_strategy.price_history) == 10

    # Cleanup
    strategy_task.cancel()
    try:
        await strategy_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_momentum_strategy_generates_buy_signal(event_bus, momentum_strategy):
    """Test that momentum strategy generates buy signal on bullish crossover"""
    signal_queue = event_bus.subscribe(TradingSignalEvent)
    strategy_task = asyncio.create_task(momentum_strategy.start())

    try:
        # Simulate downtrend then uptrend (should trigger buy signal)
        # Start with prices where 20MA < 50MA
        base_price = 50000
        for i in range(60):
            if i < 30:
                # Downtrend: prices declining
                price = base_price - (i * 100)
            else:
                # Strong uptrend: prices rising sharply
                price = base_price - (30 * 100) + ((i - 30) * 300)

            tick = MarketTickEvent(
                symbol='BTCUSDT',
                price=Decimal(str(price)),
                volume=Decimal('1000')
            )
            await event_bus.publish(tick)
            await asyncio.sleep(0.01)

        # Wait for signal
        signal = await asyncio.wait_for(signal_queue.get(), timeout=2.0)

        assert isinstance(signal, TradingSignalEvent)
        assert signal.strategy_name == 'momentum'
        assert signal.symbol == 'BTCUSDT'
        assert signal.side == 'buy'
        assert 0 < signal.confidence <= 1.0

    finally:
        strategy_task.cancel()
        try:
            await strategy_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_momentum_strategy_generates_sell_signal(event_bus, momentum_strategy):
    """Test that momentum strategy generates sell signal on bearish crossover"""
    signal_queue = event_bus.subscribe(TradingSignalEvent)
    strategy_task = asyncio.create_task(momentum_strategy.start())

    try:
        # Simulate uptrend then downtrend (should trigger sell signal)
        base_price = 40000
        for i in range(60):
            if i < 30:
                # Uptrend: prices rising
                price = base_price + (i * 100)
            else:
                # Strong downtrend: prices falling sharply
                price = base_price + (30 * 100) - ((i - 30) * 300)

            tick = MarketTickEvent(
                symbol='BTCUSDT',
                price=Decimal(str(price)),
                volume=Decimal('1000')
            )
            await event_bus.publish(tick)
            await asyncio.sleep(0.01)

        # Wait for signal
        signal = await asyncio.wait_for(signal_queue.get(), timeout=2.0)

        assert isinstance(signal, TradingSignalEvent)
        assert signal.side == 'sell'

    finally:
        strategy_task.cancel()
        try:
            await strategy_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_strategy_ignores_other_symbols(event_bus, momentum_strategy):
    """Test that strategy ignores ticks for other symbols"""
    signal_queue = event_bus.subscribe(TradingSignalEvent)
    strategy_task = asyncio.create_task(momentum_strategy.start())

    try:
        # Send ticks for different symbol
        for i in range(60):
            tick = MarketTickEvent(
                symbol='ETHUSDT',  # Different symbol
                price=Decimal(f'{3000 + i * 10}'),
                volume=Decimal('1000')
            )
            await event_bus.publish(tick)
            await asyncio.sleep(0.01)

        await asyncio.sleep(0.1)

        # Should not accumulate history
        assert len(momentum_strategy.price_history) == 0

    finally:
        strategy_task.cancel()
        try:
            await strategy_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_strategy_limits_history_size(event_bus, momentum_strategy):
    """Test that strategy limits price history size"""
    strategy_task = asyncio.create_task(momentum_strategy.start())

    try:
        # Send more ticks than max_history
        max_history = momentum_strategy.max_history
        for i in range(max_history + 50):
            tick = MarketTickEvent(
                symbol='BTCUSDT',
                price=Decimal(f'{50000 + i}'),
                volume=Decimal('1000')
            )
            await event_bus.publish(tick)
            await asyncio.sleep(0.001)

        await asyncio.sleep(0.2)

        # History should be limited to max_history
        assert len(momentum_strategy.price_history) <= max_history

    finally:
        strategy_task.cancel()
        try:
            await strategy_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_macd_strategy_generates_signal(event_bus, macd_strategy):
    """Test that MACD strategy can generate signals"""
    signal_queue = event_bus.subscribe(TradingSignalEvent)
    strategy_task = asyncio.create_task(macd_strategy.start())

    try:
        # Simulate price movement that should trigger MACD signal
        base_price = 50000
        for i in range(80):
            if i < 40:
                price = base_price + (i * 50)  # Uptrend
            else:
                price = base_price + (40 * 50) - ((i - 40) * 150)  # Strong downtrend

            tick = MarketTickEvent(
                symbol='BTCUSDT',
                price=Decimal(str(price)),
                volume=Decimal('1000')
            )
            await event_bus.publish(tick)
            await asyncio.sleep(0.01)

        # Should eventually get a signal
        signal = await asyncio.wait_for(signal_queue.get(), timeout=3.0)

        assert isinstance(signal, TradingSignalEvent)
        assert signal.strategy_name == 'macd'
        assert signal.side in ['buy', 'sell']

    finally:
        strategy_task.cancel()
        try:
            await strategy_task
        except asyncio.CancelledError:
            pass
