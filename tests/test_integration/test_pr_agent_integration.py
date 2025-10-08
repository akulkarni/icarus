"""Integration tests for PR Agent"""
import pytest
import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from src.agents.pr_agent import PRAgent
from src.core.event_bus import EventBus
from src.models.events import TradeExecutedEvent


@pytest.fixture
def mock_db():
    """Mock database manager for testing"""
    conn = AsyncMock()
    conn.execute = AsyncMock()

    manager = MagicMock()
    manager.get_connection = AsyncMock(return_value=conn)
    manager.release_connection = AsyncMock()
    return manager


@pytest.mark.asyncio
async def test_pr_agent_end_to_end(mock_db):
    """Test PR agent processes events end-to-end"""
    event_bus = EventBus()
    pr_agent = PRAgent(event_bus, mock_db)

    # Start agent
    agent_task = asyncio.create_task(pr_agent.run())

    # Give it time to start
    await asyncio.sleep(0.1)

    # Publish event
    await event_bus.publish(TradeExecutedEvent(
        strategy_name='momentum',
        symbol='BTCUSDT',
        side='buy',
        quantity=Decimal('1.0'),
        price=Decimal('50000'),
        fee=Decimal('25')
    ))

    # Give it time to process
    await asyncio.sleep(0.2)

    # Stop agent
    await pr_agent.stop()

    try:
        await asyncio.wait_for(agent_task, timeout=1.0)
    except asyncio.TimeoutError:
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass

    # Verify database was called
    assert mock_db.get_connection.called
