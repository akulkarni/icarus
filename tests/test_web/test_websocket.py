"""Test WebSocket functionality"""
import pytest
import asyncio
from fastapi.testclient import TestClient


def test_websocket_connection():
    """Test WebSocket connection can be established"""
    from src.web.api import app
    client = TestClient(app)

    with client.websocket_connect("/ws") as websocket:
        # Connection should be accepted
        assert websocket is not None


def test_websocket_disconnect():
    """Test WebSocket handles disconnect gracefully"""
    from src.web.api import app
    client = TestClient(app)

    # Connect and disconnect
    with client.websocket_connect("/ws") as websocket:
        pass  # Auto-disconnects after context

    # Should not raise exception
    assert True
