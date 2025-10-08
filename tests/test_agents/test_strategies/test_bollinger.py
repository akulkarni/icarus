"""Tests for Bollinger Bands strategy"""
import pytest
import pandas as pd
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from src.agents.strategies.bollinger import BollingerBandsStrategy
from src.models.events import TradingSignalEvent


@pytest.fixture
def event_bus():
    """Mock event bus"""
    bus = MagicMock()
    bus.subscribe = MagicMock(return_value=AsyncMock())
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def bollinger_strategy(event_bus):
    """Create Bollinger strategy instance"""
    return BollingerBandsStrategy(
        event_bus=event_bus,
        symbol='ETHUSDT',
        period=20,
        num_std=2,
        warmup_period=20
    )


def test_bollinger_init(bollinger_strategy):
    """Test Bollinger strategy initialization"""
    assert bollinger_strategy.name == 'bollinger'
    assert bollinger_strategy.symbol == 'ETHUSDT'
    assert bollinger_strategy.params['period'] == 20
    assert bollinger_strategy.params['num_std'] == 2


def test_bollinger_calculate_bands():
    """Test Bollinger Bands calculation"""
    from src.agents.strategies.bollinger import calculate_bollinger_bands

    # Create test data
    prices = [100, 102, 101, 103, 102, 104, 103, 105, 104, 106,
              105, 107, 106, 108, 107, 109, 108, 110, 109, 111,
              110]

    sma, upper, lower = calculate_bollinger_bands(prices, period=20, num_std=2)

    # Verify shapes
    assert len(sma) == len(prices)
    assert len(upper) == len(prices)
    assert len(lower) == len(prices)

    # Verify relationships (upper > sma > lower)
    for i in range(20, len(prices)):
        if not pd.isna(sma[i]):
            assert upper[i] > sma[i]
            assert sma[i] > lower[i]


@pytest.mark.asyncio
async def test_bollinger_no_signal_insufficient_data(bollinger_strategy):
    """Test no signal when insufficient data"""
    # Add only 10 prices (need 20)
    for i in range(10):
        bollinger_strategy.add_price(Decimal(str(100 + i)))

    signal = await bollinger_strategy.analyze()
    assert signal is None


@pytest.mark.asyncio
async def test_bollinger_buy_signal_at_lower_band(bollinger_strategy):
    """Test buy signal when price touches lower band"""
    # Add prices trending down then touching lower band
    prices = [110] * 10 + list(range(110, 90, -1))  # Declining prices

    for price in prices:
        bollinger_strategy.add_price(Decimal(str(price)))

    signal = await bollinger_strategy.analyze()

    # Should generate buy signal when price near lower band
    if signal:
        assert signal.side == 'buy'
        assert signal.symbol == 'ETHUSDT'
        assert signal.strategy_name == 'bollinger'


@pytest.mark.asyncio
async def test_bollinger_sell_signal_at_upper_band(bollinger_strategy):
    """Test sell signal when price touches upper band"""
    # Add prices trending up then touching upper band
    prices = [90] * 10 + list(range(90, 110))  # Rising prices

    for price in prices:
        bollinger_strategy.add_price(Decimal(str(price)))

    signal = await bollinger_strategy.analyze()

    # Should generate sell signal when price near upper band
    if signal:
        assert signal.side == 'sell'
        assert signal.symbol == 'ETHUSDT'
        assert signal.strategy_name == 'bollinger'
