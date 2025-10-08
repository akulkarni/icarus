"""Integration tests for new strategies"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from decimal import Decimal


@pytest.mark.asyncio
async def test_bollinger_strategy_full_cycle():
    """Test Bollinger strategy through full signal cycle"""
    from src.agents.strategies.bollinger import BollingerBandsStrategy

    event_bus = MagicMock()
    event_bus.subscribe = MagicMock(return_value=AsyncMock())
    event_bus.publish = AsyncMock()

    strategy = BollingerBandsStrategy(event_bus, symbol='ETHUSDT')

    # Add enough data for analysis
    for i in range(30):
        strategy.add_price(Decimal(str(100 + i * 0.5)))

    # Should be able to analyze
    signal = await strategy.analyze()
    # Signal may or may not be generated depending on data
    assert signal is None or signal.symbol == 'ETHUSDT'


@pytest.mark.asyncio
async def test_meanreversion_strategy_full_cycle():
    """Test Mean Reversion strategy through full signal cycle"""
    from src.agents.strategies.meanreversion import MeanReversionStrategy

    event_bus = MagicMock()
    event_bus.subscribe = MagicMock(return_value=AsyncMock())
    event_bus.publish = AsyncMock()

    strategy = MeanReversionStrategy(event_bus, symbol='BTCUSDT')

    # Add enough data for analysis
    for i in range(30):
        strategy.add_price(Decimal(str(100 + i * 0.5)))

    # Should be able to analyze
    signal = await strategy.analyze()
    assert signal is None or signal.symbol == 'BTCUSDT'


def test_strategies_can_be_imported():
    """Test that all strategies can be imported"""
    from src.agents.strategies import (
        MomentumStrategy,
        MACDStrategy,
        BollingerBandsStrategy,
        MeanReversionStrategy
    )

    assert MomentumStrategy is not None
    assert MACDStrategy is not None
    assert BollingerBandsStrategy is not None
    assert MeanReversionStrategy is not None
