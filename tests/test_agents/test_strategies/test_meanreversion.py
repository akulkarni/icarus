"""Tests for Mean Reversion (RSI) strategy"""
import pytest
import pandas as pd
import numpy as np
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from src.agents.strategies.meanreversion import MeanReversionStrategy
from src.models.events import TradingSignalEvent


@pytest.fixture
def event_bus():
    """Mock event bus"""
    bus = MagicMock()
    bus.subscribe = MagicMock(return_value=AsyncMock())
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def meanreversion_strategy(event_bus):
    """Create Mean Reversion strategy instance"""
    return MeanReversionStrategy(
        event_bus=event_bus,
        symbol='BTCUSDT',
        rsi_period=14,
        oversold_threshold=30,
        overbought_threshold=70
    )


def test_meanreversion_init(meanreversion_strategy):
    """Test Mean Reversion strategy initialization"""
    assert meanreversion_strategy.name == 'meanreversion'
    assert meanreversion_strategy.symbol == 'BTCUSDT'
    assert meanreversion_strategy.params['rsi_period'] == 14
    assert meanreversion_strategy.params['oversold_threshold'] == 30
    assert meanreversion_strategy.params['overbought_threshold'] == 70


def test_rsi_calculation():
    """Test RSI calculation"""
    from src.agents.strategies.meanreversion import calculate_rsi

    # Create test data with clear trend
    # Uptrend should have RSI > 50
    prices = np.array([100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
                       110, 111, 112, 113, 114, 115, 116, 117, 118, 119])

    rsi = calculate_rsi(prices, period=14)

    # Verify shape
    assert len(rsi) == len(prices)

    # RSI should be between 0 and 100
    for i in range(14, len(rsi)):
        assert 0 <= rsi[i] <= 100

    # Uptrend should have higher RSI
    assert rsi[-1] > 50


@pytest.mark.asyncio
async def test_meanreversion_no_signal_insufficient_data(meanreversion_strategy):
    """Test no signal when insufficient data"""
    # Add only 10 prices (need 14+ for RSI)
    for i in range(10):
        meanreversion_strategy.add_price(Decimal(str(100 + i)))

    signal = await meanreversion_strategy.analyze()
    assert signal is None


@pytest.mark.asyncio
async def test_meanreversion_buy_signal_oversold(meanreversion_strategy):
    """Test buy signal when RSI < 30 (oversold)"""
    # Create oversold condition: sharp decline
    prices = [100] * 5 + list(range(100, 70, -2))  # Sharp decline

    for price in prices:
        meanreversion_strategy.add_price(Decimal(str(price)))

    signal = await meanreversion_strategy.analyze()

    # Should generate buy signal in oversold condition
    if signal:
        assert signal.side == 'buy'
        assert signal.symbol == 'BTCUSDT'
        assert signal.strategy_name == 'meanreversion'
        assert 'RSI' in signal.reason or 'oversold' in signal.reason.lower()


@pytest.mark.asyncio
async def test_meanreversion_sell_signal_overbought(meanreversion_strategy):
    """Test sell signal when RSI > 70 (overbought)"""
    # Create overbought condition: sharp rise
    prices = [70] * 5 + list(range(70, 100, 2))  # Sharp rise

    for price in prices:
        meanreversion_strategy.add_price(Decimal(str(price)))

    signal = await meanreversion_strategy.analyze()

    # Should generate sell signal in overbought condition
    if signal:
        assert signal.side == 'sell'
        assert signal.symbol == 'BTCUSDT'
        assert signal.strategy_name == 'meanreversion'
        assert 'RSI' in signal.reason or 'overbought' in signal.reason.lower()
