"""
Tests for Risk Monitor Agent
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timedelta

from src.agents.risk_monitor import RiskMonitorAgent
from src.models.events import (
    TradeExecutedEvent,
    RiskAlertEvent,
    EmergencyHaltEvent,
    MarketTickEvent
)
from src.core.event_bus import EventBus


@pytest.fixture
def event_bus():
    """Create event bus for testing"""
    return EventBus()


@pytest.fixture
def risk_config():
    """Create risk configuration for testing"""
    return {
        'max_position_size_pct': 20.0,
        'max_daily_loss_pct': 5.0,
        'max_exposure_pct': 80.0,
        'max_strategy_drawdown_pct': 10.0,
        'max_leverage': 1.0
    }


@pytest.fixture
def risk_monitor(event_bus, risk_config):
    """Create risk monitor for testing"""
    return RiskMonitorAgent(
        event_bus,
        risk_config,
        initial_portfolio_value=Decimal('10000')
    )


@pytest.mark.asyncio
async def test_initialization(risk_monitor):
    """Test risk monitor initialization"""
    assert risk_monitor.max_position_size_pct == Decimal('20.0')
    assert risk_monitor.max_daily_loss_pct == Decimal('5.0')
    assert risk_monitor.max_exposure_pct == Decimal('80.0')
    assert risk_monitor.max_strategy_drawdown_pct == Decimal('10.0')
    assert risk_monitor.initial_portfolio_value == Decimal('10000')
    assert not risk_monitor.halt_active


@pytest.mark.asyncio
async def test_position_size_violation(event_bus, risk_monitor):
    """Test position size limit violation"""
    # Subscribe to risk alerts
    queue = event_bus.subscribe(RiskAlertEvent)

    # Mock portfolio value
    with patch.object(risk_monitor, '_get_current_portfolio_value',
                     return_value=Decimal('10000')):
        # Create trade that violates position size (25% > 20% limit)
        trade = TradeExecutedEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            quantity=Decimal('0.05'),
            price=Decimal('50000'),  # 0.05 * 50000 = 2500 = 25% of 10000
            fee=Decimal('2.5'),
            order_id='test-order-1'
        )

        await risk_monitor._check_trade_risk(trade)

        # Should publish critical alert
        try:
            alert = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert isinstance(alert, RiskAlertEvent)
            assert alert.severity == 'critical'
            assert alert.risk_type == 'position_size'
            assert 'exceeds limit' in alert.message.lower()
        except asyncio.TimeoutError:
            pytest.fail("Risk alert not published")


@pytest.mark.asyncio
async def test_position_size_warning(event_bus, risk_monitor):
    """Test position size warning threshold (80% of limit)"""
    queue = event_bus.subscribe(RiskAlertEvent)

    with patch.object(risk_monitor, '_get_current_portfolio_value',
                     return_value=Decimal('10000')):
        # Create trade at 17% (between 80% warning and 100% limit)
        # 80% of 20% limit = 16%
        trade = TradeExecutedEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            quantity=Decimal('0.034'),
            price=Decimal('50000'),  # 0.034 * 50000 = 1700 = 17% of 10000
            fee=Decimal('1.7'),
            order_id='test-order-2'
        )

        await risk_monitor._check_trade_risk(trade)

        # Should publish warning alert
        try:
            alert = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert isinstance(alert, RiskAlertEvent)
            assert alert.severity == 'warning'
            assert alert.risk_type == 'position_size'
            assert 'approaching limit' in alert.message.lower()
        except asyncio.TimeoutError:
            pytest.fail("Risk warning not published")


@pytest.mark.asyncio
async def test_daily_loss_limit_breach(event_bus, risk_monitor):
    """Test daily loss limit breach triggers emergency halt"""
    queue = event_bus.subscribe(EmergencyHaltEvent)

    # Set daily start value
    risk_monitor.daily_start_value = Decimal('10000')
    risk_monitor.daily_start_time = datetime.now()

    # Mock current value at 6% loss (exceeds 5% limit)
    with patch.object(risk_monitor, '_get_current_portfolio_value',
                     return_value=Decimal('9400')):
        await risk_monitor._check_daily_loss()

        # Should trigger emergency halt
        assert risk_monitor.halt_active

        # Should publish halt event
        try:
            halt = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert isinstance(halt, EmergencyHaltEvent)
            assert halt.severity == 'critical'
            assert 'daily loss' in halt.reason.lower()
        except asyncio.TimeoutError:
            pytest.fail("Emergency halt event not published")


@pytest.mark.asyncio
async def test_daily_loss_warning(event_bus, risk_monitor):
    """Test daily loss warning threshold"""
    queue = event_bus.subscribe(RiskAlertEvent)

    risk_monitor.daily_start_value = Decimal('10000')
    risk_monitor.daily_start_time = datetime.now()

    # Mock current value at 4.5% loss (between 80% warning and 100% limit)
    # 80% of 5% = 4%
    with patch.object(risk_monitor, '_get_current_portfolio_value',
                     return_value=Decimal('9550')):
        await risk_monitor._check_daily_loss()

        # Should not halt
        assert not risk_monitor.halt_active

        # Should publish warning
        try:
            alert = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert isinstance(alert, RiskAlertEvent)
            assert alert.severity == 'warning'
            assert alert.risk_type == 'daily_loss'
        except asyncio.TimeoutError:
            pytest.fail("Daily loss warning not published")


@pytest.mark.asyncio
async def test_exposure_limit_check(event_bus, risk_monitor):
    """Test exposure limit checking"""
    queue = event_bus.subscribe(RiskAlertEvent)

    # Set current prices
    risk_monitor.current_prices['BTCUSDT'] = Decimal('50000')
    risk_monitor.current_prices['ETHUSDT'] = Decimal('3000')

    # Mock database positions
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {'symbol': 'BTCUSDT', 'total_quantity': Decimal('0.15')},  # 7500
        {'symbol': 'ETHUSDT', 'total_quantity': Decimal('1.0')}    # 3000
    ]
    # Total exposure: 10500 = 105% of 10000 portfolio (exceeds 80% limit)

    with patch('src.agents.risk_monitor.get_db_manager') as mock_db:
        mock_db.return_value.get_connection.return_value = mock_conn
        mock_db.return_value.release_connection = AsyncMock()

        with patch.object(risk_monitor, '_get_current_portfolio_value',
                         return_value=Decimal('10000')):
            await risk_monitor._check_exposure()

            # Should publish critical alert
            try:
                alert = await asyncio.wait_for(queue.get(), timeout=1.0)
                assert isinstance(alert, RiskAlertEvent)
                assert alert.severity == 'critical'
                assert alert.risk_type == 'exposure'
            except asyncio.TimeoutError:
                pytest.fail("Exposure alert not published")


@pytest.mark.asyncio
async def test_strategy_drawdown_limit(event_bus, risk_monitor):
    """Test per-strategy drawdown limit"""
    queue = event_bus.subscribe(RiskAlertEvent)

    # Mock database with strategy performance
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            'strategy_name': 'momentum',
            'total_pnl': Decimal('-600'),
            'max_drawdown': Decimal('-12.0')  # Exceeds 10% limit
        }
    ]

    with patch('src.agents.risk_monitor.get_db_manager') as mock_db:
        mock_db.return_value.get_connection.return_value = mock_conn
        mock_db.return_value.release_connection = AsyncMock()

        await risk_monitor._check_strategy_drawdowns()

        # Should publish critical alert
        try:
            alert = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert isinstance(alert, RiskAlertEvent)
            assert alert.severity == 'critical'
            assert alert.risk_type == 'strategy_drawdown'
            assert 'momentum' in alert.message
        except asyncio.TimeoutError:
            pytest.fail("Strategy drawdown alert not published")


@pytest.mark.asyncio
async def test_price_tracking(risk_monitor):
    """Test market price tracking"""
    tick = MarketTickEvent(
        symbol='BTCUSDT',
        price=Decimal('50000'),
        volume=Decimal('100')
    )

    # Simulate price tracking
    risk_monitor.current_prices[tick.symbol] = tick.price

    assert risk_monitor.current_prices['BTCUSDT'] == Decimal('50000')


@pytest.mark.asyncio
async def test_daily_reset():
    """Test daily tracking reset at new day"""
    event_bus = EventBus()
    config = {
        'max_position_size_pct': 20.0,
        'max_daily_loss_pct': 5.0,
        'max_exposure_pct': 80.0,
        'max_strategy_drawdown_pct': 10.0
    }
    monitor = RiskMonitorAgent(event_bus, config, Decimal('10000'))

    # Set tracking to yesterday
    monitor.daily_start_time = datetime.now() - timedelta(days=1)
    monitor.daily_start_value = Decimal('9000')
    monitor.halt_active = True

    with patch.object(monitor, '_get_current_portfolio_value',
                     return_value=Decimal('10000')):
        await monitor._check_daily_reset()

        # Should reset to today
        assert monitor.daily_start_time.date() == datetime.now().date()
        assert monitor.daily_start_value == Decimal('10000')
        assert not monitor.halt_active  # Halt should be reset


@pytest.mark.asyncio
async def test_halt_prevents_trade_checking(risk_monitor):
    """Test that halt prevents further trade risk checking"""
    risk_monitor.halt_active = True

    trade = TradeExecutedEvent(
        strategy_name='momentum',
        symbol='BTCUSDT',
        side='buy',
        quantity=Decimal('1.0'),
        price=Decimal('50000'),
        fee=Decimal('50'),
        order_id='test-order'
    )

    # Mock to track if methods called
    with patch.object(risk_monitor, '_check_position_size') as mock_check:
        await risk_monitor._check_trade_risk(trade)

        # Should not check position size when halted
        mock_check.assert_not_called()


@pytest.mark.asyncio
async def test_get_portfolio_value(risk_monitor):
    """Test portfolio value calculation"""
    # Set prices
    risk_monitor.current_prices['BTCUSDT'] = Decimal('50000')

    # Mock database
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {'net_cash': Decimal('-5000')}  # Spent 5000
    mock_conn.fetch.return_value = [
        {'symbol': 'BTCUSDT', 'total_quantity': Decimal('0.12')}  # 0.12 * 50000 = 6000
    ]

    with patch('src.agents.risk_monitor.get_db_manager') as mock_db:
        mock_db.return_value.get_connection.return_value = mock_conn
        mock_db.return_value.release_connection = AsyncMock()

        value = await risk_monitor._get_current_portfolio_value()

        # Cash: 10000 - 5000 = 5000
        # Positions: 6000
        # Total: 11000
        assert value == Decimal('11000')


@pytest.mark.asyncio
async def test_is_halt_active(risk_monitor):
    """Test halt status check"""
    assert not risk_monitor.is_halt_active()

    risk_monitor.halt_active = True
    assert risk_monitor.is_halt_active()


@pytest.mark.asyncio
async def test_handles_missing_price_data(risk_monitor):
    """Test graceful handling of missing price data"""
    # No prices set
    risk_monitor.current_prices = {}

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {'symbol': 'BTCUSDT', 'total_quantity': Decimal('0.1')}
    ]

    with patch('src.agents.risk_monitor.get_db_manager') as mock_db:
        mock_db.return_value.get_connection.return_value = mock_conn
        mock_db.return_value.release_connection = AsyncMock()

        with patch.object(risk_monitor, '_get_current_portfolio_value',
                         return_value=Decimal('10000')):
            # Should not crash when price is missing
            await risk_monitor._check_exposure()


@pytest.mark.asyncio
async def test_handles_database_errors(risk_monitor):
    """Test graceful handling of database errors"""
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = Exception("Database error")

    with patch('src.agents.risk_monitor.get_db_manager') as mock_db:
        mock_db.return_value.get_connection.return_value = mock_conn
        mock_db.return_value.release_connection = AsyncMock()

        # Should not crash on database error
        await risk_monitor._check_exposure()
        await risk_monitor._check_strategy_drawdowns()
