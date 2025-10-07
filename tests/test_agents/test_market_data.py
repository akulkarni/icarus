"""
Tests for Market Data Agent
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from src.agents.market_data import MarketDataAgent
from src.core.event_bus import EventBus
from src.models.events import MarketTickEvent


@pytest.fixture
def event_bus():
    """Create event bus for testing"""
    return EventBus()


@pytest.fixture
def market_data_agent(event_bus):
    """Create market data agent for testing"""
    return MarketDataAgent(event_bus, ['BTCUSDT'])


@pytest.mark.asyncio
async def test_market_data_agent_initialization(event_bus):
    """Test that market data agent initializes correctly"""
    agent = MarketDataAgent(event_bus, ['BTCUSDT', 'ETHUSDT'])
    assert agent.name == "market_data"
    assert agent.symbols == ['BTCUSDT', 'ETHUSDT']
    assert agent.client is None
    assert agent.bm is None


@pytest.mark.asyncio
async def test_market_data_publishes_events(event_bus, market_data_agent):
    """Test that market data agent publishes tick events"""
    # Subscribe to market tick events
    queue = event_bus.subscribe(MarketTickEvent)

    # Mock Binance WebSocket message
    mock_message = {
        'c': '50000.00',  # Last price
        'v': '1000.50'    # Volume
    }

    # Create a mock async context manager for the websocket
    mock_socket = MagicMock()
    mock_socket.__aenter__ = AsyncMock(return_value=mock_socket)
    mock_socket.__aexit__ = AsyncMock()
    mock_socket.recv = AsyncMock(side_effect=[mock_message, asyncio.CancelledError()])

    # Mock BinanceSocketManager
    with patch('src.agents.market_data.AsyncClient.create') as mock_client_create, \
         patch('src.agents.market_data.BinanceSocketManager') as mock_bsm:

        mock_client = AsyncMock()
        mock_client_create.return_value = mock_client

        mock_manager = MagicMock()
        mock_manager.symbol_ticker_socket.return_value = mock_socket
        mock_bsm.return_value = mock_manager

        # Start agent in background
        agent_task = asyncio.create_task(market_data_agent.start())

        # Wait for event
        try:
            event = await asyncio.wait_for(queue.get(), timeout=2.0)

            # Verify event
            assert isinstance(event, MarketTickEvent)
            assert event.symbol == 'BTCUSDT'
            assert event.price == Decimal('50000.00')
            assert event.volume == Decimal('1000.50')

        finally:
            # Cleanup
            agent_task.cancel()
            try:
                await agent_task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_market_data_handles_multiple_symbols(event_bus):
    """Test that agent can handle multiple symbols"""
    agent = MarketDataAgent(event_bus, ['BTCUSDT', 'ETHUSDT'])

    # Subscribe to events
    queue = event_bus.subscribe(MarketTickEvent)

    # Mock WebSocket for multiple symbols
    with patch('src.agents.market_data.AsyncClient.create') as mock_client_create, \
         patch('src.agents.market_data.BinanceSocketManager') as mock_bsm:

        mock_client = AsyncMock()
        mock_client_create.return_value = mock_client

        # Create separate mocks for each symbol
        mock_sockets = []
        for symbol in ['BTCUSDT', 'ETHUSDT']:
            mock_socket = MagicMock()
            mock_socket.__aenter__ = AsyncMock(return_value=mock_socket)
            mock_socket.__aexit__ = AsyncMock()
            mock_socket.recv = AsyncMock(side_effect=[
                {'c': '50000.00', 'v': '1000.50'},
                asyncio.CancelledError()
            ])
            mock_sockets.append(mock_socket)

        mock_manager = MagicMock()
        mock_manager.symbol_ticker_socket.side_effect = mock_sockets
        mock_bsm.return_value = mock_manager

        # Start agent
        agent_task = asyncio.create_task(agent.start())

        try:
            # Should receive events for both symbols
            events = []
            for _ in range(2):
                event = await asyncio.wait_for(queue.get(), timeout=2.0)
                events.append(event)

            assert len(events) == 2

        finally:
            agent_task.cancel()
            try:
                await agent_task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_market_data_error_handling(event_bus, market_data_agent):
    """Test that agent handles errors gracefully"""
    mock_socket = MagicMock()
    mock_socket.__aenter__ = AsyncMock(return_value=mock_socket)
    mock_socket.__aexit__ = AsyncMock()

    # Simulate error then success
    mock_socket.recv = AsyncMock(side_effect=[
        Exception("Connection error"),
        {'c': '50000.00', 'v': '1000.50'},
        asyncio.CancelledError()
    ])

    with patch('src.agents.market_data.AsyncClient.create') as mock_client_create, \
         patch('src.agents.market_data.BinanceSocketManager') as mock_bsm:

        mock_client = AsyncMock()
        mock_client_create.return_value = mock_client

        mock_manager = MagicMock()
        mock_manager.symbol_ticker_socket.return_value = mock_socket
        mock_bsm.return_value = mock_manager

        agent_task = asyncio.create_task(market_data_agent.start())

        # Agent should continue after error
        await asyncio.sleep(0.5)

        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
