"""Test API endpoints with mocked database"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_db_manager():
    """Mock database manager"""
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])

    mock_manager = MagicMock()
    mock_manager.get_connection = AsyncMock(return_value=mock_conn)
    mock_manager.release_connection = AsyncMock()

    return mock_manager


def test_portfolio_endpoint(mock_db_manager):
    """Test portfolio endpoint returns data"""
    # Create mock connection with specific responses for positions and performance
    mock_conn = AsyncMock()

    # Mock fetch to return positions first, then performance
    call_count = [0]
    async def mock_fetch(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:  # First call - positions
            return []
        else:  # Second call - performance
            return [
                {
                    'strategy_name': 'momentum',
                    'portfolio_value': 10500.0,
                    'cash_balance': 1000.0,
                    'total_pnl': 500.0,
                    'allocation_pct': 50.0,
                    'is_active': True
                }
            ]

    mock_conn.fetch = mock_fetch
    mock_db_manager.get_connection.return_value = mock_conn

    from src.web.api import app
    # Make get_db_manager return an awaitable
    async def mock_get_db_manager():
        return mock_db_manager

    with patch('src.web.api.get_db_manager', side_effect=mock_get_db_manager):
        client = TestClient(app)
        response = client.get("/api/portfolio")

        assert response.status_code == 200
        data = response.json()
        assert 'strategies' in data
        assert 'positions' in data
        assert 'timestamp' in data
