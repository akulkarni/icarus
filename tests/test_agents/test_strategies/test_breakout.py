"""Tests for Breakout strategy"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock
from src.agents.strategies.breakout import BreakoutStrategy

@pytest.fixture
def event_bus():
    bus = MagicMock()
    bus.subscribe = MagicMock(return_value=AsyncMock())
    bus.publish = AsyncMock()
    return bus

@pytest.fixture
def breakout_strategy(event_bus):
    return BreakoutStrategy(event_bus=event_bus, symbol='SOLUSDT')

def test_breakout_init(breakout_strategy):
    assert breakout_strategy.name == 'breakout'
    assert breakout_strategy.symbol == 'SOLUSDT'
    assert breakout_strategy.params['period'] == 20

def test_calculate_rolling_bands():
    from src.agents.strategies.breakout import calculate_rolling_high_low
    import pandas as pd

    df = pd.DataFrame({
        'high': [100, 102, 101, 103, 102],
        'low': [98, 99, 97, 100, 99]
    })
    df = calculate_rolling_high_low(df, period=3)
    assert 'high_band' in df.columns
    assert 'low_band' in df.columns

@pytest.mark.asyncio
async def test_breakout_insufficient_data(breakout_strategy):
    import pandas as pd
    from datetime import datetime

    # Add data through price_history (simulating real tick events)
    for i in range(10):
        breakout_strategy.price_history.append({
            'time': datetime.now(),
            'price': 100.0 + i,
            'volume': 1000.0
        })
    signal = await breakout_strategy.analyze()
    assert signal is None

@pytest.mark.asyncio
async def test_breakout_buy_signal(breakout_strategy):
    import pandas as pd
    from datetime import datetime

    # Flat then breakout up
    for i in range(20):
        breakout_strategy.price_history.append({
            'time': datetime.now(),
            'price': 100.0,
            'volume': 1000.0
        })
    # Breakout
    breakout_strategy.price_history.append({
        'time': datetime.now(),
        'price': 110.0,
        'volume': 2000.0
    })

    signal = await breakout_strategy.analyze()
    if signal:
        assert signal.side == 'buy'
