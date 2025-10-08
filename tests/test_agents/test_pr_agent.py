"""Tests for PR Agent"""
import pytest
import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.pr_agent import PRAgent
from src.models.events import (
    TradeExecutedEvent,
    AllocationEvent,
    RiskAlertEvent,
    ForkCreatedEvent
)


@pytest.fixture
def event_bus():
    bus = MagicMock()
    bus.subscribe = MagicMock(return_value=asyncio.Queue())
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_db():
    conn = AsyncMock()
    conn.execute = AsyncMock()

    manager = MagicMock()
    manager.get_connection = AsyncMock(return_value=conn)
    manager.release_connection = AsyncMock()
    return manager


@pytest.fixture
def pr_agent(event_bus, mock_db):
    return PRAgent(event_bus=event_bus, db_manager=mock_db)


def test_pr_agent_init(pr_agent):
    """Test PR agent initialization"""
    assert pr_agent.name == 'pr_agent'
    assert pr_agent.db is not None


@pytest.mark.asyncio
async def test_pr_agent_handles_trade_event(pr_agent):
    """Test PR agent processes trade events"""
    event = TradeExecutedEvent(
        strategy_name='momentum',
        symbol='BTCUSDT',
        side='buy',
        quantity=Decimal('0.5'),
        price=Decimal('50000'),
        fee=Decimal('25')
    )

    narrative = await pr_agent._generate_trade_narrative(event)

    assert narrative is not None
    assert 'momentum' in narrative.lower()
    assert 'buy' in narrative.lower() or 'bought' in narrative.lower()


@pytest.mark.asyncio
async def test_pr_agent_handles_allocation_event(pr_agent):
    """Test PR agent processes allocation events"""
    event = AllocationEvent(
        allocations={'momentum': 0.4, 'macd': 0.6},
        reason='Performance rebalance'
    )

    narrative = await pr_agent._generate_allocation_narrative(event)

    assert narrative is not None
    assert 'allocation' in narrative.lower() or 'rebalance' in narrative.lower()


@pytest.mark.asyncio
async def test_pr_agent_calculates_importance(pr_agent):
    """Test importance scoring"""
    # High importance: large trade
    high_event = TradeExecutedEvent(
        strategy_name='momentum',
        symbol='BTCUSDT',
        side='buy',
        quantity=Decimal('10.0'),  # Large
        price=Decimal('50000'),
        fee=Decimal('2500')
    )

    high_score = pr_agent._calculate_importance(high_event, 'trade')
    assert high_score >= 7

    # Low importance: small trade
    low_event = TradeExecutedEvent(
        strategy_name='momentum',
        symbol='BTCUSDT',
        side='buy',
        quantity=Decimal('0.01'),  # Small
        price=Decimal('50000'),
        fee=Decimal('0.25')
    )

    low_score = pr_agent._calculate_importance(low_event, 'trade')
    assert low_score <= 5


@pytest.mark.asyncio
async def test_pr_agent_stores_narrative(pr_agent, mock_db):
    """Test narrative storage in database"""
    await pr_agent._store_narrative(
        narrative="Test narrative",
        category="test",
        importance=5,
        strategy=None,
        metadata=None
    )

    # Verify database insert was called
    pr_agent.db.get_connection.assert_called_once()
    conn = await pr_agent.db.get_connection()
    conn.execute.assert_called_once()
