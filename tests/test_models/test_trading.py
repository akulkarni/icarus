"""
Tests for trading models
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4

from src.models.trading import (
    Position,
    ClosedPosition,
    Trade,
    Portfolio,
    Order,
    StrategyMetrics
)


class TestPosition:
    """Test Position model"""

    def test_position_creation(self):
        """Test creating a position"""
        pos_id = uuid4()
        pos = Position(
            position_id=pos_id,
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.5'),
            entry_price=Decimal('50000.00')
        )

        assert pos.position_id == pos_id
        assert pos.strategy_name == 'momentum'
        assert pos.symbol == 'BTCUSDT'
        assert pos.quantity == Decimal('0.5')
        assert pos.entry_price == Decimal('50000.00')

    def test_position_entry_value(self):
        """Test position entry value calculation"""
        pos = Position(
            position_id=uuid4(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.5'),
            entry_price=Decimal('50000.00')
        )

        assert pos.entry_value == Decimal('25000.00')

    def test_position_current_value(self):
        """Test position current value calculation"""
        pos = Position(
            position_id=uuid4(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.5'),
            entry_price=Decimal('50000.00'),
            current_price=Decimal('55000.00')
        )

        assert pos.current_value == Decimal('27500.00')

    def test_position_update_price(self):
        """Test updating position price"""
        pos = Position(
            position_id=uuid4(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.5'),
            entry_price=Decimal('50000.00')
        )

        pos.update_price(Decimal('55000.00'))

        assert pos.current_price == Decimal('55000.00')
        assert pos.unrealized_pnl == Decimal('2500.00')  # (55000 - 50000) * 0.5

    def test_position_calculate_return_pct(self):
        """Test return percentage calculation"""
        pos = Position(
            position_id=uuid4(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.5'),
            entry_price=Decimal('50000.00'),
            current_price=Decimal('55000.00')
        )

        assert pos.calculate_return_pct() == Decimal('10.00')

    def test_position_to_dict(self):
        """Test position serialization"""
        pos = Position(
            position_id=uuid4(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.5'),
            entry_price=Decimal('50000.00')
        )

        data = pos.to_dict()
        assert data['strategy_name'] == 'momentum'
        assert data['symbol'] == 'BTCUSDT'
        assert data['quantity'] == 0.5


class TestClosedPosition:
    """Test ClosedPosition model"""

    def test_closed_position_from_position(self):
        """Test creating ClosedPosition from Position"""
        opened_at = datetime.now() - timedelta(hours=2)
        closed_at = datetime.now()

        pos = Position(
            position_id=uuid4(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.5'),
            entry_price=Decimal('50000.00'),
            opened_at=opened_at
        )

        closed_pos = ClosedPosition.from_position(pos, Decimal('55000.00'), closed_at)

        assert closed_pos.position_id == pos.position_id
        assert closed_pos.exit_price == Decimal('55000.00')
        assert closed_pos.pnl == Decimal('2500.00')
        assert closed_pos.return_pct == Decimal('10.00')
        assert closed_pos.hold_duration is not None


class TestTrade:
    """Test Trade model"""

    def test_trade_creation(self):
        """Test creating a trade"""
        trade = Trade(
            id=uuid4(),
            time=datetime.now(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            quantity=Decimal('0.5'),
            price=Decimal('50000.00'),
            fee=Decimal('25.00')
        )

        assert trade.strategy_name == 'momentum'
        assert trade.symbol == 'BTCUSDT'
        assert trade.side == 'buy'

    def test_trade_value(self):
        """Test trade value calculation"""
        trade = Trade(
            id=uuid4(),
            time=datetime.now(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            quantity=Decimal('0.5'),
            price=Decimal('50000.00'),
            fee=Decimal('25.00')
        )

        assert trade.value == Decimal('25000.00')
        assert trade.total_cost == Decimal('25025.00')


class TestPortfolio:
    """Test Portfolio model"""

    def test_portfolio_creation(self):
        """Test creating a portfolio"""
        portfolio = Portfolio(
            strategy_name='momentum',
            initial_capital=Decimal('10000.00'),
            cash=Decimal('10000.00')
        )

        assert portfolio.strategy_name == 'momentum'
        assert portfolio.initial_capital == Decimal('10000.00')
        assert portfolio.cash == Decimal('10000.00')
        assert portfolio.num_positions == 0

    def test_portfolio_add_position(self):
        """Test adding position to portfolio"""
        portfolio = Portfolio(
            strategy_name='momentum',
            initial_capital=Decimal('10000.00'),
            cash=Decimal('5000.00')
        )

        pos = Position(
            position_id=uuid4(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.1'),
            entry_price=Decimal('50000.00'),
            current_price=Decimal('50000.00')
        )

        portfolio.add_position(pos)

        assert portfolio.num_positions == 1
        assert portfolio.get_position('BTCUSDT') == pos

    def test_portfolio_total_value(self):
        """Test portfolio total value calculation"""
        portfolio = Portfolio(
            strategy_name='momentum',
            initial_capital=Decimal('10000.00'),
            cash=Decimal('5000.00')
        )

        pos = Position(
            position_id=uuid4(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.1'),
            entry_price=Decimal('50000.00'),
            current_price=Decimal('50000.00')
        )
        pos.update_price(Decimal('50000.00'))

        portfolio.add_position(pos)

        assert portfolio.positions_value == Decimal('5000.00')
        assert portfolio.total_value == Decimal('10000.00')

    def test_portfolio_unrealized_pnl(self):
        """Test portfolio unrealized PnL calculation"""
        portfolio = Portfolio(
            strategy_name='momentum',
            initial_capital=Decimal('10000.00'),
            cash=Decimal('5000.00')
        )

        pos = Position(
            position_id=uuid4(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.1'),
            entry_price=Decimal('50000.00')
        )
        pos.update_price(Decimal('55000.00'))  # Price increased 10%

        portfolio.add_position(pos)

        assert portfolio.unrealized_pnl == Decimal('500.00')

    def test_portfolio_total_return_pct(self):
        """Test portfolio total return percentage"""
        portfolio = Portfolio(
            strategy_name='momentum',
            initial_capital=Decimal('10000.00'),
            cash=Decimal('5000.00')
        )

        pos = Position(
            position_id=uuid4(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.1'),
            entry_price=Decimal('50000.00')
        )
        pos.update_price(Decimal('55000.00'))

        portfolio.add_position(pos)

        # Total value = 5000 (cash) + 5500 (position) = 10500
        # Return = (10500 - 10000) / 10000 = 5%
        assert portfolio.total_return_pct == Decimal('5.00')

    def test_portfolio_close_position(self):
        """Test closing a position"""
        portfolio = Portfolio(
            strategy_name='momentum',
            initial_capital=Decimal('10000.00'),
            cash=Decimal('5000.00')
        )

        pos = Position(
            position_id=uuid4(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.1'),
            entry_price=Decimal('50000.00'),
            opened_at=datetime.now() - timedelta(hours=2)
        )

        portfolio.add_position(pos)
        assert portfolio.num_positions == 1

        closed_pos = portfolio.close_position('BTCUSDT', Decimal('55000.00'), datetime.now())

        assert portfolio.num_positions == 0
        assert closed_pos is not None
        assert closed_pos.pnl == Decimal('500.00')
        assert len(portfolio.closed_positions) == 1

    def test_portfolio_update_prices(self):
        """Test updating all position prices"""
        portfolio = Portfolio(
            strategy_name='momentum',
            initial_capital=Decimal('10000.00'),
            cash=Decimal('3000.00')
        )

        # Add multiple positions
        btc_pos = Position(
            position_id=uuid4(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.1'),
            entry_price=Decimal('50000.00')
        )

        eth_pos = Position(
            position_id=uuid4(),
            strategy_name='momentum',
            symbol='ETHUSDT',
            quantity=Decimal('2.0'),
            entry_price=Decimal('2000.00')
        )

        portfolio.add_position(btc_pos)
        portfolio.add_position(eth_pos)

        # Update prices
        prices = {
            'BTCUSDT': Decimal('55000.00'),
            'ETHUSDT': Decimal('2200.00')
        }
        portfolio.update_prices(prices)

        assert portfolio.get_position('BTCUSDT').current_price == Decimal('55000.00')
        assert portfolio.get_position('ETHUSDT').current_price == Decimal('2200.00')

    def test_portfolio_exposure_pct(self):
        """Test portfolio exposure percentage"""
        portfolio = Portfolio(
            strategy_name='momentum',
            initial_capital=Decimal('10000.00'),
            cash=Decimal('2000.00')
        )

        pos = Position(
            position_id=uuid4(),
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.16'),
            entry_price=Decimal('50000.00'),
            current_price=Decimal('50000.00')
        )

        portfolio.add_position(pos)

        # Exposure = 8000 / 10000 = 80%
        assert portfolio.exposure_pct == Decimal('80.00')


class TestOrder:
    """Test Order model"""

    def test_order_creation(self):
        """Test creating an order"""
        order = Order(
            order_id='order123',
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            order_type='market',
            quantity=Decimal('0.5')
        )

        assert order.order_id == 'order123'
        assert order.status == 'pending'
        assert not order.is_filled

    def test_order_is_filled(self):
        """Test order filled status"""
        order = Order(
            order_id='order123',
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            order_type='market',
            quantity=Decimal('0.5'),
            filled_quantity=Decimal('0.5')
        )

        assert order.is_filled

    def test_order_partial_fill(self):
        """Test order partial fill detection"""
        order = Order(
            order_id='order123',
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            order_type='market',
            quantity=Decimal('0.5'),
            filled_quantity=Decimal('0.3')
        )

        assert order.is_partial_fill
        assert not order.is_filled


class TestStrategyMetrics:
    """Test StrategyMetrics model"""

    def test_metrics_creation(self):
        """Test creating strategy metrics"""
        metrics = StrategyMetrics(
            strategy_name='momentum',
            time_period='7d',
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=Decimal('0.60'),
            total_pnl=Decimal('5000.00')
        )

        assert metrics.strategy_name == 'momentum'
        assert metrics.total_trades == 100
        assert metrics.win_rate == Decimal('0.60')

    def test_metrics_to_dict(self):
        """Test metrics serialization"""
        metrics = StrategyMetrics(
            strategy_name='momentum',
            time_period='7d',
            total_trades=100
        )

        data = metrics.to_dict()
        assert data['strategy_name'] == 'momentum'
        assert data['total_trades'] == 100
