"""
Tests for event models
"""
import pytest
from decimal import Decimal
from datetime import datetime
from uuid import UUID

from src.models.events import (
    Event,
    MarketTickEvent,
    TradingSignalEvent,
    TradeExecutedEvent,
    PositionOpenedEvent,
    AllocationEvent,
    ForkRequestEvent,
    RiskAlertEvent,
    AgentStartedEvent,
    get_event_type,
    EVENT_TYPES
)


class TestBaseEvent:
    """Test base Event class"""

    def test_event_has_id_and_timestamp(self):
        """Test that events have ID and timestamp"""
        event = Event()
        assert isinstance(event.event_id, UUID)
        assert isinstance(event.timestamp, datetime)

    def test_event_is_immutable(self):
        """Test that events are frozen (immutable)"""
        event = Event()
        with pytest.raises(Exception):  # FrozenInstanceError
            event.event_id = None

    def test_event_to_dict(self):
        """Test event serialization"""
        event = Event()
        data = event.to_dict()
        assert 'event_id' in data
        assert 'timestamp' in data
        assert isinstance(data['event_id'], str)
        assert isinstance(data['timestamp'], str)


class TestMarketDataEvents:
    """Test market data events"""

    def test_market_tick_event(self):
        """Test MarketTickEvent creation"""
        event = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000.00'),
            volume=Decimal('1.5'),
            bid=Decimal('49999.00'),
            ask=Decimal('50001.00')
        )

        assert event.symbol == 'BTCUSDT'
        assert event.price == Decimal('50000.00')
        assert event.volume == Decimal('1.5')
        assert event.bid == Decimal('49999.00')
        assert event.ask == Decimal('50001.00')

    def test_market_tick_to_dict(self):
        """Test MarketTickEvent serialization"""
        event = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000.00'),
            volume=Decimal('1.5')
        )
        data = event.to_dict()

        assert data['symbol'] == 'BTCUSDT'
        assert data['price'] == 50000.00
        assert data['volume'] == 1.5


class TestTradingSignalEvents:
    """Test trading signal events"""

    def test_trading_signal_event(self):
        """Test TradingSignalEvent creation"""
        event = TradingSignalEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            confidence=Decimal('0.75'),
            reason='MA crossover detected'
        )

        assert event.strategy_name == 'momentum'
        assert event.symbol == 'BTCUSDT'
        assert event.side == 'buy'
        assert event.confidence == Decimal('0.75')
        assert event.reason == 'MA crossover detected'

    def test_trading_signal_with_metadata(self):
        """Test TradingSignalEvent with metadata"""
        metadata = {'ma_short': 20, 'ma_long': 50}
        event = TradingSignalEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            confidence=Decimal('0.75'),
            reason='MA crossover',
            metadata=metadata
        )

        assert event.metadata == metadata


class TestTradeExecutionEvents:
    """Test trade execution events"""

    def test_trade_executed_event(self):
        """Test TradeExecutedEvent creation"""
        event = TradeExecutedEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy',
            quantity=Decimal('0.5'),
            price=Decimal('50000.00'),
            fee=Decimal('25.00'),
            trade_mode='paper'
        )

        assert event.strategy_name == 'momentum'
        assert event.symbol == 'BTCUSDT'
        assert event.side == 'buy'
        assert event.quantity == Decimal('0.5')
        assert event.price == Decimal('50000.00')
        assert event.fee == Decimal('25.00')
        assert event.trade_mode == 'paper'


class TestPositionEvents:
    """Test position events"""

    def test_position_opened_event(self):
        """Test PositionOpenedEvent creation"""
        event = PositionOpenedEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            quantity=Decimal('0.5'),
            entry_price=Decimal('50000.00')
        )

        assert event.strategy_name == 'momentum'
        assert event.symbol == 'BTCUSDT'
        assert event.quantity == Decimal('0.5')
        assert event.entry_price == Decimal('50000.00')
        assert isinstance(event.position_id, UUID)


class TestMetaStrategyEvents:
    """Test meta-strategy events"""

    def test_allocation_event(self):
        """Test AllocationEvent creation"""
        allocations = {'momentum': 50.0, 'macd': 50.0}
        event = AllocationEvent(
            allocations=allocations,
            reason='Initial equal weighting'
        )

        assert event.allocations == allocations
        assert event.reason == 'Initial equal weighting'

    def test_allocation_event_to_dict(self):
        """Test AllocationEvent serialization"""
        allocations = {'momentum': 50.0, 'macd': 50.0}
        event = AllocationEvent(allocations=allocations, reason='Test')
        data = event.to_dict()

        assert data['allocations'] == allocations


class TestForkManagementEvents:
    """Test fork management events"""

    def test_fork_request_event(self):
        """Test ForkRequestEvent creation"""
        event = ForkRequestEvent(
            requesting_agent='backtest',
            purpose='parameter optimization',
            ttl_seconds=7200
        )

        assert event.requesting_agent == 'backtest'
        assert event.purpose == 'parameter optimization'
        assert event.ttl_seconds == 7200


class TestRiskManagementEvents:
    """Test risk management events"""

    def test_risk_alert_event(self):
        """Test RiskAlertEvent creation"""
        event = RiskAlertEvent(
            alert_type='daily_loss',
            severity='warning',
            strategy_name='momentum',
            message='Daily loss approaching 5% limit',
            current_value=Decimal('4.5'),
            threshold_value=Decimal('5.0')
        )

        assert event.alert_type == 'daily_loss'
        assert event.severity == 'warning'
        assert event.strategy_name == 'momentum'
        assert event.current_value == Decimal('4.5')
        assert event.threshold_value == Decimal('5.0')


class TestAgentEvents:
    """Test agent lifecycle events"""

    def test_agent_started_event(self):
        """Test AgentStartedEvent creation"""
        config = {'symbol': 'BTCUSDT', 'ma_period': 20}
        event = AgentStartedEvent(
            agent_name='momentum',
            config=config
        )

        assert event.agent_name == 'momentum'
        assert event.config == config


class TestEventTypeRegistry:
    """Test event type registry and utilities"""

    def test_event_type_registry_completeness(self):
        """Test that all event types are registered"""
        assert 'MarketTickEvent' in EVENT_TYPES
        assert 'TradingSignalEvent' in EVENT_TYPES
        assert 'TradeExecutedEvent' in EVENT_TYPES
        assert 'AllocationEvent' in EVENT_TYPES
        assert 'ForkRequestEvent' in EVENT_TYPES
        assert 'RiskAlertEvent' in EVENT_TYPES

    def test_get_event_type(self):
        """Test get_event_type function"""
        event = MarketTickEvent(
            symbol='BTCUSDT',
            price=Decimal('50000.00'),
            volume=Decimal('1.0')
        )

        assert get_event_type(event) == 'MarketTickEvent'

    def test_event_types_are_classes(self):
        """Test that EVENT_TYPES contains actual classes"""
        for event_name, event_class in EVENT_TYPES.items():
            assert callable(event_class)
            assert event_name == event_class.__name__


class TestEventDefaults:
    """Test event default values"""

    def test_market_tick_defaults(self):
        """Test MarketTickEvent defaults"""
        event = MarketTickEvent()
        assert event.symbol == ""
        assert event.price == Decimal('0')
        assert event.volume == Decimal('0')
        assert event.bid is None
        assert event.ask is None

    def test_trading_signal_defaults(self):
        """Test TradingSignalEvent defaults"""
        event = TradingSignalEvent()
        assert event.strategy_name == ""
        assert event.symbol == ""
        assert event.side == ""
        assert event.confidence == Decimal('0')
        assert event.metadata is None
