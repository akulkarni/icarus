"""Tests for Stochastic Oscillator strategy"""
import pytest
import numpy as np
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock
from src.agents.strategies.stochastic import StochasticStrategy

@pytest.fixture
def event_bus():
    bus = MagicMock()
    bus.subscribe = MagicMock(return_value=AsyncMock())
    bus.publish = AsyncMock()
    return bus

@pytest.fixture
def stochastic_strategy(event_bus):
    return StochasticStrategy(event_bus=event_bus, symbol='ETHUSDT')

def test_stochastic_init(stochastic_strategy):
    assert stochastic_strategy.name == 'stochastic'
    assert stochastic_strategy.params['k_period'] == 14
    assert stochastic_strategy.params['d_period'] == 3

def test_calculate_stochastic():
    from src.agents.strategies.stochastic import calculate_stochastic

    high = np.array([102, 103, 104, 103, 102] * 5)
    low = np.array([98, 99, 100, 99, 98] * 5)
    close = np.array([100, 101, 102, 101, 100] * 5)

    k, d = calculate_stochastic(high, low, close, k_period=14, d_period=3)

    assert len(k) == len(close)
    assert len(d) == len(close)
    # Values should be 0-100
    assert all(0 <= v <= 100 for v in k[14:] if not np.isnan(v))

@pytest.mark.asyncio
async def test_stochastic_insufficient_data(stochastic_strategy):
    from datetime import datetime

    for i in range(10):
        stochastic_strategy.price_history.append({
            'time': datetime.now(),
            'price': 100.0,
            'volume': 1000.0
        })
    signal = await stochastic_strategy.analyze()
    assert signal is None
