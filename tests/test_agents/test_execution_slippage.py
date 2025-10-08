"""Tests for slippage simulation"""
import pytest
from decimal import Decimal
from src.agents.execution import calculate_slippage_price


def test_buy_slippage():
    """Test slippage increases buy price"""
    market_price = Decimal('100.00')
    slippage_pct = Decimal('0.001')  # 0.1%

    fill_price = calculate_slippage_price(market_price, 'buy', slippage_pct)

    # Buy price should be higher
    assert fill_price > market_price
    assert fill_price == Decimal('100.10')


def test_sell_slippage():
    """Test slippage decreases sell price"""
    market_price = Decimal('100.00')
    slippage_pct = Decimal('0.001')  # 0.1%

    fill_price = calculate_slippage_price(market_price, 'sell', slippage_pct)

    # Sell price should be lower
    assert fill_price < market_price
    assert fill_price == Decimal('99.90')


def test_zero_slippage():
    """Test zero slippage returns market price"""
    market_price = Decimal('100.00')
    slippage_pct = Decimal('0.0')

    for side in ['buy', 'sell']:
        fill_price = calculate_slippage_price(market_price, side, slippage_pct)
        assert fill_price == market_price


def test_high_slippage():
    """Test with higher slippage percentage"""
    market_price = Decimal('1000.00')
    slippage_pct = Decimal('0.005')  # 0.5%

    buy_price = calculate_slippage_price(market_price, 'buy', slippage_pct)
    sell_price = calculate_slippage_price(market_price, 'sell', slippage_pct)

    assert buy_price == Decimal('1005.00')
    assert sell_price == Decimal('995.00')
