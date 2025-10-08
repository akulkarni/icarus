"""Tests for Binance API integration"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock
from binance.exceptions import BinanceAPIException


@pytest.fixture
def mock_binance_client():
    """Mock Binance client"""
    client = MagicMock()

    # Mock get_account for connection verification
    client.get_account = MagicMock(return_value={'accountType': 'SPOT'})

    # Mock successful order response
    client.order_market_buy = MagicMock(return_value={
        'orderId': 12345,
        'symbol': 'BTCUSDT',
        'executedQty': '0.5',
        'fills': [{
            'price': '50000.00',
            'qty': '0.5',
            'commission': '25.00',
            'commissionAsset': 'USDT'
        }]
    })

    client.order_market_sell = MagicMock(return_value={
        'orderId': 12346,
        'symbol': 'BTCUSDT',
        'executedQty': '0.5',
        'fills': [{
            'price': '50100.00',
            'qty': '0.5',
            'commission': '25.05',
            'commissionAsset': 'USDT'
        }]
    })

    return client


def test_binance_client_initialization():
    """Test Binance client can be initialized with mocking"""
    # This test verifies that we can mock the Binance client
    # In real usage, you would use actual API credentials on testnet
    with patch('binance.client.Client') as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        from binance.client import Client
        client = Client(api_key='test', api_secret='test', testnet=True)
        assert client is not None


@pytest.mark.asyncio
async def test_real_order_execution_buy(mock_binance_client):
    """Test real buy order execution"""
    from src.agents.execution import TradeExecutionAgent
    from src.models.events import TradingSignalEvent

    event_bus = MagicMock()
    event_bus.publish = AsyncMock()

    config = {
        'trading': {'mode': 'real'},
        'binance': {'api_key': 'test', 'api_secret': 'test', 'testnet': True}
    }

    # Mock the Binance client initialization
    with patch('src.agents.execution.BinanceClient') as mock_client_class:
        mock_client_class.return_value = mock_binance_client

        agent = TradeExecutionAgent(event_bus, Decimal('10000'), config)

        signal = TradingSignalEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy'
        )

        # Initialize portfolio and add some price data
        agent.strategy_portfolios['momentum'] = {'cash': Decimal('10000'), 'positions': {}}
        agent.current_prices['BTCUSDT'] = Decimal('50000')

        await agent._execute_order_real(signal, Decimal('0.5'), agent.strategy_portfolios['momentum'])

        # Verify Binance API was called
        mock_binance_client.order_market_buy.assert_called_once()

        # Verify trade event published
        event_bus.publish.assert_called()


@pytest.mark.asyncio
async def test_real_order_execution_sell(mock_binance_client):
    """Test real sell order execution"""
    from src.agents.execution import TradeExecutionAgent
    from src.models.events import TradingSignalEvent

    event_bus = MagicMock()
    event_bus.publish = AsyncMock()

    config = {
        'trading': {'mode': 'real'},
        'binance': {'api_key': 'test', 'api_secret': 'test', 'testnet': True}
    }

    # Mock the Binance client initialization
    with patch('src.agents.execution.BinanceClient') as mock_client_class:
        mock_client_class.return_value = mock_binance_client

        agent = TradeExecutionAgent(event_bus, Decimal('10000'), config)

        signal = TradingSignalEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='sell'
        )

        # Initialize portfolio and add some price data
        agent.strategy_portfolios['momentum'] = {'cash': Decimal('10000'), 'positions': {'BTCUSDT': Decimal('1.0')}}
        agent.current_prices['BTCUSDT'] = Decimal('50000')

        await agent._execute_order_real(signal, Decimal('0.5'), agent.strategy_portfolios['momentum'])

        # Verify Binance API was called
        mock_binance_client.order_market_sell.assert_called_once()

        # Verify trade event published
        event_bus.publish.assert_called()


@pytest.mark.asyncio
async def test_binance_api_error_handling(mock_binance_client):
    """Test handling of Binance API errors"""
    from src.agents.execution import TradeExecutionAgent
    from src.models.events import TradingSignalEvent

    event_bus = MagicMock()
    event_bus.publish = AsyncMock()

    config = {
        'trading': {'mode': 'real'},
        'binance': {'api_key': 'test', 'api_secret': 'test', 'testnet': True}
    }

    # Mock the Binance client initialization
    with patch('src.agents.execution.BinanceClient') as mock_client_class:
        mock_client_class.return_value = mock_binance_client

        agent = TradeExecutionAgent(event_bus, Decimal('10000'), config)

        # Create a proper mock response for the exception
        mock_response = MagicMock()
        mock_response.text = '{"code":-2010,"msg":"Insufficient balance"}'

        # Mock API error
        api_exception = BinanceAPIException(mock_response, -2010, mock_response.text)
        mock_binance_client.order_market_buy.side_effect = api_exception

        signal = TradingSignalEvent(
            strategy_name='momentum',
            symbol='BTCUSDT',
            side='buy'
        )

        # Initialize portfolio
        agent.strategy_portfolios['momentum'] = {'cash': Decimal('10000'), 'positions': {}}

        # Should not raise, but handle gracefully
        await agent._execute_order_real(signal, Decimal('0.5'), agent.strategy_portfolios['momentum'])

        # Should publish error event
        assert event_bus.publish.called
